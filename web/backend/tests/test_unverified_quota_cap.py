"""未验证邮箱 → 服务端 key 每日次数被压低（软拦）。

这个机制存在的理由，是在它之前 email_verified_at 只是一条记录：
登录、评审、配额一处都不读它，激活与不激活对用户完全没区别，验证邮件白发。

所以本文件的第一要务不是"功能可用"，而是**证明这道闸不是摆设**——
每条正向断言都配一条反向的：把条件反过来，闸门必须放行。只测正向的话，
一个 `return plan_limit` 的空实现也能让"未验证被拦"这类断言里的
大部分通过（因为额度总会用完），那就又是一个把 bug 焊死成预期行为的测试。
"""

import pytest

from app.config import settings
from app.models import User
from app.services import quota_service


@pytest.fixture(autouse=True)
def _quota_on(monkeypatch):
    """配额默认关闭；不打开的话 check_quota 第一行就 return，全测白跑。

    这一条是本文件最容易出错的地方：AL_QUOTA_ENABLED 默认 false，
    忘了它就会得到一整页"通过"的假绿。
    """
    monkeypatch.setattr(settings, "quota_enabled", True)
    monkeypatch.setattr(settings, "quota_mode", "plan")
    monkeypatch.setattr(settings, "quota_free_reviews_per_day", 5)
    monkeypatch.setattr(settings, "quota_unverified_reviews_per_day", 1)
    yield


def _make_user(db, email, verified):
    from datetime import datetime, timezone

    user = User(
        id=f"u-{email}",
        email=email,
        password_hash="x",
        email_verified_at=datetime.now(timezone.utc) if verified else None,
    )
    db.add(user)
    db.commit()
    return user


class TestEffectiveLimit:
    def test_unverified_is_capped(self, db):
        u = _make_user(db, "unverified@example.com", verified=False)
        assert quota_service.effective_reviews_limit(db, u.id, 5) == 1

    def test_verified_keeps_full_limit(self, db):
        """反向对照：同样的调用，只把 email_verified_at 填上，就必须拿回 5。

        没有这一条，上面那条断言无法区分"正确实现"和"给所有人都返回 1"。
        """
        u = _make_user(db, "verified@example.com", verified=True)
        assert quota_service.effective_reviews_limit(db, u.id, 5) == 5

    def test_never_raises_the_limit(self, db):
        """套餐上限比未验证上限还低时，取低的那个——闸门不能变漏斗。"""
        u = _make_user(db, "low@example.com", verified=False)
        assert quota_service.effective_reviews_limit(db, u.id, 0) == 0

    def test_anonymous_bucket_untouched(self, db, monkeypatch):
        """共享匿名桶不能被压：匿名访客没有邮箱可验证，压这里等于把全站
        未登录试用额度变成每天 1 次，是全局故障不是限流。

        这条以前是**空壳**：它没建 anon-shared 这一行 User，于是调用根本没走到
        匿名分支，而是从"查不到用户"那条路返回的——和 test_unknown_user_untouched
        是同一条测试换了个名字。变异测试（把匿名豁免整个删掉）它照样绿。
        所以必须真的建一个未验证的 User 行，让匿名豁免成为唯一能让它通过的原因。
        """
        monkeypatch.setattr(settings, "anonymous_user_id", "anon-shared")
        _make_user(db, "anon-shared", verified=False)
        # 覆盖掉 _make_user 生成的 id，让它就是匿名桶那个 id
        from app.models import User

        row = db.query(User).filter(User.email == "anon-shared").first()
        row.id = "anon-shared"
        db.commit()

        assert quota_service.effective_reviews_limit(db, "anon-shared", 5) == 5

    def test_disabled_by_negative_config(self, db, monkeypatch):
        monkeypatch.setattr(settings, "quota_unverified_reviews_per_day", -1)
        u = _make_user(db, "off@example.com", verified=False)
        assert quota_service.effective_reviews_limit(db, u.id, 5) == 5

    def test_unknown_user_untouched(self, db):
        """查不到 user 就别拦——没有可验证的对象，拦了只会误伤。"""
        assert quota_service.effective_reviews_limit(db, "ghost", 5) == 5


class TestGateActuallyBites:
    """走真正的 check_quota，不是只测那个纯函数。"""

    def test_second_review_rejected_for_unverified(self, db):
        from app.core.errors import QuotaExceeded

        u = _make_user(db, "gate-un@example.com", verified=False)
        quota_service.check_quota(db, u.id, key_source="server")  # 第 1 次放行
        with pytest.raises(QuotaExceeded) as exc:
            quota_service.check_quota(db, u.id, key_source="server")
        # 提示必须指向"去验证邮箱"，不能让用户以为要花钱升级套餐——
        # 他真正要做的那件事是免费的。
        assert "激活链接" in str(exc.value)

    def test_verified_user_gets_five(self, db):
        """反向对照：已验证的同一路径，第 2 次必须放行。

        缺了这条，上面那条只能证明"第二次被拒"，而一个把所有人都拒掉的
        实现同样能通过。
        """
        u = _make_user(db, "gate-ok@example.com", verified=True)
        for _ in range(5):
            quota_service.check_quota(db, u.id, key_source="server")

    def test_byok_never_capped(self, db):
        """BYOK 花的是用户自己的钱，验证与否都不该限制。"""
        u = _make_user(db, "byok@example.com", verified=False)
        for _ in range(10):
            quota_service.check_quota(db, u.id, key_source="byok")


class TestSummaryAgreesWithGate:
    def test_displayed_limit_matches_enforced_limit(self, db):
        """用量页显示的数字必须和闸门用的是同一个。

        这两处分开算过一次就出过事：页面显示 3/5、闸门按 1/1 拒绝，
        用户看到的是一个说谎的数字。
        """
        u = _make_user(db, "sum@example.com", verified=False)
        s = quota_service.usage_summary(db, u.id)
        assert s["reviews_limit"] == 1
        assert s["reviews_limit_capped_unverified"] is True

    def test_flag_false_when_verified(self, db):
        u = _make_user(db, "sum-ok@example.com", verified=True)
        s = quota_service.usage_summary(db, u.id)
        assert s["reviews_limit"] == 5
        assert s["reviews_limit_capped_unverified"] is False
