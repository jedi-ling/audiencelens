"""渐进式认证：AL_AUTH_ENABLED=true 时匿名依旧能跑（不是"开了认证就锁死匿名"），
登录只解锁个人归属与完整报告——"体验机会 + 登录看详情"。"""

import pytest

from app.config import settings

REPORT_JSON = {
    "meta": {"task_type": "concept_review"},
    "executive_summary": {
        "primary_recommendation": "advocate",
        "release_risk": "low",
        "evidence_quality": "sufficient",
    },
    "consensus": {"agreed_points": ["advocate"], "questioned_points": []},
    "major_disagreements": [{"topic": "x"}],
    "priority_fixes": [
        {"issue": "第一条修复", "severity": "high", "why_it_matters": "很重要", "suggested_fix": "改一下"},
        {"issue": "第二条修复", "severity": "medium", "why_it_matters": "次重要", "suggested_fix": "改一下2"},
    ],
    "persona_notes": [{"persona_id": "P01", "primary_stance": "advocate"}],
    "cross_examination": {"foo": "bar"},
    "simulation_notice": None,
}


def _enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


def _register_and_login(client, email="user@example.com", password="password123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["token"]


class TestProgressiveAuth:
    def test_register_disabled_by_default(self, client):
        r = client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123"})
        assert r.status_code == 400

    def test_register_and_login_work_when_enabled(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        token = _register_and_login(client, "progressive@example.com")
        assert token

        r = client.post(
            "/api/auth/login", json={"email": "progressive@example.com", "password": "password123"}
        )
        assert r.status_code == 200
        assert r.json()["token"]

    def test_anonymous_review_creation_still_works_when_auth_enabled(self, client, monkeypatch):
        """核心承诺：打开认证开关不等于关闭匿名体验——两者互不冲突。"""
        _enable_auth(monkeypatch)
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["is_anonymous"] is True

    def test_logged_in_me_reflects_real_identity(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        token = _register_and_login(client, "identity@example.com")
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["is_anonymous"] is False
        assert body["email"] == "identity@example.com"


class TestReportGatingLegacyEndpoint:
    """/api/reviews/{id}/report —— 这是 ReportPage.tsx 实际调用的端点。"""

    def _make_review(self, db, user_id="anonymous"):
        from app.models import Review

        review = Review(
            user_id=user_id,
            task_type="concept_review",
            artifact_bundle={},
            status="completed",
            report_json=REPORT_JSON,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    def test_anonymous_sees_gated_report(self, client, db, monkeypatch):
        _enable_auth(monkeypatch)
        review = self._make_review(db)
        r = client.get(f"/api/reviews/{review.id}/report")
        assert r.status_code == 200
        report = r.json()["report_json"]
        assert report["is_gated"] is True
        assert len(report["priority_fixes"]) == 1
        assert report["priority_fixes"][0]["issue"] == "第一条修复"
        assert report["persona_notes"] == []
        assert report["gated_counts"]["priority_fixes_hidden"] == 1
        assert report["gated_counts"]["persona_notes_hidden"] == 1
        # 诚实声明不能被裁掉
        assert "executive_summary" in report

    def test_logged_in_sees_full_report(self, client, db, monkeypatch):
        _enable_auth(monkeypatch)
        token = _register_and_login(client, "fullreport@example.com")
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        review = self._make_review(db, user_id=me["user_id"])

        r = client.get(
            f"/api/reviews/{review.id}/report", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        report = r.json()["report_json"]
        assert "is_gated" not in report
        assert len(report["priority_fixes"]) == 2
        assert len(report["persona_notes"]) == 1

    def test_auth_disabled_anonymous_still_gated_by_default(self, client, db):
        """AL_AUTH_ENABLED=false（默认）时也一律匿名，同样只看体验版——
        gating 不依赖认证开关，只依赖"当前请求是不是已登录身份"。"""
        review = self._make_review(db)
        r = client.get(f"/api/reviews/{review.id}/report")
        assert r.status_code == 200
        assert r.json()["report_json"]["is_gated"] is True


class TestReportGatingV2Endpoint:
    """/api/v2/reviews/{id} —— AskPage.tsx 的对话式入口走这条链路。"""

    def _make_review(self, db, user_id="anonymous"):
        from app.models import Review

        review = Review(
            user_id=user_id,
            task_type="concept_review",
            artifact_bundle={},
            status="completed",
            report_json=REPORT_JSON,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    def test_anonymous_gated(self, client, db, monkeypatch):
        _enable_auth(monkeypatch)
        review = self._make_review(db)
        r = client.get(f"/api/v2/reviews/{review.id}")
        assert r.status_code == 200
        assert r.json()["report"]["is_gated"] is True

    def test_wrong_user_gets_404_not_someone_elses_review(self, client, db, monkeypatch):
        _enable_auth(monkeypatch)
        token_a = _register_and_login(client, "usera@example.com")
        me_a = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()
        review = self._make_review(db, user_id=me_a["user_id"])

        token_b = _register_and_login(client, "userb@example.com")
        r = client.get(f"/api/v2/reviews/{review.id}", headers={"Authorization": f"Bearer {token_b}"})
        assert r.status_code == 404


class TestResolveLlmKeyProgressiveAuth:
    def test_anonymous_review_creation_not_blocked_by_auth(self, client, monkeypatch):
        """回归用例：resolve_llm_key 曾经内部还挂着 current_identity，
        导致打开 AL_AUTH_ENABLED 后匿名发评审直接 401——违背"体验机会"设计。
        无 key 时应该卡在 428（llm_key_missing），而不是 401（unauthorized）。"""
        _enable_auth(monkeypatch)
        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "x", "materials": [{"type": "text", "text": "test"}]},
            },
        )
        assert r.status_code == 428
        assert r.json()["error"]["code"] == "llm_key_missing"
