import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List as TypingList

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class SkillType(str, Enum):
    SYNTHETIC_PLAYTEST = "synthetic_playtest"
    AUDIENCE_PANEL = "audience_panel"
    RED_TEAM_AUDIENCE = "red_team_audience"
    PERSONA_GENERATE = "persona_generate"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 归属：匿名形态下为 "anonymous"；开启认证后为真实 user id
    user_id = Column(String, index=True, nullable=True, default="anonymous")
    task_type = Column(String, nullable=False)
    target_title = Column(String, nullable=True)
    artifact_bundle = Column(JSON, nullable=False)
    persona_pack = Column(String, nullable=True)
    selected_personas = Column(JSON, nullable=True)
    # 附加技能标签（见 SkillType）——影响评审 prompt 的取向，不影响流程本身
    skill_type = Column(String, nullable=True)
    # 红队叠加。与 skill_type 独立（选了受众面板也能再叠红队），此前**只作用到
    # prompt、不落库**——于是"这次评审用没用红队"事后完全查不到，既做不了
    # 按技能计次，也做不了成本归因。而红队恰恰是最贵的那一层（多跑一轮质询）。
    enable_red_team = Column(Boolean, default=False, nullable=False)
    # 这次评审花的是谁的钱：byok = 用户自己的 key，server = 平台垫付。
    # 加这一列是因为所有"免费额度"类的规则都必须豁免 BYOK（花自己的钱没理由限制），
    # 而此前 Review 上没有任何字段能回答这个问题——只有 UsageRecord 有，
    # 但那是评审**结束后**才写的，在途的评审查不到。
    key_source = Column(String, nullable=True)
    # 长期评审项目的分组键：同 project_key 的历次评审在前端聚合成一条时间线。
    # 不建独立 Project 表——纯字符串分组，用户改名即视为新项目，足够轻量。
    project_key = Column(String, index=True, nullable=True)
    # 评审完成后自动运行质量评估（8 维评分）——Wizard"启用评估"开关的落点。
    # 此前该开关从 UI 传到后端被 schema 静默丢弃，从来没有生效过。
    enable_evaluation = Column(Boolean, default=False, nullable=False)
    mode = Column(String, default="standard", nullable=False)
    status = Column(String, default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    total_cost_usd = Column(Float, default=0.0, nullable=False)
    # 本次评审真实消耗的 token（各人格 + 交叉质证的 input/output 之和）
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    report_json = Column(JSON, nullable=True)
    report_markdown = Column(Text, nullable=True)
    calibration = Column(JSON, nullable=True)

    persona_outputs = relationship("PersonaOutput", back_populates="review", cascade="all, delete-orphan")
    chat_messages = relationship("ReviewChatMessage", back_populates="review", cascade="all, delete-orphan")
    evaluation_results = relationship("EvaluationResult", back_populates="review", cascade="all, delete-orphan")
    # 评分卡也是派生内容，必须跟着评审走。它此前没有任何 relationship，
    # 于是删评审时被漏下——见 EvaluationScorecard 的说明。
    evaluation_scorecard = relationship(
        "EvaluationScorecard", back_populates="review", uselist=False, cascade="all, delete-orphan"
    )
    judgments = relationship("Judgment", back_populates="review", cascade="all, delete-orphan")
    feedback = relationship("ReviewFeedback", back_populates="review", uselist=False, cascade="all, delete-orphan")
    # 伦理报告含用户内容摘录，必须随评审一起删——删号走的就是删 Review 这条路
    ethics_reports = relationship("EthicsReport", back_populates="review", cascade="all, delete-orphan")


class PersonaOutput(Base):
    __tablename__ = "persona_outputs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey("reviews.id"), nullable=False)
    persona_id = Column(String, nullable=False)
    persona_name = Column(String, nullable=True)
    status = Column(String, default="pending", nullable=False)
    output_json = Column(JSON, nullable=True)
    validation_result = Column(JSON, nullable=True)
    cost_usd = Column(Float, default=0.0, nullable=False)
    # 该人格本次评审的真实 token 消耗（v1 引擎逐人格记；v2 只汇总到 Review 级）
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    review = relationship("Review", back_populates="persona_outputs")


class ReviewChatMessage(Base):
    """报告出来后的真对话：追问报告结论、或点名某个人格继续聊。

    persona_id=None 是"跟评审团整体聊"（针对报告结论追问）；
    非空则是"跟某个具体人格聊"，回复要用该人格的 identity_summary/
    behavior_profile/communication_style 保持人设一致，而不是通用助手腔。
    同一条 review 下，两种 thread 各自独立维护上下文（按 persona_id 分组）。
    """

    __tablename__ = "review_chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey("reviews.id"), nullable=False)
    persona_id = Column(String, nullable=True)
    role = Column(String, nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    review = relationship("Review", back_populates="chat_messages")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey("reviews.id"), nullable=False)
    dimension = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    passed = Column(Boolean, nullable=False, default=False)
    details = Column(Text, nullable=True, default="")
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    review = relationship("Review", back_populates="evaluation_results")


class EvaluationScorecard(Base):
    """评审的质量评分卡（由 evaluation_service 从报告算出，属于派生内容）。

    这张表以前是删除路径上的一个哑弹：review_id 是真外键，却既没有 ondelete、
    Review 上也没有 relationship，于是没有任何一条路径会清理它。SQLite 默认
    不校验外键，所以"删评审/删账号"在本机永远看着正常；PostgreSQL（部署文档
    指定的生产库）上同一句删除会因外键约束直接 500。
    它是派生内容不是财务事实，所以正确做法是随评审删除——两侧都声明：
    relationship 保证 ORM 删除路径清理干净（老库建表时没有 ondelete 子句），
    ondelete 保证绕过 ORM 的裸 SQL 删除也不留孤儿。
    """

    __tablename__ = "evaluation_scorecards"

    review_id = Column(
        String, ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True
    )
    overall_score = Column(Integer, nullable=False, default=0)
    passed = Column(Boolean, nullable=False, default=False)
    results_json = Column(JSON, nullable=True)
    critical_failures_json = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    review = relationship("Review", back_populates="evaluation_scorecard")


class EthicsReport(Base):
    """某次评审中某个人格输出的伦理体检结果。

    violations_json 里含用户内容的摘录，所以这张表必须是可归属、可删除的：
    没有 review_id 的行既查不回来也删不掉，会永久滞留在库里，与隐私政策
    「删号即物理删除评审内容」的承诺直接冲突。

    为什么只挂 review_id 而不再冗余一个 user_id：归属的唯一事实源是
    Review.user_id。再存一份 user_id 就有了第二个来源，两边一旦不同步
    （改归属、匿名转注册）就会出现"删了人还留着他的摘录"这种最坏情况。
    删除靠 Review 的 cascade 走，天然与评审归属保持一致。
    """

    __tablename__ = "ethics_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 老库里存在一批 review_id 为空的孤儿行（见 db.py 的迁移说明），
    # 因此列本身可空；新写入一律必须带 review_id（见 ethics_service）
    review_id = Column(String, ForeignKey("reviews.id"), index=True, nullable=True)
    persona_id = Column(String, nullable=False)
    passed = Column(Boolean, nullable=False, default=False)
    score = Column(Integer, nullable=False, default=0)
    violations_json = Column(JSON, nullable=True, default=list)
    stereotype_risk = Column(String, nullable=True, default="low")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    review = relationship("Review", back_populates="ethics_reports")


# ============================================================================
# 以下为「预埋线」模型：默认形态下大多不写入，但表结构与关系已就位，
# 打开对应开关（见 app/config.py）即可启用，无需再动 schema。
# ============================================================================


class User(Base):
    """身份（埋线：AL_AUTH_ENABLED=false 时不使用，所有数据归 anonymous）。"""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    plan = Column(String, default="free", nullable=False)  # free | pro | ...（计费用）
    is_active = Column(Boolean, default=True, nullable=False)
    # 游客身份：CDK 免登录兑换时自动签发（合成邮箱 + 不可登录的随机口令）。
    # 是真实 User 行——配额/key/评审归属全部复用既有逻辑，只是没有可登录的凭据。
    is_guest = Column(Boolean, default=False, nullable=False)
    # 邮箱是否已验证。注册即可用（不挡住上手），但未验证的账号会被提示去验证——
    # 否则用户填错邮箱自己不知道，等到要找回密码时才发现联系不上，为时已晚。
    email_verified_at = Column(DateTime, nullable=True)
    # 该用户单独的终身 token 上限；NULL = 用全局 AL_QUOTA_TOKENS_TOTAL。
    # 存 NULL 而不是存全局默认值的副本：后者会让"改了全局配置、老用户不跟随"
    # 变成一个静默的惊喜，而运营者以为自己改的是所有人。
    token_quota_total = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    api_keys = relationship("UserApiKey", back_populates="user", cascade="all, delete-orphan")


class AuthToken(Base):
    """邮箱验证 / 密码重置的一次性令牌。

    只存令牌的 SHA-256 摘要，不存原文——库被看一眼也无法拿它去重置别人的
    密码（与口令哈希同一个道理：能验证，但反推不出来）。
    """

    __tablename__ = "auth_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # ondelete CASCADE 是兜底：删号的正路是 user_data_service 显式删掉这些行
    # （令牌本身能重置密码，"账号立即物理删除"必须包含它）。但只要有任何一条
    # 路径漏了，PostgreSQL 上删 users 行就会因外键约束 500——SQLite 默认不校验
    # 外键，这种漏项在本机永远测不出来，所以库这一层也要挡住。
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # verify_email | reset_password
    purpose = Column(String, index=True, nullable=False)
    token_hash = Column(String, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)  # 用过就作废，防重放
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class UserApiKey(Base):
    """BYOK：用户自带的模型 key（密文落库，见 core/security.encrypt_secret）。"""

    __tablename__ = "user_api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 同 AuthToken：ORM 侧已有 User.api_keys 的 delete-orphan，但绕过 ORM 的
    # 批量删除（含测试清理、后台脚本）会跳过它，在 Postgres 上就是外键报错。
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider = Column(String, default="anthropic", nullable=False)  # anthropic | openai_compatible
    # openai_compatible 档专用：具体模型名 + 自定义端点（DeepSeek/Kimi/通义千问/智谱GLM/Ollama…）。
    # provider=anthropic 时通常留空，走人格分级选型（见 select_model）；显式填了则覆盖分级。
    model = Column(String, nullable=True)
    api_base = Column(String, nullable=True)
    key_ciphertext = Column(Text, nullable=False)
    key_masked = Column(String, nullable=False)  # 仅供前端回显
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="api_keys")


