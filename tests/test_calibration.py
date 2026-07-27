import os
import pytest

from runner.calibration import (
    compute_role_consistency_rate,
    compute_coverage_score,
    compute_hallucination_rate,
    compute_rerun_stability,
    run_calibration_check,
)


def _make_persona(
    persona_id="p1",
    persona_name="Tester",
    primary_stance="positive",
    key_issues=None,
    evidence=None,
    must_comment_on_check=None,
    missing_information=None,
):
    return {
        "persona_id": persona_id,
        "persona_name": persona_name,
        "persona_version": "0.1.0",
        "task_type": "demo_first_play",
        "primary_stance": primary_stance,
        "confidence": 0.8,
        "evidence_sufficiency": 0.7,
        "evidence": evidence if evidence is not None else [
            {"content": "UI is clear", "inference_level": "direct"},
        ],
        "scores": {
            "base": {"clarity": 4, "trust": 3},
            "task_specific": {"fun": 4},
        },
        "key_issues": key_issues if key_issues is not None else [],
        "continue_triggers": ["good gameplay"],
        "quit_triggers": ["bugs"],
        "first_scan_observations": ["looks nice"],
        "must_comment_on_check": must_comment_on_check if must_comment_on_check is not None else {"gameplay": True, "visuals": True},
        "missing_information": missing_information if missing_information is not None else [],
        "voice_sample": "Looks good.",
        "meta": {"caveats": ["synthetic"], "is_synthetic": True},
    }


class TestComputeRoleConsistencyRate:
    def test_full_consistency(self):
        personas = [
            _make_persona("p1", must_comment_on_check={"a": True, "b": True, "c": True}),
            _make_persona("p2", must_comment_on_check={"a": True, "b": True, "c": True}),
        ]
        result = compute_role_consistency_rate(personas)
        assert result["per_persona"]["p1"] == 1.0
        assert result["per_persona"]["p2"] == 1.0
        assert result["average"] == 1.0
        assert result["below_threshold"] == []

    def test_partial_consistency(self):
        personas = [
            _make_persona("p1", must_comment_on_check={"a": True, "b": False, "c": True}),
            _make_persona("p2", must_comment_on_check={"a": True, "b": True, "c": False}),
        ]
        result = compute_role_consistency_rate(personas)
        assert result["per_persona"]["p1"] == pytest.approx(2 / 3)
        assert result["per_persona"]["p2"] == pytest.approx(2 / 3)
        assert result["average"] == pytest.approx(2 / 3)

    def test_below_threshold(self):
        personas = [
            _make_persona("p1", must_comment_on_check={"a": True, "b": True, "c": True}),
            _make_persona("p2", must_comment_on_check={"a": False, "b": False, "c": False}),
        ]
        result = compute_role_consistency_rate(personas)
        assert "p2" in result["below_threshold"]
        assert "p1" not in result["below_threshold"]

    def test_empty_check(self):
        personas = [
            _make_persona("p1", must_comment_on_check={}),
        ]
        result = compute_role_consistency_rate(personas)
        assert result["per_persona"]["p1"] == 0.0

    def test_empty_personas(self):
        result = compute_role_consistency_rate([])
        assert result["per_persona"] == {}
        assert result["average"] == 0.0
        assert result["below_threshold"] == []


