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

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import QuotaExceeded
from app.models import UsageRecord, User
from app.services import admin_settings_service, plan_service

# ---------------------------------------------------------------------------
# 日配额的"预留"（reservation）
#
# 为什么需要它：日次数闸原本读的是 UsageRecord，而 UsageRecord 只在评审**完成后**
# 才写入（review_service 的成功分支）。检查与写入之间隔着整整一次评审，中间没有
# 任何占位——同一用户并发发起 N 个请求时全部读到 count=0，于是全部放行。
# 免费档 5 次/天配合 20 次/小时的限流，实测能把日限刷到 4 倍，烧的是平台垫付的钱。
#
# 修法是"发起即占位、完成即结算"：check_quota 在放行的同一条语句里插一条
# kind=review_pending 的占位记录，评审完成时 record_usage 把这条占位**原地改写**
# 成真实用量（不是再插一条，否则一次评审计两次）。
#
# 占位绝不能变成"永久占坑"（那正是本仓库另一个缺陷的形状：扣了不退）。三道保险：
#   1. 评审失败 → review_service 调 release_review_slot 立刻释放；
#   2. 进程重启被收尸 → db._reap_orphans 调 release_review_slot 释放（见那边）；
#   3. 上面两条都没跑到（进程被 kill -9 之类）→ 超过 RESERVATION_TTL_SECONDS 的
#      占位不再计入任何配额判断，并在下次启动收尸时被删掉。
# 也就是说最坏情况下一个占位只挡人 1 小时，而不是挡满 24 小时的统计窗口。
# ---------------------------------------------------------------------------

RESERVATION_KIND = "review_pending"

# 一条占位最多能挡多久。取值依据：单次评审（full 档、并发度低）实测在分钟量级，
# 1 小时留足冗余；同时它也是"漏释放"的最大代价上限，不能取得太长。
RESERVATION_TTL_SECONDS = 3600


def _day_ago() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=1)


def _reservation_cutoff() -> datetime:
    """早于这个时间点的占位一律当作已作废（不计数、可清理）。"""
    return datetime.now(timezone.utc) - timedelta(seconds=RESERVATION_TTL_SECONDS)


def _naive_utc(moment: datetime) -> datetime:
    """裸 SQL 绑定参数用的 UTC naive 时间。

    ORM 查询里 SQLAlchemy 会按列类型把 aware datetime 规范化，裸 text() 不会：
    sqlite3 的默认适配器会把 aware datetime 写成 "...+00:00"，和库里已存的
    "YYYY-MM-DD HH:MM:SS.ffffff" 做字符串比较必然错位——时间闸会静默失灵。
    """
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def _counts_toward_daily_reviews():
    """哪些行占用"今天已经跑了几次评审"这个名额：已结算的 + 仍然有效的占位。"""
    return or_(
        UsageRecord.kind == "review",
        and_(
            UsageRecord.kind == RESERVATION_KIND,
            UsageRecord.created_at >= _reservation_cutoff(),
        ),
    )


def _quota_enabled(db: Session) -> bool:
    return admin_settings_service.get(db, "quota_enabled", settings.quota_enabled)


def tokens_used(db: Session, user_id: str) -> int:
    """该用户在本实例上**累计**烧掉的平台 token（输入 + 输出）。

    三个刻意的选择：
      · 不设时间窗 —— 这是终身试用额度，跨天不重置。次数闸和成本闸都是 24h
        滚动窗口，拦不住"每天用满、连用一个月"这种长期消耗。
      · 只算 key_source="server" —— BYOK 花的是用户自己的钱，计进来等于
        惩罚自带 key 的用户，而他们恰恰是不花我方一分钱的那批。
      · 输入输出相加 —— 上限本身是个粗粒度的钱包保护，按单价加权反而会让
        运营者难以估算"3000000 到底等于多少钱"。要精细控制成本用成本闸。

    评审删除不影响这里：usage_records 与 reviews 是弱引用（ondelete=SET NULL），
    用户删掉评审后账仍在。否则"删掉历史就能重置额度"会是一个免费的刷量后门。
    """
    total = (
        db.query(
            func.coalesce(func.sum(UsageRecord.input_tokens), 0)
            + func.coalesce(func.sum(UsageRecord.output_tokens), 0)
        )
        .filter(
            UsageRecord.user_id == user_id,
            UsageRecord.key_source == "server",
        )
        .scalar()
    )
    return int(total or 0)


