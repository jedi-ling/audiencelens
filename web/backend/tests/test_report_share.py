"""评审报告的只读分享链接。

每条正向断言都配了反向对照。只测"能生成链接、链接能打开"的话，下面这些实现
同样能全绿，而它们各自都是事故：

  · 不校验归属 —— 任何人凭 review id 就能把别人未发布的产品材料公开出去
  · 归属校验回 403 —— 等于确认"这个 id 存在，只是不归你"，可用来枚举
  · 撤销只是前端不显示 —— 已发出的链接还能打开，"撤销"是个假动作
  · 公开响应顺手带上 user_id / 费用 / 原始材料 —— 分享报告变成公开作者账单
  · 匿名也能建链接 —— 跑评审 → 给自己建个链接 → 打开 → 完整报告，
    登录墙（report_gating）当场作废。这条是本文件最重要的一个测试。
  · 未完成的评审也能分享 —— 对方打开一个空壳，且 error_message 可能带材料片段
"""

import pytest

from app.models import Review


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


def _make_review(db, user_id, status="completed", **kw):
    """直接落库造一份评审——跑真实评审要调 LLM，测分享链路没必要。"""
    review = Review(
        user_id=user_id,
        task_type="concept_review",
        artifact_bundle={"secret_material": "还没发布的定价策略"},
        status=status,
        target_title="我的新游戏",
        report_json={"executive_summary": {"primary_recommendation": "再打磨一轮"}},
        report_markdown="# 报告全文镜像",
        total_cost_usd=1.23,
        input_tokens=4567,
        output_tokens=890,
        project_key="内部项目代号",
        **kw,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review.id


def _me(client, token):
    return client.get("/api/auth/me", headers=_h(token)).json()["user_id"]


class TestCreateAndView:
    def test_share_link_is_readable_without_any_token(self, client, db):
        """核心用途：把链接发给合伙人，对方没有账号也能打开。"""
        t = _signup(client, "share-a@example.com")
        rid = _make_review(db, _me(client, t))

        r = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t))
        assert r.status_code == 200, r.text
        share_token = r.json()["share_token"]
        assert share_token

        # 不带任何 Authorization —— 这就是"发给别人"的真实场景
        got = client.get(f"/api/v2/shared/{share_token}")
        assert got.status_code == 200, got.text
        assert got.json()["target_title"] == "我的新游戏"
        assert got.json()["report"]["executive_summary"]["primary_recommendation"] == "再打磨一轮"

    def test_creating_twice_returns_the_same_token(self, client, db):
        """幂等。否则用户再点一次分享，昨天发出去的链接就静默失效了。"""
        t = _signup(client, "share-idem@example.com")
        rid = _make_review(db, _me(client, t))
        first = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t)).json()["share_token"]
        second = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t)).json()["share_token"]
        assert first == second

    def test_token_is_long_and_random(self, client, db):
        """两份评审的 token 必须不同，且长到不可枚举。"""
        t = _signup(client, "share-rand@example.com")
        uid = _me(client, t)
        a = client.post(f"/api/v2/reviews/{_make_review(db, uid)}/share", headers=_h(t)).json()["share_token"]
        b = client.post(f"/api/v2/reviews/{_make_review(db, uid)}/share", headers=_h(t)).json()["share_token"]
        assert a != b
        assert len(a) >= 32

    def test_unknown_token_is_404(self, client):
        assert client.get("/api/v2/shared/not-a-real-token").status_code == 404


class TestNoLeak:
    def test_public_view_hides_owner_billing_and_raw_material(self, client, db):
        """公开视图是白名单。这条测试就是那份白名单的可执行版本。"""
        t = _signup(client, "share-leak@example.com")
        rid = _make_review(db, _me(client, t))
        share_token = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t)).json()["share_token"]

        body = client.get(f"/api/v2/shared/{share_token}").json()

        # 作者身份不该跟着报告走
        assert "user_id" not in body
        assert "email" not in body
        # 账单是作者的事，跟看报告的人无关
        assert "total_cost_usd" not in body
        assert "input_tokens" not in body
        assert "output_tokens" not in body
        # 最敏感的一坨：用户上传的原始材料
        assert "artifact_bundle" not in body
        # 与 report 同源的全文镜像，白给一份等于扩大暴露面
        assert "report_markdown" not in body
        # 作者给自己项目起的代号，可能暴露其他在做的东西
        assert "project_key" not in body
        # 对外标识就是 token，评审 id 没必要出现
        assert "id" not in body

        # 反向对照：确认上面那些字段在库里**确实有值**——否则这条测试可能只是
        # 在为一份本来就空的记录鼓掌，白名单漏了也测不出来。
        raw = db.get(Review, rid)
        assert raw.total_cost_usd == 1.23
        assert raw.artifact_bundle["secret_material"] == "还没发布的定价策略"
        assert raw.project_key == "内部项目代号"

    def test_serialized_body_contains_no_secret_substring(self, client, db):
        """整包序列化后做一次子串搜索——防止敏感内容从某个我没想到的
        嵌套字段里漏出去（白名单只挡顶层键，挡不住 report 里混进材料原文）。"""
        t = _signup(client, "share-substr@example.com")
        rid = _make_review(db, _me(client, t))
        share_token = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t)).json()["share_token"]

        text = client.get(f"/api/v2/shared/{share_token}").text
        assert "还没发布的定价策略" not in text
        assert "内部项目代号" not in text


