"""登出所有设备：POST /api/auth/sessions/revoke-all。

这个功能存在的全部意义是**旧令牌真的用不了了**。如果只测"接口返回 200"，
那测的和被测的一样没用——用户点了按钮、页面提示"已登出所有设备"，
而偷到令牌的人照样能继续用满 7 天 TTL。这是最糟的一类安全功能：
给了虚假的安心感，让人以为处理过了。

所以下面的核心是一条端到端断言：撤销前旧令牌能用 → 撤销后同一把令牌 401。

背景（为什么撤销机制长这样）：JWT 是自签的无状态令牌，服务端不逐个记录会话，
只记一个"撤销时间点"（AuthToken 里 purpose=session_revoke 的那行），
deps 在校验时拒掉所有 iat 早于该点的令牌。
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


def _signup(client, email, password="password123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}
    ).json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


class TestRevokeAllSessions:
    def test_old_token_stops_working_after_revoke(self, client):
        """**本文件的核心断言。**

        没有这条，"登出所有设备"就是个安慰剂按钮：页面提示成功，
        而被盗的令牌照样通行满一个 TTL。
        """
        token = _signup(client, "revoke-core@example.com")

        # 撤销前：这把令牌是能用的
        assert client.get("/api/auth/me", headers=_h(token)).json()["is_anonymous"] is False

        r = client.post("/api/auth/sessions/revoke-all", headers=_h(token))
        assert r.status_code == 200
        assert r.json() == {"revoked": True}

        # 撤销后：同一把令牌必须失效
        after = client.get("/api/keys", headers=_h(token))
        assert after.status_code == 401, (
            "撤销之后旧令牌仍然可用——「登出所有设备」没有真的登出任何设备。"
            "用户点完按钮会以为已经安全了，而偷到令牌的人还能用满 7 天。"
        )

    def test_revokes_other_devices_too(self, client):
        """多设备场景：在 A 上点撤销，B 上的会话也要失效。

        这才是这个按钮的实际用途——用户怀疑「别的地方有人登着我的号」。

        设备 B 的令牌用 create_token 显式指定一个**更早**的 iat 来构造，
        而不是再调一次 /login：JWT 的载荷只有 sub/iat/exp，同一秒内两次登录
        会得到逐字节相同的令牌（同 payload 同签名），拿它当"另一台设备"
        测不出任何东西。指定更早的 iat 才真实还原"先在另一台机器登过"。
        """
        from app.core.security import create_token

        email = "revoke-multi@example.com"
        device_a = _signup(client, email)
        uid = client.get("/api/auth/me", headers=_h(device_a)).json()["user_id"]

        # 一小时前在另一台设备登录留下的令牌
        device_b = create_token(
            uid, settings.jwt_secret, settings.jwt_ttl_seconds,
            issued_at=int(__import__("time").time()) - 3600,
        )
        assert device_b != device_a
        assert client.get("/api/keys", headers=_h(device_b)).status_code == 200, (
            "前置条件失效：构造的旧令牌本来就用不了"
        )

        client.post("/api/auth/sessions/revoke-all", headers=_h(device_a))

        assert client.get("/api/keys", headers=_h(device_b)).status_code == 401, (
            "在设备 A 上登出所有设备，设备 B 的会话却还活着"
        )

    def test_user_can_log_in_again_afterwards(self, client):
        """撤销的是已签发的令牌，不是账号——重新登录必须照常可用。

        搞错这一点会变成"点一下按钮把自己永久锁在外面"。
        """
        email = "revoke-relogin@example.com"
        token = _signup(client, email)
        client.post("/api/auth/sessions/revoke-all", headers=_h(token))

        fresh = client.post(
            "/api/auth/login", json={"email": email, "password": "password123"}
        )
        assert fresh.status_code == 200
        assert client.get("/api/keys", headers=_h(fresh.json()["token"])).status_code == 200

    def test_byok_key_survives_revocation(self, client, db):
        """撤销会话不该动用户的数据。

        写这条是因为"登出所有设备"很容易被误实现成"清理该用户的凭据"，
        顺手把 BYOK 密钥也删了——那是数据丢失，不是安全措施。
        """
        from app.services import key_service

        email = "revoke-keeps-key@example.com"
        token = _signup(client, email)
        uid = client.get("/api/auth/me", headers=_h(token)).json()["user_id"]
        client.post(
            "/api/keys",
            json={"api_key": "sk-ant-should-survive-revocation-0123456789", "provider": "anthropic"},
            headers=_h(token),
        )

        client.post("/api/auth/sessions/revoke-all", headers=_h(token))

        # 重新登录后 key 还在，且还能解出来用
        again = client.post(
            "/api/auth/login", json={"email": email, "password": "password123"}
        ).json()["token"]
        assert client.get("/api/keys", headers=_h(again)).json()["keys"], (
            "撤销会话把用户的 BYOK 密钥也弄没了——那是数据丢失，不是安全措施"
        )
        assert key_service.resolve_key(db, uid).key, "密钥还在但解不开了"
        key_service.delete_user_key(db, uid)

    def test_anonymous_cannot_revoke(self, client):
        """未登录不能调——否则任何人都能把共享匿名桶里的所有人踢下线。

        状态码是 400 而不是 401：走的是 _require_own_identity，
        它对"匿名身份不是某个人"这件事的语义就是 BadRequest。
        这里只钉住**被拒绝**，不钉具体码——码变了不影响安全性。
        """
        r = client.post("/api/auth/sessions/revoke-all")
        assert r.status_code >= 400, "未登录竟然能触发撤销"
        assert r.status_code < 500, "应该是客户端错误，不是把服务端打崩"

    def test_cannot_revoke_someone_elses_sessions(self, client):
        """只能撤销自己的。接口不收 user_id 参数，这条是防止将来有人加上去。"""
        victim_email = "revoke-victim@example.com"
        victim = _signup(client, victim_email)
        attacker = _signup(client, "revoke-attacker@example.com")

        # 攻击者用自己的令牌调，并尝试通过 body 指定受害者（当前接口不收，
        # 但要钉住"即使传了也无效"）
        client.post(
            "/api/auth/sessions/revoke-all",
            json={"user_id": "whatever", "email": victim_email},
            headers=_h(attacker),
        )

        assert client.get("/api/keys", headers=_h(victim)).status_code == 200, (
            "别人调 revoke-all 把受害者的会话也撤销了——成了一个免费的拒绝服务手段"
        )
