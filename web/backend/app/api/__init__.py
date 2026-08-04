import asyncio
import json
import os
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)

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
    RubricDimensionResponse,
    RubricResponse,
    SkillTypeResponse,
    TaskTypeResponse,
)
from app.db import get_db
from app.config import settings
from app.deps import (
    Identity,
    is_shared_anonymous,
    optional_identity,
    rate_limit,
    resolve_llm_key,
)
from app.services import (
    MaterialExtractor,
    PersonaService,
    ReviewService,
    estimate_cost,
    load_budget_config,
    report_gating,
)
from app.services import intent_service, quota_service, review_service
from app.services.evaluation_service import EvaluationService
from app.services.ethics_service import EthicsService

from sqlalchemy import func, select
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


@router.post(
    "/reviews",
    response_model=ReviewResponse,
    dependencies=[Depends(rate_limit("review", None, 3600))],
)
def create_review(
    data: ReviewCreate,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
    resolved=Depends(resolve_llm_key),  # 无 key → 428，绝不静默跑模拟数据
):
    """发起评审。请求/响应形状保持 v1 契约不变，**执行走的是 v2 那条引擎**。

    三道闸和 v2（platform.py::create_review_v2）完全一致：限流 → key → 配额。
    此前这里三道全无，而旧的 ReviewService.run_review 内部照样 resolve_key
    （managed 形态下拿到的是平台 key）——配额用尽的用户只要把请求换到这个端点
    就能无限跑，平台垫钱。安全和计费只加固新链路、把旧链路留成后门，
    是这个仓库最大的洞源。

    为什么不再有第二套执行实现：这个端点原本在后台跑
    ReviewService.run_review——一份跟 src/runner/cli.py::run_panel 平行的
    评审实现。本轮审计里「v2 修了 v1 没修」这一种形状反复出现（calibration
    落库、BYOK、降级契约、交叉质询过滤…），根因就是同一件事两套代码。
    现在这里只负责落库 + 入队，执行统一交给 review_service.enqueue_review
    → runner.cli.run_panel，与 POST /api/v2/reviews 是同一条路径。
    随之自动消失的 v1 专属缺陷（都不必再单独修一遍）：
      · 只读 materials[].description，{type,text} 形态材料渲染成空字符串；
      · 交叉质询缺 filter_genuine_controversies，凭空造争议还多花一次调用；
      · report_markdown / report_html 不带降级横幅；
      · 不写 Judgment（判断复利闭环对这个端点创建的评审永远为空）；
      · 不校验 task_type（未知类型随机抓人格照跑照扣钱，见下面这道校验）。

    对外契约有意保留的差异：仍返回 200 + 完整 Review 实体（v2 是 202 +
    {review_id, job_id}）。这是公开 API，可能有外部调用方按 `id` 字段读；
    进度照旧从 GET /api/reviews/{id} 或 WS /ws/review/{id} 拿。
    """
    # 未知 task_type 必须在入口就拒。此前这里不校验，run_panel 那道
    # ValueError 要等到后台任务里才抛——用户拿到的是一条 failed 评审，
    # 而不是一个能立刻看懂的 400。v2 在同一位置用同一份注册表校验。
    if data.task_type not in intent_service.VALID_TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"未知任务类型：{data.task_type}")

    quota_service.check_quota(
        session, identity.user_id, key_source=resolved.source, plan=identity.plan
    )

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

    # key 显式透传，绝不写进程全局 os.environ——多 worker 并发跑不同用户的
    # 评审时环境变量注入会在用户间串 key（安全 + 计费问题）。
    review_service.enqueue_review(
        review.id,
        api_key=resolved.key,
        key_source=resolved.source,
        user_id=identity.user_id,
        provider=resolved.provider,
        model=resolved.model,
        api_base=resolved.api_base,
    )
    return review


