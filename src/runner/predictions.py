"""Turn report findings into explicit, falsifiable intervention hypotheses."""

from __future__ import annotations

from typing import Mapping, Sequence


TASK_METRICS = {
    "steam_page_review": ("wishlist_add_rate", "14d"),
    "demo_first_play": ("demo_continuation_rate", "7d"),
    "concept_review": ("concept_preference_rate", "14d"),
    "monetization_review": ("purchase_conversion_rate", "14d"),
    "looking_for_party_post": ("join_intent_rate", "7d"),
    "update_announcement_review": ("return_rate", "14d"),
    "devlog_review": ("qualified_engagement_rate", "14d"),
    "kickstarter_review": ("pledge_conversion_rate", "14d"),
    "localization_review": ("task_success_rate", "14d"),
    "discord_community_review": ("community_join_rate", "14d"),
    "product_feedback_review": ("retention_rate", "14d"),
    "pricing_page_review": ("paid_conversion_rate", "14d"),
    "onboarding_review": ("onboarding_completion_rate", "7d"),
    "pitch_review": ("qualified_followup_rate", "30d"),
}

SEVERITY_CONFIDENCE = {
    "low": 0.45,
    "medium": 0.55,
    "high": 0.65,
    "critical": 0.75,
}


def _confidence(fix: Mapping, panel_size: int) -> float:
    """A conservative heuristic, explicitly not empirical calibration."""
    severity = SEVERITY_CONFIDENCE.get(str(fix.get("severity", "")).lower(), 0.45)
    affected = len(set(fix.get("affected_personas") or []))
    coverage = affected / panel_size if panel_size > 0 else 0.0
    # Support can add at most 0.15. Even unanimous synthetic agreement is capped
    # below 0.9 because it is not outcome evidence.
    return round(min(0.89, severity + 0.15 * coverage), 3)


def build_falsifiable_predictions(
    report: Mapping,
    task_type: str,
    panel_size: int,
    verification_window: str = None,
) -> list:
    """Build testable treatment-vs-control hypotheses from priority fixes.

    No effect size is invented.  The success criterion is directional and must
    be verified with a controlled comparison or equivalent real-user evidence.
    """
    metric, default_window = TASK_METRICS.get(
        task_type, ("task_success_rate", "14d")
    )
    window = verification_window or default_window
    predictions = []
    seen = set()
    for fix in report.get("priority_fixes", []) or []:
        issue = str(fix.get("issue") or fix.get("title") or "").strip()
        intervention = str(fix.get("suggested_fix") or "").strip()
        if not issue or not intervention or issue in seen:
            continue
        seen.add(issue)
        confidence = _confidence(fix, panel_size)
        predictions.append(
            {
                "prediction_id": f"PRED-{len(predictions) + 1:03d}",
                "type": "intervention_hypothesis",
                "claim": f"修复“{issue}”后，{metric} 相较当前版本将提高",
                "issue": issue,
                "intervention": intervention,
                "target_metric": metric,
                "direction": "increase",
                "comparison": "treatment_vs_current_control",
                "success_criterion": f"treatment.{metric} > control.{metric}",
                "verification_window": window,
                "verification_method": "controlled_comparison",
                "severity": fix.get("severity"),
                "confidence": confidence,
                "confidence_basis": "synthetic_panel_heuristic_not_empirically_calibrated",
                "affected_personas": list(fix.get("affected_personas") or []),
                "evidence": fix.get("why_it_matters") or fix.get("evidence"),
                "status": "pending_verification",
                "is_synthetic": True,
            }
        )
    return predictions
