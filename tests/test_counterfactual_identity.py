from src.harness.counterfactual_identity import (
    audit_panel_non_interference,
    audit_persona_non_interference,
    build_counterfactual,
)
from src.runner.persona_agent import render_prompt


def _persona():
    return {
        "id": "P99-test",
        "name": "测试评审者",
        "gender": "女",
        "age_range": "25-34",
        "region": "华东",
        "archetype": "谨慎型",
        "identity_summary": "重视证据的长期用户",
        "behavior_profile": {"patience": "高", "risk_tolerance": "低"},
        "motivations": ["降低决策风险"],
        "decision_rules": ["证据不足时保持观望"],
        "quit_triggers": ["隐瞒价格"],
        "continue_triggers": ["提供可验证数据"],
        "first_scan_focus": ["证据"],
        "review_output": {"must_comment_on": ["可信度"]},
    }


def test_counterfactual_changes_only_requested_field():
    original = _persona()
    changed = build_counterfactual(original, "region", "火星")
    assert changed["region"] == "火星"
    assert original["region"] == "华东"
    assert {k: v for k, v in changed.items() if k != "region"} == {
        k: v for k, v in original.items() if k != "region"
    }


def test_rejects_non_protected_intervention():
    try:
        build_counterfactual(_persona(), "behavior_profile")
    except ValueError as exc:
        assert "unsupported protected field" in str(exc)
    else:
        raise AssertionError("behaviour fields must not be accepted as protected interventions")


def test_current_prompt_has_structural_non_interference(tmp_path):
    template = tmp_path / "prompt.md"
    template.write_text(
        "{{ persona_yaml_minified }}\n{{ task_type }}\n{{ artifact_summary }}",
        encoding="utf-8",
    )

    def render(persona):
        return render_prompt(
            persona,
            "concept_review",
            "一个可验证的产品概念",
            str(template),
        )

    result = audit_persona_non_interference(_persona(), render)
    assert result["passed"] is True
    assert result["score"] == 1.0
    assert len(result["interventions"]) == 3


def test_audit_detects_future_protected_field_leak():
    result = audit_persona_non_interference(
        _persona(), lambda persona: f"payload:{persona['gender']}"
    )
    assert result["passed"] is False
    assert result["score"] == 0.6667
    assert [x["field"] for x in result["interventions"] if not x["passed"]] == [
        "gender"
    ]


def test_panel_report_is_aggregated_and_honest_about_scope():
    personas = [_persona(), {**_persona(), "id": "P98-test"}]
    report = audit_panel_non_interference(personas, lambda p: p["behavior_profile"])
    assert report["passed"] is True
    assert report["score"] == 1.0
    assert report["intervention_count"] == 6
    assert "does not prove" in report["limitation"]
