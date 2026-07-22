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
