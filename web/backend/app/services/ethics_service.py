import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EthicsReport as EthicsReportModel
from app.models import PersonaOutput

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
HARNESS_DIR = os.path.join(PROJECT_ROOT, "audiencelens-v0.2-harness", "harness")

STEREOTYPE_PATTERNS: List[Tuple[str, str, str]] = [
    (r"因为[她他].*是.*(?:女|男|女性|男性).*,.*所以", "gender_assumption", "基于性别的刻板假设"),
    (r"(?:因为|作为).*(?:INTJ|ENFP|ESFJ|ISTP|INFP|ESTJ|ENTJ|ISFJ|ESTP|INFJ|ENFJ|ISTJ|ISFP|ENTP|ESFP).*(?:只|都|必然|一定|肯定)", "mbti_determinism", "MBTI决定论"),
    (r"(?:因为|由于).*(?:年龄|年纪|岁).*(?:所以|必然|一定|肯定)", "age_assumption", "基于年龄的刻板假设"),
    (r"(?:女性|女人|女孩).*(?:喜欢|偏好|只关心).*(?:故事|剧情|社交|外观)", "gender_stereotype_story", "性别刻板印象：女性只关心故事"),
    (r"(?:男性|男人|男孩).*(?:喜欢|偏好|只关心).*(?:竞技|战斗|系统|数值)", "gender_stereotype_competition", "性别刻板印象：男性只关心竞技"),
    (r"(?:老年人|老玩家).*(?:不会|不能|无法).*(?:学习|适应|理解)", "age_stereotype_inability", "年龄刻板印象：老年人无法学习"),
    (r"(?:因为|作为).*(?:种族|民族|族裔).*(?:所以|必然|天生)", "race_assumption", "基于种族的刻板假设"),
    (r"(?:所有|全部|每个).*(?:女玩家|男玩家|老年玩家|年轻玩家).*(?:都|一定|必然)", "group_generalization", "群体过度概括"),
    (r"because she is (?:female|a woman).*(?:likes|prefers|cares)", "gender_assumption_en", "性别刻板假设（英文）"),
    (r"as an (?:INTJ|ENFP|ESFJ|ISTP).*(?:only|always|must|never)", "mbti_determinism_en", "MBTI决定论（英文）"),
]

RISK_KEYWORDS: Dict[str, List[str]] = {
    "high": ["刻板印象", "歧视", "偏见", "stereotype", "discrimination", "bias"],
    "medium": ["假设", "概括", "assumption", "generalization"],
    "low": ["倾向", "偏好", "preference", "tendency"],
}


