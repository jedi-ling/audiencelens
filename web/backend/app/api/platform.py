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
from app.deps import Identity, current_identity, optional_identity, rate_limit, resolve_llm_key
from app.models import Review, User
from app.services import (
    intent_service,
    job_service,
    key_service,
    ledger_service,
    plan_service,
    quota_service,
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
        raise BadRequest("该邮箱已注册")
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
    if not user or not verify_password(body.password, user.password_hash):
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
    provider: str = "anthropic"


@router.get("/keys")
async def list_keys(
    identity: Identity = Depends(current_identity), db: Session = Depends(get_db)
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
                "masked": r.key_masked,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            }
            for r in rows
        ],
    }


@router.post("/keys")
async def save_key(
    body: SaveKeyRequest,
    identity: Identity = Depends(current_identity),
    db: Session = Depends(get_db),
):
    try:
        row = key_service.save_user_key(db, identity.user_id, body.api_key, body.provider)
    except ValueError as exc:
        raise BadRequest(str(exc))
    return {"provider": row.provider, "masked": row.key_masked}


@router.delete("/keys/{provider}")
async def delete_key(
    provider: str,
    identity: Identity = Depends(current_identity),
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
    identity: Identity = Depends(current_identity),
    db: Session = Depends(get_db),
):
    """把一句大白话解析成评审参数。

    无 key 也能用：自动降级到启发式规则档（返回 method=heuristic 如实声明）。
    """
    api_key = None
    try:
        api_key = key_service.resolve_key(db, identity.user_id).key
    except Exception:
        api_key = None  # 没 key 就走启发式，不阻断

    result = intent_service.parse_intent(body.text, api_key)
    return result.to_dict()


# ============================== 上传 ==============================

@router.post("/uploads", dependencies=[Depends(rate_limit("upload", 20, 3600))])
async def upload_file(
    file: UploadFile = File(...),
    identity: Identity = Depends(current_identity),
):
    """上传材料文件，返回可直接作为 artifact 的文本内容。"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in settings.upload_allowed_ext:
        raise BadRequest(
            f"不支持的文件类型 {ext or '(无扩展名)'}；"
            f"允许：{', '.join(sorted(settings.upload_allowed_ext))}"
        )

    raw = await file.read()
    if len(raw) > settings.upload_max_bytes:
        raise BadRequest(f"文件超过上限 {settings.upload_max_bytes // 1024 // 1024} MB")

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
        "stored_as": stored_name,
        "size": len(raw),
        "text": text,
    }


# ============================== 用量 / 配额 / 套餐 ==============================

@router.get("/plans")
async def plans():
    """公开定价页数据：三档套餐及各自限额（无需登录）。"""
    return {"plans": plan_service.list_plans()}


@router.get("/usage")
async def usage(
    identity: Identity = Depends(current_identity), db: Session = Depends(get_db)
):
    return quota_service.usage_summary(db, identity.user_id, plan=identity.plan)


# ============================== 异步评审（v2 链路）==============================

class CreateReviewRequest(BaseModel):
    task_type: str
    artifact: dict = Field(description="材料包：{title, materials:[{type,text}]}")
    mode: str = "standard"
    persona_pack: str = "game-core"


@router.post(
    "/v2/reviews",
    status_code=202,
    dependencies=[Depends(rate_limit("review", None, 3600))],
)
async def create_review_v2(
    body: CreateReviewRequest,
    identity: Identity = Depends(current_identity),
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

    review = Review(
        user_id=identity.user_id,
        task_type=body.task_type,
        target_title=(body.artifact or {}).get("title"),
        artifact_bundle=body.artifact or {},
        persona_pack=body.persona_pack,
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
    identity: Identity = Depends(current_identity),
    db: Session = Depends(get_db),
):
    review = db.get(Review, review_id)
    if not review or (review.user_id or "anonymous") != identity.user_id:
        raise NotFound("评审不存在")
    return {
        "id": review.id,
        "task_type": review.task_type,
        "mode": review.mode,
        "status": review.status,
        "error_message": review.error_message,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
        "total_cost_usd": review.total_cost_usd,
        "report": review.report_json,
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
    identity: Identity = Depends(current_identity),
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
    identity: Identity = Depends(current_identity),
    db: Session = Depends(get_db),
):
    """回填真实结果 —— 闭环的另一半。真人测试回来后调这个。"""
    return ledger_service.verify_judgment(
        db, judgment_id, body.verdict, identity.user_id, body.source, body.note
    )


@router.get("/ledger/hit-rate")
async def hit_rate(
    persona_id: Optional[str] = None,
    identity: Identity = Depends(current_identity),
    db: Session = Depends(get_db),
):
    """历史命中率。样本不足时会如实标注 low_confidence。"""
    return ledger_service.hit_rate(db, identity.user_id, persona_id)


@router.get("/ledger/leaderboard")
async def leaderboard(
    identity: Identity = Depends(current_identity), db: Session = Depends(get_db)
):
    """各人格历史命中率排行——"谁的判断最值得听"。"""
    return {"personas": ledger_service.persona_leaderboard(db, identity.user_id)}


# ============================== 产品价值验证 ==============================

@router.post("/validation/reviews/{review_id}/feedback")
async def record_review_feedback(
    review_id: str,
    body: ReviewFeedbackRequest,
    identity: Identity = Depends(current_identity),
    db: Session = Depends(get_db),
):
    """回填报告是否真正影响决策；同一评审重复提交时更新。"""
    data = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    return validation_service.upsert_feedback(db, review_id, identity.user_id, data)


@router.get("/validation/metrics")
async def validation_metrics(
    identity: Identity = Depends(current_identity), db: Session = Depends(get_db)
):
    """采用率、决策影响、节省时间与付费意愿。"""
    return validation_service.metrics(db, identity.user_id)
