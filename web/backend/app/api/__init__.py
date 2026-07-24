import asyncio
import json
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile

from app.models import Review
from app.schemas import (
    ExampleResponse,
    ExtractedMaterialsResponse,
    EvaluationResultResponse,
    EvaluationScorecardResponse,
    EthicsReportResponse,
    PackSummary,
    PersonaGenerateRequest,
    PersonaOutputResponse,
    PersonaSummary,
    PresetResponse,
    ReportResponse,
    ReviewCreate,
    ReviewModeConfig,
    ReviewListItemResponse,
    ReviewResponse,
    ReviewResult,
    ReviewSession,
    RubricResponse,
    SkillTypeResponse,
    TaskTypeResponse,
)
from app.db import get_db
from app.deps import Identity, optional_identity
from app.services import MaterialExtractor, PersonaService, ReviewService, report_gating
from app.services.evaluation_service import EvaluationService
from app.services.ethics_service import EthicsService
from app.websocket import manager

from sqlalchemy.orm import Session

from app.models import Base

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

router = APIRouter(prefix="/api")


def get_session() -> Session:
    from app.main import engine
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


@router.post("/reviews", response_model=ReviewResponse)
def create_review(
    data: ReviewCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    svc = ReviewService(session)
    review = svc.create_review(
        task_type=data.task_type,
        artifact_bundle=data.artifact_bundle,
        persona_pack=data.persona_pack,
        selected_personas=data.selected_personas,
        mode=data.mode.value if hasattr(data.mode, 'value') else data.mode,
        user_id=identity.user_id,
        skill_type=data.skill_type,
        project_key=data.project_key,
    )

    def _run():
        from app.main import engine
        bg_session = Session(engine)
        try:
            bg_svc = ReviewService(bg_session)
            bg_svc.run_review(review.id, ws_manager=manager)
        finally:
            bg_session.close()

    background_tasks.add_task(_run)
    return review


def _check_review_owner(review: Review, identity: Identity) -> None:
    """review.user_id 为空视为无主历史数据（早于 user_id 字段/迁移遗留），不拦；
    否则必须跟当前身份一致。用 404 而不是 403——不向非本人确认"这个 ID 存在"。
    注意：AL_AUTH_ENABLED=false 时所有匿名请求共享同一个 "anonymous" user_id，
    这种单机/开源形态下互相能看到彼此的评审是设计使然（判断复利、CDK 额度也是
    同一个共享桶），不是这次修复要解决的问题——这里堵的是"登录用户能看别人账号"的洞。"""
    if review.user_id and review.user_id != identity.user_id:
        raise HTTPException(status_code=404, detail="Review not found")


@router.get("/reviews", response_model=List[ReviewListItemResponse])
def list_reviews(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    """列表只返回瘦身字段（见 ReviewListItemResponse）——不带 artifact_bundle /
    report_json / persona_outputs。侧栏只画一行标题，不该为此把每条评审的
    base64 截图和完整报告全量拖下来。要完整内容请求 GET /api/reviews/{id}。"""
    svc = ReviewService(session)
    return svc.list_reviews(offset=offset, limit=limit, user_id=identity.user_id)


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
def get_review(
    review_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    _check_review_owner(review, identity)
    return review


@router.delete("/reviews/{review_id}")
def delete_review(
    review_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    _check_review_owner(review, identity)
    svc.delete_review(review_id)
    return {"detail": "Deleted"}


@router.get("/reviews/{review_id}/report", response_model=ReportResponse)
def get_report(
    review_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    _check_review_owner(review, identity)
    report_json = review.report_json
    if identity.is_anonymous:
        report_json = report_gating.gate_report_for_anonymous(report_json)
    return ReportResponse(
        report_json=report_json,
        report_markdown=review.report_markdown,
        calibration=review.calibration,
    )


@router.get("/reviews/{review_id}/result", response_model=ReviewResult)
def get_review_result(
    review_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    _check_review_owner(review, identity)
    report_html = None
    if review.report_json:
        try:
            html_template_path = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.html")
            if os.path.isfile(html_template_path):
                from runner.html_report import generate_html_report
                report_html = generate_html_report(review.report_json, html_template_path)
        except Exception:
            pass
    return ReviewResult(
        session_id=review.id,
        report_json=review.report_json,
        report_md=review.report_markdown,
        report_html=report_html,
    )


@router.get("/personas", response_model=List[PersonaSummary])
def list_personas():
    all_personas = PersonaService.get_all_personas()
    result = []
    for p in all_personas:
        result.append(PersonaSummary(
            id=p["id"],
            name=p.get("name", p["id"]),
            archetype=p.get("archetype", ""),
            identity_summary=p.get("identity_summary", ""),
            behavior_profile=p.get("behavior_profile", {}),
            gaming_profile=p.get("gaming_profile", {}),
            pack=p.get("_pack", ""),
            source=p.get("source", "yaml"),
        ))
    return result


@router.get("/personas/packs", response_model=List[PackSummary])
def list_packs():
    return PersonaService.list_packs()


@router.get("/personas/packs/{pack}", response_model=List[PersonaSummary])
def list_personas_by_pack(pack: str):
    personas = PersonaService.get_personas_by_pack(pack)
    if not personas:
        raise HTTPException(status_code=404, detail=f"Pack '{pack}' not found")
    result = []
    for p in personas:
        result.append(PersonaSummary(
            id=p["id"],
            name=p.get("name", p["id"]),
            archetype=p.get("archetype", ""),
            identity_summary=p.get("identity_summary", ""),
            behavior_profile=p.get("behavior_profile", {}),
            gaming_profile=p.get("gaming_profile", {}),
            pack=p.get("_pack", pack),
            source=p.get("source", "yaml"),
        ))
    return result


@router.get("/personas/packs/{pack}/{persona_id}", response_model=PersonaSummary)
def get_persona_in_pack(pack: str, persona_id: str):
    personas = PersonaService.get_personas_by_pack(pack)
    for p in personas:
        if p["id"] == persona_id:
            return PersonaSummary(
                id=p["id"],
                name=p.get("name", p["id"]),
                archetype=p.get("archetype", ""),
                identity_summary=p.get("identity_summary", ""),
                behavior_profile=p.get("behavior_profile", {}),
                gaming_profile=p.get("gaming_profile", {}),
                pack=p.get("_pack", pack),
                source=p.get("source", "yaml"),
            )
    raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found in pack '{pack}'")


@router.get("/personas/{persona_id}", response_model=PersonaSummary)
def get_persona(persona_id: str):
    p = PersonaService.get_persona_by_id(persona_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return PersonaSummary(
        id=p["id"],
        name=p.get("name", p["id"]),
        archetype=p.get("archetype", ""),
        identity_summary=p.get("identity_summary", ""),
        behavior_profile=p.get("behavior_profile", {}),
        gaming_profile=p.get("gaming_profile", {}),
        pack=p.get("_pack", ""),
        source=p.get("source", "yaml"),
    )


@router.get("/task-types", response_model=List[TaskTypeResponse])
def list_task_types():
    return PersonaService.get_task_types()


@router.get("/task-types/{task_type}", response_model=TaskTypeResponse)
def get_task_type(task_type: str):
    result = PersonaService.get_task_type(task_type)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Task type '{task_type}' not found")
    return result


@router.get("/review-modes", response_model=List[ReviewModeConfig])
def list_review_modes():
    return PersonaService.get_review_modes()


@router.get("/presets", response_model=List[PresetResponse])
def list_presets():
    presets = PersonaService.load_presets()
    result = []
    for task_type, preset in presets.items():
        result.append(PresetResponse(
            task_type=task_type,
            default_personas=preset.get("default_personas", []),
            optional_personas=preset.get("optional_personas", []),
        ))
    return result


@router.get("/presets/{task_type}", response_model=PresetResponse)
def get_preset(task_type: str):
    preset = PersonaService.get_preset(task_type)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    return PresetResponse(
        task_type=task_type,
        default_personas=preset.get("default_personas", []),
        optional_personas=preset.get("optional_personas", []),
    )


@router.get("/examples", response_model=List[ExampleResponse])
def list_examples():
    examples_dir = os.path.join(PROJECT_ROOT, "examples")
    if not os.path.isdir(examples_dir):
        return []
    result = []
    for dirname in sorted(os.listdir(examples_dir)):
        artifact_path = os.path.join(examples_dir, dirname, "artifact.json")
        if os.path.isfile(artifact_path):
            try:
                with open(artifact_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result.append({
                    "id": dirname,
                    "title": data.get("title", dirname),
                    "type": data.get("type", ""),
                    "description": data.get("description", ""),
                    "artifact_bundle": data,
                })
            except Exception:
                pass
    return result


MAX_UPLOAD_SIZE = 10 * 1024 * 1024
# .doc（旧版二进制格式）故意不在这里——python-docx 只认 .docx（zip+XML），解不了 .doc，
# 之前把它写进"支持列表"是没兑现的承诺，见下面 _extract_text_from_file 的报错提示。
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".json", ".yaml", ".yml"}
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".yaml", ".yml"}


def _extract_text_from_file(content: bytes, ext: str) -> str:
    """按扩展名解析成纯文字。txt 系走编码解码；pdf/docx 走各自的解析库——
    之前不管什么格式都硬当 UTF-8/GBK 文本解码，PDF/DOCX 是二进制格式，
    上传就直接报"无法解析文件编码"，等于 UI 上写的支持是空头支票。"""
    if ext == ".pdf":
        import io

        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise HTTPException(status_code=400, detail="PDF 文件已加密，暂不支持解析加密文档")
            pages = [page.extract_text() or "" for page in reader.pages]
        except PdfReadError:
            raise HTTPException(status_code=400, detail="PDF 文件已损坏或格式无法识别")
        text = "\n\n".join(p for p in pages if p.strip())
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF 未提取到文字内容（可能是纯图片扫描件，暂不支持 OCR）")
        return text

    if ext == ".docx":
        import io
        import zipfile

        from docx import Document
        from docx.opc.exceptions import PackageNotFoundError

        try:
            doc = Document(io.BytesIO(content))
        except (PackageNotFoundError, zipfile.BadZipFile):
            raise HTTPException(status_code=400, detail="DOCX 文件已损坏或不是有效的 Word 文档")
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                paragraphs.extend(cell.text for cell in row.cells if cell.text.strip())
        text = "\n".join(paragraphs)
        if not text.strip():
            raise HTTPException(status_code=400, detail="DOCX 未提取到文字内容")
        return text

    # 纯文本格式：txt/md/json/yaml/yml
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="无法解析文件编码，请上传 UTF-8 或 GBK 编码的文本文件")


@router.post("/extract-materials", response_model=ExtractedMaterialsResponse)
async def extract_materials(
    task_type: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    filename = file.filename or "unknown"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext == ".doc":
        raise HTTPException(
            status_code=400,
            detail="不支持旧版 .doc 格式（仅支持 .docx）。请用 Word 另存为 .docx 后重新上传。",
        )
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，允许的类型: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    safe_name = os.path.basename(filename)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="文件名包含非法路径字符")

    content = await file.read()

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // (1024 * 1024)}MB）")

    safe_filename = str(uuid.uuid4()) + ext
    text = _extract_text_from_file(content, ext)

    # AI 抽取档走 BYOK（此前硬编码读环境变量，绕过用户配置的 key/中转/模型）；
    # 没配 key 就退回规则抽取，不阻断上传
    from app.services import key_service

    try:
        resolved = key_service.resolve_key(session, identity.user_id)
    except Exception:
        resolved = None

    result = MaterialExtractor.extract(task_type, text, safe_filename, resolved=resolved)
    return result


@router.post("/evaluations/{review_id}", response_model=EvaluationScorecardResponse)
def run_evaluation(review_id: str, session: Session = Depends(get_session)):
    """对指定评审运行完整评估"""
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status != "completed":
        raise HTTPException(status_code=400, detail="评审尚未完成，无法运行评估")

    scorecard = EvaluationService.run_full_evaluation(session, review_id)

    results = EvaluationService.get_evaluation_results(session, review_id)
    results_data = [
        EvaluationResultResponse(
            id=r.id,
            review_id=r.review_id,
            dimension=r.dimension,
            score=r.score,
            passed=r.passed,
            details=r.details or "",
            evaluated_at=r.evaluated_at,
        )
        for r in results
    ]

    return EvaluationScorecardResponse(
        review_id=scorecard.review_id,
        overall_score=scorecard.overall_score,
        passed=scorecard.passed,
        results=results_data,
        critical_failures=scorecard.critical_failures_json or [],
    )


@router.get("/evaluations/{review_id}", response_model=EvaluationScorecardResponse)
def get_evaluation(review_id: str, session: Session = Depends(get_session)):
    """获取指定评审的评估结果"""
    scorecard = EvaluationService.get_evaluation(session, review_id)
    if scorecard is None:
        raise HTTPException(status_code=404, detail="评估结果不存在，请先运行 POST /api/evaluations/{review_id}")

    results = EvaluationService.get_evaluation_results(session, review_id)
    results_data = [
        EvaluationResultResponse(
            id=r.id,
            review_id=r.review_id,
            dimension=r.dimension,
            score=r.score,
            passed=r.passed,
            details=r.details or "",
            evaluated_at=r.evaluated_at,
        )
        for r in results
    ]

    return EvaluationScorecardResponse(
        review_id=scorecard.review_id,
        overall_score=scorecard.overall_score,
        passed=scorecard.passed,
        results=results_data,
        critical_failures=scorecard.critical_failures_json or [],
    )


@router.get("/evaluations/{review_id}/ethics", response_model=List[EthicsReportResponse])
def get_ethics_reports(review_id: str, session: Session = Depends(get_session)):
    """获取指定评审中每个 persona 的伦理报告"""
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    reports = EthicsService.get_ethics_reports_for_review(session, review_id)
    return [
        EthicsReportResponse(
            id=r.id,
            persona_id=r.persona_id,
            passed=r.passed,
            score=r.score,
            violations=r.violations_json or [],
            stereotype_risk=r.stereotype_risk or "low",
        )
        for r in reports
    ]


@router.get("/skills", response_model=List[SkillTypeResponse])
def list_skills():
    """列出所有可用的技能类型"""
    return PersonaService.get_skill_types()


@router.get("/skills/{skill_type}", response_model=SkillTypeResponse)
def get_skill_detail(skill_type: str):
    """获取指定技能类型的详细信息"""
    detail = PersonaService.get_skill_detail(skill_type)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"技能类型 '{skill_type}' 不存在")
    return detail


@router.post("/generate-personas")
def generate_personas(request: PersonaGenerateRequest):
    """触发 persona 生成"""
    personas = PersonaService.generate_personas(
        domain=request.domain,
        audience=request.audience,
        goals=request.goals,
        count=request.count,
    )
    return {"personas": personas, "count": len(personas)}


@router.get("/rubric", response_model=RubricResponse)
def get_rubric():
    """获取评估评分标准"""
    rubric = EvaluationService.get_rubric()
    dimensions = []
    for dim_name, scores in rubric.get("dimensions", {}).items():
        dimensions.append(RubricDimensionResponse(dimension=dim_name, scores=scores))
    return RubricResponse(
        dimensions=dimensions,
        critical_failures=rubric.get("critical_failures", []),
    )
