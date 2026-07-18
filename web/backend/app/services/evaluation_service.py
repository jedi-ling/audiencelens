import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EvaluationResult, EvaluationScorecard, Review

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
HARNESS_DIR = os.path.join(PROJECT_ROOT, "audiencelens-v0.2-harness", "harness")
EVALUATORS_DIR = os.path.join(HARNESS_DIR, "evaluators")
RUBRICS_DIR = os.path.join(HARNESS_DIR, "rubrics")

RUBRIC_DIMENSIONS = [
    "persona_differentiation",
    "input_grounding",
    "actionability",
    "segment_conflict",
    "risk_detection",
    "ethical_persona_use",
    "report_structure",
    "calibration_honesty",
]

RUBRIC_SCORES = {
    "persona_differentiation": {
        "0": "personas sound identical",
        "1": "minor wording differences only",
        "2": "clear perspective differences",
        "3": "behavior-grounded, stable differences tied to persona rules",
    },
    "input_grounding": {
        "0": "generic advice",
        "1": "mentions project name only",
        "2": "references concrete input details",
        "3": "consistently uses input evidence and avoids unsupported claims",
    },
    "actionability": {
        "0": "no concrete actions",
        "1": "vague actions",
        "2": "concrete fixes exist",
        "3": "P0/P1/P2 actions are specific and prioritized",
    },
    "segment_conflict": {
        "0": "no disagreements",
        "1": "shallow disagreement",
        "2": "meaningful segment conflicts",
        "3": "conflicts inform product/design decisions",
    },
    "risk_detection": {
        "0": "no risks",
        "1": "generic risks",
        "2": "clear blockers and objections",
        "3": "strong rejection reasons and segment-specific risks",
    },
    "ethical_persona_use": {
        "0": "uses stereotypes",
        "1": "risky demographic/MBTI assumptions",
        "2": "mostly behavior-based",
        "3": "explicitly treats demographic/MBTI fields as weak modifiers",
    },
    "report_structure": {
        "0": "missing most required sections",
        "1": "has some required sections",
        "2": "has most required sections",
        "3": "has all required sections with proper content",
    },
    "calibration_honesty": {
        "0": "claims to predict success",
        "1": "overconfident language",
        "2": "mostly honest",
        "3": "frames findings as hypotheses and recommends real validation",
    },
}

CRITICAL_FAILURES = [
    "lacks disclaimer",
    "has no P0/P1/P2 actions",
    "uses stereotypes",
    "is not grounded in input",
    "claims real-world success prediction",
]

REQUIRED_SECTIONS = [
    "Disclaimer",
    "Executive Verdict",
    "Assumption Summary",
    "Persona Reviews",
    "Consensus",
    "Disagreements",
    "Priority Actions",
    "Real Validation Questions",
    "Harness Self-Check",
]


