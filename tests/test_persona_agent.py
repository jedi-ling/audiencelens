import json
import os

import pytest
import yaml

from runner.persona_agent import (
    estimate_cost,
    parse_persona_output,
    render_prompt,
    select_model,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "persona-prompt.md")
BUDGET_PATH = os.path.join(PROJECT_ROOT, "src", "config", "budget.yaml")


@pytest.fixture
def sample_persona():
    return {
        "id": "P01-indie-core-operator",
        "name": "林岚",
        "mbti": "INTJ",
        "archetype": "核心独立探索者",
        "identity_summary": "更在意这游戏是否真的有自己的一套东西",
        "behavior_profile": {
            "patience": "高",
            "genre_literacy": "高",
            "novelty_seeking": "高",
        },
        "motivations": ["独特机制", "作者表达"],
        "decision_rules": [
            "若15秒内看不到核心钩子，不加愿望单",
            "若有一条只有它能做到的机制证据，即使粗糙也愿继续关注",
        ],
        "quit_triggers": ["卖点说不清"],
        "continue_triggers": ["机制互锁明显"],
        "first_scan_focus": ["一句话定位", "前三张图/GIF"],
        "review_output": {
            "must_comment_on": ["独特性", "核心循环证据", "参考竞品", "首15分钟"],
        },
    }


@pytest.fixture
def budget_config():
    with open(BUDGET_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestRenderPrompt:
    def test_replaces_persona_yaml_minified(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "P01-indie-core-operator" in result
        assert "林岚" in result
        assert "核心独立探索者" in result

    def test_replaces_mbti(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "INTJ" in result

    def test_replaces_persona_name(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "作为林岚" in result

    def test_replaces_must_comment_on_items(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "独特性" in result
        assert "核心循环证据" in result
        assert "参考竞品" in result
        assert "首15分钟" in result

    def test_replaces_primary_decision_rule(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "若15秒内看不到核心钩子，不加愿望单" in result

    def test_replaces_task_type(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "demo_first_play",
            "某独立游戏Demo",
            TEMPLATE_PATH,
        )
        assert "demo_first_play" in result

    def test_replaces_artifact_summary(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "某独立游戏Steam页面" in result

    def test_persona_yaml_minified_only_core_fields(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        minified_yaml_str = None
        for line in result.split("\n"):
            if "P01-indie-core-operator" in line and "核心独立探索者" in line:
                minified_yaml_str = line
                break
        parsed = yaml.safe_load(minified_yaml_str) if minified_yaml_str else None
        if isinstance(parsed, dict):
            assert "behavior_profile" not in parsed or "id" in parsed
        assert "P01-indie-core-operator" in result


class TestParsePersonaOutput:
    def test_pure_json(self):
        data = {"persona_id": "P01", "primary_stance": "加愿望单"}
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_persona_output(raw)
        assert result["persona_id"] == "P01"
        assert result["primary_stance"] == "加愿望单"

    def test_markdown_wrapped_json(self):
        data = {"persona_id": "P02", "primary_stance": "不加"}
        raw = f"```json\n{json.dumps(data, ensure_ascii=False)}\n```"
        result = parse_persona_output(raw)
        assert result["persona_id"] == "P02"
        assert result["primary_stance"] == "不加"

    def test_mixed_text_with_json(self):
        data = {"persona_id": "P03", "primary_stance": "观望"}
        raw = f"这是我的分析结果：\n{json.dumps(data, ensure_ascii=False)}"
        result = parse_persona_output(raw)
        assert result["persona_id"] == "P03"

    def test_mixed_text_with_multiple_json_extracts_last(self):
        data1 = {"persona_id": "P03", "primary_stance": "观望"}
        data2 = {"persona_id": "P03", "primary_stance": "加愿望单"}
        raw = f"第一轮：{json.dumps(data1, ensure_ascii=False)}\n第二轮：{json.dumps(data2, ensure_ascii=False)}"
        result = parse_persona_output(raw)
        assert result["primary_stance"] == "加愿望单"

    def test_parse_error_returns_error_dict(self):
        raw = "这不是JSON"
        result = parse_persona_output(raw)
        assert result.get("parse_error") is True
        assert result["raw_output"] == raw

    def test_markdown_wrapped_with_extra_whitespace(self):
        data = {"persona_id": "P04", "confidence": 0.8}
        raw = f"  ```json  \n  {json.dumps(data, ensure_ascii=False)}  \n  ```  "
        result = parse_persona_output(raw)
        assert result["persona_id"] == "P04"


class TestEstimateCost:
    def test_sonnet_pricing(self, budget_config):
        cost = estimate_cost(1000, 500, "claude-sonnet", budget_config)
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert abs(cost - expected) < 1e-10

    def test_haiku_pricing(self, budget_config):
        cost = estimate_cost(2000, 1000, "claude-haiku", budget_config)
        expected = (2000 / 1_000_000) * 0.25 + (1000 / 1_000_000) * 1.25
        assert abs(cost - expected) < 1e-10

    def test_opus_pricing(self, budget_config):
        cost = estimate_cost(500, 200, "claude-opus", budget_config)
        expected = (500 / 1_000_000) * 15.0 + (200 / 1_000_000) * 75.0
        assert abs(cost - expected) < 1e-10

    def test_zero_tokens(self, budget_config):
        cost = estimate_cost(0, 0, "claude-sonnet", budget_config)
        assert cost == 0.0


class TestSelectModel:
    def test_persona_with_model_hint(self, budget_config):
        persona = {"model_hint": "opus"}
        result = select_model(persona, budget_config)
        assert result == "claude-opus"

    def test_persona_with_sonnet_hint(self, budget_config):
        persona = {"model_hint": "sonnet"}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet"

    def test_persona_with_haiku_hint(self, budget_config):
        persona = {"model_hint": "haiku"}
        result = select_model(persona, budget_config)
        assert result == "claude-haiku"

    def test_persona_without_model_hint_uses_default(self, budget_config):
        persona = {}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet"

    def test_persona_with_none_model_hint_uses_default(self, budget_config):
        persona = {"model_hint": None}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet"
