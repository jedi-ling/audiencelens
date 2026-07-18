"""后台管理路由：运行时配置、平台级 API Key、系统概览、判断复利、套餐、任务与评审巡检、审计日志。

全部挂在 Depends(require_admin) 之后——未设置 AL_ADMIN_TOKEN 时整体 503，
配置后需要 X-Admin-Token 请求头匹配才能访问。见 docs/MAINTENANCE.md 的
「后台管理面板」一节。
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest, NotFound
from app.db import get_db
from app.deps import require_admin
from app.models import Job, Judgment, Review, UsageRecord, User
from app.services import (
    admin_settings_service,
    audit_log_service,
    cdk_service,
    key_service,
    ledger_service,
    plan_service,
)

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


@router.get("/timeseries")
async def timeseries(days: int = 14, db: Session = Depends(get_db)):
    """近 N 天每日评审量/状态分布/成本——给可视化面板画趋势图用。

    分桶在 Python 里做而不是用 SQL 的 strftime——后者是 SQLite 方言，
    这个项目的既定迁移路径是"改 AL_DATABASE_URL 换 Postgres"，不该在这里锁死 SQLite。
    """
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    def bucket_key(dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return d.date().isoformat()

    review_by_day: dict = {}
    for created_at, status in db.query(Review.created_at, Review.status).filter(
        Review.created_at >= since
    ).all():
        k = bucket_key(created_at)
        if not k:
            continue
        bucket = review_by_day.setdefault(k, {"total": 0})
        bucket["total"] += 1
        bucket[status] = bucket.get(status, 0) + 1

    cost_by_day: dict = {}
    for created_at, cost in db.query(UsageRecord.created_at, UsageRecord.cost_usd).filter(
        UsageRecord.created_at >= since
    ).all():
        k = bucket_key(created_at)
        if not k:
            continue
        cost_by_day[k] = cost_by_day.get(k, 0.0) + float(cost or 0.0)

    series = []
    for i in range(days + 1):
        day = (since + timedelta(days=i)).date().isoformat()
        bucket = review_by_day.get(day, {"total": 0})
        series.append(
            {
                "date": day,
                "reviews_total": bucket.get("total", 0),
                "reviews_completed": bucket.get("completed", 0),
                "reviews_failed": bucket.get("failed", 0),
                "cost_usd": round(cost_by_day.get(day, 0.0), 4),
            }
        )
    return {"days": days, "series": series}


# ============================== 判断复利（跨用户聚合） ==============================

@router.get("/ledger")
async def ledger_overview(db: Session = Depends(get_db)):
    """判断复利闭环的全局视角——产品的护城河指标，此前只在单用户产品前端可见。"""
    return {
        "hit_rate": ledger_service.hit_rate(db, None),
        "persona_leaderboard": ledger_service.persona_leaderboard(db, None, limit=20),
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
    result = admin_settings_service.set_override(db, body.key, body.value)
    audit_log_service.record(db, "setting.update", body.key, {"value": body.value})
    return result


@router.delete("/settings/{key}")
async def reset_setting(key: str, db: Session = Depends(get_db)):
    """清除覆盖值，回落到环境变量默认值。"""
    cleared = admin_settings_service.clear_override(db, key)
    if cleared:
        audit_log_service.record(db, "setting.reset", key)
    return {"key": key, "cleared": cleared}


# ============================== 平台级 API Key ==============================

class ServerKeyUpdate(BaseModel):
    api_key: str
    provider: str = "anthropic"  # "anthropic" | "openai_compatible"
    model: Optional[str] = None  # openai_compatible 档必填
    api_base: Optional[str] = None


@router.get("/server-key")
async def server_key_status(provider: str = "anthropic", db: Session = Depends(get_db)):
    status = key_service.get_platform_key_status(db, provider)
    return {"configured": status is not None, "key": status}


@router.put("/server-key")
async def set_server_key(body: ServerKeyUpdate, db: Session = Depends(get_db)):
    try:
        row = key_service.save_platform_key(
            db, body.api_key, body.provider, model=body.model, api_base=body.api_base
        )
    except ValueError as exc:
        raise BadRequest(str(exc))
    audit_log_service.record(db, "server_key.set", body.provider, {"masked": row.key_masked, "model": row.model})
    return {"provider": row.provider, "model": row.model, "api_base": row.api_base, "masked": row.key_masked}


@router.post("/server-key/test")
async def test_server_key(provider: str = "anthropic", db: Session = Depends(get_db)):
    """真实测一次已保存的平台 key——走评审真正会用的那条链路（llm_client）。"""
    status = key_service.get_platform_key_status(db, provider)
    if not status:
        raise BadRequest("尚未配置该服务商的平台 key")
    row = key_service.get_user_key_row(db, key_service.PLATFORM_KEY_OWNER, provider)
    from app.core.security import decrypt_secret

    try:
        api_key = decrypt_secret(row.key_ciphertext, settings.encryption_key)
    except ValueError:
        raise BadRequest("已保存的 key 解密失败，请重新填写")

    import sys

    _SRC = os.path.join(settings.repo_root, "src")
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    from runner.llm_client import test_connection

    model = row.model or settings.intent_model
    return test_connection(model=model, api_key=api_key, provider=provider, api_base=row.api_base)


@router.delete("/server-key")
async def delete_server_key(provider: str = "anthropic", db: Session = Depends(get_db)):
    n = key_service.delete_platform_key(db, provider)
    if n:
        audit_log_service.record(db, "server_key.delete", provider)
    return {"deleted": n}


# ============================== CDK 兑换码 ==============================

class CdkGenerateRequest(BaseModel):
    count: int = 10            # 本批生成多少个码
    credits: int = 5           # 每次兑换发放的评审次数
    max_uses: int = 1          # 每个码可被多少个不同用户兑换（活动通用码可调大）
    expires_in_days: Optional[int] = None  # 不传 = 永不过期
    note: Optional[str] = None


@router.post("/cdk/generate")
async def generate_cdk(body: CdkGenerateRequest, db: Session = Depends(get_db)):
    """批量生成兑换码。码明文只在生成响应里完整给一次列表，之后走列表页也能看
    ——CDK 不是密码级别的秘密（本来就是要分发出去的），存明文便于运营查询。"""
    try:
        rows = cdk_service.generate_codes(
            db,
            count=body.count,
            credits=body.credits,
            max_uses=body.max_uses,
            expires_in_days=body.expires_in_days,
            note=body.note,
        )
    except ValueError as exc:
        raise BadRequest(str(exc))
    audit_log_service.record(
        db,
        "cdk.generate",
        rows[0].batch_id,
        {"count": body.count, "credits": body.credits, "max_uses": body.max_uses,
         "expires_in_days": body.expires_in_days, "note": body.note},
    )
    return {
        "batch_id": rows[0].batch_id,
        "codes": [r.code for r in rows],
        "count": len(rows),
        "credits": body.credits,
        "max_uses": body.max_uses,
    }


@router.get("/cdk")
async def list_cdk(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return cdk_service.list_codes(db, status=status, limit=min(limit, 200), offset=offset)


@router.put("/cdk/{code_id}/disable")
async def disable_cdk(code_id: str, db: Session = Depends(get_db)):
    if not cdk_service.disable_code(db, code_id):
        raise NotFound("兑换码不存在")
    audit_log_service.record(db, "cdk.disable", code_id)
    return {"id": code_id, "disabled": True}


# ============================== 套餐（可编辑覆盖） ==============================

@router.get("/plans")
async def list_plans(db: Session = Depends(get_db)):
    return {"plans": plan_service.list_plans_admin(db)}


class PlanOverrideUpdate(BaseModel):
    field: str
    value: Any


@router.put("/plans/{plan_id}")
async def update_plan(plan_id: str, body: PlanOverrideUpdate, db: Session = Depends(get_db)):
    try:
        plan = plan_service.set_plan_override(db, plan_id, body.field, body.value)
    except ValueError as exc:
        raise BadRequest(str(exc))
    audit_log_service.record(db, "plan.override", f"{plan_id}.{body.field}", {"value": body.value})
    return plan


@router.delete("/plans/{plan_id}/{field}")
async def reset_plan_field(plan_id: str, field: str, db: Session = Depends(get_db)):
    try:
        plan = plan_service.clear_plan_override(db, plan_id, field)
    except ValueError as exc:
        raise BadRequest(str(exc))
    audit_log_service.record(db, "plan.reset", f"{plan_id}.{field}")
    return plan


# ============================== 用户管理 ==============================

class UserUpdate(BaseModel):
    plan: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/users")
async def list_users(
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """注册用户列表，附带各自的评审数与累计成本（近 30 天 + 全部）。"""
    query = db.query(User)
    if q:
        query = query.filter(User.email.contains(q.strip().lower()))
    total = query.count()
    rows = query.order_by(User.created_at.desc()).offset(max(offset, 0)).limit(min(limit, 200)).all()

    user_ids = [u.id for u in rows]
    review_counts: dict = {}
    cost_totals: dict = {}
    if user_ids:
        review_counts = dict(
            db.query(Review.user_id, func.count(Review.id))
            .filter(Review.user_id.in_(user_ids))
            .group_by(Review.user_id)
            .all()
        )
        cost_totals = dict(
            db.query(UsageRecord.user_id, func.coalesce(func.sum(UsageRecord.cost_usd), 0.0))
            .filter(UsageRecord.user_id.in_(user_ids))
            .group_by(UsageRecord.user_id)
            .all()
        )

    return {
        "total": total,
        "offset": offset,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "plan": u.plan,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "reviews_total": int(review_counts.get(u.id, 0)),
                "cost_usd_total": round(float(cost_totals.get(u.id, 0.0)), 4),
            }
            for u in rows
        ],
    }


@router.put("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, db: Session = Depends(get_db)):
    """改套餐 / 停用启用。立即生效——下一次该用户请求时 current_identity 就会读到新状态。"""
    user = db.get(User, user_id)
    if not user:
        raise NotFound("用户不存在")

    changes: dict = {}
    if body.plan is not None:
        pid = body.plan.strip().lower()
        if pid not in plan_service.PLANS:
            raise BadRequest(f"未知套餐: {body.plan}")
        changes["plan"] = {"from": user.plan, "to": pid}
        user.plan = pid
    if body.is_active is not None:
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active

    if not changes:
        raise BadRequest("没有要修改的字段（plan / is_active）")

    db.commit()
    audit_log_service.record(db, "user.update", user.email, changes)
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.plan,
        "is_active": user.is_active,
    }


# ============================== 统计分析（可视化数据源） ==============================

@router.get("/stats/task-types")
async def stats_task_types(db: Session = Depends(get_db)):
    """按任务类型聚合：总量 / 完成 / 失败 / 成本——后台条形图的数据源。"""
    rows = (
        db.query(
            Review.task_type,
            func.count(Review.id),
            func.sum(case((Review.status == "completed", 1), else_=0)),
            func.sum(case((Review.status == "failed", 1), else_=0)),
            func.coalesce(func.sum(Review.total_cost_usd), 0.0),
        )
        .group_by(Review.task_type)
        .order_by(func.count(Review.id).desc())
        .all()
    )
    return {
        "task_types": [
            {
                "task_type": t,
                "total": int(total),
                "completed": int(completed or 0),
                "failed": int(failed or 0),
                "cost_usd": round(float(cost or 0.0), 4),
            }
            for t, total, completed, failed, cost in rows
        ]
    }


@router.get("/stats/persona-packs")
async def stats_persona_packs(db: Session = Depends(get_db)):
    """按人格包聚合评审量——看哪组人格被用得最多。"""
    rows = (
        db.query(Review.persona_pack, func.count(Review.id))
        .filter(Review.persona_pack.isnot(None))
        .group_by(Review.persona_pack)
        .order_by(func.count(Review.id).desc())
        .all()
    )
    return {"persona_packs": [{"persona_pack": p, "total": int(n)} for p, n in rows]}


@router.get("/stats/costs")
async def stats_costs(days: int = 30, db: Session = Depends(get_db)):
    """成本构成：BYOK vs 平台垫付的占比 + 消耗最高的用户——运营最关心的两个问题。"""
    days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    by_source = dict(
        db.query(UsageRecord.key_source, func.coalesce(func.sum(UsageRecord.cost_usd), 0.0))
        .filter(UsageRecord.created_at >= since)
        .group_by(UsageRecord.key_source)
        .all()
    )

    top_users = (
        db.query(
            UsageRecord.user_id,
            func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
            func.count(UsageRecord.id),
        )
        .filter(UsageRecord.created_at >= since)
        .group_by(UsageRecord.user_id)
        .order_by(func.coalesce(func.sum(UsageRecord.cost_usd), 0.0).desc())
        .limit(10)
        .all()
    )
    emails = dict(
        db.query(User.id, User.email).filter(User.id.in_([u for u, _, _ in top_users])).all()
    ) if top_users else {}

    return {
        "days": days,
        "cost_by_source": {k: round(float(v), 4) for k, v in by_source.items()},
        "top_users": [
            {
                "user_id": uid,
                "email": emails.get(uid),  # 匿名/已删除用户为 None
                "cost_usd": round(float(cost), 4),
                "records": int(n),
            }
            for uid, cost, n in top_users
        ],
    }


# ============================== 审计日志 ==============================

@router.get("/audit-log")
async def audit_log(limit: int = 100, db: Session = Depends(get_db)):
    return {"entries": audit_log_service.list_recent(db, limit)}


# ============================== 任务 / 评审巡检 ==============================

def _job_row(j: Job) -> dict:
    return {
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


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    if user_id:
        q = q.filter(Job.user_id == user_id)
    if created_after:
        q = q.filter(Job.created_at >= created_after)
    if created_before:
        q = q.filter(Job.created_at <= created_before)
    total = q.count()
    rows = q.order_by(Job.created_at.desc()).offset(max(offset, 0)).limit(min(limit, 200)).all()
    return {"total": total, "offset": offset, "jobs": [_job_row(j) for j in rows]}


@router.get("/jobs/{job_id}")
async def job_detail(job_id: str, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j:
        raise NotFound("任务不存在")
    return {
        **_job_row(j),
        "payload": j.payload,
        "started_at": j.started_at.isoformat() if j.started_at else None,
    }


def _review_row(r: Review) -> dict:
    return {
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


@router.get("/reviews")
async def list_reviews(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Review)
    if status:
        q = q.filter(Review.status == status)
    if user_id:
        q = q.filter(Review.user_id == user_id)
    if created_after:
        q = q.filter(Review.created_at >= created_after)
    if created_before:
        q = q.filter(Review.created_at <= created_before)
    total = q.count()
    rows = q.order_by(Review.created_at.desc()).offset(max(offset, 0)).limit(min(limit, 200)).all()
    return {"total": total, "offset": offset, "reviews": [_review_row(r) for r in rows]}


@router.get("/reviews/{review_id}")
async def review_detail(review_id: str, db: Session = Depends(get_db)):
    r = db.get(Review, review_id)
    if not r:
        raise NotFound("评审不存在")
    return {
        **_review_row(r),
        "persona_pack": r.persona_pack,
        "selected_personas": r.selected_personas,
        "report_json": r.report_json,
        "calibration": r.calibration,
    }


@router.delete("/reviews/{review_id}")
async def delete_review(review_id: str, db: Session = Depends(get_db)):
    """删除评审（连带 persona_outputs / judgments / feedback，模型层已配 cascade）。

    注意：UsageRecord 不删——它是计费事实源，评审删了账也要在。
    """
    r = db.get(Review, review_id)
    if not r:
        raise NotFound("评审不存在")
    title = r.target_title
    db.delete(r)
    db.commit()
    audit_log_service.record(db, "review.delete", review_id, {"target_title": title})
    return {"deleted": review_id}
