"""套餐体系（商业逻辑）：free / pro / team 三档。

设计原则：
  - free 档的限额直接跟随 settings（环境变量可调，测试可 monkeypatch），
    与旧的"写死 free 配额"行为完全兼容；
  - 未知 plan 一律回落 free —— 宁可少给额度，也不能凭空放行；
  - 这里只描述"套餐长什么样"，扣量/校验逻辑在 quota_service。

接入真实计费（Stripe 等）时，price_usd_month 对应订阅价格，
webhook 回来后改 User.plan 即可，评审链路无需改动。
"""

from typing import Dict, List, Optional

from app.config import settings


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


def get_plan(plan_id: Optional[str]) -> dict:
    """按 id 取套餐定义；未知/空 id 回落 free（返回副本，带 id 字段）。"""
    pid = (plan_id or "free").strip().lower()
    if pid not in PLANS:
        pid = "free"
    plan = dict(PLANS[pid])
    if pid == "free":
        plan.update(_free_plan())  # free 限额永远以 settings 当前值为准
    plan["id"] = pid
    return plan


def list_plans() -> List[dict]:
    """全部套餐（带 id），给 GET /api/plans 定价页用。"""
    return [get_plan(pid) for pid in PLANS]
