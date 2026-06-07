import pytest
import yaml
from runner.panel_selector import (
    load_personas,
    load_presets,
    select_panel,
    compute_behavioral_distance,
    ensure_diversity,
)

MINI_PERSONAS = [
    {
        "id": "P01-test-one",
        "name": "测试一",
        "behavior_profile": {
            "patience": "高",
            "genre_literacy": "高",
            "novelty_seeking": "高",
            "risk_tolerance": "中",
            "social_influence": "低",
            "completion_drive": "中",
            "price_sensitivity": "中",
            "criticism_style": "分析直给",
            "emotional_engagement": "中",
            "agency_preference": "高",
            "tolerance_for_ambiguity": "高",
            "platform_loyalty": "中",
        },
        "evidence_types_needed": ["核心循环说明", "实机视频"],
    },
    {
        "id": "P06-test-six",
        "name": "测试六",
        "behavior_profile": {
            "patience": "中",
            "genre_literacy": "中",
            "novelty_seeking": "高",
            "risk_tolerance": "中",
            "social_influence": "中",
            "completion_drive": "低",
            "price_sensitivity": "中",
            "criticism_style": "感受具体",
            "emotional_engagement": "高",
            "agency_preference": "低",
            "tolerance_for_ambiguity": "中",
            "platform_loyalty": "中",
        },
        "evidence_types_needed": ["胶囊图", "截图", "预告片"],
    },
    {
        "id": "P14-test-fourteen",
        "name": "测试十四",
        "behavior_profile": {
            "patience": "中",
            "genre_literacy": "中",
            "novelty_seeking": "低",
            "risk_tolerance": "低",
            "social_influence": "中",
            "completion_drive": "中",
            "price_sensitivity": "很高",
            "criticism_style": "价值评估",
            "emotional_engagement": "中",
            "agency_preference": "中",
            "tolerance_for_ambiguity": "低",
            "platform_loyalty": "中",
        },
        "evidence_types_needed": ["价格", "版本差异", "DLC说明"],
    },
    {
        "id": "P15-test-fifteen",
        "name": "测试十五",
        "behavior_profile": {
            "patience": "很低",
            "genre_literacy": "高",
            "novelty_seeking": "低",
            "risk_tolerance": "低",
            "social_influence": "高",
            "completion_drive": "低",
            "price_sensitivity": "高",
            "criticism_style": "尖锐怀疑",
            "emotional_engagement": "低",
            "agency_preference": "中",
            "tolerance_for_ambiguity": "低",
            "platform_loyalty": "低",
        },
        "evidence_types_needed": ["实机视频", "评论区样本"],
    },
    {
        "id": "P16-test-sixteen",
        "name": "测试十六",
        "behavior_profile": {
            "patience": "中",
            "genre_literacy": "很高",
            "novelty_seeking": "低",
            "risk_tolerance": "低",
            "social_influence": "中",
            "completion_drive": "中",
            "price_sensitivity": "中",
            "criticism_style": "对标式",
            "emotional_engagement": "低",
            "agency_preference": "中",
            "tolerance_for_ambiguity": "低",
            "platform_loyalty": "中",
        },
        "evidence_types_needed": ["竞品对比", "核心卖点"],
    },
]

MINI_PRESETS = {
    "steam_page_review": {
        "description": "Steam商店页评审",
        "default_personas": ["P06", "P14", "P15"],
        "optional_personas": ["P01"],
        "min_panel_size": 2,
        "max_panel_size": 5,
    },
    "concept_review": {
        "description": "概念评审",
        "default_personas": ["P01", "P16"],
        "optional_personas": ["P06"],
        "min_panel_size": 2,
        "max_panel_size": 4,
    },
    "monetization_review": {
        "description": "商业化评审",
        "default_personas": ["P14", "P15"],
        "optional_personas": [],
        "min_panel_size": 2,
        "max_panel_size": 4,
    },
}


def _write_yaml(tmp_path, filename, data):
    p = tmp_path / filename
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return str(p)


