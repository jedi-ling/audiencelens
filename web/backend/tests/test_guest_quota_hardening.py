# -*- coding: utf-8 -*-
"""游客链路的三个洞：无限铸造、绕过止血闸、失败时凭空发 CDK 余额。

这三条是同一段代码（create_review_v2 里那段"游客二选一"）的三个侧面，
放在一个文件里测，因为改动其中任何一处都可能把另外两处弄坏：

  1. 铸造游客身份此前完全不限速。身份是免费的，于是"每个游客送 3 次体验"
     实际等于"无限次平台垫付评审"——攻击者写个循环就能一直烧运营者的模型费，
     顺带每次留下一行 users 和一次 200k 轮的 PBKDF2。
     唯一的限制是评审接口那道按 IP 的 20 次/小时，它拦的是别的东西。
  2. 游客路径此前把 check_quota **整段**跳过。要跳过的只有"CDK 余额检查"
     （新铸造的游客余额恒为 0，不跳的话赠的 3 次第 1 次就被挡），
     而一起被跳掉的还有终身 token 额度和 24 小时成本硬闸——那两道保护的是
     运营者的钱包，对平台垫付的游客评审更应该生效。
  3. 游客评审失败时，两条**异步**补偿路径（后台 worker 的失败分支、
     进程重启收尸）退的是 CDK 次数。而游客压根没扣过 CDK：
     cdk_service.refund_credit 只保证"按 review_id 只退一次"，从不核对
     有没有对应的那条 -1。结果是一次失败的游客评审**凭空发一次 CDK 余额**，
     绑定邮箱之后能真的花出去。同步入队失败那条路一直是对的，形成鲜明对照。

另外还有一条相反方向的缺陷：兑过 CDK 的游客**永远花不出去**那些次数
（guest_needs_credit_gate 对 credits=0 同样为真，于是在查余额之前就 402 了），
而 redeem_cdk 的文档承诺"无需注册登录"。见 TestGuestWithCdkCanSpendIt。
"""

import pytest

from app.config import settings
from app.models import CreditLedger, Job, Review, UsageRecord, User
from app.services import cdk_service, guest_service, quota_service


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.query(Review).delete()
    db.query(Job).filter(Job.ref_id.like("guest-hard-%")).delete(synchronize_session=False)
    db.query(UsageRecord).filter(UsageRecord.user_id.like("%")).filter(
        UsageRecord.user_id.in_(
            [row[0] for row in db.query(User.id).filter(User.email.like("%@guest.local")).all()]
        )
    ).delete(synchronize_session=False)
    db.query(CreditLedger).filter(CreditLedger.user_id.like("guest-hard-%")).delete(
        synchronize_session=False
    )
    db.query(User).filter(User.email.like("%@guest.local")).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def _server_key(monkeypatch):
    """假的平台 key：让 resolve_llm_key 走 server 分支。永远不会被真的拿去发请求。"""
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
    from app.services import review_service

    monkeypatch.setattr(review_service, "enqueue_review", lambda *a, **kw: "job-stub")


def _payload():
    return {
        "task_type": "concept_review",
        "artifact": {"title": "t", "materials": [{"type": "text", "text": "x"}]},
    }


def _guest_count(db) -> int:
    return db.query(User).filter(User.email.like("%@guest.local")).count()


# ---------------------------------------------------------------------------
# 1. 铸造本身要限速
# ---------------------------------------------------------------------------


