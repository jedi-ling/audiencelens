"""
AudienceLens CLI v0.3
Multi-Agent Cross-Examination Framework for Synthetic Audience Review
"""

import json
import os
import re
import sys
from pathlib import Path

# 路径引导：让 `python -m src.cli`、`audiencelens`（console_script）、直接运行三种方式
# 都能解析 runner.* / harness.* / tools.* 这套全项目统一的裸导入。
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SRC_DIR)
for _p in (_SRC_DIR, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import click
import yaml

from runner import cli as runner_cli
from runner.task_types import default_personas_path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

VERSION = "0.3.0"

if HAS_RICH:
    console = Console()
else:
    console = None

PROJECT_ROOT = Path(__file__).parent

# 技能 → 注入给每个人格的提示语。
#
# 为什么在这里再写一份：Web 链路的权威副本在
# web/backend/app/services/__init__.py（PersonaService._SKILL_PROMPT_HINTS + apply_skill_hint），
# 但 src/ 是可以脱离 web/ 单独发包的引擎（PyPI 的 audiencelens），不能反向依赖后端。
# 以前这里干脆什么都不做——`--skill` 收下就丢，终端还打着"技能: red-team-audience"，
# 于是 CLI 跑出来的是普通评审，Web 上同名技能跑出来是红队视角，两条链路结果不一样。
# 键用 CLI 的连字符写法，值与后端下划线写法的那份逐字一致；
# tests/test_public_claims.py 会比对两份，漂移就测试失败。
SKILL_PROMPT_HINTS = {
    "red-team-audience": (
        "本次评审请采用红队/对抗性视角：优先挖掘产品的弱点、风险和「劝退点」，"
        "而不是常规的体验反馈——目标是帮团队在正式上线前找出最容易被喷、被弃、被吐槽的地方。"
    ),
    "audience-panel": (
        "本次评审请以非游戏、大众消费产品的视角来看——不要套用硬核玩家的评判标准，"
        "关注普通用户/消费者会不会用、看不看得懂、愿不愿意留下。"
    ),
    # synthetic-playtest 没有提示语：它就是默认的评审口径，加一句"请正常评审"只会浪费上下文。
}


def apply_skill_hint(artifact_bundle: dict, skill: str) -> dict:
    """把技能提示语当成一条材料塞进 bundle 最前面，与 Web 链路同一种做法。

    不改 persona-prompt 模板、不新开参数，是因为 render_prompt 本来就读
    artifact_bundle["materials"]，插一条进去每个人格都会看到，成本最低且不引入新分支。
    没有对应提示语时原样返回（返回的是同一个对象，调用方不要依赖"总是拷贝"）。
    """
    hint = SKILL_PROMPT_HINTS.get(skill or "", "")
    if not hint:
        return artifact_bundle
    bundle = dict(artifact_bundle or {})
    materials = list(bundle.get("materials") or [])
    materials.insert(0, {"type": "text", "text": f"[评审技能：{skill}] {hint}"})
    bundle["materials"] = materials
    return bundle


def _clean(msg: str) -> str:
    """去掉 rich 标记"""
    return re.sub(r'\[/?[a-z_ ]+\]', '', str(msg))


def _print(msg: str = ""):
    """统一输出"""
    if HAS_RICH and console:
        console.print(msg)
    else:
        print(_clean(msg))


@click.group()
@click.version_option(version=VERSION, prog_name="audiencelens")
def main():
    """AudienceLens - 多智能体交叉质询合成评审框架"""
    pass


@main.command()
@click.argument("skill", type=click.Choice(["synthetic-playtest", "audience-panel", "red-team-audience"]))
@click.argument("task_type")
@click.argument("artifact", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["quick", "standard", "full"]), default="standard", help="评审模式")
@click.option("--output-dir", type=click.Path(), default="./output", help="输出目录")
@click.option("--personas", type=click.Path(exists=True), help="自定义人物目录")
@click.option("--adaptive-panel/--fixed-panel", default=False, help="按边际价值逐步扩展人格面板")
def run(skill, task_type, artifact, mode, output_dir, personas, adaptive_panel):
    """运行合成评审"""
    _print(f"\n=== AudienceLens v{VERSION} ===")
    _print(f"技能: {skill} | 任务: {task_type} | 模式: {mode}\n")

    try:
        artifact_bundle = runner_cli.load_artifact_bundle(artifact)
        # skill 同理：以前也只在上面那行 _print 里露个脸。选了 red-team-audience
        # 却跑出一份普通评审，用户没有任何办法看出技能没生效。
        artifact_bundle = apply_skill_hint(artifact_bundle, skill)
        # mode 必须真的传下去。以前只在上面那行 _print 里露个脸就被丢掉，
        # run_panel 收不到 mode 就走默认档：用户 --mode quick 想省钱，
        # 实际跑的是全量面板 + 交叉质询 + 校准，钱按最贵的档花，
        # 而终端还明明白白打着「模式: quick」。
        result = runner_cli.run_panel(
            task_type=task_type,
            artifact_bundle=artifact_bundle,
            personas_path=personas,
            mode=mode,
            adaptive_panel=adaptive_panel,
        )

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        report_path = output_path / f"{task_type}_report.json"
        markdown_path = output_path / f"{task_type}_report.md"
        html_path = output_path / f"{task_type}_report.html"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result["report"], f, ensure_ascii=False, indent=2)
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(result.get("markdown", ""))
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(result.get("html", ""))

        _print("评审完成！")
        _print(f"输出目录: {output_path}")
    except Exception as e:
        _print(f"错误: {e}")
        sys.exit(1)


