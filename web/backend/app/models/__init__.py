import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List as TypingList

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
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
    mode = Column(String, default="standard", nullable=False)
    status = Column(String, default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    total_cost_usd = Column(Float, default=0.0, nullable=False)
    report_json = Column(JSON, nullable=True)
    report_markdown = Column(Text, nullable=True)
    calibration = Column(JSON, nullable=True)

    persona_outputs = relationship("PersonaOutput", back_populates="review", cascade="all, delete-orphan")
    evaluation_results = relationship("EvaluationResult", back_populates="review", cascade="all, delete-orphan")
    judgments = relationship("Judgment", back_populates="review", cascade="all, delete-orphan")


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
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    review = relationship("Review", back_populates="persona_outputs")


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
    __tablename__ = "evaluation_scorecards"

    review_id = Column(String, ForeignKey("reviews.id"), primary_key=True)
    overall_score = Column(Integer, nullable=False, default=0)
    passed = Column(Boolean, nullable=False, default=False)
    results_json = Column(JSON, nullable=True)
    critical_failures_json = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class EthicsReport(Base):
    __tablename__ = "ethics_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id = Column(String, nullable=False)
    passed = Column(Boolean, nullable=False, default=False)
    score = Column(Integer, nullable=False, default=0)
    violations_json = Column(JSON, nullable=True, default=list)
    stereotype_risk = Column(String, nullable=True, default="low")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    api_keys = relationship("UserApiKey", back_populates="user", cascade="all, delete-orphan")


class UserApiKey(Base):
    """BYOK：用户自带的模型 key（密文落库，见 core/security.encrypt_secret）。"""

    __tablename__ = "user_api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    provider = Column(String, default="anthropic", nullable=False)  # anthropic|openai|deepseek|ollama
    key_ciphertext = Column(Text, nullable=False)
    key_masked = Column(String, nullable=False)  # 仅供前端回显
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="api_keys")


class UsageRecord(Base):
    """用量流水（埋线：配额与计费的唯一事实源）。

    每次评审结束写一条；计费只需按 user_id + 时间窗聚合，无需改动评审链路。
    """

    __tablename__ = "usage_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False, default="anonymous")
    review_id = Column(String, ForeignKey("reviews.id"), nullable=True)
    kind = Column(String, default="review", nullable=False)  # review | intent | evaluation
    persona_count = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
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
