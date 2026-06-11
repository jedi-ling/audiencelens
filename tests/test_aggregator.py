import os
import pytest
from datetime import datetime

from runner.aggregator import (
    load_aggregation_rules,
    compute_consensus,
    compute_disagreements,
    compute_priority_fixes,
    aggregate_report,
    render_markdown_report,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RULES_PATH = os.path.join(PROJECT_ROOT, "src", "config", "aggregation-rules.yaml")
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "schemas", "report-schema.json")
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.md")


def _make_persona(
    persona_id="p1",
    persona_name="Tester",
    primary_stance="positive",
    confidence=0.8,
    evidence_sufficiency=0.7,
    key_issues=None,
    evidence=None,
    missing_information=None,
    must_comment_on_check=None,
    continue_triggers=None,
    quit_triggers=None,
    voice_sample="Looks good to me.",
):
    return {
        "persona_id": persona_id,
        "persona_name": persona_name,
        "persona_version": "0.1.0",
        "task_type": "demo_first_play",
        "primary_stance": primary_stance,
        "confidence": confidence,
        "evidence_sufficiency": evidence_sufficiency,
        "evidence": evidence if evidence is not None else [
            {"content": "UI is clear", "inference_level": "direct"},
        ],
        "scores": {
            "base": {"clarity": 4, "trust": 3},
            "task_specific": {"fun": 4},
        },
        "key_issues": key_issues if key_issues is not None else [],
        "continue_triggers": continue_triggers if continue_triggers is not None else ["good gameplay"],
        "quit_triggers": quit_triggers if quit_triggers is not None else ["bugs"],
        "first_scan_observations": ["looks nice"],
        "must_comment_on_check": must_comment_on_check if must_comment_on_check is not None else {"gameplay": True, "visuals": True},
        "missing_information": missing_information if missing_information is not None else [],
        "voice_sample": voice_sample,
        "meta": {"caveats": ["synthetic"], "is_synthetic": True},
    }


class TestLoadAggregationRules:
    def test_loads_yaml_successfully(self):
        rules = load_aggregation_rules(RULES_PATH)
        assert "severity_boost" in rules
        assert "consensus_threshold" in rules

    def test_severity_boost_values(self):
        rules = load_aggregation_rules(RULES_PATH)
        assert rules["severity_boost"]["critical"] == 2.0
        assert rules["severity_boost"]["high"] == 1.5
        assert rules["severity_boost"]["medium"] == 1.0
        assert rules["severity_boost"]["low"] == 0.5

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_aggregation_rules("/nonexistent/path.yaml")


class TestComputeConsensus:
    def test_full_consensus(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
            _make_persona("p3", primary_stance="positive"),
        ]
        result = compute_consensus(personas, threshold=0.7)
        assert "positive" in result["stance_distribution"]
        assert result["stance_distribution"]["positive"] == 3
        assert len(result["agreed_points"]) > 0

    def test_partial_consensus(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
            _make_persona("p3", primary_stance="positive"),
            _make_persona("p4", primary_stance="negative"),
        ]
        result = compute_consensus(personas, threshold=0.7)
        assert result["stance_distribution"]["positive"] == 3
        assert result["stance_distribution"]["negative"] == 1
        assert "positive" in result["agreed_points"]
        assert "negative" in result["questioned_points"]

    def test_complete_disagreement(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
            _make_persona("p3", primary_stance="neutral"),
        ]
        result = compute_consensus(personas, threshold=0.7)
        assert len(result["agreed_points"]) == 0
        assert len(result["questioned_points"]) == 3

    def test_threshold_boundary(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
            _make_persona("p3", primary_stance="negative"),
            _make_persona("p4", primary_stance="negative"),
            _make_persona("p5", primary_stance="positive"),
        ]
        result = compute_consensus(personas, threshold=0.6)
        assert "positive" in result["agreed_points"]
        assert result["stance_distribution"]["positive"] == 3

    def test_empty_input(self):
        result = compute_consensus([], threshold=0.7)
        assert result["agreed_points"] == []
        assert result["questioned_points"] == []
        assert result["stance_distribution"] == {}


