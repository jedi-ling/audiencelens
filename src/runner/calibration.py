from itertools import combinations
from typing import List, Optional


# 形状归一化的正主是 persona_agent.normalize_persona_output（模型输出的唯一入口边界）。
# 这里只补"绕过那道边界"的路径：老数据回放、外部直接调 calibration、单测。
# 历史上本模块用 p["persona_id"] 硬下标，v2 全靠 cli.py 里的 setdefault 才没崩，
# 直接调用路径一个缺字段的输出就能让整轮校准 KeyError。


def _persona_id(persona_output: dict, index: int) -> str:
    """persona_id 缺失时给个稳定的占位键，避免 KeyError 让整轮校准作废。
    用下标而不是空串，否则多个缺 id 的输出会在 per_persona 里互相覆盖。"""
    pid = persona_output.get("persona_id")
    if isinstance(pid, str) and pid:
        return pid
    return f"unknown-persona-{index}"


def _dict_items(value) -> List[dict]:
    """只留 dict 元素——第三方模型会把 evidence/key_issues 吐成字符串数组，
    对字符串调 .get()/["title"] 会 AttributeError / TypeError。"""
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def compute_role_consistency_rate(persona_outputs: List[dict]) -> dict:
    if not persona_outputs:
        return {"per_persona": {}, "average": 0.0, "below_threshold": []}

    per_persona = {}
    for index, p in enumerate(persona_outputs):
        check = p.get("must_comment_on_check", {})
        if not isinstance(check, dict):
            check = {}
        total = len(check)
        if total == 0:
            per_persona[_persona_id(p, index)] = 0.0
        else:
            true_count = sum(1 for v in check.values() if v)
            per_persona[_persona_id(p, index)] = true_count / total

    average = sum(per_persona.values()) / len(per_persona) if per_persona else 0.0
    below_threshold = [pid for pid, rate in per_persona.items() if rate < 0.8]

    return {
        "per_persona": per_persona,
        "average": average,
        "below_threshold": below_threshold,
    }