class UsageRecord(Base):
    """用量流水（埋线：配额与计费的唯一事实源）。

    每次评审结束写一条；计费只需按 user_id + 时间窗聚合，无需改动评审链路。

    与 Review 的关系是**弱引用**：评审可以删（用户有权删自己的内容），
    但账必须留下——这是财务事实源，绝不能跟着评审级联消失。
    """

    __tablename__ = "usage_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False, default="anonymous")
    # 以前这里是裸 ForeignKey：既没 ondelete 也没有任何清理逻辑。
    # "评审删了账要在"这条承诺只在 SQLite 默认关闭外键校验时侥幸成立，
    # 换成 PostgreSQL（部署文档指定的生产库）后，删评审 / 删账号会直接撞上
    # 外键约束报 500。SET NULL 才是这条承诺真正的落地方式：账留下，
    # 指针失效（下面这行仍能回答"某次消耗了多少 token / 多少钱"）。
    # 注意老库建表时没有这个子句，所以删除路径仍显式置空一遍，
    # 见 user_data_service.delete_user_data。
    review_id = Column(String, ForeignKey("reviews.id", ondelete="SET NULL"), nullable=True)
    kind = Column(String, default="review", nullable=False)  # review | intent | evaluation
    persona_count = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    # token 计量事实源：按 user_id + 时间窗聚合即得后台的 token 用量报表
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    key_source = Column(String, default="byok", nullable=False)  # byok | server —— 谁付的钱
    created_at = Column(DateTime, index=True, default=lambda: datetime.now(timezone.utc), nullable=False)