class TestGuestMintingIsRateLimited:
    @pytest.fixture(autouse=True)
    def _limiter_on(self, monkeypatch):
        # 单测默认关限流（conftest 设的 AL_RATELIMIT_ENABLED=false）。
        # 这道闸跟着全局限流总开关走，所以要显式打开才测得到。
        monkeypatch.setattr(settings, "ratelimit_enabled", True)

    def test_same_client_can_only_mint_a_few_per_day(
        self, client, db, _server_key, _no_op_enqueue
    ):
        """每次不带令牌的请求都铸一个新身份、各送 3 次额度，
        不限速的话 "3 次" 这个上限对同一个人毫无约束力。"""
        before = _guest_count(db)
        for i in range(guest_service.GUEST_MINT_PER_DAY):
            r = client.post("/api/v2/reviews", json=_payload())
            assert r.status_code == 202, f"第 {i + 1} 次就被挡了：{r.text}"

        blocked = client.post("/api/v2/reviews", json=_payload())
        assert blocked.status_code == 429, (
            f"同一来源铸了 {guest_service.GUEST_MINT_PER_DAY} 个身份后还能继续铸："
            f"{blocked.status_code}"
        )
        body = blocked.json()["error"]
        assert body["code"] == "rate_limited"
        # 提示必须给出下一步：注册，或者自带 key
        assert "注册" in body["message"] and "API Key" in body["message"]

        assert _guest_count(db) == before + guest_service.GUEST_MINT_PER_DAY, (
            "被拒绝的那次仍然铸了一个身份——攻击者照样能刷 users 行和 PBKDF2"
        )

    def test_holding_a_guest_token_is_not_affected(
        self, client, db, _server_key, _no_op_enqueue
    ):
        """限的是"变出新身份"，不是"已有身份继续用"。
        已经拿到令牌的游客要能把赠送的 3 次用完。"""
        first = client.post("/api/v2/reviews", json=_payload())
        token = first.json()["guest_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for _ in range(guest_service.GUEST_FREE_REVIEWS - 1):
            assert client.post("/api/v2/reviews", headers=headers, json=_payload()).status_code == 202


# ---------------------------------------------------------------------------
# 2. 游客跳过的只有 CDK 余额检查
# ---------------------------------------------------------------------------


class TestGuestsStillHitTheAbuseCeilings:
    def _mint_with_token(self, db):
        return guest_service.mint_guest(db)

    def test_daily_cost_hard_cap_still_applies(
        self, client, db, monkeypatch, _server_key, _no_op_enqueue
    ):
        """24 小时成本硬闸保护的是运营者的钱包，与"有没有买过次数"无关。
        游客花的每一分钱都是平台垫的，这道闸对他们只会更该生效。"""
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "plan")
        monkeypatch.setattr(settings, "quota_free_cost_usd_per_day", 1.0)

        uid, token = self._mint_with_token(db)
        db.add(
            UsageRecord(
                user_id=uid, kind="review", key_source="server", cost_usd=5.0,
                input_tokens=0, output_tokens=0,
            )
        )
        db.commit()

        r = client.post(
            "/api/v2/reviews", headers={"Authorization": f"Bearer {token}"}, json=_payload()
        )
        assert r.status_code == 402, (
            f"游客烧掉 $5 之后还能继续发起平台垫付的评审：{r.status_code} {r.text[:200]}"
        )
        assert "成本额度" in r.json()["error"]["message"]

        db.expire_all()
        assert db.get(User, uid).guest_review_credits == guest_service.GUEST_FREE_REVIEWS, (
            "被成本闸挡下的请求不该消耗游客的体验额度"
        )

    def test_lifetime_token_cap_still_applies(
        self, client, db, monkeypatch, _server_key, _no_op_enqueue
    ):
        """终身 token 额度（AL_QUOTA_TOKENS_TOTAL）是运营者的钱包上限，
        它有自己的开关，与计费模式无关，同样不该被游客路径跳过。"""
        monkeypatch.setattr(settings, "quota_tokens_total", 1000)
        monkeypatch.setattr(settings, "quota_tokens_per_review_estimate", 100)

        uid, token = self._mint_with_token(db)
        db.add(
            UsageRecord(
                user_id=uid, kind="review", key_source="server", cost_usd=0.0,
                input_tokens=900, output_tokens=200,
            )
        )
        db.commit()

        r = client.post(
            "/api/v2/reviews", headers={"Authorization": f"Bearer {token}"}, json=_payload()
        )
        assert r.status_code == 402, f"游客绕过了终身 token 闸：{r.status_code}"

    def test_a_normal_guest_review_still_goes_through(
        self, client, db, monkeypatch, _server_key, _no_op_enqueue
    ):
        """反向保证：止血闸补回来之后，没超任何上限的游客必须照常能跑，
        而且是在 credits 模式下（CDK 余额恒为 0 的那个场景）也能跑——
        这正是当初"整段跳过 check_quota"想解决的问题，不能修坏。"""
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")

        r = client.post("/api/v2/reviews", json=_payload())
        assert r.status_code == 202, r.text


# ---------------------------------------------------------------------------
# 3. 兑过 CDK 的游客必须花得出去
# ---------------------------------------------------------------------------


