"""游客体验额度 + 绑定邮箱转正。

覆盖：
  1. 匿名第一次发起评审就铸造独立游客身份（不再共享 anonymous 桶），
     响应里带 guest_token，Review 归属到这个新身份而不是共享桶。
  2. 赠送的 3 次体验额度只挡"服务端垫付"，BYOK 用户不受影响。
  3. 额度用完之后第 4 次评审报 402，文案指向绑邮箱/填自己的 key。
  4. 入队失败要把这次消耗的游客额度退还回去。
  5. 绑定邮箱：成功转正、同一 user_id 历史数据原样带过去、
     重复邮箱/短密码/非游客账号/游客态本身各类拒绝路径。
"""

import pytest

from app.config import settings
from app.models import Review, User
from app.services import guest_service


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.query(Review).delete()
    db.query(User).filter(User.email.like("%@guest.local")).delete(synchronize_session=False)
    db.query(User).filter(User.email == "bound@example.com").delete(synchronize_session=False)
    db.query(User).filter(User.email == "someone-else@example.com").delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def _server_key(monkeypatch):
    """假的平台 key，走 server 分支；key 本身永远不会被真的拿去发请求
    （入队在 _boom 场景里会先炸；正常场景里跑的是真实评审流水线，
     这些测试只关心配额闸，不关心评审本身跑没跑成——见下方对 enqueue_review
     的处理）。"""
    from app.services import key_service

    monkeypatch.setattr(
        key_service,
        "resolve_key",
        lambda db, user_id, provider="anthropic": key_service.ResolvedKey(
            key="sk-fake-never-used", source="server", provider="anthropic",
            model=None, api_base=None,
        ),
    )


@pytest.fixture
def _no_op_enqueue(monkeypatch):
    """评审真正入队之后会被后台 worker/队列处理——这些测试不关心评审结果，
    只关心配额闸和身份铸造，所以把入队 stub 成"成功但什么也不做"，
    不需要真的跑一遍人格评审流水线。"""
    from app.services import review_service

    monkeypatch.setattr(review_service, "enqueue_review", lambda *a, **kw: "job-stub")


def _payload():
    return {
        "task_type": "concept_review",
        "artifact": {"title": "t", "materials": [{"type": "text", "text": "x"}]},
    }


class TestGuestMintingOnFirstReview:
    def test_first_anonymous_review_mints_individual_guest(self, client, db, _server_key, _no_op_enqueue):
        r = client.post("/api/v2/reviews", json=_payload())
        assert r.status_code == 202, r.text
        body = r.json()
        # 身份在这次请求的依赖解析里就铸好了，凭证走 HttpOnly cookie 而不是响应体：
        # guest_token 只在"仍然落到共享匿名桶、需要现场铸造"时才会出现，现在不会了。
        assert settings.guest_cookie_name in r.headers.get("set-cookie", ""), (
            "第一次匿名发起评审必须铸造独立身份并把凭证带回去"
        )
        assert body.get("guest_token") is None

        review = db.query(Review).filter(Review.id == body["review_id"]).first()
        assert review.user_id != settings.anonymous_user_id, "不能继续记进共享匿名桶"

        user = db.query(User).filter(User.id == review.user_id).first()
        assert user.is_guest is True
        assert user.guest_review_credits == guest_service.GUEST_FREE_REVIEWS - 1, (
            "铸造时赠 3 次，这次评审本身也要消耗 1 次"
        )

    def test_second_request_with_guest_token_reuses_same_identity(
        self, client, db, _server_key, _no_op_enqueue
    ):
        first = client.post("/api/v2/reviews", json=_payload()).json()

        # 同一个 client = 同一份 cookie jar = 同一台浏览器
        second_resp = client.post("/api/v2/reviews", json=_payload())
        second = second_resp.json()
        assert "set-cookie" not in second_resp.headers, "已经持有游客 cookie 就不该再铸造新身份"

        r1 = db.query(Review).filter(Review.id == first["review_id"]).first()
        r2 = db.query(Review).filter(Review.id == second["review_id"]).first()
        assert r1.user_id == r2.user_id


