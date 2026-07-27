import argparse
import concurrent.futures
import json
import os
import threading
from typing import Callable, List, Optional

import yaml

try:
    from .aggregator import aggregate_report, load_aggregation_rules, render_markdown_report, render_html_report
    from .calibration import run_calibration_check
    from .cross_exam import (
        extract_controversy_points,
        render_cross_exam_prompt,
        run_cross_exam_protocol,
    )
    from .evidence_precheck import precheck_panel
    from .llm_client import chat_completion
    from .panel_selector import DISSENTER_PREFIXES, load_personas, load_presets, select_panel
    from .persona_agent import estimate_cost, normalize_persona_output, parse_persona_output, render_prompt, select_model
    from .validator import load_schema, validate_output
except ImportError:
    from runner.aggregator import aggregate_report, load_aggregation_rules, render_markdown_report, render_html_report
    from runner.calibration import run_calibration_check
    from runner.cross_exam import (
        extract_controversy_points,
        render_cross_exam_prompt,
        run_cross_exam_protocol,
    )
    from runner.evidence_precheck import precheck_panel
    from runner.llm_client import chat_completion
    from runner.panel_selector import DISSENTER_PREFIXES, load_personas, load_presets, select_panel
    from runner.persona_agent import estimate_cost, normalize_persona_output, parse_persona_output, render_prompt, select_model
    from runner.validator import load_schema, validate_output

SIMULATION_WARNING = (
    "⚠️ 模拟模式（未检测到 ANTHROPIC_API_KEY）：所有人格输出均为预制占位数据，"
    "不包含任何真实评审意见，仅用于验证流水线是否可运行。"
    "请勿将本次结果用于任何决策。设置 ANTHROPIC_API_KEY 后重新运行以获得真实评审。"
)

# 评审深度档位对引擎的三个实际效果：人数上限、是否交叉质证、是否校准检查。
# 与 web/backend/app/services/__init__.py 的 REVIEW_MODES 保持一致（那边多了给
# 前端展示用的 persona_count_range 下限和 description，这里只留引擎用得到的）。
REVIEW_MODE_CONFIG = {
    "quick": {"max_personas": 3, "cross_examination": False, "calibration": False},
    "standard": {"max_personas": 6, "cross_examination": True, "calibration": False},
    "full": {"max_personas": 8, "cross_examination": True, "calibration": True},
}

# 单一注册表：见 runner/task_types.py（这里 re-export 保持既有导入路径不破）
try:
    from .task_types import VALID_TASK_TYPES
except ImportError:
    from runner.task_types import VALID_TASK_TYPES


class AllPersonasFailedError(RuntimeError):
    """一个人格都没跑成时抛出——绝不允许拿空报告冒充"没发现问题"。

    为什么必须抛异常而不是返回报告：aggregate_report([]) 会产出
    primary_recommendation=""、release_risk="low"、0 条修复项的"干净"报告，
    用户读到的是"8 个人格都评了，没发现问题"，实际是 8 个全挂了。
    这种伪装成正常结果的失败比直接崩溃危险得多，所以必须让调用方无法忽略。

    异常也是两个调用方都已经能自然处理的形态：src/cli.py 的 run 命令外层
    catch Exception → 打印错误并 exit 1；web 后端 run_review_task 外层
    catch Exception → 把 Review 标成 failed 并广播 review.failed。

    failures：[{"persona_id": ..., "error": ...}]，各人格的真实报错原因。
    attempted / skipped_count：分别是实际发起的人格数、被证据预检等跳过的人格数。
    """

    def __init__(self, failures: List[dict], attempted: int, skipped_count: int = 0, message: str = None):
        self.failures = list(failures or [])
        self.attempted = attempted
        self.failed_count = len(self.failures)
        self.skipped_count = skipped_count
        super().__init__(message or self._build_message())

    def _build_message(self) -> str:
        if self.attempted == 0:
            return (
                "本次没有任何人格进入评审（预设面板为空，或全部被证据预检跳过），"
                f"跳过 {self.skipped_count} 位。没有任何人格输出，因此不产出报告。"
            )
        details = "; ".join(
            f"{f.get('persona_id', '?')}: {str(f.get('error', ''))[:200]}"
            for f in self.failures
        )
        return (
            f"全部 {self.attempted} 位人格评审失败，未产出任何有效输出，因此不产出报告。"
            f"各人格错误：{details}"
        )


