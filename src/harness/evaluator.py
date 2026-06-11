"""
AudienceLens Harness 8-Dimension Evaluator

Evaluates synthetic audience review reports against quantitative thresholds.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

try:
    from .stereotype_judge import detect_stereotypes
except ImportError:
    from harness.stereotype_judge import detect_stereotypes


# 默认阈值配置
DEFAULT_THRESHOLDS = {
    "actionability": {"min_ratio": 0.70, "weight": 1.0},
    "input_grounding": {"min_citation_ratio": 0.80, "min_direct_ratio": 0.60, "weight": 1.0},
    "persona_differentiation": {"min_jaccard": 0.30, "weight": 1.0},
    "stereotype_check": {"max_violations": 0, "weight": 1.5},
    "structural_integrity": {"min_section_coverage": 1.0, "weight": 1.0},
    "calibration_honesty": {"min_annotation_ratio": 1.0, "weight": 1.2},
    "risk_detection": {"min_critical_issues": 1, "weight": 1.0},
    "segment_conflict": {"min_disagreements": 2, "weight": 1.0},
}

# 必需的报告章节
REQUIRED_SECTIONS = [
    "consensus",
    "major_disagreements",
    "priority_fixes",
    "information_gaps",
    "next_human_test_recommendations",
]

# 刻板印象禁止模式
STEREOTYPE_PATTERNS = [
    re.compile(r"作为[一名个]?[男女女性男性].*?(?:所以|因此|更|偏好|倾向)", re.IGNORECASE),
    re.compile(r"(?:她|他|她们|他们)(?:天生|天然|本能地).*(?:偏好|喜欢|选择)", re.IGNORECASE),
    re.compile(r"(?:这个|那)(?:年龄|年代|岁数)(?:段|的)(?:人|玩家|用户).*(?:通常|一般|都|总是)", re.IGNORECASE),
    re.compile(r"(?:作为|身为)[A-Z]{4}.*?(?:所以|因此|决定|判断)", re.IGNORECASE),
    re.compile(r"(?:women|men|female|male)\s+(?:prefer|tend\s+to|naturally|instinctively)", re.IGNORECASE),
    re.compile(r"(?:as\s+a\s+)?(?:woman|man|girl|boy|elderly|young)\s+.*?(?:therefore|so|prefer|tend)", re.IGNORECASE),
]


def evaluate_report(report: dict, thresholds: Optional[dict] = None) -> dict:
    """
    对合成评审报告执行8维 Harness 评估。

    Args:
        report: 合成评审报告的 JSON dict，应包含 persona_reviews, consensus, cross_examination 等字段
        thresholds: 自定义阈值配置，None 则使用默认值

    Returns:
        包含8维评估结果的 dict
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    dimensions = []

    # 1. Actionability
    dimensions.append(_evaluate_actionability(report, thresholds.get("actionability", {})))

    # 2. Input Grounding
    dimensions.append(_evaluate_input_grounding(report, thresholds.get("input_grounding", {})))

    # 3. Persona Differentiation
    dimensions.append(_evaluate_persona_differentiation(report, thresholds.get("persona_differentiation", {})))

    # 4. Stereotype Check
    dimensions.append(_evaluate_stereotype_check(report, thresholds.get("stereotype_check", {})))

    # 5. Structural Integrity
    dimensions.append(_evaluate_structural_integrity(report, thresholds.get("structural_integrity", {})))

    # 6. Calibration Honesty
    dimensions.append(_evaluate_calibration_honesty(report, thresholds.get("calibration_honesty", {})))

    # 7. Risk Detection
    dimensions.append(_evaluate_risk_detection(report, thresholds.get("risk_detection", {})))

    # 8. Segment Conflict
    dimensions.append(_evaluate_segment_conflict(report, thresholds.get("segment_conflict", {})))

    # 计算综合得分
    total_weight = sum(d["weight"] for d in dimensions)
    weighted_sum = sum(d["score"] * d["weight"] for d in dimensions)
    overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    # 整体通过条件：所有维度 ≥ 2 且平均 ≥ 3.0
    all_above_min = all(d["score"] >= 2 for d in dimensions)
    overall_passed = all_above_min and overall_score >= 3.0

    return {
        "dimensions": dimensions,
        "overall_score": round(overall_score, 2),
        "overall_passed": overall_passed,
        "version": "0.3.0",
        "threshold_note": "原型阈值，未经实证验证",
    }