class TestGuestFreeReviewGate:
    def test_exhausts_after_three_then_blocked(self, client, db, _server_key, _no_op_enqueue):
        for _ in range(guest_service.GUEST_FREE_REVIEWS):
            r = client.post("/api/v2/reviews", json=_payload())
            assert r.status_code == 202, r.text

        r = client.post("/api/v2/reviews", json=_payload())
        assert r.status_code == 402
        assert r.json()["error"]["code"] == "quota_exceeded"
        assert "邮箱" in r.json()["error"]["message"]

    def test_guest_free_reviews_bypass_platform_credits_mode(
        self, client, db, monkeypatch, _server_key, _no_op_enqueue
    ):
        """回归用例：quota_mode=credits 时 check_quota 会去查 CDK 兑换余额——
        一个刚铸造、从没兑换过 CDK 的游客余额恒为 0，如果两道闸叠着走，
        赠的 3 次从第 1 次就会被"配额已用完"挡下，"赠 3 次"就是一句空话。
        游客只要还有体验额度，必须完全走这条独立闸，不经过 check_quota。"""
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")

        r = client.post("/api/v2/reviews", json=_payload())
        assert r.status_code == 202, r.text

    def test_byok_user_not_gated_by_guest_credits(self, client, db, monkeypatch, _no_op_enqueue):
        """BYOK 走自己的 key，不该被这个只挡"服务端垫付"的闸拦住。"""
        from app.services import key_service

        monkeypatch.setattr(
            key_service,
            "resolve_key",
            lambda db, user_id, provider="anthropic": key_service.ResolvedKey(
                key="sk-user-own-key", source="byok", provider="anthropic",
                model=None, api_base=None,
            ),
        )
        token = None
        for _ in range(guest_service.GUEST_FREE_REVIEWS + 2):
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            r = client.post("/api/v2/reviews", headers=headers, json=_payload())
            assert r.status_code == 202, r.text
            token = token or r.json()["guest_token"]


class TestGuestCreditRefund:
    def test_enqueue_failure_refunds_guest_credit(self, client, db, monkeypatch, _server_key):
        from app.services import review_service

        def boom(*a, **kw):
            raise RuntimeError("queue is down")

        monkeypatch.setattr(review_service, "enqueue_review", boom)

        r = client.post("/api/v2/reviews", json=_payload())
        assert r.status_code >= 500
        token = r.json().get("guest_token")
        # 入队炸的响应体里没有 guest_token 字段（走的是错误处理分支），
        # 直接从库里找刚铸造的那个游客核对余额。
        guest = db.query(User).filter(User.is_guest.is_(True)).order_by(User.created_at.desc()).first()
        assert guest is not None
        assert guest.guest_review_credits == guest_service.GUEST_FREE_REVIEWS, (
            "入队失败必须把消耗掉的那次游客额度还回去"
        )


