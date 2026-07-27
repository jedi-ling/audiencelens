"""认领匿名评审：POST /api/auth/me/claim-reviews

为什么需要这条链路：匿名评审落库时 user_id="anonymous"，而所有归属校验都是
精确字符串比对。用户一登录，identity.user_id 变成真实 id，这条评审的每个路由
立刻 404 —— 前端"登录后可查看完整报告"实测表现是**报告凭空消失**，转化漏斗
上最伤的一处。这里钉死认领后能打开、以及认领本身不能变成越权工具。
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _cleanup(db):
    from app.models import Judgment, Review, ReviewFeedback, User

    yield
    db.query(ReviewFeedback).delete()
    db.query(Judgment).delete()
    db.query(Review).delete()
    db.query(User).delete()
    db.commit()


def _enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


def _register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _anonymous_review(db, title="匿名跑的评审"):
    """直接建一条归属匿名桶的评审——等价于"用户没登录时跑的那次"。"""
    from app.models import Review

    review = Review(
        user_id="anonymous",
        task_type="concept_review",
        target_title=title,
        artifact_bundle={"title": title, "materials": [{"type": "text", "text": "x"}]},
        status="completed",
        report_json={"executive_summary": {"release_risk": "medium"}},
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review.id


class TestClaimFixesTheDisappearingReport:
    def test_login_without_claim_makes_review_404(self, client, db, monkeypatch):
        """先把 bug 本身钉住：不认领，登录后这条评审就是打不开的。"""
        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)
        token = _register(client, "ghost@example.com")

        assert client.get(f"/api/reviews/{review_id}", headers=_headers(token)).status_code == 404
        assert client.get(f"/api/v2/reviews/{review_id}", headers=_headers(token)).status_code == 404

    def test_claim_then_review_and_report_open(self, client, db, monkeypatch):
        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)
        token = _register(client, "claimer@example.com")

        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id]},
            headers=_headers(token),
        )
        assert r.status_code == 200
        assert r.json()["claimed"] == [review_id]
        assert r.json()["claimed_count"] == 1

        assert client.get(f"/api/reviews/{review_id}", headers=_headers(token)).status_code == 200
        assert (
            client.get(f"/api/reviews/{review_id}/report", headers=_headers(token)).status_code
            == 200
        )
        assert client.get(f"/api/v2/reviews/{review_id}", headers=_headers(token)).status_code == 200

    def test_claimed_review_shows_up_in_history(self, client, db, monkeypatch):
        """"报告会保存在你的历史记录里"这句文案要真的成立。"""
        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db, title="历史里应该看得到")
        token = _register(client, "history@example.com")

        client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id]},
            headers=_headers(token),
        )
        titles = [
            row["target_title"] for row in client.get("/api/reviews", headers=_headers(token)).json()
        ]
        assert "历史里应该看得到" in titles

    def test_claimed_report_is_no_longer_gated(self, client, db, monkeypatch):
        """认领的意义是拿到完整报告，不是拿到一份仍被裁剪的体验版。"""
        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)
        token = _register(client, "ungated@example.com")

        client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id]},
            headers=_headers(token),
        )
        report = client.get(f"/api/reviews/{review_id}/report", headers=_headers(token)).json()
        assert not (report["report_json"] or {}).get("is_gated")


class TestClaimSecurityBoundary:
    def test_cannot_claim_review_owned_by_another_account(self, client, db, monkeypatch):
        """认领只对匿名桶开放。已属于真实账号的评审一律拒绝——否则这个接口
        就成了"知道 uuid 就能把别人的评审偷走"的越权工具。"""
        from app.models import Review

        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)
        owner = _register(client, "owner@example.com")
        thief = _register(client, "thief@example.com")

        client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id]},
            headers=_headers(owner),
        )
        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id]},
            headers=_headers(thief),
        )
        assert r.status_code == 200
        assert r.json()["claimed"] == []
        assert review_id in r.json()["rejected"]

        db.expire_all()
        assert db.get(Review, review_id).user_id != "anonymous"
        assert client.get(f"/api/reviews/{review_id}", headers=_headers(thief)).status_code == 404
        assert client.get(f"/api/reviews/{review_id}", headers=_headers(owner)).status_code == 200

    def test_unknown_id_is_rejected_not_an_error(self, client, monkeypatch):
        """不存在的 id 与"已属于别人"同样进 rejected，不区分——与归属校验用
        404 而不是 403 同一口径：不向调用方确认某个 id 是否存在。"""
        _enable_auth(monkeypatch)
        token = _register(client, "unknown@example.com")

        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": ["11111111-2222-3333-4444-555555555555"]},
            headers=_headers(token),
        )
        assert r.status_code == 200
        assert r.json()["claimed"] == []
        assert r.json()["rejected"] == ["11111111-2222-3333-4444-555555555555"]

    def test_anonymous_caller_is_refused(self, client, db, monkeypatch):
        """匿名不是"某个人"而是所有人共用的桶，让它认领没有任何意义，
        还会把评审改挂成它自己。与导出/删号同一道闸（_require_own_identity）。"""
        from app.models import Review

        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)

        r = client.post("/api/auth/me/claim-reviews", json={"review_ids": [review_id]})
        assert r.status_code == 400
        db.expire_all()
        assert db.get(Review, review_id).user_id == "anonymous"

    def test_batch_size_is_capped(self, client, monkeypatch):
        """一次请求能塞进去的 id 数要有上限，别让它变成批量 uuid 探测器。"""
        from app.api.platform import CLAIM_MAX_IDS

        _enable_auth(monkeypatch)
        token = _register(client, "batch@example.com")

        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [f"id-{i}" for i in range(CLAIM_MAX_IDS + 1)]},
            headers=_headers(token),
        )
        assert r.status_code == 400

    def test_empty_list_is_a_noop(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        token = _register(client, "empty@example.com")

        r = client.post(
            "/api/auth/me/claim-reviews", json={"review_ids": []}, headers=_headers(token)
        )
        assert r.status_code == 200
        assert r.json() == {"claimed": [], "rejected": [], "claimed_count": 0}

    def test_duplicate_ids_counted_once(self, client, db, monkeypatch):
        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)
        token = _register(client, "dupe@example.com")

        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id, review_id, review_id]},
            headers=_headers(token),
        )
        assert r.json()["claimed"] == [review_id]
        assert r.json()["rejected"] == []


class TestClaimMovesRelatedRecords:
    """判断留档与价值回填按 user_id 过滤；不跟着改归属的话，认领回来的评审
    在「判断复利」「价值指标」里查无此人，旧数据还留在共享的匿名桶里。"""

    def test_judgments_follow_the_review(self, client, db, monkeypatch):
        from app.models import Judgment

        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)
        db.add(
            Judgment(
                review_id=review_id,
                user_id="anonymous",
                claim="新手引导太长会劝退",
                severity="high",
            )
        )
        db.commit()

        token = _register(client, "ledger@example.com")
        client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id]},
            headers=_headers(token),
        )

        listed = client.get("/api/ledger/judgments", headers=_headers(token)).json()["judgments"]
        assert any(j["claim"] == "新手引导太长会劝退" for j in listed)

    def test_feedback_follows_the_review(self, client, db, monkeypatch):
        from app.models import ReviewFeedback

        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)
        db.add(
            ReviewFeedback(
                review_id=review_id,
                user_id="anonymous",
                useful=True,
                decision_changed=True,
                fixes_suggested=3,
                fixes_adopted=2,
            )
        )
        db.commit()

        token = _register(client, "metrics@example.com")
        client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id]},
            headers=_headers(token),
        )

        metrics = client.get("/api/validation/metrics", headers=_headers(token)).json()
        assert metrics["feedback_count"] == 1
        assert metrics["fixes_adopted"] == 2

    def test_usage_records_stay_in_the_anonymous_bucket(self, client, db, monkeypatch):
        """用量是计量/财务事实源：这次消耗当时就记在匿名桶头上了。事后改挂到
        新账号 = 让用户为"注册前已经用掉的额度"再被扣一次配额。刻意不搬。"""
        from app.models import UsageRecord

        _enable_auth(monkeypatch)
        review_id = _anonymous_review(db)
        db.add(UsageRecord(user_id="anonymous", review_id=review_id, kind="review", persona_count=6))
        db.commit()

        token = _register(client, "usage@example.com")
        client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [review_id]},
            headers=_headers(token),
        )

        db.expire_all()
        row = db.query(UsageRecord).filter(UsageRecord.review_id == review_id).one()
        assert row.user_id == "anonymous"
        db.delete(row)
        db.commit()
