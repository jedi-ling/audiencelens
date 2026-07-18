"""通用产品向任务类型 + general-consumer 人格包——"不要局限于玩家"的落地验证。

覆盖三件事：
  1. 意图解析（启发式档）能识别新任务类型的关键词
  2. 新任务类型在没有命中人格包关键词时，默认落到 general-consumer 而不是 game-core
  3. 真实的 panel-presets.yaml + general-consumer.yaml 能被 panel_selector 正常选出面板
     （证明这不是"只加了枚举值"的假通用，而是端到端能跑）
"""

import os
import sys

import pytest

from app.services import intent_service

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(BACKEND_DIR))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


class TestIntentHeuristicGenericTypes:
    def test_detects_pricing_page_review(self):
        # 用 "pricing" 而非泛化的"定价/价格"——那两个词已经被 monetization_review 占用，
        # 纯关键词打分对这类语义重叠无能为力，靠更具体的词才能消歧。
        result = intent_service.parse_intent_heuristic("帮我评审一下我们网站的 pricing 展示是否清晰")
        assert result.task_type == "pricing_page_review"

    def test_detects_onboarding_review(self):
        result = intent_service.parse_intent_heuristic("评审一下我们的新用户 onboarding 引导流程")
        assert result.task_type == "onboarding_review"

    def test_detects_product_feedback_review(self):
        result = intent_service.parse_intent_heuristic("帮我看看这份产品反馈收集页面设计得好不好")
        assert result.task_type == "product_feedback_review"

    def test_generic_task_type_defaults_to_general_consumer_pack(self):
        """核心正确性：不能因为没命中 PACK_KEYWORDS 就默认塞给 game-core。"""
        result = intent_service.parse_intent_heuristic("帮我评审一下我们网站的 pricing 展示是否清晰")
        assert result.persona_pack == "general-consumer"

    def test_game_specific_task_type_still_defaults_to_game_core(self):
        """向后兼容：老的游戏向任务类型行为完全不变。"""
        result = intent_service.parse_intent_heuristic("帮我评审这个游戏的 Steam 商店页文案")
        assert result.task_type == "steam_page_review"
        assert result.persona_pack == "game-core"

    def test_explicit_pack_keyword_overrides_default(self):
        """明确提到手游相关词时，即使任务类型是新类型，也该尊重更具体的 pack 信号。"""
        result = intent_service.parse_intent_heuristic("看看这个手游的 pricing 展示方案")
        assert result.task_type == "pricing_page_review"
        assert result.persona_pack == "mobile-f2p"

    def test_generic_pricing_phrase_not_misrouted_to_monetization(self):
        """回归用例：AskPage.tsx 的对话式入口示例文案就是这句——
        曾经因为"定价"关键词被 monetization_review 和 pricing_page_review 同时命中而误判
        （平局时更早定义的 monetization_review 会赢），导致 task_type/persona_pack 不匹配
        （monetization_review 的预设人格在 general-consumer.yaml 里根本不存在，面板会选空）。"""
        result = intent_service.parse_intent_heuristic("帮我评审一下这个产品的定价页，用户会不会觉得贵")
        assert result.task_type == "pricing_page_review"
        assert result.persona_pack == "general-consumer"


class TestGeneralConsumerPanelSelection:
    """跑真实的 presets + persona yaml，证明这条链路没有断。"""

    @pytest.fixture(autouse=True)
    def _paths(self):
        self.personas_path = os.path.join(SRC_DIR, "personas", "general-consumer.yaml")
        self.presets_path = os.path.join(SRC_DIR, "presets", "panel-presets.yaml")
        assert os.path.isfile(self.personas_path)
        assert os.path.isfile(self.presets_path)

    def test_pack_has_eight_personas(self):
        from runner.panel_selector import load_personas

        personas = load_personas(self.personas_path)
        assert len(personas) == 8
        ids = {p["id"] for p in personas}
        assert "P46-value-conscious-buyer" in ids

    @pytest.mark.parametrize(
        "task_type", ["product_feedback_review", "pricing_page_review", "onboarding_review"]
    )
    def test_select_panel_for_new_task_types(self, task_type):
        from runner.panel_selector import load_personas, load_presets, select_panel

        personas = load_personas(self.personas_path)
        presets = load_presets(self.presets_path)
        result = select_panel(task_type, personas, presets)
        assert len(result["selected"]) >= presets[task_type]["min_panel_size"]
        assert result["task_type"] == task_type

    def test_unknown_task_type_still_raises(self):
        from runner.panel_selector import load_personas, load_presets, select_panel

        personas = load_personas(self.personas_path)
        presets = load_presets(self.presets_path)
        with pytest.raises(ValueError):
            select_panel("not_a_real_task_type", personas, presets)
