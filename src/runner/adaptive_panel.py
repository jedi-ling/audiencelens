"""Adaptive panel expansion using an auditable marginal-value proxy.

This module does not claim to calculate Shannon information gain.  Before the
project has enough outcome data, it ranks the next persona by three observable
signals: task affinity, behavioural novelty, and coverage of unresolved
evidence needs.  Each component is returned so callers can explain the choice.
"""

from __future__ import annotations

from typing import Iterable, List, Mapping, Optional, Sequence

from .panel_selector import compute_behavioral_distance


DEFAULT_WEIGHTS = {
    "task_affinity": 0.35,
    "behavioral_novelty": 0.40,
    "evidence_gap_coverage": 0.25,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _task_affinity(persona: Mapping, task_type: str) -> float:
    try:
        return _clamp(float((persona.get("task_affinity") or {}).get(task_type, 0)))
    except (TypeError, ValueError):
        return 0.0


def _behavioral_novelty(persona: Mapping, selected: Sequence[Mapping]) -> float:
    if not selected:
        return 1.0
    return min(compute_behavioral_distance(dict(persona), dict(item)) for item in selected)


def _normalise_terms(values: Iterable[str]) -> set:
    return {str(value).strip().casefold() for value in values if str(value).strip()}


def _evidence_gap_coverage(persona: Mapping, unresolved_evidence: Sequence[str]) -> float:
    gaps = _normalise_terms(unresolved_evidence)
    if not gaps:
        return 0.0
    needed = _normalise_terms(persona.get("evidence_types_needed", []) or [])
    return len(gaps & needed) / len(gaps)


def score_candidate(
    persona: Mapping,
    selected: Sequence[Mapping],
    task_type: str,
    unresolved_evidence: Sequence[str] = (),
    weights: Optional[Mapping[str, float]] = None,
) -> dict:
    """Return the explainable marginal-value proxy for one candidate."""
    weights = dict(weights or DEFAULT_WEIGHTS)
    unknown = set(weights) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"unknown adaptive-panel weights: {sorted(unknown)}")
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("adaptive-panel weights must sum to a positive value")

    components = {
        "task_affinity": _task_affinity(persona, task_type),
        "behavioral_novelty": _behavioral_novelty(persona, selected),
        "evidence_gap_coverage": _evidence_gap_coverage(persona, unresolved_evidence),
    }
    score = sum(components[key] * weights.get(key, 0) for key in components) / total_weight
    return {
        "persona_id": persona.get("id"),
        "score": round(score, 4),
        "components": {key: round(value, 4) for key, value in components.items()},
        "weights": weights,
        "method": "marginal_value_proxy_v1",
    }


def recommend_next_persona(
    candidates: Sequence[Mapping],
    selected: Sequence[Mapping],
    task_type: str,
    unresolved_evidence: Sequence[str] = (),
    min_score: float = 0.15,
    weights: Optional[Mapping[str, float]] = None,
) -> dict:
    """Recommend the next persona, or stop when no candidate clears ``min_score``."""
    selected_ids = {item.get("id") for item in selected}
    eligible = [item for item in candidates if item.get("id") not in selected_ids]
    ranking = [
        score_candidate(item, selected, task_type, unresolved_evidence, weights)
        for item in eligible
    ]
    ranking.sort(key=lambda item: (-item["score"], str(item["persona_id"])))
    best = ranking[0] if ranking else None
    should_continue = best is not None and best["score"] >= min_score
    return {
        "should_continue": should_continue,
        "recommended_persona_id": best["persona_id"] if should_continue else None,
        "best_score": best["score"] if best else 0.0,
        "min_score": min_score,
        "ranking": ranking,
        "method": "marginal_value_proxy_v1",
        "limitation": (
            "This is an explainable heuristic, not measured information gain. "
            "Its weights require calibration against verified outcomes."
        ),
    }
