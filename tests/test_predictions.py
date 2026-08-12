from src.runner.predictions import build_falsifiable_predictions


def test_builds_directional_control_comparison_without_inventing_effect_size():
    report = {
        "priority_fixes": [
            {
                "issue": "首屏看不到价格",
                "severity": "high",
                "why_it_matters": "用户无法判断是否值得继续",
                "suggested_fix": "在首屏展示价格与试用政策",
                "affected_personas": ["P01", "P02"],
            }
        ]
    }
    rows = build_falsifiable_predictions(report, "pricing_page_review", panel_size=4)
    assert len(rows) == 1
    prediction = rows[0]
    assert prediction["target_metric"] == "paid_conversion_rate"
    assert prediction["success_criterion"] == (
        "treatment.paid_conversion_rate > control.paid_conversion_rate"
    )
    assert prediction["verification_method"] == "controlled_comparison"
    assert prediction["confidence_basis"].endswith("not_empirically_calibrated")
    assert "effect_size" not in prediction
    assert prediction["is_synthetic"] is True


def test_skips_findings_without_an_actionable_intervention():
    report = {
        "priority_fixes": [
            {"issue": "价格不清楚", "severity": "high", "suggested_fix": ""},
            {"issue": "", "severity": "low", "suggested_fix": "补图"},
        ]
    }
    assert build_falsifiable_predictions(report, "pricing_page_review", 3) == []


def test_deduplicates_and_caps_unverified_confidence():
    fix = {
        "issue": "同一问题",
        "severity": "critical",
        "suggested_fix": "修复它",
        "affected_personas": [f"P{i}" for i in range(20)],
    }
    rows = build_falsifiable_predictions(
        {"priority_fixes": [fix, dict(fix)]}, "concept_review", panel_size=2
    )
    assert len(rows) == 1
    assert rows[0]["confidence"] == 0.89
