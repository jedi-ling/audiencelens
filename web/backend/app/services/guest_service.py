"""游客身份铸造 + 一次性体验额度 + 绑定邮箱转正。

背景：匿名访客发起评审时默认落在共享的 anonymous 桶里（deps.is_shared_anonymous）——
所有没登录的人是同一个身份，谁都能看到谁的评审。这套机制此前只在 CDK 免登录兑换时
才会给访客铸造一个独立身份（cdk_service 附近的散落代码）；现在铸造时机扩展到
"第一次发起评审"，并且直接赠送 3 次体验额度（不依赖 CDK），换回的会话令牌交给
前端存起来，同一个人后续发起评审、查报告都落在这同一个游客身份下,不再共享匿名桶。

这个额度只对**服务端垫付 key**的评审生效——BYOK 用户自己付钱，不该被这个闸拦。
它与 quota_free_reviews_per_day（全局每日刷新的免费额度）是两件独立的事：
后者按天重置、对所有匿名/免费档用户生效；这个是游客个人的一次性额度。
用完之后有三条路：绑定邮箱转正（走正常的 plan/credits 配额）、填自己的 key，
或者**兑换 CDK**——第三条曾经是假的：guest_needs_credit_gate 对 credits=0
同样为真，于是兑过码的游客在余额被查一眼之前就先 402 了，那 10 次一次也花不出去，
而 redeem_cdk 的文档白纸黑字写着"无需注册登录"。现在由 create_review_v2 里
那段"试用用完就落回正常配额链路"负责（见那边的注释）。

铸造身份本身是要限速的，见下面 GUEST_MINT_PER_DAY —— 没有它的话，
"每个游客 3 次"对同一个人毫无约束力。
"""

import re
import uuid
from typing import Dict, Optional, Tuple

from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import RateLimited
from app.core.ratelimit import get_limiter
from app.core.security import hash_password
from app.deps import (
    Identity,
    _client_key,
    is_shared_anonymous,
    issue_session_token,
    revoke_user_sessions,
)
from app.models import (
    CdkRedemption,
    Conversation,
    CreditLedger,
    Job,
    Judgment,
    Project,
    Review,
    ReviewFeedback,
    UploadedFile,
    UsageRecord,
    User,
)

GUEST_FREE_REVIEWS = 3

# ---- 铸造游客身份本身的限流 ----
#
# 为什么光有 GUEST_FREE_REVIEWS 不够：身份是**免费铸造**的。
# 「每个游客送 3 次」这句话只有在"一个人拿不到很多个游客身份"时才成立，
# 而 ensure_individual_identity 此前对每一个不带令牌的请求都铸一个新身份、
# 送 3 次额度、并且因为 guest_gated 跳过了 check_quota —— 攻击者写个循环
# 就能拿到**无限次平台垫付的评审**（烧的是运营者的模型费），顺带每次留下
# 一行 users 和一次 200k 轮的 PBKDF2。评审接口那道 rate_limit("review", 20, 3600)
# 拦不住这件事：它拦的是"每小时几次评审"，而这里要拦的是"每天能变出几个人"。
#
# 上限取 3 = 与赠额同一个数量级（一天最多 3 个身份 × 3 次 = 9 次垫付评审），
# 再多就该注册或自带 key 了。窗口 24 小时。
# 键按 _client_key(request) 取（未登录时即来源 IP），与评审限流分桶——
# 两者语义不同，共用一个桶会互相吃额度（见 deps 里 auth_register 分桶的教训）。
#
# ⚠️ 与仓库里其他限流同一套底座：进程内令牌桶，多 worker / 多副本时每个进程
# 各算各的，要真正封顶得换 Redis 后端（app/core/ratelimit.py 顶部已写明换法）。
GUEST_MINT_PER_DAY = 3
GUEST_MINT_WINDOW_SECONDS = 86400.0
GUEST_MINT_SCOPE = "guest_mint"

# 与 api/platform.py 的 register() 同一条正则——两处各自维护一份轻量校验，
# 没有共享成一个模块，因为这就一行；真出现漂移，两处的错误提示本身就会
# 先暴露出来（同一份用户输入在两条路径校验结果不一致）。
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# 游客行的密码字段。不是 pbkdf2 格式，verify_password 对它恒为 False——
# 与"随机密码的 PBKDF2 摘要"一样不可登录，但不用为每个访客烧 200k 轮哈希：
# 游客现在是每个新访客第一次请求就铸造（见 mint_cookie_guest），
# 那份哈希开销会直接变成 /auth/me 上的 CPU 放大器。
GUEST_PASSWORD_MARKER = "!guest-no-login"

