"""邮箱验证 / 密码重置的一次性令牌。

安全约定（三条都不能省）：
  1. 只存 SHA-256 摘要，不存令牌原文——库泄露也无法拿去重置别人的密码
  2. 签发新令牌时作废该用户同用途的旧令牌——避免"发了三次找回邮件、
     三个链接都还能用"这种攻击面
  3. 用过即作废（used_at）+ 到期作废，两道都验
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuthToken

PURPOSE_VERIFY_EMAIL = "verify_email"
PURPOSE_RESET_PASSWORD = "reset_password"


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue(db: Session, user_id: str, purpose: str, ttl_seconds: int) -> str:
    """签发令牌，返回明文（只在这一刻存在，之后库里只有摘要）。"""
    # 同用途旧令牌一并作废——不给"多个链接同时有效"留口子
    db.query(AuthToken).filter(
        AuthToken.user_id == user_id,
        AuthToken.purpose == purpose,
        AuthToken.used_at.is_(None),
    ).update({"used_at": datetime.now(timezone.utc)}, synchronize_session=False)

    raw = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=_digest(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
    )
    db.commit()
    return raw


def consume(db: Session, raw_token: str, purpose: str) -> Optional[str]:
    """校验并作废令牌；成功返回 user_id，失败返回 None。

    失败原因（不存在/用过/过期）对调用方一律是 None——不向外区分，
    免得成为"这个令牌是否存在过"的探测接口。
    """
    row = (
        db.query(AuthToken)
        .filter(AuthToken.token_hash == _digest(raw_token), AuthToken.purpose == purpose)
        .first()
    )
    if row is None or row.used_at is not None:
        return None

    expires_at = row.expires_at
    if expires_at.tzinfo is None:  # SQLite 取回来是 naive，补上 UTC 再比
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    row.used_at = datetime.now(timezone.utc)
    db.commit()
    return row.user_id
