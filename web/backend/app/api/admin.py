"""后台管理路由：运行时配置、平台级 API Key、系统概览、任务与评审巡检。

全部挂在 Depends(require_admin) 之后——未设置 AL_ADMIN_TOKEN 时整体 503，
配置后需要 X-Admin-Token 请求头匹配才能访问。见 docs/MAINTENANCE.md 的
「后台管理面板」一节。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.db import get_db
from app.deps import require_admin
from app.models import Job, Judgment, Review, UsageRecord, User
from app.services import admin_settings_service, key_service, plan_service

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


# ============================== 系统概览 ==============================

@router.get("/overview")
async def overview(db: Session = Depends(get_db)):
    """跨用户聚合视图——管理员看的是全局，不是某一个 user_id 的切片。"""
    since_24h = datetime.now(timezone.utc) - timedelta(days=1)

    review_counts = dict(
        db.query(Review.status, func.count(Review.id)).group_by(Review.status).all()
    )
    total_reviews = sum(review_counts.values())

    usage_24h = (
        db.query(
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
        )
        .filter(UsageRecord.created_at >= since_24h)
        .one()
    )
    usage_by_source = dict(
        db.query(UsageRecord.key_source, func.coalesce(func.sum(UsageRecord.cost_usd), 0.0))
        .filter(UsageRecord.created_at >= since_24h)
        .group_by(UsageRecord.key_source)
        .all()
    )

    total_judgments = db.query(func.count(Judgment.id)).scalar() or 0
    verified_judgments = db.query(func.count(Judgment.id)).join(
        Judgment.outcome
    ).scalar() or 0

    total_users = db.query(func.count(User.id)).scalar() or 0

    active_jobs = dict(
        db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    )

    return {
        "reviews": {"total": total_reviews, "by_status": review_counts},
        "usage_24h": {
            "count": int(usage_24h[0] or 0),
            "cost_usd_total": round(float(usage_24h[1] or 0.0), 4),
            "cost_usd_by_source": {k: round(float(v), 4) for k, v in usage_by_source.items()},
        },
        "judgments": {"total": total_judgments, "verified": verified_judgments},
        "registered_users": total_users,
        "jobs_by_status": active_jobs,
    }


# ============================== 运行时配置 ==============================

class SettingUpdate(BaseModel):
    key: str
    value: Any


@router.get("/settings")
async def list_settings(db: Session = Depends(get_db)):
    """每一项的当前有效值、是否被后台覆盖、env 默认值——面板据此渲染表单。"""
    return {"settings": admin_settings_service.get_all_effective(db)}


@router.put("/settings")
async def update_setting(body: SettingUpdate, db: Session = Depends(get_db)):
    return admin_settings_service.set_override(db, body.key, body.value)


@router.delete("/settings/{key}")
async def reset_setting(key: str, db: Session = Depends(get_db)):
    """清除覆盖值，回落到环境变量默认值。"""
    cleared = admin_settings_service.clear_override(db, key)
    return {"key": key, "cleared": cleared}


# ============================== 平台级 API Key ==============================

class ServerKeyUpdate(BaseModel):
    api_key: str
    provider: str = "anthropic"


@router.get("/server-key")
async def server_key_status(db: Session = Depends(get_db)):
    status = key_service.get_platform_key_status(db)
    return {"configured": status is not None, "key": status}


@router.put("/server-key")
async def set_server_key(body: ServerKeyUpdate, db: Session = Depends(get_db)):
    try:
        row = key_service.save_platform_key(db, body.api_key, body.provider)
    except ValueError as exc:
        raise BadRequest(str(exc))
    return {"provider": row.provider, "masked": row.key_masked}


@router.delete("/server-key")
async def delete_server_key(provider: str = "anthropic", db: Session = Depends(get_db)):
    n = key_service.delete_platform_key(db, provider)
    return {"deleted": n}


# ============================== 套餐（只读；调整需求见 docs） ==============================

@router.get("/plans")
async def list_plans():
    return {"plans": plan_service.list_plans()}


# ============================== 任务 / 评审巡检 ==============================

@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)
):
    q = db.query(Job).order_by(Job.created_at.desc())
    if status:
        q = q.filter(Job.status == status)
    rows = q.limit(min(limit, 200)).all()
    return {
        "jobs": [
            {
                "id": j.id,
                "kind": j.kind,
                "ref_id": j.ref_id,
                "user_id": j.user_id,
                "status": j.status,
                "progress": j.progress,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in rows
        ]
    }


@router.get("/reviews")
async def list_reviews(
    status: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)
):
    q = db.query(Review).order_by(Review.created_at.desc())
    if status:
        q = q.filter(Review.status == status)
    rows = q.limit(min(limit, 200)).all()
    return {
        "reviews": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "task_type": r.task_type,
                "target_title": r.target_title,
                "mode": r.mode,
                "status": r.status,
                "total_cost_usd": r.total_cost_usd,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in rows
        ]
    }
