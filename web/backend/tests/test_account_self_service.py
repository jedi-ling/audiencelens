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
        # 这句 sleep 保留，但理由已经变了，注意别再照抄旧解释：
        # 原先撤销点向下取整，同秒令牌逃生，不 sleep 这条会红——sleep 是在替
        # 那个洞打掩护。现在撤销点向上取整、同秒也会被撤销（见
        # TestRevocationHasNoSameSecondHole），这条不 sleep 同样能过。
        # 留着它是为了覆盖"跨秒"这个更常见的路径，两条各测一边。
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

    def test_anonymous_rejected(self, client, monkeypatch, db):
        """以前未登录调用一律拒绝（共享匿名桶不是"某个人"）。现在未登录访客是
        自己的游客：只能改到它自己那一行，别人的资料纹丝不动。"""
        from app.models import User

        other = _signup(client, "prof-bystander@example.com")
        r = client.patch("/api/auth/me", json={"display_name": "游客改名"})
        assert r.status_code == 200, r.text
        guest_id = client.get("/api/auth/me").json()["user_id"]
        assert r.json()["id"] == guest_id
        db.expire_all()
        assert db.get(User, guest_id).display_name == "游客改名"
        assert client.get("/api/auth/me", headers=_h(other)).json()["display_name"] != "游客改名"

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


class TestRevocationHasNoSameSecondHole:
    """同一秒内被盗的令牌也必须失效。

    这条是审计翻出来的：撤销点原先向下取整、判据是 iat < revoked_at，于是
    iat == revoked_at 恒为假，与撤销发生在同一秒的令牌不但逃过一劫，还
    **活满完整 TTL（默认 7 天）**且不会自愈——改密码这个动作对该次入侵完全无效，
    而用户以为自己已经把人赶出去了。注释当时把代价写成"≤1 秒的窗口"，
    低估了后果：窗口是 1 秒，奖品是 7 天。

    上面 test_old_token_revoked 里那句 time.sleep(1.1) 正是为绕开这个洞才加的，
    也就是说测试套永远碰不到它。这里不 sleep，专门钉住那一秒。
    """

    def _signup(self, client, email):
        client.post("/api/auth/register", json={"email": email, "password": "password123"})
        r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
        return r.json()["token"]

    def test_same_second_stolen_token_is_revoked(self, client):
        email = "samesec@example.com"
        owner = self._signup(client, email)
        # 同一秒内再登录一次，模拟"攻击者此刻偷到一把"
        stolen = client.post(
            "/api/auth/login", json={"email": email, "password": "password123"}
        ).json()["token"]

        r = client.post(
            "/api/auth/password/change",
            headers=_h(owner),
            json={"current_password": "password123", "new_password": "newpassword456"},
        )
        assert r.status_code == 200
        fresh = r.json()["token"]

        # 不 sleep：这正是原先漏掉的那一秒
        assert client.get("/api/usage", headers=_h(stolen)).status_code == 401
        # 而本人这把新令牌必须活着——向上取整若不配合 create_token(issued_at=)，
        # 这里会 401，表现为"改完密码当场掉线"。两者是一对，缺一不可。
        assert client.get("/api/usage", headers=_h(fresh)).status_code == 200

    def test_revoke_then_issue_order_is_load_bearing(self, client):
        """顺序保证本身要能被测出来。

        原先 test_old_token_revoked 里"新令牌可用"那句断言无法捕捉顺序反转：
        变异把 revoke 挪到 create_token 之后，测试照样全绿（因为同秒取整让
        iat == revoked_at 仍然通过）。改成向上取整之后，顺序反转会让新令牌
        的 iat 落在撤销点之前，这条就真的红了。
        """
        email = "order@example.com"
        t = self._signup(client, email)
        r = client.post(
            "/api/auth/password/change",
            headers=_h(t),
            json={"current_password": "password123", "new_password": "newpassword456"},
        )
        fresh = r.json()["token"]
        assert client.get("/api/usage", headers=_h(fresh)).status_code == 200
