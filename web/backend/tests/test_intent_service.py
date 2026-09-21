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


class TestEveryPackIsReachableFromChat:
    """每个人格包都必须能被对话入口路由到。

    本轮踩到的具体问题：新增了 launch-compliance 包（5 个人格，能真正把产品
    挡在上线门外的那类角色），但 PACK_KEYWORDS 里没有它——包在 /api/personas/packs
    里看得见、向导里选得到，唯独"帮我看看这个能不能过审"永远路由不过去。
    等于造了一个从主入口点不着的东西。
    """

    def test_pack_keywords_cover_every_yaml_pack(self):
        import glob
        import os

        from app.services.intent_service import DEFAULT_PACK_BY_TASK_TYPE, PACK_KEYWORDS

        # tests/ -> backend/ -> web/ -> 仓库根
        root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
        persona_dir = os.path.join(root, "src", "personas")
        packs = {
            os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(persona_dir, "*.yaml"))
        }
        assert packs, "没找到人格包目录，断言会假绿：%s" % persona_dir

        # game-core 是兜底默认包，不需要关键词
        routable = set(PACK_KEYWORDS) | set(DEFAULT_PACK_BY_TASK_TYPE.values()) | {"game-core"}
        unreachable = sorted(packs - routable)
        assert not unreachable, (
            "这些人格包从对话入口永远路由不到：%s。"
            "要么给 PACK_KEYWORDS 加关键词，要么在 DEFAULT_PACK_BY_TASK_TYPE 里指定。" % unreachable
        )

        # 反向：关键词表里不许有已经不存在的包（改名/删包后残留）
        ghosts = sorted(set(PACK_KEYWORDS) - packs)
        assert not ghosts, "PACK_KEYWORDS 里有 src/personas/ 下不存在的包：%s" % ghosts

    def test_compliance_queries_route_to_launch_compliance(self):
        from app.services.intent_service import parse_intent_heuristic

        for text in ["帮我看看这个能不能过审", "版号还没下来，这个题材有问题吗", "隐私政策要怎么写才能上架"]:
            assert parse_intent_heuristic(text).persona_pack == "launch-compliance", text

    def test_stronger_pack_signal_still_wins(self):
        """"手游的付费设计"命中 手游+内购 两个 mobile-f2p 词，不该被单个"合规"抢走。"""
        from app.services.intent_service import parse_intent_heuristic

        assert parse_intent_heuristic("帮我看看这手游的付费设计合不合规").persona_pack == "mobile-f2p"
        # "审核"是"评审"的日常说法，不该被当成平台送审
        assert parse_intent_heuristic("帮我审核一下 Steam 商店页").persona_pack == "game-core"


class TestStructuredOutputWiring:
    """意图解析必须把形状约束传给 chat_completion 的 json_schema：不传的话，
    llm_client 那边的强制工具调用/json_object 根本不启用，解析失败静默退化
    到启发式档的老问题原封不动，界面上还完全看不出来。"""

    def test_intent_parse_forwards_json_schema(self):
        from app.services.intent_service import _INTENT_SCHEMA, parse_intent_llm

        fake_response = (
            '{"task_type": "concept_review", "mode": "standard", "persona_pack": "game-core",'
            ' "confidence": 0.9, "clarifying_question": null, "skill_type": null,'
            ' "persona_hint": null, "project_key": null}'
        )
        with patch("runner.llm_client.chat_completion", return_value=(fake_response, 10, 5)) as mock_chat:
            result = parse_intent_llm("帮我评一下这个游戏概念", api_key="k")

        assert result is not None and result.task_type == "concept_review"
        assert mock_chat.call_args.kwargs["json_schema"] is _INTENT_SCHEMA
        # 提示词允许模型选不出时填 null，schema 不能把这些字段写死成 string
        assert _INTENT_SCHEMA["properties"]["task_type"]["type"] == ["string", "null"]