def _is_dissenter(persona: dict) -> bool:
    """唱反调人格（P15 毒舌怀疑者 / P16 竞品老兵），口径复用 panel_selector 的前缀表。"""
    return any(str(persona.get("id", "")).startswith(prefix) for prefix in DISSENTER_PREFIXES)


def truncate_panel(panel_selected: List[dict], max_personas: int) -> List[dict]:
    """按档位截断面板，但必须保住"唱反调"名额。

    为什么不能直接 panel_selected[:max_personas]：select_panel 为保证面板里有异议者，
    是把 P15 **append 到列表末尾**的，从头切等于系统性地把唯一的负面视角切掉——
    quick 档（3 人）遇到预设 5 人时 P15 永远被丢弃，共识度和 release_risk 因此
    结构性偏乐观（"大家都挺看好"其实是因为唱反调的那个人没被叫来）。
    """
    if max_personas < 1 or len(panel_selected) <= max_personas:
        return panel_selected

    kept = panel_selected[:max_personas]
    if any(_is_dissenter(p) for p in kept):
        return kept

    dissenter = next((p for p in panel_selected[max_personas:] if _is_dissenter(p)), None)
    if dissenter is None:
        return kept
    # 用异议者替换掉名单里最后一位，人数上限不变（档位的省钱承诺不打折）
    return kept[:-1] + [dissenter]


def filter_genuine_controversies(controversy_points: List[dict]) -> List[dict]:
    """只保留真有分歧的议题：severity 方差 > 0 且至少 2 个不同人格参与。

    extract_controversy_points 只按方差倒序取 top3、不过滤方差为 0 的议题，于是
    只要有任何人格提了任何 issue，争议列表就恒非空 —— 单人格议题进了交叉质证后
    pro/con 是同一个 persona_id，论点还是"未从原始 persona 输出中提取到…"这类占位
    文案，用户读到的是被制造出来的对立。宁可显示"本次无显著分歧"，也不要假造争议。
    """
    genuine = []
    for cp in controversy_points:
        views = cp.get("persona_views", []) or []
        participants = {v.get("persona_id", "") for v in views}
        if len(participants) < 2:
            continue
        if (cp.get("severity_variance") or 0) <= 0:
            continue
        genuine.append(cp)
    return genuine


