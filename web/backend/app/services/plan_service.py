"""套餐体系（商业逻辑）：free / pro / team 三档。

设计原则：
  - free 档的限额直接跟随 settings（环境变量可调，测试可 monkeypatch），
    与旧的"写死 free 配额"行为完全兼容；
  - 未知 plan 一律回落 free —— 宁可少给额度，也不能凭空放行；
  - 这里只描述"套餐长什么样"，扣量/校验逻辑在 quota_service。

接入真实计费（Stripe 等）时，price_usd_month 对应订阅价格，
webhook 回来后改 User.plan 即可，评审链路无需改动。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import PlatformSetting

# 可在后台面板覆盖的套餐字段（free 档限额已经由 settings/quota_enabled 驱动，
# 不纳入这里——避免两套覆盖机制打架）
OVERRIDABLE_PLAN_FIELDS = ("price_usd_month", "reviews_per_day", "cost_usd_per_day")
_FIELD_CASTS = {"price_usd_month": float, "reviews_per_day": int, "cost_usd_per_day": float}


def _override_key(plan_id: str, field: str) -> str:
    return f"plan_override:{plan_id}:{field}"


def _free_plan() -> dict:
    """free 档实时读 settings —— 保证运行时改配置/测试 monkeypatch 立即生效。"""
    return {
        "name": "Free",
        "price_usd_month": 0,
        "reviews_per_day": settings.quota_free_reviews_per_day,
        "cost_usd_per_day": settings.quota_free_cost_usd_per_day,
    }


PLANS: Dict[str, dict] = {
    "free": _free_plan(),
    "pro": {
        "name": "Pro",
        "price_usd_month": 19,
        "reviews_per_day": 100,
        "cost_usd_per_day": 20.0,
    },
    "team": {
        "name": "Team",
        "price_usd_month": 49,
        "reviews_per_day": 500,
        "cost_usd_per_day": 100.0,
    },
}


def _overridable_fields_for(pid: str) -> tuple:
    """free 档的额度已经由 admin_settings_service（quota_free_*）驱动，
    这里只再放开 price_usd_month，避免两套覆盖机制互相打架。"""
    if pid == "free":
        return ("price_usd_month",)
    return OVERRIDABLE_PLAN_FIELDS


def get_plan(plan_id: Optional[str], db: Optional[Session] = None) -> dict:
    """按 id 取套餐定义；未知/空 id 回落 free（返回副本，带 id 字段）。

    db 传入时会叠加后台面板设置的套餐覆盖值（PlatformSetting）；
    不传 db 时保持旧行为（仅 env/静态定义），向后兼容既有调用方。
    """
    pid = (plan_id or "free").strip().lower()
    if pid not in PLANS:
        pid = "free"
    plan = dict(PLANS[pid])
    if pid == "free":
        plan.update(_free_plan())  # free 限额永远以 settings 当前值为准
    plan["id"] = pid
    if db is not None:
        for field in _overridable_fields_for(pid):
            row = db.get(PlatformSetting, _override_key(pid, field))
            if row is not None:
                plan[field] = _FIELD_CASTS[field](row.value)
    return plan


def list_plans(db: Optional[Session] = None) -> List[dict]:
    """全部套餐（带 id），给 GET /api/plans 定价页用。"""
    return [get_plan(pid, db) for pid in PLANS]


def list_plans_admin(db: Session) -> List[dict]:
    """给后台面板用：每个套餐额外带 overridden_fields / env_default，供渲染"已覆盖"标记和重置按钮。"""
    out = []
    for pid in PLANS:
        base = dict(PLANS[pid])
        if pid == "free":
            base.update(_free_plan())
        base["id"] = pid
        effective = dict(base)
        overridden = []
        for field in _overridable_fields_for(pid):
            row = db.get(PlatformSetting, _override_key(pid, field))
            if row is not None:
                effective[field] = _FIELD_CASTS[field](row.value)
                overridden.append(field)
        effective["overridden_fields"] = overridden
        effective["editable_fields"] = list(_overridable_fields_for(pid))
        effective["env_default"] = {f: base[f] for f in _overridable_fields_for(pid)}
        out.append(effective)
    return out


def set_plan_override(db: Session, plan_id: str, field: str, value: Any) -> dict:
    """管理员在后台面板设置套餐字段覆盖值，立即生效（下一次 get_plan(db=...) 调用就会读到）。"""
    pid = (plan_id or "").strip().lower()
    if pid not in PLANS:
        raise ValueError(f"未知套餐: {plan_id}")
    if field not in _overridable_fields_for(pid):
        raise ValueError(f"套餐 {pid} 的 {field} 字段不可在此覆盖")
    cast = _FIELD_CASTS[field]
    try:
        casted = cast(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} 类型应为 {cast.__name__}")
    if casted < 0:
        raise ValueError(f"{field} 不能为负数")

    key = _override_key(pid, field)
    row = db.get(PlatformSetting, key)
    if row is None:
        row = PlatformSetting(key=key, value=str(casted))
        db.add(row)
    else:
        row.value = str(casted)
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return get_plan(pid, db)


def clear_plan_override(db: Session, plan_id: str, field: str) -> dict:
    """清除套餐字段覆盖值，回落到代码里的静态定义。"""
    pid = (plan_id or "").strip().lower()
    if pid not in PLANS:
        raise ValueError(f"未知套餐: {plan_id}")
    row = db.get(PlatformSetting, _override_key(pid, field))
    if row is not None:
        db.delete(row)
        db.commit()
    return get_plan(pid, db)
