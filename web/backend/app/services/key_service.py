"""LLM Key 解析（埋线核心：决定"谁付这次评审的钱"）。

解析链由 AL_KEY_MODE 决定：
  byok    用户 key → 无则报 LLMKeyMissing（服务端永不垫钱）
  managed 服务端 key → 无则报 LLMKeyMissing（用户无需填 key，但你必须开配额）
  hybrid  用户 key → 回落服务端 key → 都无则报错

返回 ResolvedKey(key, source)，source 会写进 UsageRecord.key_source，
于是"这笔 token 花的是谁的钱"永远可追溯 —— 计费的前提。
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import LLMKeyMissing
from app.core.security import decrypt_secret, encrypt_secret, mask_key
from app.models import UserApiKey
from app.services import admin_settings_service

# 平台级 server key 复用 UserApiKey 表，用这个保留 user_id 区分于真实用户——
# 避免为"一把服务端共享 key"专门开一张表。由后台管理面板写入/轮换/删除。
PLATFORM_KEY_OWNER = "__platform__"


@dataclass
class ResolvedKey:
    key: str
    source: str  # "byok" | "server"
    provider: str = "anthropic"


def get_user_key(db: Session, user_id: str, provider: str = "anthropic") -> Optional[str]:
    row = (
        db.query(UserApiKey)
        .filter(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
            UserApiKey.is_active.is_(True),
        )
        .order_by(UserApiKey.created_at.desc())
        .first()
    )
    if not row:
        return None
    try:
        return decrypt_secret(row.key_ciphertext, settings.jwt_secret)
    except ValueError:
        # 密文损坏或换过 secret —— 视为无 key，让用户重填
        return None


def save_user_key(db: Session, user_id: str, raw_key: str, provider: str = "anthropic") -> UserApiKey:
    """保存/轮换用户 key。旧 key 置为 inactive，保留审计痕迹。"""
    raw_key = (raw_key or "").strip()
    if not raw_key:
        raise ValueError("key 不能为空")

    db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id,
        UserApiKey.provider == provider,
        UserApiKey.is_active.is_(True),
    ).update({"is_active": False})

    row = UserApiKey(
        user_id=user_id,
        provider=provider,
        key_ciphertext=encrypt_secret(raw_key, settings.jwt_secret),
        key_masked=mask_key(raw_key),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_user_key(db: Session, user_id: str, provider: str = "anthropic") -> int:
    n = (
        db.query(UserApiKey)
        .filter(UserApiKey.user_id == user_id, UserApiKey.provider == provider)
        .delete()
    )
    db.commit()
    return n


def get_platform_key(db: Session, provider: str = "anthropic") -> Optional[str]:
    """后台管理面板设置的平台级 server key；env 里的 ANTHROPIC_API_KEY 仍作为回落。"""
    return get_user_key(db, PLATFORM_KEY_OWNER, provider)


def save_platform_key(db: Session, raw_key: str, provider: str = "anthropic") -> UserApiKey:
    return save_user_key(db, PLATFORM_KEY_OWNER, raw_key, provider)


def delete_platform_key(db: Session, provider: str = "anthropic") -> int:
    return delete_user_key(db, PLATFORM_KEY_OWNER, provider)


def get_platform_key_status(db: Session, provider: str = "anthropic") -> Optional[dict]:
    row = (
        db.query(UserApiKey)
        .filter(
            UserApiKey.user_id == PLATFORM_KEY_OWNER,
            UserApiKey.provider == provider,
            UserApiKey.is_active.is_(True),
        )
        .order_by(UserApiKey.created_at.desc())
        .first()
    )
    if not row:
        return None
    return {
        "provider": row.provider,
        "masked": row.key_masked,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
    }


def resolve_key(db: Session, user_id: str, provider: str = "anthropic") -> ResolvedKey:
    """按 key_mode 解析出本次调用该用哪个 key（key_mode 支持后台面板实时覆盖）。"""
    mode = admin_settings_service.get(db, "key_mode", settings.key_mode)
    user_key = get_user_key(db, user_id, provider) if mode in ("byok", "hybrid") else None

    if user_key:
        db.query(UserApiKey).filter(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
            UserApiKey.is_active.is_(True),
        ).update({"last_used_at": datetime.now(timezone.utc)})
        db.commit()
        return ResolvedKey(key=user_key, source="byok", provider=provider)

    if mode in ("managed", "hybrid"):
        # 平台 key 优先于 env：后台面板设置的 key 无需重启即可生效
        server_key = get_platform_key(db, provider) or settings.server_llm_key
        if server_key:
            return ResolvedKey(key=server_key, source="server", provider=provider)

    if mode == "managed":
        raise LLMKeyMissing("服务端未配置平台 API Key，托管模式不可用，请联系管理员在后台设置。")
    raise LLMKeyMissing()  # BYOK：引导用户去设置页填 key
