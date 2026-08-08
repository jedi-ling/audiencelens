# 新增产物的守门测试：report["panel_selection"] 的截断口径、
# validation.calibration 渲染进 Markdown/HTML、HTML 的「各人格声明的限制条件」章节，
# 以及 ≥2 人格的端到端链路（run_panel → json.dumps → 渲染产物）。
# 每条断言都盯着一个具体的行为：把对应实现改坏，这里必须红。

import json
import os

import yaml

from runner.aggregator import (
    aggregate_report,
    load_aggregation_rules,
    render_html_report,
    render_markdown_report,
)
from runner.calibration import run_calibration_check
from runner.cli import _json_safe, run_panel

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PERSONAS_PATH = os.path.join(PROJECT_ROOT, "src", "personas", "game-core.yaml")
PRESETS_PATH = os.path.join(PROJECT_ROOT, "src", "presets", "panel-presets.yaml")
RULES_PATH = os.path.join(PROJECT_ROOT, "src", "config", "aggregation-rules.yaml")
BUDGET_PATH = os.path.join(PROJECT_ROOT, "src", "config", "budget.yaml")
OUTPUT_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "schemas", "output-schema.json")
REPORT_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "schemas", "report-schema.json")
PERSONA_PROMPT_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "persona-prompt.md")
CROSS_EXAM_PROMPT_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "cross-exam-prompt.md")
REPORT_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.md")
HTML_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.html")


def _rich_bundle():
    """材料覆盖人格包全部 evidence_types_needed，让 precheck 一个都不跳过——
    这样人数相关的断言测的才是 mode 截断本身，而不是证据筛选。"""
    with open(PERSONAS_PATH, "r", encoding="utf-8") as f:
        pack = yaml.safe_load(f)
    evidence_types = set()
    for p in pack["personas"]:
        evidence_types.update(p.get("evidence_types_needed", []))
    return {
        "task_type": "concept_review",
        "target": "覆盖全证据类型的测试包",
        "materials": [{"type": t, "text": f"{t} 的占位材料"} for t in sorted(evidence_types)],
    }


def _persona_ids(n):
    with open(PERSONAS_PATH, "r", encoding="utf-8") as f:
        pack = yaml.safe_load(f)
    return [p["id"] for p in pack["personas"]][:n]


def _run_panel_simulated(**kwargs):
    os.environ.pop("ANTHROPIC_API_KEY", None)
    return run_panel(
        task_type="concept_review",
        personas_path=PERSONAS_PATH,
        presets_path=PRESETS_PATH,
        rules_path=RULES_PATH,
        budget_path=BUDGET_PATH,
        output_schema_path=OUTPUT_SCHEMA_PATH,
        report_schema_path=REPORT_SCHEMA_PATH,
        persona_prompt_path=PERSONA_PROMPT_PATH,
        cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
        report_template_path=REPORT_TEMPLATE_PATH,
        html_template_path=HTML_TEMPLATE_PATH,
        **kwargs,
    )


class TestPanelSelectionTruncationHonesty:
    def test_matched_reflects_post_truncation_panel(self):
        """点名 5 人但 quick 档限 3 人：matched 只能列真正参与的人格，
        被截掉的必须出现在 missing 与 truncated_by_mode 里，notice 要说明截断。
        以前 matched 在 truncate_panel 之前定稿，报告会说 5 个全参与、missing 为空。"""
        requested = _persona_ids(5)
        result = _run_panel_simulated(
            artifact_bundle=_rich_bundle(),
            selected_personas=requested,
            mode="quick",
        )
        sel = result["report"]["panel_selection"]
        assert sel["requested"] == requested
        # quick 档上限 3 人：matched 不许超过 3，也不许再谎报 5 人全参与
        assert len(sel["matched"]) <= 3
        assert len(sel["matched"]) < len(requested)
        # matched 必须与实际产出评审的人格一致
        participating = {n["persona_id"] for n in result["report"]["persona_notes"]}
        assert set(sel["matched"]) == set(sel["matched"]) & participating
        # 被截掉的人格必须留痕，且 missing 覆盖它们
        assert sel["truncated_by_mode"]
        for pid in sel["truncated_by_mode"]:
            assert pid in sel["missing"]
            assert pid not in sel["matched"]
        assert "人数上限被截断" in sel["notice"]
        # 横幅要进导出件，读者不点开 JSON 也能看到
        assert "人数上限被截断" in result["markdown"]

    def test_all_matched_when_no_truncation(self):
        """不设 mode、点名的 id 全部有效时：matched 完整、missing 与 truncated 为空、
        notice 为空串——不能对正常情况乱报警。"""
        requested = _persona_ids(2)
        result = _run_panel_simulated(
            artifact_bundle=_rich_bundle(),
            selected_personas=requested,
        )
        sel = result["report"]["panel_selection"]
        assert sel["matched"] == requested
        assert sel["missing"] == []
        assert sel["truncated_by_mode"] == []
        assert sel["notice"] == ""


def _make_output(pid, issues, caveats):
    return {
        "persona_id": pid,
        "persona_name": pid,
        "primary_stance": "值得推进" if pid.endswith("1") else "不推荐",
        "confidence": 0.8,
        "evidence_sufficiency": 0.7,
        "evidence": [{"content": "UI is clear", "inference_level": "direct"}],
        "key_issues": [
            {"severity": "high", "title": t, "why_it_matters": "matters", "suggested_fix": "fix"}
            for t in issues
        ],
        "missing_information": [],
        "must_comment_on_check": {"a": True, "b": True},
        "continue_triggers": [],
        "quit_triggers": [],
        "meta": {"caveats": caveats},
    }