def _score_from_ratio(ratio: float, threshold: float) -> int:
    """根据比率与阈值的关系计算1-5分"""
    if ratio >= threshold:
        if ratio >= threshold * 1.2:
            return 5
        elif ratio >= threshold * 1.1:
            return 4
        else:
            return 4
    elif ratio >= threshold * 0.8:
        return 3
    elif ratio >= threshold * 0.5:
        return 2
    else:
        return 1


def _evaluate_actionability(report: dict, config: dict) -> dict:
    """评估可操作性：建议是否具体且可执行"""
    min_ratio = config.get("min_ratio", 0.70)
    weight = config.get("weight", 1.0)

    persona_reviews = report.get("persona_reviews", [])
    total_issues = 0
    actionable_issues = 0

    for review in persona_reviews:
        key_issues = review.get("key_issues", [])
        for issue in key_issues:
            total_issues += 1
            fix = issue.get("suggested_fix", "")
            # 检查建议是否包含具体步骤（包含动词+名词模式）
            has_what = len(fix) > 10
            has_how = any(kw in fix for kw in ["添加", "修改", "删除", "增加", "减少", "调整", "优化",
                                                "add", "remove", "change", "modify", "increase", "decrease",
                                                "简化", "突出", "强化", "移除", "替换", "重构"])
            if has_what and has_how:
                actionable_issues += 1

    ratio = actionable_issues / total_issues if total_issues > 0 else 0.0
    score = _score_from_ratio(ratio, min_ratio)

    return {
        "name": "可操作性 (Actionability)",
        "key": "actionability",
        "score": score,
        "threshold": min_ratio * 5,  # 归一化到5分制显示
        "value": round(ratio, 3),
        "passed": score >= 4,
        "weight": weight,
        "details": {
            "total_issues": total_issues,
            "actionable_issues": actionable_issues,
            "ratio": round(ratio, 3),
        },
    }


def _evaluate_input_grounding(report: dict, config: dict) -> dict:
    """评估输入依据：论证是否引用了输入材料的具体细节"""
    min_citation = config.get("min_citation_ratio", 0.80)
    min_direct = config.get("min_direct_ratio", 0.60)
    weight = config.get("weight", 1.0)

    persona_reviews = report.get("persona_reviews", [])
    total_claims = 0
    cited_claims = 0
    total_evidence = 0
    direct_evidence = 0

    for review in persona_reviews:
        evidence_list = review.get("evidence", [])
        for ev in evidence_list:
            total_evidence += 1
            level = ev.get("inference_level", ev.get("level", ""))
            if level == "direct":
                direct_evidence += 1
                cited_claims += 1
            elif level == "inferred":
                cited_claims += 1
            total_claims += 1

        key_issues = review.get("key_issues", [])
        for issue in key_issues:
            total_claims += 1
            if issue.get("evidence_ref") or issue.get("why_it_matters"):
                cited_claims += 1

    citation_ratio = cited_claims / total_claims if total_claims > 0 else 0.0
    direct_ratio = direct_evidence / total_evidence if total_evidence > 0 else 0.0

    # 综合两个子指标
    avg_ratio = (citation_ratio + direct_ratio) / 2
    score = _score_from_ratio(avg_ratio, (min_citation + min_direct) / 2)

    return {
        "name": "输入依据 (Input Grounding)",
        "key": "input_grounding",
        "score": score,
        "threshold": (min_citation + min_direct) / 2 * 5,
        "value": round(avg_ratio, 3),
        "passed": score >= 4,
        "weight": weight,
        "details": {
            "citation_ratio": round(citation_ratio, 3),
            "direct_ratio": round(direct_ratio, 3),
            "total_claims": total_claims,
            "total_evidence": total_evidence,
        },
    }


def _evaluate_persona_differentiation(report: dict, config: dict) -> dict:
    """评估人物差异化：不同人物是否产生了真正不同的视角"""
    min_jaccard = config.get("min_jaccard", 0.30)
    weight = config.get("weight", 1.0)

    persona_reviews = report.get("persona_reviews", [])

    if len(persona_reviews) < 2:
        return {
            "name": "人物差异化 (Persona Differentiation)",
            "key": "persona_differentiation",
            "score": 1,
            "threshold": min_jaccard * 5,
            "value": 0.0,
            "passed": False,
            "weight": weight,
            "details": {"error": "需要至少2个人物才能计算差异化"},
        }

    # 计算所有人物对的 Jaccard 距离
    issue_sets = []
    for review in persona_reviews:
        issues = set()
        for issue in review.get("key_issues", []):
            title = issue.get("title", "")
            if title:
                issues.add(title.lower().strip())
        issue_sets.append(issues)

    distances = []
    for i in range(len(issue_sets)):
        for j in range(i + 1, len(issue_sets)):
            s1, s2 = issue_sets[i], issue_sets[j]
            if not s1 and not s2:
                continue
            union = s1 | s2
            intersection = s1 & s2
            jaccard_dist = 1 - (len(intersection) / len(union)) if union else 1.0
            distances.append(jaccard_dist)

    mean_distance = sum(distances) / len(distances) if distances else 0.0
    score = _score_from_ratio(mean_distance, min_jaccard)

    return {
        "name": "人物差异化 (Persona Differentiation)",
        "key": "persona_differentiation",
        "score": score,
        "threshold": min_jaccard * 5,
        "value": round(mean_distance, 3),
        "passed": score >= 4,
        "weight": weight,
        "details": {
            "mean_jaccard_distance": round(mean_distance, 3),
            "num_pairs": len(distances),
            "min_distance": round(min(distances), 3) if distances else 0,
            "max_distance": round(max(distances), 3) if distances else 0,
        },
    }


