# -*- coding: utf-8 -*-
"""每个用户的终身平台 token 上限（体验额度）。

存在的理由：次数闸和成本闸都是 24h 滚动窗口，跨天就重置——它们能拦住"一天刷爆"，
拦不住"每天用满、连用一个月"。这一条不滚动、不重置，是一个账号在这个实例上
能烧掉的平台 token 总量。

每条正向断言都配反向对照。只测"超了会拒"的话，一个把所有人都拒掉的实现同样能过；
只测"没超放行"的话，一个永远放行的实现（也就是这个功能压根没做）同样能过。
"""

import pytest

from app.config import settings
from app.core.errors import QuotaExceeded
from app.models import UsageRecord, User
from app.services import quota_service


@pytest.fixture(autouse=True)
def _quota_on(monkeypatch):
    # AL_QUOTA_ENABLED 默认 false，忘了打开会得到一整页假绿
    monkeypatch.setattr(settings, "quota_enabled", True)
    monkeypatch.setattr(settings, "quota_mode", "plan")
    monkeypatch.setattr(settings, "quota_tokens_total", 3_000_000)
    monkeypatch.setattr(settings, "quota_free_reviews_per_day", 999)
    monkeypatch.setattr(settings, "quota_unverified_reviews_per_day", -1)
    yield


def _user(db, email):
    from datetime import datetime, timezone

    u = User(id=f"u-{email}", email=email, password_hash="x",
             email_verified_at=datetime.now(timezone.utc))
    db.add(u)
    db.commit()
    return u


def _burn(db, user_id, tokens, key_source="server"):
    db.add(UsageRecord(
        user_id=user_id, kind="review", persona_count=7, cost_usd=0.1,
        input_tokens=tokens // 2, output_tokens=tokens - tokens // 2,
        key_source=key_source,
    ))
    db.commit()


class TestTokensUsed:
    def test_sums_input_and_output(self, db):
        u = _user(db, "tok-sum@example.com")
        _burn(db, u.id, 1000)
        _burn(db, u.id, 500)
        assert quota_service.tokens_used(db, u.id) == 1500

    def test_byok_not_counted(self, db):
        """反向对照：BYOK 花的是用户自己的钱，计进来等于惩罚自带 key 的用户
        ——而他们恰恰是不花我方一分钱的那批。"""
        u = _user(db, "tok-byok-sum@example.com")
        _burn(db, u.id, 9_999_999, key_source="byok")
        assert quota_service.tokens_used(db, u.id) == 0

    def test_other_users_not_counted(self, db):
        a = _user(db, "tok-a@example.com")
        b = _user(db, "tok-b@example.com")
        _burn(db, b.id, 5000)
        assert quota_service.tokens_used(db, a.id) == 0


class TestGate:
    def test_under_cap_passes(self, db):
        u = _user(db, "tok-under@example.com")
        _burn(db, u.id, 2_999_999)
        quota_service.check_quota(db, u.id, key_source="server")  # 不抛

    def test_at_cap_rejected(self, db):
        u = _user(db, "tok-at@example.com")
        _burn(db, u.id, 3_000_000)
        with pytest.raises(QuotaExceeded) as e:
            quota_service.check_quota(db, u.id, key_source="server")
        # 提示必须指向"填自己的 key 就能继续"——这是用户唯一能自助解决的路
        assert "BYOK" in str(e.value)

    def test_byok_never_blocked(self, db):
        """烧爆了额度，BYOK 仍然畅通。"""
        u = _user(db, "tok-byok-gate@example.com")
        _burn(db, u.id, 99_000_000)
        for _ in range(3):
            quota_service.check_quota(db, u.id, key_source="byok")

    def test_zero_means_unlimited(self, db, monkeypatch):
        monkeypatch.setattr(settings, "quota_tokens_total", 0)
        u = _user(db, "tok-unlimited@example.com")
        _burn(db, u.id, 99_000_000)
        quota_service.check_quota(db, u.id, key_source="server")  # 不抛

    def test_applies_in_credits_mode_too(self, db, monkeypatch):
        """credits 模式下同样生效。

        这条是本文件最要紧的一条：credits 分支自己 return，如果 token 闸被写在
        它后面，credits 模式就完全绕过了——而 credits 正是推荐给生产的模式。
        用户手里有 CDK 余额也不该越过终身上限，否则这道闸等于不存在。
        """
        monkeypatch.setattr(settings, "quota_mode", "credits")
        u = _user(db, "tok-credits@example.com")
        _burn(db, u.id, 3_000_000)

        from app.services import cdk_service

        rows = cdk_service.generate_codes(db, count=1, credits=10)
        cdk_service.redeem(db, rows[0].code, u.id)
        assert cdk_service.credit_balance(db, u.id) == 10  # 有余额

        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, u.id, key_source="server")
        # 而且不能把次数扣掉——被闸拦下的请求不该付费
        assert cdk_service.credit_balance(db, u.id) == 10


class TestSummary:
    def test_reports_usage_and_limit(self, db):
        u = _user(db, "tok-summary@example.com")
        _burn(db, u.id, 12_345)
        s = quota_service.usage_summary(db, u.id)
        assert s["tokens_used"] == 12_345
        assert s["tokens_limit"] == 3_000_000

    def test_limit_none_when_disabled(self, db, monkeypatch):
        monkeypatch.setattr(settings, "quota_tokens_total", 0)
        u = _user(db, "tok-summary-off@example.com")
        _burn(db, u.id, 42)
        s = quota_service.usage_summary(db, u.id)
        assert s["tokens_limit"] is None
        # 不限制也要如实回报已用量——不然用户永远不知道自己烧了多少
        assert s["tokens_used"] == 42
