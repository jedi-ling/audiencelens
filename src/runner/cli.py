import argparse
import concurrent.futures
import json
import os
from typing import List

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
) -> dict:
    budget_config = config.get("budget", {})
    persona_prompt_path = config.get("persona_prompt_path", "")

    model = select_model(persona, budget_config)

    prompt = render_prompt(persona, task_type, artifact_summary, persona_prompt_path, artifact_bundle)

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_output = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
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
) -> dict:
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

    simulated = not os.environ.get("ANTHROPIC_API_KEY")
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

    def _run(persona):
        return run_single_persona(
            persona, task_type, artifact_summary, artifact_texts, config, artifact_bundle
        )

    if workers <= 1 or len(valid_personas) <= 1:
        persona_results = [_run(p) for p in valid_personas]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            # executor.map 按输入顺序返回结果，保证确定性
            persona_results = list(ex.map(_run, valid_personas))

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