class TestGuestWithCdkCanSpendIt:
    def test_guest_can_spend_redeemed_credits_after_the_trial(
        self, client, db, monkeypatch, _server_key, _no_op_enqueue
    ):
        """场景（redeem_cdk 的文档明确承诺"无需注册登录"）：
        匿名用户兑了一个 10 次的码 → 铸出游客身份 → 用掉赠送的 3 次 →
        此后**永远**被"游客体验额度已用完"挡住，那 10 次一次都花不出去。
        成因：guest_needs_credit_gate 对 credits=0 同样为真，于是在
        check_quota 有机会查他的真实余额之前就先 402 了。
        """
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")

        uid, token = guest_service.mint_guest(db)
        headers = {"Authorization": f"Bearer {token}"}

        # 兑一个 10 次的码（走真实的兑换服务，不手搓流水）
        code = cdk_service.generate_codes(db, count=1, credits=10)[0].code
        cdk_service.redeem(db, code, uid)
        assert cdk_service.credit_balance(db, uid) == 10

        # 先把赠送的 3 次用完
        for _ in range(guest_service.GUEST_FREE_REVIEWS):
            assert client.post("/api/v2/reviews", headers=headers, json=_payload()).status_code == 202
        db.expire_all()
        assert db.get(User, uid).guest_review_credits == 0
        assert cdk_service.credit_balance(db, uid) == 10, "体验额度期间不该动用 CDK 余额"

        # 第 4 次：必须落回正常配额链路，扣他自己买的那份次数
        r = client.post("/api/v2/reviews", headers=headers, json=_payload())
        assert r.status_code == 202, (
            f"兑了 10 次的游客第 4 次就被挡住了，那些次数永远花不出去：{r.text[:300]}"
        )
        assert cdk_service.credit_balance(db, uid) == 9

    def test_guest_without_credits_still_gets_an_accurate_402(
        self, client, db, monkeypatch, _server_key, _no_op_enqueue
    ):
        """没买过次数的游客用完试用额度仍然要被挡住——"落回正常配额"不能
        变成"试用用完 = 无限畅玩"（配额开关默认是关的，无条件落回就是这个后果）。
        文案要把两件事都说到：试用没了，账上也没有可用次数。"""
        uid, token = guest_service.mint_guest(db)
        headers = {"Authorization": f"Bearer {token}"}
        for _ in range(guest_service.GUEST_FREE_REVIEWS):
            assert client.post("/api/v2/reviews", headers=headers, json=_payload()).status_code == 202

        r = client.post("/api/v2/reviews", headers=headers, json=_payload())
        assert r.status_code == 402
        msg = r.json()["error"]["message"]
        assert "游客体验额度" in msg
        assert "邮箱" in msg and "CDK" in msg


# ---------------------------------------------------------------------------
# 4. 失败的游客评审不能凭空发 CDK 余额
# ---------------------------------------------------------------------------


