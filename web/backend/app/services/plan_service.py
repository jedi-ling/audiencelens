"""套餐体系（商业逻辑）：free / pro / team 三档。

设计原则：
  - free 档的限额优先级：后台设置覆盖值（quota_free_*）> 环境变量 settings。
    传了 db 才读得到覆盖值；不传 db 时只读 env（测试可 monkeypatch）；
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

# 可在后台面板覆盖的套餐字段。
# free 档的两项限额走另一条路：后台「设置」里的 quota_free_reviews_per_day /
# quota_free_cost_usd_per_day（见 _free_plan / _overridable_fields_for），
# 不在这里重复放开，避免两套覆盖机制打架。
OVERRIDABLE_PLAN_FIELDS = ("price_usd_month", "reviews_per_day", "cost_usd_per_day")
_FIELD_CASTS = {"price_usd_month": float, "reviews_per_day": int, "cost_usd_per_day": float}

# free 档限额 -> 后台设置项键名。改这里的映射就改了「谁说了算」。
_FREE_LIMIT_SETTINGS = {
    "reviews_per_day": "quota_free_reviews_per_day",
    "cost_usd_per_day": "quota_free_cost_usd_per_day",
}


def _override_key(plan_id: str, field: str) -> str:
    return f"plan_override:{plan_id}:{field}"


def _free_plan(db: Optional[Session] = None) -> dict:
    """free 档限额的唯一事实源：后台设置覆盖值优先，回落 env（settings）。

    实时读取而不是模块加载时定死 —— 运营在面板上把「免费档每日评审次数上限」
    从 5 改成 1，下一次评审就必须按 1 拦。db 为 None 时只读 env
    （保留旧签名，供不持有 session 的调用方与测试 monkeypatch 使用）。
    """
    plan = {
        "name": "Free",
        "price_usd_month": 0,
        "reviews_per_day": settings.quota_free_reviews_per_day,
        "cost_usd_per_day": settings.quota_free_cost_usd_per_day,
    }
    if db is not None:
        from app.services import admin_settings_service

        for field, setting_key in _FREE_LIMIT_SETTINGS.items():
            plan[field] = _FIELD_CASTS[field](
                admin_settings_service.get(db, setting_key, plan[field])
            )
    return plan


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
    """free 档的两项限额由 admin_settings_service（quota_free_*）驱动 ——
    见 _free_plan()，那条路是真的通的，所以这里只再放开 price_usd_month，
    避免两套覆盖机制互相打架。"""
    if pid == "free":
        return ("price_usd_month",)
    return OVERRIDABLE_PLAN_FIELDS


def get_plan(plan_id: Optional[str], db: Optional[Session] = None) -> dict:
    """按 id 取套餐定义；未知/空 id 回落 free（返回副本，带 id 字段）。

    db 传入时会叠加后台面板的覆盖值：pro/team 走 plan_override:*，
    free 的限额走 quota_free_*（见 _free_plan）。
    不传 db 时只读 env/静态定义，向后兼容既有调用方。
    """
    pid = (plan_id or "free").strip().lower()
    if pid not in PLANS:
        pid = "free"
    plan = dict(PLANS[pid])
    if pid == "free":
        plan.update(_free_plan(db))  # free 限额以「后台覆盖值 > env」为准
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
    """给后台面板用：每个套餐额外带 overridden_fields / env_default，供渲染"已覆盖"标记和重置按钮。

    free 的 reviews_per_day / cost_usd_per_day 显示的是**真实生效值**
    （含 quota_free_* 覆盖），但不在 editable_fields 里 —— 面板应把它们渲染成
    只读，并指向「设置」页的对应开关，而不是给一个点了没用的输入框。
    """
    out = []
    for pid in PLANS:
        base = dict(PLANS[pid])
        if pid == "free":
            base.update(_free_plan())  # env 默认值（不含 DB 覆盖）
        base["id"] = pid
        effective = dict(base)
        if pid == "free":
            effective.update(_free_plan(db))  # 生效值（含 quota_free_* 覆盖）
        overridden = []
        for field in _overridable_fields_for(pid):
            row = db.get(PlatformSetting, _override_key(pid, field))
            if row is not None:
                effective[field] = _FIELD_CASTS[field](row.value)
                overridden.append(field)
        effective["overridden_fields"] = overridden
        effective["editable_fields"] = list(_overridable_fields_for(pid))
        effective["env_default"] = {f: base[f] for f in _overridable_fields_for(pid)}
        # 曾经 free 档还带一个 limits_managed_by_settings 字段（想让面板提示
        # 「这两项去『设置』页调」），但 admin 前端从未消费它，全仓唯一引用就是
        # 这里的赋值——算了没人用，删掉。面板要做这个提示时，用
        # editable_fields 里没有 reviews_per_day / cost_usd_per_day 这一事实
        # 就足以推断，不需要后端另发一份映射。
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
