"""多租户形态下，共享匿名桶不得读写个人数据。

这条缺陷是实测出来的，不是推演：AL_AUTH_ENABLED=true 的实例上，用一个
**全新的、不带任何令牌**的上下文直接请求后端，拿到了 15 条评审的标题
和 54 条判断记录的结论原文——那些都是别的未登录访客留下的。

根因：optional_identity 在没有有效 token 时回落到 settings.anonymous_user_id，
而这个值对所有未登录访客是同一个。于是「按 user_id 过滤」写得再对也没用，
因为大家的 user_id 本来就相等。config._validate_startup 里那道检查只在
auth_enabled=false 时报错，恰好漏掉了 auth_enabled=true 的未登录访客。

为什么这类缺陷此前 360+ 条测试全绿也没抓到：测试环境 auth_enabled 默认 false，
匿名断言写的是「匿名能看到自己的数据」——在共享桶里，「自己的」和「所有人的」
返回的是同一个结果，测试无法区分。所以下面每条测试都**显式打开认证**，
并且成对地验证单机形态（auth_enabled=false）不被误伤。
"""

import pytest

from app.config import settings


def _enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


def _register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


# 未登录访客不该读到的个人数据接口。共同点：都按 user_id 过滤，
# 而共享桶里 user_id 对所有人相等，过滤等于没过滤。
# /api/usage 曾漏挂 require_isolated_identity——未登录访客能读到全站未登录
# 用户加起来的用量与成本（spec 3.6）。
PRIVATE_READ_ENDPOINTS = [
    "/api/ledger/judgments",
    "/api/ledger/hit-rate",
    "/api/ledger/leaderboard",
    "/api/validation/metrics",
    "/api/usage",
]


class TestSharedAnonymousIsBlocked:
    @pytest.mark.parametrize("path", PRIVATE_READ_ENDPOINTS)
    def test_private_reads_rejected_for_shared_anonymous(self, client, monkeypatch, path):
        _enable_auth(monkeypatch)
        r = client.get(path)
        assert r.status_code == 401, (
            f"{path} 对未登录访客返回了 {r.status_code}，"
            f"共享匿名桶下这等于把别人的数据给了他：{r.text[:200]}"
        )

    def test_review_list_is_empty_not_other_peoples(self, client, monkeypatch):
        """列表要返回空 + 标记，而不是 401——侧栏在轮询它，报错会把整页打成错误态。"""
        _enable_auth(monkeypatch)
        r = client.get("/api/reviews?limit=100")
        assert r.status_code == 200
        assert r.json() == [], "未登录访客不该列出任何评审（那些是别人的）"
        assert r.headers.get("X-Requires-Login") == "1", "要给前端一个可据此提示的信号"
        assert r.headers.get("X-Total-Count") == "0"

    def test_saving_api_key_rejected(self, client, monkeypatch):
        """API Key 落进共享桶 = 把自己的付费凭据交给所有访客。"""
        _enable_auth(monkeypatch)
        r = client.post("/api/keys", json={"api_key": "sk-ant-fake-key-value", "provider": "anthropic"})
        assert r.status_code == 401, r.text

    def test_deleting_api_key_rejected(self, client, monkeypatch):
        _enable_auth(monkeypatch)
        r = client.delete("/api/keys/anthropic")
        assert r.status_code == 401, r.text

    def test_testing_stored_key_rejected(self, client, monkeypatch):
        """不传 api_key 会解密并真的拿去调模型——那把 key 是别人的。"""
        _enable_auth(monkeypatch)
        r = client.post("/api/keys/test", json={"provider": "anthropic"})
        assert r.status_code == 401, r.text

    def test_key_listing_hides_other_peoples_keys(self, client, monkeypatch):
        """GET /keys 不报错（设置页要能打开），但绝不能回显桶里别人的 key——
        连掩码和 provider 都不行，那等于告诉访客「这儿有把能用的 key」。"""
        _enable_auth(monkeypatch)
        token = _register(client, "keyowner@example.com")
        saved = client.post(
            "/api/keys",
            json={"api_key": "sk-ant-owner-secret-value", "provider": "anthropic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert saved.status_code == 200, saved.text

        r = client.get("/api/keys")
        assert r.status_code == 200
        body = r.json()
        assert body["keys"] == [], "未登录访客看到了别人的 key"
        assert body.get("requires_login") is True


class TestSingleMachineFormStillWorks:
    """auth_enabled=false 是单机开源形态：那台机器就一个人用，
    anonymous 桶就是本人。上面的守卫**不能**误伤这条路径，
    否则所有自建用户一升级就全部用不了。"""

    def test_private_reads_allowed(self, client):
        assert settings.auth_enabled is False, "本测试的前提是默认关闭认证"
        for path in PRIVATE_READ_ENDPOINTS:
            r = client.get(path)
            assert r.status_code == 200, f"{path} 在单机形态下被误伤了：{r.text[:200]}"

    def test_review_list_allowed(self, client):
        r = client.get("/api/reviews?limit=5")
        assert r.status_code == 200
        assert r.headers.get("X-Requires-Login") is None

    def test_key_save_and_delete_allowed(self, client):
        r = client.post(
            "/api/keys", json={"api_key": "sk-ant-local-machine-key", "provider": "anthropic"}
        )
        assert r.status_code == 200, r.text
        assert client.delete("/api/keys/anthropic").status_code == 200


class TestGuestsAreNotCollateralDamage:
    """CDK 兑换出来的游客也走 optional_identity，但他们持 token、有独立
    user_id、is_anonymous=False —— 那是真实且互相隔离的身份，必须照常放行。
    守卫的判定条件因此是 user_id == anonymous_user_id，而不是 is_anonymous。"""

    def test_is_shared_anonymous_distinguishes_guest_from_shared_bucket(self):
        from app.deps import Identity, is_shared_anonymous

        shared = Identity(user_id=settings.anonymous_user_id, is_anonymous=True)
        guest = Identity(user_id="guest-abc123", is_anonymous=False)
        member = Identity(user_id="user-1", email="a@b.com", is_anonymous=False)

        assert is_shared_anonymous(shared) is True
        assert is_shared_anonymous(guest) is False
        assert is_shared_anonymous(member) is False