def _check_review_owner(review: Review, identity: Identity) -> None:
    """review.user_id 为空视为无主历史数据（早于 user_id 字段/迁移遗留），不拦；
    否则必须跟当前身份一致。用 404 而不是 403——不向非本人确认"这个 ID 存在"。
    注意：AL_AUTH_ENABLED=false 时所有匿名请求共享同一个 "anonymous" user_id，
    这种单机/开源形态下互相能看到彼此的评审是设计使然（判断复利、CDK 额度也是
    同一个共享桶），不是这次修复要解决的问题——这里堵的是"登录用户能看别人账号"的洞。"""
    if review.user_id and review.user_id != identity.user_id:
        raise HTTPException(status_code=404, detail="Review not found")


def _report_json_for(review: Review) -> Optional[dict]:
    """v1 读路径统一从这里取 report_json —— 失败的评审必须能读到失败原因。

    v1 的对外契约一直是"失败评审的 report_json 就是 {"error": ...}"
    （report_gating.gate_report_for_anonymous 专门为这个形状留了透出分支：
    坏消息不许被登录墙裁掉）。旧的 v1 引擎在 except 里同时写 error_message
    和 report_json={"error": ...}，所以这个契约自然成立。
    收敛到 v2 引擎后原因只写进 error_message 列，而 ReviewResponse /
    ReportResponse 都没有这一列——不做这层转译，v1 的失败评审就会变成
    "status=failed，但为什么失败一个字都看不到"。那正是本仓库要根除的
    "失败被伪装成没有内容"。

    只在 report_json 本身为空时才兜；引擎真写了报告就原样给。
    """
    if review.report_json:
        return review.report_json
    if review.status == "failed" and review.error_message:
        return {"error": review.error_message}
    return review.report_json


def _review_response_for(review: Review, identity: Identity) -> ReviewResponse:
    """把一条 Review 序列化成"这个身份该看到的"响应。

    匿名要裁三处，缺一处登录墙就白做：
      · report_json      —— 结构化裁剪（执行摘要 + 第一条修复项）
      · report_markdown  —— 整份报告的纯文本镜像，一给就等于全给
      · persona_outputs  —— "各角色怎么看"是本产品要卖的东西，不能从侧门免费拿

    历史教训：匿名裁剪当初只接在 GET /reviews/{id}/report 上，而
    GET /reviews/{id} 和 /reviews/{id}/result 原样返回全量内容，
    前端显示"登录看完整"、换个端点请求一下全文到手。
    所以现在所有会吐报告内容的 v1 端点统一走这个函数，不各自拼装。

    artifact_bundle 不裁：那是用户自己上传的材料，本来就是他的东西。
    """
    resp = ReviewResponse.model_validate(review)
    resp = resp.model_copy(update={"report_json": _report_json_for(review)})
    if not identity.is_anonymous:
        return resp
    return resp.model_copy(
        update={
            "report_json": report_gating.gate_report_for_anonymous(resp.report_json),
            "report_markdown": report_gating.gate_markdown_for_anonymous(resp.report_markdown),
            "persona_outputs": report_gating.gate_persona_outputs_for_anonymous(
                resp.persona_outputs
            ),
        }
    )


def _count_reviews_for(session: Session, user_id: Optional[str]) -> int:
    """该身份名下的评审总条数。

    where 子句必须和 ReviewService.list_reviews **逐字一致**（同样按
    Review.user_id 精确匹配），否则前端拿总数算出的"还有 N 条"会指向一批
    永远翻不到的记录——那又是一个"数字对不上"的静默谎话。
    """
    stmt = select(func.count()).select_from(Review)
    if user_id is not None:
        stmt = stmt.where(Review.user_id == user_id)
    return int(session.scalar(stmt) or 0)


