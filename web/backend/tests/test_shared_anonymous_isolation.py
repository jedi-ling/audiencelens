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


def _seed_shared_bucket(db):
    """在 legacy anonymous 桶里放一份"别的访客留下的"数据，返回 (review_id, judgment_id)。"""
    from app.models import Judgment, Review, UsageRecord

    review = Review(
        user_id=settings.anonymous_user_id,
        task_type="concept_review",
        target_title="共享桶里别人的评审",
        artifact_bundle={},
        status="completed",
        report_json={"executive_summary": {"release_risk": "medium"}},
    )
    db.add(review)
    db.commit()
    db.add(Judgment(review_id=review.id, user_id=settings.anonymous_user_id, claim="共享桶里别人的判断"))
    db.add(UsageRecord(user_id=settings.anonymous_user_id, cost_usd=9.5, key_source="server"))
    db.commit()
    judgment = db.query(Judgment).filter(Judgment.review_id == review.id).first()
    return review.id, judgment.id


@pytest.fixture
def _cleanup_seed(db):
    yield
    from app.models import Judgment, Review, UsageRecord, UserApiKey

    db.query(Judgment).delete()
    db.query(UsageRecord).delete()
    db.query(UserApiKey).delete()
    db.query(Review).delete()
    db.commit()


@pytest.mark.usefixtures("_cleanup_seed")
class TestSharedAnonymousIsBlocked:
    """以前这里断言"未登录 → 401"：共享桶唯一安全的处理就是什么都不给。
    现在未登录访客有**自己的**游客身份（deps.resolve_guest_identity），
    这些接口照常返回 200——返回的必须只是他自己的（全新游客 = 空），
    共享桶里别人的东西一个字都不能出现。"""

    @pytest.mark.parametrize("path", PRIVATE_READ_ENDPOINTS)
    def test_private_reads_rejected_for_shared_anonymous(self, client, monkeypatch, db, path):
        _enable_auth(monkeypatch)
        _seed_shared_bucket(db)
        r = client.get(path)
        assert r.status_code == 200, r.text
        assert "共享桶里别人的" not in r.text, f"{path} 把共享桶里别人的数据给了访客：{r.text[:200]}"
        assert client.get("/api/auth/me").json()["user_id"] != settings.anonymous_user_id
        if path == "/api/usage":
            assert r.json()["cost_usd_total"] == 0, "访客看到了全站未登录用户加起来的用量"

    def test_review_list_is_empty_not_other_peoples(self, client, monkeypatch, db):
        _enable_auth(monkeypatch)
        _seed_shared_bucket(db)
        r = client.get("/api/reviews?limit=100")
        assert r.status_code == 200
        assert r.json() == [], "未登录访客不该列出任何评审（那些是别人的）"
        assert r.headers.get("X-Total-Count") == "0"

    def test_saving_api_key_rejected(self, client, monkeypatch):
        """游客可以保存自己的 key（BYOK 发起评审要用），但它只属于这个游客：
        另一个访客（另一份 cookie）看不到、也删不掉。"""
        from fastapi.testclient import TestClient

        from app.main import app

        _enable_auth(monkeypatch)
        r = client.post("/api/keys", json={"api_key": "sk-ant-fake-key-value", "provider": "anthropic"})
        assert r.status_code == 200, r.text
        assert [k["provider"] for k in client.get("/api/keys").json()["keys"]] == ["anthropic"]
        with TestClient(app) as other:
            assert other.get("/api/keys").json()["keys"] == []

    def test_deleting_api_key_rejected(self, client, monkeypatch):
        from fastapi.testclient import TestClient

        from app.main import app

        _enable_auth(monkeypatch)
        client.post("/api/keys", json={"api_key": "sk-ant-fake-key-value", "provider": "anthropic"})
        with TestClient(app) as other:
            other.delete("/api/keys/anthropic")
        assert [k["provider"] for k in client.get("/api/keys").json()["keys"]] == ["anthropic"], (
            "别的访客删掉了这个游客的 key"
        )

    def test_testing_stored_key_rejected(self, client, monkeypatch):
        """/keys/test 是出网探针，游客（自动铸造的身份）一律不开放。"""
        _enable_auth(monkeypatch)
        r = client.post("/api/keys/test", json={"provider": "anthropic"})
        assert r.status_code == 401, r.text

    def test_key_listing_hides_other_peoples_keys(self, client, monkeypatch):
        """GET /keys 不报错（设置页要能打开），但绝不能回显别人的 key——
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
        assert r.json()["keys"] == [], "未登录访客看到了别人的 key"


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


class TestLedgerWritesAreAlsoGuarded:
    """读那侧早就挂了守卫，写这侧漏了两个。

    共享匿名桶下 user_id 对所有未登录访客相等，于是：
      · /ledger/judgments/{id}/verify —— service 层那句 `j.user_id != user_id`
        在他们之间恒等成立，任何访客都能给**别人的**预测盖上"成真了/没成真"
        的章，而命中率、校准曲线、排行榜全都建立在这些回填之上；
      · /validation/reviews/{id}/feedback —— upsert 的键是 (review_id, user_id)，
        任何访客都能改写别人对某次评审的反馈，而那正是 /validation/metrics
        那些"采用率/付费意愿"数字的来源（读那边早就挡住了，写这边没挡）。
    """

    @pytest.mark.usefixtures("_cleanup_seed")
    def test_verify_judgment_rejected_for_shared_anonymous(self, client, monkeypatch, db):
        """以前未登录访客与 anonymous 桶是同一个人，service 层的归属校验恒等成立。
        现在访客是自己的游客：共享桶里的判断对他不存在。"""
        from app.models import Outcome

        _enable_auth(monkeypatch)
        _, judgment_id = _seed_shared_bucket(db)
        r = client.post(
            f"/api/ledger/judgments/{judgment_id}/verify", json={"verdict": "hit"}
        )
        assert r.status_code in (403, 404), (
            f"未登录访客能回填别人的判断：{r.status_code} {r.text[:200]}"
        )
        assert db.query(Outcome).filter(Outcome.judgment_id == judgment_id).count() == 0

    @pytest.mark.usefixtures("_cleanup_seed")
    def test_review_feedback_rejected_for_shared_anonymous(self, client, monkeypatch, db):
        from app.models import ReviewFeedback

        _enable_auth(monkeypatch)
        review_id, _ = _seed_shared_bucket(db)
        r = client.post(
            f"/api/validation/reviews/{review_id}/feedback", json={"useful": True}
        )
        assert r.status_code in (403, 404), (
            f"未登录访客能改写别人的评审反馈：{r.status_code} {r.text[:200]}"
        )
        assert db.query(ReviewFeedback).filter(ReviewFeedback.review_id == review_id).count() == 0

    def test_single_machine_form_still_allows_both(self, client, db):
        """auth_enabled=false 的单机形态不能被这两道守卫误伤。
        （这里只要求"不是 401"——不存在的 id 返回 404 是正常业务结果。）"""
        assert settings.auth_enabled is False
        assert client.post(
            "/api/ledger/judgments/no-such-judgment/verify", json={"verdict": "correct"}
        ).status_code != 401
        assert client.post(
            "/api/validation/reviews/no-such-review/feedback", json={"useful": True}
        ).status_code != 401


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