class TestNoPhantomCdkCreditOnGuestFailure:
    @pytest.fixture(autouse=True)
    def _credits_mode(self, monkeypatch):
        # refund_review_credit 只在 (credits 模式 + server key) 下才退，
        # 也就是只有这个组合能复现"凭空发次数"。
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")

    def _spent_guest(self, db):
        """一个已经消耗掉 1 次体验额度的游客（模拟发起时的扣减）。"""
        uid, _ = guest_service.mint_guest(db)
        assert guest_service.try_consume_guest_credit(db, uid)
        return uid

    def test_worker_failure_refunds_the_guest_credit_not_a_cdk_credit(self, db):
        """后台 worker 的失败分支。

        走真实的 _execute_review：传一个不存在的 review_id，函数会在 try 里
        抛 RuntimeError，正好落进那段补偿代码——这正是要测的那条路径。
        """
        from app.services import job_service, review_service

        uid = self._spent_guest(db)
        before = cdk_service.credit_balance(db, uid)
        job_id = job_service.create_job(
            kind="review", ref_id="guest-hard-worker", user_id=uid,
            payload={"key_source": "server", "guest_gated": True},
        )

        with pytest.raises(Exception):
            review_service._execute_review(
                "no-such-review-id", "sk-fake", "server", uid, job_id,
                "anthropic", None, None, True,
            )

        db.expire_all()
        assert cdk_service.credit_balance(db, uid) == before, (
            "失败的游客评审凭空发了一次 CDK 余额——他从没扣过，绑定邮箱后就能花出去"
        )
        assert db.get(User, uid).guest_review_credits == guest_service.GUEST_FREE_REVIEWS, (
            "当初扣掉的游客体验额度没有退回来"
        )

    def test_reaping_refunds_the_guest_credit_not_a_cdk_credit(self, db):
        """进程重启收尸这条路（app/db._settle_reaped_reviews）。"""
        from app import db as app_db

        uid = self._spent_guest(db)
        before = cdk_service.credit_balance(db, uid)

        review = Review(
            user_id=uid, task_type="concept_review", artifact_bundle={"title": "x"},
            status="pending",
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        db.add(
            Job(
                kind="review", ref_id=review.id, user_id=uid, status="queued",
                payload={"key_source": "server", "guest_gated": True},
            )
        )
        db.commit()

        app_db._reap_orphans()

        db.expire_all()
        assert db.get(Review, review.id).status == "failed"
        assert cdk_service.credit_balance(db, uid) == before, (
            "收尸给游客凭空发了一次 CDK 余额"
        )
        assert db.get(User, uid).guest_review_credits == guest_service.GUEST_FREE_REVIEWS

    def test_non_guest_orphan_still_gets_its_cdk_credit_back(self, db):
        """反向保证：真正扣过 CDK 的评审（非游客）照旧要退，别修坏了。"""
        from app import db as app_db

        uid = "guest-hard-real-user"
        db.add(CreditLedger(user_id=uid, delta=1, reason="cdk_redeem"))
        db.commit()
        review = Review(
            user_id=uid, task_type="concept_review", artifact_bundle={"title": "x"},
            status="pending",
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        db.add(
            Job(
                kind="review", ref_id=review.id, user_id=uid, status="queued",
                payload={"key_source": "server", "guest_gated": False},
            )
        )
        db.commit()
        quota_service.check_quota(db, uid, key_source="server", plan="free")
        assert cdk_service.credit_balance(db, uid) == 0

        app_db._reap_orphans()

        db.expire_all()
        assert cdk_service.credit_balance(db, uid) == 1, "非游客的次数退还被改坏了"

    def test_guest_credit_refund_never_exceeds_the_grant(self, db):
        """退款不能变成发额度：无论被触发几次，余额都不该超过当初赠送的数量。"""
        uid, _ = guest_service.mint_guest(db)
        for _ in range(5):
            guest_service.refund_guest_credit(db, uid)
        db.expire_all()
        assert db.get(User, uid).guest_review_credits == guest_service.GUEST_FREE_REVIEWS


# ---------------------------------------------------------------------------
# 5. /usage 必须如实报出"还能发起几次"
# ---------------------------------------------------------------------------


class TestUsageReportsTrialCredits:
    """前端此前拿 bonus_credits（CDK 余额）当"还能不能发起评审"。

    刚铸造的游客 CDK 余额恒为 0，于是 credits 模式下新游客一打开页面就看到
    "评审额度已用完 / 去兑换"，而后端其实还会痛快接下 3 次——界面说的和
    接口做的正好相反。修法是服务端直接给一个权威数字，前端只负责显示：
    reviews_remaining 与 check_quota 同源，trial_* 只负责解释这个数字的来历。
    """

    def test_fresh_guest_is_not_reported_as_exhausted(self, db, monkeypatch):
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")

        user_id, _token = guest_service.mint_guest(db)
        summary = quota_service.usage_summary(db, user_id)

        # 老字段仍然是 0——它报的是 CDK 余额，这没错，错的是拿它当额度用
        assert summary["bonus_credits"] == 0
        # 新字段必须说实话：还有 3 次可以发起
        assert summary["trial_credits_remaining"] == guest_service.GUEST_FREE_REVIEWS
        assert summary["trial_credits_total"] == guest_service.GUEST_FREE_REVIEWS
        assert summary["reviews_remaining"] == guest_service.GUEST_FREE_REVIEWS

    def test_trial_fields_are_none_for_a_normal_account(self, db, monkeypatch):
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")

        user = User(email="normal-usage@example.com", password_hash="x")
        db.add(user)
        db.commit()

        summary = quota_service.usage_summary(db, user.id)
        # None = "不适用"，不是 0（0 的语义是"用完了"）
        assert summary["trial_credits_remaining"] is None
        assert summary["trial_credits_total"] is None

        db.delete(user)
        db.commit()

    def test_exhausted_trial_plus_cdk_balance_is_reported(self, db, monkeypatch):
        """兑过 CDK 的游客：体验额度用完后，reviews_remaining 要算上 CDK 余额。"""
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")

        user_id, _token = guest_service.mint_guest(db)
        for _ in range(guest_service.GUEST_FREE_REVIEWS):
            assert guest_service.try_consume_guest_credit(db, user_id)

        # 直接写一行 +10 的流水（cdk_service 没有公开的发放函数，兑换走的是
        # redeem 那条路；这里要的只是"余额为 10"这个状态）
        db.add(CreditLedger(user_id=user_id, delta=10, reason="test-grant", ref_id="t-1"))
        db.commit()
        assert cdk_service.credit_balance(db, user_id) == 10

        summary = quota_service.usage_summary(db, user_id)
        assert summary["trial_credits_remaining"] == 0
        assert summary["reviews_remaining"] == 10

    def test_unlimited_when_quota_disabled(self, db, monkeypatch):
        """配额整体关闭时是"不设限"，不是 0——两者前端必须分得开。"""
        monkeypatch.setattr(settings, "quota_enabled", False)

        user_id, _token = guest_service.mint_guest(db)
        summary = quota_service.usage_summary(db, user_id)
        assert summary["reviews_remaining"] is None