@router.get("/reviews", response_model=List[ReviewListItemResponse])
def list_reviews(
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    """列表只返回瘦身字段（见 ReviewListItemResponse）——不带 artifact_bundle /
    report_json / persona_outputs。侧栏只画一行标题，不该为此把每条评审的
    base64 截图和完整报告全量拖下来。要完整内容请求 GET /api/reviews/{id}。

    分页总数放在 `X-Total-Count` 响应头里。
    为什么是响应头而不是把 body 换成 {items, total} 信封：历史页要显示
    "共 N 条 / 已显示 M 条"，用户才能确信第 21 条以后的旧评审只是没加载、
    不是被删了；但把 body 改成信封会一次性打断所有既有调用方。加一个头是纯
    增量，老调用方原样拿到数组。
    跨域部署时需要在 CORS expose_headers 里带上它才读得到；前端读不到时会
    退化成"这一页装满了就说明还有更多"的判断，只是显示不出总数，不会漏数据。
    """
    # 多租户形态下，共享匿名桶不是"某个人"——按 user_id="anonymous" 查出来的
    # 是**全部未登录访客**的评审，等于把张三的评审标题列给李四看。实测确实拿得到。
    # 这里返回空列表而不是 401：侧栏在轮询这个接口，报错会把整页打成错误态；
    # 返回空 + X-Requires-Login 头，前端就能显示"登录后查看历史"而不是干瞪眼。
    # 单机开源形态（auth_enabled=false）不受影响——那台机器上 anonymous 就是本人。
    if settings.auth_enabled and is_shared_anonymous(identity):
        response.headers["X-Total-Count"] = "0"
        response.headers["X-Requires-Login"] = "1"
        return []

    svc = ReviewService(session)
    items = svc.list_reviews(offset=offset, limit=limit, user_id=identity.user_id)
    response.headers["X-Total-Count"] = str(_count_reviews_for(session, identity.user_id))
    return items


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
    return _review_response_for(review, identity)


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
    report_json = _report_json_for(review)
    report_markdown = review.report_markdown
    if identity.is_anonymous:
        report_json = report_gating.gate_report_for_anonymous(report_json)
        # 这一行是重点：以前只裁了 report_json，紧接着把 report_markdown 原文
        # 一起发出去——markdown 里就是整份报告，登录墙等于没有。
        report_markdown = report_gating.gate_markdown_for_anonymous(report_markdown)
    return ReportResponse(
        report_json=report_json,
        report_markdown=report_markdown,
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

    # 先定下"这个身份能看到的 json"，再拿它去渲染 HTML——顺序反了就会
    # 渲染出一份完整报告的 HTML 发给匿名用户（此前正是如此：这个端点
    # 把原始 json + markdown + 渲染好的整份 HTML 一起返回，一个字没裁）。
    report_json = _report_json_for(review)
    report_md = review.report_markdown
    if identity.is_anonymous:
        report_json = report_gating.gate_report_for_anonymous(report_json)
        report_md = report_gating.gate_markdown_for_anonymous(report_md)

    report_html = None
    if report_json:
        try:
            html_template_path = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.html")
            if os.path.isfile(html_template_path):
                from runner.html_report import generate_html_report
                report_html = generate_html_report(report_json, html_template_path)
        except Exception:
            pass
    return ReviewResult(
        session_id=review.id,
        report_json=report_json,
        report_md=report_md,
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


@router.post(
    "/extract-materials",
    response_model=ExtractedMaterialsResponse,
    # 这个端点会拿 resolved key 真调 LLM（managed 形态下是平台 key），
    # 且能一次喂进 10MB 文本，此前一个守卫都没有。窗口对齐 /uploads。
    dependencies=[Depends(rate_limit("upload", 20, 3600))],
)
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

    # 分块读取：先整段 read() 再查大小，等于把一个超限文件整个吸进内存后才
    # 拒绝——大小检查形同虚设，一个超大请求体就能打爆进程内存。读满即中断，
    # 与 v2 /api/uploads 的 _read_capped 同一套做法。
    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // (1024 * 1024)}MB）",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

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


@router.post(
    "/evaluations/{review_id}",
    response_model=EvaluationScorecardResponse,
    dependencies=[Depends(rate_limit("evaluation", 20, 3600))],
)
def run_evaluation(
    review_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    """对指定评审运行完整评估。

    归属校验不能省：这三个 evaluations 端点此前连 identity 参数都没有，
    任何人拿到（或枚举到）别人的 review_id 就能读走别人评审的 8 维评分、
    critical_failures 和伦理报告，POST 这个还能往别人的评审上写记分卡。
    """
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    _check_review_owner(review, identity)
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
def get_evaluation(
    review_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    """获取指定评审的评估结果（先验归属，见 run_evaluation 的说明）"""
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    _check_review_owner(review, identity)

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
def get_ethics_reports(
    review_id: str,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    """获取指定评审中每个 persona 的伦理报告（先验归属，见 run_evaluation 的说明）"""
    svc = ReviewService(session)
    review = svc.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    _check_review_owner(review, identity)

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


@router.post(
    "/generate-personas",
    dependencies=[Depends(rate_limit("generate_personas", 20, 3600))],
)
def generate_personas(
    request: PersonaGenerateRequest,
    session: Session = Depends(get_session),
    identity: Identity = Depends(optional_identity),
):
    """触发 persona 生成。

    这个接口以前是完全裸奔的：没有限流、没有身份、不查配额，服务层还直接
    `os.environ.get("ANTHROPIC_API_KEY")` 拿平台垫付的 key 去调模型，用量也不记账。
    也就是说任何人都能不停地打它，花的是运营的钱，而后台成本面板上一分都看不见。
    现在与评审走同一套关卡：限流 → 身份 → 解析 key（BYOK 优先）→ 记账。

    key 是**可选**解析、不用 Depends(resolve_llm_key)：没有 key 时服务层会走
    _generate_personas_fallback（内置原型库，不发任何模型调用）。挂成硬依赖会让
    无 key 的用户拿到 428，等于把这个本来就能离线用的功能直接关掉。
    """
    from app.services import key_service

    key = provider = model = api_base = None
    key_source = "byok"
    try:
        resolved = key_service.resolve_key(session, identity.user_id)
        key, provider, model, api_base = (
            resolved.key,
            resolved.provider,
            resolved.model,
            resolved.api_base,
        )
        key_source = resolved.source
    except Exception:
        key = None  # 没 key 就走内置原型库，不阻断

    usage: dict = {}
    personas = PersonaService.generate_personas(
        domain=request.domain,
        audience=request.audience,
        goals=request.goals,
        count=request.count,
        api_key=key,
        provider=provider or "anthropic",
        model=model,
        api_base=api_base,
        usage=usage,
    )

    in_tok = int(usage.get("input_tokens") or 0)
    out_tok = int(usage.get("output_tokens") or 0)
    if in_tok or out_tok:
        cost = 0.0
        try:
            cost = estimate_cost(in_tok, out_tok, usage.get("model") or "", load_budget_config())
        except Exception:
            cost = 0.0  # 算不出钱也要把 token 记下来
        quota_service.record_usage(
            session,
            identity.user_id,
            kind="generate_personas",
            cost_usd=cost,
            input_tokens=in_tok,
            output_tokens=out_tok,
            key_source=key_source,
        )
    return {"personas": personas, "count": len(personas)}


@router.get("/rubric", response_model=RubricResponse)
def get_rubric():
    """获取评估评分标准。

    RubricDimensionResponse 曾经不在文件顶部那份 from app.schemas import (...) 里，
    而 load_rubrics 一定返回非空 dimensions（内置 RUBRIC_SCORES 兜底），
    所以循环体必定执行 → NameError → 这个端点 100% 500。
    """
    rubric = EvaluationService.get_rubric()
    dimensions = []
    for dim_name, scores in rubric.get("dimensions", {}).items():
        dimensions.append(RubricDimensionResponse(dimension=dim_name, scores=scores))
    return RubricResponse(
        dimensions=dimensions,
        critical_failures=rubric.get("critical_failures", []),
    )
