"""后台可调配置：DB 覆盖值优先于环境变量默认值。

只有白名单里的键可被管理员修改——像 jwt_secret、database_url、cors_origins
这类需要重启才能安全生效的基础设施配置，不放进这里，后台面板也不会显示可编辑项。

用法：
    admin_settings_service.get(db, "quota_enabled", settings.quota_enabled)
    admin_settings_service.set_override(db, "quota_enabled", True)

**进入 ADJUSTABLE 的唯一门槛：运行时真的有代码读它。**
一个显示「已覆盖 · 1」、审计日志也留了痕、但运行时照旧按 env 放行的旋钮，
比没有这个旋钮更糟——运营会以为已经止血。每个键下面的 `read_by` 就是读取点，
新增键时必须一起填，并配一个「改了设置后行为真的变了」的测试，
断言写入返回 200 不算数。

已有这类行为断言的键（tests/test_admin.py）：
    quota_enabled  → TestSettingsOverride::test_live_override_reaches_quota_service_without_restart
    key_mode       → TestPlatformServerKey::test_key_mode_override_takes_effect_live
**尚缺行为断言**（本轮新接线，只验证了写入校验，没验证运行时行为改变）：
    quota_free_reviews_per_day / quota_free_cost_usd_per_day / ratelimit_per_minute /
    ratelimit_review_per_hour / review_concurrency
读取点见各键的 `read_by`，接线是真的（可 grep 确认），但"改了就生效"这句话
目前靠代码审阅而不是靠测试保证——补测试之前别把它当成已验证的承诺。
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest
from app.models import PlatformSetting

# 键 -> (类型转换函数, 面板标签, 取值范围校验, 运行时读取点)
ADJUSTABLE: Dict[str, dict] = {
    "quota_enabled": {
        "cast": bool,
        "label": "配额开关",
        "read_by": "quota_service._quota_enabled",
    },
    "quota_mode": {
        "cast": str,
        "label": "配额模式（plan=套餐日限 / credits=纯CDK次数制，用完即止）",
        "choices": ("plan", "credits"),
        "read_by": "quota_service.check_quota / usage_summary",
    },
    "quota_free_reviews_per_day": {
        "cast": int,
        "label": "免费档每日评审次数上限",
        "min": 0,
        "read_by": "plan_service._free_plan → quota_service.check_quota",
    },
    "quota_free_cost_usd_per_day": {
        "cast": float,
        "label": "免费档每日成本上限（美元）",
        "min": 0,
        "read_by": "plan_service._free_plan → quota_service.check_quota",
    },
    "ratelimit_enabled": {
        "cast": bool,
        "label": "限流开关",
        "read_by": "deps.rate_limit",
    },
    "ratelimit_per_minute": {
        "cast": int,
        "label": "通用接口限流（次/分钟，不含发起评审）",
        "min": 1,
        "read_by": "deps.resolve_rate_limit（默认档）",
    },
    "ratelimit_review_per_hour": {
        "cast": int,
        "label": "发起评审限流（次/小时/用户）",
        "min": 1,
        "read_by": "deps.resolve_rate_limit（scope=review）",
    },
    "key_mode": {
        "cast": str,
        "label": "Key 解析模式",
        "choices": ("byok", "managed", "hybrid"),
        "read_by": "key_service.resolve_key",
    },
    "review_concurrency": {
        "cast": int,
        "label": "单次评审人格并发度",
        "min": 1,
        "max": 32,
        "read_by": "review_service._execute_review",
    },
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
            # 运行时读取点：面板可以显示，也方便排障时直接 grep 确认这不是假旋钮
            "read_by": spec.get("read_by"),
        })
    return out