class Job(Base):
    """异步任务（埋线：内存队列亦落库，换 Celery/RQ 时前端契约不变）。"""

    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kind = Column(String, nullable=False)  # review | evaluation
    ref_id = Column(String, index=True, nullable=True)  # 通常是 review_id
    user_id = Column(String, index=True, nullable=True, default="anonymous")
    status = Column(String, default="queued", nullable=False)  # queued|running|done|failed|cancelled
    progress = Column(Integer, default=0, nullable=False)  # 0-100
    payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# 判断复利闭环（Judgment Ledger）
#
# 这是产品的护城河层：每次评审产出的"预测"落库并盖时间戳；
# 日后真实用户测试回来，回填 Outcome 打分 —— 于是可以回答：
#   "这个人格/这类议题，历史上说中过多少次？"
# 没有这一层，评审就是一次性的；有了它，判断才会随时间复利。
# ---------------------------------------------------------------------------


class Judgment(Base):
    """一条可证伪的预测（通常来自评审报告里的 key_issue / priority_fix）。"""

    __tablename__ = "judgments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey("reviews.id"), index=True, nullable=False)
    user_id = Column(String, index=True, nullable=True, default="anonymous")
    persona_id = Column(String, index=True, nullable=True)  # 谁做的判断（None=评审团合议）
    claim = Column(Text, nullable=False)                    # 预测内容，如"新手引导太长会劝退"
    severity = Column(String, nullable=True)                # low|medium|high|critical
    confidence = Column(Float, nullable=True)               # 0-1
    evidence = Column(JSON, nullable=True)                  # 证据链（含 direct/inferred/gap 标注）
    # 时间戳：预测是何时做出的 —— 事后验证的公正性全靠它
    predicted_at = Column(DateTime, index=True, default=lambda: datetime.now(timezone.utc), nullable=False)

    review = relationship("Review", back_populates="judgments")
    outcome = relationship("Outcome", back_populates="judgment", uselist=False, cascade="all, delete-orphan")


