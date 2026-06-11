"""
证据三级标注自动检测器

检测合成评审输出中的证据标注级别：
- [direct]: 在输入材料中明确存在
- [inferred: basis]: 从材料 + 人物先验知识合理推断
- [gap]: 无可用证据，必须标注为"未指定"
"""

import re
from typing import Dict, List, Optional, Tuple


# 证据级别标注模式
EVIDENCE_PATTERNS = {
    "direct": [
        re.compile(r"\[direct\]", re.IGNORECASE),
        re.compile(r"直接证据[：:]", re.IGNORECASE),
        re.compile(r"材料中(?:明确|直接)(?:提到|指出|说明|显示)", re.IGNORECASE),
        re.compile(r"explicitly\s+(?:mentioned|stated|shown)\s+in", re.IGNORECASE),
    ],
    "inferred": [
        re.compile(r"\[inferred[:\s]", re.IGNORECASE),
        re.compile(r"推断证据[：:]", re.IGNORECASE),
        re.compile(r"可以(?:推断|推测|合理假设)", re.IGNORECASE),
        re.compile(r"(?:likely|probably|presumably)\s+(?:based|inferred)", re.IGNORECASE),
    ],
    "gap": [
        re.compile(r"\[gap\]", re.IGNORECASE),
        re.compile(r"(?:信息|证据)(?:缺口|空白|缺失)", re.IGNORECASE),
        re.compile(r"(?:未提供|无法确定|没有)(?:足够|相关|直接)(?:信息|证据|数据)", re.IGNORECASE),
        re.compile(r"(?:no|insufficient|lack\s+of)\s+(?:evidence|data|information)", re.IGNORECASE),
    ],
}

# 填补空白禁止模式（检测编造信息）
FABRICATION_PATTERNS = [
    re.compile(r"(?:我|笔者|本人)(?:亲自|实际)(?:体验|试玩|使用)了", re.IGNORECASE),
    re.compile(r"(?:根据|基于)(?:我的|本人的)(?:实际|真实)(?:经验|体验)", re.IGNORECASE),
    re.compile(r"I\s+(?:actually|personally|really)\s+(?:played|used|tried)", re.IGNORECASE),
]


def detect_evidence_levels(text: str) -> Dict[str, List[str]]:
    """
    检测文本中的证据级别标注。

    Args:
        text: 要检测的文本

    Returns:
        按级别分类的匹配列表
    """
    results = {"direct": [], "inferred": [], "gap": [], "unlabeled": []}

    # 按句子分割
    sentences = re.split(r'[。！？\n]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    for sentence in sentences:
        labeled = False
        for level, patterns in EVIDENCE_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(sentence):
                    results[level].append(sentence[:100])
                    labeled = True
                    break
            if labeled:
                break
        if not labeled:
            # 检查是否包含主张但未标注
            claim_indicators = ["建议", "应该", "需要", "问题", "风险", "优点", "缺点",
                              "should", "recommend", "issue", "risk", "problem"]
            if any(ind in sentence.lower() for ind in claim_indicators):
                results["unlabeled"].append(sentence[:100])

    return results


def detect_fabrication(text: str) -> List[str]:
    """
    检测文本中是否存在编造信息（填补空白）。

    Args:
        text: 要检测的文本

    Returns:
        检测到的编造模式列表
    """
    violations = []
    for pattern in FABRICATION_PATTERNS:
        matches = pattern.findall(text)
        violations.extend(matches)
    return violations


def compute_evidence_stats(report: dict) -> dict:
    """
    计算报告中所有人物评审的证据统计。

    Args:
        report: 合成评审报告

    Returns:
        证据统计数据
    """
    persona_reviews = report.get("persona_reviews", [])

    total_evidence = 0
    direct_count = 0
    inferred_count = 0
    gap_count = 0
    unlabeled_count = 0
    fabrication_count = 0

    for review in persona_reviews:
        # 从结构化 evidence 字段统计
        evidence_list = review.get("evidence", [])
        for ev in evidence_list:
            total_evidence += 1
            level = ev.get("inference_level", ev.get("level", "")).lower()
            if level == "direct":
                direct_count += 1
            elif level == "inferred":
                inferred_count += 1
            elif level == "gap":
                gap_count += 1
            else:
                unlabeled_count += 1

        # 从文本中检测未标注的证据
        all_text = ""
        for issue in review.get("key_issues", []):
            all_text += " " + issue.get("why_it_matters", "") + " " + issue.get("suggested_fix", "")

        if all_text.strip():
            detected = detect_evidence_levels(all_text)
            unlabeled_count += len(detected["unlabeled"])

            fabrications = detect_fabrication(all_text)
            fabrication_count += len(fabrications)

    direct_ratio = direct_count / total_evidence if total_evidence > 0 else 0.0
    inferred_ratio = inferred_count / total_evidence if total_evidence > 0 else 0.0
    gap_ratio = gap_count / total_evidence if total_evidence > 0 else 0.0

    return {
        "total_evidence": total_evidence,
        "direct": direct_count,
        "inferred": inferred_count,
        "gap": gap_count,
        "unlabeled": unlabeled_count,
        "fabrication_count": fabrication_count,
        "direct_ratio": round(direct_ratio, 3),
        "inferred_ratio": round(inferred_ratio, 3),
        "gap_ratio": round(gap_ratio, 3),
        "inferred_within_limit": inferred_ratio <= 0.4,
        "no_fabrication": fabrication_count == 0,
    }
