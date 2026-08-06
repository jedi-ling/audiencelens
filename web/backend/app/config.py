"""集中配置：所有链路的开关都在这里。

设计原则：每条"预埋线"都有一个开关 + 一个可用的默认实现。
默认配置 = 单机开源形态（匿名、BYOK、无配额、内存队列），
改几个环境变量即可切到托管 SaaS 形态（登录、服务端 key、配额计费、外部队列）。

启动自检（见 Settings._validate_startup）：
默认值是为「本机单人开发」调的，直接拿去对公网提供服务就是裸奔。
所以这里有一组「看起来像生产就拒绝启动 / 大声告警」的检查。
判据不是 AL_ENV 一个字段——最危险的情况恰恰是照着 DEPLOY.md 部署却忘了
`cp .env.production.example .env`：AL_ENV 还是 development，服务已经在公网上跑。
所以只要 CORS 白名单或站点地址指向公网主机，就按生产对待；
回环 / RFC1918 私网 / .local 一律不算，局域网里的本地开发不会被误伤。
"""

import ipaddress
import logging
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

_log = logging.getLogger("audiencelens")


def _load_dotenv_once() -> None:
    """本地开发时加载 web/.env。

    为什么需要这个：`web/.env.production.example` 是一份写得很详细的模板，
    DEPLOY.md 也让人照着填 `web/.env`——但那条路径只在 Docker 下成立
    （docker-compose 用 env_file 注入）。直接 `uvicorn app.main:app` 跑的时候，
    下面所有配置读的都是 os.environ，**根本不看那个文件**。

    结果就是一个典型的"看起来能用其实不读"：文件在、注释齐、填了没反应，
    而且不报错——只能靠"为什么改了没生效"一路查到这里。
    （更糟的变体：为了让本地能跑，把密钥塞进 .claude/launch.json 这类会进
    版本库的文件——本仓库真发生过一次，差点把 SMTP 密钥提交上去。）

    规则：**已存在的环境变量优先**。.env 只补空缺，不覆盖显式设置的值，
    这样 CI、Docker、临时 `VAR=x python ...` 的行为一律不变。
    """
    if os.environ.get("AL_SKIP_DOTENV"):
        return
    # config.py 在 web/backend/app/ 下，.env 约定在 web/ 下
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    loaded = 0
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue  # 显式设置的环境变量永远赢
            os.environ[key] = value.strip().strip('"').strip("'")
            loaded += 1
    except OSError as exc:  # 权限/编码问题不该让服务起不来
        _log.warning("读取 %s 失败，已跳过：%s", env_path, exc)
        return
    if loaded:
        # 只报数量不报键名——键名里有 AL_SMTP_PASSWORD 这类，日志不该暗示它们的存在
        _log.info("已从 %s 加载 %d 项配置（不覆盖已有环境变量）", env_path, loaded)


_load_dotenv_once()