class Outcome(Base):
    """对某条 Judgment 的事后验证（真人测试/上线数据回填）。"""

    __tablename__ = "outcomes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    judgment_id = Column(String, ForeignKey("judgments.id"), unique=True, index=True, nullable=False)
    # hit=说中了 / miss=没发生 / partial=部分成立 / unknown=暂无法判定
    verdict = Column(String, nullable=False)
    source = Column(String, nullable=True)   # playtest | analytics | store_review | manual
    note = Column(Text, nullable=True)
    verified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    judgment = relationship("Judgment", back_populates="outcome")


class ReviewFeedback(Base):
    """评审后的价值回填：衡量采用、决策影响和付费意愿。"""

    __tablename__ = "review_feedback"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey("reviews.id"), unique=True, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False, default="anonymous")
    useful = Column(Boolean, nullable=False)
    decision_changed = Column(Boolean, nullable=False, default=False)
    fixes_suggested = Column(Integer, nullable=False, default=0)
    fixes_adopted = Column(Integer, nullable=False, default=0)
    hours_saved = Column(Float, nullable=False, default=0.0)
    willingness_to_pay_usd = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    review = relationship("Review", back_populates="feedback")
    adoptions = relationship("FeedbackAdoption", back_populates="feedback", cascade="all, delete-orphan")


