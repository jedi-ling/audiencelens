"""并发化 run_panel 的验证：结果与串行一致、保序，且确实并行。"""

import os
import threading
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
        """直接记录同时执行的调用数，避免冷启动模型耗时污染墙钟断言。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(runner_cli, "precheck_panel", _passthrough_precheck)
        delay = 0.15
        real = runner_cli.run_single_persona
        lock = threading.Lock()
        active = 0
        max_active = 0

        def slow(persona, *a, **kw):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(delay)
                return real(persona, *a, **kw)
            finally:
                with lock:
                    active -= 1

        monkeypatch.setattr(runner_cli, "run_single_persona", slow)

        result = _panel(bundle, max_concurrency=6)

        n = result["cost_summary"]["persona_count"]
        assert n >= 3  # 需要足够多人格才能体现并行
        assert max_active >= 2, f"最大同时执行数为 {max_active}，未体现并行"

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


class TestExplicitApiKey:
    """api_key 显式参数：多用户服务端并发的防串 key 保证。"""

    def test_explicit_key_reaches_workers_without_env(self, bundle, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(runner_cli, "precheck_panel", _passthrough_precheck)
        seen = []
        real = runner_cli.run_single_persona

        def spy(persona, task_type, artifact_summary, artifact_texts, config,
                artifact_bundle=None, api_key=None):
            seen.append(api_key)
            # 强制走模拟输出路径，避免真调 API
            return real(persona, task_type, artifact_summary, artifact_texts,
                        config, artifact_bundle, api_key=None)

        monkeypatch.setattr(runner_cli, "run_single_persona", spy)
        result = _panel(bundle, max_concurrency=4, api_key="sk-ant-explicit")
        # 显式 key 时不再标记模拟——key 的判定不依赖进程环境变量
        assert result["simulated"] is False
        assert seen and all(k == "sk-ant-explicit" for k in seen)

    def test_env_fallback_still_works(self, bundle, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
        monkeypatch.setattr(runner_cli, "precheck_panel", _passthrough_precheck)
        seen = []
        real = runner_cli.run_single_persona

        def spy(persona, task_type, artifact_summary, artifact_texts, config,
                artifact_bundle=None, api_key=None):
            seen.append(api_key)
            return real(persona, task_type, artifact_summary, artifact_texts,
                        config, artifact_bundle, api_key=None)

        monkeypatch.setattr(runner_cli, "run_single_persona", spy)
        result = _panel(bundle, max_concurrency=4)  # 不传 api_key → 回落环境变量
        assert result["simulated"] is False
        assert seen and all(k == "sk-ant-from-env" for k in seen)


class TestProgressCallback:
    """run_panel(progress_callback=...) 的实时进度回调契约。"""

    def _collecting_callback(self):
        calls = []
        lock = threading.Lock()

        def cb(done, total, persona_id):
            with lock:
                calls.append((done, total, persona_id))

        return calls, cb

    def test_callback_invoked_once_per_persona_concurrent(self, bundle, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(runner_cli, "precheck_panel", _passthrough_precheck)
        calls, cb = self._collecting_callback()

        result = _panel(bundle, max_concurrency=6, progress_callback=cb)

        n = result["cost_summary"]["persona_count"]
        assert n >= 1
        # 调用次数 == 人格数
        assert len(calls) == n
        # done 值集合恰为 1..N（顺序可乱，但计数不丢不重）
        assert sorted(c[0] for c in calls) == list(range(1, n + 1))
        # 每次 total 都等于 N
        assert all(c[1] == n for c in calls)
        # persona_id 非空
        assert all(c[2] for c in calls)

    def test_callback_invoked_in_serial_mode(self, bundle, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(runner_cli, "precheck_panel", _passthrough_precheck)
        calls, cb = self._collecting_callback()

        result = _panel(bundle, max_concurrency=1, progress_callback=cb)

        n = result["cost_summary"]["persona_count"]
        assert len(calls) == n
        # 串行模式下 done 应严格递增 1..N
        assert [c[0] for c in calls] == list(range(1, n + 1))
        assert all(c[1] == n for c in calls)
        assert all(c[2] for c in calls)

    def test_callback_exception_does_not_break_review(self, bundle, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(runner_cli, "precheck_panel", _passthrough_precheck)

        def exploding(done, total, persona_id):
            raise RuntimeError("progress callback boom")

        result = _panel(bundle, max_concurrency=6, progress_callback=exploding)
        # 回调抛异常不得影响评审产出
        assert result["cost_summary"]["persona_count"] >= 1
        assert result["report"]["persona_notes"]
