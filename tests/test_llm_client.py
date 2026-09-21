"""统一 LLM 调用出口——不依赖 litellm（装不上，见模块 docstring）。
全部用 mock，不发真实网络请求：验证的是"两条 provider 路径的内容转换/参数传递对不对"，
不是"某个服务商今天是否在线"。
"""

import json
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
    is_retryable_error,
    supports_vision,
)
from runner.llm_client import test_connection as check_connection  # noqa: E402
from runner.persona_agent import estimate_cost  # noqa: E402
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

    def test_minimax_m3_supports_vision(self):
        # MiniMax-M3 起原生多模态（2026-07 官方发布确认）——此前漏收进
        # VISION_CAPABLE_PREFIXES，导致带图追问被误判成"模型不支持视觉"
        # 静默丢图，是本清单维护滞后，不是模型真没有该能力。
        assert supports_vision("MiniMax-M3") is True

    def test_matching_is_case_insensitive(self):
        # 各家模型名大小写不统一，前缀匹配不该因为大小写差异漏判
        assert supports_vision("Claude-Sonnet-4-20250514") is True
        assert supports_vision("MINIMAX-M3") is True


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


class TestPromptCaching:
    """system 参数不传 = 老行为完全不变（前面几个 TestChatCompletion* 类已经在
    验证这一半）。这里只测新增的那一半：传了 system 之后，两条 provider 路径
    分别接住它的方式不一样——Anthropic 走 cache_control，OpenAI 兼容协议
    走消息列表最前面的 system 消息（多数第三方服务商靠这个吃隐式前缀缓存）。"""

    def test_anthropic_system_gets_cache_control(self):
        fake_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        fake_anthropic_module = SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

        with patch.dict(sys.modules, {"anthropic": fake_anthropic_module}):
            chat_completion(
                model="claude-sonnet-4-20250514", prompt="人格专属部分", api_key="sk-ant-test",
                provider="anthropic", system="共享的评审材料前缀",
            )

        _, kwargs = fake_client.messages.create.call_args
        assert kwargs["system"] == [
            {"type": "text", "text": "共享的评审材料前缀", "cache_control": {"type": "ephemeral"}}
        ]
        # system 独立于 messages，别把它也拼进用户消息里——那样会被发两遍
        assert kwargs["messages"] == [{"role": "user", "content": "人格专属部分"}]

    def test_anthropic_without_system_omits_the_field_entirely(self):
        """老调用方不传 system：完全不该出现在发给 SDK 的参数里，
        不是传个空值——那样第一次改动就会让所有既有单元测试的
        call_args 断言集合多出一个陌生 key。"""
        fake_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        fake_anthropic_module = SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

        with patch.dict(sys.modules, {"anthropic": fake_anthropic_module}):
            chat_completion(
                model="claude-sonnet-4-20250514", prompt="hi", api_key="sk-ant-test", provider="anthropic"
            )

        _, kwargs = fake_client.messages.create.call_args
        assert "system" not in kwargs

    def test_anthropic_cache_creation_returns_true_tokens_and_weighted_cost(self):
        """缓存写入这一次：**两半都要对**。

        1) 返回的 input_tokens 必须是**真实 token 总数**（未命中 + 写入 + 读取）。
           这个数字会被 web 后端原样落库，终身 token 上限和后台用量面板都读它——
           以前这里返回的是掺了计费倍率的"等价满价 token"，用量统计因此失真。
        2) 但算出来的钱仍然要带缓存倍率（写 1.25x）：折扣挪到了
           persona_agent.estimate_cost 的 cache_breakdown 参数上，没挪丢。
        """
        fake_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(
                input_tokens=50,  # 这次新增、没缓存的部分
                output_tokens=5,
                cache_creation_input_tokens=1000,  # 首次把 shared 写入缓存
                cache_read_input_tokens=0,
            ),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        fake_anthropic_module = SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

        cache_usage = {}
        with patch.dict(sys.modules, {"anthropic": fake_anthropic_module}):
            _, in_tok, _ = chat_completion(
                model="claude-sonnet-4-20250514", prompt="hi", api_key="sk-ant-test",
                provider="anthropic", system="shared", usage_details=cache_usage,
            )

        # 真实 token 数：50 + 1000 = 1050（不是折算后的 1300）
        assert in_tok == 1050
        assert cache_usage == {
            "uncached_input_tokens": 50,
            "cache_creation_input_tokens": 1000,
            "cache_read_input_tokens": 0,
        }

        budget = {"model_pricing": {"m": {"input_per_mtok": 1_000_000.0, "output_per_mtok": 0.0}}}
        # 计费等价：50 + 1000*1.25 = 1300
        assert estimate_cost(in_tok, 0, "m", budget, cache_breakdown=cache_usage) == pytest.approx(1300.0)
        # 不给明细就按满价算（宁可高估，成本闸不会失灵）
        assert estimate_cost(in_tok, 0, "m", budget) == pytest.approx(1050.0)

    def test_anthropic_cache_hit_keeps_true_tokens_but_costs_a_tenth(self):
        """第二位及以后的人格：这次命中了第一位人格刚写入的缓存。

        1000 个被缓存的 token **仍然是 1000 个真实 token**（用量口径），
        但只该按 10% 计费——"缓存省钱"要落在钱上，不能落在 token 计数上。
        """
        fake_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(
                input_tokens=50,
                output_tokens=5,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=1000,
            ),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        fake_anthropic_module = SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

        cache_usage = {}
        with patch.dict(sys.modules, {"anthropic": fake_anthropic_module}):
            _, in_tok, _ = chat_completion(
                model="claude-sonnet-4-20250514", prompt="hi", api_key="sk-ant-test",
                provider="anthropic", system="shared", usage_details=cache_usage,
            )

        # 用量口径：真实 1050 个 token
        assert in_tok == 1050
        assert cache_usage["cache_read_input_tokens"] == 1000

        budget = {"model_pricing": {"m": {"input_per_mtok": 1_000_000.0, "output_per_mtok": 0.0}}}
        # 计费口径：50 + 1000*0.1 = 150，远低于把 1000 当满价算的 1050
        assert estimate_cost(in_tok, 0, "m", budget, cache_breakdown=cache_usage) == pytest.approx(150.0)

    def test_openai_compatible_prepends_system_message(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
        with patch("httpx.post", return_value=fake_resp) as mock_post:
            chat_completion(
                model="deepseek-chat", prompt="人格专属部分", api_key="x",
                provider="openai_compatible", api_base="https://api.deepseek.com",
                system="共享的评审材料前缀",
            )
        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        # system 必须排在第一位——排在别处或混进 user 消息里，"跟上次请求逐字重复
        # 的前缀"这个判断条件就不成立了，第三方服务商的隐式缓存吃不到
        assert messages[0] == {"role": "system", "content": "共享的评审材料前缀"}
        assert messages[1] == {"role": "user", "content": "人格专属部分"}

    def test_openai_compatible_without_system_keeps_old_single_message_shape(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        with patch("httpx.post", return_value=fake_resp) as mock_post:
            chat_completion(
                model="deepseek-chat", prompt="hi", api_key="x",
                provider="openai_compatible", api_base="https://api.deepseek.com",
            )
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["messages"] == [{"role": "user", "content": "hi"}]


class TestStructuredOutput:
    """json_schema 不传 = 老行为（前面的类已经在验证）。这里测传了之后：
    Anthropic 走强制工具调用、回复必然是合法 JSON；OpenAI 兼容开 json_object，
    并且遇到不认这个字段的服务商能退回老请求，不把整次评审拖死。"""

    SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "output-schema",
        "type": "object",
        "required": ["primary_stance"],
        "properties": {"primary_stance": {"type": "string"}},
    }

    def _anthropic(self, content_blocks, usage=None):
        fake_response = SimpleNamespace(
            content=content_blocks,
            usage=usage or SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        return fake_client, SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

    def test_anthropic_forces_a_tool_with_the_schema(self):
        fake_client, module = self._anthropic(
            [SimpleNamespace(type="tool_use", name="submit_review", input={"primary_stance": "观望"})]
        )
        with patch.dict(sys.modules, {"anthropic": module}):
            text, _, _ = chat_completion(
                model="claude-sonnet-4-20250514", prompt="hi", api_key="k",
                provider="anthropic", json_schema=self.SCHEMA,
            )

        _, kwargs = fake_client.messages.create.call_args
        assert kwargs["tool_choice"] == {"type": "tool", "name": "submit_review"}
        tool = kwargs["tools"][0]
        assert tool["name"] == "submit_review"
        # $schema/$id 是给校验器看的，Anthropic 的 input_schema 不认，必须剔掉
        assert "$schema" not in tool["input_schema"]
        assert "$id" not in tool["input_schema"]
        assert tool["input_schema"]["required"] == ["primary_stance"]
        # 回的是 JSON 字符串——下游 parse_persona_output 的裸 json.loads 兜底直接命中
        assert json.loads(text) == {"primary_stance": "观望"}

    def test_anthropic_tool_input_keeps_unicode_readable(self):
        """ensure_ascii=False：中文不能变成 \\uXXXX，否则日志和 prompt 调试字段没法读。"""
        _, module = self._anthropic(
            [SimpleNamespace(type="tool_use", name="submit_review", input={"primary_stance": "会买"})]
        )
        with patch.dict(sys.modules, {"anthropic": module}):
            text, _, _ = chat_completion(
                model="claude-sonnet-4-20250514", prompt="hi", api_key="k",
                provider="anthropic", json_schema=self.SCHEMA,
            )
        assert "会买" in text

    def test_anthropic_without_schema_sends_no_tools(self):
        fake_client, module = self._anthropic([SimpleNamespace(type="text", text="ok")])
        with patch.dict(sys.modules, {"anthropic": module}):
            chat_completion(model="claude-sonnet-4-20250514", prompt="hi", api_key="k", provider="anthropic")
        _, kwargs = fake_client.messages.create.call_args
        assert "tools" not in kwargs
        assert "tool_choice" not in kwargs

    def test_anthropic_falls_back_to_text_if_no_tool_block(self):
        """强制了工具但回复里没有 tool_use（理论上不该发生）：退回文本让下游
        如实报"无法解析"，不在这里编一个空 {} 冒充成功。"""
        _, module = self._anthropic([SimpleNamespace(type="text", text="我不想用工具")])
        with patch.dict(sys.modules, {"anthropic": module}):
            text, _, _ = chat_completion(
                model="claude-sonnet-4-20250514", prompt="hi", api_key="k",
                provider="anthropic", json_schema=self.SCHEMA,
            )
        assert text == "我不想用工具"

    def _ok_resp(self, content='{"primary_stance": "观望"}'):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        return resp

    def test_openai_compatible_requests_json_object(self):
        with patch("httpx.post", return_value=self._ok_resp()) as mock_post:
            text, _, _ = chat_completion(
                model="deepseek-chat", prompt="hi", api_key="x", provider="openai_compatible",
                api_base="https://api.deepseek.com", json_schema=self.SCHEMA,
            )
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["response_format"] == {"type": "json_object"}
        assert json.loads(text) == {"primary_stance": "观望"}

    def test_openai_compatible_without_schema_sends_no_response_format(self):
        with patch("httpx.post", return_value=self._ok_resp()) as mock_post:
            chat_completion(
                model="deepseek-chat", prompt="hi", api_key="x", provider="openai_compatible",
                api_base="https://api.deepseek.com",
            )
        _, kwargs = mock_post.call_args
        assert "response_format" not in kwargs["json"]

    def test_openai_compatible_retries_once_without_response_format_on_400(self):
        """不认 response_format 的服务商会 400 拒收：退回老请求再发一次，
        评审继续跑，而不是整位人格因为一个可选字段就失败。"""
        bad = MagicMock()
        bad.status_code = 400
        bad.text = "unknown field response_format"
        with patch("httpx.post", side_effect=[bad, self._ok_resp()]) as mock_post:
            text, _, _ = chat_completion(
                model="llama3", prompt="hi", api_key="x", provider="openai_compatible",
                api_base="http://localhost:11434/v1", json_schema=self.SCHEMA,
            )
        assert mock_post.call_count == 2
        first = mock_post.call_args_list[0].kwargs["json"]
        second = mock_post.call_args_list[1].kwargs["json"]
        assert "response_format" in first
        assert "response_format" not in second
        assert json.loads(text) == {"primary_stance": "观望"}

    def test_openai_compatible_does_not_retry_400_when_no_response_format_was_sent(self):
        """400 退避只针对 response_format 这一个字段：没发它时 400 就是请求本身
        不合法，照旧原样报错，不该多发一次。"""
        bad = MagicMock()
        bad.status_code = 400
        bad.text = "bad request"
        with patch("httpx.post", return_value=bad) as mock_post:
            with pytest.raises(LLMCallError):
                chat_completion(
                    model="deepseek-chat", prompt="hi", api_key="x", provider="openai_compatible",
                    api_base="https://api.deepseek.com",
                )
        assert mock_post.call_count == 1


class TestSamplingParamsAndModelQuirks:
    """新一代模型移除了一些老参数，传过去就是 400（不可重试的死错）。
    这几条覆盖的都是"发出去的请求里到底有没有那个字段"。"""

    SCHEMA = {"type": "object", "properties": {"primary_stance": {"type": "string"}}}

    def _anthropic(self, blocks=None, stop_reason=None):
        fake_response = SimpleNamespace(
            content=blocks if blocks is not None else [SimpleNamespace(type="text", text="ok")],
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_response
        return fake_client, SimpleNamespace(Anthropic=MagicMock(return_value=fake_client))

    def test_anthropic_omits_temperature_by_default(self):
        """Sonnet 5 / Opus 5 移除了采样参数：只要请求体里出现非默认 temperature
        就是 400，而 400 不可重试——每一位人格都会永久失败。默认必须**不发**。"""
        fake_client, module = self._anthropic()
        with patch.dict(sys.modules, {"anthropic": module}):
            chat_completion(model="claude-sonnet-5", prompt="hi", api_key="k", provider="anthropic")
        _, kwargs = fake_client.messages.create.call_args
        assert "temperature" not in kwargs

    def test_anthropic_sends_temperature_only_when_asked(self):
        fake_client, module = self._anthropic()
        with patch.dict(sys.modules, {"anthropic": module}):
            chat_completion(
                model="claude-sonnet-4-20250514", prompt="hi", api_key="k",
                provider="anthropic", temperature=0.2,
            )
        _, kwargs = fake_client.messages.create.call_args
        assert kwargs["temperature"] == 0.2

    def test_openai_compatible_omits_temperature_by_default(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        with patch("httpx.post", return_value=fake_resp) as mock_post:
            chat_completion(
                model="deepseek-v4-pro", prompt="hi", api_key="x",
                provider="openai_compatible", api_base="https://api.deepseek.com",
            )
        _, kwargs = mock_post.call_args
        assert "temperature" not in kwargs["json"]

    def test_models_without_forced_tool_use_fall_back_to_auto(self):
        """Fable / Mythos 这代移除了强制工具调用，tool_choice={"type":"tool"} 直接 400。
        退回 auto，并在提示词里点名要它调这个工具（否则它会写散文）。"""
        fake_client, module = self._anthropic(
            [SimpleNamespace(type="tool_use", name="submit_review", input={"primary_stance": "观望"})]
        )
        with patch.dict(sys.modules, {"anthropic": module}):
            chat_completion(
                model="claude-fable-5-1", prompt="hi", api_key="k",
                provider="anthropic", json_schema=self.SCHEMA,
            )
        _, kwargs = fake_client.messages.create.call_args
        assert kwargs["tool_choice"] == {"type": "auto"}
        # 工具定义本身不能丢，否则模型压根没地方交卷
        assert kwargs["tools"][0]["name"] == "submit_review"
        assert "submit_review" in kwargs["messages"][0]["content"]

    def test_truncated_structured_output_is_a_non_retryable_failure(self):
        """stop_reason=max_tokens 时 tool_use 的 input 是**残缺**的，但结构上能解析——
        不拦下来就会有半份评审被当成成功计进报告和账单。"""
        _, module = self._anthropic(
            [SimpleNamespace(type="tool_use", name="submit_review", input={"primary_stance": "观"})],
            stop_reason="max_tokens",
        )
        with patch.dict(sys.modules, {"anthropic": module}):
            with pytest.raises(LLMCallError) as exc:
                chat_completion(
                    model="claude-sonnet-5", prompt="hi", api_key="k",
                    provider="anthropic", json_schema=self.SCHEMA,
                )
        assert "截断" in str(exc.value)
        assert is_retryable_error(exc.value) is False

    def test_refusal_is_a_non_retryable_failure(self):
        """stop_reason=refusal 时连 tool_use 块都没有，以前会静默变成空文本，
        再被当成解析失败白白重试 3 次付费调用。"""
        _, module = self._anthropic([], stop_reason="refusal")
        with patch.dict(sys.modules, {"anthropic": module}):
            with pytest.raises(LLMCallError) as exc:
                chat_completion(
                    model="claude-sonnet-5", prompt="hi", api_key="k",
                    provider="anthropic", json_schema=self.SCHEMA,
                )
        assert "拒绝作答" in str(exc.value)
        assert is_retryable_error(exc.value) is False


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
