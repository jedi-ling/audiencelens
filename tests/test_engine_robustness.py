# -*- coding: utf-8 -*-
"""健壮性小项（spec 2.5）：
  · run_panel 不再就地改写调用方的 artifact_bundle（先深拷贝再补 description）；
  · 报告 JSON 写入 allow_nan=False（claude 报告落盘不允许非法 JSON）；
  · persona_agent 的成本估算不再依赖相对路径（从任意 cwd 都能读 budget.yaml）。
"""

import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SRC = os.path.join(PROJECT_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from runner import cli as runner_cli  # noqa: E402
from runner.persona_agent import estimate_cost_detailed  # noqa: E402

PERSONAS_PATH = os.path.join(SRC, "personas", "game-core.yaml")
PRESETS_PATH = os.path.join(SRC, "presets", "panel-presets.yaml")
RULES_PATH = os.path.join(SRC, "config", "aggregation-rules.yaml")
BUDGET_PATH = os.path.join(SRC, "config", "budget.yaml")
OUTPUT_SCHEMA_PATH = os.path.join(SRC, "schemas", "output-schema.json")
REPORT_SCHEMA_PATH = os.path.join(SRC, "schemas", "report-schema.json")
PERSONA_PROMPT_PATH = os.path.join(SRC, "templates", "persona-prompt.md")
CROSS_EXAM_PROMPT_PATH = os.path.join(SRC, "templates", "cross-exam-prompt.md")
REPORT_TEMPLATE_PATH = os.path.join(SRC, "templates", "report-template.md")


def _panel_kwargs(**overrides):
    kwargs = dict(
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
        selected_personas=["P01-indie-core-operator"],
    )
    kwargs.update(overrides)
    return kwargs


class TestRunPanelDoesNotMutateCallerBundle:
    def test_material_without_description_is_not_modified_in_place(self, monkeypatch):
        """对话链路发来的材料是 {type, text} 没有 description，run_panel 会在内部
        补一份 description——但必须补在拷贝上，调用方拿到的原 dict 不能多出键。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        materials = [
            {"type": "核心循环说明", "text": "核心循环说明：探索-战斗-成长"},
            {"type": "实机视频", "text": "实机视频：3分钟演示"},
        ]
        caller_bundle = {"task_type": "concept_review", "target": "测试", "materials": materials}
        materials_snapshot = [dict(m) for m in materials]

        runner_cli.run_panel(
            artifact_bundle=caller_bundle,
            **_panel_kwargs(),
        )

        assert caller_bundle["materials"] == materials_snapshot, (
            "run_panel 就地改写了调用方的 material dict——调用方再拿原 bundle "
            "干别的事时会看到自己没写过的 description 键"
        )
        assert all("description" not in m for m in caller_bundle["materials"])


class TestReportJsonIsLegal:
    def test_simulated_report_serializes_with_allow_nan_false(self, monkeypatch):
        """CLI 落盘用 json.dump(..., allow_nan=False)：NaN/Infinity 会写出非法 JSON，
        任何下游解析器都会炸。模拟报告必须能被严格序列化。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = runner_cli.run_panel(artifact_bundle={
            "task_type": "concept_review",
            "target": "测试",
            "materials": [
                {"type": "核心循环说明", "text": "核心循环说明：探索-战斗-成长"},
                {"type": "实机视频", "text": "实机视频：3分钟演示"},
            ],
        }, **_panel_kwargs())

        text = json.dumps(result["report"], ensure_ascii=False, allow_nan=False)
        assert '"persona_notes"' in text
        # 严格序列化后再解析回来必须是合法 JSON（非 NaN/Infinity 字面量）
        reloaded = json.loads(text)
        assert reloaded["meta"]["is_synthetic"] is True


class TestCostEstimateFromAnyCwd:
    def test_estimate_cost_detailed_loads_budget_by_absolute_path(self, monkeypatch, tmp_path):
        """estimate_cost_detailed 没传 budget_config 时要能自己读到 budget.yaml——
        相对路径 "src/config/budget.yaml" 只对仓库根启动的进程有效，换个 cwd 就
        FileNotFoundError（后台面板/调度脚本/测试都可能从别处启动）。"""
        monkeypatch.chdir(tmp_path)
        cost, priced = estimate_cost_detailed(1_000_000, 1_000_000, "claude-sonnet-4-20250514")
        assert priced is True
        assert cost == pytest.approx(18.0)  # 3.0 输入 + 15.0 输出（每百万 token）
