"""Counterfactual checks for identity/behaviour decoupling.

The primary guarantee tested here is *non-interference*: changing a protected
demographic field while holding behavioural fields constant must not change the
payload sent to the model.  This is deliberately a deterministic, pre-call
check.  Comparing two stochastic model samples would confound identity effects
with sampling noise and would therefore be weaker evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Callable, Iterable, Mapping, Sequence


PROTECTED_FIELDS = ("gender", "age_range", "region")

DEFAULT_COUNTERFACTUALS = {
    "gender": "__counterfactual_gender__",
    "age_range": "99-100",
    "region": "__counterfactual_region__",
}


def _canonical_payload(payload) -> bytes:
    """Return a stable byte representation for text or multimodal prompts."""
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def payload_fingerprint(payload) -> str:
    return hashlib.sha256(_canonical_payload(payload)).hexdigest()


def build_counterfactual(
    persona: Mapping,
    field: str,
    replacement=None,
) -> dict:
    """Clone ``persona`` and intervene on exactly one protected field."""
    if field not in PROTECTED_FIELDS:
        raise ValueError(f"unsupported protected field: {field}")
    result = copy.deepcopy(dict(persona))
    result[field] = (
        DEFAULT_COUNTERFACTUALS[field] if replacement is None else replacement
    )
    return result


def audit_persona_non_interference(
    persona: Mapping,
    render: Callable[[dict], object],
    protected_fields: Sequence[str] = PROTECTED_FIELDS,
) -> dict:
    """Audit whether protected-field interventions alter a rendered payload."""
    baseline = render(copy.deepcopy(dict(persona)))
    baseline_fingerprint = payload_fingerprint(baseline)
    interventions = []

    for field in protected_fields:
        counterfactual = build_counterfactual(persona, field)
        candidate = render(counterfactual)
        fingerprint = payload_fingerprint(candidate)
        interventions.append(
            {
                "field": field,
                "passed": fingerprint == baseline_fingerprint,
                "baseline_fingerprint": baseline_fingerprint,
                "counterfactual_fingerprint": fingerprint,
            }
        )

    passed_count = sum(item["passed"] for item in interventions)
    total = len(interventions)
    return {
        "persona_id": persona.get("id"),
        "passed": passed_count == total,
        "score": round(passed_count / total, 4) if total else 1.0,
        "interventions": interventions,
    }


def audit_panel_non_interference(
    personas: Iterable[Mapping],
    render: Callable[[dict], object],
    protected_fields: Sequence[str] = PROTECTED_FIELDS,
) -> dict:
    """Run the non-interference audit for a panel and aggregate the score."""
    results = [
        audit_persona_non_interference(persona, render, protected_fields)
        for persona in personas
    ]
    interventions = [
        intervention
        for result in results
        for intervention in result["interventions"]
    ]
    passed_count = sum(item["passed"] for item in interventions)
    total = len(interventions)
    failures = [
        {
            "persona_id": result["persona_id"],
            "field": item["field"],
            "baseline_fingerprint": item["baseline_fingerprint"],
            "counterfactual_fingerprint": item["counterfactual_fingerprint"],
        }
        for result in results
        for item in result["interventions"]
        if not item["passed"]
    ]
    return {
        "metric": "counterfactual_identity_non_interference",
        "definition": (
            "Protected-field interventions that leave the rendered model payload unchanged"
        ),
        "protected_fields": list(protected_fields),
        "persona_count": len(results),
        "intervention_count": total,
        "passed_interventions": passed_count,
        "score": round(passed_count / total, 4) if total else 1.0,
        "passed": not failures,
        "failures": failures,
        "personas": results,
        "limitation": (
            "This proves direct protected fields do not affect the model payload; "
            "it does not prove that names or free-text identity summaries contain no proxies."
        ),
    }
