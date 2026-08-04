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


# ============================== plan 日配额：预留式计数（spec 3.3）==============================

class TestPlanQuotaReservation:
    """日次数闸从"评审完成后写 UsageRecord"改成"发起即占位"。否则检查与写入
    之间隔着整个评审窗口，并发请求全部读到旧计数一起放行（免费档 5 次/天配
    20 次/小时限流，实测能把日限刷到 4 倍，烧的是平台垫付的钱）。"""

    def _plan_mode(self, monkeypatch, cap=3):
        from app.config import settings

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "plan")
        monkeypatch.setattr(settings, "quota_free_reviews_per_day", cap)
        monkeypatch.setattr(settings, "quota_free_cost_usd_per_day", 100.0)

    def test_check_quota_reserves_a_slot_per_approval(self, db, monkeypatch):
        from app.core.errors import QuotaExceeded
        from app.models import UsageRecord
        from app.services import quota_service

        self._plan_mode(monkeypatch)
        uid = "u-plan-reserve"
        for _ in range(3):
            quota_service.check_quota(db, uid, key_source="server", plan="free")

        pending = (
            db.query(UsageRecord)
            .filter(UsageRecord.user_id == uid, UsageRecord.kind == "review_pending")
            .count()
        )
        assert pending == 3, "放行多少次就该占多少个名额"
        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, uid, key_source="server", plan="free")

    def test_release_returns_the_slot(self, db, monkeypatch):
        from app.services import quota_service

        self._plan_mode(monkeypatch)
        uid = "u-plan-release"
        for _ in range(3):
            quota_service.check_quota(db, uid, key_source="server", plan="free")

        assert quota_service.release_review_slot(db, uid, key_source="server") is True
        # 释放 1 个名额后，又能发起一次
        quota_service.check_quota(db, uid, key_source="server", plan="free")
        from app.core.errors import QuotaExceeded

        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, uid, key_source="server", plan="free")

    def test_record_usage_settles_the_reservation_in_place(self, db, monkeypatch):
        """评审完成时把占位**原地改写**成真实用量，而不是再插一条——
        否则一次评审计两次。"""
        from app.models import UsageRecord
        from app.services import quota_service

        self._plan_mode(monkeypatch)
        uid = "u-plan-settle"
        quota_service.check_quota(db, uid, key_source="server", plan="free")
        assert (
            db.query(UsageRecord).filter(UsageRecord.user_id == uid).count() == 1
        )

        quota_service.record_usage(
            db, uid, review_id="rv-settle", cost_usd=0.42, persona_count=6, key_source="server"
        )

        rows = db.query(UsageRecord).filter(UsageRecord.user_id == uid).all()
        assert len(rows) == 1, "结算又插了一条——占位改写成真实用量才算对"
        assert rows[0].kind == "review"
        assert rows[0].review_id == "rv-settle"
        assert rows[0].cost_usd == 0.42

    def test_concurrent_requests_never_exceed_the_daily_cap(self, monkeypatch):
        """并发发起 6 个请求、日上限 3：最多放行 3 个（spec 3.3 的核心断言）。

        SQLite 上单条 INSERT...SELECT 在写锁保护下原子完成；PostgreSQL 上由
        quota 命名空间的事务级 advisory lock 兜底（见 cdk_service.serialize_user_writes）。
        每个线程用独立 session——session 不是线程安全的，不能共用。
        """
        from concurrent.futures import ThreadPoolExecutor

        from app.core.errors import QuotaExceeded
        from app.db import SessionLocal
        from app.services import quota_service

        self._plan_mode(monkeypatch)
        uid = "u-plan-race"

        def _try_check(_):
            s = SessionLocal()
            try:
                quota_service.check_quota(s, uid, key_source="server", plan="free")
                return "passed"
            except QuotaExceeded:
                return "blocked"
            finally:
                s.close()

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(_try_check, range(6)))

        passed = [r for r in results if r == "passed"]
        assert len(passed) <= 3, f"并发放行了 {len(passed)} 个，超过日上限 3：{results}"
        assert len(passed) == 3, f"并发下放行了 {len(passed)} 个，预期恰好 3 个：{results}"

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
