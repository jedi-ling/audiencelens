from typing import List


def load_evidence_types(artifact_bundle: dict) -> List[str]:
    materials = artifact_bundle.get("materials", [])
    seen = set()
    result = []
    for item in materials:
        t = item.get("type", "")
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _fuzzy_match(needed_type: str, available_types: List[str]) -> bool:
    n = needed_type.lower()
    for a in available_types:
        al = a.lower()
        if n in al or al in n:
            return True
        if len(n) > 1 and len(al) > 1:
            common = sum(1 for c in n if c in al)
            if common / max(len(n), len(al)) > 0.4:
                return True
    return False


# 对话链路（/ask）的材料统一是自由文本，type 就叫 "text"。它是"万能证据"：
# 用户用大白话把想法讲清楚，任何人格都能据此表态——不该因为缺"截图/定价页"
# 这类结构化证据类型就把人全跳过（那道门槛是给 Wizard 结构化多材料评审用的）。
# 没有这一条，每一次对话评审都会因为 type="text" 匹配不上人格需要的证据类型而
# 被整团跳过，报告空壳（0 角色/0 修复项）。
FREEFORM_EVIDENCE_TYPES = {"text", "用户输入", "补充信息", "自由描述", ""}


def check_evidence_coverage(
    persona: dict, available_evidence_types: List[str]
) -> dict:
    needed = persona.get("evidence_types_needed", [])

    has_freeform = any(t in FREEFORM_EVIDENCE_TYPES for t in available_evidence_types)

    if len(needed) == 0 or has_freeform:
        coverage_ratio = 1.0
        missing = []
    else:
        covered = []
        missing = []
        for n in needed:
            if n in available_evidence_types or _fuzzy_match(n, available_evidence_types):
                covered.append(n)
            else:
                missing.append(n)
        coverage_ratio = len(covered) / len(needed)

    sufficient = coverage_ratio >= 0.3

    return {
        "persona_id": persona["id"],
        "needed": list(needed),
        "available": list(available_evidence_types),
        "missing": missing,
        "coverage_ratio": coverage_ratio,
        "sufficient": sufficient,
    }


def precheck_panel(personas: List[dict], artifact_bundle: dict) -> dict:
    available_types = load_evidence_types(artifact_bundle)

    valid_personas = []
    skipped_personas = []
    total_needed = 0
    total_covered = 0

    for persona in personas:
        coverage = check_evidence_coverage(persona, available_types)
        needed = coverage["needed"]
        total_needed += len(needed)
        covered_count = len(set(needed) & set(available_types))
        total_covered += covered_count

        if coverage["sufficient"]:
            valid_personas.append(persona)
        else:
            skipped_personas.append({
                "persona_id": persona["id"],
                "reason": f"Insufficient evidence coverage: {coverage['coverage_ratio']:.0%}",
                "missing": coverage["missing"],
            })

    return {
        "valid_personas": valid_personas,
        "skipped_personas": skipped_personas,
        "evidence_summary": {
            "available_types": available_types,
            "total_needed": total_needed,
            "total_covered": total_covered,
        },
    }
