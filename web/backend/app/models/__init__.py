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


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String, nullable=False)
    target_title = Column(String, nullable=True)
    artifact_bundle = Column(JSON, nullable=False)
    persona_pack = Column(String, nullable=True)
    selected_personas = Column(JSON, nullable=True)
    mode = Column(String, default="standard", nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    total_cost_usd = Column(Float, default=0.0, nullable=False)
    report_json = Column(JSON, nullable=True)
    report_markdown = Column(Text, nullable=True)
    calibration = Column(JSON, nullable=True)

    persona_outputs = relationship("PersonaOutput", back_populates="review", cascade="all, delete-orphan")
    evaluation_results = relationship("EvaluationResult", back_populates="review", cascade="all, delete-orphan")


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