@main.command("personas-validate")
@click.argument("path", type=click.Path(exists=True))
@click.option("--schema", type=click.Path(), default=None, help="自定义 JSON Schema 路径")
def personas_validate(path, schema):
    """校验人物 YAML 文件"""
    from runner.validator import validate_schema

    path = Path(path)
    schema_path = Path(schema) if schema else PROJECT_ROOT / "schemas" / "persona-schema.json"

    with open(schema_path, "r", encoding="utf-8") as f:
        persona_schema = json.load(f)

    yaml_files = list(path.glob("**/*.yaml")) if path.is_dir() else [path]

    if not yaml_files:
        _print("未找到 YAML 文件")
        return

    total_personas = 0
    passed_files = 0
    failed_files = 0
    rows = []

    for yaml_file in yaml_files:
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            personas_list = data.get("personas", [data] if "id" in data else [])
            file_issues = []

            for persona in personas_list:
                total_personas += 1
                result = validate_schema(persona, persona_schema)
                if not result["valid"]:
                    file_issues.extend(result["errors"][:3])

            if file_issues:
                rows.append((yaml_file.name, str(len(personas_list)), "FAIL", "; ".join(file_issues[:2])))
                failed_files += 1
            else:
                rows.append((yaml_file.name, str(len(personas_list)), "PASS", "-"))
                passed_files += 1

        except Exception as e:
            rows.append((yaml_file.name, "?", "ERROR", str(e)[:60]))
            failed_files += 1

    # 输出表格
    if HAS_RICH and console:
        table = Table(title="人物校验结果")
        table.add_column("文件", style="cyan")
        table.add_column("人物数", justify="right")
        table.add_column("状态", style="bold")
        table.add_column("问题", style="yellow")
        for row in rows:
            status = f"[green]{row[2]}[/green]" if row[2] == "PASS" else f"[red]{row[2]}[/red]"
            table.add_row(row[0], row[1], status, row[3])
        console.print(table)
    else:
        print(f"\n{'文件':<30} {'人物数':>6} {'状态':>6} {'问题'}")
        print("-" * 70)
        for row in rows:
            print(f"{row[0]:<30} {row[1]:>6} {row[2]:>6} {row[3]}")

    _print(f"\n总计: {len(yaml_files)} 文件, {total_personas} 人物 | {passed_files} 通过 {failed_files} 失败")

    if failed_files > 0:
        sys.exit(1)


@main.command("harness-evaluate")
@click.argument("report_path", type=click.Path(exists=True))
@click.option("--format", "output_format", type=click.Choice(["table", "json", "markdown"]), default="table", help="输出格式")
@click.option("--threshold-file", type=click.Path(exists=True), default=None, help="自定义阈值文件")
def harness_evaluate(report_path, output_format, threshold_file):
    """8维 Harness 评估"""
    try:
        from harness.evaluator import evaluate_report

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        thresholds = None
        if threshold_file:
            with open(threshold_file, "r", encoding="utf-8") as f:
                thresholds = yaml.safe_load(f)

        result = evaluate_report(report, thresholds=thresholds)

        if output_format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif output_format == "markdown":
            _print_markdown_result(result)
        else:
            _print_table_result(result)

    except ImportError as e:
        _print(f"Harness 评估模块未安装: {e}")
        sys.exit(1)
    except Exception as e:
        _print(f"评估错误: {e}")
        sys.exit(1)


