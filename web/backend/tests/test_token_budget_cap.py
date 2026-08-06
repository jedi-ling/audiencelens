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


class TestNoBypassRoutes:
    """终身闸必须覆盖**所有**烧平台 key 的入口，不只是评审。

    这是审计翻出来的最严重一条：闸最初只挂在评审 v1/v2 上，而追问、意图解析、
    人格生成三条路各自都拿平台 key 发请求、各自都把 token 记进 usage_records，
    却都不查这道闸。于是 tokens_used 把它们算进来了、判断却漏了它们——
    账面早已超额，闸门永远放行。
    """

    def test_chat_followup_blocked_when_exhausted(self, db):
        """追问不扣次数是设计意图（追问是留存点），但不能等于不受总量约束。"""
        from app.services import chat_service

        u = _user(db, "tok-chat@example.com")
        _burn(db, u.id, 3_000_000)
        with pytest.raises(QuotaExceeded):
            chat_service._check_chat_quota(db, u.id, "server", "free")

    def test_chat_followup_allowed_under_cap(self, db):
        """反向对照：没超额时追问必须放行，否则这个修复就把追问功能整个关掉了。"""
        from app.services import chat_service

        u = _user(db, "tok-chat-ok@example.com")
        _burn(db, u.id, 100)
        chat_service._check_chat_quota(db, u.id, "server", "free")  # 不抛

    def test_chat_byok_unaffected(self, db):
        from app.services import chat_service

        u = _user(db, "tok-chat-byok@example.com")
        _burn(db, u.id, 9_000_000)
        chat_service._check_chat_quota(db, u.id, "byok", "free")  # 不抛

    def test_gate_is_independent_of_quota_enabled(self, db, monkeypatch):
        """这道闸由自己的开关控制，不该被 AL_QUOTA_ENABLED 一起关掉。

        它保护的是运营者的钱包上限，与"要不要按套餐计次计费"是两件事。
        挂在 quota_enabled 下面，等于关掉计费的同时把钱包保护也关了。
        评审链路与追问链路必须对这一点取同一立场——两边分歧过一次。
        """
        monkeypatch.setattr(settings, "quota_enabled", False)
        u = _user(db, "tok-noquota@example.com")
        _burn(db, u.id, 3_000_000)

        from app.services import chat_service

        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, u.id, key_source="server")
        with pytest.raises(QuotaExceeded):
            chat_service._check_chat_quota(db, u.id, "server", "free")


class TestAnonymousBucketExempt:
    def test_shared_anonymous_never_capped(self, db, monkeypatch):
        """共享匿名桶必须豁免，理由比次数闸那条更强。

        次数闸是 24h 滚动的，压错了第二天自愈；这道闸不滚动、不重置、
        没有清零路径。AL_AUTH_ENABLED=false 形态下所有未登录访客共用一个
        user_id，任何一个人烧完额度，之后**全站访客永久 402**。
        """
        monkeypatch.setattr(settings, "anonymous_user_id", "anon-tok")
        _user(db, "anon-tok@example.com")
        from app.models import User

        row = db.query(User).filter(User.email == "anon-tok@example.com").first()
        row.id = "anon-tok"
        db.commit()
        _burn(db, "anon-tok", 99_000_000)

        assert quota_service.token_cap_error(db, "anon-tok") is None
        quota_service.check_quota(db, "anon-tok", key_source="server")  # 不抛

    def test_normal_user_still_capped(self, db, monkeypatch):
        """反向对照：豁免只给匿名桶，普通用户照拦。"""
        monkeypatch.setattr(settings, "anonymous_user_id", "anon-tok2")
        u = _user(db, "tok-normal@example.com")
        _burn(db, u.id, 3_000_000)
        assert quota_service.token_cap_error(db, u.id) is not None