class TestOwnership:
    def test_other_user_cannot_share_my_review(self, client, db):
        """反向对照：这里若是 200，任何人凭 id 就能把别人的报告公开出去。"""
        a = _signup(client, "share-own-a@example.com")
        b = _signup(client, "share-own-b@example.com")
        rid = _make_review(db, _me(client, a))

        r = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(b))
        assert r.status_code == 404
        # 必须是 404 而不是 403——403 等于确认该 id 存在
        assert r.status_code != 403
        assert db.get(Review, rid).share_token is None

    def test_other_user_cannot_revoke_my_share(self, client, db):
        a = _signup(client, "share-rev-a@example.com")
        b = _signup(client, "share-rev-b@example.com")
        rid = _make_review(db, _me(client, a))
        share_token = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(a)).json()["share_token"]

        assert client.delete(f"/api/v2/reviews/{rid}/share", headers=_h(b)).status_code == 404
        # 链接仍然有效——别人撤不掉我的
        assert client.get(f"/api/v2/shared/{share_token}").status_code == 200


class TestRevoke:
    def test_revoked_link_stops_working_immediately(self, client, db):
        t = _signup(client, "share-revoke@example.com")
        rid = _make_review(db, _me(client, t))
        share_token = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t)).json()["share_token"]
        assert client.get(f"/api/v2/shared/{share_token}").status_code == 200

        assert client.delete(f"/api/v2/reviews/{rid}/share", headers=_h(t)).status_code == 200

        # 撤销必须是真的失效，不能只是前端不显示
        assert client.get(f"/api/v2/shared/{share_token}").status_code == 404

    def test_resharing_after_revoke_issues_a_new_token(self, client, db):
        """撤销再分享要换一把新钥匙——否则"撤销"只是暂时关灯，
        旧链接的持有者等作者再点一次分享就又能进来了。"""
        t = _signup(client, "share-recycle@example.com")
        rid = _make_review(db, _me(client, t))
        old = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t)).json()["share_token"]
        client.delete(f"/api/v2/reviews/{rid}/share", headers=_h(t))
        new = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t)).json()["share_token"]

        assert new != old
        assert client.get(f"/api/v2/shared/{old}").status_code == 404
        assert client.get(f"/api/v2/shared/{new}").status_code == 200


class TestLoginWallNotBypassable:
    def test_anonymous_cannot_create_a_share_link(self, client, db):
        """本文件最重要的一条。

        匿名用户看自己的报告是被 report_gating 裁剪过的（登录墙）。如果匿名
        能建分享链接，那"跑评审 → 给自己建链接 → 打开"就是一条完整的绕过路径，
        整套「登录看详情」的产品设计当场作废。
        """
        rid = _make_review(db, "anonymous")

        r = client.post(f"/api/v2/reviews/{rid}/share")  # 不带任何 token
        assert r.status_code == 401, r.text
        assert db.get(Review, rid).share_token is None

    def test_shared_report_is_not_gated(self, client, db):
        """反过来说：作者是登录用户时，分享出去的就该是完整报告——
        否则这个功能没有意义（发给合伙人一份被裁剪的报告）。"""
        t = _signup(client, "share-full@example.com")
        rid = _make_review(db, _me(client, t))
        share_token = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t)).json()["share_token"]

        body = client.get(f"/api/v2/shared/{share_token}").json()
        assert body["report"].get("is_gated") is not True


class TestStatusGate:
    @pytest.mark.parametrize("status", ["pending", "running", "failed"])
    def test_unfinished_review_cannot_be_shared(self, client, db, status):
        t = _signup(client, f"share-status-{status}@example.com")
        rid = _make_review(db, _me(client, t), status=status)
        r = client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t))
        assert r.status_code == 400
        assert db.get(Review, rid).share_token is None


class TestOwnerVisibility:
    def test_owner_sees_share_state_on_their_own_review(self, client, db):
        """报告页要靠这两个字段决定按钮显示「生成链接」还是「已公开 + 撤销」。"""
        t = _signup(client, "share-state@example.com")
        rid = _make_review(db, _me(client, t))

        before = client.get(f"/api/v2/reviews/{rid}", headers=_h(t)).json()
        assert before["share_token"] is None
        assert before["shared_at"] is None

        client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t))

        after = client.get(f"/api/v2/reviews/{rid}", headers=_h(t)).json()
        assert after["share_token"]
        assert after["shared_at"]

    def test_v1_detail_also_carries_share_state(self, client, db):
        """报告页读的是 v1 /api/reviews/{id}，不是 v2——两个端点都得带上分享状态，
        否则页面拿不到 token，按钮永远显示"未分享"。"""
        t = _signup(client, "share-v1@example.com")
        rid = _make_review(db, _me(client, t))
        client.post(f"/api/v2/reviews/{rid}/share", headers=_h(t))

        body = client.get(f"/api/reviews/{rid}", headers=_h(t)).json()
        assert body["share_token"]
        assert body["shared_at"]

    def test_share_token_never_reaches_a_different_user(self, client, db):
        """token 只回给作者本人。别人连这份评审都读不到，自然也拿不到 token。"""
        a = _signup(client, "share-tok-a@example.com")
        b = _signup(client, "share-tok-b@example.com")
        rid = _make_review(db, _me(client, a))
        client.post(f"/api/v2/reviews/{rid}/share", headers=_h(a))

        assert client.get(f"/api/reviews/{rid}", headers=_h(b)).status_code in (403, 404)
        assert client.get(f"/api/v2/reviews/{rid}", headers=_h(b)).status_code in (403, 404)