GUEST_IDENTITY_SCOPE = "guest_identity"
GUEST_IDENTITY_WINDOW_SECONDS = 3600.0


def mint_guest(
    db: Session, credits: int = GUEST_FREE_REVIEWS, ttl_seconds: Optional[int] = None
) -> Tuple[str, str]:
    """铸造一个独立的游客身份，赠送体验额度，返回 (user_id, session_token)。

    credits 传 0 表示"身份照发、试用不送"：guest_review_credits=0 与 NULL
    是两回事——0 仍受游客额度闸约束（用完了），NULL 才是不受约束。
    """
    guest = User(
        email=f"guest-{uuid.uuid4().hex[:12]}@guest.local",
        password_hash=GUEST_PASSWORD_MARKER,
        display_name="游客",
        is_guest=True,
        guest_review_credits=credits,
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    token = issue_session_token(db, guest.id, ttl_seconds=ttl_seconds)
    return guest.id, token


def mint_cookie_guest(db: Session, request) -> Tuple[User, str]:
    """给没有任何会话的访客铸造游客身份，返回 (User, 放进 cookie 的令牌)。

    两道闸，语义不同，分开数：
      · 身份闸（guest_identity_per_hour）——拦"写个循环刷出无数 users 行"。
        超了就 429：宁可拒绝，也绝不回落到共享 anonymous 桶。
      · 试用闸（GUEST_MINT_PER_DAY，沿用原来的每日 3 个）——拦"每个身份送 3 次"
        被刷成无限次平台垫付评审。超了身份照发，只是 credits=0：
        这个游客能用 BYOK / CDK / 注册，但拿不到新的免费试用。
    """
    from app.services import admin_settings_service

    if admin_settings_service.get(db, "ratelimit_enabled", settings.ratelimit_enabled):
        key = f"{GUEST_IDENTITY_SCOPE}:{_client_key(request)}"
        if not get_limiter().allow(key, settings.guest_identity_per_hour, GUEST_IDENTITY_WINDOW_SECONDS):
            raise RateLimited(
                "同一来源短时间内创建的访客会话过多，请稍后再试，或登录后继续。"
            )
    credits = GUEST_FREE_REVIEWS if mint_allowed(db, request) else 0
    user_id, token = mint_guest(db, credits=credits, ttl_seconds=settings.guest_cookie_ttl_seconds)
    return db.get(User, user_id), token


def mint_allowed(db: Session, request) -> bool:
    """这个来源今天还能不能再铸一个游客身份。

    跟着全局限流总开关走（ratelimit_enabled，后台面板可实时覆盖）——
    与仓库里其他限流一致：运营者关掉限流就是关掉所有限流，不搞例外，
    否则"我把限流关了但还是被 429"会成为一个没人查得出来的谜题。
    """
    from app.services import admin_settings_service

    if not admin_settings_service.get(db, "ratelimit_enabled", settings.ratelimit_enabled):
        return True
    key = f"{GUEST_MINT_SCOPE}:{_client_key(request)}"
    return get_limiter().allow(key, GUEST_MINT_PER_DAY, GUEST_MINT_WINDOW_SECONDS)


def ensure_individual_identity(db: Session, identity: Identity, request) -> Tuple[str, Optional[str]]:
    """共享匿名桶 → 铸造个体游客身份；已经是具名或游客身份则原样放行。

    返回 (本次请求实际应使用的 user_id, 新铸造时的会话令牌否则 None)。
    调用方需要把非 None 的令牌交还给前端——不这样做的话，游客这次评审记进了
    一个全新身份，但浏览器手里没有对应的登录态，下次刷新页面又回落回匿名桶，
    看不到自己刚发起的这条评审，体验上等同于"评审凭空消失"。

    request 是必填的，不给默认值：铸造闸（见 GUEST_MINT_PER_DAY）必须有一个
    来源标识才能生效，留一个 `request=None` 的默认参数就等于给未来的调用点
    留了一个静默绕过整道闸的入口。
    """
    if is_shared_anonymous(identity):
        if not mint_allowed(db, request):
            # 注意：这里**不铸造**。铸了再拒等于攻击者照样能刷出 users 行 + PBKDF2。
            raise RateLimited(
                f"同一来源每天最多体验 {GUEST_MINT_PER_DAY} 次免登录评审，今天的已经用完。"
                "注册一个账号即可继续（历史评审也能认领过去），"
                "或在设置里填写自己的 API Key（BYOK）不受此限制。"
            )
        return mint_guest(db)
    return identity.user_id, None


def is_guest(db: Session, user_id: str) -> bool:
    row = db.query(User.is_guest).filter(User.id == user_id).first()
    return bool(row and row[0])


def try_consume_guest_credit(db: Session, user_id: str) -> bool:
    """原子地"查游客额度并扣一次"，返回是否扣成功。

    guest_review_credits 为 NULL（非游客，或老库存量游客未曾获得这个字段）
    的账号不受这个闸约束，直接放行——见字段注释：NULL 与"0=用完"是两个
    不同状态，不能混为一谈。
    """
    result = db.execute(
        text(
            "UPDATE users SET guest_review_credits = guest_review_credits - 1 "
            "WHERE id = :uid AND guest_review_credits > 0"
        ),
        {"uid": user_id},
    )
    db.commit()
    return result.rowcount == 1


def guest_needs_credit_gate(db: Session, user_id: str) -> bool:
    """这个用户是否受游客额度闸约束——即 guest_review_credits 不是 NULL。"""
    row = db.query(User.guest_review_credits).filter(User.id == user_id).first()
    return bool(row and row[0] is not None)


def refund_guest_credit(db: Session, user_id: str) -> bool:
    """评审失败时退还一次游客额度。返回"这次真的退了吗"。

    三个调用点（三条评审失败路径必须都覆盖，缺一条就是"扣了不退"）：
      · create_review_v2 的入队失败补偿块（同步）；
      · review_service._execute_review 的失败分支（后台线程）；
      · db._settle_reaped_reviews 的启动收尸（进程重启）。
    后两条以前退的是 **CDK 次数**，而游客评审压根没扣过 CDK——
    refund_review_credit → cdk_service.refund_credit 是"按 review_id 幂等地写一条 +1"，
    不是"撤销刚才那条 -1"，于是一次失败的游客评审会**凭空发一次 CDK 余额**，
    绑定邮箱之后就能真的花出去。详见 review_service / db 两处的注释。

    不像 CDK 走流水表保证幂等——这个字段是一次性的个人额度，用
    `< GUEST_FREE_REVIEWS` 这个条件封顶即可：无论被触发几次，余额都不可能
    超过当初赠送的数量，"退款循环 = 无限额度"这条路直接被 SQL 堵死，
    比再搭一套流水表便宜得多。
    """
    result = db.execute(
        text(
            "UPDATE users SET guest_review_credits = guest_review_credits + 1 "
            "WHERE id = :uid AND guest_review_credits IS NOT NULL "
            "AND guest_review_credits < :cap"
        ),
        {"uid": user_id, "cap": GUEST_FREE_REVIEWS},
    )
    db.commit()
    return result.rowcount == 1


class BindEmailError(ValueError):
    pass


def bind_email(db: Session, user_id: str, email: str, password: str) -> User:
    """把当前游客账号原地转正：换真邮箱/真密码，同一个 user_id 不变。

    历史评审/判断/额度全部挂在这同一行 User 上，转正不需要另建账号再迁移
    数据——这正是"游客身份是真实 User 行"这个设计从一开始就要换的好处。
    """
    email = email.strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 254:
        raise BindEmailError("邮箱格式不正确")
    if len(password) < 8:
        raise BindEmailError("密码至少 8 位")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise BindEmailError("账号不存在")
    if not user.is_guest:
        raise BindEmailError("这不是一个游客账号，不能用这条接口绑定")

    existing = db.query(User).filter(User.email == email, User.id != user_id).first()
    if existing is not None:
        # 与 register() 同一句措辞——不说"已注册"，避免替枚举者确认邮箱归属
        raise BindEmailError("该邮箱不可用，请更换邮箱；若已有账号请直接登录")

    user.email = email
    user.password_hash = hash_password(password)
    user.is_guest = False
    user.guest_review_credits = None  # 转正后走正常配额，不再受这个闸约束
    user.display_name = user.display_name if user.display_name and user.display_name != "游客" else None
    try:
        db.commit()
    except IntegrityError:
        # 上面的预检只挡顺序请求：两个人同时拿同一个邮箱绑定（或一边绑定一边注册）
        # 都能通过预检，最后靠 users.email 的唯一约束兜底。不捕获就是 500，
        # 而"这个邮箱不可用"是一个业务结果，必须和预检那条走同一个 400。
        # 与 api/platform.register() 里同型的处理保持一致。
        db.rollback()
        raise BindEmailError("该邮箱不可用，请更换邮箱；若已有账号请直接登录")
    db.refresh(user)

    # 转正 = 换了身份性质，旧的游客 JWT 必须当场作废。
    # 不作废的后果不是"多一把令牌"：那把 7 天有效期的游客令牌是在 CDK 兑换
    # 响应里发出去、存在浏览器 localStorage 里的，转正后它认证的是**同一个
    # user_id**，也就是现在这个有真邮箱真密码的正式账号。任何拿到过那把旧令牌
    # 的人（共用过设备、抓过那次响应、读过 localStorage）都能继续以正式账号
    # 身份登录，而用户以为自己刚设的密码就是这个账号的唯一入口。
    # 复用改密码那条路已有的撤销机制（deps.revoke_user_sessions + iat 比对），
    # 不另起一套——两套"作废会话"的实现迟早会分岔。
    # 调用方随后必须用 deps.issue_session_token 发新令牌（它会把 iat 抬到
    # 不早于撤销点），直接 create_token 会当场被自己刚写下的撤销声明打掉。
    revoke_user_sessions(db, user.id)
    return user


# ============================================================================
# legacy 共享匿名桶的隔离（scripts/quarantine_anonymous.py 调用）
# ============================================================================
# 隔离 legacy 共享匿名桶里的存量数据。
#
# 背景：游客身份 cookie 上线之前，AL_AUTH_ENABLED=true 的实例上所有未登录访客
# 共用 user_id = "anonymous"（见 deps.resolve_guest_identity 的说明）。那段时间里
# 访客建的对话、项目、上传、跑的评审全部写在这一个 id 名下，任何未登录访客都能
# 列出、读取、改写、删除。新代码已经不会再让任何请求解析成 "anonymous"，
# 但库里的存量行还在——它们不属于任何人，也不该再被任何人看到。
#
# 做法：把这些行改挂到一个**不对应任何 User 行**的固定 owner（QUARANTINE_OWNER）。
# 不删：数据真正的主人无从识别（那正是共享桶的问题），删了就再也找不回来；
# 运营者日后若能凭别的线索确认归属，可以手工改挂回去。
#
# 幂等：第二次跑时已经没有 "anonymous" 行可改，所有计数为 0。
#
# user_id 为 NULL 的行同样隔离（仅限"内容"表）：v1 归属校验以前把 NULL 当作
# "无主历史数据，谁都能看"，它们和 anonymous 行一样是公共空间。
# 计量/财务表（UsageRecord / CreditLedger / CdkRedemption / ReviewFeedback）的
# user_id 是 NOT NULL，只处理 "anonymous"——改挂后共享桶的 CDK 余额也就不再
# 能被任何访客花掉。

QUARANTINE_OWNER = "quarantine:legacy-anonymous"

# (模型, 是否连 NULL 一起隔离)
TABLES = (
    (Review, True),
    (Conversation, True),
    (Project, True),
    (UploadedFile, True),
    (Judgment, True),
    (Job, True),
    (ReviewFeedback, False),
    (UsageRecord, False),
    (CreditLedger, False),
    (CdkRedemption, False),
)


def _condition(model, include_null: bool):
    anon = model.user_id == settings.anonymous_user_id
    return or_(anon, model.user_id.is_(None)) if include_null else anon


def count_legacy_rows(db: Session) -> Dict[str, int]:
    return {
        model.__tablename__: db.query(model).filter(_condition(model, include_null)).count()
        for model, include_null in TABLES
    }


def quarantine_legacy_anonymous(db: Session, apply: bool = False) -> Dict[str, int]:
    """返回每张表命中的行数；apply=False 时只统计不改动。"""
    counts = count_legacy_rows(db)
    if not apply:
        return counts
    for model, include_null in TABLES:
        db.query(model).filter(_condition(model, include_null)).update(
            {"user_id": QUARANTINE_OWNER}, synchronize_session=False
        )
    db.commit()
    return counts
