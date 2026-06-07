import json
import re
from typing import List, Optional

import jsonschema


def load_schema(schema_path: str) -> dict:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(output: dict, schema: dict) -> dict:
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(output), key=lambda e: list(e.path))
    error_messages = [f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]
    return {"valid": len(error_messages) == 0, "errors": error_messages}


def validate_role_consistency(output: dict, persona: dict) -> dict:
    issues = []
    must_comment_on_check = output.get("must_comment_on_check", {})
    total = len(must_comment_on_check)
    if total == 0:
        coverage = 1.0
    else:
        covered = sum(1 for v in must_comment_on_check.values() if v is True)
        coverage = covered / total
    if coverage < 0.8:
        issues.append(f"角色漂移: must_comment_on覆盖率{coverage:.0%}低于80%")

    evidence = output.get("evidence", [])
    inferred_count = sum(1 for e in evidence if e.get("inference_level") == "inferred")
    if len(evidence) == 0:
        inferred_ratio = 0.0
    else:
        inferred_ratio = inferred_count / len(evidence)
    if inferred_ratio > 0.4:
        issues.append(f"推断过度: inferred比例{inferred_ratio:.0%}超过40%")

    consistent = len(issues) == 0
    return {
        "consistent": consistent,
        "must_comment_on_coverage": coverage,
        "inferred_ratio": inferred_ratio,
        "issues": issues,
    }


def validate_evidence_grounding(output: dict, artifact_texts: List[str]) -> dict:
    evidence = output.get("evidence", [])
    direct_entries = [e for e in evidence if e.get("inference_level") == "direct"]
    ungrounded = []

    for entry in direct_entries:
        content = entry.get("content", "")
        tokens = [t for t in re.split(r"[\s,，。.!！?？、：:；;()（）\[\]【】]+", content) if len(t) > 1]
        found = False
        for token in tokens:
            for text in artifact_texts:
                if token in text:
                    found = True
                    break
            if found:
                break
        if not found:
            ungrounded.append(content)

    total_direct = len(direct_entries)
    if total_direct == 0:
        hallucination_risk = 0.0
    else:
        hallucination_risk = len(ungrounded) / total_direct

    grounded = hallucination_risk < 0.3
    return {
        "grounded": grounded,
        "ungrounded_evidence": ungrounded,
        "hallucination_risk": hallucination_risk,
    }


def validate_output(
    output: dict,
    persona: dict,
    schema: dict,
    artifact_texts: Optional[List[str]] = None,
) -> dict:
    schema_result = validate_schema(output, schema)
    role_result = validate_role_consistency(output, persona)

    schema_valid = schema_result["valid"]
    role_consistent = role_result["consistent"]

    if artifact_texts is not None:
        evidence_result = validate_evidence_grounding(output, artifact_texts)
        evidence_grounded = evidence_result["grounded"]
    else:
        evidence_grounded = True

    passed = schema_valid and role_consistent and evidence_grounded

    return {
        "schema_valid": schema_valid,
        "role_consistent": role_consistent,
        "evidence_grounded": evidence_grounded,
        "passed": passed,
        "details": {
            "schema": schema_result,
            "role": role_result,
            "evidence": validate_evidence_grounding(output, artifact_texts) if artifact_texts is not None else None,
        },
    }


def check_identity_behavior_decoupling(output: dict) -> dict:
    pattern = re.compile(r"(?:作为[男女女性男性]|她|他).*?(?:所以|因此)")
    violations = []

    for entry in output.get("evidence", []):
        content = entry.get("content", "")
        matches = pattern.findall(content)
        for m in matches:
            violations.append(f"evidence: {m}")

    for issue in output.get("key_issues", []):
        for field in ["title", "why_it_matters", "suggested_fix"]:
            text = issue.get(field, "")
            matches = pattern.findall(text)
            for m in matches:
                violations.append(f"key_issues.{field}: {m}")

    return {
        "decoupled": len(violations) == 0,
        "violations": violations,
    }
