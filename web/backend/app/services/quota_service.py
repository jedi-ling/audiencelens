"""配额与计费（埋线：AL_QUOTA_ENABLED=false 时全部放行，但用量照记）。

关键设计：**即使配额关闭，UsageRecord 也照常写入**。
于是你随时可以打开开关开始计费，而历史用量数据早已存在——
不必等"想收费了"才开始埋点，那时就晚了。

额度来源：一律走 plan_service.get_plan(plan, db)，**必须传 db** ——
free 档的日限额/日成本上限由后台面板的 quota_free_* 设置项驱动，
不传 db 就只读得到 env 默认值，运营在面板上的止血操作会静默失效。

接入真实计费（Stripe 等）时：
  1. 在 record_usage 后推送计量事件到计费服务
  2. webhook 回来后改 User.plan 即可，评审链路无需改动
  调用方（api/reviews.py）无需改动。
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import QuotaExceeded
from app.models import UsageRecord
from app.services import admin_settings_service, plan_service


def _day_ago() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=1)


def _quota_enabled(db: Session) -> bool:
    return admin_settings_service.get(db, "quota_enabled", settings.quota_enabled)


def usage_summary(db: Session, user_id: str, plan: str = "free") -> dict:
    """近 24h 用量 + 剩余额度（前端设置页/用量页直接用）。

    plan 参数向后兼容：不传等价于旧行为（free 档限额）。
    """
    quota_enabled = _quota_enabled(db)
    plan_info = plan_service.get_plan(plan, db)
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

    from app.services import cdk_service

    mode = admin_settings_service.get(db, "quota_mode", settings.quota_mode)
    # credits 模式没有"每日限额"概念——额度就是 CDK 余额本身
    plan_limits_apply = quota_enabled and mode != "credits"

    return {
        "quota_enabled": quota_enabled,
        "quota_mode": mode,
        "window": "24h",
        "plan": plan_info["id"],
        "plan_name": plan_info["name"],
        "reviews_used": int(count or 0),
        "reviews_limit": plan_info["reviews_per_day"] if plan_limits_apply else None,
        "cost_usd_total": round(float(cost or 0.0), 4),
        "cost_usd_on_server_key": round(float(server_cost or 0.0), 4),
        "cost_usd_limit": plan_info["cost_usd_per_day"] if plan_limits_apply else None,
        # CDK 次数余额：credits 模式下这就是全部额度（每次评审 -1，用完即止）；
        # plan 模式下是日限用完后的加量
        "bonus_credits": cdk_service.credit_balance(db, user_id),
    }


def check_quota(db: Session, user_id: str, key_source: str = "byok", plan: str = "free") -> None:
    """评审发起前调用。超限抛 QuotaExceeded（HTTP 402）。

    BYOK 不计入配额——用户自己付钱，没有理由限制他。
    只有走服务端 key（你垫钱）才受配额约束。

    plan 参数向后兼容：不传等价于旧行为（按 free 档限额校验）；
    未知 plan 由 plan_service 回落 free。quota_enabled 支持后台面板实时覆盖。

    两种配额模式（quota_mode，后台面板可实时切换）：
      plan    套餐日限额；CDK 次数在日限用完后垫（有余额消耗 1 次放行）。
              成本日上限是硬闸——保护运营者钱包，次数不能绕过。
      credits 纯次数制："一个码 10 次，用完就没了"。每次服务端 key 评审
              直接消耗 1 次余额，余额 0 → 402 引导兑换 CDK。无每日刷新、
              无套餐日限——总成本由发码量控制。

              ⚠️ 单次成本不是硬封顶。budget.yaml 的 max_cost_per_run_usd
              只能拦住人格环节**之后**的额外付费调用（交叉质询）——人格是
              并发发出去的，跑到一半刹不住车，所以单次评审的实际花费仍可能
              超过那个数字，超了会记进 report["budget"] 并打告警日志。
              这里写清楚是因为它此前被描述成"封顶"，而当时那个配置项
              根本没有任何代码读取，等于一句完全的空话。

    消耗发生在校验通过的瞬间（原子扣减，见 cdk_service.try_consume_credit）。
    评审随后失败的，由 refund_review_credit 退还——次数是用户花钱买的，
    不能被一次模型报错吞掉。
    """
    if not _quota_enabled(db) or key_source != "server":
        return

    from app.services import cdk_service

    mode = admin_settings_service.get(db, "quota_mode", settings.quota_mode)
    if mode == "credits":
        # 查余额和扣减是同一条原子语句——并发请求不可能把余额扣成负数
        if not cdk_service.try_consume_credit(db, user_id):
            raise QuotaExceeded(
                "评审次数已用完。请兑换 CDK 获得次数，"
                "或填写自己的 API Key（BYOK）以不受限制使用。"
            )
        return

    plan_info = plan_service.get_plan(plan, db)
    reviews_limit = plan_info["reviews_per_day"]
    cost_limit = plan_info["cost_usd_per_day"]

    since = _day_ago()

    # 成本硬闸先行：无论有没有次数余额，钱包上限碰到就停
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
    if float(cost) >= cost_limit:
        raise QuotaExceeded(
            f"24 小时内成本额度已用完（{plan_info['name']} 套餐限 ${cost_limit}/天）。"
            "可升级套餐，或填写自己的 API Key（BYOK）以不受限制使用。"
        )

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
    if count >= reviews_limit:
        if cdk_service.try_consume_credit(db, user_id):
            return
        raise QuotaExceeded(
            f"24 小时内评审次数已用完（{plan_info['name']} 套餐限 {reviews_limit} 次）。"
            "可兑换 CDK 获得加量次数、升级套餐，或填写自己的 API Key（BYOK）以不受限制使用。"
        )


def refund_review_credit(
    db: Session, user_id: str, review_id: str, key_source: str = "server"
) -> bool:
    """评审失败后，把入口扣掉的那 1 次 CDK 次数退回去。返回"这次真的退了吗"。

    以前没有这条路径：credits 模式在 check_quota 里原子扣 1 次，之后评审
    因为模型报错、进程重启收尸等原因失败，次数就凭空消失了——用户花钱买的
    次数，一次失败就没了，且账面上完全看不出来。

    只在 (credits 模式 + 服务端垫付 key) 这一种组合下退，因为那是唯一
    "入口一定扣了 1 次"的情形（见 check_quota）：
      · BYOK 从来不扣次数，退了就是凭空发次数；
      · plan 模式只有在日限用完时才垫 1 次，而扣减流水上没有 review_id
        （check_quota 跑在评审落库之前，那时还没有 id 可写），事后无法判断
        这一条评审到底垫没垫。宁可不退，也不能猜着退——猜错就是无中生有。
        要覆盖 plan 模式得把 review_id 一路传到 check_quota，涉及
        api/__init__.py 与 api/platform.py 两个调用点，不属于本次改动范围。

    幂等由 cdk_service.refund_credit 以 review_id 为键保证；退还本身写进
    credit_ledger（reason=review_refund），账面上可核对，不是隐形补偿。
    """
    if key_source != "server" or not _quota_enabled(db):
        return False
    if admin_settings_service.get(db, "quota_mode", settings.quota_mode) != "credits":
        return False

    from app.services import cdk_service

    return cdk_service.refund_credit(db, user_id, review_id)


def record_usage(
    db: Session,
    user_id: str,
    *,
    review_id: Optional[str] = None,
    kind: str = "review",
    persona_count: int = 0,
    cost_usd: float = 0.0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    key_source: str = "byok",
) -> UsageRecord:
    """评审结束后调用。无论配额是否开启都记录——这是日后计费/token 报表的事实源。"""
    row = UsageRecord(
        user_id=user_id,
        review_id=review_id,
        kind=kind,
        persona_count=persona_count,
        cost_usd=float(cost_usd or 0.0),
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        key_source=key_source,
    )
    db.add(row)
    db.commit()
    # 计费接入点：在此推送计量事件到 Stripe/自建计费
    # billing_client.report_usage(user_id, cost_usd)  # noqa: ERA001
    return row
