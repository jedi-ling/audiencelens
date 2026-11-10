import json
import os
import re
import sys

import pytest

from runner.persona_agent import (
    TASK_SCORE_DIMENSIONS,
    TASK_STANCE_ENUM,
    render_prompt,
    stance_enum_for,
)
from runner.task_types import VALID_TASK_TYPES
from runner.validator import (
    load_schema,
    validate_schema,
    validate_role_consistency,
    check_entry_grounding,
    load_grounding_config,
    validate_evidence_grounding,
    validate_output,
    check_identity_behavior_decoupling,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "schemas")
OUTPUT_SCHEMA_PATH = os.path.join(SCHEMA_DIR, "output-schema.json")
PERSONA_PROMPT_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "persona-prompt.md")


def _make_valid_output():
    return {
        "persona_id": "P01-test",
        "persona_name": "测试角色",
        "persona_version": "1.0",
        "task_type": "steam_page_review",
        "primary_stance": "positive",
        "confidence": 0.8,
        "evidence_sufficiency": 0.7,
        "evidence": [
            {"content": "画面精美", "inference_level": "direct"},
            {"content": "价格合理", "inference_level": "direct"},
            {"content": "玩法机制丰富", "inference_level": "direct"},
            {"content": "玩法可能有趣", "inference_level": "inferred"},
        ],
        "scores": {
            "base": {"clarity": 4, "trust": 3},
            "task_specific": {"fun": 4},
        },
        "key_issues": [
            {
                "severity": "medium",
                "title": "价格偏高",
                "why_it_matters": "影响购买决策",
                "suggested_fix": "调整定价策略",
            }
        ],
        "continue_triggers": ["好评多"],
        "quit_triggers": ["差评多"],
        "first_scan_observations": ["画面吸引人"],
        "must_comment_on_check": {
            "画面表现": True,
            "玩法机制": True,
            "价格策略": True,
            "社区反馈": True,
            "音效设计": True,
        },
        "missing_information": ["实际玩法体验"],
        "voice_sample": "这游戏画面真不错",
        "meta": {"caveats": ["仅基于页面信息"], "is_synthetic": True},
    }


def _make_persona():
    return {
        "id": "P01-test",
        "name": "测试角色",
        "gender": "男",
        "age_range": "25-35",
        "region": "中国",
        "language": "中文",
        "archetype": "核心玩家",
        "identity_summary": "资深核心玩家",
        "gaming_profile": {
            "experience": "核心",
            "platforms": ["PC"],
            "genres": ["RPG"],
            "session_length": "2-4小时",
        },
        "behavior_profile": {
            "patience": "高",
            "genre_literacy": "很高",
            "novelty_seeking": "中",
            "risk_tolerance": "中",
            "social_influence": "低",
            "completion_drive": "高",
            "price_sensitivity": "中",
            "criticism_style": "分析直给",
            "emotional_engagement": "中",
            "agency_preference": "高",
            "tolerance_for_ambiguity": "中",
            "platform_loyalty": "中",
        },
        "motivations": ["挑战"],
        "likes": ["RPG"],
        "dislikes": ["氪金"],
        "decision_rules": ["看玩法"],
        "quit_triggers": ["氪金严重"],
        "continue_triggers": ["玩法有趣"],
        "first_scan_focus": ["画面"],
        "review_output": {
            "tone": "分析型",
            "strictness": 3,
            "must_comment_on": ["画面表现", "玩法机制", "价格策略", "社区反馈", "音效设计"],
            "avoid": [],
        },
    }


# ---------------------------------------------------------------------------
# "照抄提示词骨架的输出必须能过 schema"——本文件最核心的一条回归
#
# 修复前实跑复现：提示词骨架写 "scores": {"base": {}, "task_specific": {}}，
# 而 schema 要求 scores.base 必须含 clarity 和 trust（且 additionalProperties:false），
# 提示词全文没出现过这两个词。于是一份**字段一字不差照抄骨架**的输出仍然报
#   scores.base: 'clarity' is a required property
#   scores.base: 'trust' is a required property
# 结果：报告评分表恒为空、validation 恒为 fail、任何基于"schema 合格率"的
# 质量门形同虚设。
#
# 下面这组测试不手抄一份"理想输出"（那样只测到测试作者的记忆），而是**从真正
# 渲染出来的提示词里把骨架抠出来**，只把 <...> 占位说明换成合法取值，再送进
# schema。提示词与 schema 任何一方再次跑偏，这里立刻红。
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
# 骨架里的占位说明一律写成 <...>
_PLACEHOLDER_RE = re.compile(r"^<.*>$", re.DOTALL)
# 骨架里用 "a|b|c" 表示"从中选一个"的字段
_CHOICE_DEFAULTS = {"inference_level": "direct", "severity": "medium"}

