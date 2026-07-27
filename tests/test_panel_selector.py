import glob
import os

import pytest
import yaml
from runner.cli import REVIEW_MODE_CONFIG, truncate_panel
from runner.panel_selector import (
    DISTANCE_AXES,
    LEVEL,
    PACK_DISSENTERS,
    compute_behavioral_distance,
    detect_pack,
    ensure_diversity,
    load_personas,
    load_presets,
    select_panel,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONA_DIR = os.path.join(REPO_ROOT, "src", "personas")
PRESETS_PATH = os.path.join(REPO_ROOT, "src", "presets", "panel-presets.yaml")

PACK_PATHS = sorted(glob.glob(os.path.join(PERSONA_DIR, "*.yaml")))
PACK_NAMES = [os.path.splitext(os.path.basename(p))[0] for p in PACK_PATHS]

REAL_PRESETS = load_presets(PRESETS_PATH)
REAL_TASK_TYPES = sorted(REAL_PRESETS)


_PACK_CACHE = {}


def _real_pack(pack_name):
    """真实人格包，读一次缓存住——下面的参数化测试有上百个组合，
    每次都重新解析 yaml 会让这个文件跑将近一分钟。选人逻辑不修改人格字典，缓存是安全的。
    """
    if pack_name not in _PACK_CACHE:
        _PACK_CACHE[pack_name] = load_personas(os.path.join(PERSONA_DIR, pack_name + ".yaml"))
    return _PACK_CACHE[pack_name]

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
        """11 条轴共用一张五档量表，全部拉满 = 归一化距离 1.0。"""
        p_low = {
            "id": "X-low",
            "behavior_profile": {axis: "很低" for axis in DISTANCE_AXES},
        }
        p_high = {
            "id": "X-high",
            "behavior_profile": {axis: "很高" for axis in DISTANCE_AXES},
        }
        dist = compute_behavioral_distance(p_low, p_high)
        assert dist == 1.0

    def test_schema_legal_extremes_below_one(self):
        """persona-schema 不允许 risk_tolerance=很高、platform_loyalty=很高 等取值，
        所以真实人格能达到的最大距离小于 1.0——这是量表本身的性质，不是 bug。
        """
        p_low = {
            "id": "X-low",
            "behavior_profile": {
                "patience": "很低",
                "genre_literacy": "很低",
                "novelty_seeking": "很低",
                "risk_tolerance": "低",
                "social_influence": "低",
                "completion_drive": "很低",
                "price_sensitivity": "低",
                "emotional_engagement": "低",
                "agency_preference": "低",
                "tolerance_for_ambiguity": "很低",
                "platform_loyalty": "很低",
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
                "emotional_engagement": "很高",
                "agency_preference": "很高",
                "tolerance_for_ambiguity": "很高",
                "platform_loyalty": "高",
            },
        }
        dist = compute_behavioral_distance(p_low, p_high)
        assert 0.7 < dist < 1.0

    def test_missing_axis_is_skipped_not_crash(self):
        """缺轴的人格不会让距离计算崩，也不会因为"缺"而被算成差异巨大。"""
        full = MINI_PERSONAS[0]
        partial = {"id": "X-partial", "behavior_profile": {"patience": "高"}}
        dist = compute_behavioral_distance(full, partial)
        assert dist == 0.0  # patience 两边都是"高"，唯一可比的轴完全一致

    def test_unknown_axis_value_does_not_crash(self):
        weird = {
            "id": "X-weird",
            "behavior_profile": dict(MINI_PERSONAS[0]["behavior_profile"], patience="爆表"),
        }
        dist = compute_behavioral_distance(MINI_PERSONAS[0], weird)
        assert 0.0 <= dist <= 1.0

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


# ---------------------------------------------------------------------------
# 下面几组用**真实的 src/personas/*.yaml + src/presets/panel-presets.yaml** 跑，
# 而不是 MINI_ 假数据。原因：这次要修的三个缺陷（半数人格永远选不出来、
# localization 面板里没人懂本地化、ensure_diversity 一碰真实取值就 KeyError）
# 全都只在真实数据上才暴露 —— MINI_PERSONAS 那 25 个测试全绿的同时，
# 生产环境有 4 个人格包在全部 14 种任务下都选出 0 个人。
# ---------------------------------------------------------------------------


class TestEveryPersonaIsReachable:
    """每个包的每个人格，至少存在一个 (task_type, mode) 组合能把它选出来。

    修复前实测：accessibility / mobile-f2p / vr-immersive / educational-serious
    四个包 22 个人格在任何组合下都选不出来，family-casual 差 4 个、
    competitive-esport 差 3 个、startup-panel 差 2 个（含写得最好的 P56/P60）。
    """

    @pytest.mark.parametrize("pack", PACK_NAMES)
    def test_all_personas_selectable_in_some_combo(self, pack):
        personas = _real_pack(pack)
        reachable = set()
        for task_type in REAL_TASK_TYPES:
            panel = select_panel(task_type, personas, REAL_PRESETS)["selected"]
            for cfg in REVIEW_MODE_CONFIG.values():
                for p in truncate_panel(panel, cfg["max_personas"]):
                    reachable.add(p["id"])
        unreachable = [p["id"] for p in personas if p["id"] not in reachable]
        assert unreachable == [], u"%s 里这些人格永远选不出来：%s" % (pack, unreachable)

    @pytest.mark.parametrize("pack", PACK_NAMES)
    @pytest.mark.parametrize("task_type", REAL_TASK_TYPES)
    def test_panel_never_degenerate(self, pack, task_type):
        """任何 (包, 任务) 组合都不许选出 0-2 人的面板。

        0 人在生产里等于 AllPersonasFailedError（整场评审直接失败），
        1-2 人等于"多人格评审"名不副实。
        """
        result = select_panel(task_type, _real_pack(pack), REAL_PRESETS)
        assert len(result["selected"]) >= 3, u"%s/%s 只选出 %d 人：%s" % (
            pack, task_type, len(result["selected"]),
            [p["id"] for p in result["selected"]],
        )

    @pytest.mark.parametrize("pack", PACK_NAMES)
    @pytest.mark.parametrize("task_type", REAL_TASK_TYPES)
    def test_no_duplicate_personas(self, pack, task_type):
        ids = [p["id"] for p in select_panel(task_type, _real_pack(pack), REAL_PRESETS)["selected"]]
        assert len(ids) == len(set(ids))


class TestPitchReviewDoesNotDegrade:
    """pitch_review 用默认人格包（game-core）时曾经退化成"只有 P15 一个人"：
    预设点名的 P54-P61 全在 startup-panel 包里，game-core 一个都没有。
    """

    def test_pitch_review_on_default_pack(self):
        result = select_panel("pitch_review", _real_pack("game-core"), REAL_PRESETS)
        ids = [p["id"] for p in result["selected"]]
        assert len(ids) >= 4, ids
        # P13 发行商星探是 game-core 里唯一本职就在评估待签项目的人
        assert any(pid.startswith("P13") for pid in ids), ids

    def test_pitch_review_on_startup_pack_covers_curated_personas(self):
        """P56 行业分析师 / P60 单位经济怀疑者原先只写在 optional_personas 里，
        而那个字段从来没被读过 —— 两个人格因此永远不可达。
        """
        personas = _real_pack("startup-panel")
        reachable = set()
        for task_type in REAL_TASK_TYPES:
            for p in select_panel(task_type, personas, REAL_PRESETS)["selected"]:
                reachable.add(p["id"])
        assert "P56-industry-analyst" in reachable
        assert "P60-unit-economics-skeptic" in reachable


class TestLocalizationPanelKnowsLocalization:
    """localization_review 的默认面板里原先没有一个人懂本地化：
    选出的五人 must_comment_on 全是"独特性/核心循环/视觉辨识度/20秒转化/信任风险"。
    """

    LOC_AFFINITY_FLOOR = 0.7

    @pytest.mark.parametrize("pack", PACK_NAMES)
    def test_panel_includes_localization_capable_persona(self, pack):
        personas = _real_pack(pack)
        capable = set(
            p["id"] for p in personas
            if (p.get("task_affinity") or {}).get("localization_review", 0)
            >= self.LOC_AFFINITY_FLOOR
        )
        if not capable:
            pytest.skip(u"%s 包里没有本地化亲和度 >= %s 的人格" % (pack, self.LOC_AFFINITY_FLOOR))
        panel = set(
            p["id"] for p in select_panel("localization_review", personas, REAL_PRESETS)["selected"]
        )
        assert capable & panel, u"%s 的本地化面板里没有任何懂本地化的人；候选 %s，实际选出 %s" % (
            pack, sorted(capable), sorted(panel)
        )

    def test_default_pack_has_localization_persona(self):
        """默认包（game-core）是绝大多数用户实际跑到的那条路径。"""
        panel = select_panel("localization_review", _real_pack("game-core"), REAL_PRESETS)
        ids = [p["id"] for p in panel["selected"]]
        assert "P67-localization-dependent-player" in ids, ids


class TestDissenterGuaranteeAcrossPacks:
    """"保证面板里有反对者"这条承诺此前只对 game-core 成立：
    代码只会去找 P15，别的九个包一个都找不到。
    """

    @pytest.mark.parametrize("pack", PACK_NAMES)
    @pytest.mark.parametrize("task_type", REAL_TASK_TYPES)
    def test_dissenter_present_and_first(self, pack, task_type):
        result = select_panel(task_type, _real_pack(pack), REAL_PRESETS)
        assert result["dissenter_id"] is not None, u"%s/%s 面板里没有唱反调的人" % (pack, task_type)
        # 排在队首才能在 cli.truncate_panel 按档位从头截断时活下来
        assert result["selected"][0]["id"] == result["dissenter_id"]

    @pytest.mark.parametrize("pack", PACK_NAMES)
    def test_pack_has_dissenter_registry_entry(self, pack):
        assert pack in PACK_DISSENTERS, u"新增人格包 %s 必须在 PACK_DISSENTERS 里指定唱反调的人格" % pack

    @pytest.mark.parametrize("pack", PACK_NAMES)
    def test_registered_dissenter_ids_exist(self, pack):
        """写错一个 id 不会报错，只会静默地让"保证有反对者"失效——所以必须卡死。"""
        ids = set(p["id"] for p in _real_pack(pack))
        for ref in PACK_DISSENTERS[pack]:
            assert ref in ids, u"PACK_DISSENTERS['%s'] 里的 %s 不在该包内" % (pack, ref)

    @pytest.mark.parametrize("pack", PACK_NAMES)
    @pytest.mark.parametrize("mode", sorted(REVIEW_MODE_CONFIG))
    def test_dissenter_survives_mode_truncation(self, pack, mode):
        personas = _real_pack(pack)
        for task_type in REAL_TASK_TYPES:
            result = select_panel(task_type, personas, REAL_PRESETS)
            kept = truncate_panel(result["selected"], REVIEW_MODE_CONFIG[mode]["max_personas"])
            assert result["dissenter_id"] in [p["id"] for p in kept], (
                u"%s/%s/%s 截断后唱反调的人被切掉了" % (pack, task_type, mode)
            )


class TestPresetsIntegrity:
    def test_by_pack_refs_resolve(self):
        """by_pack 里写错的 id 不会报错，只会悄悄退回亲和度兜底——必须卡死。"""
        packs = dict((name, _real_pack(name)) for name in PACK_NAMES)
        problems = []
        for task_type, preset in REAL_PRESETS.items():
            for pack, refs in (preset.get("by_pack") or {}).items():
                assert pack in packs, u"%s.by_pack 指向不存在的人格包 %s" % (task_type, pack)
                ids = set(p["id"] for p in packs[pack])
                for ref in refs:
                    if ref not in ids and not any(i.startswith(ref + "-") for i in ids):
                        problems.append("%s.by_pack.%s: %s" % (task_type, pack, ref))
        assert problems == [], problems

    def test_pack_preset_is_actually_used(self):
        """写了 by_pack 就必须真的走 pack_preset 分支，否则等于白写。"""
        for task_type, preset in REAL_PRESETS.items():
            for pack in (preset.get("by_pack") or {}):
                result = select_panel(task_type, _real_pack(pack), REAL_PRESETS)
                assert result["selection_method"] == "pack_preset", (
                    u"%s/%s 写了 by_pack 却没走 pack_preset：%s"
                    % (task_type, pack, result["selection_method"])
                )

    def test_selection_method_is_honest(self):
        """预设名单在当前包里一个都没命中时，必须标成 affinity_fallback 而不是 preset。"""
        result = select_panel("product_feedback_review", _real_pack("vr-immersive"), REAL_PRESETS)
        assert result["selection_method"] == "affinity_fallback"
        assert result["pack"] == "vr-immersive"

    def test_max_panel_size_enforced(self):
        for task_type, preset in REAL_PRESETS.items():
            cap = preset.get("max_panel_size")
            if not cap:
                continue
            for pack in PACK_NAMES:
                selected = select_panel(task_type, _real_pack(pack), REAL_PRESETS)["selected"]
                assert len(selected) <= cap, u"%s/%s 超过 max_panel_size=%s" % (pack, task_type, cap)

    def test_optional_personas_are_read(self):
        """optional_personas 此前是典型假旋钮：写在 yaml 里，运行时一次都没读过。"""
        presets = {
            "tiny_task": {
                "default_personas": ["P06"],
                "optional_personas": ["P14"],
                "min_panel_size": 2,
            }
        }
        ids = [p["id"] for p in select_panel("tiny_task", MINI_PERSONAS, presets)["selected"]]
        assert "P14-test-fourteen" in ids, ids


class TestEnsureDiversityOnRealData:
    """ensure_diversity 原先是死代码，而且一旦被调用就会崩：
    AXIS_MAP 里 risk_tolerance / platform_loyalty 只有 {低,中,高} 三档，
    可 16 个人格的 20 个取值是「很高」或「很低」→ KeyError。
    """

    @pytest.mark.parametrize("pack", PACK_NAMES)
    def test_no_keyerror_on_real_personas(self, pack):
        pairs = ensure_diversity(_real_pack(pack))  # 修复前这里直接 KeyError('很低')
        assert isinstance(pairs, list)

    def test_packs_actually_contain_extreme_values(self):
        """守住上一个测试的前提：真实数据里确实存在「很高/很低」。
        哪天数据被改成只剩三档，上面那个测试就形同虚设，这里会先失败提醒。
        """
        extremes = 0
        for pack in PACK_NAMES:
            for p in _real_pack(pack):
                for axis in DISTANCE_AXES:
                    if p["behavior_profile"].get(axis) in (u"很高", u"很低"):
                        extremes += 1
        assert extremes >= 20, extremes

    @pytest.mark.parametrize("pack", PACK_NAMES)
    @pytest.mark.parametrize("task_type", REAL_TASK_TYPES)
    def test_select_panel_reports_diversity(self, pack, task_type):
        result = select_panel(task_type, _real_pack(pack), REAL_PRESETS)
        assert isinstance(result["diversity_warnings"], list)
        for pair in result["diversity_warnings"]:
            assert set(["persona_1", "persona_2", "distance"]) <= set(pair)

    def test_diversity_is_used_as_tiebreak(self):
        """亲和度同档时挑与已选面板行为差异更大的那个——这是这套距离度量
        在生产选人路径上真正起作用的地方（不是只报个数字）。
        """
        base = dict(MINI_PERSONAS[0])
        clone = dict(MINI_PERSONAS[0])
        clone["id"] = "P90-clone"
        distinct = dict(MINI_PERSONAS[3])
        distinct["id"] = "P91-distinct"
        pool = []
        for p in (base, clone, distinct):
            q = dict(p)
            q["task_affinity"] = {"solo_task": 0.8}
            q.pop("evidence_types_needed", None)
            pool.append(q)
        presets = {"solo_task": {"default_personas": ["P01"], "min_panel_size": 2}}
        ids = [p["id"] for p in select_panel("solo_task", pool, presets)["selected"]]
        assert "P91-distinct" in ids and "P90-clone" not in ids, ids


class TestPackDetection:
    def test_load_personas_stamps_pack(self):
        personas = _real_pack("mobile-f2p")
        assert all(p["_pack"] == "mobile-f2p" for p in personas)
        assert detect_pack(personas) == "mobile-f2p"

    def test_detect_pack_none_for_handmade_list(self):
        assert detect_pack(MINI_PERSONAS) is None

    def test_pack_argument_overrides_detection(self):
        result = select_panel(
            "localization_review", _real_pack("game-core"), REAL_PRESETS, pack="game-core"
        )
        assert result["pack"] == "game-core"

    def test_internal_pack_field_not_in_persona_prompt(self):
        """_pack 是内部字段，绝不能漏进发给模型的身份卡。"""
        from runner.persona_agent import _minify_persona

        card = _minify_persona(_real_pack("game-core")[0])
        assert "_pack" not in card
