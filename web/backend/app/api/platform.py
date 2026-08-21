"""平台链路路由：健康检查 / 认证 / BYOK Key / 意图解析 / 上传 / 用量 / 判断复利闭环 / 异步评审。

这些是"预埋线"的对外出口。原有 /api 业务路由（personas、task-types 等）不受影响。
"""

import ipaddress
import os
import re
import socket
import uuid
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.config import settings
from app.core.errors import AppError, BadRequest, NotFound, Unauthorized
from app.core.logging import logger
from app.core.security import create_token, hash_password, verify_password
from app.db import get_db
from app.deps import (
    Identity,
    is_shared_anonymous,
    optional_identity,
    probe_identity,
    rate_limit,
    require_isolated_identity,
    resolve_llm_key,
    issue_session_token,
    revoke_user_sessions,
)
from app.models import Job, Review, User
from app.services import (
    admin_settings_service,
    intent_service,
    job_service,
    key_service,
    ledger_service,
    plan_service,
    project_memory_service,
    quota_service,
    report_gating,
    review_service,
    share_service,
    validation_service,
)

router = APIRouter()


# ============================== 健康检查 ==============================

@router.get("/health")
async def health(db: Session = Depends(get_db)):
    """探活 + 当前生效的链路开关（绝不泄露密钥）。

    这条**不做依赖探测**（不判断数据库健不健康），是纯进程存活语义，
    用于容器 healthcheck 之类"进程还在不在"的场景。要判断"服务是不是
    真的能用"，用 /health/ready。

    但它确实要读一次库，因为下面两项能在后台面板运行时覆盖：

      · key_mode           —— admin_settings 表里的覆盖值（key_service.resolve_key
                              读的就是它，不是 env）
      · server_key_present —— 后台面板设的平台 key 存在**数据库**里
                              （PLATFORM_KEY_OWNER 那行），而 settings.server_llm_key
                              只是 env 里的 ANTHROPIC_API_KEY

    不合成的话会出现这个具体故障：运营在后台配好平台 key、把 key_mode 切成
    managed，前端拿到的仍是启动时的快照（byok / server_key_present=false），
    于是 session-store 的 canReview() 判定为 false，"发起评审"按钮是灰的——
    而后端 resolve_key 明明已经能解析出 key，跑得起来。
    后台点了没反应、又没有任何报错，是最难排查的一类。

    读库失败不该让存活探测跟着失败（那是 /health/ready 的职责），
    所以这里回落到 env 快照并打日志。
    """
    config = settings.sanitized()
    try:
        config["key_mode"] = admin_settings_service.get(db, "key_mode", settings.key_mode)
        config["server_key_present"] = bool(
            settings.server_llm_key or key_service.get_platform_key_status(db)
        )
    except Exception as exc:  # noqa: BLE001  存活探测不因读库失败而失败
        logger.warning("health: 读运行时覆盖值失败，回落 env 快照：%s", exc)
    return {"status": "ok", "config": config}


@router.get("/health/ready")
async def health_ready(db: Session = Depends(get_db)):
    """就绪探测：真的打一次数据库，不可用时返回 503。

    为什么需要单独一条：上面的 /health 返回的 "ok" 是写死的字符串，
    数据库挂掉、磁盘满、连接池耗尽时它**照样 200**。拿它接 UptimeRobot
    这类外部监控，监控到的只是"uvicorn 进程还活着"——而用户看到的是
    每个页面都在报错。这正是"监控一片绿、服务全挂"的经典形态。

    刻意只查数据库，不查上游模型服务商：
      · 上游是按调用计费的，健康检查每分钟打一次会产生真实账单
      · 上游抖动不该让本服务被判定为宕机（评审会失败，但站点是能用的）
    上游的可用性通过后台「系统健康度」的失败率趋势事后观察，不做实时探测。

    不需要鉴权：外部监控探针没有令牌，加了鉴权就没法用了。
    响应里也刻意不含任何业务数据，只有 ok/error 两种形态。
    """
    try:
        # SELECT 1 是最轻的连通性探测：不读表、不加锁、不受数据量影响。
        # 用 text() 显式包一层——SQLAlchemy 2.x 不再接受裸字符串 SQL。
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001  连通性探测要抓所有异常
        # 把异常类型带出去（不带消息——消息里可能有连接串/主机名）。
        # 监控告警里能看到 OperationalError 还是 TimeoutError，排查方向完全不同。
        logger.error("readiness probe failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "checks": {"database": type(exc).__name__}},
        )
    return {"status": "ok", "checks": {"database": "ok"}}


# ============================== 认证（埋线）==============================

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


def _require_auth_enabled():
    if not settings.auth_enabled:
        raise BadRequest(
            "认证未启用（当前为匿名/开源形态）。设置 AL_AUTH_ENABLED=true 后此接口生效。"
        )


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# scope 用 "auth_register" 而不是共用的 "auth"：限流桶的 key 是 scope + 主体，
# 三个认证接口以前共用 "auth" 桶，而令牌桶取 min(limit, ...) —— 注册那个 10
# 会把登录的 20 一起压成 10，且额度是共享的。实测"连注册 12 次后，一个从未
# 登录过的合法账号直接 429"：注册把登录的额度吃光了。
# 把注册单独分桶后，刷注册只会封住注册，不再连坐登录。
@router.post("/auth/register", dependencies=[Depends(rate_limit("auth_register", 10, 3600))])
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    _require_auth_enabled()
    email = body.email.strip().lower()
    # 之前 email 字段裸收字符串，"abc" 也能注册成功——落库一个永远收不到任何
    # 通知、也无法找回的账号标识。宽松格式校验兜底（不追求 RFC 完备）。
    if not _EMAIL_RE.match(email) or len(email) > 254:
        raise BadRequest("邮箱格式不正确")
    if db.query(User).filter(User.email == email).first():
        # 不说"已注册"——那等于替枚举者确认这个邮箱存在账号
        raise BadRequest("该邮箱不可用，请更换邮箱；若已有账号请直接登录")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        display_name=body.display_name or email.split("@")[0],
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # 上面的预检只挡顺序请求；并发注册同邮箱时两个请求都能通过预检，
        # 靠 users.email 的唯一约束兜底。不捕获的话这里就是 500——
        # 而"这个邮箱注册过"是一个业务结果，应该和预检拦截返回同一个 400。
        db.rollback()
        raise BadRequest("该邮箱不可用，请更换邮箱；若已有账号请直接登录")
    db.refresh(user)
    await _send_verify_email(db, user)  # 失败不抛，注册本身不受影响
    token = issue_session_token(db, user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "plan": user.plan}}


@router.post("/auth/login", dependencies=[Depends(rate_limit("auth", 20, 3600))])
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    _require_auth_enabled()
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user:
        # 对不存在的邮箱也算一次哈希——抹平"跳过验证"带来的响应时长差，
        # 否则计时攻击能区分邮箱是否注册过
        verify_password(body.password, hash_password("timing-equalizer"))
        raise Unauthorized("邮箱或密码错误")
    if not verify_password(body.password, user.password_hash):
        raise Unauthorized("邮箱或密码错误")
    if not user.is_active:
        raise Unauthorized("账号已停用")
    token = issue_session_token(db, user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "plan": user.plan}}


@router.get("/auth/me")
async def me(identity: Identity = Depends(probe_identity)):
    """「我是谁」。用 probe_identity 而不是 optional_identity：
    别的接口遇到失效令牌一律 401，唯独这一条要返回 200 + session_expired=true，
    前端才有机会把烂 token 清掉并提示"登录已过期"（见 deps.probe_identity）。"""
    return identity.to_dict()


# ---------- 邮箱验证 / 忘记密码 ----------
# 未验证邮箱不挡住上手（注册即可用），但要给用户机会确认邮箱是真的——
# 否则填错邮箱自己不知道，等到要找回密码时才发现联系不上，为时已晚。


async def _send_mail_off_loop(to: str, subject: str, body: str) -> None:
    """把发信丢到线程池，绝不在事件循环里做同步 SMTP。

    mail_service.send_mail 内部是同步 smtplib：建连、TLS 握手、认证、投递，
    每一步都可能卡住几十秒（邮件服务商限流、DNS 慢、网络抖动，超时甚至更久）。
    在 async 路由里直接调它，卡住的不是这一个请求，而是**整个事件循环**——
    单 worker 进程下全站所有用户的请求一起排队等这封邮件，看起来就是"网站挂了"。
    注册和忘记密码都是未登录就能打的接口，等于任何人都能触发这个停顿。

    发信失败不外抛：注册/找回本身已经成功，不能因为发信失败把用户挡在门外
    （原来的调用点也是这个语义，这里保持不变，只是补上日志——
    以前失败是彻底静默的，运维根本不知道邮件没发出去）。
    """
    from starlette.concurrency import run_in_threadpool

    from app.services import mail_service

    try:
        await run_in_threadpool(mail_service.send_mail, to, subject, body)
    except Exception as exc:  # noqa: BLE001 —— 发信失败不该影响主流程
        logger.warning("发信失败 | 收件人=%s | 主题=%s | %s", to, subject, exc)


async def _send_verify_email(db: Session, user: User) -> None:
    from app.services import auth_token_service

    raw = auth_token_service.issue(
        db, user.id, auth_token_service.PURPOSE_VERIFY_EMAIL, settings.email_token_ttl_seconds
    )
    link = f"{settings.public_web_url}/verify-email?token={raw}"
    await _send_mail_off_loop(
        user.email,
        "验证你的 AudienceLens 邮箱",
        f"点击链接完成邮箱验证（{settings.email_token_ttl_seconds // 3600} 小时内有效）：\n{link}\n\n"
        "如果不是你本人操作，忽略这封邮件即可。",
    )


