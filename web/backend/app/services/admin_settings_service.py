"""后台可调配置：DB 覆盖值优先于环境变量默认值。

只有白名单里的键可被管理员修改——像 jwt_secret、database_url、cors_origins
这类需要重启才能安全生效的基础设施配置，不放进这里，后台面板也不会显示可编辑项。

用法：
    admin_settings_service.get(db, "quota_enabled", settings.quota_enabled)
    admin_settings_service.set_override(db, "quota_enabled", True)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest
from app.models import PlatformSetting

# 键 -> (类型转换函数, 描述, 取值范围校验)
ADJUSTABLE: Dict[str, dict] = {
    "quota_enabled": {"cast": bool, "label": "配额开关"},
    "quota_mode": {
        "cast": str,
        "label": "配额模式（plan=套餐日限 / credits=纯CDK次数制，用完即止）",
        "choices": ("plan", "credits"),
    },
    "quota_free_reviews_per_day": {"cast": int, "label": "免费档每日评审次数上限", "min": 0},
    "quota_free_cost_usd_per_day": {"cast": float, "label": "免费档每日成本上限（美元）", "min": 0},
    "ratelimit_enabled": {"cast": bool, "label": "限流开关"},
    "ratelimit_per_minute": {"cast": int, "label": "通用接口限流（次/分钟）", "min": 1},
    "ratelimit_review_per_hour": {"cast": int, "label": "评审接口限流（次/小时）", "min": 1},
    "key_mode": {"cast": str, "label": "Key 解析模式", "choices": ("byok", "managed", "hybrid")},
    "review_concurrency": {"cast": int, "label": "单次评审人格并发度", "min": 1, "max": 32},
}


def _cast(key: str, raw: str):
    spec = ADJUSTABLE[key]
    if spec["cast"] is bool:
        return raw == "1"
    return spec["cast"](raw)


def _to_raw(key: str, value) -> str:
    spec = ADJUSTABLE[key]
    if spec["cast"] is bool:
        return "1" if bool(value) else "0"
    return str(spec["cast"](value))


def _validate(key: str, value) -> None:
    spec = ADJUSTABLE[key]
    if "choices" in spec and value not in spec["choices"]:
        raise BadRequest(f"{key} 必须是 {'/'.join(spec['choices'])} 之一")
    if "min" in spec and spec["cast"] is not bool and float(value) < spec["min"]:
        raise BadRequest(f"{key} 不能小于 {spec['min']}")
    if "max" in spec and spec["cast"] is not bool and float(value) > spec["max"]:
        raise BadRequest(f"{key} 不能大于 {spec['max']}")


def get(db: Session, key: str, default):
    """单个键的有效值：DB 覆盖优先，否则回落传入的 env 默认值。"""
    if key not in ADJUSTABLE:
        return default
    row = db.get(PlatformSetting, key)
    if row is None:
        return default
    try:
        return _cast(key, row.value)
    except (ValueError, TypeError):
        return default


def set_override(db: Session, key: str, value) -> dict:
    if key not in ADJUSTABLE:
        raise BadRequest(f"未知或不可调整的配置项：{key}")
    spec = ADJUSTABLE[key]
    try:
        typed = spec["cast"](value)
    except (ValueError, TypeError):
        raise BadRequest(f"{key} 类型应为 {spec['cast'].__name__}")
    _validate(key, typed)
    row = db.get(PlatformSetting, key)
    raw = _to_raw(key, typed)
    if row is None:
        row = PlatformSetting(key=key, value=raw)
        db.add(row)
    else:
        row.value = raw
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"key": key, "value": typed}


def clear_override(db: Session, key: str) -> bool:
    if key not in ADJUSTABLE:
        raise BadRequest(f"未知配置项：{key}")
    row = db.get(PlatformSetting, key)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def get_all_effective(db: Session) -> list:
    """后台面板用：每一项的当前有效值、是否被覆盖、env 默认值、说明。"""
    env_defaults = {
        "quota_enabled": settings.quota_enabled,
        "quota_mode": settings.quota_mode,
        "quota_free_reviews_per_day": settings.quota_free_reviews_per_day,
        "quota_free_cost_usd_per_day": settings.quota_free_cost_usd_per_day,
        "ratelimit_enabled": settings.ratelimit_enabled,
        "ratelimit_per_minute": settings.ratelimit_per_minute,
        "ratelimit_review_per_hour": settings.ratelimit_review_per_hour,
        "key_mode": settings.key_mode,
        "review_concurrency": settings.review_concurrency,
    }
    overrides = {row.key: row for row in db.query(PlatformSetting).all()}
    out = []
    for key, spec in ADJUSTABLE.items():
        overridden = key in overrides
        try:
            effective = _cast(key, overrides[key].value) if overridden else env_defaults[key]
        except (ValueError, TypeError):
            effective = env_defaults[key]
        out.append({
            "key": key,
            "label": spec["label"],
            "type": spec["cast"].__name__,
            "choices": spec.get("choices"),
            "env_default": env_defaults[key],
            "effective_value": effective,
            "overridden": overridden,
        })
    return out