def compute_coverage_score(persona_outputs: List[dict]) -> dict:
    issue_sets = {}
    for index, p in enumerate(persona_outputs):
        # 只取 dict 形态的 issue 且 title 非空：字符串形态的 issue 会让 issue["title"]
        # 抛 TypeError（string indices must be integers），实测 {"key_issues": "无重大问题"}
        titles = set(
            title
            for title in (
                issue.get("title", "") for issue in _dict_items(p.get("key_issues", []))
            )
            if isinstance(title, str) and title
        )
        issue_sets[_persona_id(p, index)] = titles

    ids = list(issue_sets.keys())
    pairwise_distances = {}

    if len(ids) < 2:
        # 覆盖度是"人格之间"的两两距离，n<2 时这个指标在数学上就不存在。
        # 以前这里返回 0.0，单人格面板的导出件会打印「视角覆盖度 0.0 / 合格线 ≥0.3 /
        # 未通过」——把"无定义"伪装成"很差"。无定义就得说无定义：值给 None，
        # 并带 not_applicable 标记让渲染层和 overall_pass 都能识别。
        return {
            "pairwise_distances": pairwise_distances,
            "average_distance": None,
            "min_distance": None,
            "not_applicable": True,
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
    """每位人格的 direct 证据里，**未落地条目的占比**（报告级的校准指标）。

    和校验器是同一个函数、同一份参数（validator.validate_evidence_grounding →
    src/config/grounding.yaml）：只核对 direct 条目的 quote，缺 quote 算未落地。
    以前这里是另一套口径——整条 content 必须是材料的子串——同一条证据在门控和校准里
    会得出两个结论。键名 hallucination 为兼容保留；它不是"幻觉概率"。
    """
    from .validator import validate_evidence_grounding

    per_persona = {}
    high_risk_personas = []

    for index, p in enumerate(persona_outputs):
        pid = _persona_id(p, index)
        if not isinstance(p, dict):
            per_persona[pid] = 0.0
            continue
        rate = validate_evidence_grounding(p, artifact_texts)["hallucination_risk"]
        per_persona[pid] = rate
        if rate > 0.5:
            high_risk_personas.append(pid)

    average = sum(per_persona.values()) / len(per_persona) if per_persona else 0.0
    below_threshold = [pid for pid, rate in per_persona.items() if rate < 0.8]

    return {
        "per_persona": per_persona,
        "average": average,
        "below_threshold": below_threshold,
    }


def compute_coverage_score(persona_outputs: List[dict]) -> dict:
    issue_sets = {}
    for index, p in enumerate(persona_outputs):
        # 只取 dict 形态的 issue 且 title 非空：字符串形态的 issue 会让 issue["title"]
        # 抛 TypeError（string indices must be integers），实测 {"key_issues": "无重大问题"}
        titles = set(
            title
            for title in (
                issue.get("title", "") for issue in _dict_items(p.get("key_issues", []))
            )
            if isinstance(title, str) and title
        )
        issue_sets[_persona_id(p, index)] = titles

    ids = list(issue_sets.keys())
    pairwise_distances = {}

    if len(ids) < 2:
        # 覆盖度是"人格之间"的两两距离，n<2 时这个指标在数学上就不存在。
        # 以前这里返回 0.0，单人格面板的导出件会打印「视角覆盖度 0.0 / 合格线 ≥0.3 /
        # 未通过」——把"无定义"伪装成"很差"。无定义就得说无定义：值给 None，
        # 并带 not_applicable 标记让渲染层和 overall_pass 都能识别。
        return {
            "pairwise_distances": pairwise_distances,
            "average_distance": None,
            "min_distance": None,
            "not_applicable": True,
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

    for index, p in enumerate(persona_outputs):
        pid = _persona_id(p, index)
        direct_evidence = [
            e
            for e in _dict_items(p.get("evidence", []))
            if e.get("inference_level") == "direct"
        ]
        if not direct_evidence:
            per_persona[pid] = 0.0
            continue

        unsupported = 0
        for e in direct_evidence:
            content = e.get("content", "")
            if not isinstance(content, str) or not content:
                # 没有可核对的原文就不算"未被支持"，否则会凭空推高幻觉率
                continue
            found = any(content in text for text in artifact_texts)
            if not found:
                unsupported += 1

        rate = unsupported / len(direct_evidence)
        per_persona[pid] = rate
        if rate > 0.5:
            high_risk_personas.append(pid)

    average = sum(per_persona.values()) / len(per_persona) if per_persona else 0.0

    return {
        "per_persona": per_persona,
        "average": average,
        "high_risk_personas": high_risk_personas,
    }


def compute_rerun_stability(outputs_run1: List[dict], outputs_run2: List[dict]) -> dict:
    # primary_stance 缺失时用空串占位：两轮都缺就算"一致"，一轮缺就算"分歧"，
    # 都比 KeyError 让整个稳定性检查作废合理
    run1_map = {
        _persona_id(p, i): p.get("primary_stance", "") for i, p in enumerate(outputs_run1)
    }
    run2_map = {
        _persona_id(p, i): p.get("primary_stance", "") for i, p in enumerate(outputs_run2)
    }

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

    # 覆盖度在 n<2 时无定义（not_applicable）：不适用不能算失败，否则单人格评审
    # 永远"校准未通过"，把指标缺席伪装成质量问题。此时总判定只看角色一致性。
    if coverage.get("not_applicable"):
        coverage_ok = True
    else:
        coverage_ok = coverage["average_distance"] >= 0.3
    overall_pass = role_consistency["average"] >= 0.8 and coverage_ok

    return {
        "role_consistency": role_consistency,
        "coverage": coverage,
        "hallucination": hallucination,
        "stability": stability,
        "overall_pass": overall_pass,
    }
