"""已登录用户自助改密码 / 改昵称。

这两条在此之前**完全不存在**：
  · 改密码：登录着也没有接口，唯一的路是退出 → 忘记密码 → 收邮件 → 点链接。
    而邮件链路在很多部署里根本没配通（AL_SMTP_* 空着只告警不拒启），
    两件事叠起来的实际效果是"密码不可更改"——怀疑密码泄露时也改不了。
  · 昵称：display_name 只在注册那一刻写入，之后没有任何路径能改。

安全属性比功能本身更要紧，所以下面每条正向断言都配了反向对照：
只测"改成功了"的话，一个不验旧密码、或者改完不撤销旧会话的实现同样能全绿，
而那两个恰恰是这类接口最容易出的致命错。
"""

import time

import pytest


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


def _signup(client, email, password="password123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


class TestChangePassword:
    def test_changes_password(self, client):
        t = _signup(client, "chpw@example.com")
        r = client.post(
            "/api/auth/password/change",
            headers=_h(t),
            json={"current_password": "password123", "new_password": "newpassword456"},
        )
        assert r.status_code == 200
        assert r.json()["changed"] is True
        # 新密码能登录
        assert client.post(
            "/api/auth/login",
            json={"email": "chpw@example.com", "password": "newpassword456"},
        ).status_code == 200

    def test_old_password_stops_working(self, client):
        """反向对照：光测"新密码能登录"证明不了旧密码已失效。"""
        t = _signup(client, "chpw2@example.com")
        client.post(
            "/api/auth/password/change",
            headers=_h(t),
            json={"current_password": "password123", "new_password": "newpassword456"},
        )
        assert client.post(
            "/api/auth/login",
            json={"email": "chpw2@example.com", "password": "password123"},
        ).status_code == 401

    def test_wrong_current_password_rejected(self, client):
        """不验旧密码的话，偷到一把 JWT 就能永久夺走账号——
        原主人改完再也登不进去，令牌泄露从"临时冒用"升级成"彻底丢号"。"""
        t = _signup(client, "chpw3@example.com")
        r = client.post(
            "/api/auth/password/change",
            headers=_h(t),
            json={"current_password": "wrong-one", "new_password": "newpassword456"},
        )
        assert r.status_code == 401
        # 而且密码必须没被改动
        assert client.post(
            "/api/auth/login",
            json={"email": "chpw3@example.com", "password": "password123"},
        ).status_code == 200

    def test_old_token_revoked(self, client):
        """改密码必须踢掉旧会话。

        JWT 是自签的，只认签名和 exp——不撤销的话，改密码前偷到的令牌还能再用
        满一个 TTL（默认 7 天），"改密码"对已经发生的入侵毫无作用。
        """
        stolen = _signup(client, "chpw4@example.com")
        # 必须让旧令牌确实早于撤销点**一整秒**再改密码。
        # 撤销点向下取整到整秒、判据是 iat < revoked_at（见 deps.sessions_revoked_at），
        # 于是同一秒内签发的令牌会逃过一劫——这是刻意的取舍：JWT 的 iat 只有整秒精度，
        # 拿带微秒的时间点去比会让"改完密码立刻拿到的新令牌"被当场判死，用户改完就登不进去。
        # 不 sleep 的话本测试测的是那个 ≤1 秒窗口，而不是撤销本身，会红得莫名其妙。
        time.sleep(1.1)
        r = client.post(
            "/api/auth/password/change",
            headers=_h(stolen),
            json={"current_password": "password123", "new_password": "newpassword456"},
        )
        fresh = r.json()["token"]

        # 旧令牌：已作废
        assert client.get("/api/usage", headers=_h(stolen)).status_code == 401
        # 新令牌：本设备继续可用——改密码不该把自己也踢下线
        assert client.get("/api/usage", headers=_h(fresh)).status_code == 200

    def test_same_password_rejected(self, client):
        t = _signup(client, "chpw5@example.com")
        r = client.post(
            "/api/auth/password/change",
            headers=_h(t),
            json={"current_password": "password123", "new_password": "password123"},
        )
        assert r.status_code == 400

    def test_short_password_rejected(self, client):
        t = _signup(client, "chpw6@example.com")
        r = client.post(
            "/api/auth/password/change",
            headers=_h(t),
            json={"current_password": "password123", "new_password": "short"},
        )
        assert r.status_code == 422

    def test_anonymous_rejected(self, client):
        r = client.post(
            "/api/auth/password/change",
            json={"current_password": "password123", "new_password": "newpassword456"},
        )
        assert r.status_code in (400, 401)


class TestUpdateProfile:
    def test_updates_display_name(self, client):
        t = _signup(client, "prof@example.com")
        r = client.patch("/api/auth/me", headers=_h(t), json={"display_name": "熵呓"})
        assert r.status_code == 200
        assert r.json()["display_name"] == "熵呓"

    def test_persists(self, client, db):
        """反向对照：接口回显参数太容易了，得确认真的落库。"""
        t = _signup(client, "prof2@example.com")
        client.patch("/api/auth/me", headers=_h(t), json={"display_name": "改过了"})

        from app.models import User

        db.expire_all()
        u = db.query(User).filter(User.email == "prof2@example.com").first()
        assert u.display_name == "改过了"

    def test_blank_rejected(self, client):
        t = _signup(client, "prof3@example.com")
        r = client.patch("/api/auth/me", headers=_h(t), json={"display_name": "   "})
        assert r.status_code == 400

    def test_anonymous_rejected(self, client):
        r = client.patch("/api/auth/me", json={"display_name": "谁"})
        assert r.status_code in (400, 401)

    def test_email_is_not_changeable_here(self, client):
        """邮箱是登录名 + 找回密码的收件地址 + 账号唯一键，换它必须走
        "向新地址发验证信、验证通过才生效"的两步流程。这个接口不接受 email 字段，
        免得看起来支持了、实际上填错一个字母就把账号锁死。"""
        t = _signup(client, "prof4@example.com")
        client.patch(
            "/api/auth/me",
            headers=_h(t),
            json={"display_name": "x", "email": "hijack@example.com"},
        )
        me = client.get("/api/auth/me", headers=_h(t)).json()
        assert "hijack@example.com" not in str(me)
