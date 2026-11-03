"""匿名期的对话，登录后归到账号名下。

先把这件事的边界说清楚，措辞不能夸大：这**不是**"匿名跨设备"。匿名身份
本就没有可信标识，换台机器谁也认不出你。它做到的是"登录之后归入账号，
此后跨设备可见"——线索是浏览器 localStorage 里的那串 id，清掉就断了。

每条正向断言都配反向对照。只测"能认领"的话，下面这些实现同样能全绿：
  · 认领时不校验当前归属 —— 猜中 id 就能把别人账号里的对话抢走
  · 只带对话来认领被提前 return 吞掉 —— "聊了半天还没开评审就去登录"
    这种最常见的情形永远归不到账号
  · 对话改挂了但图片没改挂 —— 消息还在、file_id 还在，取回接口按归属校验
    全部 404，用户看到的是"登录之后图全丢了"
"""

import io

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


def _anon_conv(client, text="匿名期打的字"):
    """不带 token 建一段对话并说一句话——模拟"还没登录就先聊起来"。"""
    cid = client.post("/api/v2/conversations", json={"title": None}).json()["id"]
    client.post(
        f"/api/v2/conversations/{cid}/messages",
        json={"role": "user", "content": text, "meta": None},
    )
    return cid


class TestClaim:
    def test_anonymous_conversation_becomes_mine(self, client):
        cid = _anon_conv(client, "登录前说的话，登录后必须还在")
        t = _signup(client, "claim-c1@example.com")

        # 反向对照：认领之前，登录身份看不到它
        assert client.get(f"/api/v2/conversations/{cid}", headers=_h(t)).status_code == 404

        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [], "conversation_ids": [cid]},
            headers=_h(t),
        )
        assert r.status_code == 200, r.text
        assert r.json()["claimed_conversations"] == [cid]

        got = client.get(f"/api/v2/conversations/{cid}", headers=_h(t))
        assert got.status_code == 200
        assert got.json()["messages"][0]["content"] == "登录前说的话，登录后必须还在"

    def test_claim_works_with_no_review_ids(self, client):
        """最常见的情形：聊了半天还没开评审就去登录。

        端点原本在 review_ids 为空时提前 return，会把这种请求整个吞掉。
        """
        cid = _anon_conv(client)
        t = _signup(client, "claim-c2@example.com")
        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"conversation_ids": [cid]},  # 完全不带 review_ids
            headers=_h(t),
        )
        assert r.status_code == 200
        assert r.json()["claimed_conversations"] == [cid]

    def test_cannot_steal_another_users_conversation(self, client):
        a = _signup(client, "claim-steal-a@example.com")
        b = _signup(client, "claim-steal-b@example.com")
        cid = client.post("/api/v2/conversations", json={"title": "A 的"}, headers=_h(a)).json()["id"]

        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"conversation_ids": [cid]},
            headers=_h(b),
        )
        assert r.status_code == 200
        # 反向对照：这里若出现在 claimed 里，就是猜中 id 即可抢走他人对话
        assert r.json()["claimed_conversations"] == []
        assert cid in r.json()["rejected_conversations"]
        # 且原主人仍然读得到
        assert client.get(f"/api/v2/conversations/{cid}", headers=_h(a)).status_code == 200

    def test_shows_up_in_my_list_after_claim(self, client):
        cid = _anon_conv(client, "认领后要出现在侧栏")
        t = _signup(client, "claim-list@example.com")
        before = client.get("/api/v2/conversations", headers=_h(t)).json()["conversations"]
        assert all(c["id"] != cid for c in before)

        client.post(
            "/api/auth/me/claim-reviews",
            json={"conversation_ids": [cid]},
            headers=_h(t),
        )
        after = client.get("/api/v2/conversations", headers=_h(t)).json()["conversations"]
        assert any(c["id"] == cid for c in after)


class TestImagesFollowTheConversation:
    def test_claimed_conversation_images_are_still_readable(self, client):
        """对话改挂了但图没改挂 = 登录之后图全变 404。"""
        # 匿名期上传一张图
        up = client.post(
            "/api/uploads",
            files={"file": ("s.png", io.BytesIO(bytes([137, 80, 78, 71]) + b"claimimg"), "image/png")},
        ).json()
        fid, url = up["file_id"], up["url"]

        cid = client.post("/api/v2/conversations", json={"title": None}).json()["id"]
        client.post(
            f"/api/v2/conversations/{cid}/messages",
            json={"role": "user", "content": "看这张图", "meta": {"kind": "images", "fileIds": [fid]}},
        )

        t = _signup(client, "claim-img@example.com")
        # 前置条件：认领前这个账号取不到这张图
        assert client.get(url, headers=_h(t)).status_code == 404

        client.post(
            "/api/auth/me/claim-reviews",
            json={"conversation_ids": [cid]},
            headers=_h(t),
        )
        # 反向对照：只改挂对话、不改挂图片的实现会让这里仍然 404
        assert client.get(url, headers=_h(t)).status_code == 200, "对话认领了但图还留在匿名桶里"

    def test_does_not_claim_unrelated_files(self, client):
        """认领搬的是**当前游客**名下的东西。别的访客（另一份 cookie）上传的图
        绝不能跟着划到自己名下——以前共享匿名桶里大家的文件混在一起，
        所以这里才要"只跟着对话走"；现在边界是游客身份本身。"""
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as stranger:
            other = stranger.post(
                "/api/uploads",
                files={"file": ("o.png", io.BytesIO(bytes([137, 80, 78, 71]) + b"unrelated"), "image/png")},
            ).json()

        cid = _anon_conv(client)  # 这段对话里没有任何图
        t = _signup(client, "claim-img2@example.com")
        client.post(
            "/api/auth/me/claim-reviews",
            json={"conversation_ids": [cid]},
            headers=_h(t),
        )
        assert client.get(other["url"], headers=_h(t)).status_code == 404


class TestLimits:
    def test_rejects_oversized_batch(self, client):
        """上限的意义不是"够不够用"，是别让这个接口变成 uuid 扫描器。"""
        t = _signup(client, "claim-max@example.com")
        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"conversation_ids": [f"id-{i}" for i in range(51)]},
            headers=_h(t),
        )
        assert r.status_code == 400
        # 反向对照：上限之内要放行，别把闸门设成什么都不让过
        r2 = client.post(
            "/api/auth/me/claim-reviews",
            json={"conversation_ids": [f"id-{i}" for i in range(50)]},
            headers=_h(t),
        )
        assert r2.status_code == 200