def load_artifact_bundle(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Artifact bundle not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8") as f:
        if ext == ".json":
            return json.load(f)
        elif ext in (".yaml", ".yml"):
            return yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported artifact format: {ext}")


def _build_simulated_output(persona: dict, task_type: str) -> dict:
    must_comment_on = persona.get("review_output", {}).get("must_comment_on", [])
    must_comment_on_check = {item: True for item in must_comment_on}
    return {
        "persona_id": persona["id"],
        "persona_name": persona.get("name", persona["id"]),
        "persona_version": "0.1.0",
        "task_type": task_type,
        "primary_stance": "观望",
        "confidence": 0.7,
        "evidence_sufficiency": 0.8,
        "evidence": [
            {
                "content": "模拟证据内容",
                "inference_level": "direct",
            }
        ],
        "scores": {
            "base": {"clarity": 3, "trust": 3},
            "task_specific": {"overall": 3},
        },
        "key_issues": [
            {
                "severity": "medium",
                "title": "模拟问题",
                "why_it_matters": "模拟原因",
                "suggested_fix": "模拟建议",
            }
        ],
        "continue_triggers": persona.get("continue_triggers", []),
        "quit_triggers": persona.get("quit_triggers", []),
        "first_scan_observations": ["模拟观察"],
        "must_comment_on_check": must_comment_on_check,
        "missing_information": [],
        "voice_sample": "（模拟占位数据，非真实评审意见）",
        "meta": {
            "caveats": ["此为模拟占位输出，不包含任何真实评审意见，请勿用于决策"],
            "is_synthetic": True,
            "is_simulated": True,
        },
    }


def run_single_persona(
    persona: dict,
    task_type: str,
    artifact_summary: str,
    artifact_texts: List[str],
    config: dict,
    artifact_bundle: dict = None,
    api_key: str = None,
    provider: str = "anthropic",
    model_override: Optional[str] = None,
    api_base: Optional[str] = None,
) -> dict:
    """api_key 显式传入优先于环境变量——多用户服务端并发跑评审时，
    绝不能靠进程全局的 os.environ 注入 key（会在用户间串 key）。

    provider/api_base：BYOK 支持任意 OpenAI 兼容服务商（DeepSeek/Kimi/通义千问/智谱GLM/
    Ollama…），不再只认 Anthropic，见 src/runner/llm_client.py。
    model_override：非 Anthropic 服务商没有"haiku/sonnet/opus"分级概念，必须传一个具体
    模型名；显式传了就优先于人格的 model_hint 分级（用户在 BYOK 里选了具体模型即是本意）。
    """
    budget_config = config.get("budget", {})
    persona_prompt_path = config.get("persona_prompt_path", "")

    model = model_override or select_model(persona, budget_config)

    prompt = render_prompt(persona, task_type, artifact_summary, persona_prompt_path, artifact_bundle)

    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            raw_output, input_tokens, output_tokens = chat_completion(
                model=model,
                prompt=prompt,
                api_key=api_key,
                provider=provider,
                api_base=api_base,
            )
            cost = estimate_cost(input_tokens, output_tokens, model, budget_config)
            output = normalize_persona_output(parse_persona_output(raw_output))
            # 身份不靠模型回填：聚合器要 output 里带 persona_id/persona_name，但不同模型
            # 未必按 schema 原样吐回来（MiniMax 就把身份塞进了 persona:{name,archetype}，
            # 顶层没有 persona_id，聚合时 KeyError 整份报告作废）。用我们已知的 persona
            # 强制注入，engine 从此不依赖模型是否老实 echo 身份字段。
            if isinstance(output, dict):
                output.setdefault("persona_id", persona["id"])
                output.setdefault("persona_name", persona.get("name", persona["id"]))
                # 聚合器对 primary_stance 是硬取值——模型偶尔漏这个字段就会让整份
                # 报告 KeyError 作废。缺了就按"观望"兜底（各任务 stance_enum 的通用中立项）。
                output.setdefault("primary_stance", "观望")
            return {
                "persona_id": persona["id"],
                "output": output,
                "prompt": prompt,
                "model": model,
                "cost": cost,
                # 真实 token 计数（来自各 provider 的 usage 字段），供上层汇总/落库
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "error": None,
            }
        except Exception as e:
            return {
                "persona_id": persona["id"],
                "output": None,
                "prompt": prompt,
                "model": model,
                "cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "error": str(e),
            }
    else:
        output = _build_simulated_output(persona, task_type)
        return {
            "persona_id": persona["id"],
            "output": output,
            "prompt": prompt,
            "model": model,
            "cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": None,
        }


def run_panel(
    task_type: str,
    artifact_bundle: dict,
    personas_path: str = None,
    presets_path: str = None,
    rules_path: str = None,
    budget_path: str = None,
    output_schema_path: str = None,
    report_schema_path: str = None,
    persona_prompt_path: str = None,
    cross_exam_prompt_path: str = None,
    report_template_path: str = None,
    html_template_path: str = None,
    max_concurrency: int = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    api_key: str = None,
    provider: str = "anthropic",
    model_override: Optional[str] = None,
    api_base: Optional[str] = None,
    selected_personas: Optional[List[str]] = None,
    mode: Optional[str] = None,
) -> dict:
    """progress_callback(done_count, total, persona_id)：每个人格评审完成后
    在 worker 线程内回调一次（线程安全计数）。回调抛异常不影响评审流程。
    默认 None 时行为与旧版完全一致。

    api_key：显式传入优先于环境变量。服务端多用户并发时必须显式传，
    避免通过进程全局 os.environ 注入导致用户间串 key（安全+计费问题）。

    provider/model_override/api_base：BYOK 选了非 Anthropic 服务商时透传下去，
    见 run_single_persona 的同名参数说明。

    selected_personas：显式指定要哪几个具体角色（id 列表），跳过 select_panel
    按 task_type 预设自动选人的逻辑——对话里"呼叫角色"用这个。id 一个都不在
    personas_path 对应人格包里时（拼错/串包），静默回落到自动选人，不让评审
    因为一次无效的显式指定就直接跑空面板。

    mode：评审深度档位（quick/standard/full，见 REVIEW_MODE_CONFIG）——控制人数
    上限、是否交叉质证、是否校准检查。None（CLI/旧调用方）保持历史行为：不截人数、
    交叉质证和校准都跑，等价于 full。此前 Web v2 链路的 mode 只落库不进引擎，
    "快速扫一眼"实际跑的是全量流程，人数和钱都没省——这个参数就是补那条断链的。"""
    if task_type not in VALID_TASK_TYPES:
        raise ValueError(f"Unknown task type: {task_type}")

    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if personas_path is None:
        personas_path = os.path.join(base, "src", "personas", "game-core.yaml")
    if presets_path is None:
        presets_path = os.path.join(base, "src", "presets", "panel-presets.yaml")
    if budget_path is None:
        budget_path = os.path.join(base, "src", "config", "budget.yaml")
    if rules_path is None:
        rules_path = os.path.join(base, "src", "config", "aggregation-rules.yaml")
    if output_schema_path is None:
        output_schema_path = os.path.join(base, "src", "schemas", "output-schema.json")
    if report_schema_path is None:
        report_schema_path = os.path.join(base, "src", "schemas", "report-schema.json")
    if persona_prompt_path is None:
        persona_prompt_path = os.path.join(base, "src", "templates", "persona-prompt.md")
    if cross_exam_prompt_path is None:
        cross_exam_prompt_path = os.path.join(base, "src", "templates", "cross-exam-prompt.md")
    if report_template_path is None:
        report_template_path = os.path.join(base, "src", "templates", "report-template.md")
    if html_template_path is None:
        html_template_path = os.path.join(base, "src", "templates", "report-template.html")

    effective_api_key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY")
    simulated = not effective_api_key
    if simulated:
        print(f"\n{SIMULATION_WARNING}\n", flush=True)

    personas = load_personas(personas_path)
    presets = load_presets(presets_path)

    with open(budget_path, "r", encoding="utf-8") as f:
        budget_config = yaml.safe_load(f)

    rules = load_aggregation_rules(rules_path)
    output_schema = load_schema(output_schema_path)

    # 材料形态统一：对话链路（/ask）发的是 {type:'text', text:内容}，Wizard 发的是
    # {type:字段名, description:内容}。引擎的模板/证据抽取全按 description 读——不统一
    # 的话对话评审的正文（在 text 键里）根本到不了人格手上，人格拿到空材料。
    # 这里把 text 补进 description（已有 description 的 Wizard 材料原样不动），
    # 图片材料（image_data）不碰，交给 render_prompt 走多模态。
    _materials = artifact_bundle.get("materials", []) or []
    for _m in _materials:
        if _m.get("type") != "image" and not _m.get("description") and _m.get("text"):
            _m["description"] = _m["text"]

    artifact_texts = [
        (m.get("description") or m.get("text") or "")
        for m in _materials
        if m.get("type") != "image"
    ]
    artifact_summary = artifact_bundle.get("title", "")

    panel_selected = None
    panel_skipped = []
    if selected_personas:
        panel_selected = [p for p in personas if p["id"] in selected_personas]
        if not panel_selected:
            panel_selected = None  # 一个都没匹配上——回落自动选人，别跑空面板

    if panel_selected is None:
        panel = select_panel(task_type, personas, presets)
        panel_selected = panel["selected"]
        panel_skipped = panel["skipped"]

    mode_config = REVIEW_MODE_CONFIG.get(mode) if mode else None
    if mode_config:
        panel_selected = truncate_panel(panel_selected, mode_config["max_personas"])

    precheck = precheck_panel(panel_selected, artifact_bundle)
    valid_personas = precheck["valid_personas"]
    skipped_count = len(panel_skipped) + len(precheck["skipped_personas"])

    config = {
        "budget": budget_config,
        "persona_prompt_path": persona_prompt_path,
    }

    # 人格评审彼此独立，是 I/O 密集（等 LLM 返回）任务，用线程池并发。
    # run_single_persona 内部已兜住异常并返回 error 字段，故 future 不会抛。
    if max_concurrency is None:
        max_concurrency = int(os.environ.get("AUDIENCELENS_MAX_CONCURRENCY", "6"))
    workers = max(1, min(max_concurrency, len(valid_personas))) if valid_personas else 1

    # 实时进度：线程安全计数器，每个人格完成后在 worker 线程内回调
    total_personas = len(valid_personas)
    progress_lock = threading.Lock()
    done_counter = [0]

    def _run(persona):
        result = run_single_persona(
            persona, task_type, artifact_summary, artifact_texts, config, artifact_bundle,
            api_key=effective_api_key,
            provider=provider,
            model_override=model_override,
            api_base=api_base,
        )
        if progress_callback is not None:
            with progress_lock:
                done_counter[0] += 1
                done = done_counter[0]
            try:
                progress_callback(done, total_personas, persona["id"])
            except Exception:
                # 进度回调故障不得影响评审本身
                pass
        return result

    if workers <= 1 or len(valid_personas) <= 1:
        persona_results = [_run(p) for p in valid_personas]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            # 按提交顺序收集 future 结果，保证与输入人格顺序一致（确定性）
            futures = [ex.submit(_run, p) for p in valid_personas]
            persona_results = [f.result() for f in futures]

    persona_outputs = []
    failed_personas = []
    for r in persona_results:
        if r["output"] is not None:
            validation = validate_output(
                r["output"],
                next((p for p in valid_personas if p["id"] == r["persona_id"]), {}),
                output_schema,
                artifact_texts,
            )
            r["validation"] = validation
            persona_outputs.append(r["output"])
        else:
            # 失败的人格必须被记下来并透出去：以前这里直接 continue，
            # 每个人格的 error 从头到尾没有一条带出 run_panel。
            failed_personas.append({
                "persona_id": r["persona_id"],
                "error": r.get("error") or "未知错误",
                "model": r.get("model", ""),
            })

    # 全盘失败（含"一个人格都没进来"）绝不产出报告——见 AllPersonasFailedError 的说明
    if not persona_outputs:
        raise AllPersonasFailedError(
            failures=failed_personas,
            attempted=len(persona_results),
            skipped_count=skipped_count,
        )

    attempted_count = len(persona_results)
    succeeded_count = len(persona_outputs)
    failed_count = len(failed_personas)
    degraded = failed_count > 0

    cross_exam_enabled = mode_config["cross_examination"] if mode_config else True
    cross_exam_data = None
    if cross_exam_enabled and persona_outputs and cross_exam_prompt_path:
        controversy_points = filter_genuine_controversies(
            extract_controversy_points(persona_outputs)
        )
        if controversy_points:
            cross_exam_prompt = render_cross_exam_prompt(
                controversy_points, persona_outputs, cross_exam_prompt_path
            )
            cross_exam_data = run_cross_exam_protocol(
                persona_outputs, controversy_points
            )

    report = aggregate_report(
        persona_outputs,
        task_type,
        artifact_summary,
        rules,
        cross_exam_data,
    )

    if simulated:
        report["simulation_notice"] = SIMULATION_WARNING

    # 降级标记进 report 本体：web 后端把 report 整份落库（report_json），
    # 前端读的也是它——只放在返回值顶层的话，重新打开历史报告就看不到"本次有人
    # 没跑成"了，那份报告又会被当成完整结论。
    report["degradation"] = {
        "degraded": degraded,
        "attempted_count": attempted_count,
        "succeeded_count": succeeded_count,
        "failed_count": failed_count,
        "failed_personas": failed_personas,
        "notice": (
            f"本次有 {failed_count} 位人格未能完成评审，以下结论仅基于 {succeeded_count} 位人格的输出。"
            if degraded
            else ""
        ),
    }

    calibration_enabled = mode_config["calibration"] if mode_config else True
    calibration = run_calibration_check(persona_outputs, artifact_texts) if calibration_enabled else None

    markdown = ""
    if report_template_path:
        markdown = render_markdown_report(report, report_template_path)
        if simulated:
            markdown = f"> **{SIMULATION_WARNING}**\n\n{markdown}"
        # 报告模板不认识 degradation 字段（模板不在本次改动范围），横幅在这里补上，
        # 保证降级信息在渲染产物里也看得见，而不是只躺在 JSON 里
        if degraded:
            markdown = f"> **⚠️ {report['degradation']['notice']}**\n\n{markdown}"

    report["_persona_outputs"] = persona_outputs
    html = ""
    if html_template_path:
        html = render_html_report(report, html_template_path)
        if simulated and "<body" in html:
            banner = (
                '<div style="background:#fef3c7;border:2px solid #d97706;color:#92400e;'
                'padding:12px 16px;margin:8px;border-radius:8px;font-weight:bold;">'
                f"{SIMULATION_WARNING}</div>"
            )
            idx = html.index(">", html.index("<body")) + 1
            html = html[:idx] + banner + html[idx:]
        if degraded and "<body" in html:
            failed_list = "、".join(f["persona_id"] for f in failed_personas)
            banner = (
                '<div style="background:#fee2e2;border:2px solid #dc2626;color:#991b1b;'
                'padding:12px 16px;margin:8px;border-radius:8px;font-weight:bold;">'
                f"⚠️ {report['degradation']['notice']}未完成的人格：{failed_list}"
                "</div>"
            )
            idx = html.index(">", html.index("<body")) + 1
            html = html[:idx] + banner + html[idx:]
    del report["_persona_outputs"]

    total_cost = sum(r["cost"] for r in persona_results)
    total_input_tokens = sum(r.get("input_tokens", 0) for r in persona_results)
    total_output_tokens = sum(r.get("output_tokens", 0) for r in persona_results)

    return {
        "report": report,
        "markdown": markdown,
        "html": html,
        "calibration": calibration,
        "simulated": simulated,
        # 降级标记也放顶层：调用方在落库前就能判断要不要提示用户 / 要不要按满额计费
        "degraded": degraded,
        "failed_personas": failed_personas,
        "cost_summary": {
            "total_cost": total_cost,
            # persona_count 必须是真实成功数：以前算的是 len(persona_results)（把失败的
            # 也算进去），于是"8 个人格"的说法和计费都建立在没跑成的人格上。
            "persona_count": succeeded_count,
            "attempted_count": attempted_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="AudienceLens 多人评审系统 CLI")
    parser.add_argument("task_type", choices=VALID_TASK_TYPES, help="评审任务类型")
    parser.add_argument("artifact_path", help="评审材料包路径")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    parser.add_argument("--personas", default=None, help="Persona YAML 路径")
    parser.add_argument("--presets", default=None, help="Preset YAML 路径")

    args = parser.parse_args()

    artifact_bundle = load_artifact_bundle(args.artifact_path)

    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    personas_path = args.personas or os.path.join(src_root, "personas", "game-core.yaml")
    presets_path = args.presets or os.path.join(src_root, "presets", "panel-presets.yaml")
    rules_path = os.path.join(src_root, "config", "aggregation-rules.yaml")
    budget_path = os.path.join(src_root, "config", "budget.yaml")
    output_schema_path = os.path.join(src_root, "schemas", "output-schema.json")
    report_schema_path = os.path.join(src_root, "schemas", "report-schema.json")
    persona_prompt_path = os.path.join(src_root, "templates", "persona-prompt.md")
    cross_exam_prompt_path = os.path.join(src_root, "templates", "cross-exam-prompt.md")
    report_template_path = os.path.join(src_root, "templates", "report-template.md")

    try:
        result = run_panel(
            task_type=args.task_type,
            artifact_bundle=artifact_bundle,
            personas_path=personas_path,
            presets_path=presets_path,
            rules_path=rules_path,
            budget_path=budget_path,
            output_schema_path=output_schema_path,
            report_schema_path=report_schema_path,
            persona_prompt_path=persona_prompt_path,
            cross_exam_prompt_path=cross_exam_prompt_path,
            report_template_path=report_template_path,
        )
    except AllPersonasFailedError as e:
        # 一份文件都不写：宁可什么都没有，也不要在磁盘上留一份"无风险"的假报告
        print("=" * 60)
        print(f"评审失败：{e}")
        print("=" * 60)
        raise SystemExit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    json_path = os.path.join(
        args.output_dir, f"{args.task_type}_report.json"
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result["report"], f, ensure_ascii=False, indent=2)

    md_path = os.path.join(
        args.output_dir, f"{args.task_type}_report.md"
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result["markdown"])

    html_path = os.path.join(
        args.output_dir, f"{args.task_type}_report.html"
    )
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(result["html"])

    if result.get("simulated"):
        print("=" * 60)
        print(SIMULATION_WARNING)
        print("=" * 60)
