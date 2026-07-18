"""创业评审团（startup-panel）+ pitch_review 任务类型——"用自己的产品评自己的BP"链路验证。

与 test_general_consumer_pack.py 同一套验证纪律：
  1. 意图解析（启发式档）能识别 BP/路演/申报表类关键词
  2. pitch_review 没命中人格包关键词时默认落 startup-panel，不落 game-core
  3. 真实的 presets + startup-panel.yaml 能被 panel_selector 选出面板（端到端能跑）
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


class TestIntentHeuristicPitchReview:
    def test_detects_pitch_review_from_bp(self):
        result = intent_service.parse_intent_heuristic("帮我看看这份商业计划书写得行不行")
        assert result.task_type == "pitch_review"

    def test_detects_pitch_review_from_application_form(self):
        result = intent_service.parse_intent_heuristic("这是我的创业项目申报表，帮我用投资人的眼光过一遍")
        assert result.task_type == "pitch_review"
        assert result.persona_pack == "startup-panel"

    def test_pitch_review_defaults_to_startup_panel(self):
        """核心正确性：评 BP 不能被塞游戏玩家人格。"""
        result = intent_service.parse_intent_heuristic("下周要路演了，帮我提前挑挑毛病")
        assert result.task_type == "pitch_review"
        assert result.persona_pack == "startup-panel"

    def test_game_task_types_unaffected(self):
        """向后兼容：游戏向任务类型行为不变。"""
        result = intent_service.parse_intent_heuristic("帮我评审这个游戏的 Steam 商店页文案")
        assert result.task_type == "steam_page_review"
        assert result.persona_pack == "game-core"


class TestStartupPanelSelection:
    """跑真实的 presets + startup-panel.yaml，证明链路没断。"""

    @pytest.fixture(autouse=True)
    def _paths(self):
        self.personas_path = os.path.join(SRC_DIR, "personas", "startup-panel.yaml")
        self.presets_path = os.path.join(SRC_DIR, "presets", "panel-presets.yaml")
        assert os.path.isfile(self.personas_path)
        assert os.path.isfile(self.presets_path)

    def test_pack_has_eight_personas(self):
        from runner.panel_selector import load_personas

        personas = load_personas(self.personas_path)
        assert len(personas) == 8
        ids = {p["id"] for p in personas}
        assert "P54-angel-investor" in ids
        assert "P61-devils-advocate" in ids

    def test_select_panel_for_pitch_review(self):
        from runner.panel_selector import load_personas, load_presets, select_panel

        personas = load_personas(self.personas_path)
        presets = load_presets(self.presets_path)
        result = select_panel("pitch_review", personas, presets)
        assert len(result["selected"]) >= presets["pitch_review"]["min_panel_size"]
        selected_ids = {p["id"] for p in result["selected"]}
        # 毒舌怀疑型合伙人必须在默认面板里——对抗质询是产品的核心机制
        assert "P61-devils-advocate" in selected_ids

    def test_all_personas_have_pitch_review_affinity(self):
        """每个创业评审人格都应声明对 pitch_review 的亲和度——这是这组人格存在的意义。"""
        from runner.panel_selector import load_personas

        personas = load_personas(self.personas_path)
        for p in personas:
            assert "pitch_review" in p.get("task_affinity", {}), f"{p['id']} 缺 pitch_review 亲和度"