# 开发默认 JWT 密钥。它同时是落库加密密钥的回落值——泄露 = 所有已存 API key 可解。
DEV_JWT_SECRET = "dev-insecure-secret-change-me"
# 后台令牌是静态共享密钥、无有效期，长度就是它唯一的强度来源。
ADMIN_TOKEN_MIN_LENGTH = 16


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


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _is_public_host(raw: str) -> bool:
    """origin / URL 是否指向公网可达的主机。

    解析不出主机名时按「公网」处理：`.env` 里留着 `https://你的域名.com`
    这种占位符正是最该被拦下的情况，不该因为解析失败而放行。
    """
    raw = (raw or "").strip()
    if not raw:
        return False
    host = (urlparse(raw if "://" in raw else "//" + raw).hostname or "").lower()
    if not host:
        return True
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test")):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True  # 是个域名 → 当作公网
    return not (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified)


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
        # 用 `or` 而不是 get(name, default)：docker-compose 里 `${AL_DATABASE_URL:-}`
        # 会把变量设成空字符串（"已设置但为空"），此时 get() 拿到的是 ""，
        # create_engine("") 直接抛异常。空值一律等同未设置。
        default_db = os.path.join(self.backend_dir, "data", "reviews.db")
        self.database_url: str = (
            os.environ.get("AL_DATABASE_URL", "").strip() or f"sqlite:///{default_db}"
        )

        # ---- 身份 / 认证（埋线：默认匿名，打开后走 JWT）----
        # False: 所有请求归入匿名身份，无需登录（开源单机形态）
        # True : 需要 Bearer token，注册/登录接口生效（托管形态）
        self.auth_enabled: bool = _bool("AL_AUTH_ENABLED", False)
        self.jwt_secret: str = os.environ.get("AL_JWT_SECRET", DEV_JWT_SECRET)
        self.jwt_ttl_seconds: int = _int("AL_JWT_TTL_SECONDS", 7 * 24 * 3600)
        self.anonymous_user_id: str = "anonymous"
        # BYOK/平台 key 落库加密的密钥，与 JWT 签名密钥分离——
        # 轮换 JWT 密钥只会踢掉登录态，不该让所有已存的 API key 变成解不开的密文。
        # 未设置时回落 jwt_secret（兼容存量数据：旧密文都是用 jwt_secret 加密的）。
        self.encryption_key: str = os.environ.get("AL_ENCRYPTION_KEY") or self.jwt_secret

        # ---- LLM key 解析策略（埋线：BYOK vs 托管）----
        # "byok"    : 只用用户自带 key（服务端不垫钱）
        # "managed" : 只用服务端 key（你垫钱，必须配合配额/计费）
        # "hybrid"  : 用户有 key 用用户的，否则回落服务端 key
        self.key_mode: str = (os.environ.get("AL_KEY_MODE", "").strip() or "byok").lower()
        self.server_llm_key: str = os.environ.get("ANTHROPIC_API_KEY", "").strip()

        # ---- 配额 / 计费（埋线：默认关闭，打开即生效）----
        self.quota_enabled: bool = _bool("AL_QUOTA_ENABLED", False)
        # plan   = 按套餐日限额（免费档每天 N 次，CDK 次数在日限用完后垫）
        # credits = 纯次数制：每次服务端 key 评审消耗 1 次 CDK 余额，用完即止，无每日刷新
        #           ——"一个码 10 次，用完就没了"，适合 CDK 发码运营
        self.quota_mode: str = os.environ.get("AL_QUOTA_MODE", "plan").lower()
        # 这两项是平台垫付的止血阀：后台面板可实时覆盖（见 admin_settings_service），
        # 真正的读取点是 plan_service._free_plan(db)。
        self.quota_free_reviews_per_day: int = _int("AL_QUOTA_FREE_REVIEWS_PER_DAY", 5)
        self.quota_free_cost_usd_per_day: float = _float("AL_QUOTA_FREE_COST_USD_PER_DAY", 1.0)
        # 每个用户**累计**（非每日）能烧掉的平台 token 上限，0 = 不限制。
        # 这是钱包的最后一道闸，和次数/成本那两道的性质不同：
        #   · 次数闸管"一天能发几次"，跨天就重置，拦不住长期消耗；
        #   · 成本闸同样按 24h 窗口滚动，同理；
        #   · 这一条不滚动、不重置，是一个用户在这个实例上的**终身**试用额度。
        # 只统计 key_source="server" 的消耗——BYOK 花的是用户自己的钱，与我方无关。
        # 注意它拦不住"单次评审内部超支"：token 用量要等评审跑完才知道，人格又是
        # 并发发出去的，跑到一半刹不住车。它保证的是"下一次还能不能开始"，
        # 不是"这一次不会超"。真正的硬约束仍然是发出去多少 CDK 次数。
        self.quota_tokens_total: int = _int("AL_QUOTA_TOKENS_TOTAL", 0)
        # 发起一次评审时，先按这个数字给终身额度**占位**，评审结束用真实用量顶掉。
        # 存在的理由是终身闸本来是 check-then-use：查用量与真正烧 token 之间没有
        # 任何写入，8 个并发请求实测全部读到"没超"、8/8 全放行，超额可达一个数量级。
        # 占位让并发请求彼此可见：第 N 个请求看到的是"已用 + 前 N-1 个的占位"。
        # 精度不是重点（真实用量差异很大），量级对就够——它把超额从"并发数 ×
        # 单次用量"压到"一次评审的估算误差"。设 0 = 关闭占位，退回旧的 check-then-use。
        self.quota_tokens_per_review_estimate: int = _int(
            "AL_QUOTA_TOKENS_PER_REVIEW_ESTIMATE", 150_000
        )

        # ---- 高级技能的免费体验次数 ----
        # 每个账号能免费用几次高级技能（用平台垫付 key 时）。用完**不报错**，
        # 静默降级成普通评审——报告照出，只是少了那一层。理由：新用户往往还没
        # 建立价值感就撞墙，转化反而更差；"你已经见过好东西了"比"此路不通"有效。
        # 0 = 该技能对免费用户完全关闭；负数 = 不限制。
        self.skill_free_uses: int = _int("AL_SKILL_FREE_USES", 3)
        # 哪些技能算"高级"。默认只有红队：它是唯一真正多花钱的那层（在人格
        # 评审之后额外跑一轮对抗质询），而受众面板是本产品的核心价值，
        # 把它设成收费等于把产品本身关掉。逗号分隔，取值见 models.SkillType。
        self.premium_skills: set = {
            s.strip()
            for s in os.environ.get("AL_PREMIUM_SKILLS", "red_team_audience").split(",")
            if s.strip()
        }

        # 未验证邮箱的账号，服务端 key 每日次数上限（软拦：能用，但只够试一次）。
        # 在此之前 email_verified_at 只是一条记录，登录/评审/配额一处都不读它——
        # 激活与不激活完全没区别，等于验证邮件白发。这一项是它唯一的抓手。
        # 只压次数、不挡登录，也不影响 BYOK（用户自己的钱没理由限制）和 CDK
        # 次数（那是花钱换来的）。设为负数即关闭本机制。
        self.quota_unverified_reviews_per_day: int = _int(
            "AL_QUOTA_UNVERIFIED_REVIEWS_PER_DAY", 1
        )

        # ---- 限流（埋线：内存令牌桶，可换 Redis）----
        # 两个旋钮各管各的：per_minute 管普通接口，review_per_hour 只管发起评审
        # （评审直接烧平台垫付的钱，必须能单独收紧）。解析逻辑见 deps.rate_limit。
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

        # ---- 邮件（埋线：默认 console，不真发信也能跑通验证/找回链路）----
        # console 档日志里只留脱敏正文，完整邮件写到 mail_outbox_dir 下的 0600 文件
        # （见 mail_service._write_outbox）—— 用户仍然拿不到可用链接，
        # 所以类生产 + 开了账号体系时启动自检会拦下。
        self.mail_backend: str = (os.environ.get("AL_MAIL_BACKEND", "").strip() or "console").lower()
        self.mail_from: str = (
            os.environ.get("AL_MAIL_FROM", "").strip() or "AudienceLens <noreply@localhost>"
        )
        self.smtp_host: str = os.environ.get("AL_SMTP_HOST", "").strip()
        self.smtp_port: int = _int("AL_SMTP_PORT", 587)
        self.smtp_user: str = os.environ.get("AL_SMTP_USER", "")
        self.smtp_password: str = os.environ.get("AL_SMTP_PASSWORD", "")
        self.smtp_use_ssl: bool = _bool("AL_SMTP_USE_SSL", False)
        # 不设超时 = 用 socket 的全局默认值（通常等于永不超时），
        # 一台连不上的 SMTP 主机就能把发起注册的那个工作线程永久挂住。
        self.smtp_timeout_seconds: float = _float("AL_SMTP_TIMEOUT_SECONDS", 15.0)
        # console 档的本地投递目录。默认在 backend/data 下——该目录已被
        # web/backend/.gitignore 覆盖，不会有令牌被 git add 进历史。
        self.mail_outbox_dir: str = (
            os.environ.get("AL_MAIL_OUTBOX_DIR", "").strip()
            or os.path.join(self.backend_dir, "data", "outbox")
        )
        # 邮件里链接的落点（前端地址）——本地开发默认 vite 端口
        self.public_web_url: str = (
            os.environ.get("AL_PUBLIC_WEB_URL", "").strip() or "http://localhost:5199"
        )
        self.email_token_ttl_seconds: int = _int("AL_EMAIL_TOKEN_TTL_SECONDS", 24 * 3600)
        self.reset_token_ttl_seconds: int = _int("AL_RESET_TOKEN_TTL_SECONDS", 3600)

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
        # 图片走独立白名单：不进 upload_allowed_ext（那个是"抽取成文字材料"的格式），
        # 图片是原样转 data URI 塞进多模态请求，见 src/runner/llm_client.py
        self.upload_allowed_image_ext: set = {
            e.strip().lower()
            for e in os.environ.get(
                "AL_UPLOAD_ALLOWED_IMAGE_EXT", ".png,.jpg,.jpeg,.webp,.gif"
            ).split(",")
            if e.strip()
        }
        self.upload_max_image_bytes: int = _int("AL_UPLOAD_MAX_IMAGE_BYTES", 8 * 1024 * 1024)

        # ---- 意图解析（埋线：无 key 时降级为启发式规则）----
        self.intent_llm_enabled: bool = _bool("AL_INTENT_LLM_ENABLED", True)
        self.intent_model: str = os.environ.get("AL_INTENT_MODEL", "claude-haiku-4-5-20251001")

        # ---- 判断复利闭环（埋线：默认开，记录预测供日后回填验证）----
        self.ledger_enabled: bool = _bool("AL_LEDGER_ENABLED", True)

        # ---- 后台管理面板（埋线：默认关闭，设置 token 才启用）----
        # 未设置时 /api/admin/* 全部返回 503——安全默认值，绝不无密钥暴露管理接口。
        self.admin_token: str = os.environ.get("AL_ADMIN_TOKEN", "")

        # ---- 危险默认值的逃生舱（必须显式打开，且只在类生产环境下才有意义）----
        # 留逃生舱而不是一刀切：单人自建、内网试跑这类场景确实可能就是要这么跑，
        # 但必须是一次「明知故犯」的动作，而不是忘了配置的默认结果。
        self.allow_shared_anonymous: bool = _bool("AL_ALLOW_SHARED_ANONYMOUS", False)
        self.allow_console_mail: bool = _bool("AL_ALLOW_CONSOLE_MAIL", False)

        # ---- 启动自检 ----
        self.startup_warnings: list = []
        self._validate_startup()

    # 便捷判断
    @property
    def is_managed(self) -> bool:
        return self.key_mode in ("managed", "hybrid")

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_token)

    @property
    def looks_like_production(self) -> bool:
        """「看起来像生产」：显式声明，或已经在对公网主机提供服务。

        只看 AL_ENV 是不够的——docker-compose 曾把它默认成 development，
        于是所有生产检查永远不触发，忘了配 .env 也能正常起来、健康检查还通过。
        """
        if self.env == "production":
            return True
        if any(_is_public_host(o) for o in self.cors_origins):
            return True
        return _is_public_host(self.public_web_url)

    # ---------------------------- 启动自检 ----------------------------

    def _validate_startup(self) -> None:
        """拒绝启动 / 大声告警。拒绝启动的每一条都给出可执行的修复动作。"""
        # 后台令牌强度：与是不是生产无关——静态共享密钥、无有效期、无失败上限，
        # 长度是它唯一的强度来源；非 ASCII 还会让 hmac 比较抛 TypeError（每请求 500）。
        self._validate_admin_token()

        if not self.looks_like_production:
            return

        # 类生产环境下没显式设 AL_DEBUG 就关掉 debug：
        # debug=True 会把异常类型和消息回给调用方（见 core/errors.py）。
        if os.environ.get("AL_DEBUG") is None:
            self.debug = False

        if self.jwt_secret == DEV_JWT_SECRET:
            raise RuntimeError(
                "检测到类生产环境（AL_ENV=production 或 CORS/站点地址指向公网），"
                "但 AL_JWT_SECRET 仍是开发默认值。该密钥同时用于签发登录态和加密落库的 "
                "API Key，泄露即等于所有用户的 key 全部可解。"
                "请先生成强随机密钥：openssl rand -hex 32"
            )

        if not self.auth_enabled and not self.allow_shared_anonymous:
            raise RuntimeError(
                "检测到类生产环境，但 AL_AUTH_ENABLED=false。"
                "关闭认证时所有请求共用同一个 anonymous 身份——访客能看到彼此的评审、"
                "彼此的用量和彼此填的 API Key。"
                "对公网提供服务请设 AL_AUTH_ENABLED=true；"
                "若确认是单人自用且接受共享身份，显式设 AL_ALLOW_SHARED_ANONYMOUS=true。"
            )

        if self.mail_backend == "smtp" and not self.smtp_host:
            raise RuntimeError(
                "AL_MAIL_BACKEND=smtp 但未配置 AL_SMTP_HOST。"
                "此时 mail_service 会回落到 console 发送器——"
                "用户收不到验证/重置邮件，令牌只会落到服务器本地的 outbox 文件。"
                "请补齐 SMTP 配置（填法见 web/DEPLOY.md 的「邮件发送」一节）。"
            )

        if self.mail_backend != "smtp" and self.auth_enabled and not self.allow_console_mail:
            raise RuntimeError(
                "检测到类生产环境且已开启账号体系（AL_AUTH_ENABLED=true），"
                f"但邮件后端是 {self.mail_backend!r}（非 smtp）。"
                "此时邮箱验证和密码重置邮件不会真的发出，用户无法完成注册与找回；"
                "含令牌的完整邮件会落到服务器磁盘上的 outbox 文件，能读该文件的人"
                "即可接管任意账号。"
                "请配置 AL_MAIL_BACKEND=smtp 与 AL_SMTP_HOST（填法见 web/DEPLOY.md 的"
                "「邮件发送」一节）；若确认暂不需要邮件链路，显式设 AL_ALLOW_CONSOLE_MAIL=true。"
            )

        # ---- 以下只告警，不拦启动 ----

        # 邮件配置的三类"配了但发不出去"。都只告警：真假要靠后台
        # 「发送测试邮件」当场打一次才算数，启动期猜不出服务商的脾气。
        if self.mail_backend == "smtp" and self.smtp_host:
            if self.mail_from.endswith("localhost>") or "@localhost" in self.mail_from:
                self._warn(
                    f"AL_MAIL_FROM 仍是默认值 {self.mail_from!r}。"
                    "几乎所有服务商都会拒收 @localhost 的发件人（SMTPSenderRefused）。"
                    "请改成 AL_SMTP_USER 对应的那个邮箱地址。"
                )
            if self.smtp_port == 465 and not self.smtp_use_ssl:
                self._warn(
                    "AL_SMTP_PORT=465 但 AL_SMTP_USE_SSL=false。465 是隐式 SSL 端口，"
                    "用 STARTTLS 连它通常会超时或被中断。请设 AL_SMTP_USE_SSL=true。"
                )
            if self.smtp_port in (25, 587) and self.smtp_use_ssl:
                self._warn(
                    f"AL_SMTP_PORT={self.smtp_port} 但 AL_SMTP_USE_SSL=true。"
                    f"{self.smtp_port} 是 STARTTLS 端口，用隐式 SSL 连它会 TLS 握手失败。"
                    "请设 AL_SMTP_USE_SSL=false，或改用 465 端口。"
                )
            if not _is_public_host(self.public_web_url):
                self._warn(
                    f"邮件能发出，但链接指向 AL_PUBLIC_WEB_URL={self.public_web_url!r}——"
                    "这不是一个公网地址，用户点开验证/重置链接会打不开。"
                    "请设成用户实际访问的站点地址，例如 https://你的域名。"
                )
        if not os.environ.get("AL_ENCRYPTION_KEY"):
            self._warn(
                "未设置 AL_ENCRYPTION_KEY，落库加密密钥回落到 AL_JWT_SECRET。"
                "此后轮换 JWT 密钥会让所有已存的 API Key 解不开。建议现在就分开设置。"
            )

        if self.env != "production":
            self._warn(
                f"AL_ENV={self.env!r} 但服务已对公网主机提供服务"
                f"（CORS={self.cors_origins}，站点={self.public_web_url}）。"
                "请显式设 AL_ENV=production。"
            )

        if self.is_managed and self.server_llm_key and not self.quota_enabled:
            self._warn(
                f"AL_KEY_MODE={self.key_mode} 且已配置平台垫付 key，但 AL_QUOTA_ENABLED=false——"
                "任何人都能无限量地花你的钱。上线前请开启配额。"
            )

        if self.allow_shared_anonymous and not self.auth_enabled:
            self._warn(
                "AL_ALLOW_SHARED_ANONYMOUS=true：所有访客共用 anonymous 身份，"
                "彼此可见对方的评审与用量。仅当此实例是单人自用时才应如此。"
            )

        if self.allow_console_mail and self.mail_backend != "smtp":
            self._warn(
                "AL_ALLOW_CONSOLE_MAIL=true：验证/重置邮件不会真的发出——用户注册后"
                "激活不了、忘记密码找不回。含令牌的完整邮件会写到 "
                f"{self.mail_outbox_dir}（0600 文件），请确保该目录的访问权限等同于账号权限。"
            )

    def _validate_admin_token(self) -> None:
        token = self.admin_token
        if not token:
            return
        if any(not (33 <= ord(c) <= 126) for c in token):
            raise RuntimeError(
                "AL_ADMIN_TOKEN 含空白字符或非 ASCII 可见字符。"
                "该令牌走 HTTP 头传输并用 hmac 恒定时间比较，非 ASCII 会让每个后台请求 500。"
                "请改用 ASCII 可见字符，例如 openssl rand -hex 32 的输出。"
            )
        if len(token) < ADMIN_TOKEN_MIN_LENGTH:
            raise RuntimeError(
                f"AL_ADMIN_TOKEN 太短（{len(token)} 字符，至少 {ADMIN_TOKEN_MIN_LENGTH}）。"
                "它是后台的唯一凭据，静态、无有效期，长度就是全部强度。"
                "请用 openssl rand -hex 32 生成。"
            )

    def _warn(self, message: str) -> None:
        """记录并立刻打印。

        启动自检发生在 import 期，早于 core.logging.setup_logging 装 handler；
        WARNING 级别会走 logging 的 lastResort handler 直接落到 stderr，
        所以 docker compose logs 里一定看得见。
        """
        self.startup_warnings.append(message)
        _log.warning("[启动自检] %s", message)

    def sanitized(self) -> dict:
        """给 /health 用：绝不泄露密钥。

        不含 admin_enabled——那等于向公网广播「这里有后台管理接口」，
        而后台是静态共享令牌，没必要主动告诉扫描器它存在。
        """
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