@router.post("/auth/verify-email/send", dependencies=[Depends(rate_limit("auth_mail", 5, 3600))])
async def send_verify_email(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    _require_auth_enabled()
    if identity.is_anonymous:
        raise Unauthorized("请先登录")
    user = db.get(User, identity.user_id)
    if not user:
        raise NotFound("账号不存在")
    if user.email_verified_at:
        return {"sent": False, "detail": "邮箱已验证"}
    # 这里**不能**复用注册那条"失败也吞掉"的路径。注册时吞是对的（注册本身
    # 已经成功，不该因为邮件服务商抽风把用户挡在门外）；但这个接口是用户
    # 亲手点了「重新发送」，这一次点击的全部目的就是把信发出去。失败还回
    # sent:true，用户会守着收件箱空等，然后反复点，把发信配额打满。
    #
    # 曾经就是这样：_send_mail_off_loop 吞掉异常，这里写死 sent:True，
    # 于是 SMTP 报 550 被拒、日志里明明白白记了一行 WARNING，前端照样显示
    # "已发送，请查收"。
    from starlette.concurrency import run_in_threadpool

    from app.services import auth_token_service, mail_service
    from app.services.mail_service import MailError

    raw = auth_token_service.issue(
        db, user.id, auth_token_service.PURPOSE_VERIFY_EMAIL, settings.email_token_ttl_seconds
    )
    link = f"{settings.public_web_url}/verify-email?token={raw}"
    try:
        await run_in_threadpool(
            mail_service.send_mail_strict,
            user.email,
            "验证你的 AudienceLens 邮箱",
            f"点击链接完成邮箱验证（{settings.email_token_ttl_seconds // 3600} 小时内有效）：\n{link}\n\n"
            "如果不是你本人操作，忽略这封邮件即可。",
        )
    except MailError as exc:
        # 真实原因进日志给运维；返回给用户的是一句他能行动的话。
        # mail_service 的错误文案是写给运维看的（会点名 AL_SMTP_* 该改哪一项），
        # 直接吐给终端用户既没用又泄露部署细节。
        logger.warning("重发验证邮件失败 | 收件人=%s | %s", user.email, exc)
        return {"sent": False, "detail": "邮件发送失败，请稍后再试；若持续失败请联系我们"}
    return {"sent": True}


class TokenBody(BaseModel):
    token: str


@router.post("/auth/verify-email/confirm")
async def confirm_verify_email(body: TokenBody, db: Session = Depends(get_db)):
    _require_auth_enabled()
    from app.services import auth_token_service

    user_id = auth_token_service.consume(
        db, body.token, auth_token_service.PURPOSE_VERIFY_EMAIL
    )
    if not user_id:
        raise BadRequest("验证链接无效或已过期，请重新发送")
    user = db.get(User, user_id)
    if not user:
        raise BadRequest("验证链接无效或已过期，请重新发送")
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return {"verified": True, "email": user.email}


class ForgotPasswordRequest(BaseModel):
    email: str


@router.post("/auth/password/forgot", dependencies=[Depends(rate_limit("auth_mail", 5, 3600))])
async def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """无论邮箱是否注册过都返回同样的成功响应——否则这个接口就成了
    "这个邮箱有没有注册"的枚举器（与注册接口同一套防枚举口径）。"""
    _require_auth_enabled()
    from app.services import auth_token_service

    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user and user.is_active:
        raw = auth_token_service.issue(
            db, user.id, auth_token_service.PURPOSE_RESET_PASSWORD,
            settings.reset_token_ttl_seconds,
        )
        link = f"{settings.public_web_url}/reset-password?token={raw}"
        await _send_mail_off_loop(
            user.email,
            "重置你的 AudienceLens 密码",
            f"点击链接重置密码（{settings.reset_token_ttl_seconds // 60} 分钟内有效，只能用一次）：\n{link}\n\n"
            "如果不是你本人操作，忽略这封邮件即可，你的密码不会有任何变化。",
        )
    return {"sent": True, "detail": "如果该邮箱已注册，重置链接已发送"}


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


@router.post("/auth/password/reset")
async def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    _require_auth_enabled()
    from app.services import auth_token_service

    user_id = auth_token_service.consume(
        db, body.token, auth_token_service.PURPOSE_RESET_PASSWORD
    )
    if not user_id:
        raise BadRequest("重置链接无效或已过期，请重新申请")
    user = db.get(User, user_id)
    if not user:
        raise BadRequest("重置链接无效或已过期，请重新申请")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    # 改完密码必须把已签发的 JWT 一并作废，否则"改密码"对已经发生的入侵毫无作用：
    # 攻击者手上那把在改密码之前偷到的 token 是自签 JWT，只认签名和 exp，
    # 密码换了它照样通行，最长能再用满一个 TTL（默认 7 天）——而用户以为自己
    # 已经把人赶出去了。这也是"找回密码"这条路径存在的意义之一。
    # 代价：本人在其他设备上的登录态同样失效，需要重新登录。这是应该的。
    revoke_user_sessions(db, user.id)
    # 不自动登录：重置成功后让用户用新密码走一次正常登录，
    # 免得链接被中途截获的人直接拿到会话。
    return {"reset": True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/auth/password/change", dependencies=[Depends(rate_limit("auth", 20, 3600))])
async def change_password(
    body: ChangePasswordRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """已登录改密码。

    在此之前**根本没有这个接口**：登录着的用户想改密码，唯一的路是退出登录 →
    忘记密码 → 收邮件 → 点链接重置。而邮件链路在很多部署里压根没配通
    （AL_SMTP_* 是空的、启动自检只是告警不拒启），两件事叠在一起的实际效果是
    「密码不可更改」——包括怀疑自己密码泄露时也改不了。

    必须验旧密码：只凭一把 JWT 就能换密码的话，任何偷到令牌的人都能把账号
    永久夺走（改完密码原主人再也登不进去），令牌泄露从"临时冒用"升级成"彻底丢号"。

    改完同样要 revoke_user_sessions——理由和密码重置那条完全一样：JWT 是自签的，
    只认签名和 exp，密码换了旧令牌照样通行满一个 TTL（默认 7 天）。不撤销的话
    "改密码"对已经发生的入侵毫无作用。
    """
    _require_auth_enabled()
    _require_own_identity(identity)
    user = db.get(User, identity.user_id)
    if not user:
        raise NotFound("账号不存在")
    if not verify_password(body.current_password, user.password_hash):
        raise Unauthorized("当前密码不正确")
    if verify_password(body.new_password, user.password_hash):
        raise BadRequest("新密码不能与当前密码相同")

    user.password_hash = hash_password(body.new_password)
    db.commit()
    revoke_user_sessions(db, user.id)
    # 顺序要紧：先撤销、再签发。但**只靠顺序不够**——撤销点是向上取整到整秒的
    # （deps.sessions_revoked_at，这样同一秒内被盗的令牌才会真的失效），
    # 而自然签发的 iat 取的是当前整秒，必定落在撤销点之前，新令牌会被自己
    # 那次撤销当场杀掉。所以要把撤销点原样读回来传给 create_token。
    # 这两处是一对：改任何一处都会退化——要么被盗令牌活满 7 天，要么用户
    # 改完密码当场掉线。
    token = issue_session_token(db, user.id)
    # 换新令牌让**本设备**继续用，其他设备上的旧会话则已作废。
    # 这正是改密码该有的语义：把别人踢出去，自己不用重登。
    return {"changed": True, "token": token}


@router.post("/auth/sessions/revoke-all", dependencies=[Depends(rate_limit("auth", 20, 3600))])
async def revoke_all_sessions(
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """登出所有设备：作废该账号当前已签发的全部 JWT。

    为什么单独给一个入口，而不是让用户去改密码：
    用户怀疑账号被盗时，第一反应是"把别人踢下线"，而改密码要求他先想出并
    记住一个新密码——多一道摩擦，且在慌乱时最容易被拖延。撤销会话是止血，
    改密码是治本，两件事不该被绑成一件。

    这个能力对 BYOK 用户尤其重要：账号里存着他自己的模型 API Key，
    会话被盗意味着别人能拿他的 key 跑评审花钱（虽然看不到明文）。

    **本设备也会被登出**，前端拿到响应后要清掉本地令牌跳回登录页。
    刻意不像 change_password 那样顺手换一把新令牌给本设备：
    用户点这个按钮的语境是"我不确定哪台设备是我的"，此时"除了你都踢掉"
    是个需要他信任当前设备的假设——而他正因为不确定才点的。
    全部登出、重新登一次，语义上没有歧义。

    要做到"看得见有哪些设备、逐个踢"需要为每次登录存一条会话记录
    （设备/IP/最后活跃）。那是另一件事：新表、新数据，而且存 IP 要同步
    改隐私政策。这里先给出安全价值最大的那一半。
    """
    _require_auth_enabled()
    _require_own_identity(identity)
    user = db.get(User, identity.user_id)
    if not user:
        raise NotFound("账号不存在")

    revoke_user_sessions(db, user.id)
    audit_target = user.email
    logger.info("user %s revoked all sessions", audit_target)
    return {"revoked": True}


class UpdateProfileRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=50)


# 本轮新增的写接口里唯一漏挂限流的一条：实测单令牌连打 200 次全部 200，
# 每次都是一轮 UPDATE + commit。改昵称是低频动作，30 次/小时绰绰有余。
@router.patch("/auth/me", dependencies=[Depends(rate_limit("profile", 30, 3600))])
async def update_profile(
    body: UpdateProfileRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """改昵称。

    在此之前 display_name 只在注册那一刻写入（没填就取邮箱 @ 前面那截），
    之后没有任何路径能改——注册时随手填的名字会跟着账号一辈子。

    这里只放开昵称。**改邮箱故意不做**：邮箱同时是登录名、找回密码的收件地址
    和账号唯一键，换它必须走"向新地址发验证信、验证通过后才生效"的两步流程，
    否则填错一个字母就等于把账号锁死（登不进、也找不回）。那是一条独立的链路，
    不该顺手塞进这个接口里假装支持了。
    """
    _require_auth_enabled()
    _require_own_identity(identity)
    user = db.get(User, identity.user_id)
    if not user:
        raise NotFound("账号不存在")
    name = body.display_name.strip()
    if not name:
        raise BadRequest("昵称不能为空")
    # 控制字符一律拒绝。重点是 NUL：SQLite 会照单全收，而 PostgreSQL 的 text
    # 类型不接受 0x00，psycopg2 会直接抛错——也就是说这是一条"本机测不出来、
    # 上了生产才 500"的路径（生产库按部署文档就是 PostgreSQL）。
    # 顺带挡掉 U+202E 这类双向覆写符：它能让昵称在界面上反向显示，
    # 用来伪装成别人或伪造后缀。可打印的 Unicode（中日韩、emoji）不受影响。
    if any(ch < " " or ch == "\x7f" for ch in name) or any(
        "‪" <= ch <= "‮" or "⁦" <= ch <= "⁩" for ch in name
    ):
        raise BadRequest("昵称包含不可见的控制字符，请去掉后重试")
    user.display_name = name
    db.commit()
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


# ---------- 数据自主权：导出我的数据 / 删除我的账号 ----------
# 让"你的东西归你"不只是一句承诺，而是用户能亲手验证的两个按钮。


def _require_own_identity(identity: Identity) -> None:
    """这两个接口必须有"唯一属于你"的身份，匿名一律拒绝。

    原因是匿名身份不是"某个人"，而是一个**所有人共用的桶**：
    AL_AUTH_ENABLED=false（默认值！）时每个请求都拿到同一个
    settings.anonymous_user_id，全实例的评审 user_id 也都是它。
    于是 delete_user_data(db, "anonymous") 匹配到的不是"我的数据"，
    而是**全库所有人的数据**——任何访客不用登录不用密码就能清空整个实例；
    导出接口同理会把所有人的材料原文和报告打包给调用方。

    注意别误伤 CDK 兑换出来的游客：他们持 token、有独立 user_id、
    is_anonymous=False，属于真实身份，照常放行。
    """
    if identity.is_anonymous:
        raise BadRequest(
            "这个操作需要一个属于你自己的账号。当前是未登录的共享身份，"
            "无法区分哪些数据属于你——请先注册或登录。"
        )


# ---------- 认领：把登录前跑的匿名评审挂到自己账号下 ----------


class ClaimReviewsRequest(BaseModel):
    review_ids: List[str] = Field(default_factory=list)
    # 对话与评审是两套独立归属（一段对话可能一条评审都没产出），所以认领
    # 评审并不会顺带把对话带过来。放在同一个端点而不是新开一个：
    # 归属校验与并发条件 UPDATE 那套逻辑一模一样，抄一遍必然会有一份先腐烂。
    conversation_ids: List[str] = Field(default_factory=list)
    # 项目本身没有内容（只是个名字），但如果不认领它，一个真实的坑会发生：
    # 用户匿名时新建项目、把对话拖进去，登录后只认领了对话——对话的
    # project_id 还指向匿名桶里那个项目，get_owned 按新账号一查就是 404，
    # 侧栏里那段对话会从项目里"消失"（实际是查不到项目、不是对话丢了，
    # 但用户看到的现象就是"我建的项目不见了"）。
    project_ids: List[str] = Field(default_factory=list)


# 一次最多认领多少条。上限的意义不是"够不够用"，而是别让这个接口变成
# 一次请求就能扫一大批 uuid 的探测器（配合限流一起看）。
CLAIM_MAX_IDS = 50


@router.post(
    "/auth/me/claim-reviews",
    dependencies=[Depends(rate_limit("claim_reviews", 20, 3600))],
)
async def claim_reviews(
    body: ClaimReviewsRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """把「登录前以匿名身份跑的评审」改挂到当前账号名下。

    为什么必须有这个接口：匿名评审落库时 user_id = settings.anonymous_user_id，
    而所有归属校验都是精确字符串比对（v1 的 _check_review_owner、v2 的
    `review.user_id != identity.user_id → 404`）。用户一登录，identity.user_id
    变成真实 id，这条评审的每一个路由都开始返回 404——前端承诺的"登录后可查看
    完整报告"实际表现是**报告凭空消失**。没有认领，那句文案就是假的。

    ── 安全边界（写清楚，不假装它不存在）──────────────────────────
    1. 只认领**当前仍归属匿名桶**（anonymous_user_id）或 user_id 为空的评审。
       已经属于某个真实账号的一律跳过，绝不转移——所以这个接口无法把别人
       账号里的评审偷过来。
    2. 匿名桶是**共享**的：AL_AUTH_ENABLED=false 时全实例共用一个 anonymous
       身份。因此"任何知道某条评审 uuid 的人都能把它认领走"是事实，唯一的
       防线是 review.id 为 uuid4（122 位随机，不可枚举）+ 本接口的限流。
       这是取舍，不是疏漏：换成"必须先证明你是创建者"就得引入匿名会话密钥，
       而匿名本来就没有可信的身份可绑。
    3. 认领是**一次性、不可逆**的（先到先得）：评审一旦离开匿名桶，其他匿名
       访客就再也看不到它。单机/开源形态（认证关闭）下所有人都是匿名，
       `_require_own_identity` 会直接挡住调用，不受影响。
    4. 返回值不区分"这条 id 不存在"和"这条已属于别人"——两者都进 rejected。
       理由与归属校验用 404 而不是 403 一致：不向调用方确认某个 id 是否存在。

    ── 关联记录怎么处理 ─────────────────────────────────────────
    跟着评审走（它们随 Review 级联删除，归属必须一致，否则新主人在
    「判断复利」「价值指标」里看不到自己评审的数据，旧数据还留在匿名桶里）：
        · Judgment（该评审产出的预测，/ledger/* 全部按 user_id 过滤）
        · ReviewFeedback（价值回填，/validation/metrics 按 user_id 聚合）
    **不跟着走**（计量/财务事实源，与 user_data_service 的删除口径同一条线）：
        · UsageRecord / CreditLedger —— 这次消耗当时就记在匿名桶头上了，
          事后改挂到新账号等于让用户为"注册前已经用掉的额度"再被扣一次配额。
        · Job —— 队列簿记，评审跑完就没用了，不值得为它多写一次库。
    """
    from sqlalchemy import or_

    from app.models import Judgment, ReviewFeedback

    _require_own_identity(identity)

    seen = set()
    wanted: List[str] = []
    for raw in body.review_ids or []:
        rid = str(raw).strip()
        if rid and rid not in seen:
            seen.add(rid)
            wanted.append(rid)
    if len(wanted) > CLAIM_MAX_IDS:
        raise BadRequest(f"一次最多认领 {CLAIM_MAX_IDS} 条评审")
    # 注意这里没有"评审为空就提前返回"：只带对话来认领是完全正常的情形
    # （用户聊了半天还没开评审就去登录了）。之前那个 early return 会把
    # 这种请求直接吞掉，对话永远归不到账号名下。
    anon = settings.anonymous_user_id
    rows = db.query(Review).filter(Review.id.in_(wanted)).all() if wanted else []
    claimed: List[str] = []
    for review in rows:
        if review.user_id and review.user_id != anon:
            continue  # 已属于某个真实账号 —— 拒绝，不做转移
        # 条件 UPDATE：只有"此刻仍归属匿名桶/无主"的行才改挂。并发认领时
        # 后到者的 UPDATE 匹配不到行（rowcount=0），绝不覆盖先到者的归属——
        # 无条件赋值是"谁先读谁赢"（读到旧值覆盖新值），这里是"谁先写谁赢"。
        updated = (
            db.query(Review)
            .filter(
                Review.id == review.id,
                or_(Review.user_id.is_(None), Review.user_id == anon),
            )
            .update({"user_id": identity.user_id}, synchronize_session=False)
        )
        if updated == 1:
            claimed.append(review.id)

    if claimed:
        for model in (Judgment, ReviewFeedback):
            db.query(model).filter(
                model.review_id.in_(claimed),
                or_(model.user_id == anon, model.user_id.is_(None)),
            ).update({"user_id": identity.user_id}, synchronize_session=False)
        db.commit()

    # ---- 对话：同一套条件 UPDATE ----
    wanted_convs = list(dict.fromkeys(body.conversation_ids or []))
    if len(wanted_convs) > CLAIM_MAX_IDS:
        raise BadRequest(f"一次最多认领 {CLAIM_MAX_IDS} 段对话")
    claimed_convs: List[str] = []
    if wanted_convs:
        from app.models import Conversation, UploadedFile

        conv_rows = db.query(Conversation).filter(Conversation.id.in_(wanted_convs)).all()
        for conv in conv_rows:
            if conv.user_id and conv.user_id != anon:
                continue  # 已属真实账号，绝不转移
            updated = (
                db.query(Conversation)
                .filter(
                    Conversation.id == conv.id,
                    or_(Conversation.user_id.is_(None), Conversation.user_id == anon),
                )
                .update({"user_id": identity.user_id}, synchronize_session=False)
            )
            if updated == 1:
                claimed_convs.append(conv.id)

        if claimed_convs:
            # 对话里引用的图片也要跟着改挂，否则重放时每张图都 404：
            # 消息还在、file_id 还在，但那些文件仍归匿名桶，取回接口按归属校验
            # 会拒绝。用户看到的是"登录之后图全丢了"。
            file_ids: set = set()
            for conv in conv_rows:
                if conv.id not in claimed_convs:
                    continue
                for m in conv.messages:
                    meta = m.meta_json or {}
                    for fid in meta.get("fileIds") or []:
                        if isinstance(fid, str):
                            file_ids.add(fid)
            if file_ids:
                db.query(UploadedFile).filter(
                    UploadedFile.id.in_(list(file_ids)),
                    or_(UploadedFile.user_id == anon, UploadedFile.user_id.is_(None)),
                ).update({"user_id": identity.user_id}, synchronize_session=False)
            db.commit()

    # ---- 项目：同一套条件 UPDATE。放在对话认领之后——项目本身的认领
    # 顺序其实无所谓，但这样读下来是"内容 → 内容的容器"，逻辑顺序更顺。
    wanted_projects = list(dict.fromkeys(body.project_ids or []))
    if len(wanted_projects) > CLAIM_MAX_IDS:
        raise BadRequest(f"一次最多认领 {CLAIM_MAX_IDS} 个项目")
    claimed_projects: List[str] = []
    if wanted_projects:
        from app.models import Project

        proj_rows = db.query(Project).filter(Project.id.in_(wanted_projects)).all()
        for proj in proj_rows:
            if proj.user_id and proj.user_id != anon:
                continue  # 已属真实账号，绝不转移
            updated = (
                db.query(Project)
                .filter(
                    Project.id == proj.id,
                    or_(Project.user_id.is_(None), Project.user_id == anon),
                )
                .update({"user_id": identity.user_id}, synchronize_session=False)
            )
            if updated == 1:
                claimed_projects.append(proj.id)
        if claimed_projects:
            db.commit()

    claimed_set = set(claimed)
    claimed_conv_set = set(claimed_convs)
    claimed_project_set = set(claimed_projects)
    return {
        "claimed": claimed,
        "rejected": [rid for rid in wanted if rid not in claimed_set],
        "claimed_count": len(claimed),
        "claimed_conversations": claimed_convs,
        "rejected_conversations": [c for c in wanted_convs if c not in claimed_conv_set],
        "claimed_projects": claimed_projects,
        "rejected_projects": [p for p in wanted_projects if p not in claimed_project_set],
    }


@router.get("/auth/me/export", dependencies=[Depends(rate_limit("data_export", 5, 3600))])
async def export_my_data(
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """导出我的全部数据（JSON）。密钥只给掩码，不导出明文。"""
    from app.services import user_data_service

    _require_own_identity(identity)
    return user_data_service.export_user_data(db, identity.user_id)


class DeleteAccountRequest(BaseModel):
    # 二次确认：必须原样输入这个词，避免误点就把账号删了
    confirm: str
    # 已注册用户还要验密码——光有 token 不够，token 可能是被人捡到的
    password: Optional[str] = None


DELETE_CONFIRM_PHRASE = "删除我的账号"


@router.post("/auth/me/delete", dependencies=[Depends(rate_limit("account_delete", 5, 3600))])
async def delete_my_account(
    body: DeleteAccountRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """彻底删除我的内容与账号。财务流水改为切断关联的墓碑 id（见 user_data_service）。"""
    from app.services import user_data_service

    # 顺序要紧：先卡身份再看确认词。匿名身份下这个接口会删全库
    # （见 _require_own_identity），不能让它有任何走到删除逻辑的机会。
    _require_own_identity(identity)

    if body.confirm != DELETE_CONFIRM_PHRASE:
        raise BadRequest(f"请输入「{DELETE_CONFIRM_PHRASE}」以确认此操作")

    user = db.get(User, identity.user_id)
    if not user:
        raise NotFound("账号不存在")
    if not body.password or not verify_password(body.password, user.password_hash):
        raise Unauthorized("密码不正确")

    stats = user_data_service.delete_user_data(db, identity.user_id)
    return {"deleted": True, "detail": stats}


# ============================== BYOK Key（埋线）==============================

# ---------- api_base 的 SSRF 防线 ----------
#
# api_base 是**请求方完全可控**的字符串，会被原样拼成 URL 由服务器发出去
# （src/runner/llm_client.py：`url = api_base.rstrip("/") + "/chat/completions"`），
# 失败时的报错还会把目标响应正文的前 300 字符回显给调用方。也就是说：
# 不设防的话，任何人都能把这台后端当成打内网的跳板，并读回响应片段——
# 云上最典型的目标是 169.254.169.254（实例元数据，能读出临时凭证）。
#
# 判定边界（写清楚，免得下一个人以为可以放宽）：
#   拒绝  非 http/https 的协议；解析不出主机名/端口非法的地址；
#         主机名解析出的**任何**一个 IP 落在环回 / 私有网段 / 链路本地
#         （含 169.254.169.254）/ 组播 / 保留段 / 0.0.0.0 上。
#         IPv4-mapped IPv6（::ffff:127.0.0.1 这种绕法）由 is_private 一并覆盖。
#   放行  公网地址。BYOK 用户自建的 Ollama/中转只要挂在公网 IP 或公网域名上
#         就完全不受影响——这条防线拦的是"指回内网"，不是"不是大厂域名"。
#
# 什么时候允许私网地址：只有「单机自建形态」——AL_AUTH_ENABLED=false（这台
# 机器就一个使用者，不存在"别人的访客"）且 looks_like_production=False
# （CORS/公开地址都还指着 localhost，没在对公网提供服务）。这一档下
# http://localhost:11434/v1（llm_client 里的 Ollama 预设）必须继续可用，
# 否则等于把自建用户的本地模型这条路直接砍掉。任何一个条件不成立，
# 就按多租户对待，私网一律拒绝。
#
# 已知残留风险（不假装它不存在）：这里解析一次、httpx 发请求时再解析一次，
# 中间存在 DNS rebinding 的时间窗。堵死它需要把校验通过的 IP 钉进 httpx 的
# transport，涉及 src/runner/llm_client.py（不属于本次改动范围）。
_ALLOWED_API_BASE_SCHEMES = ("http", "https")


def _private_api_base_allowed() -> bool:
    """当前形态下允不允许把请求指向私网/环回地址。"""
    return not settings.auth_enabled and not settings.looks_like_production


def _is_internal_ip(ip) -> bool:
    return (
        ip.is_loopback
        or ip.is_private          # 含 10/8、172.16/12、192.168/16、fc00::/7、::ffff:0:0/96
        or ip.is_link_local       # 含 169.254.0.0/16（云元数据地址就在这里）
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified      # 0.0.0.0 / ::
    )


def assert_api_base_is_safe(api_base: Optional[str]) -> None:
    """api_base 指向内网就抛 BadRequest。**必须在发请求之前调**。

    事后过滤响应没有意义：请求一旦发出去，探测这件事本身就已经完成了
    （端口开没开、响应多快、返回什么状态码，全都是情报）。
    """
    raw = (api_base or "").strip()
    if not raw:
        return  # 留空 = 用服务商官方地址，没有可被操纵的目标

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_API_BASE_SCHEMES:
        raise BadRequest("api_base 必须以 http:// 或 https:// 开头")
    host = (parsed.hostname or "").strip()
    if not host:
        raise BadRequest("api_base 里解析不出主机名")
    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError:
        raise BadRequest("api_base 的端口不合法")

    if _private_api_base_allowed():
        return

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        # 解析不了的主机名本来也发不出请求，在这里挡掉顺带避免把 DNS 失败
        # 变成一次真实外发尝试。
        raise BadRequest(f"api_base 的主机名无法解析：{host}")

    for info in infos:
        addr = str(info[4][0]).split("%")[0]  # 去掉 IPv6 的 zone id（fe80::1%eth0）
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            raise BadRequest(f"api_base 解析出的地址无法识别：{addr}")
        if _is_internal_ip(ip):
            raise BadRequest(
                f"api_base 指向内网地址（{host} → {addr}），已拒绝。"
                "服务端不会替调用方访问环回/私有/链路本地地址；"
                "自建端点请填写公网可达的地址。"
            )


async def _assert_api_base_is_safe_off_loop(api_base: Optional[str]) -> None:
    """在线程池里做校验：getaddrinfo 是同步阻塞调用，没有超时参数，
    一个慢 DNS 就能把整个事件循环卡住（全站所有请求一起等）。"""
    from starlette.concurrency import run_in_threadpool

    await run_in_threadpool(assert_api_base_is_safe, api_base)


class SaveKeyRequest(BaseModel):
    api_key: str
    provider: str = "anthropic"  # "anthropic" | "openai_compatible"
    model: Optional[str] = None  # openai_compatible 档必填（如 "deepseek-v4-pro"）
    api_base: Optional[str] = None  # openai_compatible 档的自定义端点


class TestKeyRequest(BaseModel):
    """测试连接：可以测"还没保存、正准备填的 key"，也可以不传 api_key 测已保存的。"""

    api_key: Optional[str] = None
    provider: str = "anthropic"
    model: Optional[str] = None
    api_base: Optional[str] = None


@router.get("/keys")
async def list_keys(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    """回显当前 key 状态（仅掩码，绝不返回明文）。

    共享匿名桶在多租户形态下直接当作「没有 key」，而不是 401：
    这个接口是设置页一进来就调的，报错会把整页打成错误态；返回空则页面
    自然显示「还没配置 key」，配合下面 save_key 的 401 提示引导去登录。
    要点是**不能把别人存的 key 回显出来**——连掩码和 provider 都不行，
    那等于告诉访客「这里有一把可用的 key」，而它确实能被拿去花钱。
    """
    from app.models import UserApiKey

    if is_shared_anonymous(identity) and settings.auth_enabled:
        return {
            "key_mode": settings.key_mode,
            "server_key_available": bool(settings.server_llm_key) and settings.is_managed,
            "keys": [],
            "requires_login": True,
        }

    rows = (
        db.query(UserApiKey)
        .filter(UserApiKey.user_id == identity.user_id, UserApiKey.is_active.is_(True))
        .all()
    )
    return {
        "key_mode": settings.key_mode,
        "server_key_available": bool(settings.server_llm_key) and settings.is_managed,
        "keys": [
            {
                "provider": r.provider,
                "model": r.model,
                "api_base": r.api_base,
                "masked": r.key_masked,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            }
            for r in rows
        ],
    }


@router.post("/keys")
async def save_key(
    body: SaveKeyRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    # API Key 是最不该落进共享桶的东西：存进去等于把自己的付费凭据交给
    # 所有未登录访客——他们能用它跑评审花钱，也能顺手删掉。
    require_isolated_identity(identity)
    # 存下来的 api_base 之后每次评审/意图解析/追问都会被服务器拿去发请求
    # （key_service.resolve_key 一路透传到 llm_client）。只在 /keys/test 上设防
    # 等于只堵了一个入口——存进来再由评审链路发出去是同一个 SSRF，必须一起挡。
    await _assert_api_base_is_safe_off_loop(body.api_base)
    try:
        row = key_service.save_user_key(
            db, identity.user_id, body.api_key, body.provider, model=body.model, api_base=body.api_base
        )
    except ValueError as exc:
        raise BadRequest(str(exc))
    return {"provider": row.provider, "model": row.model, "api_base": row.api_base, "masked": row.key_masked}


@router.post("/keys/test", dependencies=[Depends(rate_limit("key_test", 10, 3600))])
async def test_key(
    body: TestKeyRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """真实发一次最小请求验证 key/模型/端点可用——测的是评审真正会走的那条链路
    （src/runner/llm_client.py），不是另一套摆设的连接校验。

    不传 api_key 时测"当前已保存"的那把 key，方便"保存后再测一次"的场景。
    """
    # 身份要求提到最前面，不再只在「测已保存的那把」分支里要。
    # 理由：这个端点会让**服务器**按调用方给的地址发一次真实请求，并把结果
    # （含失败时目标响应正文的前 300 字符）回显。自带 api_key 一样能驱动它，
    # 所以此前"带了 key 就不需要任何身份"等于给未认证访客开了一个出网探针。
    # 代价可控：单机开源形态（AL_AUTH_ENABLED=false）下这一句是空操作，
    # 只有多租户形态才要求先登录——那正是"未登录访客"真实存在的形态。
    require_isolated_identity(identity)
    # 拒绝必须发生在发请求之前，见 assert_api_base_is_safe 的说明
    await _assert_api_base_is_safe_off_loop(body.api_base)

    api_key = body.api_key
    model = body.model
    api_base = body.api_base
    if not api_key:
        # 「测已保存的那把」会解密并真的拿去调模型。共享匿名桶里的 key 是别人的，
        # 不挡住等于让任何访客点一下按钮就花别人的钱。传了 api_key 的现填现测不受影响。
        row = key_service.get_user_key_row(db, identity.user_id, body.provider)
        if not row:
            raise BadRequest("没有已保存的 key 可测，请先填写 api_key")
        from app.core.security import decrypt_secret

        try:
            api_key = decrypt_secret(row.key_ciphertext, settings.encryption_key)
        except ValueError:
            raise BadRequest("已保存的 key 解密失败，请重新填写")
        model = model or row.model
        api_base = api_base or row.api_base

    if body.provider == "openai_compatible" and not (model or "").strip():
        raise BadRequest("非 Anthropic 服务商必须指定模型名")

    # 再校验一次**最终生效**的那个地址：上面走「测已保存的那把」分支时
    # api_base 来自库里，可能是在单机形态下存进去的私网地址，而这台实例
    # 现在已经是多租户/对公网服务了。第一道只看请求体，这道才是最后闸门。
    await _assert_api_base_is_safe_off_loop(api_base)

    effective_model = model or settings.intent_model  # anthropic 档没填模型时用一个已知可用的默认值

    import sys

    from starlette.concurrency import run_in_threadpool

    _SRC = os.path.join(settings.repo_root, "src")
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    from runner.llm_client import test_connection

    # test_connection 是同步网络调用（anthropic SDK / httpx.post，非 async）——
    # 直接 await 会在单一事件循环里原地阻塞，一个卡住的第三方中转会拖死整个后端
    # 对所有用户的响应（不止这一个请求）。丢进线程池，事件循环不受影响。
    return await run_in_threadpool(
        test_connection,
        model=effective_model, api_key=api_key, provider=body.provider, api_base=api_base,
    )


@router.delete("/keys/{provider}")
async def delete_key(
    provider: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    # 共享桶里的 key 不属于调用方，不能让任何访客顺手删掉别人的凭据。
    require_isolated_identity(identity)
    n = key_service.delete_user_key(db, identity.user_id, provider)
    return {"deleted": n}


# ============================== 意图解析（对话式入口）==============================

class IntentRequest(BaseModel):
    text: str


@router.post("/intent/parse", dependencies=[Depends(rate_limit("intent", 30, 60))])
async def parse_intent(
    body: IntentRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """把一句大白话解析成评审参数。

    无 key 也能用：自动降级到启发式规则档（返回 method=heuristic 如实声明）。
    """
    api_key = None
    provider = "anthropic"
    model = None
    api_base = None
    key_source = "byok"
    try:
        resolved = key_service.resolve_key(db, identity.user_id)
        api_key = resolved.key
        provider = resolved.provider
        model = resolved.model
        api_base = resolved.api_base
        key_source = resolved.source
    except Exception:
        api_key = None  # 没 key 就走启发式，不阻断

    # 终身 token 额度用完后，不再用平台 key 打这个接口——但**不报错**，
    # 降级成启发式档继续服务。这条路本来就有"没 key 就走启发式"的降级，
    # 额度用完与没配 key 是同一类情形：能力下降，功能不断。
    # 在对话框里输入一句话就 402 是最糟的表现形式（用户还没发起评审就被挡），
    # 真正该拦的是评审本身，那条路在 check_quota 里。
    if key_source == "server" and quota_service.token_cap_error(db, identity.user_id):
        api_key = None
        key_source = "byok"  # 不再消耗平台额度，记账也不该记到平台头上

    # 用量必须记账。对话页每发一条消息就调一次这个接口，走平台垫付 key 时
    # 它是一笔真实开销，以前既不进 UsageRecord 也不受任何配额约束——
    # 后台成本面板看不见它，日成本硬闸也管不到它。
    usage: dict = {}
    result = intent_service.parse_intent(
        body.text, api_key, provider=provider, model=model, api_base=api_base, usage=usage
    )

    in_tok = int(usage.get("input_tokens") or 0)
    out_tok = int(usage.get("output_tokens") or 0)
    if in_tok or out_tok:
        cost = 0.0
        try:
            import sys

            _src = os.path.join(settings.repo_root, "src")
            if _src not in sys.path:
                sys.path.insert(0, _src)
            import yaml as _yaml
            from runner.persona_agent import estimate_cost

            with open(os.path.join(_src, "config", "budget.yaml"), encoding="utf-8") as fh:
                budget_config = _yaml.safe_load(fh)
            cost = estimate_cost(in_tok, out_tok, usage.get("model") or "", budget_config)
        except Exception:
            # 估价失败不该让意图解析本身失败——但 token 数照记，
            # 不能因为算不出钱就连"用了多少"都丢掉。
            cost = 0.0
        quota_service.record_usage(
            db,
            identity.user_id,
            kind="intent",
            cost_usd=cost,
            input_tokens=in_tok,
            output_tokens=out_tok,
            key_source=key_source,
        )

    return result.to_dict()


# ============================== 上传 ==============================

_IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@router.get("/uploads/{file_id}")
async def get_uploaded_file(
    file_id: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """取回自己上传的图片。对话重放时 <img src> 指向这里。

    归属校验回 404 而不是 403：403 等于确认"该 id 存在但不是你的"，
    可以被用来枚举他人上传的文件。
    """
    from fastapi.responses import Response

    from app.services import file_store

    row = file_store.get_owned(db, file_id, identity.user_id)
    if row is None:
        raise NotFound("文件不存在")
    data = file_store.read_bytes(row)
    if data is None:
        # 库里有记录、磁盘上没字节。当成不存在处理，但要留日志——
        # 静默返回空图会让"图片丢了"变成一个查不出原因的现象。
        logger.warning("uploaded_file_missing_on_disk id=%s", file_id)
        raise NotFound("文件不存在")
    return Response(
        content=data,
        media_type=row.media_type,
        headers={
            # 私有内容，不能进任何共享缓存
            "Cache-Control": "private, max-age=86400",
            # 浏览器嗅探出的类型可能与声明的不一致，据此执行是 XSS 面
            "X-Content-Type-Options": "nosniff",
            # 即便有人上传了 SVG 之类，也不让它在本域下当文档执行
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post("/uploads", dependencies=[Depends(rate_limit("upload", 20, 3600))])
async def upload_file(
    file: UploadFile = File(...),
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """上传材料文件。文本类抽取成文字返回；图片类（截图/UI稿/BP页面）转成 data URI，
    前端把它塞进 material {type: "image", image_data: ...} 交给多模态模型直接"看"。"""
    ext = os.path.splitext(file.filename or "")[1].lower()

    async def _read_capped(limit: int, label: str) -> bytes:
        """分块读并在超限的那一刻立即中止——不能先把整个 body 吸进内存再检查，
        否则一个超大请求体就能打爆进程内存（大小检查形同虚设）。"""
        chunks = []
        total = 0
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise BadRequest(f"{label}超过上限 {limit // 1024 // 1024} MB")
            chunks.append(chunk)
        return b"".join(chunks)

    if ext in settings.upload_allowed_image_ext:
        raw = await _read_capped(settings.upload_max_image_bytes, "图片")
        import base64

        media_type = _IMAGE_MEDIA_TYPES.get(ext, "application/octet-stream")
        data_uri = f"data:{media_type};base64,{base64.b64encode(raw).decode('ascii')}"

        # 落盘并登记。此前图片只以 data URI 形式活在浏览器内存里，刷新即消失，
        # 对话重放时那些图就永远回不来了。
        # 注意扩展名取的是白名单映射里的那个，不是用户传来的——用户可以把任意
        # 内容叫成 .png，落盘名必须由服务端决定。
        from app.services import file_store

        stored = file_store.save_bytes(
            db, identity.user_id, raw, media_type, ext, filename=file.filename
        )

        return {
            "filename": file.filename,
            "kind": "image",
            "size": len(raw),
            # data URI 继续返回：评审链路与追问链路一路把它当 image_url 传给模型
            # （persona_agent.py:362 / chat_service.py:282），改成路径要动引擎，
            # 这次不动。前端发消息时仍用它，只是**持久化时改存 file_id**。
            "image_data": data_uri,
            "file_id": stored.id,
            "url": f"/api/uploads/{stored.id}",
        }

    if ext not in settings.upload_allowed_ext:
        raise BadRequest(
            f"不支持的文件类型 {ext or '(无扩展名)'}；"
            f"文本类允许：{', '.join(sorted(settings.upload_allowed_ext))}；"
            f"图片类允许：{', '.join(sorted(settings.upload_allowed_image_ext))}"
        )

    raw = await _read_capped(settings.upload_max_bytes, "文件")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise BadRequest("文件必须是 UTF-8 文本")

    # 不再往磁盘写副本：抽取出的 text 直接随响应回给前端，前端把它并进材料
    # 文本一起提交评审，评审内容最终落在 Review.artifact_bundle 里。此前额外
    # 存的那份 data/uploads/{uuid}.txt 从写下去那一刻起就没有任何代码读过它
    # （stored_as 只在类型定义里出现，没有下载/引用入口），纯粹在攒垃圾文件、
    # 且没有任何清理逻辑——磁盘只增不减。备份脚本也只备份 reviews.db，
    # 不含这个目录，所以它连"数据资产"都算不上。
    return {
        "filename": file.filename,
        "kind": "text",
        "size": len(raw),
        "text": text,
    }


# ============================== CDK 兑换码 ==============================

class RedeemCdkRequest(BaseModel):
    code: str


@router.post("/cdk/redeem", dependencies=[Depends(rate_limit("cdk", 10, 60))])
async def redeem_cdk(
    body: RedeemCdkRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """兑换 CDK 获得评审次数——无需注册登录。

    身份归属的三种情况：
      已登录        → 次数记到该账号
      匿名+认证开启  → 自动签发游客身份（真实 User 行 + JWT），次数记到游客账号；
                      前端存下返回的 token，后续评审/查余额都带它——
                      不这样做的话，所有匿名访客共享同一个 anonymous 桶，
                      第一个人兑的码会被全站陌生人分掉
      匿名+认证关闭  → 单机形态，本来就只有一个使用者，直接记到 anonymous

    限流必须严：兑换码可被暴力枚举，此接口限 10 次/分钟（按 IP/用户）。
    """
    from app.services import cdk_service

    guest_token = None
    guest_user = None
    user_id = identity.user_id

    if settings.auth_enabled and identity.is_anonymous:
        import secrets as _secrets

        guest_user = User(
            email=f"guest-{uuid.uuid4().hex[:12]}@guest.local",
            password_hash=hash_password(_secrets.token_urlsafe(32)),  # 不可登录
            display_name="游客",
            is_guest=True,
        )
        db.add(guest_user)
        db.commit()
        db.refresh(guest_user)
        user_id = guest_user.id
        guest_token = issue_session_token(db, user_id)

    try:
        result = cdk_service.redeem(db, body.code, user_id)
    except cdk_service.CdkError as exc:
        # 兑换失败时回滚刚创建的游客——不给枚举者留下批量制造空账号的口子
        if guest_user is not None:
            db.delete(guest_user)
            db.commit()
        raise BadRequest(str(exc))

    resp = {**result, "user_id": user_id}
    if guest_token:
        resp["token"] = guest_token
        resp["guest"] = True
    return resp


# ============================== 用量 / 配额 / 套餐 ==============================

@router.get("/plans")
async def plans(db: Session = Depends(get_db)):
    """公开定价页数据：三档套餐及各自限额（无需登录）。"""
    return {"plans": plan_service.list_plans(db)}


@router.get("/usage")
async def usage(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    # 用量是"属于你自己"的数据：多租户形态下未登录访客共用同一个匿名桶，
    # 直接返回会让访客看到**全站所有未登录用户加起来**的用量与成本。
    # 与 list_judgments / validation_metrics 同一道隔离口径。
    require_isolated_identity(identity)
    return quota_service.usage_summary(db, identity.user_id, plan=identity.plan)


# ============================== 异步评审（v2 链路）==============================

def _valid_persona_packs() -> set:
    """合法 persona_pack = src/personas/ 下真实存在且非空的人格包。

    与前端 list_packs 同源（PersonaService 直读 src/personas/*.yaml）。
    拼错的包名此前被静默回落 game-core：用户选 A 包，跑的是 B 包，
    报告人格与所见不符——这是功能缺陷不是容错，必须在入口显式 400。
    """
    from app.services import PersonaService

    packs = PersonaService.load_all_personas()
    return {pid for pid, personas in packs.items() if personas}


def _validate_artifact(artifact: dict) -> None:
    """入队**前**把材料包的形状问题拦下来。

    此前 artifact 只声明成 `dict`，没有任何结构校验。形状写错时的实际表现是：
    接口 200 收下 → 评审入队 → 跑到最后抛 AllPersonasFailedError，
    错误消息是「本次没有任何人格进入评审（预设面板为空，或全部被证据预检
    跳过）」——指向的是人格面板，而真正的原因是**材料里根本没有 materials
    数组**（evidence_precheck.load_evidence_types 只读这个键，读不到就等于
    没有任何证据类型，于是全部人格被跳过）。

    这个失败形态有三重代价：
      · 用户/接入方按错误提示去查人格配置，方向完全是错的
      · 用平台 key 时已经占了一次配额（放行瞬间就预留）
      · 真跑起来的话还会产生模型调用费用

    实测踩过一次：传 {"text": "..."} 而不是 {"materials": [...]}，
    全程无警告，直到最后才失败。校验放在入队前，错误说清楚该怎么改。

    刻意只校验**形状**，不校验内容长短：材料多短算够用是引擎的判断
    （evidence_precheck 的 coverage 阈值），不该在 API 层再设一道
    口径不同的门槛。
    """
    materials = artifact.get("materials")
    if materials is None:
        raise BadRequest(
            "artifact 缺少 materials 数组。正确形状："
            '{"title": "标题", "materials": [{"type": "text", "text": "材料正文"}]}。'
            "只传 title 或把正文直接放在 artifact 顶层都不行——评审会因为读不到"
            "任何证据而把全部人格跳过，最终失败。"
        )
    if not isinstance(materials, list):
        raise BadRequest(f"artifact.materials 必须是数组，收到的是 {type(materials).__name__}")
    if not materials:
        raise BadRequest("artifact.materials 是空数组，没有任何材料可供评审")

    for i, m in enumerate(materials):
        if not isinstance(m, dict):
            raise BadRequest(f"artifact.materials[{i}] 必须是对象，收到的是 {type(m).__name__}")
        mtype = m.get("type")
        if not mtype:
            raise BadRequest(f'artifact.materials[{i}] 缺少 type（文本材料用 "text"，图片用 "image"）')
        if mtype == "image":
            if not m.get("image_data"):
                raise BadRequest(f"artifact.materials[{i}] 是图片但没有 image_data")
        elif not (m.get("text") or m.get("description")):
            # 这里点名 text 是因为引擎读的就是它（runner/cli.py 组装
            # artifact_texts 时取 description or text）。写成别的键名不会报错，
            # 只会让人格收到一份空材料——照样调用模型、照样计费、
            # 产出一份基于空白的报告。那比直接失败更糟。
            raise BadRequest(
                f'artifact.materials[{i}] 缺少 text（文本材料的正文字段名是 "text"）。'
                "用别的键名不会报错，但人格会收到空材料——照样调用模型、照样计费，"
                "产出一份基于空白的报告。"
            )


class CreateReviewRequest(BaseModel):
    task_type: str
    artifact: dict = Field(description="材料包：{title, materials:[{type,text}]}")
    mode: str = "standard"
    persona_pack: str = "game-core"
    # 呼叫具体角色：id 必须落在 persona_pack 对应的人格包内，不属于该包的会被
    # select_panel_by_mode 静默过滤掉（见 services/__init__.py），不算错误。
    selected_personas: Optional[List[str]] = None
    # 插入技能：只有 red_team_audience / audience_panel 真正影响 prompt 取向
    # （见 PersonaService.get_skill_prompt_hint）；其余值原样落库当标签，不报错。
    skill_type: Optional[str] = None
    # 长期评审项目分组键：同名即同一个项目，前端按它把历次评审聚合成时间线。
    project_key: Optional[str] = None
    # 评审完成后自动运行 8 维质量评估（Wizard"启用评估"开关）
    enable_evaluation: bool = False
    # 追加红队对抗视角提示（与 skill_type 独立——选了别的技能也能叠加红队）
    enable_red_team: bool = False
    # 自动面板才可用；显式 selected_personas 时引擎保留全员并在报告中解释禁用原因。
    adaptive_panel: bool = False
    # 两层评审开关：全包初筛后按分歧门禁选深评面板。默认关。
    wide_screen: bool = False


# 路径不能用 /skills/quota —— api/__init__.py 已经有 /api/skills/{skill_type}，
# 那条动态路由会把 "quota" 当成技能类型名匹配掉，返回 404「技能类型 'quota' 不存在」。
# 两个 router 挂在同一个 /api 前缀下，谁先注册谁先匹配，靠顺序取胜是隐患。
@router.get("/skill-quota")
async def skill_quota(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    """每个高级技能还剩几次免费体验。null = 不受限（BYOK / 匿名桶 / 机制关闭）。

    单独开一个接口而不是塞进 /api/usage：技能次数与配额是两套独立的东西
    （配额管"能不能发起评审"，这个管"发起时带不带那一层"），混在一个响应里
    迟早有人把两个数字当成同一件事。
    """
    from app.services import key_service, skill_quota_service

    # 必须知道"这个用户此刻会用谁的 key"，否则 BYOK 用户会看到一个根本不适用于
    # 他的数字。解析失败（还没配任何 key）按平台垫付算——那时他看到的次数
    # 正是真实会遇到的限制。
    try:
        key_source = key_service.resolve_key(db, identity.user_id).source
    except Exception:
        key_source = "server"

    return {
        "key_source": key_source,
        "free_uses": settings.skill_free_uses,
        "skills": {
            skill: skill_quota_service.uses_left(db, identity.user_id, skill, key_source)
            for skill in sorted(settings.premium_skills)
        },
    }


@router.post(
    "/v2/reviews",
    status_code=202,
    dependencies=[Depends(rate_limit("review", None, 3600))],
)
async def create_review_v2(
    body: CreateReviewRequest,
    identity: Identity = Depends(optional_identity),
    resolved=Depends(resolve_llm_key),  # 无 key → 428，绝不返回模拟数据
    db: Session = Depends(get_db),
):
    """发起评审：落库 + 入队 + 立刻返回。进度走 WS /ws/review/{id}。

    全链路守卫已在依赖里跑完（限流 → 身份 → key → 配额）。
    """
    if body.task_type not in intent_service.VALID_TASK_TYPES:
        raise BadRequest(f"未知任务类型：{body.task_type}")
    if body.mode not in intent_service.VALID_MODES:
        raise BadRequest(f"未知模式：{body.mode}")
    # 放在配额检查**之前**：材料形状错了不该白占一次配额
    # （check_quota 在放行的瞬间就预留名额，见 _reserve_review_slot）。
    _validate_artifact(body.artifact)
    # persona_pack 拼错此前静默回落 game-core——用户选 A 包，跑的是 B 包。
    # 报告的每一条人格都来自 B 包，而用户以为看到的是 A 包的视角。
    persona_pack = (body.persona_pack or "game-core").strip()
    if persona_pack not in _valid_persona_packs():
        raise BadRequest(f"未知人格包：{persona_pack}")

    quota_service.check_quota(
        db, identity.user_id, key_source=resolved.source, plan=identity.plan
    )

    from app.services import apply_skill_hint, skill_quota_service

    # 高级技能的免费次数：用完不报错，降级成普通评审并**如实告知**。
    # 必须在 apply_skill_hint 之前——降级后的值要同时用于拼 prompt 和落库，
    # 只拿提示去展示、仍按原参数跑，就成了"说降级了实际没降"。
    skill_type, enable_red_team, degraded = skill_quota_service.apply(
        db, identity.user_id, resolved.source, body.skill_type, body.enable_red_team
    )

    bundle = apply_skill_hint(body.artifact or {}, skill_type)
    if enable_red_team and skill_type != "red_team_audience":
        # 红队开关与技能选择独立：选了受众面板也能叠加对抗视角提示
        bundle = apply_skill_hint(bundle, "red_team_audience")

    # 项目记忆：同 project_key 下尚未被证伪的历史判断带进本次提示词。
    # project_key 此前只是前端分组用的显示标签，从没被读回过——同一个产品
    # 连评三版，第三版的人格对前两版一无所知。详见 project_memory_service。
    # v1 的 ReviewService.create_review 调的是同一个函数（收敛测试会盯着）。
    bundle = project_memory_service.attach_to_bundle(
        db, bundle, identity.user_id, body.project_key
    )

    review = Review(
        user_id=identity.user_id,
        task_type=body.task_type,
        target_title=(body.artifact or {}).get("title"),
        artifact_bundle=bundle,
        persona_pack=persona_pack,
        selected_personas=body.selected_personas,
        skill_type=skill_type,          # 降级后的值，不是 body 里的原值
        project_key=body.project_key,
        enable_evaluation=body.enable_evaluation,
        enable_red_team=enable_red_team,
        adaptive_panel=body.adaptive_panel,
        wide_screen=body.wide_screen,
        key_source=resolved.source,
        mode=body.mode,
        status="pending",
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    try:
        job_id = review_service.enqueue_review(
            review.id,
            api_key=resolved.key,
            key_source=resolved.source,
            user_id=identity.user_id,
            provider=resolved.provider,
            model=resolved.model,
            api_base=resolved.api_base,
        )
    except Exception as exc:
        # 落库与入队要么都成、要么都补偿：check_quota 已经扣过配额
        # （credits 扣 1 次 / plan 占 1 个名额），入队失败不补偿的话，
        # 就是"review 永久 pending + 用户次数凭空消失"。与后台收尸
        # （db._settle_reaped_reviews）共用同一套幂等退款原语。
        try:
            db.delete(review)
            db.commit()
        except Exception:
            db.rollback()
            try:
                review = db.get(Review, review.id)
                if review:
                    review.status = "failed"
                    review.error_message = "评审任务入队失败，已执行计费补偿，请重新发起"
                    db.commit()
            except Exception:
                db.rollback()
        try:
            quota_service.refund_review_credit(
                db, identity.user_id, review.id, key_source=resolved.source
            )
            quota_service.release_review_slot(
                db, identity.user_id, key_source=resolved.source
            )
        except Exception:
            db.rollback()
            logger.exception(
                "review %s 入队失败后的计费补偿也失败——用户 %s 的额度可能被吞，需人工核对",
                review.id,
                identity.user_id,
            )
        # 补偿完成后再报错：5xx 返回给调用方，但钱不能跟着一起丢
        raise AppError("评审任务入队失败，请稍后重试") from exc

    return {
        "review_id": review.id,
        "job_id": job_id,
        "status": "pending",
        "key_source": resolved.source,  # 让用户知道这次花的是谁的钱
        # 降级说明。None = 没降级。必须回给前端并显示出来——不吭声地少给一层
        # 能力，用户会以为产品本来就这样，这正是本仓库要根除的"静默降级"。
        "skill_degraded": degraded,
        "websocket": f"/ws/review/{review.id}",
    }


@router.get("/v2/reviews/{review_id}")
async def get_review_v2(
    review_id: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    review = db.get(Review, review_id)
    if not review or (review.user_id or "anonymous") != identity.user_id:
        raise NotFound("评审不存在")
    report = review.report_json
    if identity.is_anonymous:
        report = report_gating.gate_report_for_anonymous(report)
    return {
        "id": review.id,
        "task_type": review.task_type,
        # v1 详情一直回它、v2 一直漏着——被 test_review_serialization_parity
        # 抓出来的第一条真实漂移。评审标题是最基本的展示字段，
        # 走 v2 读评审的调用方没有理由拿不到。
        "target_title": review.target_title,
        "mode": review.mode,
        "persona_pack": review.persona_pack,
        "selected_personas": review.selected_personas,
        "adaptive_panel": review.adaptive_panel,
        "wide_screen": review.wide_screen,
        "skill_type": review.skill_type,
        "project_key": review.project_key,
        "status": review.status,
        "error_message": review.error_message,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
        "total_cost_usd": review.total_cost_usd,
        "input_tokens": review.input_tokens,
        "output_tokens": review.output_tokens,
        "report": report,
        "calibration": review.calibration,
        # 分享状态跟着报告一起回：报告页要据此决定"分享"按钮显示的是
        # 「生成链接」还是「已公开 + 撤销」。token 本身只给作者。
        "share_token": review.share_token,
        "shared_at": review.shared_at.isoformat() if review.shared_at else None,
    }


# ---------------------------------------------------------------------------
# 报告只读分享
#
# 目的是"把报告发给合伙人/团队看"，不是做公开广场——所以是一份一份显式开启、
# 随时可撤销的不可猜链接，没有任何聚合列表接口。
# 设计约束与字段白名单见 services/share_service.py 的模块注释。
# ---------------------------------------------------------------------------


def _owned_review_or_404(db: Session, review_id: str, identity: Identity) -> Review:
    """取自己的评审。查不到和不属于自己都回 404（不是 403）——403 等于确认
    "这个 id 存在，只是不归你"，可以拿来枚举。与项目/对话端点同一口径。"""
    review = db.get(Review, review_id)
    if not review or (review.user_id or "anonymous") != identity.user_id:
        raise NotFound("评审不存在")
    return review


@router.post(
    "/v2/reviews/{review_id}/share",
    dependencies=[Depends(rate_limit("share", 30, 3600))],
)
async def create_review_share(
    review_id: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """开启只读分享，返回 token（幂等：已开启则原样返回旧 token）。

    require_isolated_identity 这行不能省，它堵的是一条具体的绕过路径：
    匿名用户看自己的报告是被 report_gating 裁剪过的，如果匿名也能建分享链接，
    那么"跑评审 → 给自己建个链接 → 打开" 就能看到完整报告，登录墙当场作废。
    """
    require_isolated_identity(identity)
    review = _owned_review_or_404(db, review_id, identity)
    if review.status != "completed":
        # 未完成的评审分享出去，对方看到的是空壳；而 error_message 可能带着
        # 用户材料的片段。两个理由都指向"没跑完就不给分享"。
        raise BadRequest("只有已完成的评审可以分享")
    token = share_service.enable_share(db, review)
    return {
        "share_token": token,
        "shared_at": review.shared_at.isoformat() if review.shared_at else None,
    }


@router.delete("/v2/reviews/{review_id}/share")
async def revoke_review_share(
    review_id: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """撤销分享。已发出去的旧链接立刻全部失效。"""
    require_isolated_identity(identity)
    review = _owned_review_or_404(db, review_id, identity)
    share_service.disable_share(db, review)
    return {"share_token": None, "shared_at": None}


@router.get(
    "/v2/shared/{token}",
    # 唯一一个不需要任何身份的读接口。限流不是为了防爆破（43 个 base64url
    # 字符爆不动），是防批量抓取——万一某个 token 从聊天记录里泄漏出去，
    # 至少不该让人拿它当稳定的抓取入口。
    dependencies=[Depends(rate_limit("shared_view", 120, 3600))],
)
async def get_shared_review(token: str, db: Session = Depends(get_db)):
    """公开只读地取一份被分享的报告。**不做任何身份校验，这就是本意。**

    撤销后（share_token 置回 NULL）这里查不到，直接 404——和"这个 token 从来
    没存在过"是同一个响应，不泄漏"曾经有过但被撤了"。
    """
    review = share_service.get_by_token(db, token)
    if not review:
        raise NotFound("分享链接不存在或已被作者撤销")
    return share_service.to_public_dict(review)


class ChatMessageRequest(BaseModel):
    message: str
    # None = 跟评审团整体聊（追问报告结论）；给定人格 id = 跟该人格保持人设聊
    persona_id: Optional[str] = None
    # 随消息附带的截图（data URI 列表）——支持视觉的模型直接"看"，其余静默降级纯文字
    images: Optional[List[str]] = None


def _serialize_chat_message(m, gate_assistant: bool = False) -> dict:
    """gate_assistant=True（匿名用户）时裁剪 assistant 回复内容——用户自己发的
    问题从不裁剪，裁的是"AI/角色答了什么"这半边，逼真实回复价值留在登录后。"""
    content = m.content
    is_gated = False
    full_length: Optional[int] = None
    if gate_assistant and m.role == "assistant":
        from app.services import report_gating

        gated = report_gating.gate_chat_reply_for_anonymous(m.content)
        content = gated["content"]
        is_gated = gated["is_gated"]
        full_length = gated["full_length"]
    return {
        "id": m.id,
        "review_id": m.review_id,
        "persona_id": m.persona_id,
        "role": m.role,
        "content": content,
        "is_gated": is_gated,
        "full_length": full_length,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ---------------------------------------------------------------------------
# 项目：对话的分组容器（CC Desktop 风格侧栏）
#
# 与下面"对话持续化"是同一批端点的姊妹组，但先声明——项目端点在
# patch_conversation 里被引用（挂靠项目时要校验项目归属）。
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ProjectPatchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("/v2/projects")
async def list_projects(
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    from app.services import project_service

    rows = project_service.list_projects(db, identity.user_id)
    counts = project_service.conversation_counts(db, [p.id for p in rows])
    return {"projects": [project_service.to_dict(p, counts.get(p.id, 0)) for p in rows]}


@router.post(
    "/v2/projects",
    dependencies=[Depends(rate_limit("project_create", 60, 3600))],
)
async def create_project(
    body: ProjectCreateRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    from app.services import project_service

    try:
        project = project_service.create_project(db, identity.user_id, body.name)
    except ValueError as exc:
        raise BadRequest(str(exc))
    return project_service.to_dict(project, 0)


@router.patch("/v2/projects/{project_id}")
async def patch_project(
    project_id: str,
    body: ProjectPatchRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    from app.services import project_service

    project = project_service.get_owned(db, project_id, identity.user_id)
    if project is None:
        raise NotFound("项目不存在")
    try:
        project_service.rename_project(db, project, body.name)
    except ValueError as exc:
        raise BadRequest(str(exc))
    counts = project_service.conversation_counts(db, [project.id])
    return project_service.to_dict(project, counts.get(project.id, 0))


@router.delete("/v2/projects/{project_id}")
async def delete_project(
    project_id: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """删除项目。归属的对话不会被删除，只是解除挂靠、回到"未分组"——
    见 project_service.delete_project 的文档。"""
    from app.services import project_service

    project = project_service.get_owned(db, project_id, identity.user_id)
    if project is None:
        raise NotFound("项目不存在")
    unlinked = project_service.delete_project(db, project)
    return {"ok": True, "conversations_unlinked": unlinked}


# ---------------------------------------------------------------------------
# 对话持续化
#
# 与上面 /v2/reviews/{id}/chat 的分工不要搞混：
#   · 这一组   —— 评审被创建**之前**的那段来回澄清，可以一条评审都还没有
#   · reviews/chat —— 评审完成**之后**的追问，必须挂在某条 review 上
# 此前只有后者落库，前者活在前端内存里，刷新即永久丢失。
#
# 所有端点的归属校验一律回 404 而不是 403：403 等于确认"这个 id 存在但不是
# 你的"，可被用来枚举他人对话 id。口径与 review 一致。
# ---------------------------------------------------------------------------


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)


class ConversationMessageRequest(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    # 单条消息的长度上限。不设上限时，一次粘贴整本 BP 就能把单行撑到几 MB，
    # 之后每次打开这段对话都要全量拉回。
    content: str = Field(min_length=1, max_length=100_000)
    # 卡片类消息（评审卡 / 确认卡 / 附件列表）的结构化载荷：
    # 重放时要还原"当时那条气泡长什么样"，只存纯文本还原不出来。
    meta: Optional[dict] = None


class ConversationPatchRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    review_id: Optional[str] = None
    # project_id 用 model_fields_set 而不是"是否为 None"来判断有没有传：
    # 这个字段的语义天生需要区分三种情况——不传（不动项目归属）、
    # 显式传 null（移回未分组）、传具体 id（挂到某个项目）。若只看值是否
    # 为 None，后两种会被合并成同一种，"移出项目"这个操作就做不出来。
    project_id: Optional[str] = None


@router.get("/v2/conversations")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    from app.services import conversation_service

    rows = conversation_service.list_conversations(db, identity.user_id, limit, offset)
    return {"conversations": [conversation_service.to_dict(c) for c in rows]}


@router.post(
    "/v2/conversations",
    dependencies=[Depends(rate_limit("conversation_create", 60, 3600))],
)
async def create_conversation(
    body: ConversationCreateRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    from app.services import conversation_service

    conv = conversation_service.create_conversation(db, identity.user_id, body.title)
    return conversation_service.to_dict(conv)


@router.get("/v2/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    from app.services import conversation_service

    conv = conversation_service.get_owned(db, conversation_id, identity.user_id)
    if conv is None:
        raise NotFound("对话不存在")
    return conversation_service.to_dict(conv, with_messages=True)


@router.patch("/v2/conversations/{conversation_id}")
async def patch_conversation(
    conversation_id: str,
    body: ConversationPatchRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    from app.services import conversation_service

    conv = conversation_service.get_owned(db, conversation_id, identity.user_id)
    if conv is None:
        raise NotFound("对话不存在")
    if body.title is not None:
        conv.title = body.title.strip()[:200] or None
    if body.review_id is not None:
        # 只允许关联自己的评审，否则可以把任意评审 id 绑到自己的对话上，
        # 让前端顺着这条关联去拉他人报告。
        review = db.get(Review, body.review_id)
        if not review or (review.user_id or "anonymous") != identity.user_id:
            raise NotFound("评审不存在")
        conv.review_id = body.review_id
    if "project_id" in body.model_fields_set:
        if body.project_id is None:
            conv.project_id = None  # 显式移回未分组
        else:
            from app.services import project_service

            project = project_service.get_owned(db, body.project_id, identity.user_id)
            if project is None:
                # 同样的道理：把任意项目 id 绑到自己的对话上，就能顺着这条关联
                # 探测别人有没有某个项目 id（虽然项目本身不含敏感内容，但归属
                # 校验的口径必须处处一致，不能因为"反正项目没什么好偷"就放水）。
                raise NotFound("项目不存在")
            conv.project_id = project.id
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conversation_service.to_dict(conv)


@router.delete("/v2/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    from app.services import conversation_service

    conv = conversation_service.get_owned(db, conversation_id, identity.user_id)
    if conv is None:
        raise NotFound("对话不存在")
    conversation_service.delete_conversation(db, conv)
    return {"ok": True}


@router.post(
    "/v2/conversations/{conversation_id}/messages",
    dependencies=[Depends(rate_limit("conversation_message", 300, 3600))],
)
async def append_conversation_message(
    conversation_id: str,
    body: ConversationMessageRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """只做落库，不产生任何模型调用——回复由既有的评审/意图链路生成。

    这样写的原因：把"存"和"生成"绑在一起，会让持久化跟着模型调用一起失败，
    而两者的失败率完全不是一个量级。
    """
    from app.services import conversation_service

    conv = conversation_service.get_owned(db, conversation_id, identity.user_id)
    if conv is None:
        raise NotFound("对话不存在")
    try:
        msg = conversation_service.append_message(db, conv, body.role, body.content, body.meta)
    except ValueError as exc:
        raise BadRequest(str(exc))
    return {
        "id": msg.id,
        "seq": msg.seq,
        "role": msg.role,
        "content": msg.content,
        "meta": msg.meta_json,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.get("/v2/reviews/{review_id}/chat")
async def list_review_chat(
    review_id: str,
    persona_id: Optional[str] = None,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    review = db.get(Review, review_id)
    if not review or (review.user_id or "anonymous") != identity.user_id:
        raise NotFound("评审不存在")
    from app.services import chat_service

    messages = chat_service.list_messages(db, review_id, persona_id)
    return {
        "messages": [
            _serialize_chat_message(m, gate_assistant=identity.is_anonymous) for m in messages
        ]
    }


@router.post(
    "/v2/reviews/{review_id}/chat",
    dependencies=[Depends(rate_limit("review_chat", 30, 3600))],
)
async def post_review_chat(
    review_id: str,
    body: ChatMessageRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    review = db.get(Review, review_id)
    if not review or (review.user_id or "anonymous") != identity.user_id:
        raise NotFound("评审不存在")
    from app.services import chat_service

    # 匿名用户能追问，但只给回复的体验版——完整内容已存进历史，登录后
    # 同一条 thread 直接展示完整版，不需要重问。真对话在同一个对话框里，
    # 不弹窗不跳转，只是回复本身打了个"登录看完整"的马赛克。
    #
    # plan 要一路传到 chat_service：追问的配额校验（成本硬闸 / CDK 余额）按套餐取限额，
    # 不传就恒按 free 档判，付费用户会被误拦。校验本身在 send_message 里做——
    # 那里才拿得到 resolve_key 的 key_source（BYOK 豁免的判定依据）。
    reply = chat_service.send_message(
        db, review, body.message, body.persona_id, images=body.images, plan=identity.plan
    )
    return {"reply": _serialize_chat_message(reply, gate_assistant=identity.is_anonymous)}


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """任务状态与进度。归属校验与评审端点同一口径。

    这里以前连 identity 参数都没有，是全后端唯一既无身份也无归属校验的数据接口：
    知道（或撞对）一个 job_id 就能读到它的 ref_id（= review_id，拿去打评审接口的
    钥匙）和 error_message（含上游报错原文）。job_id 是 uuid4 不可枚举，
    但"不可枚举"是运气不是鉴权——review 的 id 同样是 uuid4，那边照样做归属校验。

    仍用 optional_identity 而不是强制登录：匿名也能发起评审（"先体验后注册"），
    发起后就得能查自己那条任务的进度。归属比对沿用 v2 评审端点那句
    `(row.user_id or "anonymous") != identity.user_id`——老数据 user_id 为空时
    归入匿名桶，与 Job.user_id 的默认值一致。

    没有下线这个端点：前端 apiClient 里有 getJob（当前无调用点，但它是公开
    契约的一部分，docs/ARCHITECTURE.md 也列着），后端测试也用它轮询任务状态。
    """
    row = db.get(Job, job_id)
    # 不存在与不属于你返回同一个 404：与评审端点一致，不向调用方确认某个 id 是否存在
    if not row or (row.user_id or "anonymous") != identity.user_id:
        raise NotFound("任务不存在")
    job = job_service.get_job(job_id)
    if not job:
        raise NotFound("任务不存在")
    return job


# ============================== 判断复利闭环 ==============================

class VerifyRequest(BaseModel):
    verdict: str = Field(description="hit | miss | partial | unknown")
    source: str = "playtest"
    note: Optional[str] = None


class ReviewFeedbackRequest(BaseModel):
    useful: bool
    decision_changed: bool = False
    fixes_suggested: int = Field(default=0, ge=0)
    fixes_adopted: int = Field(default=0, ge=0)
    hours_saved: float = Field(default=0, ge=0)
    willingness_to_pay_usd: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = None
    adopted_fixes: Optional[List[str]] = None


@router.get("/ledger/judgments")
async def list_judgments(
    review_id: Optional[str] = None,
    only_unverified: bool = False,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """列出历史预测（可筛未验证的 —— 这就是"待回填"工作台）。

    这里返回的 claim 是各角色提出问题的**原文**，和报告正文同源。所以它既是
    个人数据，也是报告门禁的一个侧门：/reviews/{id}/report 对匿名做了脱敏，
    而这个接口没有，未登录访客曾能从这里把别人评审的结论一条条读出来。
    """
    require_isolated_identity(identity)
    # service 已返回 {"judgments": [...], "truncated": bool}，直接透传。
    # truncated=true 时前端把总数显示成 "N+"——正好取满 limit 的数字不可信。
    return ledger_service.list_judgments(
        db, identity.user_id, review_id=review_id, only_unverified=only_unverified
    )


@router.post("/ledger/judgments/{judgment_id}/verify")
async def verify_judgment(
    judgment_id: str,
    body: VerifyRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """回填真实结果 —— 闭环的另一半。真人测试回来后调这个。"""
    return ledger_service.verify_judgment(
        db, judgment_id, body.verdict, identity.user_id, body.source, body.note
    )


class UserJudgmentRequest(BaseModel):
    """用户自己的判断。claim 必填——没有内容的判断无法被证伪，也就无法回填。"""

    claim: str
    stance: str  # agree | disagree | partial
    confidence: Optional[float] = None
    rationale: Optional[List[str]] = None
    based_on_judgment_id: Optional[str] = None


@router.post("/ledger/reviews/{review_id}/my-judgment")
async def create_my_judgment(
    review_id: str,
    body: UserJudgmentRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """记录**用户自己的**判断（与评审团的预测并列留档）。

    留档层此前只记评审团的预测，回填后也只能回答"评审团准不准"。
    用户真正关心的是自己的判断在变准——所以两边都要记，用同一套回填与
    校准算法，日后才可比。
    """
    require_isolated_identity(identity)
    return ledger_service.create_user_judgment(
        db,
        review_id=review_id,
        user_id=identity.user_id,
        claim=body.claim,
        stance=body.stance,
        confidence=body.confidence,
        rationale=body.rationale,
        based_on_judgment_id=body.based_on_judgment_id,
    )


@router.get("/ledger/scoreboard")
async def ledger_scoreboard(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    """你 vs 评审团：同一批回填结果下两个来源各自的命中率。

    双方都有已定论样本时才给对比结论——不拿 0/0 拼一个"你领先"出来。
    """
    require_isolated_identity(identity)
    return ledger_service.scoreboard(db, identity.user_id)


@router.get("/ledger/hit-rate")
async def hit_rate(
    persona_id: Optional[str] = None,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """历史命中率。样本不足时会如实标注 low_confidence。"""
    require_isolated_identity(identity)
    return ledger_service.hit_rate(db, identity.user_id, persona_id)


@router.get("/ledger/calibration")
async def confidence_calibration(
    persona_id: Optional[str] = None,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """置信度与真实回填结果的可靠性：Brier 分数、ECE 与分箱明细。"""
    require_isolated_identity(identity)
    return ledger_service.confidence_calibration(db, identity.user_id, persona_id)


@router.get("/ledger/leaderboard")
async def leaderboard(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    """各人格历史命中率排行——"谁的判断最值得听"。"""
    require_isolated_identity(identity)
    return {"personas": ledger_service.persona_leaderboard(db, identity.user_id)}


# ============================== 产品价值验证 ==============================

@router.post("/validation/reviews/{review_id}/feedback")
async def record_review_feedback(
    review_id: str,
    body: ReviewFeedbackRequest,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """回填报告是否真正影响决策；同一评审重复提交时更新。"""
    data = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    return validation_service.upsert_feedback(db, review_id, identity.user_id, data)


@router.get("/validation/metrics")
async def validation_metrics(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    """采用率、决策影响、节省时间与付费意愿。

    按 user_id 聚合，所以在共享匿名桶下算的是"所有未登录访客加起来"的数字——
    既不是调用方自己的，也把别人做过多少次评审透了出去。
    """
    require_isolated_identity(identity)
    return validation_service.metrics(db, identity.user_id)
