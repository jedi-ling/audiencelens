from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator


class ReviewMode(str, Enum):
    quick = "quick"
    standard = "standard"
    full = "full"


class ReviewCreate(BaseModel):
    task_type: str
    artifact_bundle: Dict[str, Any]
    persona_pack: Optional[str] = None
    selected_personas: Optional[List[str]] = None
    mode: ReviewMode = ReviewMode.standard
    skill_type: Optional[str] = None
    project_key: Optional[str] = None


class PersonaOutputResponse(BaseModel):
    id: str
    review_id: str
    persona_id: str
    persona_name: Optional[str] = None
    status: str
    output_json: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    cost_usd: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReviewResponse(BaseModel):
    id: str
    task_type: str
    target_title: Optional[str] = None
    artifact_bundle: Dict[str, Any]
    persona_pack: Optional[str] = None
    selected_personas: Optional[List[str]] = None
    skill_type: Optional[str] = None
    project_key: Optional[str] = None
    mode: str = "standard"
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_cost_usd: float
    report_json: Optional[Dict[str, Any]] = None
    report_markdown: Optional[str] = None
    calibration: Optional[Dict[str, Any]] = None
    persona_outputs: List[PersonaOutputResponse] = []

    model_config = {"from_attributes": True}


class ReviewListItemResponse(BaseModel):
    """列表专用的瘦身响应——只有侧栏/历史页真正要显示的字段。

    此前 /api/reviews 直接返回完整 ReviewResponse：每条都带着完整
    artifact_bundle（内含 base64 图片，一张截图就能有几 MB）、report_json、
    report_markdown、以及每个人格的完整 output_json。侧栏其实只画一行标题，
    却要为此下载几十 MB——评审越多、带图越多，历史页只会越来越慢。

    需要完整内容的地方走 GET /api/reviews/{id}（仍返回 ReviewResponse）。
    """

    id: str
    task_type: str
    target_title: Optional[str] = None
    project_key: Optional[str] = None
    mode: str = "standard"
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_cost_usd: float
    input_tokens: int = 0
    output_tokens: int = 0

    model_config = {"from_attributes": True}


class PersonaSummary(BaseModel):
    id: str
    name: str
    archetype: str
    identity_summary: str
    behavior_profile: Dict[str, Any]
    gaming_profile: Dict[str, Any] = {}
    pack: str
    source: str = "yaml"


class PackSummary(BaseModel):
    panel_id: str
    name: str
    description: str
    persona_count: int
    category: str = 'special'


class PresetResponse(BaseModel):
    task_type: str
    default_personas: List[str]
    optional_personas: List[str]


class ReportResponse(BaseModel):
    report_json: Optional[Dict[str, Any]] = None
    report_markdown: Optional[str] = None
    calibration: Optional[Dict[str, Any]] = None


class ExampleResponse(BaseModel):
    id: str
    title: str
    type: str
    description: str
    artifact_bundle: Dict[str, Any]


class ExtractedMaterialsResponse(BaseModel):
    title: str
    materials: Dict[str, str]


class ReviewSession(BaseModel):
    id: str
    task_type: str
    materials: Dict[str, Any]
    mode: ReviewMode = ReviewMode.standard
    panel_personas: List[str] = []
    status: str = "pending"
    created_at: datetime


class ReviewResult(BaseModel):
    session_id: str
    report_json: Optional[Dict[str, Any]] = None
    report_md: Optional[str] = None
    report_html: Optional[str] = None


class TaskTypeStanceDimension(BaseModel):
    stance_enum: List[str]
    score_dimensions: List[str]
    base_dimensions: List[str] = ["clarity", "trust"]


class TaskTypeResponse(BaseModel):
    task_type: str
    name_zh: str
    description: str
    stance_enum: List[str]
    score_dimensions: List[str]
    base_dimensions: List[str] = ["clarity", "trust"]


class ReviewModeConfig(BaseModel):
    mode: ReviewMode
    persona_count_range: List[int]
    cross_examination: bool
    calibration: bool
    description: str


class EvaluationResultResponse(BaseModel):
    id: str
    review_id: str
    dimension: str
    score: int
    passed: bool
    details: str = ""
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class EvaluationScorecardResponse(BaseModel):
    review_id: str
    overall_score: int
    passed: bool
    results: List[EvaluationResultResponse] = []
    critical_failures: List[str] = []

    model_config = {"from_attributes": True}


class EthicsReportResponse(BaseModel):
    id: str
    persona_id: str
    passed: bool
    score: int
    violations: List[Dict[str, Any]] = []
    stereotype_risk: str = "low"

    model_config = {"from_attributes": True}


class SkillTypeResponse(BaseModel):
    skill_type: str
    name: str
    description: str


class RubricDimensionResponse(BaseModel):
    dimension: str
    scores: Dict[str, str]


class RubricResponse(BaseModel):
    dimensions: List[RubricDimensionResponse]
    critical_failures: List[str]


class PersonaGenerateRequest(BaseModel):
    domain: str
    audience: str = ""
    goals: str = ""
    count: int = 4