class EthicsService:
    _stereotype_cache: Optional[List[Tuple[str, str, str]]] = None

    @classmethod
    def _load_stereotype_patterns(cls) -> List[Tuple[str, str, str]]:
        """加载刻板印象检测模式，优先从 harness 文件加载"""
        if cls._stereotype_cache is not None:
            return cls._stereotype_cache

        patterns = list(STEREOTYPE_PATTERNS)

        stereo_check_path = os.path.join(HARNESS_DIR, "evaluators", "stereotype-check.md")
        if os.path.isfile(stereo_check_path):
            try:
                with open(stereo_check_path, "r", encoding="utf-8") as f:
                    content = f.read()
                fail_section = cls._extract_section(content, "Fail")
                for line in fail_section.split("\n"):
                    line = line.strip().lstrip("- ")
                    if line and len(line) > 5:
                        escaped = re.escape(line[:30])
                        patterns.append((escaped, "harness_custom", f"harness 自定义规则: {line[:50]}"))
            except Exception:
                pass

        cls._stereotype_cache = patterns
        return patterns

    @classmethod
    def _extract_section(cls, content: str, section_name: str) -> str:
        """从 markdown 中提取指定章节内容"""
        lines = content.split("\n")
        in_section = False
        section_lines = []
        for line in lines:
            if re.match(r"^#+\s+", line):
                heading = re.sub(r"^#+\s+", "", line).strip()
                if heading.lower().startswith(section_name.lower()):
                    in_section = True
                    continue
                elif in_section:
                    break
            elif in_section:
                section_lines.append(line)
        return "\n".join(section_lines)

    @classmethod
    def check_stereotypes(cls, text: str) -> List[str]:
        """检测文本中的刻板印象，返回检测到的违规列表"""
        patterns = cls._load_stereotype_patterns()
        detections = []
        for pattern, rule_id, description in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detections.append(f"[{rule_id}] {description}")
        return detections

    @classmethod
    def evaluate_persona_output(
        cls,
        session: Session,
        persona_id: str,
        output_data: Dict[str, Any],
        input_materials: Optional[Dict[str, Any]] = None,
    ) -> EthicsReportModel:
        """评估 persona 输出的伦理合规性"""
        import json
        text = json.dumps(output_data, ensure_ascii=False)

        stereotype_detections = cls.check_stereotypes(text)

        violations = []
        for detection in stereotype_detections:
            severity = "medium"
            for sev, keywords in RISK_KEYWORDS.items():
                if any(kw in detection.lower() for kw in keywords):
                    severity = sev
                    break
            parts = detection.split("] ", 1)
            rule = parts[0].lstrip("[") if len(parts) > 1 else "unknown"
            detail = parts[1] if len(parts) > 1 else detection
            violations.append({
                "severity": severity,
                "rule": rule,
                "detail": detail,
            })

        high_count = sum(1 for v in violations if v["severity"] == "high")
        medium_count = sum(1 for v in violations if v["severity"] == "medium")

        if high_count > 0:
            score = max(0, 60 - high_count * 20 - medium_count * 5)
        elif medium_count > 0:
            score = max(50, 90 - medium_count * 10)
        else:
            score = 100

        if high_count > 0:
            stereotype_risk = "high"
        elif medium_count > 0:
            stereotype_risk = "medium"
        else:
            stereotype_risk = "low"

        passed = score >= 70 and high_count == 0

        report = EthicsReportModel(
            id=str(uuid.uuid4()),
            persona_id=persona_id,
            passed=passed,
            score=score,
            violations_json=violations,
            stereotype_risk=stereotype_risk,
        )
        session.add(report)
        session.commit()
        session.refresh(report)

        return report

    @classmethod
    def calculate_panel_differentiation(cls, panel_outputs: List[Dict[str, Any]]) -> float:
        """计算面板差异化程度，使用平均 Jaccard 距离"""
        if len(panel_outputs) < 2:
            return 0.0

        def _extract_tokens(output: Dict[str, Any]) -> Set[str]:
            tokens: Set[str] = set()
            for key in ("key_points", "findings", "concerns", "opportunities"):
                items = output.get(key, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, str):
                            tokens.update(item.lower().split())
                        elif isinstance(item, dict):
                            for v in item.values():
                                if isinstance(v, str):
                                    tokens.update(v.lower().split())
            stance = output.get("stance", output.get("verdict", ""))
            if isinstance(stance, str) and stance:
                tokens.update(stance.lower().split())
            return tokens

        token_sets = [_extract_tokens(po) for po in panel_outputs]
        distances = []
        for i in range(len(token_sets)):
            for j in range(i + 1, len(token_sets)):
                a, b = token_sets[i], token_sets[j]
                if not a and not b:
                    continue
                union = len(a | b)
                if union == 0:
                    continue
                intersection = len(a & b)
                jaccard_dist = 1.0 - (intersection / union)
                distances.append(jaccard_dist)

        if not distances:
            return 0.0

        return round(sum(distances) / len(distances), 4)

    @classmethod
    def get_ethics_reports_for_review(cls, session: Session, review_id: str) -> List[EthicsReportModel]:
        """获取某个评审下所有 persona 的伦理报告"""
        stmt = select(PersonaOutput).where(PersonaOutput.review_id == review_id)
        persona_outputs = list(session.scalars(stmt).all())

        reports = []
        for po in persona_outputs:
            if po.output_json:
                report = cls.evaluate_persona_output(
                    session=session,
                    persona_id=po.persona_id,
                    output_data=po.output_json,
                )
                reports.append(report)
        return reports
