# -*- coding: utf-8 -*-
"""后台给单个用户单独提额（终身 token 上限的用户级覆盖）。

背景：AL_QUOTA_TOKENS_TOTAL 是全局的，想给某一个用户多一点只能改全局配置——
等于给所有人都提了。这里加 users.token_quota_total（NULL = 跟随全局）。

这类"覆盖值 > 全局值"的机制最容易出的错不是功能不通，而是**只有一半读取点
认得覆盖值**：闸门认、页面不认（后台明明提了额，用户看到的还是旧数字），
或者反过来（页面显示提额了、闸门照拦）。所以下面每条都成对断言闸门与页面。
"""

import pytest

from app.config import settings
from app.core.errors import QuotaExceeded
from app.models import UsageRecord, User
from app.services import quota_service


@pytest.fixture(autouse=True)
def _quota_on(monkeypatch):
    monkeypatch.setattr(settings, "quota_enabled", True)
    monkeypatch.setattr(settings, "quota_mode", "plan")
    monkeypatch.setattr(settings, "quota_tokens_total", 1_000_000)
    monkeypatch.setattr(settings, "quota_tokens_per_review_estimate", 0)  # 关占位，专测上限解析
    monkeypatch.setattr(settings, "quota_free_reviews_per_day", 999)
    monkeypatch.setattr(settings, "quota_unverified_reviews_per_day", -1)
    yield


def _user(db, email, cap=None):
    from datetime import datetime, timezone

    u = User(id=f"pq-{email}", email=email, password_hash="x",
             email_verified_at=datetime.now(timezone.utc), token_quota_total=cap)
    db.add(u)
    db.commit()
    return u


def _burn(db, user_id, tokens):
    db.add(UsageRecord(user_id=user_id, kind="review", persona_count=1, cost_usd=0.1,
                       input_tokens=tokens, output_tokens=0, key_source="server"))
    db.commit()


class TestOverrideResolution:
    def test_null_follows_global(self, db):
        u = _user(db, "follow@example.com", cap=None)
        assert quota_service.effective_token_cap(db, u.id) == 1_000_000

    def test_override_wins(self, db):
        u = _user(db, "raised@example.com", cap=5_000_000)
        assert quota_service.effective_token_cap(db, u.id) == 5_000_000

    def test_override_can_lower_too(self, db):
        """反向对照：覆盖值不只能调高。只测"能提额"的话，一个
        `return max(global, override)` 的实现也能过。"""
        u = _user(db, "lowered@example.com", cap=100)
        assert quota_service.effective_token_cap(db, u.id) == 100

    def test_override_zero_means_unlimited(self, db):
        u = _user(db, "unlimited@example.com", cap=0)
        assert quota_service.effective_token_cap(db, u.id) == 0
        _burn(db, u.id, 99_000_000)
        quota_service.check_quota(db, u.id, key_source="server")  # 不抛


class TestGateAndSummaryAgree:
    """闸门与页面必须同时认得覆盖值——只认一半是这类机制的典型故障。"""

    def test_raised_user_passes_where_global_would_block(self, db):
        u = _user(db, "gate-raised@example.com", cap=5_000_000)
        _burn(db, u.id, 2_000_000)          # 超了全局的 100 万，没超他自己的 500 万
        quota_service.check_quota(db, u.id, key_source="server")   # 闸门放行
        s = quota_service.usage_summary(db, u.id)
        assert s["tokens_limit"] == 5_000_000, "页面必须显示提额后的上限"
        assert s["tokens_used"] == 2_000_000

    def test_default_user_still_blocked_at_global(self, db):
        """反向对照：没提额的人照旧按全局拦，否则"提额"等于给所有人提额。"""
        u = _user(db, "gate-default@example.com", cap=None)
        _burn(db, u.id, 2_000_000)
        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, u.id, key_source="server")
        assert quota_service.usage_summary(db, u.id)["tokens_limit"] == 1_000_000

    def test_lowered_user_blocked_earlier(self, db):
        u = _user(db, "gate-lowered@example.com", cap=500)
        _burn(db, u.id, 600)
        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, u.id, key_source="server")


class TestAdminEndpoint:
    def _hdr(self):
        return {"X-Admin-Token": settings.admin_token}

    def test_set_and_clear_override(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "test-admin-token-0123456789")
        u = _user(db, "admin-set@example.com", cap=None)

        r = client.put(f"/api/admin/users/{u.id}",
                       headers={"X-Admin-Token": settings.admin_token},
                       json={"token_quota_total": 9_000_000})
        assert r.status_code == 200
        assert r.json()["token_quota_total"] == 9_000_000
        db.expire_all()
        assert quota_service.effective_token_cap(db, u.id) == 9_000_000

        # -1 = 清除覆盖，回落全局。用 -1 而不是 null：Pydantic 里
        # "传了 null" 和 "没传" 在 Optional 上无法区分。
        r = client.put(f"/api/admin/users/{u.id}",
                       headers={"X-Admin-Token": settings.admin_token},
                       json={"token_quota_total": -1})
        assert r.status_code == 200
        assert r.json()["token_quota_total"] is None
        db.expire_all()
        assert quota_service.effective_token_cap(db, u.id) == 1_000_000

    def test_rejects_bad_value(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "test-admin-token-0123456789")
        u = _user(db, "admin-bad@example.com", cap=None)
        r = client.put(f"/api/admin/users/{u.id}",
                       headers={"X-Admin-Token": settings.admin_token},
                       json={"token_quota_total": -5})
        assert r.status_code == 400
