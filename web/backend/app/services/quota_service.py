"""配额与计费（埋线：AL_QUOTA_ENABLED=false 时全部放行，但用量照记）。

关键设计：**即使配额关闭，UsageRecord 也照常写入**。
于是你随时可以打开开关开始计费，而历史用量数据早已存在——
不必等"想收费了"才开始埋点，那时就晚了。

接入真实计费（Stripe 等）时：
  1. 在 check_quota 里按 user.plan 查套餐额度（替换下面的 free 常量）
  2. 在 record_usage 后推送计量事件到计费服务
  调用方（api/reviews.py）无需改动。
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import QuotaExceeded
from app.models import UsageRecord


def _day_ago() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=1)


def usage_summary(db: Session, user_id: str) -> dict:
    """近 24h 用量 + 剩余额度（前端设置页/用量页直接用）。"""
    since = _day_ago()
    q = db.query(
        func.count(UsageRecord.id),
        func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
    ).filter(
        UsageRecord.user_id == user_id,
        UsageRecord.kind == "review",
        UsageRecord.created_at >= since,
    )
    count, cost = q.one()

    # BYOK 花的是用户自己的钱，不该算进"我方配额"
    server_cost = (
        db.query(func.coalesce(func.sum(UsageRecord.cost_usd), 0.0))
        .filter(
            UsageRecord.user_id == user_id,
            UsageRecord.key_source == "server",
            UsageRecord.created_at >= since,
        )
        .scalar()
    )

    return {
        "quota_enabled": settings.quota_enabled,
        "window": "24h",
        "reviews_used": int(count or 0),
        "reviews_limit": settings.quota_free_reviews_per_day if settings.quota_enabled else None,
        "cost_usd_total": round(float(cost or 0.0), 4),
        "cost_usd_on_server_key": round(float(server_cost or 0.0), 4),
        "cost_usd_limit": settings.quota_free_cost_usd_per_day if settings.quota_enabled else None,
    }


def check_quota(db: Session, user_id: str, key_source: str = "byok") -> None:
    """评审发起前调用。超限抛 QuotaExceeded（HTTP 402）。

    BYOK 不计入配额——用户自己付钱，没有理由限制他。
    只有走服务端 key（你垫钱）才受配额约束。
    """
    if not settings.quota_enabled or key_source != "server":
        return

    since = _day_ago()
    count = (
        db.query(func.count(UsageRecord.id))
        .filter(
            UsageRecord.user_id == user_id,
            UsageRecord.kind == "review",
            UsageRecord.key_source == "server",
            UsageRecord.created_at >= since,
        )
        .scalar()
        or 0
    )
    if count >= settings.quota_free_reviews_per_day:
        raise QuotaExceeded(
            f"24 小时内免费评审次数已用完（{settings.quota_free_reviews_per_day} 次）。"
            "可填写自己的 API Key（BYOK）以不受限制使用。"
        )

    cost = (
        db.query(func.coalesce(func.sum(UsageRecord.cost_usd), 0.0))
        .filter(
            UsageRecord.user_id == user_id,
            UsageRecord.key_source == "server",
            UsageRecord.created_at >= since,
        )
        .scalar()
        or 0.0
    )
    if float(cost) >= settings.quota_free_cost_usd_per_day:
        raise QuotaExceeded(
            f"24 小时内免费额度已用完（${settings.quota_free_cost_usd_per_day}）。"
            "可填写自己的 API Key（BYOK）以不受限制使用。"
        )


def record_usage(
    db: Session,
    user_id: str,
    *,
    review_id: Optional[str] = None,
    kind: str = "review",
    persona_count: int = 0,
    cost_usd: float = 0.0,
    key_source: str = "byok",
) -> UsageRecord:
    """评审结束后调用。无论配额是否开启都记录——这是日后计费的事实源。"""
    row = UsageRecord(
        user_id=user_id,
        review_id=review_id,
        kind=kind,
        persona_count=persona_count,
        cost_usd=float(cost_usd or 0.0),
        key_source=key_source,
    )
    db.add(row)
    db.commit()
    # 计费接入点：在此推送计量事件到 Stripe/自建计费
    # billing_client.report_usage(user_id, cost_usd)  # noqa: ERA001
    return row