@main.command("parity-check")
@click.option("--synthetic", type=click.Path(exists=True), required=True, help="合成评审 JSON 文件")
@click.option("--human", type=click.Path(exists=True), required=True, help="人类评审 JSON 文件")
def parity_check(synthetic, human):
    """对等验证：合成评审 vs 人类评审"""
    try:
        from tools.parity_check import compute_parity

        with open(synthetic, "r", encoding="utf-8") as f:
            synthetic_data = json.load(f)
        with open(human, "r", encoding="utf-8") as f:
            human_data = json.load(f)

        result = compute_parity(synthetic_data, human_data)

        if HAS_RICH and console:
            table = Table(title="对等验证结果")
            table.add_column("维度", style="cyan")
            table.add_column("权重", justify="right")
            table.add_column("得分", justify="right")
            table.add_column("状态", style="bold")
            for dim in result["dimensions"]:
                status = "[green]PASS[/green]" if dim["passed"] else "[red]FAIL[/red]"
                table.add_row(dim["name"], f"{dim['weight']:.2f}", f"{dim['score']:.3f}", status)
            console.print(table)
        else:
            print(f"\n{'维度':<20} {'权重':>6} {'得分':>8} {'状态'}")
            print("-" * 50)
            for dim in result["dimensions"]:
                status = "PASS" if dim["passed"] else "FAIL"
                print(f"{dim['name']:<20} {dim['weight']:>6.2f} {dim['score']:>8.3f} {status}")

        overall = result["overall_score"]
        _print(f"\n综合得分: {overall:.3f} | 等级: {_grade(overall)}")

    except ImportError:
        _print("提示: parity_check 模块需要适配")
        _print(f"  命令: python tools/parity_check.py --synthetic {synthetic} --human {human}")
    except Exception as e:
        _print(f"错误: {e}")
        sys.exit(1)


@main.command("benchmark-compare")
@click.option("--reference", type=click.Path(exists=True), required=True, help="真人研究参考 JSON")
@click.option("--candidate", "candidates", multiple=True, required=True, help="候选：name=path.json，可重复")
@click.option("--output", type=click.Path(), default=None, help="保存完整 JSON 结果")
def benchmark_compare(reference, candidates, output):
    """统一比较 AudienceLens、单次模型、人工快评等方法。"""
    from tools.benchmark_compare import compare_methods, load_candidate

    try:
        with open(reference, "r", encoding="utf-8") as f:
            reference_data = json.load(f)
        methods = dict(load_candidate(spec) for spec in candidates)
        result = compare_methods(methods, reference_data)
        _print(f"参考样本: n={result['reference_sample_size']}" + ("（低置信度）" if result["low_confidence"] else ""))
        for row in result["methods"]:
            cost = "—" if row["cost_usd"] is None else f"${row['cost_usd']:.2f}"
            duration = "—" if row["duration_minutes"] is None else f"{row['duration_minutes']}m"
            _print(f"  #{row['rank']} {row['method']}: {row['overall_score']:.3f} | 成本 {cost} | 用时 {duration}")
        _print(f"胜出方法: {result['winner']} | 分差: {result['score_spread']:.3f}")
        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            _print(f"结果已写入: {output}")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(str(exc))


@main.command("benchmark-suite")
@click.option("--manifest", type=click.Path(exists=True), required=True, help="跨案例套件 manifest.json")
@click.option("--output", type=click.Path(), default=None, help="保存聚合 JSON 结果")
def benchmark_suite(manifest, output):
    """运行跨案例基准，报告均值、方差、胜率和配对置信区间。"""
    from tools.benchmark_suite import run_manifest

    try:
        result = run_manifest(manifest)
        confidence = "低置信度" if result["low_confidence"] else ""
        _print(f"套件: {result['suite_name']} | 案例: {result['case_count']} {confidence}")
        for row in result["methods"]:
            _print(f"  {row['method']}: 均值 {row['mean_score']:.3f} ± {row['score_stdev']:.3f} | 胜率 {row['win_rate']:.1%}")
        paired = result["paired_comparison"]
        _print(f"{paired['target']} vs {paired['baseline']}: Δ={paired['mean_delta']} | 95% CI={paired['ci95']} | {paired['conclusion']}")
        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            _print(f"结果已写入: {output}")
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(str(exc))


