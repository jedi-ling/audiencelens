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

try:
    from .similarity import get_issue_similarity
except ImportError:
    try:
        from runner.similarity import get_issue_similarity
    except ImportError:
        get_issue_similarity = None


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

# 必需的报告章节。键名以**引擎实际产出的键**为准（src/runner/aggregator.py 的
# aggregate_report 返回值），别名只是为了兼容外部/历史报告。
#
# 历史成因：这里原来写死 "next_human_test_recommendations"，而引擎产出的是
# "next_human_test"——于是任何一份引擎自己产的报告，结构完整性都恒定缺一节
# （coverage=0.8 → score 3），overall 永远差那一口气。这类"评估器和被评估对象
# 各说各的键名"是本仓库反复出现的形状，所以现在统一走别名表，改键名时两边一起改。
SECTION_ALIASES = {
    "consensus": ("consensus",),
    "major_disagreements": ("major_disagreements",),
    "priority_fixes": ("priority_fixes",),
    "information_gaps": ("information_gaps",),
    "next_human_test": ("next_human_test", "next_human_test_recommendations"),
}
REQUIRED_SECTIONS = list(SECTION_ALIASES)

# 人格逐条评审在报告里的位置，按优先级依次尝试：
#   persona_reviews  —— run_panel 写进报告的对外键（自 0.4.0 起）
#   _persona_outputs —— run_panel 渲染 HTML 时的临时键（内存中的报告可能还带着它）
# 都没有时退化到 persona_notes（aggregator 的摘要视图），但那份是**有损**的：
# 只有 issue 标题和证据正文，没有 severity / suggested_fix / inference_level，
# 于是可操作性、输入依据、校准诚实度三个维度会退化成"无法评估"而不是"0 分"。
PERSONA_REVIEW_KEYS = ("persona_reviews", "_persona_outputs")

# 刻板印象禁止模式
STEREOTYPE_PATTERNS = [
    re.compile(r"作为[一名个]?[男女女性男性].*?(?:所以|因此|更|偏好|倾向)", re.IGNORECASE),
    re.compile(r"(?:她|他|她们|他们)(?:天生|天然|本能地).*(?:偏好|喜欢|选择)", re.IGNORECASE),
    re.compile(r"(?:这个|那)(?:年龄|年代|岁数)(?:段|的)(?:人|玩家|用户).*(?:通常|一般|都|总是)", re.IGNORECASE),
    re.compile(r"(?:作为|身为)[A-Z]{4}.*?(?:所以|因此|决定|判断)", re.IGNORECASE),
    re.compile(r"(?:women|men|female|male)\s+(?:prefer|tend\s+to|naturally|instinctively)", re.IGNORECASE),
    re.compile(r"(?:as\s+a\s+)?(?:woman|man|girl|boy|elderly|young)\s+.*?(?:therefore|so|prefer|tend)", re.IGNORECASE),
]


def _reviews_from_persona_notes(notes: List[dict]) -> List[dict]:
    """把 aggregator 的 persona_notes 摘要还原成评估器认的形状（有损）。

    persona_notes 只留了 evidence 正文和 issue 标题，severity / suggested_fix /
    inference_level 全部丢失——所以这里**不伪造**这些字段（比如给个默认 severity），
    宁可让依赖它们的维度判成"无法评估"。伪造出来的分数比没有分数更危险。
    """
    reviews = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        reviews.append({
            "persona_id": note.get("persona_id", ""),
            "persona_name": note.get("persona_name", ""),
            "primary_stance": note.get("stance", ""),
            "evidence": [
                {"content": c} for c in (note.get("evidence_top3") or []) if isinstance(c, str)
            ],
            "key_issues": [
                {"title": t} for t in (note.get("top_issues") or []) if isinstance(t, str)
            ],
        })
    return reviews


def extract_persona_reviews(report: dict) -> tuple:
    """返回 (人格逐条评审列表, 数据来源标记)。

    评估器过去只认 report["persona_reviews"]，而引擎产的报告里根本没有这个键，
    于是 5 个维度恒定拿到空列表——分数是"永远 1 分"和"因为没数据所以满分"两种假象。
    这里做一次形状适配，并把来源如实带出去，让读报告的人知道这次评的是全量数据
    还是有损摘要。
    """
    for key in PERSONA_REVIEW_KEYS:
        value = report.get(key)
        if isinstance(value, list) and value:
            return [r for r in value if isinstance(r, dict)], key

    notes = report.get("persona_notes")
    if isinstance(notes, list) and notes:
        return _reviews_from_persona_notes(notes), "persona_notes"

    return [], "none"


