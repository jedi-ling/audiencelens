"""商业验证闭环：不能用调用次数冒充客户价值。"""

from app.models import Review


def _completed_review(db, user_id="anonymous"):
    row = Review(user_id=user_id, task_type="steam_page_review", artifact_bundle={}, status="completed", total_cost_usd=0.6)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_feedback_and_metrics_end_to_end(client, db):
    review = _completed_review(db)
    response = client.post(
        f"/api/validation/reviews/{review.id}/feedback",
        json={
            "useful": True,
            "decision_changed": True,
            "fixes_suggested": 4,
            "fixes_adopted": 3,
            "adopted_fixes": ["缩短教程", "明确价格", "增强首屏卖点"],
            "hours_saved": 2.5,
            "willingness_to_pay_usd": 29,
        },
    )
    assert response.status_code == 200
    metrics = client.get("/api/validation/metrics").json()
    assert metrics["feedback_count"] >= 1
    assert metrics["useful_rate"] == 1.0
    assert metrics["decision_change_rate"] == 1.0
    assert metrics["adoption_rate"] == 0.75
    assert metrics["hours_saved"] >= 2.5
    assert metrics["cost_per_useful_review_usd"] is not None
    assert metrics["cost_per_adopted_fix_usd"] is not None
    assert any(row["task_type"] == "steam_page_review" for row in metrics["by_task_type"])
    assert metrics["top_adopted_fixes"][0]["adoption_count"] >= 1
    assert metrics["low_confidence"] is True


def test_feedback_is_upserted_not_double_counted(client, db):
    review = _completed_review(db)
    url = f"/api/validation/reviews/{review.id}/feedback"
    assert client.post(url, json={"useful": False}).status_code == 200
    assert client.post(url, json={"useful": True, "fixes_suggested": 2, "fixes_adopted": 1}).status_code == 200
    metrics = client.get("/api/validation/metrics").json()
    # Other tests may share the session DB; this review itself must still have only one row.
    from app.models import ReviewFeedback
    assert db.query(ReviewFeedback).filter_by(review_id=review.id).count() == 1


def test_rejects_impossible_adoption(client, db):
    review = _completed_review(db)
    response = client.post(
        f"/api/validation/reviews/{review.id}/feedback",
        json={"useful": True, "fixes_suggested": 1, "fixes_adopted": 2},
    )
    assert response.status_code == 400


def test_rejects_feedback_before_completion(client, db):
    review = Review(user_id="anonymous", task_type="concept_review", artifact_bundle={}, status="running")
    db.add(review)
    db.commit()
    response = client.post(
        f"/api/validation/reviews/{review.id}/feedback", json={"useful": True}
    )
    assert response.status_code == 400
