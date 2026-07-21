"""评审历史/权限：/api/reviews 系列此前完全没有按用户身份过滤——任何登录用户
都能列出/查看/删除所有人的评审，v1 创建接口也从不记录真实 user_id（永远落在
共享的 anonymous 桶里）。这里验证修复后两个不同账号互相看不到对方的评审。
"""

import pytest

from app.config import settings


def _enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


def _register_and_login(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    return r.json()["token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_review(client, token, title="我的评审"):
    r = client.post(
        "/api/reviews",
        json={
            "task_type": "concept_review",
            "artifact_bundle": {"title": title, "materials": [{"type": "text", "text": "x"}]},
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(autouse=True)
def _cleanup(db):
    from app.models import Review, User

    yield
    db.query(Review).delete()
    db.query(User).delete()
    db.commit()


class TestReviewOwnership:
    def test_v1_create_records_real_user_id(self, client, monkeypatch, db):
        """此前这里永远写死 "anonymous"，跟谁登录无关。"""
        from app.models import Review

        _enable_auth(monkeypatch)
        token = _register_and_login(client, "owner@example.com")
        review_id = _create_review(client, token)

        row = db.get(Review, review_id)
        assert row.user_id != "anonymous"

    def test_list_reviews_only_shows_own(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        token_a = _register_and_login(client, "alice@example.com")
        token_b = _register_and_login(client, "bob@example.com")
        _create_review(client, token_a, "Alice 的评审")
        _create_review(client, token_b, "Bob 的评审")

        r = client.get("/api/reviews", headers=_auth_headers(token_a))
        assert r.status_code == 200
        titles = [row["target_title"] for row in r.json()]
        assert "Alice 的评审" in titles
        assert "Bob 的评审" not in titles

    def test_get_other_users_review_is_404(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        token_a = _register_and_login(client, "alice2@example.com")
        token_b = _register_and_login(client, "bob2@example.com")
        review_id = _create_review(client, token_a)

        r = client.get(f"/api/reviews/{review_id}", headers=_auth_headers(token_b))
        assert r.status_code == 404

    def test_owner_can_get_own_review(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        token = _register_and_login(client, "alice3@example.com")
        review_id = _create_review(client, token)

        r = client.get(f"/api/reviews/{review_id}", headers=_auth_headers(token))
        assert r.status_code == 200

    def test_report_of_other_users_review_is_404(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        token_a = _register_and_login(client, "alice4@example.com")
        token_b = _register_and_login(client, "bob4@example.com")
        review_id = _create_review(client, token_a)

        r = client.get(f"/api/reviews/{review_id}/report", headers=_auth_headers(token_b))
        assert r.status_code == 404

    def test_delete_other_users_review_is_404_and_not_deleted(self, client, monkeypatch, db):
        from app.models import Review

        _enable_auth(monkeypatch)
        token_a = _register_and_login(client, "alice5@example.com")
        token_b = _register_and_login(client, "bob5@example.com")
        review_id = _create_review(client, token_a)

        r = client.delete(f"/api/reviews/{review_id}", headers=_auth_headers(token_b))
        assert r.status_code == 404
        assert db.get(Review, review_id) is not None

    def test_owner_can_delete_own_review(self, client, monkeypatch, db):
        from app.models import Review

        _enable_auth(monkeypatch)
        token = _register_and_login(client, "alice6@example.com")
        review_id = _create_review(client, token)

        r = client.delete(f"/api/reviews/{review_id}", headers=_auth_headers(token))
        assert r.status_code == 200
        assert db.get(Review, review_id) is None

    def test_anonymous_bucket_still_shared_by_design(self, client):
        """AL_AUTH_ENABLED=false（默认）时所有匿名请求共享同一个 user_id——
        这是单机/开源形态的既有设计（判断复利、CDK 额度都是同一个桶），不是本次要堵的洞。"""
        review_id = _create_review_anonymous(client)
        r = client.get(f"/api/reviews/{review_id}")
        assert r.status_code == 200


def _create_review_anonymous(client):
    r = client.post(
        "/api/reviews",
        json={
            "task_type": "concept_review",
            "artifact_bundle": {"title": "匿名评审", "materials": [{"type": "text", "text": "x"}]},
        },
    )
    assert r.status_code == 200
    return r.json()["id"]
