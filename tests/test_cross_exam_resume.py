"""交叉质询的 max_tokens / 截断，以及"用已有人格输出续跑"（run_panel_from_outputs）。

两件事的来由见 docs/evaluation/dedup-fallback-finding.md：三份 Sonnet 5.5 样例的人格
输出里本来就有真分歧，只是当时词面去重合并不了它们；补跑交叉质询不该为此把已经
通过校验的人格评审重跑一遍（又贵、结果还会变）。
"""

import json

import pytest
import yaml

import runner.cli as runner_cli
from tests import test_cli as tc


class FakeLLM:
    """人格调用一律报错（续跑不许重跑人格）；交叉质询调用记下 kwargs 并应答。"""

    def __init__(self, stop_reason=None):
        self.cross_exam_calls = []
        self.persona_calls = 0
        self.stop_reason = stop_reason

    def __call__(self, **kwargs):
        prompt = kwargs["prompt"]
        if tc.CROSS_EXAM_MARKER in prompt:
            self.cross_exam_calls.append(kwargs)
            details = kwargs.get("debug_details")
            if details is not None and self.stop_reason:
                details["stop_reason"] = self.stop_reason
            return (tc._moderated_reply()(prompt),) + tc.CROSS_EXAM_TOKENS
        self.persona_calls += 1
        raise AssertionError("续跑时不应该再调用人格评审")


def _duel_outputs():
    return [
        json.loads(tc._llm_json(pid, severity=sev, title=tc.DUEL_TITLE))
        for pid, sev in tc.DUEL_SEVERITIES.items()
    ]


def _stage(fake, monkeypatch, budget_config):
    outputs, points = tc._synthetic_duel()
    usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
    monkeypatch.setattr(runner_cli, "chat_completion", fake)
    data = runner_cli.run_cross_exam_stage(
        persona_outputs=outputs, controversy_points=points, personas=[],
        template_path=tc.CROSS_EXAM_PROMPT_PATH, rules=None, budget_config=budget_config,
        usage=usage, mode="standard", api_key="sk-test-not-real",
    )
    return data, usage


# ---------------------------------------------------------------------------
# max_tokens / 截断
# ---------------------------------------------------------------------------


def test_budget_yaml_sets_cross_exam_max_tokens():
    budget = yaml.safe_load(open(tc.BUDGET_PATH, encoding="utf-8"))
    assert budget["cross_exam_max_tokens"] == runner_cli.PERSONA_MAX_TOKENS == 8192


def test_cross_exam_call_uses_the_configured_max_tokens(monkeypatch):
    fake = FakeLLM()
    _stage(fake, monkeypatch, {"cross_exam_max_tokens": 12000})
    assert fake.cross_exam_calls[0]["max_tokens"] == 12000


def test_cross_exam_defaults_to_the_persona_limit_not_4096(monkeypatch):
    fake = FakeLLM()
    _stage(fake, monkeypatch, {})
    assert fake.cross_exam_calls[0]["max_tokens"] == runner_cli.PERSONA_MAX_TOKENS


def test_truncated_rebuttal_is_a_recorded_failure_and_still_billed(monkeypatch):
    fake = FakeLLM(stop_reason="max_tokens")
    data, usage = _stage(fake, monkeypatch, {})
    assert data["failures"], "被截断的反驳不能当成功"
    assert "截断" in data["failures"][0]["error"]
    assert data["mode"] == "derived_summary" and data["is_live_debate"] is False
    assert usage["calls"] == 1 and usage["output_tokens"] == tc.CROSS_EXAM_TOKENS[1]


# ---------------------------------------------------------------------------
# run_panel_from_outputs
# ---------------------------------------------------------------------------


def _resume(monkeypatch, fake, outputs, **overrides):
    monkeypatch.setattr(runner_cli, "chat_completion", fake)
    kwargs = dict(
        task_type="concept_review",
        artifact_bundle=tc._rich_bundle(),
        persona_outputs=outputs,
        personas_path=tc.PERSONAS_PATH,
        presets_path=tc.PRESETS_PATH,
        rules_path=tc.RULES_PATH,
        budget_path=tc.BUDGET_PATH,
        output_schema_path=tc.OUTPUT_SCHEMA_PATH,
        report_schema_path=tc.REPORT_SCHEMA_PATH,
        persona_prompt_path=tc.PERSONA_PROMPT_PATH,
        cross_exam_prompt_path=tc.CROSS_EXAM_PROMPT_PATH,
        report_template_path=tc.REPORT_TEMPLATE_PATH,
        api_key="sk-test-not-real",
        mode="standard",
    )
    kwargs.update(overrides)
    return runner_cli.run_panel_from_outputs(**kwargs)


