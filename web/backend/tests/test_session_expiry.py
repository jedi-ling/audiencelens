"""登录态失效的可见性 + 密码重置吊销旧令牌。

这两条都在修同一个病灶：**失败被伪装成正常结果**。
  · 以前 optional_identity 对失效令牌一律回落匿名，前端拿到 200，
    用户看到的是"评审归属跑了、报告被裁了、历史空了"，却没有任何提示；
  · 以前改完密码不作废旧 JWT，攻击者手上那把偷来的令牌还能再用满 TTL，
    用户以为自己已经把人赶出去了。

核心断言只有一句话：「从来没登录」和「登录过但令牌已失效」必须是两种
可区分的结果，且后者绝不能表现得像前者。
"""

import time

import pytest

from app.config import settings
from app.core.security import create_token


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    """多租户形态才有"登录态"这回事，测试里显式打开。"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


@pytest.fixture
def captured_mail(monkeypatch):
    sent = []
    from app.services import mail_service

    monkeypatch.setattr(
        mail_service, "send_mail", lambda to, subject, body: sent.append((to, subject, body))
    )
    return sent


def _register(client, email, password="password123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _token_from_link(body: str) -> str:
    for part in body.split():
        if "token=" in part:
            return part.split("token=", 1)[1].strip()
    raise AssertionError(f"邮件里没有找到 token: {body}")


class TestExpiredTokenIsDistinguishableFromAnonymous:
    """三种状态各自的表现必须不同：没登录 / 令牌失效 / 正常登录。"""

    def test_no_token_stays_anonymous(self, client):
        """"不登录也能试用"这条产品线不能被这次改动堵死。"""
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["is_anonymous"] is True
        assert body["session_expired"] is False  # 从来没带过令牌，谈不上"过期"

        # 匿名照样能打公开接口。注意不能用 /api/usage 当这个探测口：
        # 用量是"属于你自己的数据"，多租户下未登录访客共用匿名桶，会 401
        # （spec 3.6，见 test_shared_anonymous_isolation.py）
        assert client.get("/api/plans").status_code == 200

    def test_expired_token_is_reported_not_silently_downgraded(self, client, monkeypatch):
        expired = create_token("whoever", settings.jwt_secret, -1)

        # /auth/me 是唯一允许"令牌坏了还返回 200"的探测口——但必须如实说明
        me = client.get("/api/auth/me", headers=_auth(expired))
        assert me.status_code == 200
        body = me.json()
        assert body["is_anonymous"] is True
        assert body["session_expired"] is True  # 与"从来没登录"的区别就在这个字段

        # 其余接口一律 401，绝不当成匿名放行
        r = client.get("/api/usage", headers=_auth(expired))
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "session_expired"

    def test_tampered_and_unknown_user_tokens_also_401(self, client):
        """签名不对 / 用户不存在，与过期同一口径——都是"带了令牌但它不好使"。"""
        bogus = create_token("user-x", "not-the-real-secret", 300)
        assert client.get("/api/usage", headers=_auth(bogus)).status_code == 401

        # 签名对但 sub 指向不存在的用户
        ghost = create_token("no-such-user-id", settings.jwt_secret, 300)
        r = client.get("/api/usage", headers=_auth(ghost))
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "session_expired"

    def test_valid_token_unaffected(self, client):
        token = _register(client, "still-valid@example.com")
        me = client.get("/api/auth/me", headers=_auth(token))
        assert me.status_code == 200
        assert me.json()["is_anonymous"] is False
        assert me.json()["session_expired"] is False
        assert client.get("/api/usage", headers=_auth(token)).status_code == 200

    def test_expired_token_does_not_create_reviews_under_anonymous(self, client):
        """最贵的那个后果：令牌过期后新发起的评审被记到共享匿名桶名下，
        认领不回来。现在这条路走不通了——请求直接 401。"""
        expired = create_token("whoever", settings.jwt_secret, -1)
        r = client.post(
            "/api/v2/reviews",
            headers=_auth(expired),
            json={"task_type": "concept_review", "artifact": {"title": "t", "materials": []}},
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "session_expired"

    def test_garbage_authorization_header_is_treated_as_no_token(self, client):
        """不是 Bearer（比如反代塞进来的 Basic）就当没带令牌，走匿名——
        401 只留给"确实带了一个 Bearer 令牌、但它无效"。"""
        r = client.get("/api/auth/me", headers={"Authorization": "Basic zzz"})
        assert r.status_code == 200
        assert r.json()["session_expired"] is False


class TestPasswordResetRevokesOldTokens:
    def test_old_token_dies_after_reset(self, client, captured_mail):
        old = _register(client, "revoke@example.com", "oldpassword1")
        assert client.get("/api/usage", headers=_auth(old)).status_code == 200

        captured_mail.clear()
        client.post("/api/auth/password/forgot", json={"email": "revoke@example.com"})
        raw = _token_from_link(captured_mail[-1][2])
        # 令牌 iat 只有整秒精度，作废时间点也向下取整到秒——同一秒内签发的
        # 令牌按设计会逃过一劫（见 deps.sessions_revoked_at）。等过一秒再重置，
        # 测的才是"改密码之前签发的令牌"这个真实场景。
        time.sleep(1.1)
        r = client.post(
            "/api/auth/password/reset", json={"token": raw, "new_password": "brandnew123"}
        )
        assert r.status_code == 200

        # 攻击者手上那把旧 token：必须立刻失效，而不是等 TTL 到期
        r = client.get("/api/usage", headers=_auth(old))
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "session_expired"

        me = client.get("/api/auth/me", headers=_auth(old))
        assert me.status_code == 200
        assert me.json()["session_expired"] is True

    def test_new_login_after_reset_works(self, client, captured_mail):
        _register(client, "relogin@example.com", "oldpassword1")
        captured_mail.clear()
        client.post("/api/auth/password/forgot", json={"email": "relogin@example.com"})
        raw = _token_from_link(captured_mail[-1][2])
        time.sleep(1.1)
        client.post("/api/auth/password/reset", json={"token": raw, "new_password": "brandnew123"})

        r = client.post(
            "/api/auth/login", json={"email": "relogin@example.com", "password": "brandnew123"}
        )
        assert r.status_code == 200
        fresh = r.json()["token"]
        # 作废声明不能把重置之后签发的令牌也一起打死，否则用户改完密码登不进来
        assert client.get("/api/usage", headers=_auth(fresh)).status_code == 200
        assert client.get("/api/auth/me", headers=_auth(fresh)).json()["is_anonymous"] is False

    def test_revoke_marker_is_not_usable_as_a_reset_token(self, client, db):
        """作废标记行落在 auth_tokens 里，但它不是任何人手上的令牌：
        purpose 不同，consume 按 purpose 过滤，摘要对应的原文也没人有。"""
        from app.deps import SESSION_REVOKE_PURPOSE, revoke_user_sessions
        from app.models import AuthToken, User
        from app.services import auth_token_service

        user = User(email="marker@example.com", password_hash="x")
        db.add(user)
        db.commit()
        revoke_user_sessions(db, user.id)

        row = (
            db.query(AuthToken)
            .filter(AuthToken.user_id == user.id, AuthToken.purpose == SESSION_REVOKE_PURPOSE)
            .one()
        )
        assert row.used_at is None
        # 即便有人拿到了这一行的 token_hash，也没有对应的原文；而且用途不匹配
        assert (
            auth_token_service.consume(
                db, row.token_hash, auth_token_service.PURPOSE_RESET_PASSWORD
            )
            is None
        )