class EvaluationService:
    _evaluators_cache: Dict[str, str] = {}
    _rubric_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def load_evaluators(cls) -> Dict[str, str]:
        """从 harness/evaluators/ 加载评估器 .md 文件"""
        if cls._evaluators_cache:
            return cls._evaluators_cache
        if not os.path.isdir(EVALUATORS_DIR):
            return {}
        for fname in os.listdir(EVALUATORS_DIR):
            if fname.endswith(".md"):
                dimension = os.path.splitext(fname)[0]
                path = os.path.join(EVALUATORS_DIR, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cls._evaluators_cache[dimension] = f.read()
                except Exception:
                    pass
        return cls._evaluators_cache

    @classmethod
    def load_rubrics(cls) -> Dict[str, Any]:
        """从 harness/rubrics/ 加载评分标准"""
        if cls._rubric_cache is not None:
            return cls._rubric_cache
        cls._rubric_cache = {"dimensions": RUBRIC_SCORES, "critical_failures": CRITICAL_FAILURES}
        if not os.path.isdir(RUBRICS_DIR):
            return cls._rubric_cache
        for fname in os.listdir(RUBRICS_DIR):
            if fname.endswith(".md"):
                path = os.path.join(RUBRICS_DIR, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    parsed = cls._parse_rubric_md(content)
                    if parsed:
                        cls._rubric_cache.update(parsed)
                except Exception:
                    pass
        return cls._rubric_cache

    @classmethod
    def _parse_rubric_md(cls, content: str) -> Optional[Dict[str, Any]]:
        """解析评分标准 markdown 文件"""
        dimensions = {}
        current_dim = None
        for line in content.split("\n"):
            dim_match = re.match(r"^##\s+(\d+)\.\s+(.+)$", line.strip())
            if dim_match:
                current_dim = dim_match.group(2).strip().lower().replace(" ", "_")
                dimensions[current_dim] = {}
                continue
            score_match = re.match(r"^(\d+)\s*=\s*(.+)$", line.strip())
            if score_match and current_dim:
                dimensions[current_dim][score_match.group(1)] = score_match.group(2).strip()
        if not dimensions:
            return None
        return {"dimensions": dimensions}

    @classmethod
    def get_rubric(cls) -> Dict[str, Any]:
        """获取8维度评分标准"""
        return cls.load_rubrics()

    @classmethod
    def run_full_evaluation(cls, session: Session, review_id: str) -> EvaluationScorecard:
        """对评审结果运行完整评估，返回评分卡"""
        review = session.get(Review, review_id)
        if review is None:
            raise ValueError(f"评审 {review_id} 不存在")

        report = review.report_json or {}
        markdown = review.report_markdown or ""
        persona_outputs = [po.output_json for po in review.persona_outputs if po.output_json]

        results = []
        critical_failures = []

        for dimension in RUBRIC_DIMENSIONS:
            result = cls.evaluate_dimension(
                dimension=dimension,
                report=report,
                markdown=markdown,
                persona_outputs=persona_outputs,
            )
            ev_result = EvaluationResult(
                id=str(uuid.uuid4()),
                review_id=review_id,
                dimension=dimension,
                score=result["score"],
                passed=result["passed"],
                details=result["details"],
                evaluated_at=datetime.now(timezone.utc),
            )
            session.add(ev_result)
            results.append(ev_result)

        for cf in CRITICAL_FAILURES:
            if cls._check_critical_failure(cf, report, markdown, persona_outputs):
                critical_failures.append(cf)

        overall_score = cls._calculate_overall_score(results)
        passed = overall_score >= 60 and len(critical_failures) == 0

        existing = session.get(EvaluationScorecard, review_id)
        if existing:
            session.delete(existing)
            session.flush()

        scorecard = EvaluationScorecard(
            review_id=review_id,
            overall_score=overall_score,
            passed=passed,
            results_json=[{"dimension": r.dimension, "score": r.score, "passed": r.passed, "details": r.details} for r in results],
            critical_failures_json=critical_failures,
        )
        session.add(scorecard)
        session.commit()
        session.refresh(scorecard)

        return scorecard

    @classmethod
    def evaluate_dimension(
        cls,
        dimension: str,
        report: Optional[Dict[str, Any]] = None,
        markdown: Optional[str] = None,
        persona_outputs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """评估单个维度，返回评分结果"""
        report = report or {}
        markdown = markdown or ""
        persona_outputs = persona_outputs or []

        evaluators = cls.load_evaluators()
        evaluator_text = evaluators.get(dimension, "")

        if dimension == "persona_differentiation":
            return cls._eval_persona_differentiation(persona_outputs, evaluator_text)
        elif dimension == "input_grounding":
            return cls._eval_input_grounding(report, persona_outputs, evaluator_text)
        elif dimension == "actionability":
            return cls._eval_actionability(report, markdown, evaluator_text)
        elif dimension == "segment_conflict":
            return cls._eval_segment_conflict(report, persona_outputs, evaluator_text)
        elif dimension == "risk_detection":
            return cls._eval_risk_detection(report, markdown, evaluator_text)
        elif dimension == "ethical_persona_use":
            return cls._eval_ethical_persona_use(persona_outputs, evaluator_text)
        elif dimension == "report_structure":
            return cls._eval_report_structure(markdown, evaluator_text)
        elif dimension == "calibration_honesty":
            return cls._eval_calibration_honesty(report, markdown, evaluator_text)
        else:
            return {"score": 0, "passed": False, "details": f"未知维度: {dimension}"}

    @classmethod
    def _eval_persona_differentiation(cls, persona_outputs: List[Dict], evaluator_text: str) -> Dict[str, Any]:
        """评估 persona 差异化程度"""
        if not persona_outputs or len(persona_outputs) < 2:
            return {"score": 0, "passed": False, "details": "persona 输出不足，无法评估差异化"}

        stances = set()
        key_phrases = set()
        for po in persona_outputs:
            stance = po.get("stance", po.get("verdict", ""))
            if stance:
                stances.add(stance.lower().strip())
            for key in po.get("key_points", po.get("findings", [])):
                if isinstance(key, str):
                    key_phrases.add(key.lower().strip()[:50])
                elif isinstance(key, dict):
                    key_phrases.add(str(key.get("point", ""))[:50].lower().strip())

        unique_ratio = len(stances) / max(len(persona_outputs), 1) if stances else 0

        if unique_ratio >= 0.6 and len(key_phrases) >= len(persona_outputs):
            score = 3
        elif unique_ratio >= 0.4 or len(key_phrases) >= len(persona_outputs) * 0.7:
            score = 2
        elif unique_ratio > 0 or len(key_phrases) > 1:
            score = 1
        else:
            score = 0

        passed = score >= 2
        return {"score": score, "passed": passed, "details": f"差异化评分: {score}/3, 立场种类: {len(stances)}, 关键点种类: {len(key_phrases)}"}

    @classmethod
    def _eval_input_grounding(cls, report: Dict, persona_outputs: List[Dict], evaluator_text: str) -> Dict[str, Any]:
        """评估输入依据程度"""
        if not report and not persona_outputs:
            return {"score": 0, "passed": False, "details": "无报告内容可评估"}

        text_to_check = ""
        if report:
            import json
            text_to_check += json.dumps(report, ensure_ascii=False)[:3000]
        for po in persona_outputs[:3]:
            import json
            text_to_check += json.dumps(po, ensure_ascii=False)[:1000]

        specific_refs = len(re.findall(r"(?:核心循环|机制|平台|类型|截图|定价|玩法|genre|mechanic|platform|screenshot|monetiz)", text_to_check, re.IGNORECASE))
        generic_refs = len(re.findall(r"(?:有潜力|不错|还可以|has potential|could be|might be)", text_to_check, re.IGNORECASE))

        if specific_refs >= 5 and generic_refs == 0:
            score = 3
        elif specific_refs >= 3:
            score = 2
        elif specific_refs >= 1:
            score = 1
        else:
            score = 0

        passed = score >= 2
        return {"score": score, "passed": passed, "details": f"具体引用: {specific_refs}, 泛泛之谈: {generic_refs}"}

    @classmethod
    def _eval_actionability(cls, report: Dict, markdown: str, evaluator_text: str) -> Dict[str, Any]:
        """评估可操作性"""
        text = markdown or ""
        if not text and report:
            import json
            text = json.dumps(report, ensure_ascii=False)

        p0_count = len(re.findall(r"P0|紧急|critical|必须修复", text, re.IGNORECASE))
        p1_count = len(re.findall(r"P1|重要|important|应该修复", text, re.IGNORECASE))
        p2_count = len(re.findall(r"P2|建议|nice.to.have|可以考虑", text, re.IGNORECASE))
        concrete_actions = len(re.findall(r"(?:替换|修改|增加|删除|调整|replace|change|add|remove|adjust|redesign)", text, re.IGNORECASE))

        total_priority = p0_count + p1_count + p2_count

        if total_priority >= 3 and concrete_actions >= 3:
            score = 3
        elif concrete_actions >= 2:
            score = 2
        elif concrete_actions >= 1 or total_priority >= 1:
            score = 1
        else:
            score = 0

        passed = score >= 2
        return {"score": score, "passed": passed, "details": f"优先级行动: P0={p0_count} P1={p1_count} P2={p2_count}, 具体操作: {concrete_actions}"}

    @classmethod
    def _eval_segment_conflict(cls, report: Dict, persona_outputs: List[Dict], evaluator_text: str) -> Dict[str, Any]:
        """评估群体冲突程度"""
        disagreements = report.get("disagreements", report.get("segment_disagreements", []))
        if isinstance(disagreements, dict):
            disagreements = list(disagreements.values()) if disagreements else []

        conflict_count = len(disagreements) if disagreements else 0

        stance_variety = set()
        for po in persona_outputs:
            stance = po.get("stance", po.get("verdict", ""))
            if stance:
                stance_variety.add(stance.lower().strip())

        if conflict_count >= 2 and len(stance_variety) >= 2:
            score = 3
        elif conflict_count >= 1 or len(stance_variety) >= 3:
            score = 2
        elif len(stance_variety) >= 2:
            score = 1
        else:
            score = 0

        passed = score >= 2
        return {"score": score, "passed": passed, "details": f"冲突点: {conflict_count}, 立场种类: {len(stance_variety)}"}

    @classmethod
    def _eval_risk_detection(cls, report: Dict, markdown: str, evaluator_text: str) -> Dict[str, Any]:
        """评估风险检测程度"""
        blockers = report.get("top_blockers", report.get("blockers", []))
        risks = report.get("risks", [])
        objections = report.get("objections", [])

        if isinstance(blockers, dict):
            blockers = list(blockers.values()) if blockers else []
        if isinstance(risks, dict):
            risks = list(risks.values()) if risks else []
        if isinstance(objections, dict):
            objections = list(objections.values()) if objections else []

        text = markdown or ""
        risk_keywords = len(re.findall(r"(?:风险|阻碍|拒绝|危险|流失|risk|blocker|objection|churn|reject)", text, re.IGNORECASE))

        total_risks = len(blockers) + len(risks) + len(objections)

        if total_risks >= 3 and risk_keywords >= 3:
            score = 3
        elif total_risks >= 2 or risk_keywords >= 2:
            score = 2
        elif total_risks >= 1 or risk_keywords >= 1:
            score = 1
        else:
            score = 0

        passed = score >= 2
        return {"score": score, "passed": passed, "details": f"风险项: {total_risks}, 风险关键词: {risk_keywords}"}

    @classmethod
    def _eval_ethical_persona_use(cls, persona_outputs: List[Dict], evaluator_text: str) -> Dict[str, Any]:
        """评估伦理 persona 使用"""
        from app.services.ethics_service import EthicsService

        violations = []
        for po in persona_outputs:
            import json
            text = json.dumps(po, ensure_ascii=False)
            stereo = EthicsService.check_stereotypes(text)
            violations.extend(stereo)

        if not violations:
            score = 3
        elif len(violations) <= 1:
            score = 2
        elif len(violations) <= 2:
            score = 1
        else:
            score = 0

        passed = score >= 2
        details = f"刻板印象违规: {len(violations)}"
        if violations:
            details += f" — {', '.join(v[:80] for v in violations[:3])}"
        return {"score": score, "passed": passed, "details": details}

    @classmethod
    def _eval_report_structure(cls, markdown: str, evaluator_text: str) -> Dict[str, Any]:
        """评估报告结构完整性"""
        if not markdown:
            return {"score": 0, "passed": False, "details": "无报告内容"}

        found = 0
        missing = []
        for section in REQUIRED_SECTIONS:
            if re.search(re.escape(section), markdown, re.IGNORECASE):
                found += 1
            else:
                missing.append(section)

        ratio = found / len(REQUIRED_SECTIONS)
        if ratio >= 0.9:
            score = 3
        elif ratio >= 0.7:
            score = 2
        elif ratio >= 0.4:
            score = 1
        else:
            score = 0

        passed = score >= 2
        details = f"找到 {found}/{len(REQUIRED_SECTIONS)} 个必要章节"
        if missing:
            details += f"，缺失: {', '.join(missing[:5])}"
        return {"score": score, "passed": passed, "details": details}

    @classmethod
    def _eval_calibration_honesty(cls, report: Dict, markdown: str, evaluator_text: str) -> Dict[str, Any]:
        """评估校准诚实度"""
        text = markdown or ""
        if not text and report:
            import json
            text = json.dumps(report, ensure_ascii=False)

        prediction_claims = len(re.findall(r"(?:预测.*成功|保证.*效果|一定会|will succeed|guaranteed|predict.*success)", text, re.IGNORECASE))
        hypothesis_claims = len(re.findall(r"(?:假设|假说|建议验证|hypothes|recommend.*validat|real.*test)", text, re.IGNORECASE))
        overconfident = len(re.findall(r"(?:肯定|绝对|毫无疑问|definitely|absolutely|certainly)", text, re.IGNORECASE))

        if prediction_claims > 0:
            score = 0
        elif overconfident >= 3:
            score = 1
        elif hypothesis_claims >= 1 and overconfident == 0:
            score = 3
        elif overconfident <= 1:
            score = 2
        else:
            score = 1

        passed = score >= 2
        return {"score": score, "passed": passed, "details": f"预测声明: {prediction_claims}, 假设措辞: {hypothesis_claims}, 过度自信: {overconfident}"}

    @classmethod
    def _check_critical_failure(
        cls, failure_type: str, report: Dict, markdown: str, persona_outputs: List[Dict]
    ) -> bool:
        """检查是否触发了关键失败条件"""
        text = markdown or ""
        if not text and report:
            import json
            text = json.dumps(report, ensure_ascii=False)

        if failure_type == "lacks disclaimer":
            return not bool(re.search(r"disclaimer|免责|声明", text, re.IGNORECASE))
        elif failure_type == "has no P0/P1/P2 actions":
            return not bool(re.search(r"P[012]", text))
        elif failure_type == "uses stereotypes":
            from app.services.ethics_service import EthicsService
            for po in persona_outputs:
                import json
                po_text = json.dumps(po, ensure_ascii=False)
                if EthicsService.check_stereotypes(po_text):
                    return True
            return False
        elif failure_type == "is not grounded in input":
            specific_refs = len(re.findall(r"(?:核心循环|机制|平台|genre|mechanic|platform)", text, re.IGNORECASE))
            return specific_refs == 0
        elif failure_type == "claims real-world success prediction":
            return bool(re.search(r"(?:预测.*成功|保证.*效果|will succeed|guaranteed)", text, re.IGNORECASE))
        return False

    @classmethod
    def _calculate_overall_score(cls, results: List[EvaluationResult]) -> int:
        """计算总体评分 (0-100)"""
        if not results:
            return 0
        total = sum(r.score for r in results)
        max_possible = len(results) * 3
        return int((total / max_possible) * 100) if max_possible > 0 else 0

    @classmethod
    def get_evaluation(cls, session: Session, review_id: str) -> Optional[EvaluationScorecard]:
        """获取评审的评估结果"""
        return session.get(EvaluationScorecard, review_id)

    @classmethod
    def get_evaluation_results(cls, session: Session, review_id: str) -> List[EvaluationResult]:
        """获取评审的各维度评估结果"""
        stmt = select(EvaluationResult).where(EvaluationResult.review_id == review_id)
        return list(session.scalars(stmt).all())
