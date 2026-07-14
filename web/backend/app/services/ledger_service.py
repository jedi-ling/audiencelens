"""判断复利闭环（Judgment Ledger）——产品的护城河层。

一次性评审工具的问题：跑完出报告，关系就断了，经验不沉淀。
这一层把每次评审的**可证伪预测**落库并盖时间戳；日后真人测试/上线数据
回来，回填 Outcome 打分。于是系统能回答：

    "P14 价格敏感型历史上说中过多少次？"
    "'新手引导太长' 这类判断，我们的命中率是多少？"

与投资类产品不同的是：我们的验证来源是**真实用户测试**，
是干净的 ground truth，不像股价那样掺杂运气噪音——这是我们更强的地方。

诚实原则：命中率基于样本量，样本不足时必须如实标注 low_confidence，
绝不用 3 个样本吹"准确率 100%"。
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest, NotFound
from app.models import Judgment, Outcome, Review

VALID_VERDICTS = ("hit", "miss", "partial", "unknown")

# 样本量低于此值时，命中率不具统计意义，必须标注
MIN_SAMPLES_FOR_CONFIDENCE = 10


def extract_judgments_from_report(report: dict) -> List[dict]:
    """从评审报告里抽出可证伪的预测。

    来源优先级：priority_fixes（已经是"该修什么"的断言）> 各人格 key_issues。
    只抽有明确断言的，不抽"感觉还行"这种无法证伪的话。
    """
    out = []
    seen = set()

    for fix in report.get("priority_fixes", []) or []:
        claim = (fix.get("title") or fix.get("issue") or "").strip()
        if not claim or claim in seen:
            continue
        seen.add(claim)
        out.append(
            {
                "persona_id": None,  # 合议结论
                "claim": claim,
                "severity": fix.get("severity"),
                "confidence": fix.get("confidence"),
                "evidence": fix.get("evidence") or fix.get("why_it_matters"),
            }
        )

    for note in report.get("persona_notes", []) or []:
        pid = note.get("persona_id")
        for issue in note.get("key_issues", []) or []:
            claim = (issue.get("title") or "").strip()
            key = f"{pid}::{claim}"
            if not claim or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "persona_id": pid,
                    "claim": claim,
                    "severity": issue.get("severity"),
                    "confidence": note.get("confidence"),
                    "evidence": issue.get("why_it_matters"),
                }
            )
    return out


def record_judgments(db: Session, review: Review, report: dict) -> int:
    """评审完成时调用：把预测落库并盖时间戳。返回记录条数。"""
    if not settings.ledger_enabled or not report:
        return 0

    rows = extract_judgments_from_report(report)
    now = datetime.now(timezone.utc)
    for r in rows:
        db.add(
            Judgment(
                review_id=review.id,
                user_id=review.user_id or "anonymous",
                persona_id=r["persona_id"],
                claim=r["claim"][:2000],
                severity=r.get("severity"),
                confidence=r.get("confidence"),
                evidence={"note": r.get("evidence")} if r.get("evidence") else None,
                predicted_at=now,
            )
        )
    db.commit()
    return len(rows)


def list_judgments(
    db: Session, user_id: str, review_id: str = None, only_unverified: bool = False, limit: int = 200
) -> List[dict]:
    q = db.query(Judgment).filter(Judgment.user_id == user_id)
    if review_id:
        q = q.filter(Judgment.review_id == review_id)
    rows = q.order_by(Judgment.predicted_at.desc()).limit(limit).all()

    out = []
    for j in rows:
        oc = j.outcome
        if only_unverified and oc is not None:
            continue
        out.append(
            {
                "id": j.id,
                "review_id": j.review_id,
                "persona_id": j.persona_id,
                "claim": j.claim,
                "severity": j.severity,
                "confidence": j.confidence,
                "predicted_at": j.predicted_at.isoformat() if j.predicted_at else None,
                "outcome": (
                    {
                        "verdict": oc.verdict,
                        "source": oc.source,
                        "note": oc.note,
                        "verified_at": oc.verified_at.isoformat() if oc.verified_at else None,
                    }
                    if oc
                    else None
                ),
            }
        )
    return out


def verify_judgment(
    db: Session,
    judgment_id: str,
    verdict: str,
    user_id: str,
    source: str = "playtest",
    note: Optional[str] = None,
) -> dict:
    """回填验证结果——闭环的另一半。"""
    if verdict not in VALID_VERDICTS:
        raise BadRequest(f"verdict 必须是 {', '.join(VALID_VERDICTS)} 之一")

    j = db.get(Judgment, judgment_id)
    if not j:
        raise NotFound("判断不存在")
    if (j.user_id or "anonymous") != user_id:
        raise NotFound("判断不存在")  # 不泄露他人数据的存在性

    existing = db.query(Outcome).filter(Outcome.judgment_id == judgment_id).first()
    if existing:
        existing.verdict = verdict
        existing.source = source
        existing.note = note
        existing.verified_at = datetime.now(timezone.utc)
    else:
        db.add(
            Outcome(
                judgment_id=judgment_id, verdict=verdict, source=source, note=note
            )
        )
    db.commit()
    return {"judgment_id": judgment_id, "verdict": verdict, "source": source}


def hit_rate(db: Session, user_id: str, persona_id: str = None) -> dict:
    """命中率统计。样本不足时如实标注，不吹牛。"""
    q = (
        db.query(Outcome.verdict, func.count(Outcome.id))
        .join(Judgment, Outcome.judgment_id == Judgment.id)
        .filter(Judgment.user_id == user_id)
    )
    if persona_id:
        q = q.filter(Judgment.persona_id == persona_id)
    counts = dict(q.group_by(Outcome.verdict).all())

    hit = int(counts.get("hit", 0))
    partial = int(counts.get("partial", 0))
    miss = int(counts.get("miss", 0))
    unknown = int(counts.get("unknown", 0))
    decided = hit + partial + miss  # unknown 不计入分母

    total_judgments = (
        db.query(func.count(Judgment.id)).filter(Judgment.user_id == user_id).scalar() or 0
    )

    rate = None
    if decided > 0:
        # partial 记半分
        rate = round((hit + 0.5 * partial) / decided, 3)

    return {
        "persona_id": persona_id,
        "total_judgments": int(total_judgments),
        "verified": decided + unknown,
        "pending_verification": int(total_judgments) - (decided + unknown),
        "hit": hit,
        "partial": partial,
        "miss": miss,
        "unknown": unknown,
        "hit_rate": rate,
        "sample_size": decided,
        # 诚实标注：样本太少时命中率不具统计意义
        "low_confidence": decided < MIN_SAMPLES_FOR_CONFIDENCE,
        "note": (
            f"样本量 {decided} < {MIN_SAMPLES_FOR_CONFIDENCE}，命中率仅供参考，不具统计意义"
            if decided < MIN_SAMPLES_FOR_CONFIDENCE
            else None
        ),
    }


def persona_leaderboard(db: Session, user_id: str, limit: int = 20) -> List[dict]:
    """各人格的历史命中率排行——"哪个人格的判断最值得听"。"""
    rows = (
        db.query(
            Judgment.persona_id,
            func.count(Outcome.id).label("decided"),
            func.sum(case((Outcome.verdict == "hit", 1), else_=0)).label("hits"),
            func.sum(case((Outcome.verdict == "partial", 1), else_=0)).label("partials"),
        )
        .join(Outcome, Outcome.judgment_id == Judgment.id)
        .filter(
            Judgment.user_id == user_id,
            Judgment.persona_id.isnot(None),
            Outcome.verdict != "unknown",
        )
        .group_by(Judgment.persona_id)
        .order_by(func.count(Outcome.id).desc())
        .limit(limit)
        .all()
    )

    out = []
    for persona_id, decided, hits, partials in rows:
        decided = int(decided or 0)
        hits = int(hits or 0)
        partials = int(partials or 0)
        out.append(
            {
                "persona_id": persona_id,
                "sample_size": decided,
                "hit_rate": round((hits + 0.5 * partials) / decided, 3) if decided else None,
                "low_confidence": decided < MIN_SAMPLES_FOR_CONFIDENCE,
            }
        )
    return out
