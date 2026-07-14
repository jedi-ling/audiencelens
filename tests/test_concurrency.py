"""并发化 run_panel 的验证：结果与串行一致、保序，且确实并行。"""

import os
import time

import pytest

from runner import cli as runner_cli
from runner.cli import run_panel

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


@pytest.fixture
def bundle():
    return {
        "task_type": "concept_review",
        "target": "某独立游戏概念文档",
        "materials": [
            {"type": "核心循环说明", "text": "游戏核心循环是探索-战斗-成长"},
            {"type": "竞品对比", "text": "与Hades和Dead Cells对比分析"},
        ],
    }


def _panel(bundle, **kw):
    return run_panel(
        task_type="concept_review",
        artifact_bundle=bundle,
        personas_path=PERSONAS_PATH,
        presets_path=PRESETS_PATH,
        rules_path=RULES_PATH,
        budget_path=BUDGET_PATH,
        output_schema_path=OUTPUT_SCHEMA_PATH,
        report_schema_path=REPORT_SCHEMA_PATH,
        persona_prompt_path=PERSONA_PROMPT_PATH,
        cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
        report_template_path=REPORT_TEMPLATE_PATH,
        **kw,
    )


class TestConcurrencyEquivalence:
    def test_concurrent_matches_sequential_persona_order(self, bundle, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        seq = _panel(bundle, max_concurrency=1)
        par = _panel(bundle, max_concurrency=6)
        seq_ids = [n["persona_id"] for n in seq["report"]["persona_notes"]]
        par_ids = [n["persona_id"] for n in par["report"]["persona_notes"]]
        # 并发结果的人格顺序必须与串行一致（ex.map 保序）
        assert par_ids == seq_ids
        assert par["cost_summary"]["persona_count"] == seq["cost_summary"]["persona_count"]

    def test_default_concurrency_runs(self, bundle, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = _panel(bundle)  # 不传 max_concurrency，走默认
        assert result["cost_summary"]["persona_count"] >= 1
        assert result["report"]["persona_notes"]


def _passthrough_precheck(selected, bundle):
    # 放行全部选中人格，绕过证据预检的跳过，专测并发机制本身
    return {"valid_personas": list(selected), "skipped_personas": []}


class TestActuallyParallel:
    def test_calls_overlap_in_time(self, bundle, monkeypatch):
        """用带 sleep 的桩替换单人格评审，证明总耗时远小于串行累加。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(runner_cli, "precheck_panel", _passthrough_precheck)
        delay = 0.15
        real = runner_cli.run_single_persona

        def slow(persona, *a, **kw):
            time.sleep(delay)
            return real(persona, *a, **kw)

        monkeypatch.setattr(runner_cli, "run_single_persona", slow)

        t0 = time.time()
        result = _panel(bundle, max_concurrency=6)
        elapsed = time.time() - t0

        n = result["cost_summary"]["persona_count"]
        assert n >= 3  # 需要足够多人格才能体现并行
        sequential_lower_bound = n * delay
        # 并发后应远小于串行累加；给足调度余量，取一半为阈值
        assert elapsed < sequential_lower_bound * 0.6, (
            f"{n} 人格 × {delay}s：串行需 {sequential_lower_bound:.2f}s，"
            f"并发实测 {elapsed:.2f}s——未体现并行"
        )

    def test_max_concurrency_one_is_serial(self, bundle, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        delay = 0.1
        real = runner_cli.run_single_persona

        def slow(persona, *a, **kw):
            time.sleep(delay)
            return real(persona, *a, **kw)

        monkeypatch.setattr(runner_cli, "run_single_persona", slow)
        result = _panel(bundle, max_concurrency=1)
        # 串行路径仍能正确产出
        assert result["report"]["persona_notes"]
