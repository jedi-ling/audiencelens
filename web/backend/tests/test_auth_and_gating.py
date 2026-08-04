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

    def test_register_rejects_malformed_email(self, client, monkeypatch):
        """email 字段曾经裸收字符串——"abc" 也能注册成功，落库一个永远无法
        通知/找回的账号标识。现在服务端做宽松格式校验兜底。"""
        _enable_auth(monkeypatch)
        for bad in ["abc", "a@b", "@b.com", "a b@c.com", "a@"]:
            r = client.post("/api/auth/register", json={"email": bad, "password": "password123"})
            assert r.status_code == 400, f"畸形邮箱 {bad!r} 不该注册成功"
        # 正常邮箱不受影响
        r = client.post(
            "/api/auth/register", json={"email": "valid@example.com", "password": "password123"}
        )
        assert r.status_code == 200

    def test_register_rejects_short_password(self, client, monkeypatch):
        """服务端强制密码 >=8 位（不能只靠前端校验）。"""
        _enable_auth(monkeypatch)
        r = client.post("/api/auth/register", json={"email": "short@example.com", "password": "1234567"})
        assert r.status_code == 422  # pydantic min_length 校验

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


class TestWebSocketOwnership:
    """WS 归属校验：登录用户的评审只有本人能订阅。"""

    def _mk_review(self, db, user_id):
        from app.models import Review

        row = Review(
            user_id=user_id,
            task_type="concept_review",
            artifact_bundle={"text": "x"},
            status="running",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id

    def test_stranger_cannot_subscribe_to_owned_review(self, client, db):
        import pytest as _pytest
        from starlette.websockets import WebSocketDisconnect

        rid = self._mk_review(db, "owner-user-1")
        # 不带 token（匿名）订阅别人的评审 → 服务端在握手后立即关闭
        with _pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/ws/review/{rid}"):
                pass
        assert exc.value.code == 4403

    def test_owner_can_subscribe_with_token(self, client, db):
        from app.config import settings
        from app.core.security import create_token

        rid = self._mk_review(db, "owner-user-2")
        token = create_token("owner-user-2", settings.jwt_secret, 300)
        with client.websocket_connect(f"/ws/review/{rid}?token={token}"):
            pass  # 能建立连接不被拒即通过

    def test_unknown_review_closed(self, client):
        import pytest as _pytest
        from starlette.websockets import WebSocketDisconnect

        with _pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/review/no-such-id"):
                pass
        assert exc.value.code == 4404


class TestConcurrentRegisterSameEmail:
    """并发注册同邮箱（spec 3.6）：预检只挡顺序请求，并发时两个请求都能通过
    预检，靠 users.email 唯一约束兜底。不捕获 IntegrityError 就是 500——
    而"这个邮箱注册过"是一个业务结果，应该和预检拦截返回同一个 400。"""

    def test_duplicate_email_never_500s(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        import threading

        results = []

        def do_register():
            r = client.post(
                "/api/auth/register",
                json={"email": "race@example.com", "password": "password123"},
            )
            results.append(r.status_code)

        threads = [threading.Thread(target=do_register) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert 200 in results, f"两个并发注册都失败了：{results}"
        assert 500 not in results, f"并发注册同邮箱出现 500：{results}"
        assert all(code in (200, 400) for code in results), results