class TestLoadPersonas:
    def test_load_personas_returns_list(self, tmp_path):
        yaml_data = {"version": "0.1.0", "panel_id": "test", "personas": MINI_PERSONAS}
        path = _write_yaml(tmp_path, "personas.yaml", yaml_data)
        result = load_personas(path)
        assert isinstance(result, list)
        assert len(result) == 5

    def test_load_personas_each_item_is_dict(self, tmp_path):
        yaml_data = {"version": "0.1.0", "panel_id": "test", "personas": MINI_PERSONAS}
        path = _write_yaml(tmp_path, "personas.yaml", yaml_data)
        result = load_personas(path)
        for item in result:
            assert isinstance(item, dict)
            assert "id" in item
            assert "behavior_profile" in item

    def test_load_personas_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_personas("/nonexistent/path.yaml")


class TestLoadPresets:
    def test_load_presets_returns_dict(self, tmp_path):
        yaml_data = {"version": "0.1.0", "presets": MINI_PRESETS}
        path = _write_yaml(tmp_path, "presets.yaml", yaml_data)
        result = load_presets(path)
        assert isinstance(result, dict)
        assert "steam_page_review" in result
        assert "concept_review" in result

    def test_load_presets_structure(self, tmp_path):
        yaml_data = {"version": "0.1.0", "presets": MINI_PRESETS}
        path = _write_yaml(tmp_path, "presets.yaml", yaml_data)
        result = load_presets(path)
        preset = result["steam_page_review"]
        assert "default_personas" in preset
        assert isinstance(preset["default_personas"], list)


class TestSelectPanel:
    def test_select_panel_normal(self):
        result = select_panel("steam_page_review", MINI_PERSONAS, MINI_PRESETS)
        assert result["task_type"] == "steam_page_review"
        assert len(result["selected"]) >= 2
        selected_ids = [p["id"] for p in result["selected"]]
        assert "P06-test-six" in selected_ids
        assert "P14-test-fourteen" in selected_ids

    def test_select_panel_unknown_task_type(self):
        with pytest.raises(ValueError, match="Unknown task type"):
            select_panel("nonexistent_task", MINI_PERSONAS, MINI_PRESETS)

    def test_select_panel_dissent_auto_add(self):
        no_dissent_presets = {
            "no_dissent_task": {
                "description": "无反对者任务",
                "default_personas": ["P01", "P06", "P14"],
                "optional_personas": [],
                "min_panel_size": 2,
                "max_panel_size": 5,
            }
        }
        result = select_panel("no_dissent_task", MINI_PERSONAS, no_dissent_presets)
        selected_ids = [p["id"] for p in result["selected"]]
        has_dissenter = any(
            pid.startswith("P15") or pid.startswith("P16") for pid in selected_ids
        )
        assert has_dissenter

    def test_select_panel_dissent_already_present(self):
        result = select_panel("steam_page_review", MINI_PERSONAS, MINI_PRESETS)
        selected_ids = [p["id"] for p in result["selected"]]
        p15_count = sum(1 for pid in selected_ids if pid.startswith("P15"))
        assert p15_count <= 1

    def test_select_panel_with_evidence_filter(self):
        result = select_panel(
            "steam_page_review",
            MINI_PERSONAS,
            MINI_PRESETS,
            artifact_evidence_types=["胶囊图", "截图"],
        )
        dissenters = [p for p in result["selected"] if p["id"].startswith(("P15", "P16"))]
        non_dissenters = [p for p in result["selected"] if not p["id"].startswith(("P15", "P16"))]
        for p in non_dissenters:
            if "evidence_types_needed" in p:
                overlap = set(p["evidence_types_needed"]) & {"胶囊图", "截图"}
                assert len(overlap) > 0

    def test_select_panel_evidence_skipped_recorded(self):
        result = select_panel(
            "steam_page_review",
            MINI_PERSONAS,
            MINI_PRESETS,
            artifact_evidence_types=["胶囊图", "截图"],
        )
        skipped_ids = [s["persona_id"] for s in result["skipped"]]
        assert "P15-test-fifteen" in skipped_ids

    def test_select_panel_no_evidence_filter(self):
        result = select_panel("steam_page_review", MINI_PERSONAS, MINI_PRESETS)
        assert len(result["selected"]) == 3

    def test_select_panel_returns_skipped_list(self):
        result = select_panel("steam_page_review", MINI_PERSONAS, MINI_PRESETS)
        assert "skipped" in result
        assert isinstance(result["skipped"], list)


