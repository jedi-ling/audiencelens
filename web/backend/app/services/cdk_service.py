"""CDK 兑换码：后台批量生成 → 用户免登录兑换 → 获得评审次数（credits）。

设计要点：
  1. 次数只对"服务端垫付 key"的评审生效——BYOK 用户自己付钱，本来就不限量
     （见 quota_service.check_quota 的 key_source 判断）。
  2. 余额是 CreditLedger 流水求和，不是可变计数器——与 UsageRecord 同一哲学，
     事实源永远是只增不改的流水，天然可审计、可对账。
  3. 兑换码用 secrets 生成，去掉易混淆字符（0/O、1/I/L）；
     redeem 接口必须配严格限流（见 platform.py），否则可被暴力枚举。
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CdkCode, CdkRedemption, CreditLedger

# 去掉 0/O/1/I/L 这些印刷体里易混淆的字符——用户是要手抄/口播这个码的
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CODE_GROUPS = 3
_CODE_GROUP_LEN = 4


class CdkError(ValueError):
    """兑换失败的业务错误（码不存在/已停用/已过期/已用完/重复兑换）。"""


def _random_code() -> str:
    groups = [
        "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_GROUP_LEN))
        for _ in range(_CODE_GROUPS)
    ]
    return "AL-" + "-".join(groups)


def generate_codes(
    db: Session,
    count: int,
    credits: int,
    max_uses: int = 1,
    expires_in_days: Optional[int] = None,
    note: Optional[str] = None,
) -> List[CdkCode]:
    """批量生成兑换码，返回同一 batch_id 的一组码。"""
    if count < 1 or count > 500:
        raise ValueError("单批生成数量须在 1-500 之间")
    if credits < 1 or credits > 10000:
        raise ValueError("每码发放次数须在 1-10000 之间")
    if max_uses < 1 or max_uses > 100000:
        raise ValueError("每码可兑换人数须在 1-100000 之间")

    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        if expires_in_days
        else None
    )
    batch_id = str(uuid.uuid4())
    rows = []
    for _ in range(count):
        # unique 约束兜底；随机空间 31^12 ≈ 7.9e17，同批撞码概率可忽略，
        # 万一撞上让唯一约束报错重试一次即可（这里简单起见直接重新生成）
        code = _random_code()
        while db.query(CdkCode.id).filter(CdkCode.code == code).first() is not None:
            code = _random_code()
        row = CdkCode(
            code=code,
            credits=credits,
            max_uses=max_uses,
            expires_at=expires_at,
            batch_id=batch_id,
            note=note,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def list_codes(
    db: Session,
    status: Optional[str] = None,  # active | disabled | exhausted | expired
    limit: int = 50,
    offset: int = 0,
) -> dict:
    now = datetime.now(timezone.utc)
    q = db.query(CdkCode)
    if status == "disabled":
        q = q.filter(CdkCode.is_disabled.is_(True))
    elif status == "exhausted":
        q = q.filter(CdkCode.used_count >= CdkCode.max_uses)
    elif status == "expired":
        q = q.filter(CdkCode.expires_at.isnot(None), CdkCode.expires_at < now)
    elif status == "active":
        q = q.filter(
            CdkCode.is_disabled.is_(False),
            CdkCode.used_count < CdkCode.max_uses,
        ).filter((CdkCode.expires_at.is_(None)) | (CdkCode.expires_at >= now))

    total = q.count()
    rows = q.order_by(CdkCode.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "codes": [_code_to_dict(r, now) for r in rows],
    }


def _code_to_dict(row: CdkCode, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    expires_at = row.expires_at
    # SQLite 存的是 naive datetime，比较前补 UTC 时区
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if row.is_disabled:
        status = "disabled"
    elif row.used_count >= row.max_uses:
        status = "exhausted"
    elif expires_at is not None and expires_at < now:
        status = "expired"
    else:
        status = "active"
    return {
        "id": row.id,
        "code": row.code,
        "credits": row.credits,
        "max_uses": row.max_uses,
        "used_count": row.used_count,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "status": status,
        "batch_id": row.batch_id,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def disable_code(db: Session, code_id: str) -> bool:
    row = db.get(CdkCode, code_id)
    if not row:
        return False
    row.is_disabled = True
    db.commit()
    return True


def redeem(db: Session, code_str: str, user_id: str) -> dict:
    """兑换。所有校验失败统一抛 CdkError（对外只说"无效或已被使用"，
    不区分"码不存在"和"码已用完"——枚举者拿不到额外信息）。"""
    code_str = (code_str or "").strip().upper()
    if not code_str:
        raise CdkError("请输入兑换码")

    row = db.query(CdkCode).filter(CdkCode.code == code_str).first()
    now = datetime.now(timezone.utc)
    expires_at = row.expires_at if row else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        not row
        or row.is_disabled
        or row.used_count >= row.max_uses
        or (expires_at is not None and expires_at < now)
    ):
        raise CdkError("兑换码无效或已被使用")

    already = (
        db.query(CdkRedemption.id)
        .filter(CdkRedemption.code_id == row.id, CdkRedemption.user_id == user_id)
        .first()
    )
    if already:
        raise CdkError("你已经兑换过这个码了")

    # used_count 的检查与自增必须是同一条语句——上面的预检只是快速失败，
    # 并发时两个请求都可能通过预检，靠这里的条件 UPDATE 保证不超发
    # is_disabled 用绑定参数而不是字面量 0：0/1 是 SQLite 的布尔写法，
    # PostgreSQL（部署文档指定的生产库）里 boolean 列跟整数不可比，
    # 这条 UPDATE 会直接报错 —— 也就是切到 Postgres 后所有 CDK 兑换全挂。
    # 交给 SQLAlchemy 按方言适配 False，两种库上都成立。
    claimed = db.execute(
        text(
            "UPDATE cdk_codes SET used_count = used_count + 1 "
            "WHERE id = :cid AND is_disabled = :disabled AND used_count < max_uses "
            "AND (expires_at IS NULL OR expires_at >= :now)"
        ),
        {"cid": row.id, "disabled": False, "now": datetime.utcnow()},
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise CdkError("兑换码无效或已被使用")

    db.add(CdkRedemption(code_id=row.id, user_id=user_id, credits=row.credits))
    db.add(
        CreditLedger(
            user_id=user_id, delta=row.credits, reason="cdk_redeem", ref_id=row.id
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # (code_id, user_id) 唯一约束兜底：并发重复兑换时回滚（连同上面的自增一起撤销）
        db.rollback()
        raise CdkError("你已经兑换过这个码了")
    return {"credits_granted": row.credits, "balance": credit_balance(db, user_id)}


def credit_balance(db: Session, user_id: str) -> int:
    total = (
        db.query(func.coalesce(func.sum(CreditLedger.delta), 0))
        .filter(CreditLedger.user_id == user_id)
        .scalar()
    )
    return int(total or 0)


def _credit_lock_key(user_id: str) -> int:
    """把 user_id 映射成 pg_advisory_lock 需要的 64 位有符号整数。"""
    digest = hashlib.blake2b(f"al:credits:{user_id}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


def _serialize_credit_writes(db: Session, user_id: str) -> None:
    """把同一用户的次数扣减/退还串行化到本事务结束。

    这里以前只有一条 `INSERT ... SELECT ... WHERE (子查询)`，注释还写着
    "检查与扣减在同一条语句里，并发不可能双花"。那句话在 SQLite 上碰巧成立
    （单条写语句全程持库级写锁），但生产库是 PostgreSQL：READ COMMITTED 下
    子查询看到的是**语句开始时**的快照，两个并发请求都能读到余额 1，
    于是各插一条 -1 —— 余额被扣成负数，用户白跑一次评审。
    事务级 advisory lock 是代价最小的正解：不动"流水求和才是事实源"这个模型
    （改成可变计数器就会与流水漂移），锁随 commit/rollback 自动释放，
    也不会在 SQLite 上引入任何行为变化（那边直接跳过）。
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _credit_lock_key(user_id)})


