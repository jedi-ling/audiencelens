"""产品价值验证：记录采用、决策影响、节省时间和付费意愿。"""

from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.errors import BadRequest, NotFound
from app.models import FeedbackAdoption, Review, ReviewFeedback


def upsert_feedback(db: Session, review_id: str, user_id: str, data: dict) -> dict:
    review = db.get(Review, review_id)
    if not review or (review.user_id or "anonymous") != user_id:
        raise NotFound("评审不存在")
    if review.status != "completed":
        raise BadRequest("只能评价已完成的评审")
    suggested, adopted = int(data.get("fixes_suggested", 0)), int(data.get("fixes_adopted", 0))
    hours, wtp = float(data.get("hours_saved", 0)), data.get("willingness_to_pay_usd")
    if suggested < 0 or adopted < 0 or adopted > suggested:
        raise BadRequest("采纳数必须介于 0 和建议数之间")
    if hours < 0 or (wtp is not None and float(wtp) < 0):
        raise BadRequest("节省时间和付费意愿不能为负数")
    row = db.query(ReviewFeedback).filter_by(review_id=review_id).first()
    if row is None:
        row = ReviewFeedback(review_id=review_id, user_id=user_id, useful=bool(data["useful"]))
        db.add(row)
    row.useful = bool(data["useful"])
    row.decision_changed = bool(data.get("decision_changed", False))
    row.fixes_suggested, row.fixes_adopted = suggested, adopted
    row.hours_saved = hours
    row.willingness_to_pay_usd = float(wtp) if wtp is not None else None
    row.note, row.updated_at = data.get("note"), datetime.now(timezone.utc)
    if data.get("adopted_fixes") is not None:
        titles = []
        for title in data.get("adopted_fixes") or []:
            normalized = str(title).strip()
            if normalized and normalized not in titles:
                titles.append(normalized[:500])
        if len(titles) != adopted:
            raise BadRequest("具体采纳建议数量必须与 fixes_adopted 一致")
        row.adoptions.clear()
        row.adoptions.extend(FeedbackAdoption(fix_title=title) for title in titles)
    db.commit()
    return {"review_id": review_id, "recorded": True}


def metrics(db: Session, user_id: str) -> dict:
    completed = db.query(func.count(Review.id)).filter(Review.user_id == user_id, Review.status == "completed").scalar() or 0
    rows = db.query(ReviewFeedback).filter(ReviewFeedback.user_id == user_id).all()
    n = len(rows)
    suggested, adopted = sum(r.fixes_suggested for r in rows), sum(r.fixes_adopted for r in rows)
    wtp = [r.willingness_to_pay_usd for r in rows if r.willingness_to_pay_usd is not None]
    total_cost = sum(float(r.review.total_cost_usd or 0) for r in rows)
    useful_count = sum(r.useful for r in rows)
    task_groups = {}
    for row in rows:
        group = task_groups.setdefault(row.review.task_type, {"feedback_count": 0, "useful": 0, "suggested": 0, "adopted": 0})
        group["feedback_count"] += 1
        group["useful"] += int(row.useful)
        group["suggested"] += row.fixes_suggested
        group["adopted"] += row.fixes_adopted
    by_task_type = [{
        "task_type": task,
        "feedback_count": group["feedback_count"],
        "useful_rate": round(group["useful"] / group["feedback_count"], 3),
        "adoption_rate": round(group["adopted"] / group["suggested"], 3) if group["suggested"] else None,
        "low_confidence": group["feedback_count"] < 10,
    } for task, group in sorted(task_groups.items())]
    adopted_titles = {}
    for row in rows:
        for adoption in row.adoptions:
            adopted_titles[adoption.fix_title] = adopted_titles.get(adoption.fix_title, 0) + 1
    top_adopted_fixes = [
        {"title": title, "adoption_count": count}
        for title, count in sorted(adopted_titles.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    return {
        "completed_reviews": int(completed), "feedback_count": n,
        "feedback_coverage": round(n / completed, 3) if completed else None,
        "useful_rate": round(sum(r.useful for r in rows) / n, 3) if n else None,
        "decision_change_rate": round(sum(r.decision_changed for r in rows) / n, 3) if n else None,
        "fixes_suggested": suggested, "fixes_adopted": adopted,
        "adoption_rate": round(adopted / suggested, 3) if suggested else None,
        "hours_saved": round(sum(r.hours_saved for r in rows), 2),
        "average_willingness_to_pay_usd": round(sum(wtp) / len(wtp), 2) if wtp else None,
        "total_model_cost_usd": round(total_cost, 4),
        "average_model_cost_usd": round(total_cost / n, 4) if n else None,
        "cost_per_useful_review_usd": round(total_cost / useful_count, 4) if useful_count else None,
        "cost_per_adopted_fix_usd": round(total_cost / adopted, 4) if adopted else None,
        "by_task_type": by_task_type,
        "top_adopted_fixes": top_adopted_fixes,
        "low_confidence": n < 10,
        "note": f"仅收集 {n} 份反馈，指标暂不具统计意义" if n < 10 else None,
    }
