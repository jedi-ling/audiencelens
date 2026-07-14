"""集中配置：所有链路的开关都在这里。

设计原则：每条"预埋线"都有一个开关 + 一个可用的默认实现。
默认配置 = 单机开源形态（匿名、BYOK、无配额、内存队列），
改几个环境变量即可切到托管 SaaS 形态（登录、服务端 key、配额计费、外部队列）。
"""

import os
from functools import lru_cache


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Settings:
    """从环境变量读取；不依赖 pydantic-settings，减少依赖面。"""

    def __init__(self) -> None:
        base = os.path.dirname(os.path.abspath(__file__))
        self.backend_dir = os.path.dirname(base)
        self.repo_root = os.path.dirname(os.path.dirname(self.backend_dir))

        # ---- 基础 ----
        self.env: str = os.environ.get("AL_ENV", "development")
        self.debug: bool = _bool("AL_DEBUG", self.env != "production")
        self.cors_origins: list = [
            o.strip()
            for o in os.environ.get(
                "AL_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
            ).split(",")
            if o.strip()
        ]

        # ---- 数据库 ----
        default_db = os.path.join(self.backend_dir, "data", "reviews.db")
        self.database_url: str = os.environ.get(
            "AL_DATABASE_URL", f"sqlite:///{default_db}"
        )

        # ---- 身份 / 认证（埋线：默认匿名，打开后走 JWT）----
        # False: 所有请求归入匿名身份，无需登录（开源单机形态）
        # True : 需要 Bearer token，注册/登录接口生效（托管形态）
        self.auth_enabled: bool = _bool("AL_AUTH_ENABLED", False)
        self.jwt_secret: str = os.environ.get("AL_JWT_SECRET", "dev-insecure-secret-change-me")
        self.jwt_ttl_seconds: int = _int("AL_JWT_TTL_SECONDS", 7 * 24 * 3600)
        self.anonymous_user_id: str = "anonymous"

        # ---- LLM key 解析策略（埋线：BYOK vs 托管）----
        # "byok"    : 只用用户自带 key（服务端不垫钱）
        # "managed" : 只用服务端 key（你垫钱，必须配合配额/计费）
        # "hybrid"  : 用户有 key 用用户的，否则回落服务端 key
        self.key_mode: str = os.environ.get("AL_KEY_MODE", "byok").lower()
        self.server_llm_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

        # ---- 配额 / 计费（埋线：默认关闭，打开即生效）----
        self.quota_enabled: bool = _bool("AL_QUOTA_ENABLED", False)
        self.quota_free_reviews_per_day: int = _int("AL_QUOTA_FREE_REVIEWS_PER_DAY", 5)
        self.quota_free_cost_usd_per_day: float = float(
            os.environ.get("AL_QUOTA_FREE_COST_USD_PER_DAY", "1.0")
        )

        # ---- 限流（埋线：内存令牌桶，可换 Redis）----
        self.ratelimit_enabled: bool = _bool("AL_RATELIMIT_ENABLED", True)
        self.ratelimit_per_minute: int = _int("AL_RATELIMIT_PER_MINUTE", 60)
        self.ratelimit_review_per_hour: int = _int("AL_RATELIMIT_REVIEW_PER_HOUR", 20)

        # ---- 任务队列（埋线：内存线程池，可换 Celery/RQ）----
        # "inprocess" : 进程内线程池（单机够用）
        # "external"  : 外部队列（需实现 JobBackend，见 services/job_service.py）
        self.queue_backend: str = os.environ.get("AL_QUEUE_BACKEND", "inprocess").lower()
        self.queue_workers: int = _int("AL_QUEUE_WORKERS", 2)
        # 单次评审内部的人格并发度（透传给 runner.run_panel）
        self.review_concurrency: int = _int("AUDIENCELENS_MAX_CONCURRENCY", 6)

        # ---- 上传 ----
        self.upload_dir: str = os.environ.get(
            "AL_UPLOAD_DIR", os.path.join(self.backend_dir, "data", "uploads")
        )
        self.upload_max_bytes: int = _int("AL_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
        self.upload_allowed_ext: set = {
            e.strip().lower()
            for e in os.environ.get(
                "AL_UPLOAD_ALLOWED_EXT", ".txt,.md,.json,.yaml,.yml"
            ).split(",")
            if e.strip()
        }

        # ---- 意图解析（埋线：无 key 时降级为启发式规则）----
        self.intent_llm_enabled: bool = _bool("AL_INTENT_LLM_ENABLED", True)
        self.intent_model: str = os.environ.get("AL_INTENT_MODEL", "claude-haiku-4-5-20251001")

        # ---- 判断复利闭环（埋线：默认开，记录预测供日后回填验证）----
        self.ledger_enabled: bool = _bool("AL_LEDGER_ENABLED", True)

    # 便捷判断
    @property
    def is_managed(self) -> bool:
        return self.key_mode in ("managed", "hybrid")

    def sanitized(self) -> dict:
        """给 /health 用：绝不泄露密钥。"""
        return {
            "env": self.env,
            "auth_enabled": self.auth_enabled,
            "key_mode": self.key_mode,
            "server_key_present": bool(self.server_llm_key),
            "quota_enabled": self.quota_enabled,
            "ratelimit_enabled": self.ratelimit_enabled,
            "queue_backend": self.queue_backend,
            "ledger_enabled": self.ledger_enabled,
            "review_concurrency": self.review_concurrency,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