class TestComputeCoverageScore:
    def test_identical_coverage(self):
        personas = [
            _make_persona("p1", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = compute_coverage_score(personas)
        assert result["average_distance"] == 0.0
        assert result["min_distance"] == 0.0

    def test_completely_different_coverage(self):
        personas = [
            _make_persona("p1", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", key_issues=[
                {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = compute_coverage_score(personas)
        assert result["average_distance"] == 1.0

    def test_partial_overlap(self):
        personas = [
            _make_persona("p1", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug C", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = compute_coverage_score(personas)
        assert result["average_distance"] == pytest.approx(2 / 3)

    def test_pairwise_distances_keys(self):
        personas = [
            _make_persona("p1", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", key_issues=[
                {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = compute_coverage_score(personas)
        key = ("p1", "p2")
        assert key in result["pairwise_distances"]

    def test_single_persona(self):
        personas = [
            _make_persona("p1", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = compute_coverage_score(personas)
        assert result["average_distance"] == 0.0

    def test_too_similar_flag(self):
        personas = [
            _make_persona("p1", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = compute_coverage_score(personas)
        assert result["average_distance"] < 0.3


class TestComputeHallucinationRate:
    def test_no_hallucination(self):
        artifact_texts = ["The UI is clear and responsive."]
        personas = [
            _make_persona("p1", evidence=[
                {"content": "UI is clear", "inference_level": "direct"},
            ]),
        ]
        result = compute_hallucination_rate(personas, artifact_texts)
        assert result["per_persona"]["p1"] == 0.0
        assert result["average"] == 0.0
        assert result["high_risk_personas"] == []

    def test_full_hallucination(self):
        artifact_texts = ["The game runs at 60fps."]
        personas = [
            _make_persona("p1", evidence=[
                {"content": "The game crashes every 5 minutes", "inference_level": "direct"},
            ]),
        ]
        result = compute_hallucination_rate(personas, artifact_texts)
        assert result["per_persona"]["p1"] == 1.0
        assert "p1" in result["high_risk_personas"]

    def test_mixed_evidence(self):
        artifact_texts = ["The UI is clear and responsive."]
        personas = [
            _make_persona("p1", evidence=[
                {"content": "UI is clear", "inference_level": "direct"},
                {"content": "Game crashes often", "inference_level": "direct"},
            ]),
        ]
        result = compute_hallucination_rate(personas, artifact_texts)
        assert result["per_persona"]["p1"] == 0.5

    def test_inferred_evidence_ignored(self):
        artifact_texts = ["Game runs at 60fps on average."]
        personas = [
            _make_persona("p1", evidence=[
                {"content": "Players might enjoy the combat", "inference_level": "inferred"},
                {"content": "Game runs at 60fps", "inference_level": "direct"},
            ]),
        ]
        result = compute_hallucination_rate(personas, artifact_texts)
        assert result["per_persona"]["p1"] == 0.0

    def test_no_direct_evidence(self):
        artifact_texts = ["Some text."]
        personas = [
            _make_persona("p1", evidence=[
                {"content": "Players feel engaged", "inference_level": "inferred"},
            ]),
        ]
        result = compute_hallucination_rate(personas, artifact_texts)
        assert result["per_persona"]["p1"] == 0.0

    def test_empty_artifact_texts(self):
        artifact_texts = []
        personas = [
            _make_persona("p1", evidence=[
                {"content": "UI is clear", "inference_level": "direct"},
            ]),
        ]
        result = compute_hallucination_rate(personas, artifact_texts)
        assert result["per_persona"]["p1"] == 1.0


class TestComputeRerunStability:
    def test_full_stability(self):
        run1 = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        run2 = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        result = compute_rerun_stability(run1, run2)
        assert result["stance_agreement_rate"] == 1.0
        assert result["disagreed_personas"] == []
        assert result["stable"] is True

    def test_no_stability(self):
        run1 = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        run2 = [
            _make_persona("p1", primary_stance="negative"),
            _make_persona("p2", primary_stance="positive"),
        ]
        result = compute_rerun_stability(run1, run2)
        assert result["stance_agreement_rate"] == 0.0
        assert "p1" in result["disagreed_personas"]
        assert "p2" in result["disagreed_personas"]
        assert result["stable"] is False

    def test_partial_stability(self):
        run1 = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
            _make_persona("p3", primary_stance="neutral"),
            _make_persona("p4", primary_stance="positive"),
            _make_persona("p5", primary_stance="negative"),
        ]
        run2 = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
            _make_persona("p3", primary_stance="positive"),
            _make_persona("p4", primary_stance="positive"),
            _make_persona("p5", primary_stance="neutral"),
        ]
        result = compute_rerun_stability(run1, run2)
        assert result["stance_agreement_rate"] == pytest.approx(0.6)
        assert result["stable"] is False

    def test_boundary_stability(self):
        run1 = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
            _make_persona("p3", primary_stance="neutral"),
            _make_persona("p4", primary_stance="positive"),
            _make_persona("p5", primary_stance="negative"),
        ]
        run2 = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
            _make_persona("p3", primary_stance="neutral"),
            _make_persona("p4", primary_stance="positive"),
            _make_persona("p5", primary_stance="negative"),
        ]
        result = compute_rerun_stability(run1, run2)
        assert result["stance_agreement_rate"] == 1.0
        assert result["stable"] is True


class TestRunCalibrationCheck:
    def test_basic_calibration(self):
        personas = [
            _make_persona("p1", must_comment_on_check={"a": True, "b": True}, key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", must_comment_on_check={"a": True, "b": True}, key_issues=[
                {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = run_calibration_check(personas)
        assert "role_consistency" in result
        assert "coverage" in result
        assert "hallucination" in result
        assert "stability" in result
        assert "overall_pass" in result

    def test_overall_pass(self):
        personas = [
            _make_persona("p1", must_comment_on_check={"a": True, "b": True, "c": True, "d": True, "e": True}, key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug X", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", must_comment_on_check={"a": True, "b": True, "c": True, "d": True, "e": True}, key_issues=[
                {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug Y", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = run_calibration_check(personas)
        assert result["overall_pass"] is True

    def test_overall_fail_low_consistency(self):
        personas = [
            _make_persona("p1", must_comment_on_check={"a": False, "b": False, "c": False, "d": False, "e": False}, key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", must_comment_on_check={"a": False, "b": False, "c": False, "d": False, "e": False}, key_issues=[
                {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = run_calibration_check(personas)
        assert result["overall_pass"] is False

    def test_overall_fail_too_similar(self):
        personas = [
            _make_persona("p1", must_comment_on_check={"a": True, "b": True, "c": True, "d": True, "e": True}, key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", must_comment_on_check={"a": True, "b": True, "c": True, "d": True, "e": True}, key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                {"severity": "medium", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = run_calibration_check(personas)
        assert result["overall_pass"] is False


class TestOffSchemaInputDoesNotCrash:
    """形状归一化的正主是 persona_agent.normalize_persona_output，但直接调 calibration
    的路径（老数据回放、外部集成、单测）没过那道边界，本模块自己也要顶住：
    历史实现里 issue["title"] / e["content"] / p["persona_id"] 都是硬下标，
    第三方模型吐的字符串形态能让整轮校准直接抛异常。"""

    def test_string_key_issues_do_not_crash_coverage(self):
        # calibration.py 旧 :33 —— issue["title"] 对字符串是 TypeError
        p1 = _make_persona("p1", key_issues="无重大问题")
        p2 = _make_persona("p2", key_issues=["纯字符串问题", {"title": "Bug A"}])
        result = compute_coverage_score([p1, p2])
        # 字符串形态没有可比的 title，不参与集合距离，但不能崩
        assert result["pairwise_distances"][("p1", "p2")] == 1.0

    def test_string_evidence_do_not_crash_hallucination(self):
        # calibration.py 旧 :73/:80 —— e.get(...) / e["content"] 对字符串是 AttributeError
        p = _make_persona("p1", evidence=["文案不清晰"])
        result = compute_hallucination_rate([p], ["页面原文"])
        assert result["per_persona"]["p1"] == 0.0

    def test_missing_persona_id_falls_back_instead_of_keyerror(self):
        # calibration.py 旧 :14/:74/:88/:101 —— p["persona_id"] 硬下标
        p1 = {"primary_stance": "观望", "must_comment_on_check": {"a": True}}
        p2 = {"primary_stance": "值得推进", "must_comment_on_check": {"a": False}}
        rate = compute_role_consistency_rate([p1, p2])
        assert len(rate["per_persona"]) == 2  # 占位键不能互相覆盖
        assert compute_hallucination_rate([p1], ["页面原文"])["average"] == 0.0

    def test_missing_stance_does_not_crash_stability(self):
        # calibration.py 旧 :101 —— p["primary_stance"] 硬下标
        run1 = [{"persona_id": "p1"}]
        run2 = [{"persona_id": "p1", "primary_stance": "观望"}]
        result = compute_rerun_stability(run1, run2)
        assert result["disagreed_personas"] == ["p1"]

    def test_non_dict_must_comment_check_does_not_crash(self):
        p = _make_persona("p1", must_comment_on_check=["独特性", "首15分钟"])
        result = compute_role_consistency_rate([p])
        assert result["per_persona"]["p1"] == 0.0

    def test_with_artifact_texts(self):
        artifact_texts = ["The UI is clear."]
        personas = [
            _make_persona("p1", must_comment_on_check={"a": True, "b": True}, key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
            ], evidence=[
                {"content": "UI is clear", "inference_level": "direct"},
            ]),
            _make_persona("p2", must_comment_on_check={"a": True, "b": True}, key_issues=[
                {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ], evidence=[
                {"content": "UI is clear", "inference_level": "direct"},
            ]),
        ]
        result = run_calibration_check(personas, artifact_texts=artifact_texts)
        assert result["hallucination"] is not None
        assert result["hallucination"]["average"] == 0.0

    def test_with_previous_outputs(self):
        previous = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        personas = [
            _make_persona("p1", primary_stance="positive", must_comment_on_check={"a": True, "b": True}, key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", primary_stance="negative", must_comment_on_check={"a": True, "b": True}, key_issues=[
                {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = run_calibration_check(personas, previous_outputs=previous)
        assert result["stability"] is not None
        assert result["stability"]["stance_agreement_rate"] == 1.0

    def test_no_artifact_no_previous(self):
        personas = [
            _make_persona("p1", must_comment_on_check={"a": True, "b": True}, key_issues=[
                {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
            _make_persona("p2", must_comment_on_check={"a": True, "b": True}, key_issues=[
                {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
            ]),
        ]
        result = run_calibration_check(personas)
        assert result["hallucination"] is None
        assert result["stability"] is None
