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
    from .panel_selector import load_personas, load_presets, select_panel
    from .persona_agent import estimate_cost, parse_persona_output, render_prompt, select_model
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
    from runner.panel_selector import load_personas, load_presets, select_panel
    from runner.persona_agent import estimate_cost, parse_persona_output, render_prompt, select_model
    from runner.validator import load_schema, validate_output

SIMULATION_WARNING = (
    "⚠️ 模拟模式（未检测到 ANTHROPIC_API_KEY）：所有人格输出均为预制占位数据，"
    "不包含任何真实评审意见，仅用于验证流水线是否可运行。"
    "请勿将本次结果用于任何决策。设置 ANTHROPIC_API_KEY 后重新运行以获得真实评审。"
)

VALID_TASK_TYPES = [
    "steam_page_review",
    "demo_first_play",
    "concept_review",
    "monetization_review",
    "looking_for_party_post",
    "update_announcement_review",
    "devlog_review",
    "kickstarter_review",
    "localization_review",
    "discord_community_review",
    # 通用产品向任务类型（不限游戏）——见 src/personas/general-consumer.yaml
    "product_feedback_review",
    "pricing_page_review",
    "onboarding_review",
    # 创业项目评审（BP/路演/申报表）——见 src/personas/startup-panel.yaml
    "pitch_review",
]


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
            output = parse_persona_output(raw_output)
            return {
                "persona_id": persona["id"],
                "output": output,
                "prompt": prompt,
                "model": model,
                "cost": cost,
                "error": None,
            }
        except Exception as e:
            return {
                "persona_id": persona["id"],
                "output": None,
                "prompt": prompt,
                "model": model,
                "cost": 0.0,
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
) -> dict:
    """progress_callback(done_count, total, persona_id)：每个人格评审完成后
    在 worker 线程内回调一次（线程安全计数）。回调抛异常不影响评审流程。
    默认 None 时行为与旧版完全一致。

    api_key：显式传入优先于环境变量。服务端多用户并发时必须显式传，
    避免通过进程全局 os.environ 注入导致用户间串 key（安全+计费问题）。

    provider/model_override/api_base：BYOK 选了非 Anthropic 服务商时透传下去，
    见 run_single_persona 的同名参数说明。"""
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

    artifact_texts = [
        m.get("description", "") for m in artifact_bundle.get("materials", [])
    ]
    artifact_summary = artifact_bundle.get("title", "")

    panel = select_panel(task_type, personas, presets)

    precheck = precheck_panel(panel["selected"], artifact_bundle)
    valid_personas = precheck["valid_personas"]
    skipped_count = len(panel["skipped"]) + len(precheck["skipped_personas"])

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

    cross_exam_data = None
    if persona_outputs and cross_exam_prompt_path:
        controversy_points = extract_controversy_points(persona_outputs)
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

    calibration = run_calibration_check(persona_outputs, artifact_texts)

    markdown = ""
    if report_template_path:
        markdown = render_markdown_report(report, report_template_path)
        if simulated:
            markdown = f"> **{SIMULATION_WARNING}**\n\n{markdown}"

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
    del report["_persona_outputs"]

    total_cost = sum(r["cost"] for r in persona_results)

    return {
        "report": report,
        "markdown": markdown,
        "html": html,
        "calibration": calibration,
        "simulated": simulated,
        "cost_summary": {
            "total_cost": total_cost,
            "persona_count": len(persona_results),
            "skipped_count": skipped_count,
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