_SKELETON_PERSONA = {
    "id": "P-skeleton",
    "name": "骨架测试角色",
    "mbti": "INTJ",
    "decision_rules": ["没有可核验证据就不下结论"],
    "review_output": {"must_comment_on": ["必答项甲", "必答项乙"]},
}


def _fill_value(key, value, task_type):
    """单个字符串值的占位替换：字段名不动，只把 <...> 换成该字段的合法取值。"""
    if key in _CHOICE_DEFAULTS and "|" in value:
        return _CHOICE_DEFAULTS[key]
    if key == "primary_stance":
        stances = stance_enum_for(task_type)
        return stances[0] if stances else "观望"
    if _PLACEHOLDER_RE.match(value):
        return f"占位替换：{key} 的具体内容"
    return value


def _output_from_prompt_skeleton(task_type: str) -> dict:
    """渲染提示词 → 抠出 ```json 骨架 → 填占位 → 得到"最听话的模型"会交回的输出。"""
    prompt = render_prompt(
        _SKELETON_PERSONA, task_type, "某评审对象", PERSONA_PROMPT_PATH
    )
    block = _JSON_BLOCK_RE.search(prompt)
    assert block, "提示词里找不到 ```json 骨架块"

    # 骨架本身必须是合法 JSON——它是给模型逐字照抄的样板，自己都解析不了就没救了
    skeleton = json.loads(block.group(1))

    must_items = iter(_SKELETON_PERSONA["review_output"]["must_comment_on"])

    def walk(node, parent_key=None):
        if isinstance(node, dict):
            out = {}
            for key, value in node.items():
                real_key = next(must_items) if _PLACEHOLDER_RE.match(key) else key
                out[real_key] = walk(value, key)
            return out
        if isinstance(node, list):
            return [walk(item, parent_key) for item in node]
        if isinstance(node, str):
            return _fill_value(parent_key, node, task_type)
        return node

    return walk(skeleton)


class TestPromptSkeletonMatchesSchema:
    """提示词骨架 ↔ schema 的一致性。这是"报告评分表永远是空的"的根因所在。"""

    def test_skeleton_block_is_parseable_json(self):
        prompt = render_prompt(
            _SKELETON_PERSONA, "steam_page_review", "某评审对象", PERSONA_PROMPT_PATH
        )
        block = _JSON_BLOCK_RE.search(prompt)
        assert block is not None
        json.loads(block.group(1))

    @pytest.mark.parametrize("task_type", VALID_TASK_TYPES)
    def test_verbatim_skeleton_passes_schema(self, task_type):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _output_from_prompt_skeleton(task_type)
        result = validate_schema(output, schema)
        assert result["valid"] is True, (
            f"{task_type}: 照抄提示词骨架的输出被 schema 拒绝 → {result['errors']}"
        )

    @pytest.mark.parametrize("task_type", VALID_TASK_TYPES)
    def test_skeleton_carries_required_base_scores(self, task_type):
        # 骨架必须把 clarity / trust 明写出来。此前这两个词在提示词全文都不存在，
        # 模型无从知道要输出它们 —— 评分表因此恒为空。
        output = _output_from_prompt_skeleton(task_type)
        assert set(output["scores"]["base"]) == {"clarity", "trust"}
        for value in output["scores"]["base"].values():
            assert isinstance(value, int) and 1 <= value <= 5

    @pytest.mark.parametrize("task_type", VALID_TASK_TYPES)
    def test_skeleton_carries_task_specific_dimensions(self, task_type):
        output = _output_from_prompt_skeleton(task_type)
        assert list(output["scores"]["task_specific"]) == list(
            TASK_SCORE_DIMENSIONS[task_type]
        )

    def test_pitch_review_stance_is_in_enum(self):
        # 创业评审面板此前没有任何立场词表，8 个人格自造 8 种说法，
        # 聚合器拿 primary_stance 当 dict 键做立场聚类 → 共识/分歧统计直接失效
        output = _output_from_prompt_skeleton("pitch_review")
        assert output["primary_stance"] in TASK_STANCE_ENUM["pitch_review"]
        assert TASK_STANCE_ENUM["pitch_review"] == ["值得跟进", "不投", "观望"]

    @pytest.mark.parametrize("task_type", VALID_TASK_TYPES)
    def test_every_task_type_has_stance_words_in_prompt(self, task_type):
        prompt = render_prompt(
            _SKELETON_PERSONA, task_type, "某评审对象", PERSONA_PROMPT_PATH
        )
        for stance in TASK_STANCE_ENUM[task_type]:
            assert stance in prompt, f"{task_type} 的立场词「{stance}」没进提示词"