def _unevaluable(name: str, key: str, weight: float, threshold: float, reason: str) -> dict:
    """输入数据缺失时的维度结果：分数 0、明确标 evaluable=False、名字里带"无法评估"。

    为什么不复用"最低分 1 分"或"满分通过"：这两种都在拿分数冒充结论。
    刻板印象检查曾经因为输入是空列表而恒定 5 分通过——"没有可检查的文本"
    被当成"检查通过了"，这正是最需要杜绝的静默假阳性。
    名字里带标记是因为 src/cli.py 的结果表只打印 name/score/threshold/passed，
    不带的话"无法评估"在终端上和普通 FAIL 长得一模一样。
    """
    return {
        "name": f"{name}（无法评估）",
        "key": key,
        "score": 0,
        "threshold": threshold,
        "value": None,
        "passed": False,
        "evaluable": False,
        "weight": weight,
        "details": {"reason": reason},
    }


def evaluate_report(report: dict, thresholds: Optional[dict] = None) -> dict:
    """
    对合成评审报告执行8维 Harness 评估。

    Args:
        report: 合成评审报告的 JSON dict。人格逐条评审按 extract_persona_reviews
            的优先级读取（persona_reviews / _persona_outputs / persona_notes），
            章节键名按 SECTION_ALIASES 兼容。
        thresholds: 自定义阈值配置，None 则使用默认值

    Returns:
        包含8维评估结果的 dict。unevaluable_dimensions 非空时 overall_passed 必为
        False——缺数据不等于合格。
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    persona_reviews, reviews_source = extract_persona_reviews(report)

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

    # 综合得分只对"评得动"的维度求加权平均——把"无法评估"的 0 分算进平均
    # 会把缺数据说成"质量差"，两回事。但整体结论不能因此变好看：只要有一个维度
    # 无法评估，overall_passed 一律 False（见下）。
    evaluable = [d for d in dimensions if d.get("evaluable", True)]
    unevaluable_keys = [d["key"] for d in dimensions if not d.get("evaluable", True)]

    total_weight = sum(d["weight"] for d in evaluable)
    weighted_sum = sum(d["score"] * d["weight"] for d in evaluable)
    overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    # 整体通过条件：8 个维度全都评得动、每个 ≥ 2 且加权平均 ≥ 3.0
    all_above_min = all(d["score"] >= 2 for d in evaluable)
    overall_passed = not unevaluable_keys and all_above_min and overall_score >= 3.0

    return {
        "dimensions": dimensions,
        "overall_score": round(overall_score, 2),
        "overall_passed": overall_passed,
        # 这次评估到底吃到了什么数据：persona_reviews（全量）/ persona_notes（有损摘要）
        # / none（没有人格数据）。不透出来的话，一份"因为报告里没有人格数据所以低分"
        # 的评估结果会被误读成"这次评审质量差"。
        "persona_reviews_source": reviews_source,
        "persona_reviews_count": len(persona_reviews),
        "unevaluable_dimensions": unevaluable_keys,
        "version": "0.4.0",
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

    persona_reviews, source = extract_persona_reviews(report)
    total_issues = 0
    actionable_issues = 0
    issues_with_fix_field = 0

    for review in persona_reviews:
        key_issues = review.get("key_issues", [])
        for issue in key_issues:
            total_issues += 1
            fix = issue.get("suggested_fix", "")
            if "suggested_fix" in issue:
                issues_with_fix_field += 1
            # 检查建议是否包含具体步骤（包含动词+名词模式）
            has_what = len(fix) > 10
            has_how = any(kw in fix for kw in ["添加", "修改", "删除", "增加", "减少", "调整", "优化",
                                                "add", "remove", "change", "modify", "increase", "decrease",
                                                "简化", "突出", "强化", "移除", "替换", "重构"])
            if has_what and has_how:
                actionable_issues += 1

    if total_issues == 0:
        return _unevaluable(
            "可操作性 (Actionability)", "actionability", weight, min_ratio * 5,
            f"报告里没有任何人格议题可评（人格数据来源：{source}）",
        )
    if issues_with_fix_field == 0:
        # 有议题但整批都没有 suggested_fix 字段：多半是从 persona_notes 这类
        # 有损摘要还原出来的，此时算出的 0% 不是"建议都不可操作"，而是"没数据"。
        return _unevaluable(
            "可操作性 (Actionability)", "actionability", weight, min_ratio * 5,
            f"人格议题里不含 suggested_fix 字段，无法判断可操作性（数据来源：{source}）",
        )

    ratio = actionable_issues / total_issues
    score = _score_from_ratio(ratio, min_ratio)

    return {
        "name": "可操作性 (Actionability)",
        "key": "actionability",
        "score": score,
        "threshold": min_ratio * 5,  # 归一化到5分制显示
        "value": round(ratio, 3),
        "passed": score >= 4,
        "evaluable": True,
        "weight": weight,
        "details": {
            "total_issues": total_issues,
            "actionable_issues": actionable_issues,
            "ratio": round(ratio, 3),
            "source": source,
        },
    }


def _evaluate_input_grounding(report: dict, config: dict) -> dict:
    """评估输入依据：论证是否引用了输入材料的具体细节"""
    min_citation = config.get("min_citation_ratio", 0.80)
    min_direct = config.get("min_direct_ratio", 0.60)
    weight = config.get("weight", 1.0)

    persona_reviews, source = extract_persona_reviews(report)
    total_claims = 0
    cited_claims = 0
    total_evidence = 0
    direct_evidence = 0
    evidence_with_level = 0

    for review in persona_reviews:
        evidence_list = review.get("evidence", [])
        for ev in evidence_list:
            total_evidence += 1
            level = ev.get("inference_level", ev.get("level", ""))
            if "inference_level" in ev or "level" in ev:
                evidence_with_level += 1
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

    threshold = (min_citation + min_direct) / 2 * 5
    if total_claims == 0 and total_evidence == 0:
        return _unevaluable(
            "输入依据 (Input Grounding)", "input_grounding", weight, threshold,
            f"报告里没有任何证据或议题可评（人格数据来源：{source}）",
        )
    if total_evidence > 0 and evidence_with_level == 0:
        # 证据条目在，但一条都没带 inference_level：direct_ratio 会恒 0，
        # 那是"字段没被带出来"，不是"没有一条直接证据"。
        return _unevaluable(
            "输入依据 (Input Grounding)", "input_grounding", weight, threshold,
            f"证据条目不含 inference_level 字段，无法区分直接引用与推断（数据来源：{source}）",
        )

    citation_ratio = cited_claims / total_claims if total_claims > 0 else 0.0
    direct_ratio = direct_evidence / total_evidence if total_evidence > 0 else 0.0

    # 综合两个子指标
    avg_ratio = (citation_ratio + direct_ratio) / 2
    score = _score_from_ratio(avg_ratio, (min_citation + min_direct) / 2)

    return {
        "name": "输入依据 (Input Grounding)",
        "key": "input_grounding",
        "score": score,
        "threshold": threshold,
        "value": round(avg_ratio, 3),
        "passed": score >= 4,
        "evaluable": True,
        "weight": weight,
        "details": {
            "citation_ratio": round(citation_ratio, 3),
            "direct_ratio": round(direct_ratio, 3),
            "total_claims": total_claims,
            "total_evidence": total_evidence,
            "source": source,
        },
    }


def _evaluate_persona_differentiation(report: dict, config: dict) -> dict:
    """评估人物差异化：不同人物是否产生了真正不同的视角"""
    min_jaccard = config.get("min_jaccard", 0.30)
    weight = config.get("weight", 1.0)

    persona_reviews, source = extract_persona_reviews(report)

    if len(persona_reviews) < 2:
        return _unevaluable(
            "人物差异化 (Persona Differentiation)", "persona_differentiation",
            weight, min_jaccard * 5,
            f"需要至少 2 个人格才能计算差异化，本次只有 {len(persona_reviews)} 个"
            f"（人格数据来源：{source}）",
        )

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

    # 语义分化度：使用 embedding 计算议题向量间的余弦距离
    semantic_distance = None
    if get_issue_similarity is not None:
        sim = get_issue_similarity()
        if sim.method == "semantic":
            # 为每个 persona 构建议题文本向量（取所有 issue title 拼接）
            persona_issue_texts = []
            for review in persona_reviews:
                titles = [issue.get("title", "") for issue in review.get("key_issues", []) if issue.get("title")]
                persona_issue_texts.append(" ".join(titles))

            if len(persona_issue_texts) >= 2:
                sem_distances = []
                for i in range(len(persona_issue_texts)):
                    for j in range(i + 1, len(persona_issue_texts)):
                        if persona_issue_texts[i] and persona_issue_texts[j]:
                            d = 1.0 - sim.similarity(persona_issue_texts[i], persona_issue_texts[j])
                            sem_distances.append(d)
                if sem_distances:
                    semantic_distance = sum(sem_distances) / len(sem_distances)

    details = {
        "mean_jaccard_distance": round(mean_distance, 3),
        "num_pairs": len(distances),
        "min_distance": round(min(distances), 3) if distances else 0,
        "max_distance": round(max(distances), 3) if distances else 0,
        "source": source,
    }
    if semantic_distance is not None:
        details["semantic_distance"] = round(semantic_distance, 3)
        details["dedup_method"] = "semantic"
    else:
        details["dedup_method"] = "lexical"

    return {
        "name": "人物差异化 (Persona Differentiation)",
        "key": "persona_differentiation",
        "score": score,
        "threshold": min_jaccard * 5,
        "value": round(mean_distance, 3),
        "passed": score >= 4,
        "evaluable": True,
        "weight": weight,
        "details": details,
    }


def _evaluate_stereotype_check(report: dict, config: dict) -> dict:
    """评估刻板印象检查：判断是否基于行为画像而非人口统计学特征"""
    max_violations = config.get("max_violations", 0)
    weight = config.get("weight", 1.5)

    use_llm = config.get("use_llm", False)
    violations = []
    detection_method = "regex"
    persona_reviews, source = extract_persona_reviews(report)
    checked_text_count = 0

    for review in persona_reviews:
        persona_id = review.get("persona_id", "unknown")

        # 检查所有文本字段
        text_fields = []
        for issue in review.get("key_issues", []):
            for field in ["title", "why_it_matters", "suggested_fix"]:
                text_fields.append(issue.get(field, ""))
        for ev in review.get("evidence", []):
            text_fields.append(ev.get("content", ""))

        checked_text_count += sum(1 for t in text_fields if t and t.strip())
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

    # 没有一个字的可检文本时**绝不能判通过**。
    # 这是本维度最严重的历史缺陷：报告里根本没有 persona_reviews（键名对不上），
    # 每轮循环都不执行，violation_count=0 → passed=True → 满分 5 分，
    # 权重还是最高的 1.5。也就是说"完全没检查"被记成"检查得最好的一项"。
    # 空输入的正确结论是「无法评估」，不是「合规」。
    if checked_text_count == 0:
        return _unevaluable(
            "刻板印象检查 (Stereotype Check)", "stereotype_check", weight, max_violations,
            f"没有任何可检文本（人格数据来源：{source}），未做检查——不等于没有违规",
        )

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
        "evaluable": True,
        "weight": weight,
        "details": {
            "violation_count": violation_count,
            "violations": violations[:5],  # 只保留前5条
            "detection_method": detection_method,
            "checked_text_count": checked_text_count,
            "source": source,
        },
    }


def _evaluate_structural_integrity(report: dict, config: dict) -> dict:
    """评估结构完整性：报告是否包含所有必需章节"""
    min_coverage = config.get("min_section_coverage", 1.0)
    weight = config.get("weight", 1.0)

    present_sections = []
    missing_sections = []

    for section in REQUIRED_SECTIONS:
        # 检查多种可能的键名：别名表 + 连字符/下划线两种写法
        keys_to_check = set()
        for alias in SECTION_ALIASES[section]:
            keys_to_check.add(alias)
            keys_to_check.add(alias.replace("_", "-"))
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
        "evaluable": True,
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

    persona_reviews, source = extract_persona_reviews(report)
    total_findings = 0
    annotated_findings = 0

    # 检查是否有 AI 生成声明。引擎报告的声明落在 meta.is_synthetic
    # （aggregator 恒写 True），旧口径只认顶层 ai_disclaimer/disclaimer——
    # 于是引擎自产报告永远被判"没有 AI 声明"，比率再乘 0.5，恒定不及格。
    meta = report.get("meta") or {}
    has_ai_disclaimer = bool(
        report.get("ai_disclaimer")
        or report.get("disclaimer")
        or (isinstance(meta, dict) and meta.get("is_synthetic"))
    )

    # 「发现」的计量单位为什么是 evidence 而不是 key_issues：
    # src/schemas/output-schema.json 里 key_issues 的 items 是
    # additionalProperties:false，字段只有 severity/title/why_it_matters/suggested_fix，
    # 结构上**不可能**带 inference_level 或 caveat。旧口径按 issue 数 inference_level 数，
    # 于是这个维度对任何合法输出都恒定 0%——测的不是校准诚实度，是 schema 的形状。
    # evidence 才是这套 schema 里承载校准的地方：inference_level 是必填枚举
    # （direct/inferred/gap），inferred 还应给 inference_basis。
    # key_issues 上的标注字段仍然认（外部报告/旧数据可能带），只是不再当分母主体。
    valid_levels = {"direct", "inferred", "gap"}
    unbased_inferred = 0
    for review in persona_reviews:
        for ev in review.get("evidence", []) or []:
            if not isinstance(ev, dict):
                continue
            total_findings += 1
            level = ev.get("inference_level", ev.get("level", ""))
            if level in valid_levels:
                annotated_findings += 1
            if level == "inferred" and not (ev.get("inference_basis") or "").strip():
                unbased_inferred += 1

        for issue in review.get("key_issues", []) or []:
            if not isinstance(issue, dict):
                continue
            has_level = bool(issue.get("inference_level") or issue.get("evidence_level"))
            has_caveat = bool(issue.get("caveat") or issue.get("limitation"))
            # 只有当 issue 真带标注字段时才计入——否则等于用一批结构上不可能
            # 带标注的条目去稀释分母
            if has_level or has_caveat:
                total_findings += 1
                annotated_findings += 1

    if total_findings == 0:
        return _unevaluable(
            "校准诚实度 (Calibration Honesty)", "calibration_honesty",
            weight, min_annotation * 5,
            f"报告里没有任何带推理层级的证据条目可评（人格数据来源：{source}）",
        )

    annotation_ratio = annotated_findings / total_findings

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
        "evaluable": True,
        "weight": weight,
        "details": {
            "annotation_ratio": round(annotation_ratio, 3),
            "has_ai_disclaimer": has_ai_disclaimer,
            "total_findings": total_findings,
            "annotated_findings": annotated_findings,
            # inferred 却没写推理依据的条目：不直接扣分（schema 里 inference_basis
            # 是"建议填写"不是必填），但必须让读报告的人看见
            "inferred_without_basis": unbased_inferred,
            "source": source,
        },
    }


def _evaluate_risk_detection(report: dict, config: dict) -> dict:
    """评估风险检测：是否识别了关键风险"""
    min_critical = config.get("min_critical_issues", 1)
    weight = config.get("weight", 1.0)

    persona_reviews, source = extract_persona_reviews(report)
    critical_issues = []
    high_issues = []
    total_issues = 0
    issues_with_severity = 0

    for review in persona_reviews:
        for issue in review.get("key_issues", []):
            total_issues += 1
            if issue.get("severity"):
                issues_with_severity += 1
            severity = issue.get("severity", "").lower()
            if severity in ("critical", "关键", "严重"):
                critical_issues.append(issue.get("title", ""))
            elif severity in ("high", "高", "重要"):
                high_issues.append(issue.get("title", ""))

    if total_issues == 0:
        return _unevaluable(
            "风险检测 (Risk Detection)", "risk_detection", weight, min_critical,
            f"报告里没有任何人格议题可评（人格数据来源：{source}）",
        )
    if issues_with_severity == 0:
        # 有议题但全没 severity：算出来的"0 个高危"是字段缺失，不是真没风险
        return _unevaluable(
            "风险检测 (Risk Detection)", "risk_detection", weight, min_critical,
            f"人格议题不含 severity 字段，无法判断风险等级（数据来源：{source}）",
        )

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
        "evaluable": True,
        "weight": weight,
        "details": {
            "critical_count": len(critical_issues),
            "high_count": len(high_issues),
            "critical_issues": critical_issues[:3],
            "high_issues": high_issues[:3],
            "total_issues": total_issues,
            "source": source,
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

    persona_reviews, source = extract_persona_reviews(report)

    # 从 persona_reviews 的立场差异推断
    if not disagreements:
        stances = {}
        for review in persona_reviews:
            stance = review.get("primary_stance", review.get("stance", ""))
            if stance:
                stances.setdefault(stance, []).append(review.get("persona_id", ""))

        if len(stances) >= 2:
            for stance, personas in stances.items():
                if len(personas) >= 1:
                    disagreements.append({"topic": f"立场分歧: {stance}", "severity": "medium"})

    # 三条来源（交叉质询 / major_disagreements / 人格立场）**全都没有数据**时才判
    # 无法评估。只要报告里有 major_disagreements 这一节（哪怕是空列表）且有人格立场
    # 可比，"没有分歧"就是一个真实结论，该给低分而不是判无法评估。
    if not disagreements and not persona_reviews and "major_disagreements" not in report:
        return _unevaluable(
            "细分冲突 (Segment Conflict)", "segment_conflict", weight, min_disagreements,
            f"报告里既无分歧章节也无人格立场可比（人格数据来源：{source}）",
        )

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
        "evaluable": True,
        "weight": weight,
        "details": {
            "meaningful_disagreements": count,
            "total_disagreements": len(disagreements),
            "disagreement_topics": [d.get("topic", "") for d in disagreements[:5]],
            "source": source,
        },
    }