class FeedbackAdoption(Base):
    """被实际采纳的具体建议，支持后续分析哪些建议真正产生行为。"""

    __tablename__ = "feedback_adoptions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    feedback_id = Column(String, ForeignKey("review_feedback.id"), index=True, nullable=False)
    fix_title = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    feedback = relationship("ReviewFeedback", back_populates="adoptions")


# ---------------------------------------------------------------------------
# 后台管理（Admin）
#
# PlatformSetting 是运行时可调配置的唯一落点：管理员在后台面板改的每一项
# （配额开关、限流参数、key_mode…）落这张表，读取时"DB 覆盖值优先于环境变量默认值"。
# 好处是改配置不需要重启进程；坏处是每次读取多一次数据库查询——
# 对自托管/单机部署这个量级完全无感，多副本 SaaS 规模才需要加缓存层。
# ---------------------------------------------------------------------------


class PlatformSetting(Base):
    """管理员在后台面板调整的运行时配置覆盖（键值对，值统一存字符串，按声明类型转换）。"""

    __tablename__ = "platform_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# ---------------------------------------------------------------------------
# CDK 兑换码
#
# 后台批量生成 → 分发给用户 → 免登录兑换获得评审次数（credits）。
# 次数只对"服务端垫付 key"的评审生效（BYOK 本来就不限量，见 quota_service）。
# 余额不存 users 表：匿名/游客/注册用户统一走 CreditLedger 流水求和，
# 与 UsageRecord 同一设计哲学——事实源是流水，不是可变计数器。
# ---------------------------------------------------------------------------


class CdkCode(Base):
    """一个兑换码。max_uses 允许同一码发给多人（如活动通用码），
    但同一用户对同一码只能兑一次（CdkRedemption 唯一约束兜底）。"""

    __tablename__ = "cdk_codes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, unique=True, index=True, nullable=False)
    credits = Column(Integer, nullable=False)             # 每次兑换发放的评审次数
    max_uses = Column(Integer, default=1, nullable=False)  # 可被多少个不同用户兑换
    used_count = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=True)           # NULL = 永不过期
    is_disabled = Column(Boolean, default=False, nullable=False)
    batch_id = Column(String, index=True, nullable=True)   # 同一次生成的批次号
    note = Column(String, nullable=True)                   # 用途备注（如"首发活动"）
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    redemptions = relationship("CdkRedemption", back_populates="cdk_code", cascade="all, delete-orphan")


class CdkRedemption(Base):
    """一次兑换记录。(code_id, user_id) 唯一——同一人不能重复兑同一码。"""

    __tablename__ = "cdk_redemptions"
    __table_args__ = (UniqueConstraint("code_id", "user_id", name="uq_cdk_code_user"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code_id = Column(String, ForeignKey("cdk_codes.id"), index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    credits = Column(Integer, nullable=False)  # 兑换时的发放量快照（码后来改了也不影响历史）
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    cdk_code = relationship("CdkCode", back_populates="redemptions")


class CreditLedger(Base):
    """评审次数流水：+ 为发放（兑换），- 为消耗（超出套餐限额时垫一次）。
    余额 = SUM(delta)。只增不改，天然可审计。"""

    __tablename__ = "credit_ledger"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)  # cdk_redeem | review
    ref_id = Column(String, nullable=True)   # code_id 或 review 相关标识
    created_at = Column(DateTime, index=True, default=lambda: datetime.now(timezone.utc), nullable=False)


class AdminAuditLog(Base):
    """管理员操作审计流水——谁在何时改了哪个配置/套餐/平台 Key。只增不改。"""

    __tablename__ = "admin_audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String, index=True, nullable=False)  # 如 setting.update / plan.override / server_key.set
    target = Column(String, nullable=True)  # 被改动对象，如 setting key、plan id
    detail = Column(Text, nullable=True)  # JSON 字符串，记录变更前后的值
    created_at = Column(DateTime, index=True, default=lambda: datetime.now(timezone.utc), nullable=False)