class TestComputeDisagreements:
    def test_no_disagreements(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
        ]
        result = compute_disagreements(personas)
        assert len(result) == 0

    def test_basic_disagreement(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        result = compute_disagreements(personas)
        assert len(result) >= 1
        assert result[0]["topic"] != ""
        assert len(result[0]["persona_stances"]) >= 2
        assert result[0]["resolution_suggestion"] != ""

    def test_disagreement_with_common_issues(self):
        personas = [
            _make_persona(
                "p1",
                primary_stance="positive",
                key_issues=[
                    {"severity": "low", "title": "UI lag", "why_it_matters": "annoying", "suggested_fix": "optimize"},
                ],
            ),
            _make_persona(
                "p2",
                primary_stance="negative",
                key_issues=[
                    {"severity": "critical", "title": "UI lag", "why_it_matters": "game-breaking", "suggested_fix": "rewrite"},
                ],
            ),
        ]
        result = compute_disagreements(personas)
        assert len(result) >= 1
        topic_found = any("UI lag" in d["topic"] for d in result)
        assert topic_found

    def test_disagreement_persona_stances_structure(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        result = compute_disagreements(personas)
        for d in result:
            for ps in d["persona_stances"]:
                assert "persona_id" in ps
                assert "stance" in ps
                assert "evidence" in ps

    def test_disagreement_dedup_method_recorded(self):
        """P1-2: disagreements 应记录 dedup_method"""
        from runner.similarity import get_issue_similarity
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        result = compute_disagreements(personas)
        for d in result:
            assert "dedup_method" in d
            assert d["dedup_method"] in ("semantic", "lexical")

    def test_disagreement_similarity_merges_paraphrased_titles(self):
        """P1-2: 相似度合并应将换措辞的同一议题归为一组"""
        personas = [
            _make_persona(
                "p1",
                primary_stance="positive",
                key_issues=[
                    {"severity": "low", "title": "UI lag", "why_it_matters": "annoying", "suggested_fix": "optimize"},
                ],
            ),
            _make_persona(
                "p2",
                primary_stance="negative",
                key_issues=[
                    {"severity": "critical", "title": "UI lag", "why_it_matters": "game-breaking", "suggested_fix": "rewrite"},
                ],
            ),
        ]
        from runner.similarity import get_issue_similarity
        sim = get_issue_similarity(force_lexical=True)
        result = compute_disagreements(personas, similarity=sim)
        # 两个 persona 对同一议题有不同立场，应产生争议
        assert len(result) >= 1
        for d in result:
            assert d["dedup_method"] == "lexical"


class TestComputePriorityFixes:
    def test_basic_priority(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "critical", "title": "Crash on start", "why_it_matters": "can't play", "suggested_fix": "fix init"},
                ],
            ),
            _make_persona(
                "p2",
                key_issues=[
                    {"severity": "medium", "title": "Slow menu", "why_it_matters": "annoying", "suggested_fix": "optimize"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        assert len(result) >= 2
        assert result[0]["severity"] == "critical"
        assert result[0]["priority"] == 1

    def test_deduplication_by_title(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "high", "title": "UI lag", "why_it_matters": "bad UX", "suggested_fix": "optimize"},
                ],
            ),
            _make_persona(
                "p2",
                key_issues=[
                    {"severity": "high", "title": "UI lag", "why_it_matters": "slow", "suggested_fix": "cache"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        ui_lag_items = [r for r in result if r["issue"] == "UI lag"]
        assert len(ui_lag_items) == 1
        assert len(ui_lag_items[0]["affected_personas"]) == 2

    def test_severity_score_calculation(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "critical", "title": "Crash", "why_it_matters": "broken", "suggested_fix": "fix"},
                ],
            ),
            _make_persona(
                "p2",
                key_issues=[
                    {"severity": "low", "title": "Typo", "why_it_matters": "minor", "suggested_fix": "edit"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        crash_item = next(r for r in result if r["issue"] == "Crash")
        typo_item = next(r for r in result if r["issue"] == "Typo")
        assert crash_item["score"] > typo_item["score"]

    def test_affected_count_increases_score(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                ],
            ),
            _make_persona(
                "p2",
                key_issues=[
                    {"severity": "high", "title": "Bug A", "why_it_matters": "bad", "suggested_fix": "fix"},
                ],
            ),
            _make_persona(
                "p3",
                key_issues=[
                    {"severity": "high", "title": "Bug B", "why_it_matters": "bad", "suggested_fix": "fix"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        bug_a = next(r for r in result if r["issue"] == "Bug A")
        bug_b = next(r for r in result if r["issue"] == "Bug B")
        assert bug_a["score"] > bug_b["score"]

    def test_empty_issues(self):
        personas = [_make_persona("p1", key_issues=[])]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        assert result == []

    def test_result_structure(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "high", "title": "Bug", "why_it_matters": "bad", "suggested_fix": "fix it"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        item = result[0]
        assert "priority" in item
        assert "issue" in item
        assert "severity" in item
        assert "why_it_matters" in item
        assert "affected_personas" in item
        assert "suggested_fix" in item
        assert "score" in item


class TestAggregateReport:
    def test_basic_report_structure(self):
        personas = [
            _make_persona("p1", primary_stance="positive", missing_information=["price"]),
            _make_persona("p2", primary_stance="positive", missing_information=["release date"]),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert "meta" in report
        assert "executive_summary" in report
        assert "consensus" in report
        assert "major_disagreements" in report
        assert "priority_fixes" in report
        assert "persona_notes" in report
        assert "information_gaps" in report
        assert "next_human_test" in report

    def test_meta_fields(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        meta = report["meta"]
        assert meta["task_type"] == "demo_first_play"
        assert meta["target"] == "GameX"
        assert meta["build_version"] == "0.1.0"
        assert meta["prompt_version"] == "0.1.0"
        assert meta["persona_pack_version"] == "0.1.0"
        assert meta["is_synthetic"] is True
        datetime.fromisoformat(meta["generated_at"])

    def test_executive_summary_primary_recommendation(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
            _make_persona("p3", primary_stance="negative"),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["primary_recommendation"] == "positive"

    def test_executive_summary_release_risk(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "critical", "title": "Crash", "why_it_matters": "broken", "suggested_fix": "fix"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["release_risk"] in ["low", "medium", "high", "critical"]

    def test_executive_summary_release_risk_critical(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "critical", "title": "Crash", "why_it_matters": "broken", "suggested_fix": "fix"},
                    {"severity": "high", "title": "Bug", "why_it_matters": "bad", "suggested_fix": "fix"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["release_risk"] == "critical"

    def test_executive_summary_evidence_quality(self):
        personas = [
            _make_persona("p1", evidence_sufficiency=0.9),
            _make_persona("p2", evidence_sufficiency=0.8),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["evidence_quality"] in ["strong", "medium", "weak", "insufficient"]

    def test_information_gaps_dedup(self):
        personas = [
            _make_persona("p1", missing_information=["price", "release date"]),
            _make_persona("p2", missing_information=["price", "system requirements"]),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        gaps = report["information_gaps"]
        assert "price" in gaps
        assert gaps.count("price") == 1

    def test_next_human_test_structure(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        nht = report["next_human_test"]
        assert "suggested_tasks" in nht
        assert "recruit_types" in nht
        assert "next_materials" in nht

    def test_persona_notes_structure(self):
        personas = [_make_persona("p1", persona_name="Alice")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        notes = report["persona_notes"]
        assert len(notes) == 1
        assert notes[0]["persona_id"] == "p1"
        assert notes[0]["persona_name"] == "Alice"

    def test_with_cross_exam_data(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        cross_exam = {"rounds": [{"round_num": 1, "is_current": True}], "disputes": [], "vote_changes": [], "confidence_changes": []}
        report = aggregate_report(personas, "demo_first_play", "GameX", rules, cross_exam_data=cross_exam)
        assert "meta" in report
        assert "cross_examination" in report
        assert report["cross_examination"] is not None


class TestRenderMarkdownReport:
    def test_renders_basic_report(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        md = render_markdown_report(report, TEMPLATE_PATH)
        assert "GameX" in md
        assert "demo_first_play" in md
        assert "positive" in md

    def test_template_file_not_found(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        with pytest.raises(FileNotFoundError):
            render_markdown_report(report, "/nonexistent/template.md")

    def test_markdown_contains_sections(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        md = render_markdown_report(report, TEMPLATE_PATH)
        assert "Consensus" in md
        assert "Priority Fixes" in md
