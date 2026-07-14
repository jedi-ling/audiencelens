"""商业逻辑——套餐体系：/api/plans、按套餐限额校验、未知 plan 回落 free。"""

import pytest


# ============================== 套餐目录 ==============================

class TestPlansEndpoint:
    def test_plans_endpoint_shape(self, client):
        """公开端点：三档齐全，每档带 id + 完整限额字段。"""
        r = client.get("/api/plans")
        assert r.status_code == 200
        plans = r.json()["plans"]
        ids = {p["id"] for p in plans}
        assert {"free", "pro", "team"} <= ids
        for p in plans:
            for key in ("id", "name", "price_usd_month", "reviews_per_day", "cost_usd_per_day"):
                assert key in p, f"套餐 {p.get('id')} 缺字段 {key}"

    def test_plan_tiers_are_ordered(self, client):
        """价格与额度应随档位递增——定价页的基本诚实。"""
        plans = {p["id"]: p for p in client.get("/api/plans").json()["plans"]}
        assert plans["free"]["price_usd_month"] == 0
        assert plans["pro"]["price_usd_month"] == 19
        assert plans["team"]["price_usd_month"] == 49
        assert (
            plans["free"]["reviews_per_day"]
            < plans["pro"]["reviews_per_day"]
            < plans["team"]["reviews_per_day"]
        )


# ============================== 按套餐限额校验 ==============================

class TestPlanQuota:
    def test_free_blocked_but_pro_allowed(self, db, monkeypatch):
        """同一份用量：free 超限被拒，pro 额度内放行。"""
        from app.config import settings
        from app.core.errors import QuotaExceeded
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        uid = "u-plan-free-vs-pro"
        for _ in range(5):  # free 默认 5 次/天，记满
            quota_service.record_usage(db, uid, cost_usd=0.01, key_source="server")

        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, uid, key_source="server", plan="free")
        # pro 限 100 次/天 —— 5 条远未触顶，必须放行
        quota_service.check_quota(db, uid, key_source="server", plan="pro")

    def test_byok_unlimited_regardless_of_plan(self, db, monkeypatch):
        """BYOK 花用户自己的钱——任何套餐下都不受限。"""
        from app.config import settings
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_free_reviews_per_day", 1)
        uid = "u-plan-byok"
        for _ in range(3):
            quota_service.record_usage(db, uid, cost_usd=1.0, key_source="byok")
        quota_service.check_quota(db, uid, key_source="byok", plan="free")  # 不抛


# ============================== 未知 plan 回落 free ==============================

class TestUnknownPlanFallback:
    def test_get_plan_falls_back_to_free(self):
        from app.services import plan_service

        for bogus in ("enterprise-max", "", None, "FREE "):
            p = plan_service.get_plan(bogus)
            assert p["id"] == "free"
            assert p["name"] == "Free"

    def test_check_quota_unknown_plan_uses_free_limits(self, db, monkeypatch):
        """未知 plan 不能凭空放行——必须按 free 限额校验。"""
        from app.config import settings
        from app.core.errors import QuotaExceeded
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_free_reviews_per_day", 2)
        uid = "u-plan-unknown"
        for _ in range(2):
            quota_service.record_usage(db, uid, cost_usd=0.01, key_source="server")
        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, uid, key_source="server", plan="does-not-exist")


# ============================== usage_summary 带套餐限额 ==============================

class TestUsageSummaryPlan:
    def test_summary_carries_plan_and_limits(self, db, monkeypatch):
        from app.config import settings
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        s = quota_service.usage_summary(db, "u-plan-summary", plan="pro")
        assert s["plan"] == "pro"
        assert s["reviews_limit"] == 100
        assert s["cost_usd_limit"] == 20.0

    def test_summary_defaults_to_free(self, db, monkeypatch):
        """不传 plan = 旧行为：free 档限额（向后兼容）。"""
        from app.config import settings
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        s = quota_service.usage_summary(db, "u-plan-summary-default")
        assert s["plan"] == "free"
        assert s["reviews_limit"] == settings.quota_free_reviews_per_day
        assert s["cost_usd_limit"] == settings.quota_free_cost_usd_per_day

    def test_usage_endpoint_exposes_plan(self, client):
        """HTTP 层透传 identity.plan（匿名默认 free）。"""
        r = client.get("/api/usage")
        assert r.status_code == 200
        assert r.json()["plan"] == "free"
