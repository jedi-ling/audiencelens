"""CDK 兑换码：后台生成 → 免登录兑换（自动签发游客身份）→ 次数垫配额。

关键行为逐条验证：
  1. 生成需要管理员令牌；参数越界被拒
  2. 匿名兑换（认证开启）自动创建游客 User + 返回可用 JWT——
     次数落在游客身上，不进共享 anonymous 桶
  3. 已登录用户兑换落自己账号；同一人同一码兑两次被拒
  4. 停用/过期/用完的码统一报"无效或已被使用"（不给枚举者可区分信号）
  5. 套餐日限用完后，有余额则消耗 1 次放行；成本硬闸不被次数绕过
  6. /api/usage 返回 bonus_credits 余额
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models import CdkCode, CdkRedemption, CreditLedger, UsageRecord, User

ADMIN_TOKEN = "test-admin-token-xyz"


def _admin_headers():
    return {"X-Admin-Token": ADMIN_TOKEN}


@pytest.fixture(autouse=True)
def _enable_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", ADMIN_TOKEN)


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.query(CdkRedemption).delete()
    db.query(CdkCode).delete()
    db.query(CreditLedger).delete()
    db.query(UsageRecord).delete()
    db.query(User).filter(User.email.like("%@guest.local")).delete(synchronize_session=False)
    db.query(User).filter(User.email.like("cdk-%@example.com")).delete(synchronize_session=False)
    db.commit()


def _generate(client, **kwargs):
    payload = {"count": 1, "credits": 5, **kwargs}
    r = client.post("/api/admin/cdk/generate", json=payload, headers=_admin_headers())
    assert r.status_code == 200, r.text
    return r.json()


class TestGenerate:
    def test_requires_admin_token(self, client):
        r = client.post("/api/admin/cdk/generate", json={"count": 1, "credits": 5})
        assert r.status_code == 401

    def test_batch_generation(self, client):
        body = _generate(client, count=5, credits=3, note="首发活动")
        assert body["count"] == 5
        assert len(body["codes"]) == 5
        assert len(set(body["codes"])) == 5  # 无重复
        for code in body["codes"]:
            assert code.startswith("AL-")

    def test_rejects_out_of_range(self, client):
        r = client.post(
            "/api/admin/cdk/generate",
            json={"count": 0, "credits": 5},
            headers=_admin_headers(),
        )
        assert r.status_code == 400
        r = client.post(
            "/api/admin/cdk/generate",
            json={"count": 1, "credits": 999999},
            headers=_admin_headers(),
        )
        assert r.status_code == 400

    def test_list_and_status(self, client):
        _generate(client, count=2, credits=5)
        r = client.get("/api/admin/cdk?status=active", headers=_admin_headers())
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 2
        assert all(c["status"] == "active" for c in body["codes"])


class TestRedeemAnonymous:
    def test_anonymous_redeem_issues_guest_token(self, client, monkeypatch, db):
        """认证开启时，匿名兑换必须签发游客身份——不然次数会进共享桶被陌生人分掉。"""
        monkeypatch.setattr(settings, "auth_enabled", True)
        code = _generate(client, credits=7)["codes"][0]

        r = client.post("/api/cdk/redeem", json={"code": code})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["credits_granted"] == 7
        assert body["balance"] == 7
        assert body["guest"] is True
        assert body["user_id"] != settings.anonymous_user_id
        # 凭证是游客 cookie（第一次请求就铸好了），不再在响应体里发 token
        assert "token" not in body

        # 游客是真实 User 行，同一份 cookie 能正常通过身份解析
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["is_anonymous"] is False
        assert me.json()["user_id"] == body["user_id"]
        assert client.get("/api/usage").json()["bonus_credits"] == 7

        guest = db.get(User, body["user_id"])
        assert guest.is_guest is True

    def test_auth_disabled_redeems_to_anonymous(self, client):
        """单机形态（认证关闭）：只有一个使用者，直接落 anonymous，不造游客。"""
        code = _generate(client, credits=3)["codes"][0]
        r = client.post("/api/cdk/redeem", json={"code": code})
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == settings.anonymous_user_id
        assert "token" not in body

    def test_failed_redeem_does_not_leave_orphan_guest(self, client, monkeypatch, db):
        """以前兑换时才铸造游客，失败要回滚那一行，免得枚举者批量制造空账号。
        现在游客是这个访客自己的会话身份（第一次请求就有），兑换失败不该
        把它删掉；要守住的是"反复失败不会多出任何账号"。刷身份本身由
        guest_identity_per_hour 拦（见 tests/test_guest_isolation.py）。"""
        monkeypatch.setattr(settings, "auth_enabled", True)
        before = db.query(User).filter(User.is_guest.is_(True)).count()
        for _ in range(3):
            r = client.post("/api/cdk/redeem", json={"code": "AL-FAKE-FAKE-FAKE"})
            assert r.status_code == 400
        after = db.query(User).filter(User.is_guest.is_(True)).count()
        assert after - before <= 1  # 至多就是这个访客自己的游客身份


class TestRedeemRules:
    def test_logged_in_user_redeems_to_own_account(self, client, monkeypatch):
        monkeypatch.setattr(settings, "auth_enabled", True)
        reg = client.post(
            "/api/auth/register",
            json={"email": "cdk-owner@example.com", "password": "password123"},
        )
        token = reg.json()["token"]
        user_id = reg.json()["user"]["id"]

        code = _generate(client, credits=4)["codes"][0]
        r = client.post(
            "/api/cdk/redeem", json={"code": code},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["user_id"] == user_id
        assert "token" not in r.json()  # 已有身份，不再发游客 token

    def test_same_user_cannot_redeem_same_code_twice(self, client):
        code = _generate(client, credits=2, max_uses=10)["codes"][0]
        assert client.post("/api/cdk/redeem", json={"code": code}).status_code == 200
        r = client.post("/api/cdk/redeem", json={"code": code})
        assert r.status_code == 400
        assert "已经兑换过" in r.json()["error"]["message"]

    def test_exhausted_disabled_expired_all_look_the_same(self, client, db, monkeypatch):
        """三种不可用状态对外话术必须一致——不给暴力枚举者可区分的信号。"""
        monkeypatch.setattr(settings, "auth_enabled", True)  # 每次兑换都是新游客，绕开"同人重复"拦截

        exhausted = _generate(client, credits=1, max_uses=1)["codes"][0]
        client.post("/api/cdk/redeem", json={"code": exhausted})  # 用完它

        gen = _generate(client, credits=1)
        disabled_code = gen["codes"][0]
        row = db.query(CdkCode).filter(CdkCode.code == disabled_code).first()
        client.put(f"/api/admin/cdk/{row.id}/disable", headers=_admin_headers())

        expired_code = _generate(client, credits=1)["codes"][0]
        row2 = db.query(CdkCode).filter(CdkCode.code == expired_code).first()
        row2.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

        messages = set()
        for code in (exhausted, disabled_code, expired_code, "AL-XXXX-YYYY-ZZZZ"):
            r = client.post("/api/cdk/redeem", json={"code": code})
            assert r.status_code == 400
            messages.add(r.json()["error"]["message"])
        assert messages == {"兑换码无效或已被使用"}

    def test_multi_use_code_shared_by_different_users(self, client, monkeypatch):
        monkeypatch.setattr(settings, "auth_enabled", True)
        code = _generate(client, credits=2, max_uses=3)["codes"][0]
        # 三个匿名访客（三份 cookie jar）各自兑换 → 各自拿到独立游客身份
        from fastapi.testclient import TestClient

        from app.main import app

        user_ids = set()
        for _ in range(3):
            with TestClient(app) as visitor:
                r = visitor.post("/api/cdk/redeem", json={"code": code})
            assert r.status_code == 200
            user_ids.add(r.json()["user_id"])
        assert len(user_ids) == 3
        # 第 4 人：用完了
        with TestClient(app) as visitor:
            r = visitor.post("/api/cdk/redeem", json={"code": code})
        assert r.status_code == 400


class TestCreditsExtendQuota:
    def test_credit_consumed_when_plan_limit_exhausted(self, client, db, monkeypatch):
        from app.core.errors import QuotaExceeded
        from app.services import cdk_service, quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        user_id = "cdk-quota-user"

        # 灌满 free 档的日次数限额（5 次，全部 server key）
        for _ in range(5):
            quota_service.record_usage(db, user_id, kind="review", key_source="server")

        # 无余额 → 402
        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, user_id, key_source="server", plan="free")

        # 兑 2 次余额 → 放行 2 次，每次消耗 1
        db.add(CreditLedger(user_id=user_id, delta=2, reason="cdk_redeem"))
        db.commit()
        quota_service.check_quota(db, user_id, key_source="server", plan="free")
        assert cdk_service.credit_balance(db, user_id) == 1
        quota_service.check_quota(db, user_id, key_source="server", plan="free")
        assert cdk_service.credit_balance(db, user_id) == 0

        # 余额清零 → 又 402
        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, user_id, key_source="server", plan="free")

    def test_cost_ceiling_not_bypassed_by_credits(self, client, db, monkeypatch):
        """成本上限保护的是运营者的钱包——次数余额不能绕过它。"""
        from app.core.errors import QuotaExceeded
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        user_id = "cdk-cost-user"
        db.add(CreditLedger(user_id=user_id, delta=100, reason="cdk_redeem"))
        db.commit()
        # 一笔就烧穿 free 档 $1/天 的成本硬闸
        quota_service.record_usage(db, user_id, kind="review", key_source="server", cost_usd=2.0)

        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, user_id, key_source="server", plan="free")

    def test_byok_never_touches_credits(self, client, db, monkeypatch):
        from app.services import cdk_service, quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        user_id = "cdk-byok-user"
        db.add(CreditLedger(user_id=user_id, delta=3, reason="cdk_redeem"))
        db.commit()
        for _ in range(10):
            quota_service.record_usage(db, user_id, kind="review", key_source="byok")
        # BYOK 不受配额约束，也绝不消耗余额
        quota_service.check_quota(db, user_id, key_source="byok", plan="free")
        assert cdk_service.credit_balance(db, user_id) == 3


class TestCreditsMode:
    """quota_mode=credits：纯次数制——"一个码 10 次，用完就没了"。
    每次服务端 key 评审直接消耗 1 次，无每日刷新、无套餐日限。"""

    @pytest.fixture(autouse=True)
    def _credits_mode(self, monkeypatch):
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")

    def test_each_review_consumes_one_until_zero(self, client, db):
        from app.core.errors import QuotaExceeded
        from app.services import cdk_service, quota_service

        user_id = "credits-mode-user"
        db.add(CreditLedger(user_id=user_id, delta=3, reason="cdk_redeem"))
        db.commit()

        for expect_left in (2, 1, 0):
            quota_service.check_quota(db, user_id, key_source="server", plan="free")
            assert cdk_service.credit_balance(db, user_id) == expect_left

        # 第 4 次：用完了，402
        with pytest.raises(QuotaExceeded) as exc:
            quota_service.check_quota(db, user_id, key_source="server", plan="free")
        assert "兑换 CDK" in str(exc.value)

    def test_zero_balance_blocked_from_first_review(self, client, db):
        """credits 模式下没有免费额度——没兑过码的用户第一次就被挡。"""
        from app.core.errors import QuotaExceeded
        from app.services import quota_service

        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, "credits-fresh-user", key_source="server", plan="free")

    def test_no_daily_limit_with_enough_credits(self, client, db):
        """有 10 次余额就能连跑 10 次——不受 free 档每天 5 次的限制。"""
        from app.services import cdk_service, quota_service

        user_id = "credits-heavy-user"
        db.add(CreditLedger(user_id=user_id, delta=10, reason="cdk_redeem"))
        db.commit()
        for _ in range(10):
            quota_service.check_quota(db, user_id, key_source="server", plan="free")
            quota_service.record_usage(db, user_id, kind="review", key_source="server")
        assert cdk_service.credit_balance(db, user_id) == 0

    def test_byok_still_free_in_credits_mode(self, client, db):
        from app.services import cdk_service, quota_service

        user_id = "credits-byok-user"
        # 零余额 + BYOK → 照常放行，不消耗
        quota_service.check_quota(db, user_id, key_source="byok", plan="free")
        assert cdk_service.credit_balance(db, user_id) == 0

    def test_usage_summary_hides_daily_limits_in_credits_mode(self, client, db):
        db.add(CreditLedger(user_id="anonymous", delta=6, reason="cdk_redeem"))
        db.commit()
        r = client.get("/api/usage")
        body = r.json()
        assert body["quota_mode"] == "credits"
        assert body["reviews_limit"] is None  # 日限概念不适用
        assert body["bonus_credits"] == 6


class TestUsageExposesBalance:
    def test_usage_summary_includes_bonus_credits(self, client, db):
        code = _generate(client, credits=9)["codes"][0]
        client.post("/api/cdk/redeem", json={"code": code})
        r = client.get("/api/usage")
        assert r.status_code == 200
        assert r.json()["bonus_credits"] == 9


class TestAtomicity:
    """并发双花防线：检查与扣减必须是同一条原子语句。"""

    def test_consume_cannot_go_negative(self, client, db):
        from app.services import cdk_service

        user_id = "atomic-user-1"
        db.add(CreditLedger(user_id=user_id, delta=1, reason="cdk_redeem"))
        db.commit()
        # 余额 1：第一次成功，第二次必须失败（而不是把余额扣成 -1）
        assert cdk_service.try_consume_credit(db, user_id) is True
        assert cdk_service.try_consume_credit(db, user_id) is False
        assert cdk_service.credit_balance(db, user_id) == 0

    def test_consume_zero_balance_rejected(self, client, db):
        from app.services import cdk_service

        assert cdk_service.try_consume_credit(db, "atomic-user-2") is False
        assert cdk_service.credit_balance(db, "atomic-user-2") == 0

    def test_redeem_cannot_exceed_max_uses(self, client, db):
        from app.services import cdk_service

        code_str = _generate(client, credits=5, max_uses=1)["codes"][0]
        cdk_service.redeem(db, code_str, "atomic-user-3")
        # 第二个用户兑同一单次码：条件 UPDATE 拿不到名额，必须失败
        with pytest.raises(cdk_service.CdkError):
            cdk_service.redeem(db, code_str, "atomic-user-4")
        row = db.query(CdkCode).filter(CdkCode.code == code_str).first()
        assert row.used_count == 1  # 没有被并发超发

    def test_redeem_duplicate_user_rolls_back_increment(self, client, db):
        from app.services import cdk_service

        code_str = _generate(client, credits=5, max_uses=10)["codes"][0]
        cdk_service.redeem(db, code_str, "atomic-user-5")
        with pytest.raises(cdk_service.CdkError):
            cdk_service.redeem(db, code_str, "atomic-user-5")
        row = db.query(CdkCode).filter(CdkCode.code == code_str).first()
        assert row.used_count == 1  # 重复兑换的自增被回滚
        assert cdk_service.credit_balance(db, "atomic-user-5") == 5  # 只发了一次
