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
def run(skill, task_type, artifact, mode, output_dir, personas):
    """运行合成评审"""
    _print(f"\n=== AudienceLens v{VERSION} ===")
    _print(f"技能: {skill} | 任务: {task_type} | 模式: {mode}\n")

    try:
        artifact_bundle = runner_cli.load_artifact_bundle(artifact)
        result = runner_cli.run_panel(
            task_type=task_type,
            artifact_bundle=artifact_bundle,
            personas_path=personas,
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
        _print("提示: parity-check 模块需要适配")
        _print(f"  命令: python tools/parity-check.py --synthetic {synthetic} --human {human}")
    except Exception as e:
        _print(f"错误: {e}")
        sys.exit(1)


@main.command("stereotype-eval")
@click.option("--llm", "use_llm", is_flag=True, help="启用 LLM 复审层（需 ANTHROPIC_API_KEY）")
def stereotype_eval(use_llm):
    """刻板印象检测评测：在30条标注集上算准确率/精确率/召回率"""
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
@click.option("--personas", type=click.Path(exists=True), default=None, help="Persona YAML 路径（默认 game-core）")
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
    personas_path = personas or str(PROJECT_ROOT / "personas" / "game-core.yaml")
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