class TestComputeBehavioralDistance:
    def test_same_persona_distance_zero(self):
        p = MINI_PERSONAS[0]
        dist = compute_behavioral_distance(p, p)
        assert dist == 0.0

    def test_opposite_personas_large_distance(self):
        p_low = {
            "id": "X-low",
            "behavior_profile": {
                "patience": "很低",
                "genre_literacy": "很低",
                "novelty_seeking": "很低",
                "risk_tolerance": "低",
                "social_influence": "低",
                "completion_drive": "很低",
                "price_sensitivity": "很低",
                "criticism_style": "分析直给",
                "emotional_engagement": "低",
                "agency_preference": "低",
                "tolerance_for_ambiguity": "低",
                "platform_loyalty": "低",
            },
        }
        p_high = {
            "id": "X-high",
            "behavior_profile": {
                "patience": "很高",
                "genre_literacy": "很高",
                "novelty_seeking": "很高",
                "risk_tolerance": "高",
                "social_influence": "很高",
                "completion_drive": "很高",
                "price_sensitivity": "很高",
                "criticism_style": "尖锐怀疑",
                "emotional_engagement": "高",
                "agency_preference": "高",
                "tolerance_for_ambiguity": "高",
                "platform_loyalty": "高",
            },
        }
        dist = compute_behavioral_distance(p_low, p_high)
        assert dist == 1.0

    def test_known_distance_p01_p06(self):
        p01 = MINI_PERSONAS[0]
        p06 = MINI_PERSONAS[1]
        dist = compute_behavioral_distance(p01, p06)
        assert 0.0 < dist < 1.0

    def test_distance_symmetry(self):
        p01 = MINI_PERSONAS[0]
        p06 = MINI_PERSONAS[1]
        d1 = compute_behavioral_distance(p01, p06)
        d2 = compute_behavioral_distance(p06, p01)
        assert abs(d1 - d2) < 1e-9

    def test_distance_normalized(self):
        for i in range(len(MINI_PERSONAS)):
            for j in range(i + 1, len(MINI_PERSONAS)):
                dist = compute_behavioral_distance(MINI_PERSONAS[i], MINI_PERSONAS[j])
                assert 0.0 <= dist <= 1.0

    def test_distance_p01_p15(self):
        p01 = MINI_PERSONAS[0]
        p15 = MINI_PERSONAS[3]
        dist = compute_behavioral_distance(p01, p15)
        assert dist > 0.3


class TestEnsureDiversity:
    def test_no_redundancy(self):
        diverse = [MINI_PERSONAS[0], MINI_PERSONAS[3]]
        result = ensure_diversity(diverse, min_distance=0.1)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_with_redundancy(self):
        p1 = MINI_PERSONAS[0]
        p2 = dict(MINI_PERSONAS[0])
        p2["id"] = "P01-clone"
        result = ensure_diversity([p1, p2], min_distance=0.1)
        assert len(result) > 0

    def test_redundancy_pair_format(self):
        p1 = MINI_PERSONAS[0]
        p2 = dict(MINI_PERSONAS[0])
        p2["id"] = "P01-clone"
        result = ensure_diversity([p1, p2], min_distance=0.1)
        pair = result[0]
        assert "persona_1" in pair
        assert "persona_2" in pair
        assert "distance" in pair

    def test_empty_panel(self):
        result = ensure_diversity([], min_distance=0.2)
        assert result == []

    def test_single_persona(self):
        result = ensure_diversity([MINI_PERSONAS[0]], min_distance=0.2)
        assert result == []

    def test_custom_min_distance(self):
        p1 = MINI_PERSONAS[0]
        p2 = MINI_PERSONAS[1]
        result_strict = ensure_diversity([p1, p2], min_distance=0.01)
        result_loose = ensure_diversity([p1, p2], min_distance=0.9)
        assert len(result_strict) <= len(result_loose)
