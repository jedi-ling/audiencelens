# -*- coding: utf-8 -*-
"""校验接入门控（2.2）+ 重试配置生效（2.3）。

2.2：validate_output 的结果以前只写进 r["validation"] 就原地归档，输出照样进
persona_outputs——"校验"是一道假门。现在 schema 关键字段不合格 / 角色漂移 /
幻觉率超标的输出不得进入聚合报告，计入 failed_personas / degradation，并在
报告里可见。模拟占位输出（meta.is_simulated）例外：它们存在的意义是让无 LLM
的环境里流水线能跑通，拦住它们等于废掉模拟模式（AGENTS.md 铁律：不得弱化
模拟模式警告，模拟输出必须仍能跑通流水线）。

2.3：budget.yaml 的 retry 段（max_retries_per_persona / retry_on）以前全仓
零读取点。现在 run_single_persona 按它执行最多 N 次重试，retry_on 决定哪些
失败类型重试；不传 retry_settings = 不重试，既有调用方行为不变。
"""

import json
import os
import sys

import pytest
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SRC = os.path.join(PROJECT_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from runner import cli as runner_cli  # noqa: E402
from runner.cli import AllPersonasFailedError  # noqa: E402
from runner.llm_client import LLMCallError  # noqa: E402

PERSONAS_PATH = os.path.join(SRC, "personas", "game-core.yaml")
PRESETS_PATH = os.path.join(SRC, "presets", "panel-presets.yaml")
RULES_PATH = os.path.join(SRC, "config", "aggregation-rules.yaml")
OUTPUT_SCHEMA_PATH = os.path.join(SRC, "schemas", "output-schema.json")
REPORT_SCHEMA_PATH = os.path.join(SRC, "schemas", "report-schema.json")
PERSONA_PROMPT_PATH = os.path.join(SRC, "templates", "persona-prompt.md")
CROSS_EXAM_PROMPT_PATH = os.path.join(SRC, "templates", "cross-exam-prompt.md")
REPORT_TEMPLATE_PATH = os.path.join(SRC, "templates", "report-template.md")
BUDGET_PATH = os.path.join(SRC, "config", "budget.yaml")

P01 = "P01-indie-core-operator"


def _valid_json(pid=P01, evidence_content="核心循环说明"):
    """能通过 schema/角色/证据三层校验的最小合法人格输出。"""
    return json.dumps(
        {
            "persona_id": pid,
            "persona_name": pid,
            "persona_version": "0.1.0",
            "task_type": "concept_review",
            "primary_stance": "观望",
            "confidence": 0.6,
            "evidence_sufficiency": 0.7,
            "evidence": [{"content": evidence_content, "inference_level": "direct"}],
            "scores": {"base": {"clarity": 3, "trust": 3}, "task_specific": {"overall": 3}},
            "key_issues": [
                {
                    "severity": "high",
                    "title": "上手门槛偏高",
                    "why_it_matters": "新玩家可能在第一关就走不下去",
                    "suggested_fix": "添加一段新手引导动画并简化操作说明",
                }
            ],
            "continue_triggers": [],
            "quit_triggers": [],
            "first_scan_observations": ["定位清楚"],
            "must_comment_on_check": {},
            "missing_information": [],
            "voice_sample": "看起来还行。",
            "meta": {"caveats": ["合成输出"], "is_synthetic": True},
        },
        ensure_ascii=False,
    )


@pytest.fixture
def bundle():
    """覆盖 P01 的证据需求（precheck 不跳过），且文本包含可接地的证据词。"""
    return {
        "task_type": "concept_review",
        "target": "测试",
        "materials": [
            {"type": "核心循环说明", "text": "核心循环说明：探索-战斗-成长"},
            {"type": "实机视频", "text": "实机视频：3分钟演示"},
        ],
    }


@pytest.fixture
def no_retry_budget(tmp_path):
    """retry 全关的预算配置：门控测试不想因为 schema_failure 重试而 sleep。"""
    p = tmp_path / "budget.yaml"
    p.write_text("max_cost_per_run_usd: 0\n", encoding="utf-8")
    return str(p)


def _panel(monkeypatch, chat_fn, budget_path, **kw):
    monkeypatch.setattr(runner_cli, "chat_completion", chat_fn)
    return runner_cli.run_panel(
        task_type="concept_review",
        artifact_bundle=kw.pop("artifact_bundle", None) or _bundle(),
        personas_path=PERSONAS_PATH,
        presets_path=PRESETS_PATH,
        rules_path=RULES_PATH,
        budget_path=budget_path,
        output_schema_path=OUTPUT_SCHEMA_PATH,
        report_schema_path=REPORT_SCHEMA_PATH,
        persona_prompt_path=PERSONA_PROMPT_PATH,
        cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
        report_template_path=REPORT_TEMPLATE_PATH,
        api_key=kw.pop("api_key", "sk-test-not-real"),
        **kw,
    )


def _bundle():
    return {
        "task_type": "concept_review",
        "target": "测试",
        "materials": [
            {"type": "核心循环说明", "text": "核心循环说明：探索-战斗-成长"},
            {"type": "实机视频", "text": "实机视频：3分钟演示"},
        ],
    }


class TestGating:
    """2.2：校验结果真正参与门控。"""

    def test_schema_invalid_output_is_gated(self, monkeypatch, no_retry_budget):
        def chat(**kwargs):
            out = json.loads(_valid_json())
            out.pop("key_issues")  # BLOCKING_SCHEMA_FIELDS 里的关键字段
            return json.dumps(out, ensure_ascii=False), 100, 200

        with pytest.raises(AllPersonasFailedError) as exc:
            _panel(monkeypatch, chat, no_retry_budget, selected_personas=[P01])

        failure = exc.value.failures[0]
        assert failure["failure_reason"] == "schema_failure"
        assert "schema" in failure["error"]

    def test_role_drift_output_is_gated(self, monkeypatch, no_retry_budget):
        def chat(**kwargs):
            out = json.loads(_valid_json())
            out["must_comment_on_check"] = {"a": True, "b": False}  # 覆盖率 50% < 80%
            return json.dumps(out, ensure_ascii=False), 100, 200

        with pytest.raises(AllPersonasFailedError) as exc:
            _panel(monkeypatch, chat, no_retry_budget, selected_personas=[P01])

        assert exc.value.failures[0]["failure_reason"] == "role_drift"

    def test_hallucination_output_is_gated(self, monkeypatch, no_retry_budget):
        def chat(**kwargs):
            return (
                _valid_json(evidence_content="这段内容完全不在评审材料里出现"),
                100,
                200,
            )

        with pytest.raises(AllPersonasFailedError) as exc:
            _panel(monkeypatch, chat, no_retry_budget, selected_personas=[P01])

        failure = exc.value.failures[0]
        assert failure["failure_reason"] == "hallucination"
        assert "材料中找不到出处" in failure["error"]

    def test_valid_output_passes_gating_and_report_visible(self, monkeypatch, no_retry_budget):
        def chat(**kwargs):
            return _valid_json(), 100, 200

        result = _panel(monkeypatch, chat, no_retry_budget, selected_personas=[P01])
        assert result["report"]["persona_notes"][0]["persona_id"] == P01
        assert result["degraded"] is False
        # 校验/重试口径进报告本体，重新打开历史报告也看得见
        assert result["report"]["validation"]["retry"]["max_retries"] == 0
        assert result["report"]["validation"]["gated_out"] == []

    def test_partial_gating_is_degradation_and_visible_in_report(self, monkeypatch, no_retry_budget, bundle):
        """一好一坏：坏的被拦下，好的照常进报告；degradation / markdown 都看得见。"""
        monkeypatch.setattr(
            runner_cli,
            "precheck_panel",
            lambda panel, b: {"valid_personas": list(panel), "skipped_personas": []},
        )

        def chat(**kwargs):
            if P01 in kwargs["prompt"]:
                return _valid_json(P01), 100, 200
            return _valid_json("P02-systems-theorycrafter", evidence_content="完全虚构的证据内容"), 100, 200

        result = _panel(
            monkeypatch, chat, no_retry_budget,
            selected_personas=[P01, "P02-systems-theorycrafter"],
            artifact_bundle=bundle,
        )
        cost = result["cost_summary"]
        assert cost["persona_count"] == 1
        assert cost["failed_count"] == 1
        assert result["degraded"] is True

        assert result["report"]["degradation"]["degraded"] is True
        failed = result["report"]["degradation"]["failed_personas"][0]
        assert failed["failure_reason"] == "hallucination"
        assert result["report"]["validation"]["gated_out"] == [
            {"persona_id": "P02-systems-theorycrafter", "failure_reason": "hallucination"}
        ]
        assert "未能完成" in result["markdown"]  # 渲染产物里也看得见

    def test_simulated_outputs_are_not_gated(self, monkeypatch, no_retry_budget):
        """模拟占位输出（meta.is_simulated）跳过门控：没有 LLM 的环境里流水线必须
        仍能跑通，模拟数据放行、真实模式照常门控。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        def chat(**kwargs):  # 不会被调用
            raise AssertionError("模拟模式不应该发任何 LLM 调用")

        result = _panel(monkeypatch, chat, no_retry_budget, selected_personas=[P01], api_key=None)
        assert result["simulated"] is True
        assert len(result["report"]["persona_notes"]) == 1
        assert result["degraded"] is False


class TestRetry:
    """2.3：budget.yaml 的 retry 配置真实生效。"""

    @pytest.fixture
    def sample_persona(self):
        return {
            "id": P01,
            "name": "林岚",
            "archetype": "核心独立探索者",
            "identity_summary": "测试人格",
            "behavior_profile": {},
            "motivations": [],
            "decision_rules": [],
            "review_output": {"must_comment_on": ["独特性"]},
            "model_hint": "sonnet",
        }

    @pytest.fixture
    def config(self):
        with open(BUDGET_PATH, encoding="utf-8") as f:
            budget = yaml.safe_load(f)
        return {"budget": budget, "persona_prompt_path": PERSONA_PROMPT_PATH}

    @pytest.fixture
    def output_schema(self):
        with open(OUTPUT_SCHEMA_PATH, encoding="utf-8") as f:
            return json.load(f)

    def _run(self, sample_persona, config, output_schema, retry_settings):
        return runner_cli.run_single_persona(
            persona=sample_persona,
            task_type="concept_review",
            artifact_summary="测试",
            artifact_texts=["核心循环说明：探索-战斗-成长"],
            config=config,
            api_key="sk-test-not-real",
            retry_settings=retry_settings,
            output_schema=output_schema,
        )

    def test_transport_error_retries_then_succeeds(self, monkeypatch, sample_persona, config, output_schema):
        calls = []

        def chat(**kwargs):
            calls.append(1)
            if len(calls) <= 2:
                raise LLMCallError("模拟 429 限流", status_code=429, retryable=True)
            return _valid_json(), 100, 200

        monkeypatch.setattr(runner_cli, "chat_completion", chat)
        result = self._run(
            sample_persona, config, output_schema,
            {"max_retries": 3, "retry_on": ["transport_error"], "backoff_base_seconds": 0.0},
        )
        assert result["output"] is not None
        assert result["retries"] == 2
        assert len(calls) == 3
        assert result["cost"] > 0

    def test_transport_retries_exhaust_and_record_reasons(self, monkeypatch, sample_persona, config, output_schema):
        def chat(**kwargs):
            raise LLMCallError("模拟 500 服务端抖动", status_code=500, retryable=True)

        monkeypatch.setattr(runner_cli, "chat_completion", chat)
        result = self._run(
            sample_persona, config, output_schema,
            {"max_retries": 3, "retry_on": ["transport_error"], "backoff_base_seconds": 0.0},
        )
        assert result["output"] is None
        assert result["retries"] == 3
        assert result["retry_reasons"] == ["transport_error"] * 3
        assert "500" in result["error"]

    def test_schema_failure_retries_via_validation(self, monkeypatch, sample_persona, config, output_schema):
        calls = []

        def chat(**kwargs):
            calls.append(1)
            if len(calls) == 1:
                out = json.loads(_valid_json())
                out.pop("key_issues")
                return json.dumps(out, ensure_ascii=False), 100, 200
            return _valid_json(), 100, 200

        monkeypatch.setattr(runner_cli, "chat_completion", chat)
        result = self._run(
            sample_persona, config, output_schema,
            {"max_retries": 2, "retry_on": ["schema_failure"], "backoff_base_seconds": 0.0},
        )
        assert result["output"] is not None
        assert result["retries"] == 1
        assert result["validation"]["passed"] is True

    def test_role_drift_retries_via_validation(self, monkeypatch, sample_persona, config, output_schema):
        calls = []

        def chat(**kwargs):
            calls.append(1)
            if len(calls) == 1:
                out = json.loads(_valid_json())
                out["must_comment_on_check"] = {"a": True, "b": False}
                return json.dumps(out, ensure_ascii=False), 100, 200
            return _valid_json(), 100, 200

        monkeypatch.setattr(runner_cli, "chat_completion", chat)
        result = self._run(
            sample_persona, config, output_schema,
            {"max_retries": 2, "retry_on": ["role_drift"], "backoff_base_seconds": 0.0},
        )
        assert result["output"] is not None
        assert result["retries"] == 1

    def test_no_retry_when_reason_not_in_retry_on(self, monkeypatch, sample_persona, config, output_schema):
        def chat(**kwargs):
            raise LLMCallError("模拟 429 限流", status_code=429, retryable=True)

        monkeypatch.setattr(runner_cli, "chat_completion", chat)
        result = self._run(
            sample_persona, config, output_schema,
            {"max_retries": 3, "retry_on": ["schema_failure"], "backoff_base_seconds": 0.0},
        )
        assert result["output"] is None
        assert result["retries"] == 0
        assert result["retry_reasons"] == []

    def test_dead_error_not_retried(self, monkeypatch, sample_persona, config, output_schema):
        """401/余额不足这类死错重试一百次也一样，必须一次就报出来。"""

        def chat(**kwargs):
            raise LLMCallError("HTTP 401 key 无效", status_code=401, retryable=False)

        monkeypatch.setattr(runner_cli, "chat_completion", chat)
        result = self._run(
            sample_persona, config, output_schema,
            {"max_retries": 3, "retry_on": ["transport_error"], "backoff_base_seconds": 0.0},
        )
        assert result["output"] is None
        assert result["retries"] == 0
        assert "401" in result["error"]

    def test_no_retry_settings_keeps_single_attempt(self, monkeypatch, sample_persona, config, output_schema):
        """不传 retry_settings = 不重试（默认 0），保持所有既有调用方行为不变。"""
        calls = []

        def chat(**kwargs):
            calls.append(1)
            raise LLMCallError("模拟 429 限流", status_code=429, retryable=True)

        monkeypatch.setattr(runner_cli, "chat_completion", chat)
        result = self._run(sample_persona, config, output_schema, None)
        assert result["output"] is None
        assert result["retries"] == 0
        assert len(calls) == 1

    def test_run_panel_reads_retry_config_from_budget(self, monkeypatch, tmp_path):
        """端到端：run_panel 从 budget.yaml 读 retry 段并真的应用（传输层重试后成功）。"""
        budget = tmp_path / "budget.yaml"
        budget.write_text(
            "max_cost_per_run_usd: 0\n"
            "retry:\n"
            "  max_retries_per_persona: 2\n"
            "  retry_on: [transport_error]\n"
            "  backoff_base_seconds: 0.0\n",
            encoding="utf-8",
        )
        calls = []

        def chat(**kwargs):
            calls.append(1)
            if len(calls) <= 2:
                raise LLMCallError("模拟 429 限流", status_code=429, retryable=True)
            return _valid_json(), 100, 200

        result = _panel(monkeypatch, chat, str(budget), selected_personas=[P01])
        assert len(calls) == 3
        assert result["cost_summary"]["persona_count"] == 1
        assert result["report"]["validation"]["retry"]["max_retries"] == 2
        assert result["report"]["validation"]["retry"]["retry_on"] == ["transport_error"]