def test_resume_runs_cross_exam_without_rerunning_personas(monkeypatch):
    fake = FakeLLM()
    result = _resume(monkeypatch, fake, _duel_outputs())

    assert fake.persona_calls == 0
    assert len(fake.cross_exam_calls) == 1
    cross = result["report"]["cross_examination"]
    assert cross["mode"] == "moderated_rebuttal" and cross["is_live_debate"] is True
    assert result["markdown"] and result["html"].rstrip().endswith("</html>")
    # 复用的人格输出不再计费：账上只有这次交叉质询
    cs = result["cost_summary"]
    assert cs["total_cost"] == pytest.approx(cs["cross_exam"]["cost"])
    assert cs["total_input_tokens"] == tc.CROSS_EXAM_TOKENS[0]
    assert result["report"]["degradation"]["degraded"] is False


def test_resume_revalidates_and_reports_failed_personas(monkeypatch):
    """旧的校验结论不被信任：残缺的输出在续跑时照样被门控、计入降级说明。"""
    outputs = _duel_outputs()
    broken = {k: v for k, v in outputs[1].items() if k not in ("scores", "key_issues")}
    fake = FakeLLM()
    result = _resume(monkeypatch, fake, [outputs[0], broken])

    deg = result["report"]["degradation"]
    assert deg["degraded"] is True and deg["failed_count"] == 1
    assert deg["failed_personas"][0]["persona_id"] == tc.DUEL_CON
    assert fake.cross_exam_calls == [], "只剩一位人格，不该凭空制造争议"


def test_resume_rejects_personas_outside_the_panel(monkeypatch):
    outputs = _duel_outputs()
    outputs[0]["persona_id"] = "P99-not-in-any-pack"
    with pytest.raises(ValueError, match="P99-not-in-any-pack"):
        _resume(monkeypatch, FakeLLM(), outputs)


# ---------------------------------------------------------------------------
# 去重退化到词面相似度时，报告要如实说明
# ---------------------------------------------------------------------------


def _simulated_panel(monkeypatch, method):
    monkeypatch.setattr(runner_cli, "_issue_dedup_method", lambda: method)
    return tc._panel(artifact_bundle=tc._rich_bundle(), mode="standard",
                     html_template_path=tc.REPORT_TEMPLATE_PATH.replace(".md", ".html"))


def test_lexical_dedup_is_announced_in_json_markdown_and_html(monkeypatch):
    result = _simulated_panel(monkeypatch, "lexical")
    dedup = result["report"]["dedup"]
    assert dedup["method"] == "lexical"
    assert "Semantic dedup not installed" in dedup["notice"]
    assert "Semantic dedup not installed" in result["markdown"]
    assert "Semantic dedup not installed" in result["html"]


def test_semantic_dedup_carries_no_notice(monkeypatch):
    result = _simulated_panel(monkeypatch, "semantic")
    assert result["report"]["dedup"] == {"method": "semantic", "notice": ""}
    assert "Semantic dedup not installed" not in result["markdown"]
    assert "Semantic dedup not installed" not in result["html"]


# ---------------------------------------------------------------------------
# Docker 镜像预下载的模型必须就是引擎要加载的那个
# ---------------------------------------------------------------------------


def test_docker_image_bakes_the_model_the_engine_loads():
    """镜像里 HF_HUB_OFFLINE=1，运行时不再下载：两边模型名一旦不一致，引擎加载失败、
    悄悄退回词面档，报告里只会多一条"语义去重未安装"的提示。"""
    import os
    import re

    from runner.similarity import SEMANTIC_MODEL_NAME

    dockerfile = open(os.path.join(tc.PROJECT_ROOT, "web", "backend", "Dockerfile"), encoding="utf-8").read()
    assert re.search(r"^ARG INSTALL_SEMANTIC_DEDUP=true$", dockerfile, re.M), "语义去重应默认开启"
    model = re.search(r"^ARG SEMANTIC_MODEL=(\S+)$", dockerfile, re.M)
    assert model and model.group(1) == SEMANTIC_MODEL_NAME
    assert "download.pytorch.org/whl/cpu" in dockerfile, "只能装 CPU 版 torch"
    assert re.search(r"^ENV HF_HUB_OFFLINE=1$", dockerfile, re.M)
