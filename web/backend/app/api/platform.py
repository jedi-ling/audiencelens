"""平台链路路由：健康检查 / 认证 / BYOK Key / 意图解析 / 上传 / 用量 / 判断复利闭环 / 异步评审。

这些是"预埋线"的对外出口。原有 /api 业务路由（personas、task-types 等）不受影响。
"""

import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest, NotFound, Unauthorized
from app.core.security import create_token, hash_password, verify_password
from app.db import get_db
from app.deps import Identity, optional_identity, rate_limit, resolve_llm_key
from app.models import Review, User
from app.services import (
    intent_service,
    job_service,
    key_service,
    ledger_service,
    plan_service,
    quota_service,
    report_gating,
    review_service,
    validation_service,
)

router = APIRouter()


# ============================== 健康检查 ==============================

@router.get("/health")
async def health():
    """探活 + 当前生效的链路开关（绝不泄露密钥）。"""
    return {"status": "ok", "config": settings.sanitized()}


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


@router.post("/auth/register", dependencies=[Depends(rate_limit("auth", 10, 3600))])
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    _require_auth_enabled()
    email = body.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        # 不说"已注册"——那等于替枚举者确认这个邮箱存在账号
        raise BadRequest("该邮箱不可用，请更换邮箱；若已有账号请直接登录")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        display_name=body.display_name or email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
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
    token = create_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
    return {"token": token, "user": {"id": user.id, "email": user.email, "plan": user.plan}}


@router.get("/auth/me")
async def me(identity: Identity = Depends(optional_identity)):
    return identity.to_dict()


# ============================== BYOK Key（埋线）==============================

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
    """回显当前 key 状态（仅掩码，绝不返回明文）。"""
    from app.models import UserApiKey

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
    api_key = body.api_key
    model = body.model
    api_base = body.api_base
    if not api_key:
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
    try:
        resolved = key_service.resolve_key(db, identity.user_id)
        api_key = resolved.key
        provider = resolved.provider
        model = resolved.model
        api_base = resolved.api_base
    except Exception:
        api_key = None  # 没 key 就走启发式，不阻断

    result = intent_service.parse_intent(body.text, api_key, provider=provider, model=model, api_base=api_base)
    return result.to_dict()


# ============================== 上传 ==============================

_IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@router.post("/uploads", dependencies=[Depends(rate_limit("upload", 20, 3600))])
async def upload_file(
    file: UploadFile = File(...),
    identity: Identity = Depends(optional_identity),
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
        return {
            "filename": file.filename,
            "kind": "image",
            "size": len(raw),
            "image_data": data_uri,
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

    os.makedirs(settings.upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.upload_dir, stored_name), "w", encoding="utf-8") as f:
        f.write(text)

    return {
        "filename": file.filename,
        "kind": "text",
        "stored_as": stored_name,
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
        guest_token = create_token(user_id, settings.jwt_secret, settings.jwt_ttl_seconds)

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
    return quota_service.usage_summary(db, identity.user_id, plan=identity.plan)


# ============================== 异步评审（v2 链路）==============================

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

    quota_service.check_quota(
        db, identity.user_id, key_source=resolved.source, plan=identity.plan
    )

    from app.services import apply_skill_hint

    review = Review(
        user_id=identity.user_id,
        task_type=body.task_type,
        target_title=(body.artifact or {}).get("title"),
        artifact_bundle=apply_skill_hint(body.artifact or {}, body.skill_type),
        persona_pack=body.persona_pack,
        selected_personas=body.selected_personas,
        skill_type=body.skill_type,
        project_key=body.project_key,
        mode=body.mode,
        status="pending",
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    job_id = review_service.enqueue_review(
        review.id,
        api_key=resolved.key,
        key_source=resolved.source,
        user_id=identity.user_id,
        provider=resolved.provider,
        model=resolved.model,
        api_base=resolved.api_base,
    )

    return {
        "review_id": review.id,
        "job_id": job_id,
        "status": "pending",
        "key_source": resolved.source,  # 让用户知道这次花的是谁的钱
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
        "mode": review.mode,
        "status": review.status,
        "error_message": review.error_message,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
        "total_cost_usd": review.total_cost_usd,
        "report": report,
        "calibration": review.calibration,
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
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
    """列出历史预测（可筛未验证的 —— 这就是"待回填"工作台）。"""
    return {
        "judgments": ledger_service.list_judgments(
            db, identity.user_id, review_id=review_id, only_unverified=only_unverified
        )
    }


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


@router.get("/ledger/hit-rate")
async def hit_rate(
    persona_id: Optional[str] = None,
    identity: Identity = Depends(optional_identity),
    db: Session = Depends(get_db),
):
    """历史命中率。样本不足时会如实标注 low_confidence。"""
    return ledger_service.hit_rate(db, identity.user_id, persona_id)


@router.get("/ledger/leaderboard")
async def leaderboard(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    """各人格历史命中率排行——"谁的判断最值得听"。"""
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
    """采用率、决策影响、节省时间与付费意愿。"""
    return validation_service.metrics(db, identity.user_id)