def effective_reviews_limit(db: Session, user_id: str, plan_limit: int) -> int:
    """把「未验证邮箱」这条软拦叠加到套餐日次数上限之上。

    返回 min(套餐上限, 未验证上限)——**只会压低，永远不会抬高**。这条不是
    风格问题：如果写成直接返回未验证上限，那么当运营把免费档调到 1 次以下时，
    未验证账号反而比已验证账号额度更高，闸门会变成漏斗。

    三种情况原样返回 plan_limit（即本机制不介入）：
      · 配置为负数 —— 显式关闭；
      · user_id 是共享匿名桶 —— 匿名访客根本没有邮箱可验证，压这里等于把
        全站所有未登录访客共用的试用额度压成每天 1 次，是全局故障不是限流；
      · 库里查不到这个 user 或已验证 —— 没有可拦的对象。

    调用点必须同时覆盖 check_quota（真闸门）和 usage_summary（前端显示的数字）。
    只改其中一个的后果在本文件里已经有前车之鉴：用量页显示 3/5、闸门按 1/1 拒绝，
    用户看到的是一个说谎的数字。
    """
    cap = settings.quota_unverified_reviews_per_day
    if cap < 0:
        return plan_limit
    if user_id == settings.anonymous_user_id:
        return plan_limit
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.email_verified_at is not None:
        return plan_limit
    return min(plan_limit, cap)


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
        # 与 check_quota 用同一个谓词：正在跑的评审（占位）也算"已经用掉一次"。
        # 否则用量页会显示 3/5 而配额闸按 5/5 拒绝，用户看到的是一个说谎的数字。
        _counts_toward_daily_reviews(),
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
        "reviews_limit": (
            effective_reviews_limit(db, user_id, plan_info["reviews_per_day"])
            if plan_limits_apply
            else None
        ),
        # 前端据此决定要不要显示「验证邮箱解锁完整额度」提示条。放在这里而不是
        # 让前端自己拿用户资料去判断：额度是不是真被压了，只有这一处算得准
        # （还要看 quota_enabled / quota_mode / 是否匿名），前端重算必然走偏。
        "reviews_limit_capped_unverified": (
            plan_limits_apply
            and effective_reviews_limit(db, user_id, plan_info["reviews_per_day"])
            < plan_info["reviews_per_day"]
        ),
        "cost_usd_total": round(float(cost or 0.0), 4),
        "cost_usd_on_server_key": round(float(server_cost or 0.0), 4),
        "cost_usd_limit": plan_info["cost_usd_per_day"] if plan_limits_apply else None,
        # CDK 次数余额：credits 模式下这就是全部额度（每次评审 -1，用完即止）；
        # plan 模式下是日限用完后的加量
        "bonus_credits": cdk_service.credit_balance(db, user_id),
        # 终身 token 额度。与上面几项不同，它不随 quota_mode 变化，也不按 24h 滚动，
        # 所以 quota_enabled=false 时同样如实回报"已用了多少"（只是不拦）——
        # 让用户和运营都能看见真实消耗，而不是等撞上限才第一次知道有这回事。
        "tokens_used": tokens_used(db, user_id),
        "tokens_limit": settings.quota_tokens_total or None,
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

    plan 模式的日次数闸同样在放行的瞬间就**占位**（_reserve_review_slot），
    不再等评审跑完才写 UsageRecord —— 否则检查与写入之间的几分钟里，
    并发请求全部读到旧的计数，日限形同虚设（详见文件头的说明）。
    占位的释放路径：release_review_slot（失败/收尸）+ TTL 兜底。

    ⚠️ 日**成本**闸没有对应的预留，也做不出来：一次评审要花多少钱，
    发起时无从得知（取决于人格数、材料长度、上游返回多少 token）。
    它仍然是"按此刻已知的花销判断"，并发时最多同时放行到次数上限那么多个请求。
    次数闸收紧之后，成本的并发溢出被压在 (日次数上限 × 单次成本) 这个量级，
    不再是"限流上限 × 单次成本"。这是取舍，写在这里免得下一个人以为它是硬闸。
    """
    if not _quota_enabled(db) or key_source != "server":
        return

    from app.services import cdk_service

    # 终身 token 闸必须在 mode 分支**之前**：credits 分支自己 return，放在它后面
    # 等于 credits 模式完全绕过这道闸——而 credits 恰恰是推荐给生产的模式。
    # 这类"新加的检查被放在早退分支之后"的漏，在这个项目里出现过不止一次。
    total_cap = settings.quota_tokens_total
    if total_cap > 0:
        used = tokens_used(db, user_id)
        if used >= total_cap:
            raise QuotaExceeded(
                f"体验额度已用完（累计 {used:,} / {total_cap:,} tokens）。"
                "填写自己的 API Key（BYOK）即可继续使用，不受此限制。"
            )

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
    reviews_limit = effective_reviews_limit(db, user_id, plan_info["reviews_per_day"])
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

    # 次数闸：查与占位必须是同一条语句，否则并发全部读到同一个旧计数一起放行
    if _reserve_review_slot(db, user_id, reviews_limit, since):
        return

    # 日限满了：CDK 次数在这里垫一次。垫出来的这一次不占日名额（它本来就是
    # "超出日限之后的加量"），所以不再插占位记录。
    if cdk_service.try_consume_credit(db, user_id):
        return
    # 额度是被"未验证"压下来的时候，必须先说这件事：此时用户看到的
    # "限 1 次"根本不是套餐的真实额度，让他去升级套餐或兑换 CDK 属于误导，
    # 而他真正要做的（去邮箱点一下激活链接）是免费且立刻生效的。
    if reviews_limit < plan_info["reviews_per_day"]:
        raise QuotaExceeded(
            f"24 小时内评审次数已用完（未验证邮箱的账号每天限 {reviews_limit} 次）。"
            f"去邮箱点一下激活链接即可解锁 {plan_info['name']} 套餐的"
            f"每天 {plan_info['reviews_per_day']} 次——没收到可在账户页重新发送。"
            "也可以填写自己的 API Key（BYOK）以不受限制使用。"
        )
    raise QuotaExceeded(
        f"24 小时内评审次数已用完（{plan_info['name']} 套餐限 {reviews_limit} 次）。"
        "可兑换 CDK 获得加量次数、升级套餐，或填写自己的 API Key（BYOK）以不受限制使用。"
    )


# ---------------------------------------------------------------------------
# 预留的三个动作：占位 / 结算 / 释放
# ---------------------------------------------------------------------------


def _reserve_review_slot(
    db: Session, user_id: str, reviews_limit: int, since: datetime
) -> bool:
    """名额没满就占一个，返回"占到了吗"。检查与占位在同一条 SQL 里完成。

    并发正确性与 cdk_service.try_consume_credit 同一套防线（那边是次数余额，
    这边是日名额，形状完全一样）：
      · PostgreSQL：先取该用户在 quota 命名空间上的事务级 advisory lock，
        READ COMMITTED 下子查询读的是语句开始时的快照，不加锁挡不住并发；
      · SQLite：单条 INSERT...SELECT 全程在写锁保护下完成。
    """
    from app.services import cdk_service

    cdk_service.serialize_user_writes(db, user_id, "quota")
    result = db.execute(
        text(
            "INSERT INTO usage_records "
            "(id, user_id, review_id, kind, persona_count, cost_usd, "
            " input_tokens, output_tokens, key_source, created_at) "
            "SELECT :id, :uid, NULL, :res_kind, 0, 0.0, 0, 0, 'server', :now "
            "WHERE (SELECT COUNT(*) FROM usage_records "
            "       WHERE user_id = :uid AND key_source = 'server' "
            "         AND created_at >= :since "
            "         AND (kind = 'review' "
            "              OR (kind = :res_kind AND created_at >= :cutoff))) < :cap"
        ),
        {
            "id": str(uuid.uuid4()),
            "uid": user_id,
            "res_kind": RESERVATION_KIND,
            "now": _naive_utc(datetime.now(timezone.utc)),
            "since": _naive_utc(since),
            "cutoff": _naive_utc(_reservation_cutoff()),
            "cap": int(reviews_limit),
        },
    )
    db.commit()
    return result.rowcount == 1


def _oldest_reservation(db: Session, user_id: str) -> Optional[UsageRecord]:
    """该用户最早的一条未结算占位。

    占位之间是**可互换**的（每条就是"一个名额"，不带 review_id —— check_quota
    跑在评审落库之前，那时还没有 id 可写）。所以结算/释放取最早的一条即可：
    并发跑两条评审、先完成的那条结算掉更早的占位，对计数没有任何差别，
    唯一的痕迹是这条用量记录的 created_at 是"发起时刻"而不是"完成时刻"——
    而按发起时刻计入 24h 窗口本来就更贴近"这次请求算今天的"。
    """
    return (
        db.query(UsageRecord)
        .filter(
            UsageRecord.user_id == user_id,
            UsageRecord.kind == RESERVATION_KIND,
            UsageRecord.key_source == "server",
        )
        .order_by(UsageRecord.created_at.asc())
        .first()
    )


def _settle_reservation(db: Session, user_id: str, values: dict) -> Optional[UsageRecord]:
    """把最早的一条占位原地改写成真实用量；没有占位可结算时返回 None。

    条件 UPDATE（`WHERE kind = 占位`）保证两个并发结算不会改同一行：
    第二个 rowcount=0，退回去走"插一条新的"，计数仍然正确。
    """
    row = _oldest_reservation(db, user_id)
    if row is None:
        return None
    updated = (
        db.query(UsageRecord)
        .filter(UsageRecord.id == row.id, UsageRecord.kind == RESERVATION_KIND)
        .update(values, synchronize_session=False)
    )
    if updated != 1:
        return None
    db.commit()
    db.refresh(row)  # 上面是批量 UPDATE，内存里的 row 还是占位时的旧值
    return row


def release_review_slot(db: Session, user_id: str, key_source: str = "server") -> bool:
    """释放一个占位（评审失败 / 被收尸时调）。返回"这次真的释放了吗"。

    必须存在这条路径：占位是在评审**发起**时写的，评审没跑成的话它就成了
    永久占坑——用户被自己失败的评审挡在门外，直到 24h 窗口滑过去。
    这正是本仓库"扣了不退"那个缺陷的同型陷阱，不能再犯第二次。

    没有可释放的占位时返回 False 而不是报错：credits 模式、BYOK、配额关闭
    这三种情形下 check_quota 压根不占位，调用方不必先判断自己该不该调。
    """
    if key_source != "server":
        return False
    row = _oldest_reservation(db, user_id)
    if row is None:
        return False
    deleted = (
        db.query(UsageRecord)
        .filter(UsageRecord.id == row.id, UsageRecord.kind == RESERVATION_KIND)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted == 1


def sweep_stale_reservations(db: Session) -> int:
    """删掉超过 TTL 仍未结算/释放的占位，返回删了几条。

    兜底用：进程被 kill -9 时 release_review_slot 没机会跑。TTL 之外的占位
    早已不参与任何配额判断（见 _counts_toward_daily_reviews），这里只是不让
    它们在用量表里当垃圾长期堆着。启动收尸时调一次（见 app/db.py）。
    """
    n = (
        db.query(UsageRecord)
        .filter(
            UsageRecord.kind == RESERVATION_KIND,
            UsageRecord.created_at < _reservation_cutoff(),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(n or 0)


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
    """评审结束后调用。无论配额是否开启都记录——这是日后计费/token 报表的事实源。

    平台垫付的评审（kind=review + key_source=server）优先**改写**入口留下的占位，
    而不是插一条新记录：占位已经占掉了一个日名额，再插一条就等于一次评审计两次。
    找不到占位就照旧插入——BYOK、配额关闭、credits 模式、以及占位已过 TTL 被清掉
    的情形都走这一条，语义与改动前完全一致。
    """
    if kind == "review" and key_source == "server":
        settled = _settle_reservation(
            db,
            user_id,
            {
                "kind": "review",
                "review_id": review_id,
                "persona_count": int(persona_count or 0),
                "cost_usd": float(cost_usd or 0.0),
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
            },
        )
        if settled is not None:
            return settled

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