class TestBindEmail:
    def _mint(self, db):
        return guest_service.mint_guest(db)

    def test_binds_and_preserves_history(self, client, db):
        user_id, token = self._mint(db)
        review = Review(user_id=user_id, task_type="concept_review", artifact_bundle={}, status="completed")
        db.add(review)
        db.commit()

        r = client.post(
            "/api/auth/bind-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "bound@example.com", "password": "password123"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["user"]["email"] == "bound@example.com"

        db.expire_all()
        user = db.query(User).filter(User.id == user_id).first()
        assert user.is_guest is False
        assert user.guest_review_credits is None
        assert user.email == "bound@example.com"

        # 历史评审原样挂在同一个 user_id 下，不需要迁移
        still_there = db.query(Review).filter(Review.id == review.id).first()
        assert still_there.user_id == user_id

    def test_rejects_duplicate_email(self, client, db):
        db.add(User(email="someone-else@example.com", password_hash="x", is_active=True))
        db.commit()

        user_id, token = self._mint(db)
        r = client.post(
            "/api/auth/bind-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "someone-else@example.com", "password": "password123"},
        )
        assert r.status_code == 400

    def test_concurrent_duplicate_email_is_a_400_not_a_500(self, client, db, monkeypatch):
        """预检只挡顺序请求：两个人同时拿同一个邮箱绑定（或一边绑定一边注册），
        都能通过预检，最后靠 users.email 的唯一约束兜底。不捕获就是 500——
        而"这个邮箱不可用"是一个业务结果，必须和预检那条走同一个 400。

        注入点选 hash_password：它在预检之后、commit 之前被调用，
        正好是那个竞态窗口。
        """
        from app.core.security import hash_password as _real
        from app.db import session_scope

        user_id, token = self._mint(db)

        def _inject(secret):
            other = session_scope()
            try:
                if other.query(User).filter(User.email == "bound@example.com").first() is None:
                    other.add(
                        User(email="bound@example.com", password_hash="x", is_active=True)
                    )
                    other.commit()
            finally:
                other.close()
            return _real(secret)

        monkeypatch.setattr(guest_service, "hash_password", _inject)

        r = client.post(
            "/api/auth/bind-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "bound@example.com", "password": "password123"},
        )
        assert r.status_code == 400, f"并发绑定同一邮箱打成了 {r.status_code}：{r.text[:200]}"

        # 抢输的那个游客必须原样留在游客态，不能被改成半吊子状态
        db.expire_all()
        loser = db.get(User, user_id)
        assert loser.is_guest is True
        assert loser.email.endswith("@guest.local")

    def test_rejects_short_password(self, client, db):
        user_id, token = self._mint(db)
        r = client.post(
            "/api/auth/bind-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "bound@example.com", "password": "short"},
        )
        assert r.status_code in (400, 422)

    def test_rejects_non_guest_account(self, client, db):
        client.post("/api/auth/register", json={"email": "already-real@example.com", "password": "password123"})
        token = client.post(
            "/api/auth/login", json={"email": "already-real@example.com", "password": "password123"}
        ).json()["token"]

        r = client.post(
            "/api/auth/bind-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "bound@example.com", "password": "password123"},
        )
        assert r.status_code == 400

        db.query(User).filter(User.email == "already-real@example.com").delete()
        db.commit()

    def test_old_guest_token_stops_working_after_binding(self, client, db):
        """转正必须作废旧的游客 JWT。

        那把令牌有效期 7 天、在 CDK 兑换响应里发出去、躺在浏览器
        localStorage 里，转正之后它认证的是**同一个 user_id**——也就是现在
        这个有真邮箱真密码的正式账号。不作废的话，任何拿到过它的人
        （共用过设备、抓过那次响应、读过 localStorage）都能继续以正式账号
        身份进来，而用户以为自己刚设的密码是这个账号的唯一入口。
        """
        user_id, old_token = self._mint(db)
        r = client.post(
            "/api/auth/bind-email",
            headers={"Authorization": f"Bearer {old_token}"},
            json={"email": "bound@example.com", "password": "password123"},
        )
        assert r.status_code == 200, r.text
        new_token = r.json()["token"]

        # 旧令牌：任何要求登录的接口都必须拒掉它
        stale = client.get("/api/keys", headers={"Authorization": f"Bearer {old_token}"})
        assert stale.status_code == 401, "转正后旧游客令牌仍然有效"
        # /auth/me 是唯一允许 200 的探测口，但必须如实标注令牌失效
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
        assert me.status_code == 200
        assert me.json()["session_expired"] is True

        # 新令牌必须当场可用——撤销点向上取整 + issue_session_token 抬 iat
        # 这对机制只要断一边，用户就会"绑定完当场掉线"
        fresh = client.get("/api/keys", headers={"Authorization": f"Bearer {new_token}"})
        assert fresh.status_code == 200, fresh.text

    def test_guest_synthetic_email_is_not_exposed(self, client, db):
        """游客的 guest-xxxx@guest.local 不是能收信的地址，回给前端只会让人
        以为"我注册过这个邮箱"。QQ 账号同理，而那边泄露的是 openid
        （一个稳定的第三方标识符）。"""
        _, token = self._mint(db)
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        assert me["email"] is None, f"合成占位邮箱被回给了前端：{me['email']}"
        assert "email" in me, "返回 null，而不是把这个键删掉——前端拿它做兜底显示"

    def test_real_email_is_returned_after_binding(self, client, db):
        """挡的是合成邮箱，不是"所有游客转正过来的账号"。绑定之后那是真邮箱。"""
        _, token = self._mint(db)
        r = client.post(
            "/api/auth/bind-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "bound@example.com", "password": "password123"},
        )
        new_token = r.json()["token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).json()
        assert me["email"] == "bound@example.com"

    def test_bound_account_can_login_with_new_credentials(self, client, db):
        user_id, token = self._mint(db)
        client.post(
            "/api/auth/bind-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "bound@example.com", "password": "password123"},
        )
        r = client.post("/api/auth/login", json={"email": "bound@example.com", "password": "password123"})
        assert r.status_code == 200
