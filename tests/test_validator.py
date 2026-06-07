import os
import pytest
from runner.validator import (
    load_schema,
    validate_schema,
    validate_role_consistency,
    validate_evidence_grounding,
    validate_output,
    check_identity_behavior_decoupling,
)

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "schemas")
OUTPUT_SCHEMA_PATH = os.path.join(SCHEMA_DIR, "output-schema.json")


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