@main.command("benchmark-init")
@click.option("--dir", "root_dir", type=click.Path(), required=True, help="试点数据根目录")
@click.option("--case-id", required=True, help="项目匿名编号，如 studio-001")
@click.option("--title", default="", help="内部项目名称（可留空）")
def benchmark_init(root_dir, case_id, title):
    """创建一个不会覆盖已有数据的三方盲测案例。"""
    from tools.benchmark_scaffold import init_case

    try:
        result = init_case(root_dir, case_id, title)
        _print(f"案例已创建: {result['case_dir']}")
        _print(f"套件清单: {result['manifest']}")
    except (ValueError, FileExistsError, OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(str(exc))


@main.command("stereotype-eval")
@click.option("--llm", "use_llm", is_flag=True, help="启用 LLM 复审层（需 ANTHROPIC_API_KEY）")
def stereotype_eval(use_llm):
    """刻板印象检测评测：在标注回归集上算准确率/精确率/召回率"""
    import os

    if use_llm and not os.environ.get("ANTHROPIC_API_KEY"):
        _print("[red]错误: --llm 需要设置 ANTHROPIC_API_KEY[/red]")
        sys.exit(1)

    from tools.stereotype_eval import evaluate

    method = "regex+llm" if use_llm else "regex"
    _print(f"\n评测方法: [bold]{method}[/bold]")
    r = evaluate(use_llm=use_llm)

    if HAS_RICH and console:
        table = Table(title="刻板印象检测评测结果")
        table.add_column("指标", style="cyan")
        table.add_column("值", justify="right")
        table.add_row("用例数", str(r["total"]))
        table.add_row("准确率", f"{r['accuracy']:.1%}")
        table.add_row("精确率", f"{r['precision']:.1%}")
        table.add_row("召回率", f"{r['recall']:.1%}")
        table.add_row("TP/FP/TN/FN", f"{r['tp']}/{r['fp']}/{r['tn']}/{r['fn']}")
        console.print(table)
    else:
        print(f"用例数: {r['total']}")
        print(f"准确率: {r['accuracy']:.1%}  精确率: {r['precision']:.1%}  召回率: {r['recall']:.1%}")
        print(f"TP={r['tp']} FP={r['fp']} TN={r['tn']} FN={r['fn']}")

    if r["errors"]:
        _print("\n[yellow]错误样本:[/yellow]")
        for kind, text in r["errors"]:
            _print(f"  [{kind}] {text[:60]}")


@main.command()
@click.argument("task_type")
@click.argument("artifact", type=click.Path(exists=True))
@click.option("--personas", type=click.Path(exists=True), default=None, help="Persona YAML 路径（默认按任务类型取，见 runner/task_types.py）")
@click.option("--limit", type=int, default=4, help="参与实验的人格数量")
@click.option("--model", default="claude-haiku-4-5-20251001", help="实验用模型")
@click.option("--conditions", default="full,no_behavior,bare", help="逗号分隔的实验条件")
@click.option("--output", "output_path", type=click.Path(), default=None, help="结果 JSON 输出路径")
def ablation(task_type, artifact, personas, limit, model, conditions, output_path):
    """人格分化消融实验：full vs no_behavior vs bare（需 ANTHROPIC_API_KEY）"""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        _print("[red]错误: 消融实验需要 ANTHROPIC_API_KEY，模拟数据上测分化度没有意义[/red]")
        sys.exit(1)

    from harness.ablation import run_ablation
    from runner.panel_selector import load_personas

    artifact_bundle = runner_cli.load_artifact_bundle(artifact)
    personas_path = personas or default_personas_path(task_type, str(PROJECT_ROOT / "personas"))
    persona_prompt_path = str(PROJECT_ROOT / "templates" / "persona-prompt.md")

    all_personas = load_personas(personas_path)
    panel = all_personas[:limit]
    condition_list = [c.strip() for c in conditions.split(",") if c.strip()]

    _print(f"\n=== 人格分化消融实验 ===")
    _print(f"人格: {[p['id'] for p in panel]}")
    _print(f"条件: {condition_list} | 模型: {model}\n")

    result = run_ablation(
        personas=panel,
        task_type=task_type,
        artifact_bundle=artifact_bundle,
        persona_prompt_path=persona_prompt_path,
        model=model,
        conditions=condition_list,
        progress=lambda cond, pid: _print(f"  [{cond}] {pid} 完成"),
    )

    _print(f"\n相似度方法: {result['similarity_method']}")
    if HAS_RICH and console:
        table = Table(title="分化度指标（越高越分化）")
        table.add_column("条件", style="cyan")
        table.add_column("议题分化度", justify="right")
        table.add_column("严重度JS散度", justify="right")
        table.add_column("立场熵", justify="right")
        table.add_column("失败数", justify="right")
        for cond, m in result["conditions"].items():
            table.add_row(
                cond,
                f"{m['issue_divergence']:.3f}",
                f"{m['severity_js']:.3f}",
                f"{m['stance_entropy']:.3f}",
                str(m["failures"]),
            )
        console.print(table)
    else:
        print(f"\n{'条件':<14} {'议题分化':>8} {'JS散度':>8} {'立场熵':>8} {'失败':>4}")
        print("-" * 50)
        for cond, m in result["conditions"].items():
            print(f"{cond:<14} {m['issue_divergence']:>8.3f} {m['severity_js']:>8.3f} {m['stance_entropy']:>8.3f} {m['failures']:>4}")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        _print(f"\n结果已保存: {output_path}")


@main.command("cross-exam-ablation")
@click.argument("task_type")
@click.argument("artifact", type=click.Path(exists=True))
@click.option("--personas", type=click.Path(exists=True), default=None, help="Persona YAML 路径（默认按任务类型取，见 runner/task_types.py）")
@click.option("--panel", default=None, help="逗号分隔的人格 id，固定面板；不传则按 task_type 自动选人")
@click.option("--conditions", default="none,moderated,multi_agent", help="逗号分隔的实验条件（必须含 none 基线）")
@click.option("--output", "output_path", type=click.Path(), default=None, help="结果 JSON 输出路径")
def cross_exam_ablation(task_type, artifact, personas, panel, conditions, output_path):
    """交叉质询消融：关掉反驳，报告会变吗？（需 ANTHROPIC_API_KEY）

    人格评审只跑一次、三个条件共用，因此反驳是唯一变量。
    注意：本实验能证伪（没变=纯成本），不能证实（变了≠变好了）。
    """
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        _print("[red]错误: 交叉质询消融需要 ANTHROPIC_API_KEY，模拟模式下一次反驳都不发[/red]")
        sys.exit(1)

    from harness.cross_exam_ablation import run_cross_exam_ablation

    artifact_bundle = runner_cli.load_artifact_bundle(artifact)
    condition_list = [c.strip() for c in conditions.split(",") if c.strip()]
    panel_ids = [p.strip() for p in panel.split(",") if p.strip()] if panel else None

    _print("\n=== 交叉质询消融实验 ===")
    _print(f"条件: {condition_list}")
    _print("[dim]人格评审只跑一次，三个条件共用同一批输出[/dim]\n")

    result = run_cross_exam_ablation(
        task_type=task_type,
        artifact_bundle=artifact_bundle,
        personas_path=personas,
        selected_personas=panel_ids,
        conditions=condition_list,
        progress=lambda cond, info: _print(f"  [{cond}] {info}"),
    )

    _print(f"\n面板: {result['panel']}")
    _print(f"争议点: {result['controversy_points_found']} | 相似度方法: {result['similarity_method']}")

    rows = []
    for cond, m in result["conditions"].items():
        f = m["priority_fixes"]
        rows.append((
            cond, m["cross_exam_mode"], str(f["net_new"]), str(f["dropped"]),
            f"{f['rank_churn']:.3f}", f"{f['delta_ratio']:.3f}",
            f"{m['vote_changes']}/{m['suppressed_changes']}",
            f"{m['cost']['cost_usd']:.4f}",
        ))

    headers = ["条件", "反驳模式", "新增", "删除", "排序位移", "改动率", "改票/被抑制", "成本$"]
    if HAS_RICH and console:
        table = Table(title="相对 none 基线的报告差异")
        for h, style in zip(headers, ["cyan"] + [None] * 7):
            table.add_column(h, style=style, justify="left" if style else "right")
        for r in rows:
            table.add_row(*r)
        console.print(table)
    else:
        print("\n" + "  ".join(f"{h:>10}" for h in headers))
        print("-" * 90)
        for r in rows:
            print("  ".join(f"{c:>10}" for c in r))

    v = result["verdict"]
    _print(f"\n[bold]结论[/bold]: {v['headline']}")
    _print(f"[yellow]{v['caveat']}[/yellow]")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        _print(f"\n结果已保存: {output_path}")


@main.command("identity-invariance")
@click.argument("task_type")
@click.argument("artifact", type=click.Path(exists=True))
@click.option("--personas", type=click.Path(exists=True), default=None, help="Persona YAML path (default: the pack registered for the task type)")
@click.option("--limit", type=int, default=None, help="Maximum personas to audit; default is all")
@click.option("--output", "output_path", type=click.Path(), default=None, help="JSON output path")
def identity_invariance(task_type, artifact, personas, limit, output_path):
    """Verify that protected identity fields cannot alter the model payload."""
    from harness.counterfactual_identity import audit_panel_non_interference
    from runner.panel_selector import load_personas
    from runner.persona_agent import render_prompt

    artifact_bundle = runner_cli.load_artifact_bundle(artifact)
    personas_path = personas or default_personas_path(task_type, str(PROJECT_ROOT / "personas"))
    persona_prompt_path = str(PROJECT_ROOT / "templates" / "persona-prompt.md")
    panel = load_personas(personas_path)
    if limit is not None:
        if limit < 1:
            raise click.BadParameter("must be greater than zero", param_hint="--limit")
        panel = panel[:limit]

    artifact_summary = artifact_bundle.get("title", "")

    def render(persona):
        return render_prompt(
            persona,
            task_type,
            artifact_summary,
            persona_prompt_path,
            artifact_bundle,
        )

    result = audit_panel_non_interference(panel, render)
    _print("\n=== Counterfactual identity invariance audit ===")
    _print(f"Personas: {result['persona_count']} | interventions: {result['intervention_count']}")
    _print(f"Score: {result['score']:.4f} | {'PASS' if result['passed'] else 'FAIL'}")
    if result["failures"]:
        for failure in result["failures"]:
            _print(f"  [red]{failure['persona_id']} / {failure['field']} changed the model payload[/red]")
    _print(f"[yellow]Scope: {result['limitation']}[/yellow]")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        _print(f"Result saved: {output_path}")

    if not result["passed"]:
        raise click.ClickException("a protected identity field reached the model payload")


@main.command()
def version():
    """显示版本信息"""
    if HAS_RICH and console:
        console.print(Panel(
            f"[bold cyan]AudienceLens[/bold cyan] v{VERSION}\n"
            f"Multi-Agent Cross-Examination Framework\n"
            f"Python {sys.version.split()[0]}",
            title="版本信息"
        ))
    else:
        print(f"AudienceLens v{VERSION}")
        print("Multi-Agent Cross-Examination Framework")
        print(f"Python {sys.version.split()[0]}")


def _grade(score: float) -> str:
    if score >= 0.8:
        return "A"
    elif score >= 0.6:
        return "B"
    elif score >= 0.4:
        return "C"
    else:
        return "D"


def _print_table_result(result: dict):
    """以表格输出 Harness 评估结果"""
    if HAS_RICH and console:
        table = Table(title="Harness 8维评估结果")
        table.add_column("#", justify="right", style="dim")
        table.add_column("维度", style="cyan")
        table.add_column("得分", justify="right")
        table.add_column("阈值", justify="right")
        table.add_column("状态", style="bold")
        for i, dim in enumerate(result["dimensions"], 1):
            status = "[green]PASS[/green]" if dim["passed"] else "[red]FAIL[/red]"
            table.add_row(str(i), dim["name"], f"{dim['score']:.2f}", f"{dim['threshold']:.2f}", status)
        console.print(table)
    else:
        print(f"\n{'#':>2} {'维度':<30} {'得分':>6} {'阈值':>6} {'状态'}")
        print("-" * 60)
        for i, dim in enumerate(result["dimensions"], 1):
            status = "PASS" if dim["passed"] else "FAIL"
            print(f"{i:>2} {dim['name']:<30} {dim['score']:>6.2f} {dim['threshold']:>6.2f} {status}")

    overall = result["overall_score"]
    overall_pass = result["overall_passed"]
    _print(f"\n综合得分: {overall:.2f} | 整体状态: {'PASS' if overall_pass else 'FAIL'}")


def _print_markdown_result(result: dict):
    """以 Markdown 格式输出 Harness 评估结果"""
    print("| # | 维度 | 得分 | 阈值 | 状态 |")
    print("|---|------|------|------|------|")
    for i, dim in enumerate(result["dimensions"], 1):
        status = "PASS" if dim["passed"] else "FAIL"
        print(f"| {i} | {dim['name']} | {dim['score']:.2f} | {dim['threshold']:.2f} | {status} |")
    print(f"\n综合得分: {result['overall_score']:.2f} | 整体: {'PASS' if result['overall_passed'] else 'FAIL'}")


if __name__ == "__main__":
    main()