def try_consume_credit(db: Session, user_id: str, ref_id: Optional[str] = None) -> bool:
    """原子地"查余额并扣一次"：余额 > 0 才插入 -1 流水，返回是否扣成功。

    原子性由两层共同保证（见 _serialize_credit_writes）：
      · PostgreSQL：先取该用户的事务级 advisory lock，同一时刻只有一个请求
        能进到这段临界区，后到的那个会在前一个提交后才读余额；
      · SQLite：单条 INSERT...SELECT 本身就在写锁保护下完成。
    """
    _serialize_credit_writes(db, user_id)
    result = db.execute(
        text(
            "INSERT INTO credit_ledger (id, user_id, delta, reason, ref_id, created_at) "
            "SELECT :id, :uid, -1, 'review', :ref, :now "
            "WHERE (SELECT COALESCE(SUM(delta), 0) FROM credit_ledger WHERE user_id = :uid) > 0"
        ),
        {
            "id": str(uuid.uuid4()),
            "uid": user_id,
            "ref": ref_id,
            "now": datetime.utcnow(),
        },
    )
    db.commit()
    return result.rowcount == 1


def refund_credit(db: Session, user_id: str, ref_id: str, reason: str = "review_refund") -> bool:
    """把一次已扣的评审次数退回去；返回"这次真的退了吗"。

    幂等键是 (user_id, reason, ref_id)：同一条评审无论失败几次、收尸补跑几次，
    都只会多出一行 +1。判重与插入必须在同一条语句里，否则并发退款会退两次——
    与扣减同一套并发防线（PostgreSQL 上再加事务级 advisory lock）。

    ref_id 强制必填：没有幂等键的退还根本无法保证只退一次，宁可让调用方报错，
    也不能悄悄插一行"看起来退成功了"的凭空发次数。
    """
    if not ref_id:
        raise ValueError("退还评审次数必须带 ref_id（幂等键），否则无法保证只退一次")

    _serialize_credit_writes(db, user_id)
    result = db.execute(
        text(
            "INSERT INTO credit_ledger (id, user_id, delta, reason, ref_id, created_at) "
            "SELECT :id, :uid, 1, :reason, :ref, :now "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM credit_ledger "
            "  WHERE user_id = :uid AND reason = :reason AND ref_id = :ref"
            ")"
        ),
        {
            "id": str(uuid.uuid4()),
            "uid": user_id,
            "reason": reason,
            "ref": ref_id,
            "now": datetime.utcnow(),
        },
    )
    db.commit()
    return result.rowcount == 1
