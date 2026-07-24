"""邮箱验证 / 忘记密码链路回归。

这两条链路的安全属性比功能本身更要紧：令牌不能明文落库、不能重放、
不能过期还有效、不能成为"这个邮箱注册过没有"的枚举器。
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    """这些接口在 AL_AUTH_ENABLED=false 时整体 400，测试里显式打开。"""
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


@pytest.fixture
def captured_mail(monkeypatch):
    """截获发信内容——console 后端本来就只写日志，这里直接抓参数更稳。"""
    sent = []
    from app.services import mail_service

    monkeypatch.setattr(
        mail_service, "send_mail", lambda to, subject, body: sent.append((to, subject, body))
    )
    return sent


def _register(client, email="user@example.com", password="password123"):
    return client.post(
        "/api/auth/register", json={"email": email, "password": password}
    )


def _token_from_link(body: str) -> str:
    for part in body.split():
        if "token=" in part:
            return part.split("token=", 1)[1].strip()
    raise AssertionError(f"邮件里没有找到 token: {body}")


class TestEmailVerification:
    def test_register_sends_verification_mail(self, client, captured_mail):
        r = _register(client, "verify-me@example.com")
        assert r.status_code == 200
        assert len(captured_mail) == 1
        to, subject, body = captured_mail[0]
        assert to == "verify-me@example.com"
        assert "验证" in subject
        assert "/verify-email?token=" in body

    def test_confirm_marks_verified(self, client, db, captured_mail):
        _register(client, "confirm@example.com")
        token = _token_from_link(captured_mail[0][2])

        r = client.post("/api/auth/verify-email/confirm", json={"token": token})
        assert r.status_code == 200
        assert r.json()["verified"] is True

        from app.models import User

        user = db.query(User).filter(User.email == "confirm@example.com").first()
        assert user.email_verified_at is not None

    def test_token_cannot_be_reused(self, client, captured_mail):
        """用过即作废——防重放。"""
        _register(client, "replay@example.com")
        token = _token_from_link(captured_mail[0][2])

        assert client.post("/api/auth/verify-email/confirm", json={"token": token}).status_code == 200
        assert client.post("/api/auth/verify-email/confirm", json={"token": token}).status_code == 400

    def test_bogus_token_rejected(self, client):
        r = client.post("/api/auth/verify-email/confirm", json={"token": "not-a-real-token"})
        assert r.status_code == 400


class TestForgotPassword:
    def test_does_not_leak_whether_email_registered(self, client, captured_mail):
        """注册过和没注册过必须返回一模一样的响应，否则就是邮箱枚举器。"""
        _register(client, "known@example.com")
        captured_mail.clear()

        known = client.post("/api/auth/password/forgot", json={"email": "known@example.com"})
        unknown = client.post("/api/auth/password/forgot", json={"email": "nobody@example.com"})

        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
        # 但只有真实存在的账号才会真的收到信
        assert len(captured_mail) == 1
        assert captured_mail[0][0] == "known@example.com"

    def test_reset_changes_password(self, client, captured_mail):
        _register(client, "reset@example.com", "oldpassword1")
        captured_mail.clear()
        client.post("/api/auth/password/forgot", json={"email": "reset@example.com"})
        token = _token_from_link(captured_mail[0][2])

        r = client.post(
            "/api/auth/password/reset", json={"token": token, "new_password": "brandnew123"}
        )
        assert r.status_code == 200

        # 旧密码失效、新密码可用
        assert client.post(
            "/api/auth/login", json={"email": "reset@example.com", "password": "oldpassword1"}
        ).status_code == 401
        assert client.post(
            "/api/auth/login", json={"email": "reset@example.com", "password": "brandnew123"}
        ).status_code == 200

    def test_reset_token_single_use(self, client, captured_mail):
        _register(client, "single@example.com", "oldpassword1")
        captured_mail.clear()
        client.post("/api/auth/password/forgot", json={"email": "single@example.com"})
        token = _token_from_link(captured_mail[0][2])

        client.post("/api/auth/password/reset", json={"token": token, "new_password": "firstnew123"})
        again = client.post(
            "/api/auth/password/reset", json={"token": token, "new_password": "secondnew123"}
        )
        assert again.status_code == 400

    def test_requesting_again_invalidates_previous_link(self, client, captured_mail):
        """连发两次找回邮件时，第一个链接必须失效——不给"多个链接同时有效"留口子。"""
        _register(client, "twice@example.com", "oldpassword1")
        captured_mail.clear()

        client.post("/api/auth/password/forgot", json={"email": "twice@example.com"})
        first = _token_from_link(captured_mail[0][2])
        client.post("/api/auth/password/forgot", json={"email": "twice@example.com"})
        second = _token_from_link(captured_mail[1][2])

        assert first != second
        assert client.post(
            "/api/auth/password/reset", json={"token": first, "new_password": "viafirst123"}
        ).status_code == 400
        assert client.post(
            "/api/auth/password/reset", json={"token": second, "new_password": "viasecond123"}
        ).status_code == 200


class TestTokenStorage:
    def test_token_stored_only_as_hash(self, client, db, captured_mail):
        """库里绝不能有令牌原文——泄露了也不能拿去重置别人密码。"""
        _register(client, "hashonly@example.com")
        token = _token_from_link(captured_mail[0][2])

        from app.models import AuthToken

        rows = db.query(AuthToken).all()
        assert rows, "应当有令牌记录"
        assert all(r.token_hash != token for r in rows)
        assert all(token not in (r.token_hash or "") for r in rows)

    def test_expired_token_rejected(self, client, db, captured_mail):
        from datetime import datetime, timedelta, timezone

        from app.models import AuthToken

        _register(client, "expired@example.com")
        token = _token_from_link(captured_mail[0][2])

        row = db.query(AuthToken).order_by(AuthToken.created_at.desc()).first()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

        assert client.post(
            "/api/auth/verify-email/confirm", json={"token": token}
        ).status_code == 400
