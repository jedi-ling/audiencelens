"""统一 LLM 调用出口——不依赖 litellm（装不上，见模块 docstring）。
全部用 mock，不发真实网络请求：验证的是"两条 provider 路径的内容转换/参数传递对不对"，
不是"某个服务商今天是否在线"。
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "src")

from runner.llm_client import (  # noqa: E402
    LLMCallError,
    _parse_data_uri,
    _to_anthropic_content,
    chat_completion,
    supports_vision,
)
from runner.llm_client import test_connection as check_connection  # noqa: E402
# 起别名——否则 pytest 会把这个从 runner.llm_client 导入进来的同名函数
# 当成本文件里的测试用例收集，试图把它的形参当 fixture 注入，直接报错。


class TestSupportsVision:
    def test_claude_models_support_vision(self):
        assert supports_vision("claude-sonnet-4-20250514") is True
        assert supports_vision("claude-haiku-4-5-20251001") is True

    def test_gpt4o_supports_vision(self):
        assert supports_vision("gpt-4o") is True

    def test_deepseek_chat_does_not(self):
        assert supports_vision("deepseek-chat") is False


class TestParseDataUri:
    def test_parses_png(self):
        media_type, data = _parse_data_uri("data:image/png;base64,QUJD")
        assert media_type == "image/png"
        assert data == "QUJD"

    def test_rejects_non_data_uri(self):
        with pytest.raises(LLMCallError):
            _parse_data_uri("https://example.com/pic.png")


class TestToAnthropicContent:
    def test_string_passthrough(self):
        assert _to_anthropic_content("hello") == "hello"

    def test_converts_image_block(self):
        content = [
            {"type": "text", "text": "看看这个"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        ]
        result = _to_anthropic_content(content)
        assert result[0] == {"type": "text", "text": "看看这个"}
        assert result[1]["type"] == "image"
        assert result[1]["source"] == {"type": "base64", "media_type": "image/png", "data": "QUJD"}


class TestChatCompletionAnthropic:
    def test_calls_anthropic_sdk_with_key_and_model(self):
        fake_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hi there")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        fake_anthropic_module = SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

        with patch.dict(sys.modules, {"anthropic": fake_anthropic_module}):
            text, in_tok, out_tok = chat_completion(
                model="claude-sonnet-4-20250514", prompt="Hi", api_key="sk-ant-test", provider="anthropic"
            )

        assert text == "hi there"
        assert in_tok == 10
        assert out_tok == 5
        fake_anthropic_module.Anthropic.assert_called_once_with(api_key="sk-ant-test", base_url=None, timeout=120.0)
        fake_client.messages.create.assert_called_once()
        _, kwargs = fake_client.messages.create.call_args
        assert kwargs["model"] == "claude-sonnet-4-20250514"

    def test_custom_api_base_reaches_anthropic_sdk(self):
        """Anthropic 也有第三方中转/代理场景（cc-switch 的 aggregator/relay 分类），
        api_base 不该被 anthropic 分支静默丢弃——这是曾经存在过的真 bug。"""
        fake_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        fake_anthropic_module = SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

        with patch.dict(sys.modules, {"anthropic": fake_anthropic_module}):
            chat_completion(
                model="claude-sonnet-4-20250514",
                prompt="Hi",
                api_key="sk-ant-test",
                provider="anthropic",
                api_base="https://relay.example.com/anthropic",
            )

        fake_anthropic_module.Anthropic.assert_called_once_with(
            api_key="sk-ant-test", base_url="https://relay.example.com/anthropic", timeout=120.0
        )

    def test_multimodal_content_reaches_anthropic_when_vision_capable(self):
        fake_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="看到了")],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        fake_anthropic_module = SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

        content = [
            {"type": "text", "text": "看看这张图"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        ]
        with patch.dict(sys.modules, {"anthropic": fake_anthropic_module}):
            chat_completion(
                model="claude-sonnet-4-20250514", prompt=content, api_key="sk-ant-test", provider="anthropic"
            )
        _, kwargs = fake_client.messages.create.call_args
        sent_content = kwargs["messages"][0]["content"]
        assert sent_content[0] == {"type": "text", "text": "看看这张图"}
        assert sent_content[1]["type"] == "image"


class TestChatCompletionOpenAiCompatible:
    def test_posts_openai_format_to_custom_base(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "深圳你好"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
        with patch("httpx.post", return_value=fake_resp) as mock_post:
            text, in_tok, out_tok = chat_completion(
                model="deepseek-chat",
                prompt="你好",
                api_key="sk-deepseek-test",
                provider="openai_compatible",
                api_base="https://api.deepseek.com",
            )
        assert text == "深圳你好"
        assert in_tok == 3
        assert out_tok == 2
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.deepseek.com/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-deepseek-test"
        assert kwargs["json"]["model"] == "deepseek-chat"

    def test_non_vision_model_gets_text_only_content(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        content = [
            {"type": "text", "text": "文字材料"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        ]
        with patch("httpx.post", return_value=fake_resp) as mock_post:
            chat_completion(
                model="deepseek-chat", prompt=content, api_key="x",
                provider="openai_compatible", api_base="https://api.deepseek.com",
            )
        _, kwargs = mock_post.call_args
        sent_content = kwargs["json"]["messages"][0]["content"]
        assert sent_content == "文字材料"  # 图片块被降级丢弃，只剩文字

    def test_defaults_to_openai_base_when_none_given(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        with patch("httpx.post", return_value=fake_resp) as mock_post:
            chat_completion(model="gpt-4o", prompt="hi", api_key="x", provider="openai_compatible")
        args, _ = mock_post.call_args
        assert args[0] == "https://api.openai.com/v1/chat/completions"

    def test_non_200_raises_llm_call_error(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 401
        fake_resp.text = "invalid api key"
        with patch("httpx.post", return_value=fake_resp):
            with pytest.raises(LLMCallError):
                chat_completion(
                    model="deepseek-chat", prompt="hi", api_key="bad-key",
                    provider="openai_compatible", api_base="https://api.deepseek.com",
                )

    def test_malformed_response_raises_llm_call_error(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"unexpected": "shape"}
        with patch("httpx.post", return_value=fake_resp):
            with pytest.raises(LLMCallError):
                chat_completion(
                    model="deepseek-chat", prompt="hi", api_key="x",
                    provider="openai_compatible", api_base="https://api.deepseek.com",
                )


class TestTestConnection:
    def test_success_shape(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        with patch("httpx.post", return_value=fake_resp):
            result = check_connection(
                model="deepseek-chat", api_key="x", provider="openai_compatible",
                api_base="https://api.deepseek.com",
            )
        assert result["connected"] is True
        assert result["model"] == "deepseek-chat"
        assert "pong" in result["sample"]

    def test_failure_shape_never_raises(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 500
        fake_resp.text = "server error"
        with patch("httpx.post", return_value=fake_resp):
            result = check_connection(
                model="deepseek-chat", api_key="x", provider="openai_compatible",
                api_base="https://api.deepseek.com",
            )
        assert result["connected"] is False
        assert "error" in result
