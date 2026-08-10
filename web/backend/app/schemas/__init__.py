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
    # v2（POST /api/v2/reviews）一直收这两个开关，v1 的 schema 里没有——
    # pydantic 对未声明字段默认忽略，于是外部调用方按公开文档传了
    # enable_red_team=true，请求 200、评审照跑，但红队那一层压根没开，
    # 也没有任何回执说明。这是"以为开了其实没开"，比直接 422 更坏。
    enable_red_team: bool = False
    enable_evaluation: bool = False


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
    # 列表接口（ReviewListItemResponse）一直有这两个数，详情接口反而没有——
    # 于是"点进去看这次花了多少 token"比在列表上看还少信息。
    input_tokens: int = 0
    output_tokens: int = 0
    # 失败原因必须能被读到。此前只能靠 _report_json_for 在 report_json 为空时
    # 伪造一个 {"error": ...}：引擎写了半份报告又失败时 report_json 非空，
    # 兜底分支不触发，失败原因彻底看不见——status=failed 但一个字的解释都没有。
    error_message: Optional[str] = None
    # 高级技能降级说明。None = 没降级。v2 一直回它并由前端弹提示，v1 没有任何
    # 字段承载，走 v1 的用户会以为红队/高级技能正常跑了。静默降级是本仓库要根除的形状。
    # 注意它不是 Review 表的列，由端点显式 model_copy 填入（from_attributes 取不到）。
    skill_degraded: Optional[str] = None
    report_json: Optional[Dict[str, Any]] = None
    report_markdown: Optional[str] = None
    calibration: Optional[Dict[str, Any]] = None
    persona_outputs: List[PersonaOutputResponse] = []
    # 只读分享状态。None = 未分享。报告页据此决定分享按钮显示「生成链接」
    # 还是「已公开 + 撤销」。
    # 出现在这里是安全的：所有吐 ReviewResponse 的端点都先过 _check_review_owner，
    # 也就是说这个 token 只会回给它自己的作者。
    share_token: Optional[str] = None
    shared_at: Optional[datetime] = None

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
    # 与 ReviewResponse 同理：报告为空时，用户有权知道是"还没跑完"还是"跑失败了、原因是这个"
    error_message: Optional[str] = None


class ExampleResponse(BaseModel):
    id: str
    title: str
    type: str
    description: str
    artifact_bundle: Dict[str, Any]


class UploadConfigResponse(BaseModel):
    allowed_ext: List[str]
    allowed_image_ext: List[str]
    max_bytes: int
    max_image_bytes: int


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
    # report_html 为空时的原因。None 且 report_html 也为 None，只可能是
    # report_json 本身为空（评审还没跑完/失败）。
    # 有这一条前端才能区分"渲染坏了"和"这份报告本来就没有 HTML"，
    # 而不是把导出按钮一直亮着、下发一张写着"尚未生成"的白页。
    html_error: Optional[str] = None


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
    """技能条目。列表端点只填前三个字段，详情端点（GET /api/skills/{skill_type}）
    还会填下面这些按技能类型分支组装的能力描述。

    为什么把详情字段并进同一个模型而不是不设 response_model：
    不设的话这个端点就从 OpenAPI 文档里消失了形状，外部调用方只能靠猜。
    为什么全部 Optional 且默认 None：不同技能能回答的问题本来就不一样
    （人格生成有 parameters、评审类技能有 task_types），硬造出空列表来凑齐字段
    会让前端把「答案是空」和「这个技能不谈这个问题」混为一谈。
    曾有过 supported_domains / attack_surfaces 两个字段——值是手写的四个词，
    全仓没有任何代码按它分支，属于编造的能力承诺，已随服务层一起删除。

    这些字段此前全部被 FastAPI 按 response_model 静默裁掉——服务层
    get_skill_detail 认认真真算了一遍，一个字都没到前端。于是前端只好自己
    写死一份 task_types 假清单（数字追溯不到任何事实源）。加字段这件事
    本身就是在拆掉那份假数据的存在理由。
    """

    skill_type: str
    name: str
    description: str
    # 该技能可用的人格包 id（当前只有 synthetic_playtest 给）
    available_packs: Optional[List[str]] = None
    # 该技能支持的任务类型（真实值来自 TASK_TYPES 注册表，不是手写清单）
    task_types: Optional[List[str]] = None
    parameters: Optional[List[str]] = None


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