def _evaluate_stereotype_check(report: dict, config: dict) -> dict:
    """评估刻板印象检查：判断是否基于行为画像而非人口统计学特征"""
    max_violations = config.get("max_violations", 0)
    weight = config.get("weight", 1.5)

    use_llm = config.get("use_llm", False)
    violations = []
    detection_method = "regex"
    persona_reviews = report.get("persona_reviews", [])

    for review in persona_reviews:
        persona_id = review.get("persona_id", "unknown")

        # 检查所有文本字段
        text_fields = []
        for issue in review.get("key_issues", []):
            for field in ["title", "why_it_matters", "suggested_fix"]:
                text_fields.append(issue.get(field, ""))
        for ev in review.get("evidence", []):
            text_fields.append(ev.get("content", ""))

        detection = detect_stereotypes(text_fields, use_llm=use_llm)
        if detection["method"] == "regex+llm":
            detection_method = "regex+llm"
        for v in detection["violations"]:
            violations.append({
                "persona_id": persona_id,
                "source": v["source"],
                "match": v["quoted_text"][:50],
                "reasoning": v.get("reasoning", ""),
            })

    violation_count = len(violations)
    passed = violation_count <= max_violations
    score = 5 if passed else max(1, 3 - violation_count)

    return {
        "name": "刻板印象检查 (Stereotype Check)",
        "key": "stereotype_check",
        "score": score,
        "threshold": max_violations,
        "value": violation_count,
        "passed": passed,
        "weight": weight,
        "details": {
            "violation_count": violation_count,
            "violations": violations[:5],  # 只保留前5条
            "detection_method": detection_method,
        },
    }


def _evaluate_structural_integrity(report: dict, config: dict) -> dict:
    """评估结构完整性：报告是否包含所有必需章节"""
    min_coverage = config.get("min_section_coverage", 1.0)
    weight = config.get("weight", 1.0)

    present_sections = []
    missing_sections = []

    for section in REQUIRED_SECTIONS:
        # 检查多种可能的键名
        keys_to_check = [section, section.replace("_", "-"), section.replace("-", "_")]
        found = any(report.get(k) is not None for k in keys_to_check)
        if found:
            present_sections.append(section)
        else:
            missing_sections.append(section)

    coverage = len(present_sections) / len(REQUIRED_SECTIONS)
    score = 5 if coverage >= min_coverage else (3 if coverage >= 0.8 else 1)

    return {
        "name": "结构完整性 (Structural Integrity)",
        "key": "structural_integrity",
        "score": score,
        "threshold": min_coverage * 5,
        "value": round(coverage, 3),
        "passed": coverage >= min_coverage,
        "weight": weight,
        "details": {
            "present_sections": present_sections,
            "missing_sections": missing_sections,
            "coverage": round(coverage, 3),
        },
    }


