from itertools import combinations
from typing import List, Optional


def compute_role_consistency_rate(persona_outputs: List[dict]) -> dict:
    if not persona_outputs:
        return {"per_persona": {}, "average": 0.0, "below_threshold": []}

    per_persona = {}
    for p in persona_outputs:
        check = p.get("must_comment_on_check", {})
        total = len(check)
        if total == 0:
            per_persona[p["persona_id"]] = 0.0
        else:
            true_count = sum(1 for v in check.values() if v)
            per_persona[p["persona_id"]] = true_count / total

    average = sum(per_persona.values()) / len(per_persona) if per_persona else 0.0
    below_threshold = [pid for pid, rate in per_persona.items() if rate < 0.8]

    return {
        "per_persona": per_persona,
        "average": average,
        "below_threshold": below_threshold,
    }


def compute_coverage_score(persona_outputs: List[dict]) -> dict:
    issue_sets = {}
    for p in persona_outputs:
        titles = set(issue["title"] for issue in p.get("key_issues", []))
        issue_sets[p["persona_id"]] = titles

    ids = list(issue_sets.keys())
    pairwise_distances = {}

    if len(ids) < 2:
        return {
            "pairwise_distances": pairwise_distances,
            "average_distance": 0.0,
            "min_distance": 0.0,
        }

    for id1, id2 in combinations(ids, 2):
        set1 = issue_sets[id1]
        set2 = issue_sets[id2]
        union = set1 | set2
        if len(union) == 0:
            distance = 0.0
        else:
            intersection = set1 & set2
            distance = 1.0 - len(intersection) / len(union)
        pairwise_distances[(id1, id2)] = distance

    distances = list(pairwise_distances.values())
    average_distance = sum(distances) / len(distances)
    min_distance = min(distances)

    return {
        "pairwise_distances": pairwise_distances,
        "average_distance": average_distance,
        "min_distance": min_distance,
    }


def compute_hallucination_rate(persona_outputs: List[dict], artifact_texts: List[str]) -> dict:
    per_persona = {}
    high_risk_personas = []

    for p in persona_outputs:
        direct_evidence = [
            e for e in p.get("evidence", []) if e.get("inference_level") == "direct"
        ]
        if not direct_evidence:
            per_persona[p["persona_id"]] = 0.0
            continue

        unsupported = 0
        for e in direct_evidence:
            content = e["content"]
            found = any(content in text for text in artifact_texts)
            if not found:
                unsupported += 1

        rate = unsupported / len(direct_evidence)
        per_persona[p["persona_id"]] = rate
        if rate > 0.5:
            high_risk_personas.append(p["persona_id"])

    average = sum(per_persona.values()) / len(per_persona) if per_persona else 0.0

    return {
        "per_persona": per_persona,
        "average": average,
        "high_risk_personas": high_risk_personas,
    }


def compute_rerun_stability(outputs_run1: List[dict], outputs_run2: List[dict]) -> dict:
    run1_map = {p["persona_id"]: p["primary_stance"] for p in outputs_run1}
    run2_map = {p["persona_id"]: p["primary_stance"] for p in outputs_run2}

    common_ids = set(run1_map.keys()) & set(run2_map.keys())
    if not common_ids:
        return {
            "stance_agreement_rate": 0.0,
            "disagreed_personas": [],
            "stable": False,
        }

    agreed = 0
    disagreed_personas = []
    for pid in common_ids:
        if run1_map[pid] == run2_map[pid]:
            agreed += 1
        else:
            disagreed_personas.append(pid)

    agreement_rate = agreed / len(common_ids)
    stable = agreement_rate >= 0.8

    return {
        "stance_agreement_rate": agreement_rate,
        "disagreed_personas": disagreed_personas,
        "stable": stable,
    }


def run_calibration_check(
    persona_outputs: List[dict],
    artifact_texts: Optional[List[str]] = None,
    previous_outputs: Optional[List[dict]] = None,
) -> dict:
    role_consistency = compute_role_consistency_rate(persona_outputs)
    coverage = compute_coverage_score(persona_outputs)

    hallucination = None
    if artifact_texts is not None:
        hallucination = compute_hallucination_rate(persona_outputs, artifact_texts)

    stability = None
    if previous_outputs is not None:
        stability = compute_rerun_stability(previous_outputs, persona_outputs)

    overall_pass = (
        role_consistency["average"] >= 0.8 and coverage["average_distance"] >= 0.3
    )

    return {
        "role_consistency": role_consistency,
        "coverage": coverage,
        "hallucination": hallucination,
        "stability": stability,
        "overall_pass": overall_pass,
    }