class TestSchemaTaskTypeEnum:
    """schema 的 task_type 枚举与引擎注册表漂移 → 合法输出被判枚举不符 → 报告没评分。
    persona_agent 导入时已有同样的断言，这里再钉一遍，避免有人把断言删了。"""

    def test_enum_matches_engine_registry(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        assert set(schema["properties"]["task_type"]["enum"]) == set(VALID_TASK_TYPES)

    @pytest.mark.parametrize("task_type", VALID_TASK_TYPES)
    def test_every_registered_task_type_accepted(self, task_type):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        output["task_type"] = task_type
        result = validate_schema(output, schema)
        assert result["valid"] is True, result["errors"]

    def test_previously_missing_four_are_now_accepted(self):
        # 实测挂过的四个：引擎认、schema 不认
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        for task_type in (
            "pitch_review",
            "product_feedback_review",
            "pricing_page_review",
            "onboarding_review",
        ):
            output = _make_valid_output()
            output["task_type"] = task_type
            assert validate_schema(output, schema)["valid"] is True


class TestLoadSchema:
    def test_load_output_schema(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        assert schema["title"] == "Single Persona Review Output Schema"
        assert "properties" in schema

    def test_load_nonexistent_schema(self):
        with pytest.raises(FileNotFoundError):
            load_schema("nonexistent.json")


class TestValidateSchema:
    def test_valid_output(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        result = validate_schema(output, schema)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_invalid_output_missing_required_field(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        del output["persona_id"]
        result = validate_schema(output, schema)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_invalid_output_wrong_type(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        output["confidence"] = "not_a_number"
        result = validate_schema(output, schema)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_invalid_output_wrong_enum(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        output["task_type"] = "invalid_type"
        result = validate_schema(output, schema)
        assert result["valid"] is False
        assert len(result["errors"]) > 0


class TestValidateRoleConsistency:
    def test_full_coverage(self):
        output = _make_valid_output()
        persona = _make_persona()
        result = validate_role_consistency(output, persona)
        assert result["must_comment_on_coverage"] == 1.0
        assert result["consistent"] is True
        assert "角色漂移" not in " ".join(result["issues"])

    def test_80_percent_coverage(self):
        output = _make_valid_output()
        output["must_comment_on_check"] = {
            "画面表现": True,
            "玩法机制": True,
            "价格策略": True,
            "社区反馈": True,
            "音效设计": False,
        }
        persona = _make_persona()
        result = validate_role_consistency(output, persona)
        assert result["must_comment_on_coverage"] == 0.8
        assert result["consistent"] is True

    def test_50_percent_coverage_role_drift(self):
        output = _make_valid_output()
        output["must_comment_on_check"] = {
            "画面表现": True,
            "玩法机制": True,
            "价格策略": False,
            "社区反馈": False,
            "音效设计": False,
        }
        persona = _make_persona()
        result = validate_role_consistency(output, persona)
        assert result["must_comment_on_coverage"] == 0.4
        assert result["consistent"] is False
        assert any("角色漂移" in issue for issue in result["issues"])

    def test_inferred_ratio_ok(self):
        output = _make_valid_output()
        persona = _make_persona()
        result = validate_role_consistency(output, persona)
        assert result["inferred_ratio"] == 0.25
        assert not any("推断过度" in issue for issue in result["issues"])

    def test_inferred_ratio_too_high(self):
        output = _make_valid_output()
        output["evidence"] = [
            {"content": "可能好玩", "inference_level": "inferred"},
            {"content": "也许不错", "inference_level": "inferred"},
            {"content": "大概还行", "inference_level": "inferred"},
            {"content": "画面精美", "inference_level": "direct"},
        ]
        persona = _make_persona()
        result = validate_role_consistency(output, persona)
        assert result["inferred_ratio"] == 0.75
        assert result["consistent"] is False
        assert any("推断过度" in issue for issue in result["issues"])


class TestValidateEvidenceGrounding:
    def test_all_grounded(self):
        output = _make_valid_output()
        artifact_texts = ["游戏画面精美，场景细腻", "玩法机制丰富多样", "定价价格合理公道"]
        result = validate_evidence_grounding(output, artifact_texts)
        assert result["grounded"] is True
        assert result["hallucination_risk"] == 0.0
        assert result["ungrounded_evidence"] == []

    def test_ungrounded_evidence(self):
        output = _make_valid_output()
        artifact_texts = ["完全无关的文本"]
        result = validate_evidence_grounding(output, artifact_texts)
        assert result["grounded"] is False
        assert result["hallucination_risk"] == 1.0
        assert len(result["ungrounded_evidence"]) == 3

    def test_partial_grounding(self):
        output = _make_valid_output()
        output["evidence"] = [
            {"content": "画面精美", "inference_level": "direct"},
            {"content": "玩法可能有趣", "inference_level": "direct"},
        ]
        artifact_texts = ["游戏画面精美"]
        result = validate_evidence_grounding(output, artifact_texts)
        assert result["hallucination_risk"] == 0.5
        assert result["grounded"] is False
        assert len(result["ungrounded_evidence"]) == 1

    def test_no_direct_evidence(self):
        output = _make_valid_output()
        output["evidence"] = [
            {"content": "可能好玩", "inference_level": "inferred"},
        ]
        artifact_texts = ["一些文本"]
        result = validate_evidence_grounding(output, artifact_texts)
        assert result["hallucination_risk"] == 0.0
        assert result["grounded"] is True
        assert result["ungrounded_evidence"] == []

    def test_chinese_quoted_verbatim_evidence_is_grounded(self):
        # 回归：模型用「」/""/+/—— 逐字引用材料词组时，引号曾和词句粘成
        # 永远匹配不上的长 token，诚实引用被误判为幻觉（Balatro 材料实测
        # 4/6 人格被误伤）。引号、加号、破折号都不得妨碍匹配。
        output = _make_valid_output()
        output["evidence"] = [
            {"content": "页面明确宣称视觉风格为「CRT风格的像素艺术」", "inference_level": "direct"},
            {"content": "“扑克之旅”+“策略构建”", "inference_level": "direct"},
            {"content": "短描述写着：“扑克之旅”——“策略构建游戏”", "inference_level": "direct"},
        ]
        artifact_texts = [
            "沉浸于 CRT风格的像素艺术，细节惊人",
            "Balatro是一场循环不息的扑克之旅。策略构建游戏。",
        ]
        result = validate_evidence_grounding(output, artifact_texts)
        assert result["ungrounded_evidence"] == []
        assert result["grounded"] is True

    def test_quote_followed_by_own_commentary_is_not_a_direct_quote(self):
        # 覆盖率规则带来的行为变化（有意为之）：同一条里引用之后再接一段自己的评论，
        # 整条不再算 direct。旧的任意片段规则会因为“扑克之旅”四个字放行整条。
        # 被点名的是没找到的那一段，引用本身不在其中。
        entry = "短描述直接给出核心承诺：“扑克之旅”+“策略构建”——三秒能读到机制核心"
        result = check_entry_grounding(entry, ["Balatro是一场循环不息的扑克之旅。策略构建游戏。"])
        assert result["grounded"] is False
        assert any("三秒能读到机制核心" in u for u in result["uncovered"])
        assert not any("扑克之旅" in u for u in result["uncovered"])

    def test_fabricated_quote_still_fails_after_tokenizer_fix(self):
        # 切词放宽不等于放水：材料里不存在的词组，引号拆开也匹配不上。
        output = _make_valid_output()
        output["evidence"] = [
            {"content": "页面宣称「支持多人联机对战」", "inference_level": "direct"},
        ]
        artifact_texts = ["这是一款单人roguelike卡牌游戏"]
        result = validate_evidence_grounding(output, artifact_texts)
        assert result["grounded"] is False
        assert result["ungrounded_evidence"] == ["页面宣称「支持多人联机对战」"]

    # ---- 覆盖率规则（外部评审指出任意片段规则的两个洞之后） ----

    def test_probe_true_quote_plus_fabricated_addition_fails(self):
        # 探针 a：旧规则下"售价68元"一个片段命中就整条通过。
        material = ["深渊回响是一款卡牌肉鸽游戏，售价68元，首发支持简体中文。"]
        entry = "售价68元，并且官方承诺永久免费更新全部DLC"
        output = {"evidence": [{"inference_level": "direct", "content": entry}]}
        result = validate_evidence_grounding(output, material)
        assert result["ungrounded_evidence"] == [entry]
        detail = result["ungrounded_details"][0]
        assert any("官方承诺永久免费更新" in u for u in detail["uncovered"])
        assert not any("售价68元" in u for u in detail["uncovered"])

    def test_probe_english_entry_sharing_only_common_words_fails(self):
        # 探针 b：旧规则按空白切词，"the" / "is" 任何一个词命中就整条通过。
        material = ["Abyss Echo is a roguelike deck-builder. The price is $14.99 and the demo lasts 40 minutes."]
        entry = "The developers admit the game is unfinished and refunds are refused"
        output = {"evidence": [{"inference_level": "direct", "content": entry}]}
        result = validate_evidence_grounding(output, material)
        assert result["ungrounded_evidence"] == [entry]
        assert result["hallucination_risk"] == 1.0

    def test_normalisation_differences_do_not_break_a_quote(self):
        material = ["预计流程 12-15 小时，支持手柄与键鼠。\nPlanned price: $16.99 — “No combat” and no fail state."]
        for entry in ("预计流程12-15小时,支持手柄与键鼠",          # 空格、半角逗号
                      "预计流程 １２-１５ 小时，支持手柄与键鼠",    # 全角数字
                      "planned price：$16.99",                     # 大小写、全角冒号
                      'Planned price: $16.99 - "No combat" and no fail state'):  # 引号、破折号
            assert check_entry_grounding(entry, material)["grounded"] is True, entry

    def test_one_altered_number_fails_even_when_the_rest_is_verbatim(self):
        material = ["预计下个月开一轮小范围 Discord 内测，名额 50 个，感兴趣的可以在评论区留言"]
        entry = "预计下个月开一轮小范围 Discord 内测，名额 500 个，感兴趣的可以在评论区留言"
        result = check_entry_grounding(entry, material)
        assert result["coverage"] > 0.9
        assert result["uncovered_numbers"] == ["500"]
        assert result["grounded"] is False

    def test_framing_is_dropped_but_what_follows_must_still_be_a_quote(self):
        material = ["Repair and upgrade the lamp, the foghorn and the supply dock in any order"]
        ok = 'The page says "Repair and upgrade the lamp, the foghorn and the supply dock in any order".'
        bad = 'The page says "every repair costs real money and cannot be undone".'
        assert check_entry_grounding(ok, material)["grounded"] is True
        assert check_entry_grounding(bad, material)["grounded"] is False
        # 词内撇号不是引号：不能把 "In the devlog" 当成引导语切掉后半句
        own = "In the devlog's own words: \"Repair and upgrade the lamp, the foghorn and the supply dock in any order\""
        assert check_entry_grounding(own, material)["grounded"] is True

    def test_short_common_spans_do_not_count(self):
        # 单个常见词 / 两三个字的巧合命中不构成覆盖
        assert check_entry_grounding("这个游戏很好玩", ["一款游戏"])["coverage"] == 0.0
        assert check_entry_grounding("It is the best of the genre", ["It is a game. The end of the road."])["coverage"] == 0.0

    def test_match_does_not_run_across_two_materials(self):
        result = check_entry_grounding("黑白水墨风格", ["黑白水", "墨风格"])
        assert result["grounded"] is False

    def test_parameters_come_from_config_not_code(self):
        config = load_grounding_config()
        assert set(config) >= {"min_span_cjk_chars", "min_span_latin_words", "coverage_threshold",
                               "require_numbers_covered", "framing"}
        entry, material = "黑白水墨风格的游戏，我觉得不错", ["黑白水墨风格的游戏"]
        strict = dict(config, coverage_threshold=0.95)
        loose = dict(config, coverage_threshold=0.5)
        assert check_entry_grounding(entry, material, strict)["grounded"] is False
        assert check_entry_grounding(entry, material, loose)["grounded"] is True


class TestGroundingEvalSet:
    """tests/fixtures/grounding_eval：集合本身的不变量 + 当前规则在 dev 划分上不得退化。

    只卡 dev。test 划分是留出集，不放进断言里——放进来就等于拿它调参。
    """

    def test_items_file_matches_builder(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures", "grounding_eval"))
        import build_set
        with open(build_set.OUT, encoding="utf-8") as f:
            assert f.read() == build_set.render()

    def test_dev_split_has_no_scored_errors(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
        import eval_grounding
        report = eval_grounding.evaluate(eval_grounding.load_items(), eval_grounding.current_validator, ("dev",))
        overall = report["dev"]["all scored items"]
        assert (overall["fp"], overall["fn"]) == (0, 0), overall

    def test_legacy_rule_baseline_is_reproducible(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
        import eval_grounding
        report = eval_grounding.evaluate(eval_grounding.load_items(), eval_grounding.legacy_any_fragment, ("dev",))
        english = report["dev"]["constructed · en"]
        assert english["false_accept_rate"] == 1.0   # 旧规则：英文未落地条目全部放行


class TestValidateOutput:
    def test_all_pass(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        persona = _make_persona()
        artifact_texts = ["游戏画面精美，场景细腻", "玩法机制丰富多样", "定价价格合理公道"]
        result = validate_output(output, persona, schema, artifact_texts)
        assert result["schema_valid"] is True
        assert result["role_consistent"] is True
        assert result["evidence_grounded"] is True
        assert result["passed"] is True

    def test_schema_fails(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        del output["persona_id"]
        persona = _make_persona()
        result = validate_output(output, persona, schema)
        assert result["schema_valid"] is False
        assert result["passed"] is False

    def test_no_artifact_texts_skips_grounding(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        persona = _make_persona()
        result = validate_output(output, persona, schema)
        assert result["evidence_grounded"] is True
        assert result["passed"] is True

    def test_role_inconsistent_fails(self):
        schema = load_schema(OUTPUT_SCHEMA_PATH)
        output = _make_valid_output()
        output["must_comment_on_check"] = {
            "画面表现": True,
            "玩法机制": False,
            "价格策略": False,
            "社区反馈": False,
            "音效设计": False,
        }
        output["evidence"] = [
            {"content": "可能好玩", "inference_level": "inferred"},
            {"content": "也许不错", "inference_level": "inferred"},
            {"content": "大概还行", "inference_level": "inferred"},
        ]
        persona = _make_persona()
        result = validate_output(output, persona, schema)
        assert result["role_consistent"] is False
        assert result["passed"] is False


class TestCheckIdentityBehaviorDecoupling:
    def test_no_violations(self):
        output = _make_valid_output()
        result = check_identity_behavior_decoupling(output)
        assert result["decoupled"] is True
        assert result["violations"] == []

    def test_violation_in_evidence(self):
        output = _make_valid_output()
        output["evidence"] = [
            {"content": "作为男性所以更喜欢动作游戏", "inference_level": "direct"},
        ]
        result = check_identity_behavior_decoupling(output)
        assert result["decoupled"] is False
        assert len(result["violations"]) > 0

    def test_violation_in_key_issues(self):
        output = _make_valid_output()
        output["key_issues"] = [
            {
                "severity": "high",
                "title": "性别偏见",
                "why_it_matters": "作为女性因此更关注社交",
                "suggested_fix": "避免偏见",
            }
        ]
        result = check_identity_behavior_decoupling(output)
        assert result["decoupled"] is False
        assert len(result["violations"]) > 0

    def test_multiple_violations(self):
        output = _make_valid_output()
        output["evidence"] = [
            {"content": "作为男性所以喜欢竞技", "inference_level": "direct"},
        ]
        output["key_issues"] = [
            {
                "severity": "medium",
                "title": "偏好问题",
                "why_it_matters": "她因此不喜欢暴力游戏",
                "suggested_fix": "调整",
            }
        ]
        result = check_identity_behavior_decoupling(output)
        assert result["decoupled"] is False
        assert len(result["violations"]) >= 2


class TestIdentityBehaviorFalsePositives:
    """旧正则 (?:作为[男女女性男性]|她|他).*?(?:所以|因此) 把裸"他"当人称指代，
    会命中「其他」「他们」里的那个字。中文里"其他…所以"密度极高，正常 UX 建议被判
    违规 → aggregator 每条扣 10 分 → 5 条就 ethics_score<50 → compliance"驳回"
    + "全部评审结果需要人工复核"。两个方向都必须测：正常文本放行、真违规仍被抓。"""

    NORMAL_TEXTS = [
        "其他玩家很容易困惑，所以建议加提示",
        "他们看不懂教程，因此会流失",
        "这个功能没有其他入口，所以要改",
        # 「他人」同样是泛指，不是身份刻板推理
        "看不到他人的进度，所以缺少对比动力",
        # 「性」字曾因错写的字符类 [男女女性男性] 单独触发
        "游戏性说明不足，因此第一印象弱",
        # 跨句连结：两件无关的事不该被 .*? 串成一条违规
        "她提到教程不清晰。另外价格偏高，所以建议调整定价",
    ]

    VIOLATION_TEXTS = [
        "作为女性玩家她肯定不喜欢硬核战斗，所以要降低难度",
        "作为男性所以更喜欢动作游戏",
        "她因此不喜欢暴力游戏",
        # 「她们」显式带性别，属于性别泛化，保留为违规
        "她们对数值成长没兴趣，所以要弱化养成线",
    ]

    @pytest.mark.parametrize("text", NORMAL_TEXTS)
    def test_normal_chinese_not_flagged(self, text):
        output = _make_valid_output()
        output["evidence"] = [{"content": text, "inference_level": "direct"}]
        result = check_identity_behavior_decoupling(output)
        assert result["decoupled"] is True, f"误伤正常文本: {result['violations']}"

    @pytest.mark.parametrize("text", VIOLATION_TEXTS)
    def test_real_violation_still_caught(self, text):
        output = _make_valid_output()
        output["evidence"] = [{"content": text, "inference_level": "direct"}]
        result = check_identity_behavior_decoupling(output)
        assert result["decoupled"] is False, f"漏放真违规: {text}"

    def test_five_normal_issues_keep_ethics_clean(self):
        # 这就是实跑复现的场景：5 条正常报告条目，旧正则全中 → 报告被判驳回
        output = _make_valid_output()
        output["evidence"] = [
            {"content": t, "inference_level": "inferred"} for t in self.NORMAL_TEXTS
        ]
        output["key_issues"] = [
            {"severity": "medium", "title": "提示缺失",
             "why_it_matters": "其他玩家很容易困惑，所以建议加提示",
             "suggested_fix": "在首屏加一行说明，因此其他入口也要同步"}
        ]
        result = check_identity_behavior_decoupling(output)
        assert result["violations"] == []

    def test_offschema_shapes_do_not_crash(self):
        # 字符串形态的 evidence/key_issues（第三方模型实测）不能让伦理检查崩
        result = check_identity_behavior_decoupling(
            {"evidence": ["文案不清晰"], "key_issues": "无重大问题"}
        )
        assert result["decoupled"] is True

    def test_violation_inside_string_shaped_issue_still_caught(self):
        # 兜底分支不能变成违规文本的逃生通道
        result = check_identity_behavior_decoupling(
            {"key_issues": ["作为女性她不玩这类游戏，所以不用管这块"]}
        )
        assert result["decoupled"] is False

    def test_violation_in_whole_string_key_issues_still_caught(self):
        # key_issues 整体被吐成一句话时，旧写法会 for 出单个字符、一条都查不出来
        result = check_identity_behavior_decoupling(
            {"key_issues": "作为女性她不玩这类游戏，所以不用管这块"}
        )
        assert result["decoupled"] is False

    def test_violation_in_mapping_shaped_key_issues_still_caught(self):
        # {维度: 描述} 形态：描述里的违规必须查出来
        result = check_identity_behavior_decoupling(
            {"key_issues": {"目标人群": "作为女性玩家她不感兴趣，所以砍掉"}}
        )
        assert result["decoupled"] is False

    def test_violation_in_inference_basis_caught(self):
        # inference_basis 恰恰是刻板推理最爱藏的字段，旧实现只看 content
        result = check_identity_behavior_decoupling({
            "evidence": [{
                "content": "教程冗长",
                "inference_level": "inferred",
                "inference_basis": "她是女性所以耐心低",
            }]
        })
        assert result["decoupled"] is False

    def test_normalizer_backfilled_basis_is_not_a_violation(self):
        # 归一化会给缺层级的 evidence 补一条 inference_basis 说明；伦理检查现在也扫
        # 这个字段，所以那句说明本身绝不能命中正则，否则每个 off-schema 输出都被判违规
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"evidence": ["文案不清晰", "价格没写"]})
        assert check_identity_behavior_decoupling(out)["violations"] == []
