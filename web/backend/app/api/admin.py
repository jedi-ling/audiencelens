"""后台管理路由：运行时配置、平台级 API Key、系统概览、判断复利、套餐、任务与评审巡检、审计日志。

全部挂在 Depends(require_admin) 之后——未设置 AL_ADMIN_TOKEN 时整体 503，
配置后需要 X-Admin-Token 请求头匹配才能访问。见 docs/MAINTENANCE.md 的
「后台管理面板」一节。
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest, NotFound
from app.db import get_db
from app.deps import rate_limit, require_admin
from app.models import (
    CdkCode,
    CdkRedemption,
    CreditLedger,
    Job,
    Judgment,
    Review,
    UsageRecord,
    User,
    UserApiKey,
)
from app.services import (
    admin_settings_service,
    audit_log_service,
    cdk_service,
    key_service,
    ledger_service,
    mail_service,
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
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
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
            "input_tokens_total": int(usage_24h[2] or 0),
            "output_tokens_total": int(usage_24h[3] or 0),
            "tokens_total": int((usage_24h[2] or 0) + (usage_24h[3] or 0)),
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
    tokens_by_day: dict = {}
    for created_at, cost, in_tok, out_tok in db.query(
        UsageRecord.created_at,
        UsageRecord.cost_usd,
        UsageRecord.input_tokens,
        UsageRecord.output_tokens,
    ).filter(UsageRecord.created_at >= since).all():
        k = bucket_key(created_at)
        if not k:
            continue
        cost_by_day[k] = cost_by_day.get(k, 0.0) + float(cost or 0.0)
        b = tokens_by_day.setdefault(k, {"in": 0, "out": 0})
        b["in"] += int(in_tok or 0)
        b["out"] += int(out_tok or 0)

    series = []
    for i in range(days + 1):
        day = (since + timedelta(days=i)).date().isoformat()
        bucket = review_by_day.get(day, {"total": 0})
        tok = tokens_by_day.get(day, {"in": 0, "out": 0})
        series.append(
            {
                "date": day,
                "reviews_total": bucket.get("total", 0),
                "reviews_completed": bucket.get("completed", 0),
                "reviews_failed": bucket.get("failed", 0),
                "cost_usd": round(cost_by_day.get(day, 0.0), 4),
                "input_tokens": tok["in"],
                "output_tokens": tok["out"],
                "tokens_total": tok["in"] + tok["out"],
            }
        )
    return {"days": days, "series": series}


# ---------------- 运营健康（成功率 / 耗时 / 卡死）----------------
#
# timeseries 回答"跑了多少、花了多少钱"，这一段回答"跑得好不好"。
# 两者刻意分开：前者是业务量，后者是系统健康度，看板上也该是两张图。

# 一个任务在 queued/running 待多久算"卡死"。默认 30 分钟——
# 一次评审要调数十次 LLM，正常也可能跑几分钟，阈值太小会天天误报。
STUCK_MINUTES_DEFAULT = 30


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """库里存的是 naive UTC（见 models 的 default=datetime.now(timezone.utc)，
    SQLite 落盘时丢时区）。跟 aware 的 now() 相减前必须补回 tzinfo，否则 TypeError。"""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _percentile(sorted_values: list, pct: float) -> Optional[float]:
    """最近秩法。刻意不引入 numpy/statistics.quantiles——
    这里只喂看板，样本量小的时候插值法反而让人以为精度比实际高。"""
    if not sorted_values:
        return None
    k = max(0, min(len(sorted_values) - 1, int(round(pct / 100.0 * len(sorted_values) + 0.5)) - 1))
    return round(float(sorted_values[k]), 2)


_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_NUM_RE = re.compile(r"\d+")


def _error_signature(msg: Optional[str]) -> str:
    """把错误消息归一成"同一类错误"的签名，好让 Top 榜真的能聚起来。

    不归一的话，每条消息里的 review_id / 行号 / 耗时都不一样，
    N 次同类故障会散成 N 个只出现 1 次的条目，榜单等于没有。
    """
    if not msg:
        return "(无错误消息)"
    s = _UUID_RE.sub("<id>", msg.strip())
    s = _NUM_RE.sub("<n>", s)
    return s[:160]


@router.get("/stats/health")
async def stats_health(
    days: int = 14,
    stuck_minutes: int = STUCK_MINUTES_DEFAULT,
    db: Session = Depends(get_db),
):
    """系统健康度：按天成功率 + 评审耗时分位数 + 当前卡死的任务。

    卡死的定义是"状态还停在 queued/running，但创建时间已超过阈值"。
    进程内队列（InProcessBackend）在进程重启后不会自动把这些行推进到终态——
    启动时的孤儿清理只覆盖启动那一刻，之后再卡住就没人管了，只能靠这里看见。
    """
    days = max(1, min(days, 90))
    stuck_minutes = max(1, min(stuck_minutes, 60 * 24))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    by_day: dict = {}
    durations: list = []
    for created_at, completed_at, status in db.query(
        Review.created_at, Review.completed_at, Review.status
    ).filter(Review.created_at >= since).all():
        c = _as_utc(created_at)
        if c is None:
            continue
        bucket = by_day.setdefault(c.date().isoformat(), {"completed": 0, "failed": 0, "other": 0})
        if status == "completed":
            bucket["completed"] += 1
            done = _as_utc(completed_at)
            if done is not None:
                secs = (done - c).total_seconds()
                # 负数只可能来自时钟回拨或脏数据；混进分位数会把 P50 拉歪
                if secs >= 0:
                    durations.append(secs)
        elif status == "failed":
            bucket["failed"] += 1
        else:
            bucket["other"] += 1

    series = []
    for i in range(days + 1):
        day = (since + timedelta(days=i)).date().isoformat()
        b = by_day.get(day, {"completed": 0, "failed": 0, "other": 0})
        settled = b["completed"] + b["failed"]
        series.append(
            {
                "date": day,
                "completed": b["completed"],
                "failed": b["failed"],
                "running": b["other"],
                # 没有已结束的评审时是 None 而不是 100——
                # 那天没跑过任何东西，不该在图上画成一条漂亮的满分线
                "success_rate": round(b["completed"] / settled, 4) if settled else None,
            }
        )

    durations.sort()
    stuck_before = now - timedelta(minutes=stuck_minutes)
    stuck_rows = (
        db.query(Job)
        .filter(Job.status.in_(["queued", "running"]), Job.created_at <= stuck_before)
        .order_by(Job.created_at.asc())
        .limit(50)
        .all()
    )

    settled_total = sum(s["completed"] + s["failed"] for s in series)
    failed_total = sum(s["failed"] for s in series)
    return {
        "days": days,
        "series": series,
        "totals": {
            "completed": sum(s["completed"] for s in series),
            "failed": failed_total,
            "success_rate": round((settled_total - failed_total) / settled_total, 4)
            if settled_total
            else None,
        },
        "duration_seconds": {
            "sample_size": len(durations),
            "p50": _percentile(durations, 50),
            "p95": _percentile(durations, 95),
            "avg": round(sum(durations) / len(durations), 2) if durations else None,
            "max": round(durations[-1], 2) if durations else None,
        },
        "stuck": {
            "threshold_minutes": stuck_minutes,
            "count": len(stuck_rows),
            "jobs": [
                {
                    **_job_row(j),
                    "stuck_minutes": int((now - _as_utc(j.created_at)).total_seconds() // 60),
                }
                for j in stuck_rows
            ],
        },
    }


@router.get("/stats/jobs")
async def stats_jobs(days: int = 14, db: Session = Depends(get_db)):
    """任务队列的聚合视图：状态分布 + 失败原因 Top 榜 + 执行耗时。

    /jobs 是逐条日志流，出事时你得自己往下翻。这条是"翻之前先看哪儿"。
    """
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    by_status = dict(
        db.query(Job.status, func.count(Job.id))
        .filter(Job.created_at >= since)
        .group_by(Job.status)
        .all()
    )
    by_kind = dict(
        db.query(Job.kind, func.count(Job.id))
        .filter(Job.created_at >= since)
        .group_by(Job.kind)
        .all()
    )

    reasons: dict = {}
    for (msg,) in db.query(Job.error_message).filter(
        Job.created_at >= since, Job.status == "failed"
    ).all():
        sig = _error_signature(msg)
        slot = reasons.setdefault(sig, {"signature": sig, "count": 0, "sample": msg})
        slot["count"] += 1

    runtimes = []
    for started_at, finished_at in db.query(Job.started_at, Job.finished_at).filter(
        Job.created_at >= since, Job.started_at.isnot(None), Job.finished_at.isnot(None)
    ).all():
        s, f = _as_utc(started_at), _as_utc(finished_at)
        if s and f and (f - s).total_seconds() >= 0:
            runtimes.append((f - s).total_seconds())
    runtimes.sort()

    return {
        "days": days,
        "by_status": {k: int(v) for k, v in by_status.items()},
        "by_kind": {k: int(v) for k, v in by_kind.items()},
        "failure_reasons": sorted(reasons.values(), key=lambda r: -r["count"])[:10],
        "runtime_seconds": {
            "sample_size": len(runtimes),
            "p50": _percentile(runtimes, 50),
            "p95": _percentile(runtimes, 95),
            "max": round(runtimes[-1], 2) if runtimes else None,
        },
    }


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
    from starlette.concurrency import run_in_threadpool

    model = row.model or settings.intent_model
    # 同上（platform.py 的 /keys/test）：test_connection 是同步网络调用，
    # 直接 await 会堵死事件循环，卡住的中转会拖垮整个后端的响应能力。
    return await run_in_threadpool(
        test_connection, model=model, api_key=api_key, provider=provider, api_base=row.api_base
    )


@router.delete("/server-key")
async def delete_server_key(provider: str = "anthropic", db: Session = Depends(get_db)):
    n = key_service.delete_platform_key(db, provider)
    if n:
        audit_log_service.record(db, "server_key.delete", provider)
    return {"deleted": n}


# ============================== 邮件发送 ==============================
# 邮件链路配错的代价是"用户注册后激活不了、密码忘了找不回"，而且默认 console 档
# 不会报任何错——不主动打一封真信就发现不了。所以这里给运营一个当场验证的入口。

# 只做"长得像邮箱"的最低限度校验：真正的判据是那封信到底发不发得出去，
# 不该在这里用正则去争论 RFC 5322 的边角。
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


@router.get("/mail/status")
async def mail_status():
    """当前邮件配置快照（不含密码）。

    configured_backend 与 effective_backend 可能不一致——配了 smtp 却缺
    AL_SMTP_HOST 就会回落 console，那正是最该被看见的一种配错。
    """
    return mail_service.describe_config()


class TestMailRequest(BaseModel):
    to: str


@router.post(
    "/mail/test",
    # 这个端点能让持令牌者向任意地址发信。主题和正文都是写死的（见下），
    # 所以它不是通用转发器；再加一道限流把"拿它当发信机刷"的成本压住。
    dependencies=[Depends(rate_limit("admin_mail_test", 10, 3600))],
)
async def send_test_mail(body: TestMailRequest, db: Session = Depends(get_db)):
    """真的发一封测试邮件。失败时回可读原因，不吞异常。

    与 send_mail 的区别正在于此：注册链路不能因为邮件服务商抽风就整体失败，
    所以那条路吞异常；而这条路存在的唯一目的就是把异常给运营看。
    """
    to = (body.to or "").strip()
    if not _EMAIL_RE.match(to):
        raise BadRequest("收件地址格式不对，请填一个你能打开的真实邮箱。")

    config = mail_service.describe_config()
    subject = "AudienceLens 测试邮件"
    # 正文写死：不接受调用方内容，避免这个端点被当成匿名转发器。
    text = (
        "这是一封来自 AudienceLens 后台的测试邮件。\n\n"
        "你能读到它，说明 SMTP 配置正确，用户的邮箱验证与密码重置邮件也能正常送达。\n"
        f"发件人: {config['mail_from']}\n"
        f"SMTP: {config['smtp_host']}:{config['smtp_port']}"
        f"（{'SSL' if config['smtp_use_ssl'] else 'STARTTLS'}）\n"
        f"站点地址(邮件里链接的落点): {config['public_web_url']}\n"
    )

    from starlette.concurrency import run_in_threadpool

    # SMTP 是同步阻塞网络调用；直接 await 会堵死事件循环，
    # 一台卡住的邮件服务器足以拖垮整个后端的响应能力（同 /server-key/test）。
    try:
        backend = await run_in_threadpool(mail_service.send_mail_strict, to, subject, text)
    except mail_service.MailError as exc:
        audit_log_service.record(db, "mail.test", to, {"ok": False, "error": str(exc)})
        return {
            "ok": False,
            "delivered": False,
            "backend": config["effective_backend"],
            "to": to,
            "error": str(exc),
            **config,
        }

    audit_log_service.record(db, "mail.test", to, {"ok": True, "backend": backend})
    if backend != "smtp":
        # console 档："调用成功"但根本没发出去。必须说清楚，不能让运营
        # 看见一个绿勾就以为配好了——那正是这个按钮要防的事。
        return {
            "ok": True,
            "delivered": False,
            "backend": backend,
            "to": to,
            "warning": (
                f"当前是 {backend} 档，邮件**没有真的发出**，只写到了服务器本地的 "
                f"{config['outbox_dir']}。用户仍然收不到任何邮件。"
                "要真发信请配 AL_MAIL_BACKEND=smtp 与 AL_SMTP_HOST 后重启。"
            ),
            **config,
        }
    return {
        "ok": True,
        "delivered": True,
        "backend": backend,
        "to": to,
        "message": (
            f"已通过 SMTP 投递给 {to}。请到该邮箱收件箱确认；"
            "几分钟内没收到就翻垃圾箱，仍然没有则去服务商后台看发信日志"
            "（SMTP 返回成功只代表服务商收下了，不代表对方收件服务器接受了）。"
        ),
        **config,
    }


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


@router.get("/cdk/redemptions")
async def list_cdk_redemptions(
    code: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """谁在什么时候兑了哪个码、拿到多少次数。

    在此之前 CdkRedemption 表只被 cdk_service（去重）和 user_data_service
    （用户自己导出数据）读过，后台一条都看不到——运营只能看见 used_count 这个
    数字，"我兑了码但没到账"这类客诉完全没法查。

    带上 credit_ledger 里对应的入账行：兑换记录存在、但流水没进账，
    正是"码用掉了次数没到"的形态，两边并排放才看得出来。
    """
    q = (
        db.query(CdkRedemption, CdkCode.code, CdkCode.note, User.email)
        .join(CdkCode, CdkCode.id == CdkRedemption.code_id)
        # outer join：匿名兑换（guest token）的 user_id 不在 users 表里，
        # 用 inner join 会把这批记录整个吞掉——而它们恰恰是最容易出问题的一批
        .outerjoin(User, User.id == CdkRedemption.user_id)
    )
    if code:
        q = q.filter(CdkCode.code == code.strip().upper())
    if user_id:
        q = q.filter(CdkRedemption.user_id == user_id.strip())

    total = q.count()
    rows = (
        q.order_by(CdkRedemption.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(limit, 200))
        .all()
    )

    ledger_by_user_code: dict = {}
    if rows:
        pairs = {(r.user_id, r.code_id) for r, _, _, _ in rows}
        for uid, ref, delta in db.query(
            CreditLedger.user_id, CreditLedger.ref_id, func.coalesce(func.sum(CreditLedger.delta), 0)
        ).filter(
            CreditLedger.reason == "cdk_redeem",
            CreditLedger.user_id.in_({u for u, _ in pairs}),
        ).group_by(CreditLedger.user_id, CreditLedger.ref_id).all():
            ledger_by_user_code[(uid, ref)] = int(delta or 0)

    return {
        "total": total,
        "offset": offset,
        "redemptions": [
            {
                "id": r.id,
                "code": code_str,
                "code_id": r.code_id,
                "note": note,
                "user_id": r.user_id,
                "user_email": email,  # None = 匿名/访客兑换，或用户已注销
                "credits": r.credits,
                # 对不上就是有问题：这一列存在的全部意义就是让"没到账"能被一眼看见
                "credited_in_ledger": ledger_by_user_code.get((r.user_id, r.code_id)),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r, code_str, note, email in rows
        ],
    }


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
    # 该用户单独的终身 token 上限。语义三态，不能只用一个可空整数表达：
    #   不传   → 不改动
    #   >= 0  → 设为该值（0 = 这个人不受限制）
    #   -1    → 清除覆盖，回落全局 AL_QUOTA_TOKENS_TOTAL
    # 用 -1 而不是 null 表示"清除"：Pydantic 里 null 与"没传"在 Optional 上
    # 无法区分，运营想恢复默认时会变成一个做不到的操作。
    token_quota_total: Optional[int] = None


@router.get("/users")
async def list_users(
    q: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """注册用户列表，附带各自的评审数与累计成本（近 30 天 + 全部）。"""
    query = db.query(User)
    if q:
        query = query.filter(User.email.contains(q.strip().lower()))
    total = query.count()

    # 排序只允许 User 表自己的列。reviews_total / cost_usd_total 是在 Python 里
    # 聚合出来的，只覆盖当前这一页——按它们排序会得到"页内有序、跨页乱序"的结果，
    # 比不能排序更容易误导人。要按用量排全局，得先把聚合下推到 SQL。
    sortable = {
        "created_at": User.created_at,
        "email": User.email,
        "plan": User.plan,
        "is_active": User.is_active,
    }
    col = sortable.get((sort or "created_at").strip())
    if col is None:
        raise BadRequest(f"不支持按 {sort} 排序，可选：{', '.join(sortable)}")
    query = query.order_by(col.asc() if order == "asc" else col.desc())

    rows = query.offset(max(offset, 0)).limit(min(limit, 200)).all()

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
        token_totals = {
            uid: (int(in_tok or 0), int(out_tok or 0))
            for uid, in_tok, out_tok in db.query(
                UsageRecord.user_id,
                func.coalesce(func.sum(UsageRecord.input_tokens), 0),
                func.coalesce(func.sum(UsageRecord.output_tokens), 0),
            )
            .filter(UsageRecord.user_id.in_(user_ids))
            .group_by(UsageRecord.user_id)
            .all()
        }

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
                "input_tokens_total": token_totals.get(u.id, (0, 0))[0],
                "output_tokens_total": token_totals.get(u.id, (0, 0))[1],
                "tokens_total": sum(token_totals.get(u.id, (0, 0))),
                # None = 跟随全局配置
                "token_quota_total": u.token_quota_total,
            }
            for u in rows
        ],
    }


@router.get("/users/{user_id}")
async def user_detail(user_id: str, db: Session = Depends(get_db)):
    """单个用户的全景：评审、用量按 key 来源拆分、BYOK 密钥、次数余额、兑换记录。

    列表页只能回答"这个人跑了多少、花了多少"。出问题时要问的是更细的：
    他用的是自己的 key 还是平台的？余额对不对得上兑换记录？最近几次是不是都失败了？
    这些以前只能连数据库查。

    **不返回任何密钥内容**——只返回 key_masked（本来就是给前端回显的字段）
    和 provider/last_used_at。密文永远不出这台机器。
    """
    u = db.get(User, user_id)
    if not u:
        raise NotFound("用户不存在")

    # 隐私政策明确写了"这类访问会记入后台审计日志"——列表页（/users）不记，
    # 因为它不含评审内容；这个端点会带出 recent 评审标题，属于政策里说的
    # "查看评审内容"，必须留痕，否则政策那句话就是空话。
    audit_log_service.record(db, "user.view_detail", u.email)

    review_status = dict(
        db.query(Review.status, func.count(Review.id))
        .filter(Review.user_id == user_id)
        .group_by(Review.status)
        .all()
    )
    recent_reviews = (
        db.query(Review)
        .filter(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
        .limit(20)
        .all()
    )

    usage_by_source = [
        {
            "key_source": src or "(未记录)",
            "count": int(cnt or 0),
            "cost_usd": round(float(cost or 0.0), 4),
            "input_tokens": int(in_tok or 0),
            "output_tokens": int(out_tok or 0),
        }
        for src, cnt, cost, in_tok, out_tok in db.query(
            UsageRecord.key_source,
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
        )
        .filter(UsageRecord.user_id == user_id)
        .group_by(UsageRecord.key_source)
        .all()
    ]

    keys = [
        {
            "provider": k.provider,
            "model": k.model,
            "api_base": k.api_base,
            "key_masked": k.key_masked,
            "is_active": k.is_active,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in db.query(UserApiKey).filter(UserApiKey.user_id == user_id).all()
    ]

    redemptions = [
        {
            "code": code_str,
            "credits": r.credits,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, code_str in db.query(CdkRedemption, CdkCode.code)
        .join(CdkCode, CdkCode.id == CdkRedemption.code_id)
        .filter(CdkRedemption.user_id == user_id)
        .order_by(CdkRedemption.created_at.desc())
        .all()
    ]

    return {
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "plan": u.plan,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "token_quota_total": u.token_quota_total,
        "reviews": {
            "by_status": {k: int(v) for k, v in review_status.items()},
            "total": sum(int(v) for v in review_status.values()),
            "recent": [_review_row(r) for r in recent_reviews],
        },
        "usage_by_key_source": usage_by_source,
        "api_keys": keys,
        "credit_balance": cdk_service.credit_balance(db, user_id),
        "cdk_redemptions": redemptions,
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
    if body.token_quota_total is not None:
        if body.token_quota_total < -1:
            raise BadRequest("token_quota_total 只能是 -1（清除覆盖）或 >= 0 的整数")
        new_cap = None if body.token_quota_total == -1 else int(body.token_quota_total)
        changes["token_quota_total"] = {"from": user.token_quota_total, "to": new_cap}
        user.token_quota_total = new_cap

    if not changes:
        raise BadRequest("没有要修改的字段（plan / is_active / token_quota_total）")

    db.commit()
    audit_log_service.record(db, "user.update", user.email, changes)
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.plan,
        "is_active": user.is_active,
        "token_quota_total": user.token_quota_total,
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


# ---------------- 任务的两个运维操作 ----------------
#
# 刻意**没有**「重试」：enqueue_review 只把 {"key_source": ...} 写进 payload，
# API key 是显式传参、绝不落库的（review_service.py 里那段注释解释了原因——
# 多 worker 并发时用环境变量注入会在用户之间串 key）。后台手上没有密钥，
# 重试必然当场失败，加一个注定失败的按钮比没有按钮更糟。
# 用户要重跑，走产品前端重新发起一次（那条路上有他自己的 key）。

TERMINAL_JOB_STATUSES = ("done", "failed", "cancelled")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """取消尚未开始的任务。

    只对 queued 生效：InProcessBackend 用线程池，已经在跑的线程杀不掉
    （Python 没有安全的线程中断）。对 running 返回 400 并指向 force-fail，
    而不是假装取消成功——那会让 UI 显示"已取消"而任务还在烧钱。
    """
    from app.services import job_service

    j = db.get(Job, job_id)
    if not j:
        raise NotFound("任务不存在")
    if j.status in TERMINAL_JOB_STATUSES:
        raise BadRequest(f"任务已是终态（{j.status}），无需取消")
    if j.status == "running":
        raise BadRequest(
            "任务已在执行中，进程内队列无法中断正在运行的线程。"
            "若确认它已卡死，请用「标记为失败」。"
        )

    backend_cancelled = job_service.get_backend().cancel(job_id)
    db.refresh(j)
    # backend.cancel 只有在 future 还没被线程池取走时才返回 True。
    # 返回 False 也要把库里的状态推到终态：不然这一行会永远停在 queued，
    # 既污染统计，也让"卡死任务"面板长期挂着一条永远不会动的记录。
    if j.status not in TERMINAL_JOB_STATUSES:
        j.status = "cancelled"
        j.finished_at = datetime.now(timezone.utc)
        db.commit()

    audit_log_service.record(
        db, "job.cancel", job_id, {"backend_cancelled": backend_cancelled, "kind": j.kind}
    )
    return {**_job_row(j), "backend_cancelled": backend_cancelled}


@router.post("/jobs/{job_id}/force-fail")
async def force_fail_job(job_id: str, db: Session = Depends(get_db)):
    """把卡死的任务强制推到 failed。

    这不会真的停下后台线程（停不了）——它做的是把库里那行推到终态，
    于是：统计不再被一条永远 running 的记录污染，关联评审也不再卡在
    "进行中"让用户干等。若线程其实还活着并最终跑完，_finish_job 会把
    状态改回 done，这是可接受的：终态被更正总好过永远没有终态。
    """
    j = db.get(Job, job_id)
    if not j:
        raise NotFound("任务不存在")
    if j.status in TERMINAL_JOB_STATUSES:
        raise BadRequest(f"任务已是终态（{j.status}）")

    prev = j.status
    j.status = "failed"
    j.finished_at = datetime.now(timezone.utc)
    j.error_message = "管理员标记为失败（任务卡死，无终态回写）"

    # 关联评审一并推到终态——否则用户前端会一直转圈等一个永远不来的结果
    review_updated = None
    if j.kind == "review" and j.ref_id:
        r = db.get(Review, j.ref_id)
        if r is not None and r.status not in ("completed", "failed"):
            r.status = "failed"
            r.error_message = "任务卡死，已由管理员终止"
            review_updated = r.id
    db.commit()

    audit_log_service.record(
        db, "job.force_fail", job_id, {"from": prev, "review_updated": review_updated}
    )
    return {**_job_row(j), "review_updated": review_updated}


def _review_row(r: Review) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "task_type": r.task_type,
        "target_title": r.target_title,
        "mode": r.mode,
        "status": r.status,
        "total_cost_usd": r.total_cost_usd,
        "input_tokens": r.input_tokens,
        "output_tokens": r.output_tokens,
        "tokens_total": (r.input_tokens or 0) + (r.output_tokens or 0),
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
    """带出 report_json 全文——用户材料与评审结论都在里面。

    隐私政策就是照着这个端点写的："为处理客诉、排查滥用、核对计费争议，
    运营方可以查看评审内容……这类访问会记入后台审计日志"。target_title 记进
    审计详情而不是只记 review_id：出事复盘时一眼能看出看的是哪份材料，
    不用再反查一次数据库。
    """
    r = db.get(Review, review_id)
    if not r:
        raise NotFound("评审不存在")
    audit_log_service.record(
        db, "review.view_detail", review_id, {"target_title": r.target_title}
    )
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