def _report_with_calibration(outputs):
    rules = load_aggregation_rules(RULES_PATH)
    report = aggregate_report(outputs, "concept_review", "测试目标", rules)
    calibration = run_calibration_check(outputs, artifact_texts=["UI is clear"])
    report.setdefault("validation", {})["calibration"] = _json_safe(calibration)
    return report, calibration


class TestCalibrationRendering:
    def test_markdown_renders_calibration_metrics(self):
        outputs = [
            _make_output("p1", ["Bug A", "Bug B", "Bug C"], ["仅基于概念文档"]),
            _make_output("p2", ["Bug A"], ["未见实机画面"]),
        ]
        report, calibration = _report_with_calibration(outputs)
        md = render_markdown_report(report, REPORT_TEMPLATE_PATH)
        assert "校准指标" in md
        assert "角色一致性" in md
        # 覆盖度：2 人共 3 个议题、1 个重合 → 距离 2/3，模板 round(4) 后应为 0.6667。
        # 这条断言同时钉住"数值真的被渲染"与"round 真的生效"（0.6666666666666666 会红）
        import pytest
        assert calibration["coverage"]["average_distance"] == pytest.approx(2 / 3)
        assert "0.6667" in md
        # 幻觉率方向必须与 HTML 一致：标"幻觉率"打 x 本身，不再打 1-x 标"无幻觉率"
        assert "幻觉率" in md
        assert "无幻觉率" not in md
        assert "0.9500000000000001" not in md

    def test_markdown_single_persona_shows_not_applicable(self):
        """n<2：导出件必须写"单人格无覆盖度指标"，不许打印 0.0 判未通过。"""
        outputs = [_make_output("p1", ["Bug A"], ["仅基于概念文档"])]
        report, calibration = _report_with_calibration(outputs)
        assert calibration["coverage"]["not_applicable"] is True
        md = render_markdown_report(report, REPORT_TEMPLATE_PATH)
        assert "单人格无覆盖度指标" in md
        # 角色一致性达标时总判定必须是通过——不适用不能算失败
        assert "校准总判定：通过" in md
        # 覆盖度那一行绝不许再出现「0.0 | ≥0.3」这种"无定义装很差"的组合
        assert "0.0 | ≥0.3" not in md

    def test_html_renders_calibration_metrics(self):
        outputs = [
            _make_output("p1", ["Bug A", "Bug B", "Bug C"], ["仅基于概念文档"]),
            _make_output("p2", ["Bug A"], ["未见实机画面"]),
        ]
        report, _ = _report_with_calibration(outputs)
        html = render_html_report(report, HTML_TEMPLATE_PATH)
        assert "角色一致性" in html
        assert "视角覆盖度" in html
        assert "0.6667" in html
        assert "幻觉率" in html

    def test_html_single_persona_shows_not_applicable(self):
        outputs = [_make_output("p1", ["Bug A"], ["仅基于概念文档"])]
        report, _ = _report_with_calibration(outputs)
        html = render_html_report(report, HTML_TEMPLATE_PATH)
        assert "单人格无覆盖度指标" in html
        assert "校准通过" in html


class TestHtmlCaveatsSection:
    def test_caveats_section_renders_each_declared_caveat(self):
        outputs = [
            _make_output("p1", ["Bug A"], ["仅基于概念文档，未见实机"]),
            _make_output("p2", ["Bug B"], ["评审时材料缺少定价信息"]),
        ]
        report, _ = _report_with_calibration(outputs)
        html = render_html_report(report, HTML_TEMPLATE_PATH)
        assert "各人格声明的限制条件" in html
        assert "仅基于概念文档，未见实机" in html
        assert "评审时材料缺少定价信息" in html

    def test_caveats_section_absent_when_none_declared(self):
        outputs = [
            _make_output("p1", ["Bug A"], []),
            _make_output("p2", ["Bug B"], []),
        ]
        report, _ = _report_with_calibration(outputs)
        html = render_html_report(report, HTML_TEMPLATE_PATH)
        assert "各人格声明的限制条件" not in html


class TestEndToEndMultiPersona:
    def test_full_chain_json_and_renders(self):
        """≥2 人格端到端：run_panel → json.dumps(report) → markdown / html 全链路无异常。
        重点钉住 ad84be1 修过的回归：calibration.coverage.pairwise_distances 的元组键
        必须在进 report 前拍平成 'id1|id2' 字符串，否则 json.dumps 直接 TypeError。"""
        result = _run_panel_simulated(artifact_bundle=_rich_bundle())
        report = result["report"]
        assert result["cost_summary"]["persona_count"] >= 2

        # report 必须整份可 JSON 序列化（CLI 落盘与 web report_json 列共同依赖）
        dumped = json.dumps(report, ensure_ascii=False)
        assert dumped

        cal = report["validation"]["calibration"]
        pairwise = cal["coverage"]["pairwise_distances"]
        assert pairwise, "≥2 成功人格时必须有两两距离"
        for key in pairwise:
            assert isinstance(key, str) and "|" in key

        assert "校准指标" in result["markdown"]
        assert "<html" in result["html"].lower() or "<div" in result["html"]