def _evaluate_calibration_honesty(report: dict, config: dict) -> dict:
    """评估校准诚实度：研究发现是否正确标注为假设而非事实"""
    min_annotation = config.get("min_annotation_ratio", 1.0)
    weight = config.get("weight", 1.2)

    persona_reviews = report.get("persona_reviews", [])
    total_findings = 0
    annotated_findings = 0

    # 检查是否有 AI 生成声明
    has_ai_disclaimer = bool(report.get("ai_disclaimer") or report.get("disclaimer"))

    for review in persona_reviews:
        key_issues = review.get("key_issues", [])
        for issue in key_issues:
            total_findings += 1
            # 检查是否有推理级别标注
            has_level = bool(issue.get("inference_level") or issue.get("evidence_level"))
            has_caveat = bool(issue.get("caveat") or issue.get("limitation"))
            if has_level or has_caveat:
                annotated_findings += 1

    annotation_ratio = annotated_findings / total_findings if total_findings > 0 else 1.0

    # 如果没有 AI 声明，扣分
    if not has_ai_disclaimer:
        annotation_ratio *= 0.5

    score = _score_from_ratio(annotation_ratio, min_annotation)

    return {
        "name": "校准诚实度 (Calibration Honesty)",
        "key": "calibration_honesty",
        "score": score,
        "threshold": min_annotation * 5,
        "value": round(annotation_ratio, 3),
        "passed": score >= 4 and has_ai_disclaimer,
        "weight": weight,
        "details": {
            "annotation_ratio": round(annotation_ratio, 3),
            "has_ai_disclaimer": has_ai_disclaimer,
            "total_findings": total_findings,
            "annotated_findings": annotated_findings,
        },
    }


def _evaluate_risk_detection(report: dict, config: dict) -> dict:
    """评估风险检测：是否识别了关键风险"""
    min_critical = config.get("min_critical_issues", 1)
    weight = config.get("weight", 1.0)

    persona_reviews = report.get("persona_reviews", [])
    critical_issues = []
    high_issues = []

    for review in persona_reviews:
        for issue in review.get("key_issues", []):
            severity = issue.get("severity", "").lower()
            if severity in ("critical", "关键", "严重"):
                critical_issues.append(issue.get("title", ""))
            elif severity in ("high", "高", "重要"):
                high_issues.append(issue.get("title", ""))

    total_risks = len(critical_issues) + len(high_issues)
    detected = len(critical_issues) >= min_critical or total_risks >= 2

    if len(critical_issues) >= 2:
        score = 5
    elif len(critical_issues) >= 1:
        score = 4
    elif total_risks >= 2:
        score = 3
    elif total_risks >= 1:
        score = 2
    else:
        score = 1

    return {
        "name": "风险检测 (Risk Detection)",
        "key": "risk_detection",
        "score": score,
        "threshold": min_critical,
        "value": total_risks,
        "passed": detected,
        "weight": weight,
        "details": {
            "critical_count": len(critical_issues),
            "high_count": len(high_issues),
            "critical_issues": critical_issues[:3],
            "high_issues": high_issues[:3],
        },
    }


def _evaluate_segment_conflict(report: dict, config: dict) -> dict:
    """评估细分冲突：人物细分之间是否存在有意义的分歧"""
    min_disagreements = config.get("min_disagreements", 2)
    weight = config.get("weight", 1.0)

    # 从交叉质询或主要分歧中提取
    disagreements = []

    # 优先从 cross_examination 字段提取
    cross_exam = report.get("cross_examination", {})
    if cross_exam:
        controversy_points = cross_exam.get("controversy_points", [])
        for cp in controversy_points:
            disagreements.append({
                "topic": cp.get("topic", cp.get("issue", "")),
                "severity": cp.get("severity", "medium"),
            })

    # 从 major_disagreements 字段提取
    major_disagreements = report.get("major_disagreements", [])
    if major_disagreements:
        for md in major_disagreements:
            disagreements.append({
                "topic": md.get("topic", md.get("issue", "")),
                "severity": md.get("severity", "high"),
            })

    # 从 persona_reviews 的立场差异推断
    if not disagreements:
        persona_reviews = report.get("persona_reviews", [])
        stances = {}
        for review in persona_reviews:
            stance = review.get("primary_stance", review.get("stance", ""))
            if stance:
                stances.setdefault(stance, []).append(review.get("persona_id", ""))

        if len(stances) >= 2:
            for stance, personas in stances.items():
                if len(personas) >= 1:
                    disagreements.append({"topic": f"立场分歧: {stance}", "severity": "medium"})

    meaningful = [d for d in disagreements if d.get("severity", "") in ("high", "critical", "关键", "严重", "高")]
    if not meaningful:
        meaningful = disagreements

    count = len(meaningful)
    passed = count >= min_disagreements

    if count >= 4:
        score = 5
    elif count >= 3:
        score = 4
    elif count >= 2:
        score = 4
    elif count >= 1:
        score = 2
    else:
        score = 1

    return {
        "name": "细分冲突 (Segment Conflict)",
        "key": "segment_conflict",
        "score": score,
        "threshold": min_disagreements,
        "value": count,
        "passed": passed,
        "weight": weight,
        "details": {
            "meaningful_disagreements": count,
            "total_disagreements": len(disagreements),
            "disagreement_topics": [d.get("topic", "") for d in disagreements[:5]],
        },
    }
