"""每个未登录访客一个游客身份：数据不再跨访客共享。

缺陷：AL_AUTH_ENABLED=true 的实例上，不带令牌的请求一律解析成同一个
user_id="anonymous"（GET /api/auth/me 实测返回 anonymous）。游客身份只在
「首次发起评审 / 兑换 CDK」时才铸造，在那之前的对话、项目、上传全部写进
共享桶——/api/v2/conversations、/api/v2/projects 返回的是全站未登录访客的数据，
v1 /api/reviews/{id} 对 anonymous 行按字符串相等放行，谁都能读、能删。

修复后的口径（deps.resolve_guest_identity）：
  · 第一次没有会话的请求就铸造游客（真实 User 行，is_guest=True），
    凭证是 HttpOnly + SameSite=Lax 的签名 cookie；
  · 带着 cookie 的后续请求保持同一个身份；
  · 任何接口都不会再返回别的游客、或 legacy "anonymous" 名下的数据；
  · 登录后认领只搬**当前这个游客**名下的数据。

两个访客 = 两个 TestClient（各自一份 cookie jar），和两台浏览器一样互不相干。
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings


@pytest.fixture(autouse=True)
def _multi_tenant(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


@pytest.fixture(autouse=True)
def _cleanup(db):
    yield
    from app.models import (
        Conversation,
        CreditLedger,
        Judgment,
        Project,
        Review,
        ReviewFeedback,
        UploadedFile,
        UsageRecord,
        User,
    )

    for model in (
        ReviewFeedback, Judgment, UsageRecord, CreditLedger, UploadedFile,
        Conversation, Project, Review, User,
    ):
        db.query(model).delete()
    db.commit()


@pytest.fixture
def visitor_a():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def visitor_b():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _me(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200, r.text
    return r.json()


def _guest_id(client):
    me = _me(client)
    assert me["is_guest"] is True and me["is_anonymous"] is False, me
    return me["user_id"]


def _review(db, user_id, title="评审"):
    from app.models import Review

    row = Review(
        user_id=user_id,
        task_type="concept_review",
        target_title=title,
        artifact_bundle={"title": title, "materials": [{"type": "text", "text": "x"}]},
        status="completed",
        report_json={"executive_summary": {"release_risk": "medium"}},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def _register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---------------------------------------------------------------------------
# 身份本身
# ---------------------------------------------------------------------------


class TestGuestCookie:
    def test_request_without_cookie_gets_a_new_guest_id(self, visitor_a):
        r = visitor_a.get("/api/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] != settings.anonymous_user_id
        assert body["is_guest"] is True
        assert body["email"] is None, "合成的 guest-xxx@guest.local 不该回给前端"

        cookie = r.headers.get("set-cookie", "")
        assert cookie.startswith(f"{settings.guest_cookie_name}="), cookie
        lowered = cookie.lower()
        assert "httponly" in lowered
        assert "samesite=lax" in lowered
        assert "path=/" in lowered

    def test_request_with_cookie_keeps_the_same_id(self, visitor_a):
        first = _guest_id(visitor_a)
        r = visitor_a.get("/api/auth/me")
        assert r.json()["user_id"] == first
        assert "set-cookie" not in r.headers, "已有有效 cookie 时不该再铸造"

    def test_two_visitors_get_different_ids(self, visitor_a, visitor_b):
        assert _guest_id(visitor_a) != _guest_id(visitor_b)

    def test_forged_cookie_is_ignored_and_replaced(self, visitor_a, visitor_b):
        """cookie 是签名令牌而不是裸 id：把别人的 user_id 塞进 cookie 冒充不了他。"""
        victim = _guest_id(visitor_b)
        visitor_a.cookies.set(settings.guest_cookie_name, victim)
        me = _me(visitor_a)
        assert me["user_id"] != victim

    def test_secure_flag_follows_setting(self, visitor_a, monkeypatch):
        monkeypatch.setattr(settings, "guest_cookie_secure", True)
        r = visitor_a.get("/api/auth/me")
        assert "secure" in r.headers.get("set-cookie", "").lower()

    def test_cookie_never_authenticates_a_full_account(self, visitor_a, db):
        """游客 cookie 只认游客：转正后的账号必须走 Authorization 头。"""
        from app.models import User

        gid = _guest_id(visitor_a)
        user = db.get(User, gid)
        user.is_guest = False
        db.commit()
        assert _me(visitor_a)["user_id"] != gid

    def test_single_machine_form_is_unchanged(self, visitor_a, monkeypatch):
        """认证关闭（单机开源形态）时仍是 anonymous，也不发 cookie。"""
        monkeypatch.setattr(settings, "auth_enabled", False)
        r = visitor_a.get("/api/auth/me")
        assert r.json()["user_id"] == settings.anonymous_user_id
        assert "set-cookie" not in r.headers

    def test_identity_minting_is_capped_per_source_and_never_falls_back(
        self, monkeypatch
    ):
        """刷身份被 429 拦住，而不是悄悄回落到共享 anonymous 桶。"""
        from app.main import app

        monkeypatch.setattr(settings, "ratelimit_enabled", True)
        monkeypatch.setattr(settings, "guest_identity_per_hour", 2)
        codes = []
        for _ in range(3):
            with TestClient(app) as fresh:
                codes.append(fresh.get("/api/auth/me").status_code)
        assert codes == [200, 200, 429]

    def test_trial_budget_exhaustion_still_mints_isolated_guests(self, monkeypatch, db):
        """试用闸（每来源每天 3 个）用完后照样发身份，只是不再送试用次数。"""
        from app.main import app
        from app.models import User

        monkeypatch.setattr(settings, "ratelimit_enabled", True)
        credits = []
        for _ in range(4):
            with TestClient(app) as fresh:
                uid = _guest_id(fresh)
            db.expire_all()
            credits.append(db.get(User, uid).guest_review_credits)
        assert credits == [3, 3, 3, 0]


# ---------------------------------------------------------------------------
# 对话 / 项目 / 评审：A 碰不到 B 的东西
# ---------------------------------------------------------------------------


class TestConversationsAreIsolated:
    def test_list_read_update_delete(self, visitor_a, visitor_b):
        conv = visitor_b.post("/api/v2/conversations", json={"title": "B 的对话"}).json()
        cid = conv["id"]

        assert visitor_a.get("/api/v2/conversations").json()["conversations"] == []
        assert visitor_a.get(f"/api/v2/conversations/{cid}").status_code == 404
        assert visitor_a.patch(f"/api/v2/conversations/{cid}", json={"title": "改"}).status_code == 404
        assert (
            visitor_a.post(
                f"/api/v2/conversations/{cid}/messages", json={"role": "user", "content": "x"}
            ).status_code
            == 404
        )
        assert visitor_a.delete(f"/api/v2/conversations/{cid}").status_code == 404

        mine = visitor_b.get("/api/v2/conversations").json()["conversations"]
        assert [c["id"] for c in mine] == [cid]
        assert visitor_b.get(f"/api/v2/conversations/{cid}").json()["title"] == "B 的对话"


class TestProjectsAreIsolated:
    def test_list_update_delete(self, visitor_a, visitor_b):
        pid = visitor_b.post("/api/v2/projects", json={"name": "B 的项目"}).json()["id"]

        assert visitor_a.get("/api/v2/projects").json()["projects"] == []
        assert visitor_a.patch(f"/api/v2/projects/{pid}", json={"name": "改"}).status_code == 404
        assert visitor_a.delete(f"/api/v2/projects/{pid}").status_code == 404
        assert [p["id"] for p in visitor_b.get("/api/v2/projects").json()["projects"]] == [pid]

    def test_cannot_attach_own_conversation_to_someone_elses_project(self, visitor_a, visitor_b):
        pid = visitor_b.post("/api/v2/projects", json={"name": "B 的项目"}).json()["id"]
        cid = visitor_a.post("/api/v2/conversations", json={}).json()["id"]
        r = visitor_a.patch(f"/api/v2/conversations/{cid}", json={"project_id": pid})
        assert r.status_code == 404


class TestReviewsAreIsolated:
    def test_list_read_delete_v1_and_v2(self, visitor_a, visitor_b, db):
        rid = _review(db, _guest_id(visitor_b), "B 的评审")
        _guest_id(visitor_a)

        assert visitor_a.get("/api/reviews?limit=100").json() == []
        for path in (
            f"/api/reviews/{rid}",
            f"/api/reviews/{rid}/report",
            f"/api/reviews/{rid}/result",
            f"/api/v2/reviews/{rid}",
            f"/api/v2/reviews/{rid}/chat",
        ):
            assert visitor_a.get(path).status_code == 404, path
        assert visitor_a.delete(f"/api/reviews/{rid}").status_code == 404

        listed = visitor_b.get("/api/reviews?limit=100").json()
        assert [r["id"] for r in listed] == [rid]
        assert visitor_b.get(f"/api/reviews/{rid}").status_code == 200

    def test_cannot_link_someone_elses_review_to_own_conversation(self, visitor_a, visitor_b, db):
        rid = _review(db, _guest_id(visitor_b))
        cid = visitor_a.post("/api/v2/conversations", json={}).json()["id"]
        r = visitor_a.patch(f"/api/v2/conversations/{cid}", json={"review_id": rid})
        assert r.status_code == 404


class TestUsageAndCreditsArePerGuest:
    def test_usage(self, visitor_a, visitor_b, db):
        from app.models import UsageRecord

        db.add(UsageRecord(user_id=_guest_id(visitor_b), cost_usd=1.25, key_source="byok"))
        db.commit()
        _guest_id(visitor_a)

        a = visitor_a.get("/api/usage")
        assert a.status_code == 200, a.text
        assert a.json()["cost_usd_total"] == 0
        assert visitor_b.get("/api/usage").json()["cost_usd_total"] == 1.25

    def test_cdk_balance(self, visitor_a, visitor_b, db):
        from app.models import CreditLedger

        db.add(CreditLedger(user_id=_guest_id(visitor_b), delta=10, reason="cdk_redeem"))
        db.commit()
        _guest_id(visitor_a)

        assert visitor_a.get("/api/usage").json()["bonus_credits"] == 0
        assert visitor_b.get("/api/usage").json()["bonus_credits"] == 10


# ---------------------------------------------------------------------------
# legacy anonymous 行：谁都看不到
# ---------------------------------------------------------------------------


class TestLegacyAnonymousRowsAreInvisible:
    def _seed(self, db):
        from app.models import Conversation, CreditLedger, Project, Review

        rid = _review(db, settings.anonymous_user_id, "共享桶里的评审")
        orphan = _review(db, None, "无主评审")
        conv = Conversation(user_id=settings.anonymous_user_id, title="共享桶里的对话")
        proj = Project(user_id=settings.anonymous_user_id, name="共享桶里的项目")
        db.add_all([conv, proj, CreditLedger(user_id="anonymous", delta=5, reason="cdk_redeem")])
        db.commit()
        return rid, orphan, conv.id, proj.id

    def test_invisible_before_quarantine(self, visitor_a, db):
        rid, orphan, cid, pid = self._seed(db)

        assert visitor_a.get("/api/v2/conversations").json()["conversations"] == []
        assert visitor_a.get("/api/v2/projects").json()["projects"] == []
        assert visitor_a.get("/api/reviews?limit=100").json() == []
        for review_id in (rid, orphan):
            assert visitor_a.get(f"/api/reviews/{review_id}").status_code == 404
            assert visitor_a.get(f"/api/v2/reviews/{review_id}").status_code == 404
            assert visitor_a.delete(f"/api/reviews/{review_id}").status_code == 404
        assert visitor_a.get(f"/api/v2/conversations/{cid}").status_code == 404
        assert visitor_a.get("/api/usage").json()["bonus_credits"] == 0

    def test_claim_cannot_pull_rows_out_of_the_shared_bucket(self, visitor_a, db):
        """以前认领接口会把任意已知 id 的 anonymous 行搬走——现在一条都不搬。"""
        from app.models import Conversation, Project, Review

        rid, orphan, cid, pid = self._seed(db)
        headers = _register(visitor_a, "claim-legacy@example.com")
        r = visitor_a.post(
            "/api/auth/me/claim-reviews",
            json={"review_ids": [rid, orphan], "conversation_ids": [cid], "project_ids": [pid]},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["claimed"] == [] and set(body["rejected"]) == {rid, orphan}
        assert body["claimed_conversations"] == [] and body["claimed_projects"] == []
        db.expire_all()
        assert db.get(Review, rid).user_id == settings.anonymous_user_id
        assert db.get(Conversation, cid).user_id == settings.anonymous_user_id
        assert db.get(Project, pid).user_id == settings.anonymous_user_id

    def test_quarantine_moves_rows_and_is_idempotent(self, db):
        from app.models import Conversation, CreditLedger, Project, Review
        from app.services import guest_service

        rid, orphan, cid, pid = self._seed(db)

        preview = guest_service.quarantine_legacy_anonymous(db, apply=False)
        assert preview["reviews"] == 2 and preview["conversations"] == 1
        assert preview["projects"] == 1 and preview["credit_ledger"] == 1
        db.expire_all()
        assert db.get(Review, rid).user_id == settings.anonymous_user_id, "预览不该改数据"

        guest_service.quarantine_legacy_anonymous(db, apply=True)
        db.expire_all()
        owner = guest_service.QUARANTINE_OWNER
        assert db.get(Review, rid).user_id == owner
        assert db.get(Review, orphan).user_id == owner
        assert db.get(Conversation, cid).user_id == owner
        assert db.get(Project, pid).user_id == owner
        assert db.query(CreditLedger).filter(CreditLedger.user_id == owner).count() == 1
        assert db.query(Review).count() == 2, "隔离不删数据"

        again = guest_service.quarantine_legacy_anonymous(db, apply=True)
        assert sum(again.values()) == 0


# ---------------------------------------------------------------------------
# 登录后认领：只搬当前游客的
# ---------------------------------------------------------------------------


class TestClaimAfterLogin:
    def test_moves_only_this_guests_records(self, visitor_a, visitor_b, db):
        from app.models import Conversation, Judgment, Project, Review, UploadedFile

        a_id = _guest_id(visitor_a)
        b_id = _guest_id(visitor_b)
        a_review = _review(db, a_id, "A 的评审")
        b_review = _review(db, b_id, "B 的评审")
        db.add(Judgment(review_id=a_review, user_id=a_id, claim="A 的判断"))
        db.add(UploadedFile(user_id=a_id, media_type="image/png", ext=".png", byte_size=1, sha256="a"))
        db.commit()
        a_conv = visitor_a.post("/api/v2/conversations", json={"title": "A"}).json()["id"]
        a_proj = visitor_a.post("/api/v2/projects", json={"name": "A"}).json()["id"]
        b_conv = visitor_b.post("/api/v2/conversations", json={"title": "B"}).json()["id"]
        b_proj = visitor_b.post("/api/v2/projects", json={"name": "B"}).json()["id"]

        headers = _register(visitor_a, "claim-a@example.com")
        account = visitor_a.get("/api/auth/me", headers=headers).json()["user_id"]
        r = visitor_a.post(
            "/api/auth/me/claim-reviews",
            # 把 B 的 id 也塞进去：请求体不决定搬什么
            json={
                "review_ids": [a_review, b_review],
                "conversation_ids": [b_conv],
                "project_ids": [b_proj],
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["claimed"] == [a_review]
        assert body["rejected"] == [b_review]
        assert body["claimed_conversations"] == [a_conv]
        assert body["rejected_conversations"] == [b_conv]
        assert body["claimed_projects"] == [a_proj]
        assert body["rejected_projects"] == [b_proj]

        db.expire_all()
        assert db.get(Review, a_review).user_id == account
        assert db.get(Conversation, a_conv).user_id == account
        assert db.get(Project, a_proj).user_id == account
        assert db.query(Judgment).filter(Judgment.user_id == account).count() == 1
        assert db.query(UploadedFile).filter(UploadedFile.user_id == account).count() == 1
        # B 的东西原封不动
        assert db.get(Review, b_review).user_id == b_id
        assert db.get(Conversation, b_conv).user_id == b_id
        assert db.get(Project, b_proj).user_id == b_id

        # 认领后能用正式账号打开，游客 cookie 被清掉
        assert visitor_a.get(f"/api/reviews/{a_review}", headers=headers).status_code == 200
        assert settings.guest_cookie_name not in visitor_a.cookies

    def test_claim_without_guest_cookie_moves_nothing(self, visitor_b, db):
        from app.main import app
        from app.models import Review

        b_review = _review(db, _guest_id(visitor_b))
        with TestClient(app) as stranger:
            headers = _register(stranger, "claim-stranger@example.com")
            stranger.cookies.clear()
            r = stranger.post(
                "/api/auth/me/claim-reviews", json={"review_ids": [b_review]}, headers=headers
            )
        assert r.status_code == 200
        assert r.json()["claimed"] == []
        db.expire_all()
        assert db.get(Review, b_review).user_id != settings.anonymous_user_id

    def test_bind_email_converts_the_cookie_guest_in_place(self, visitor_a, db):
        from app.models import Review

        gid = _guest_id(visitor_a)
        rid = _review(db, gid)
        r = visitor_a.post(
            "/api/auth/bind-email", json={"email": "bound@example.com", "password": "password123"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["user"]["id"] == gid, "同一个 user_id 原地转正"
        headers = {"Authorization": f"Bearer {r.json()['token']}"}
        assert visitor_a.get(f"/api/reviews/{rid}", headers=headers).status_code == 200
        # 旧 cookie 已失效：不带令牌时回到一个新的游客，而不是那个正式账号
        assert settings.guest_cookie_name not in visitor_a.cookies
        assert _me(visitor_a)["user_id"] != gid
