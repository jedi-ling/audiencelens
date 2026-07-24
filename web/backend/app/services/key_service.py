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
from app.core.security import decrypt_secret, encrypt_secret, is_legacy_ciphertext, mask_key
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
    model: Optional[str] = None  # openai_compatible 档必填；anthropic 档为空则走人格分级
    api_base: Optional[str] = None


def get_user_key_row(db: Session, user_id: str, provider: str = "anthropic") -> Optional[UserApiKey]:
    return (
        db.query(UserApiKey)
        .filter(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
            UserApiKey.is_active.is_(True),
        )
        .order_by(UserApiKey.created_at.desc())
        .first()
    )


def get_user_key(db: Session, user_id: str, provider: str = "anthropic") -> Optional[str]:
    row = get_user_key_row(db, user_id, provider)
    if not row:
        return None
    try:
        return decrypt_secret(row.key_ciphertext, settings.encryption_key)
    except ValueError:
        # 密文损坏或换过 secret —— 视为无 key，让用户重填
        return None


def save_user_key(
    db: Session,
    user_id: str,
    raw_key: str,
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_base: Optional[str] = None,
) -> UserApiKey:
    """保存/轮换用户 key。旧 key 置为 inactive，保留审计痕迹。

    provider="openai_compatible" 时 model 必填（DeepSeek/Kimi/通义千问/智谱GLM/Ollama 等
    没有统一的默认模型，不像 Anthropic 能靠人格分级兜底）。
    """
    raw_key = (raw_key or "").strip()
    if not raw_key:
        raise ValueError("key 不能为空")
    if provider == "openai_compatible" and not (model or "").strip():
        raise ValueError("非 Anthropic 服务商必须指定模型名")

    db.query(UserApiKey).filter(
        UserApiKey.user_id == user_id,
        UserApiKey.provider == provider,
        UserApiKey.is_active.is_(True),
    ).update({"is_active": False})

    row = UserApiKey(
        user_id=user_id,
        provider=provider,
        model=(model or "").strip() or None,
        api_base=(api_base or "").strip() or None,
        key_ciphertext=encrypt_secret(raw_key, settings.encryption_key),
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


def save_platform_key(
    db: Session,
    raw_key: str,
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_base: Optional[str] = None,
) -> UserApiKey:
    return save_user_key(db, PLATFORM_KEY_OWNER, raw_key, provider, model=model, api_base=api_base)


def delete_platform_key(db: Session, provider: str = "anthropic") -> int:
    return delete_user_key(db, PLATFORM_KEY_OWNER, provider)


def get_platform_key_status(db: Session, provider: str = "anthropic") -> Optional[dict]:
    row = get_user_key_row(db, PLATFORM_KEY_OWNER, provider)
    if not row:
        return None
    return {
        "provider": row.provider,
        "model": row.model,
        "api_base": row.api_base,
        "masked": row.key_masked,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
    }


# provider 目前只有这两档（UserApiKey.provider 的取值范围），resolve_key 找不到
# 请求的档位时会按此顺序继续找用户/平台实际配置了的那一档——
# 否则"只填了 DeepSeek 没填 Anthropic"的用户会被写死的 provider="anthropic" 默认值堵在门外，
# 明明有能用的 key 却收到 428 llm_key_missing。
KNOWN_PROVIDERS = ("anthropic", "openai_compatible")


def resolve_key(db: Session, user_id: str, provider: str = "anthropic") -> ResolvedKey:
    """按 key_mode 解析出本次调用该用哪个 key（key_mode 支持后台面板实时覆盖）。"""
    mode = admin_settings_service.get(db, "key_mode", settings.key_mode)
    providers_to_try = [provider] + [p for p in KNOWN_PROVIDERS if p != provider]

    if mode in ("byok", "hybrid"):
        for p in providers_to_try:
            user_row = get_user_key_row(db, user_id, p)
            if not user_row:
                continue
            try:
                user_key = decrypt_secret(user_row.key_ciphertext, settings.encryption_key)
            except ValueError:
                continue
            if user_key:
                update_fields = {"last_used_at": datetime.now(timezone.utc)}
                # 顺手把 v1 存量密文升级成 v2（Fernet）——用户无需重填 key，
                # 用一次就自动迁移一条，不需要停机批处理。
                if is_legacy_ciphertext(user_row.key_ciphertext):
                    update_fields["key_ciphertext"] = encrypt_secret(
                        user_key, settings.encryption_key
                    )
                db.query(UserApiKey).filter(
                    UserApiKey.user_id == user_id,
                    UserApiKey.provider == p,
                    UserApiKey.is_active.is_(True),
                ).update(update_fields)
                db.commit()
                return ResolvedKey(
                    key=user_key, source="byok", provider=p,
                    model=user_row.model, api_base=user_row.api_base,
                )

    if mode in ("managed", "hybrid"):
        # 平台 key 优先于 env：后台面板设置的 key 无需重启即可生效
        for p in providers_to_try:
            platform_row = get_user_key_row(db, PLATFORM_KEY_OWNER, p)
            if not platform_row:
                continue
            try:
                platform_key = decrypt_secret(platform_row.key_ciphertext, settings.encryption_key)
            except ValueError:
                continue
            if platform_key:
                return ResolvedKey(
                    key=platform_key, source="server", provider=p,
                    model=platform_row.model, api_base=platform_row.api_base,
                )
        if settings.server_llm_key:
            return ResolvedKey(key=settings.server_llm_key, source="server", provider=provider)

    if mode == "managed":
        raise LLMKeyMissing("服务端未配置平台 API Key，托管模式不可用，请联系管理员在后台设置。")
    raise LLMKeyMissing()  # BYOK：引导用户去设置页填 key
