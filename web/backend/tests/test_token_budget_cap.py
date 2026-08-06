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


class TestConcurrencyIsBounded:
    """并发发起时，终身闸不能让所有人一起过。

    修复前是纯 check-then-use：查用量与真正烧 token 之间没有任何写入，
    实测 used=cap-1 时 8 个并发请求 8/8 全部放行，超额量级 =
    并发数 × 单次评审用量（10^5~10^6），也就是终身额度能在一小时内被超出
    一个数量级。次数闸当初正是因为同型问题才加的占位。

    修法是在放行的瞬间按估算值占位，让并发请求彼此可见。这里断言的是
    "放行数被压到个位数量级"而不是精确值——占位是估算，本来就不追求精确，
    要的是把超额从"并发数倍"压到"一次估算误差"。
    """

    def test_concurrent_requests_do_not_all_pass(self, db):
        import threading

        from app.db import SessionLocal

        cap = settings.quota_tokens_total          # 3_000_000
        est = settings.quota_tokens_per_review_estimate  # 150_000
        u = _user(db, "tok-race@example.com")
        # 留出恰好 2 个估算位的余量：正确实现最多放行 2~3 个
        _burn(db, u.id, cap - 2 * est)

        results = []
        barrier = threading.Barrier(8)

        def worker():
            s = SessionLocal()
            try:
                barrier.wait(timeout=10)
                quota_service.check_quota(s, u.id, key_source="server")
                results.append("pass")
            except QuotaExceeded:
                results.append("blocked")
            except Exception as e:  # 并发下 SQLite 可能报 locked，如实记下不掩盖
                results.append(f"error:{type(e).__name__}")
            finally:
                s.close()

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        passed = results.count("pass")
        assert passed < 8, f"8 个并发全部放行 = 闸门形同虚设：{results}"
        # 上界放宽到 4：SQLite 下的串行化靠库级写锁，边界上可能多放一个。
        # 关键是"远小于 8"，不是精确到个位。
        assert passed <= 4, f"放行数 {passed} 超出估算占位应有的量级：{results}"

    def test_hold_is_released_on_settlement(self, db):
        """评审结束后占位必须被真实用量顶掉，不能双重计数。"""
        u = _user(db, "tok-settle@example.com")
        before = quota_service.tokens_used(db, u.id)
        quota_service.check_quota(db, u.id, key_source="server")
        held = quota_service.tokens_used(db, u.id)
        assert held > before, "放行后应留下占位"

        quota_service.record_usage(
            db, u.id, kind="review", key_source="server",
            input_tokens=1000, output_tokens=500,
        )
        after = quota_service.tokens_used(db, u.id)
        assert after == before + 1500, f"占位没被顶掉，出现双重计数：{after}"

    def test_hold_is_released_on_failure(self, db):
        """评审失败释放名额时，token 占位同样要放掉——否则失败的评审
        会在 TTL 内一直吃着终身额度。credits 模式下没有日名额占位，
        这条尤其容易漏（release_review_slot 会提前 return False）。"""
        u = _user(db, "tok-fail@example.com")
        before = quota_service.tokens_used(db, u.id)
        quota_service.check_quota(db, u.id, key_source="server")
        assert quota_service.tokens_used(db, u.id) > before

        quota_service.release_review_slot(db, u.id, key_source="server")
        assert quota_service.tokens_used(db, u.id) == before

    def test_stale_hold_stops_counting(self, db):
        """漏释放要能自愈：过了 TTL 的占位不再计数。

        终身额度没有任何清零路径，一次进程崩溃如果永久吃掉一部分额度，
        对用户就是永久损失。
        """
        from datetime import datetime, timedelta, timezone

        from app.models import UsageRecord

        u = _user(db, "tok-stale@example.com")
        before = quota_service.tokens_used(db, u.id)
        stale = UsageRecord(
            user_id=u.id, kind=quota_service.TOKEN_HOLD_KIND,
            persona_count=0, cost_usd=0.0,
            input_tokens=999_999, output_tokens=0, key_source="server",
            created_at=datetime.now(timezone.utc)
            - timedelta(seconds=quota_service.RESERVATION_TTL_SECONDS + 60),
        )
        db.add(stale)
        db.commit()
        assert quota_service.tokens_used(db, u.id) == before
