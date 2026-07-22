"""意图解析 LLM 档：此前硬编码 anthropic.Anthropic(api_key=...)，完全无视用户
BYOK 配的 provider/api_base/model——配了第三方中转（DeepSeek/Kimi/MiniMax 等）
的用户，key 会被拿去打官方 api.anthropic.com，认证必然失败，异常被吞掉，静默
退化成启发式档，界面上看起来就像"填了 key 也没用"。

覆盖：parse_intent_llm 现在走 runner.llm_client.chat_completion 统一出口，
provider/api_base/model 三个字段必须原样传下去，不能被丢在半路。
"""

import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, "src")

from app.services import intent_service  # noqa: E402


class TestParseIntentLlmRoutesThroughUnifiedClient:
    def test_anthropic_official_no_custom_model(self):
        """默认档（provider=anthropic，没填 model/api_base）：走官方地址 + settings.intent_model。"""
        fake_response = '{"task_type": "steam_page_review", "mode": "standard", "confidence": 0.9}'
        with patch(
            "runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)
        ) as mock_chat:
            result = intent_service.parse_intent_llm("帮我看看 Steam 商店页", api_key="sk-ant-test")

        assert result is not None
        assert result.method == "llm"
        assert result.task_type == "steam_page_review"
        _, kwargs = mock_chat.call_args
        assert kwargs["provider"] == "anthropic"
        assert kwargs["api_base"] is None
        assert kwargs["model"] == intent_service.settings.intent_model

    def test_custom_relay_config_passed_through_not_dropped(self):
        """这是曾经的真 bug：配了中转地址 + 自定义模型（如 MiniMax），
        之前这两个字段在半路就被丢了，请求永远打去官方地址。"""
        fake_response = '{"task_type": "demo_first_play", "mode": "standard", "confidence": 0.8}'
        with patch(
            "runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)
        ) as mock_chat:
            result = intent_service.parse_intent_llm(
                "看看这个 Demo",
                api_key="sk-cp-minimax-test",
                provider="anthropic",
                model="MiniMax-M3",
                api_base="https://api.minimaxi.com/anthropic",
            )

        assert result is not None
        _, kwargs = mock_chat.call_args
        assert kwargs["api_key"] == "sk-cp-minimax-test"
        assert kwargs["provider"] == "anthropic"
        assert kwargs["model"] == "MiniMax-M3"
        assert kwargs["api_base"] == "https://api.minimaxi.com/anthropic"

    def test_openai_compatible_provider_passed_through(self):
        fake_response = '{"task_type": "pricing_page_review", "mode": "quick", "confidence": 0.7}'
        with patch(
            "runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)
        ) as mock_chat:
            intent_service.parse_intent_llm(
                "看看这个定价页",
                api_key="sk-deepseek-test",
                provider="openai_compatible",
                model="deepseek-v4-pro",
                api_base="https://api.deepseek.com",
            )

        _, kwargs = mock_chat.call_args
        assert kwargs["provider"] == "openai_compatible"
        assert kwargs["model"] == "deepseek-v4-pro"

    def test_upstream_failure_falls_back_to_none_not_raises(self):
        """中转本身连不上/认证失败：捕获异常返回 None，调用方降级启发式，不能整个报错。"""
        with patch("runner.llm_client.chat_completion", side_effect=Exception("401 unauthorized")):
            result = intent_service.parse_intent_llm(
                "看看这个", api_key="bad-key", provider="anthropic", api_base="https://bad.example.com"
            )
        assert result is None

    def test_parse_intent_dispatcher_passes_provider_fields(self):
        fake_response = '{"task_type": "concept_review", "mode": "standard", "confidence": 0.85}'
        with patch("runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)) as mock_chat:
            result = intent_service.parse_intent(
                "评审一下这个概念",
                api_key="sk-cp-test",
                provider="anthropic",
                model="MiniMax-M3",
                api_base="https://api.minimaxi.com/anthropic",
            )
        assert result.method == "llm"
        _, kwargs = mock_chat.call_args
        assert kwargs["model"] == "MiniMax-M3"

    def test_parse_intent_falls_back_to_heuristic_without_key(self):
        result = intent_service.parse_intent("帮我看看 Steam 商店页", api_key=None)
        assert result.method == "heuristic"


class TestChatFeaturesHeuristic:
    """对话内插入技能/呼叫角色/长期评审项目——启发式档（零成本兜底）的字段提取。"""

    def test_skill_keyword_detected(self):
        r = intent_service.parse_intent_heuristic("帮我评审一下 Steam 商店页，红队来一下，专门挑毛病")
        assert r.skill_type == "red_team_audience"

    def test_no_skill_keyword_leaves_none(self):
        r = intent_service.parse_intent_heuristic("帮我评审一下 Steam 商店页")
        assert r.skill_type is None

    def test_persona_call_trigger_matches_archetype(self):
        r = intent_service.parse_intent_heuristic("叫上核心独立探索者这个角色，帮我看看这个游戏概念")
        assert "P01-indie-core-operator" in r.matched_personas

    def test_no_persona_trigger_means_no_match_even_if_archetype_mentioned(self):
        """光是提到某个 archetype 词不算"点名要角色"——没有触发词就不该误伤。"""
        r = intent_service.parse_intent_heuristic("这个游戏面向核心独立探索者这类人群，看看概念行不行")
        assert r.matched_personas == []

    def test_project_key_extracted_from_quoted_name(self):
        r = intent_service.parse_intent_heuristic(
            "创建「新手引导优化」长期评审项目，帮我看看新手引导流程"
        )
        assert r.project_key == "新手引导优化"

    def test_no_project_trigger_means_none(self):
        r = intent_service.parse_intent_heuristic("帮我看看新手引导流程")
        assert r.project_key is None


class TestChatFeaturesLlmDispatch:
    """LLM 档：这几个字段由模型直接判断，本地只做校验 + 复用同一套角色匹配逻辑。"""

    def test_skill_type_from_llm_passed_through_when_valid(self):
        fake_response = (
            '{"task_type": "steam_page_review", "mode": "standard", "confidence": 0.9, '
            '"skill_type": "red_team_audience", "persona_hint": null, "project_key": null}'
        )
        with patch("runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)):
            result = intent_service.parse_intent_llm("红队来一下", api_key="sk-test")
        assert result.skill_type == "red_team_audience"

    def test_invalid_skill_type_from_llm_is_dropped(self):
        """persona_generate 不是能通过评审创建触发的技能——模型瞎猜也要被本地过滤掉。"""
        fake_response = (
            '{"task_type": "steam_page_review", "mode": "standard", "confidence": 0.9, '
            '"skill_type": "persona_generate", "persona_hint": null, "project_key": null}'
        )
        with patch("runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)):
            result = intent_service.parse_intent_llm("随便看看", api_key="sk-test")
        assert result.skill_type is None

    def test_persona_hint_from_llm_resolved_against_pack_roster(self):
        fake_response = (
            '{"task_type": "concept_review", "mode": "standard", "persona_pack": "game-core", '
            '"confidence": 0.9, "persona_hint": "核心独立探索者", "skill_type": null, "project_key": null}'
        )
        with patch("runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)):
            result = intent_service.parse_intent_llm("帮我看看这个概念", api_key="sk-test")
        assert "P01-indie-core-operator" in result.matched_personas

    def test_project_key_from_llm_passed_through_and_trimmed(self):
        fake_response = (
            '{"task_type": "onboarding_review", "mode": "standard", "confidence": 0.9, '
            '"skill_type": null, "persona_hint": null, "project_key": "  新手引导优化  "}'
        )
        with patch("runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)):
            result = intent_service.parse_intent_llm("看看新手引导", api_key="sk-test")
        assert result.project_key == "新手引导优化"
