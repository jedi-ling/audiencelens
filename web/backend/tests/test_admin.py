"""后台管理链路：认证门禁 + 运行时配置覆盖 + 平台 key + 系统概览/巡检。"""

import pytest

from app.config import settings

ADMIN_TOKEN = "test-admin-token-xyz"


@pytest.fixture(autouse=True)
def _reset_admin_state(monkeypatch, db):
    """每个用例结束都清掉覆盖值/平台 key/审计日志，避免污染其他测试。"""
    from app.models import AdminAuditLog, PlatformSetting, UserApiKey

    yield
    db.query(PlatformSetting).delete()
    db.query(UserApiKey).filter(UserApiKey.user_id == "__platform__").delete()
    db.query(AdminAuditLog).delete()
    db.commit()


def _enable_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", ADMIN_TOKEN)


def _headers(token=ADMIN_TOKEN):
    return {"X-Admin-Token": token}


class TestAdminGate:
    def test_disabled_by_default_returns_503(self, client, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "")
        r = client.get("/api/admin/overview")
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "admin_disabled"

    def test_missing_token_401(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.get("/api/admin/overview")
        assert r.status_code == 401

    def test_wrong_token_401(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.get("/api/admin/overview", headers=_headers("wrong-token"))
        assert r.status_code == 401

    def test_correct_token_200(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.get("/api/admin/overview", headers=_headers())
        assert r.status_code == 200


class TestOverview:
    def test_shape(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        body = client.get("/api/admin/overview", headers=_headers()).json()
        assert "reviews" in body and "by_status" in body["reviews"]
        assert "usage_24h" in body
        assert "judgments" in body
        assert "jobs_by_status" in body

    def test_reflects_real_data(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        before = client.get("/api/admin/overview", headers=_headers()).json()
        db.add(Review(user_id="anonymous", task_type="concept_review", artifact_bundle={}, status="completed"))
        db.commit()
        after = client.get("/api/admin/overview", headers=_headers()).json()
        assert after["reviews"]["total"] == before["reviews"]["total"] + 1


class TestSettingsOverride:
    def test_list_shape_and_defaults(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        rows = client.get("/api/admin/settings", headers=_headers()).json()["settings"]
        keys = {r["key"] for r in rows}
        assert "quota_enabled" in keys and "key_mode" in keys
        quota_row = next(r for r in rows if r["key"] == "quota_enabled")
        assert quota_row["overridden"] is False
        assert quota_row["effective_value"] == settings.quota_enabled

    def test_set_and_effective_value_updates(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.put(
            "/api/admin/settings", json={"key": "quota_enabled", "value": True}, headers=_headers()
        )
        assert r.status_code == 200
        assert r.json() == {"key": "quota_enabled", "value": True}

        rows = client.get("/api/admin/settings", headers=_headers()).json()["settings"]
        row = next(x for x in rows if x["key"] == "quota_enabled")
        assert row["overridden"] is True
        assert row["effective_value"] is True

    def test_live_override_reaches_quota_service_without_restart(self, client, monkeypatch, db):
        """核心承诺：改配置不需要重启进程。"""
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", False)  # env 默认关闭
        assert quota_service.usage_summary(db, "anonymous")["quota_enabled"] is False

        _enable_admin(monkeypatch)
        client.put("/api/admin/settings", json={"key": "quota_enabled", "value": True}, headers=_headers())
        assert quota_service.usage_summary(db, "anonymous")["quota_enabled"] is True

        client.delete("/api/admin/settings/quota_enabled", headers=_headers())
        assert quota_service.usage_summary(db, "anonymous")["quota_enabled"] is False

    def test_rejects_unknown_key(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.put("/api/admin/settings", json={"key": "jwt_secret", "value": "x"}, headers=_headers())
        assert r.status_code == 400

    def test_rejects_invalid_choice(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.put("/api/admin/settings", json={"key": "key_mode", "value": "bogus"}, headers=_headers())
        assert r.status_code == 400

    def test_rejects_out_of_range(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.put(
            "/api/admin/settings", json={"key": "review_concurrency", "value": 999}, headers=_headers()
        )
        assert r.status_code == 400

    def test_clear_nonexistent_override_is_noop(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.delete("/api/admin/settings/ratelimit_enabled", headers=_headers())
        assert r.status_code == 200
        assert r.json()["cleared"] is False


class TestPlatformServerKey:
    def test_initially_not_configured(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.get("/api/admin/server-key", headers=_headers()).json()
        assert r["configured"] is False

    def test_set_masks_and_status_updates(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.put(
            "/api/admin/server-key", json={"api_key": "sk-ant-abcdefghijklmnop"}, headers=_headers()
        )
        assert r.status_code == 200
        assert "sk-ant-abcdefghijklmnop" not in r.text  # 绝不回显明文
        assert r.json()["masked"].endswith("mnop")

        status = client.get("/api/admin/server-key", headers=_headers()).json()
        assert status["configured"] is True

    def test_delete_removes_key(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        client.put("/api/admin/server-key", json={"api_key": "sk-ant-tempkey00001"}, headers=_headers())
        r = client.delete("/api/admin/server-key", headers=_headers())
        assert r.json()["deleted"] >= 1
        assert client.get("/api/admin/server-key", headers=_headers()).json()["configured"] is False

    def test_resolve_key_prefers_platform_key_over_env(self, client, monkeypatch, db):
        """managed 模式下，后台设置的平台 key 优先于 env 里的 ANTHROPIC_API_KEY。"""
        from app.services import key_service

        monkeypatch.setattr(settings, "key_mode", "managed")
        monkeypatch.setattr(settings, "server_llm_key", "sk-ant-env-fallback")

        resolved_before = key_service.resolve_key(db, "someone")
        assert resolved_before.key == "sk-ant-env-fallback"
        assert resolved_before.source == "server"

        key_service.save_platform_key(db, "sk-ant-platform-override")
        resolved_after = key_service.resolve_key(db, "someone")
        assert resolved_after.key == "sk-ant-platform-override"
        assert resolved_after.source == "server"

    def test_key_mode_override_takes_effect_live(self, client, monkeypatch, db):
        from app.core.errors import LLMKeyMissing
        from app.services import key_service

        monkeypatch.setattr(settings, "key_mode", "byok")
        with pytest.raises(LLMKeyMissing):
            key_service.resolve_key(db, "nobody-with-key")

        _enable_admin(monkeypatch)
        client.put("/api/admin/settings", json={"key": "key_mode", "value": "managed"}, headers=_headers())
        client.put(
            "/api/admin/server-key", json={"api_key": "sk-ant-live-override"}, headers=_headers()
        )
        resolved = key_service.resolve_key(db, "nobody-with-key")
        assert resolved.key == "sk-ant-live-override"


class TestPlansEditable:
    def test_lists_three_tiers_with_override_metadata(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        plans = client.get("/api/admin/plans", headers=_headers()).json()["plans"]
        assert {p["id"] for p in plans} == {"free", "pro", "team"}
        pro = next(p for p in plans if p["id"] == "pro")
        assert pro["overridden_fields"] == []
        assert "price_usd_month" in pro["editable_fields"]

    def test_override_pro_price_takes_effect_live(self, client, monkeypatch, db):
        from app.services import plan_service

        _enable_admin(monkeypatch)
        r = client.put(
            "/api/admin/plans/pro",
            json={"field": "price_usd_month", "value": 29},
            headers=_headers(),
        )
        assert r.status_code == 200
        assert r.json()["price_usd_month"] == 29.0
        assert plan_service.get_plan("pro", db)["price_usd_month"] == 29.0

        plans = client.get("/api/admin/plans", headers=_headers()).json()["plans"]
        pro = next(p for p in plans if p["id"] == "pro")
        assert pro["overridden_fields"] == ["price_usd_month"]

    def test_reset_plan_field_falls_back_to_static(self, client, monkeypatch, db):
        from app.services import plan_service

        _enable_admin(monkeypatch)
        client.put(
            "/api/admin/plans/team",
            json={"field": "reviews_per_day", "value": 999},
            headers=_headers(),
        )
        assert plan_service.get_plan("team", db)["reviews_per_day"] == 999

        client.delete("/api/admin/plans/team/reviews_per_day", headers=_headers())
        assert plan_service.get_plan("team", db)["reviews_per_day"] == 500

    def test_rejects_unknown_plan(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.put(
            "/api/admin/plans/bogus", json={"field": "price_usd_month", "value": 1}, headers=_headers()
        )
        assert r.status_code == 400

    def test_rejects_non_overridable_field_on_free(self, client, monkeypatch):
        """free 档的额度已经由 quota_free_* 设置项驱动，这里不重复放开。"""
        _enable_admin(monkeypatch)
        r = client.put(
            "/api/admin/plans/free",
            json={"field": "reviews_per_day", "value": 5},
            headers=_headers(),
        )
        assert r.status_code == 400

    def test_rejects_negative_value(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.put(
            "/api/admin/plans/pro", json={"field": "price_usd_month", "value": -5}, headers=_headers()
        )
        assert r.status_code == 400

    def test_public_plans_endpoint_reflects_override(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        client.put(
            "/api/admin/plans/pro", json={"field": "price_usd_month", "value": 39}, headers=_headers()
        )
        plans = client.get("/api/plans").json()["plans"]
        pro = next(p for p in plans if p["id"] == "pro")
        assert pro["price_usd_month"] == 39.0


class TestAuditLog:
    def test_setting_change_is_logged(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        client.put("/api/admin/settings", json={"key": "quota_enabled", "value": True}, headers=_headers())
        entries = client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]
        assert any(e["action"] == "setting.update" and e["target"] == "quota_enabled" for e in entries)

    def test_plan_override_is_logged(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        client.put(
            "/api/admin/plans/pro", json={"field": "price_usd_month", "value": 25}, headers=_headers()
        )
        entries = client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]
        assert any(e["action"] == "plan.override" and e["target"] == "pro.price_usd_month" for e in entries)

    def test_failed_update_is_not_logged(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        client.put("/api/admin/settings", json={"key": "bogus_key", "value": 1}, headers=_headers())
        entries = client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]
        assert not any(e["target"] == "bogus_key" for e in entries)


class TestLedgerAdmin:
    def test_shape(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        body = client.get("/api/admin/ledger", headers=_headers()).json()
        assert "hit_rate" in body and "persona_leaderboard" in body
        assert body["hit_rate"]["persona_id"] is None

    def test_aggregates_across_users(self, client, monkeypatch, db):
        from datetime import datetime, timezone

        from app.models import Judgment, Outcome, Review

        _enable_admin(monkeypatch)
        review = Review(user_id="user-a", task_type="concept_review", artifact_bundle={}, status="completed")
        db.add(review)
        db.commit()
        db.refresh(review)

        j1 = Judgment(review_id=review.id, user_id="user-a", persona_id="p1", claim="claim-a", predicted_at=datetime.now(timezone.utc))
        j2 = Judgment(review_id=review.id, user_id="user-b", persona_id="p1", claim="claim-b", predicted_at=datetime.now(timezone.utc))
        db.add_all([j1, j2])
        db.commit()
        db.refresh(j1)
        db.refresh(j2)
        db.add_all([Outcome(judgment_id=j1.id, verdict="hit"), Outcome(judgment_id=j2.id, verdict="miss")])
        db.commit()

        body = client.get("/api/admin/ledger", headers=_headers()).json()
        assert body["hit_rate"]["sample_size"] >= 2
        leaderboard = body["persona_leaderboard"]
        p1_entry = next((e for e in leaderboard if e["persona_id"] == "p1"), None)
        assert p1_entry is not None
        assert p1_entry["sample_size"] >= 2  # 跨 user-a / user-b 两个用户聚合


class TestTimeseries:
    def test_shape_and_range(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        body = client.get("/api/admin/timeseries?days=7", headers=_headers()).json()
        assert body["days"] == 7
        assert len(body["series"]) == 8  # 含今天，共 days+1 个点
        assert set(body["series"][0].keys()) == {
            "date", "reviews_total", "reviews_completed", "reviews_failed", "cost_usd",
            "input_tokens", "output_tokens", "tokens_total",
        }

    def test_reflects_new_review(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        before = client.get("/api/admin/timeseries?days=1", headers=_headers()).json()
        db.add(Review(user_id="anonymous", task_type="concept_review", artifact_bundle={}, status="completed"))
        db.commit()
        after = client.get("/api/admin/timeseries?days=1", headers=_headers()).json()
        assert after["series"][-1]["reviews_total"] >= before["series"][-1]["reviews_total"] + 1

    def test_clamps_days_range(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        body = client.get("/api/admin/timeseries?days=9999", headers=_headers()).json()
        assert body["days"] == 90


class TestJobsAndReviewsInspection:
    def test_jobs_list_shape(self, client, monkeypatch):
        from app.services import job_service

        _enable_admin(monkeypatch)
        job_service.create_job(kind="review", ref_id="r-admin-test")
        rows = client.get("/api/admin/jobs", headers=_headers()).json()["jobs"]
        assert any(j["ref_id"] == "r-admin-test" for j in rows)

    def test_jobs_filter_by_status(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.get("/api/admin/jobs?status=queued", headers=_headers())
        assert r.status_code == 200
        assert all(j["status"] == "queued" for j in r.json()["jobs"])

    def test_jobs_filter_by_user_id(self, client, monkeypatch):
        from app.services import job_service

        _enable_admin(monkeypatch)
        job_service.create_job(kind="review", ref_id="r-user-filter", user_id="user-filter-test")
        rows = client.get(
            "/api/admin/jobs?user_id=user-filter-test", headers=_headers()
        ).json()["jobs"]
        assert len(rows) >= 1
        assert all(j["user_id"] == "user-filter-test" for j in rows)

    def test_jobs_pagination_total_and_offset(self, client, monkeypatch):
        from app.services import job_service

        _enable_admin(monkeypatch)
        for i in range(3):
            job_service.create_job(kind="review", ref_id=f"r-page-{i}")
        page1 = client.get("/api/admin/jobs?limit=1&offset=0", headers=_headers()).json()
        page2 = client.get("/api/admin/jobs?limit=1&offset=1", headers=_headers()).json()
        assert page1["total"] >= 3
        assert len(page1["jobs"]) == 1
        assert page1["jobs"][0]["id"] != page2["jobs"][0]["id"]

    def test_job_detail_includes_payload(self, client, monkeypatch):
        from app.services import job_service

        _enable_admin(monkeypatch)
        job_id = job_service.create_job(kind="review", ref_id="r-detail-test", payload={"foo": "bar"})
        r = client.get(f"/api/admin/jobs/{job_id}", headers=_headers())
        assert r.status_code == 200
        assert r.json()["payload"] == {"foo": "bar"}

    def test_job_detail_404(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.get("/api/admin/jobs/does-not-exist", headers=_headers())
        assert r.status_code == 404

    def test_reviews_list_shape(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        db.add(Review(user_id="anonymous", task_type="steam_page_review", artifact_bundle={}, status="completed", target_title="巡检用例"))
        db.commit()
        rows = client.get("/api/admin/reviews", headers=_headers()).json()["reviews"]
        assert any(r["target_title"] == "巡检用例" for r in rows)

    def test_reviews_filter_by_user_id_and_pagination(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        db.add(Review(user_id="user-review-filter", task_type="concept_review", artifact_bundle={}, status="completed"))
        db.commit()
        rows = client.get(
            "/api/admin/reviews?user_id=user-review-filter", headers=_headers()
        ).json()["reviews"]
        assert len(rows) >= 1
        assert all(r["user_id"] == "user-review-filter" for r in rows)

    def test_review_detail_includes_report(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        review = Review(
            user_id="anonymous",
            task_type="concept_review",
            artifact_bundle={},
            status="completed",
            report_json={"executive_summary": "详情钻取测试"},
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        r = client.get(f"/api/admin/reviews/{review.id}", headers=_headers())
        assert r.status_code == 200
        assert r.json()["report_json"]["executive_summary"] == "详情钻取测试"

    def test_review_detail_404(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.get("/api/admin/reviews/does-not-exist", headers=_headers())
        assert r.status_code == 404


class TestUserManagement:
    def _make_user(self, db, email="managed@example.com", plan="free"):
        from app.core.security import hash_password
        from app.models import User

        user = User(email=email, password_hash=hash_password("password123"), plan=plan)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def test_list_users_with_aggregates(self, client, monkeypatch, db):
        from app.models import Review, UsageRecord

        _enable_admin(monkeypatch)
        user = self._make_user(db, email="aggr@example.com")
        db.add(Review(user_id=user.id, task_type="concept_review", artifact_bundle={}, status="completed"))
        db.add(UsageRecord(user_id=user.id, kind="review", cost_usd=1.25, key_source="server"))
        db.commit()

        body = client.get("/api/admin/users?q=aggr", headers=_headers()).json()
        assert body["total"] >= 1
        row = next(u for u in body["users"] if u["email"] == "aggr@example.com")
        assert row["reviews_total"] == 1
        assert row["cost_usd_total"] == 1.25

    def test_update_plan_and_active(self, client, monkeypatch, db):
        _enable_admin(monkeypatch)
        user = self._make_user(db, email="plan-change@example.com")

        r = client.put(
            f"/api/admin/users/{user.id}", json={"plan": "pro", "is_active": False}, headers=_headers()
        )
        assert r.status_code == 200
        assert r.json()["plan"] == "pro"
        assert r.json()["is_active"] is False

        entries = client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]
        assert any(e["action"] == "user.update" and e["target"] == "plan-change@example.com" for e in entries)

    def test_update_rejects_unknown_plan(self, client, monkeypatch, db):
        _enable_admin(monkeypatch)
        user = self._make_user(db, email="bad-plan@example.com")
        r = client.put(f"/api/admin/users/{user.id}", json={"plan": "platinum"}, headers=_headers())
        assert r.status_code == 400

    def test_update_requires_some_field(self, client, monkeypatch, db):
        _enable_admin(monkeypatch)
        user = self._make_user(db, email="empty-update@example.com")
        r = client.put(f"/api/admin/users/{user.id}", json={}, headers=_headers())
        assert r.status_code == 400

    def test_update_missing_user_404(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.put("/api/admin/users/nope", json={"plan": "pro"}, headers=_headers())
        assert r.status_code == 404

    def test_disabled_user_cannot_login(self, client, monkeypatch, db):
        """停用要真的生效——不是只改个字段给后台看。"""
        _enable_admin(monkeypatch)
        monkeypatch.setattr(settings, "auth_enabled", True)
        user = self._make_user(db, email="disabled@example.com")
        client.put(f"/api/admin/users/{user.id}", json={"is_active": False}, headers=_headers())

        r = client.post(
            "/api/auth/login", json={"email": "disabled@example.com", "password": "password123"}
        )
        assert r.status_code == 401


class TestAdminStats:
    def test_task_type_stats_reflect_data(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        db.add(Review(user_id="anonymous", task_type="pitch_review", artifact_bundle={}, status="completed", total_cost_usd=0.5))
        db.add(Review(user_id="anonymous", task_type="pitch_review", artifact_bundle={}, status="failed"))
        db.commit()

        body = client.get("/api/admin/stats/task-types", headers=_headers()).json()
        row = next(t for t in body["task_types"] if t["task_type"] == "pitch_review")
        assert row["total"] >= 2
        assert row["completed"] >= 1
        assert row["failed"] >= 1
        assert row["cost_usd"] >= 0.5

    def test_persona_pack_stats(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        db.add(Review(user_id="anonymous", task_type="pitch_review", artifact_bundle={}, persona_pack="startup-panel", status="completed"))
        db.commit()

        body = client.get("/api/admin/stats/persona-packs", headers=_headers()).json()
        assert any(p["persona_pack"] == "startup-panel" for p in body["persona_packs"])

    def test_cost_stats_by_source_and_top_users(self, client, monkeypatch, db):
        from app.core.security import hash_password
        from app.models import UsageRecord, User

        _enable_admin(monkeypatch)
        user = User(email="whale@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(UsageRecord(user_id=user.id, kind="review", cost_usd=9.9, key_source="server"))
        db.add(UsageRecord(user_id="anonymous", kind="review", cost_usd=0.1, key_source="byok"))
        db.commit()

        body = client.get("/api/admin/stats/costs?days=7", headers=_headers()).json()
        assert body["cost_by_source"].get("server", 0) >= 9.9
        assert body["cost_by_source"].get("byok", 0) >= 0.1
        top = body["top_users"][0]
        assert top["email"] == "whale@example.com"
        assert top["cost_usd"] >= 9.9


class TestAdminDeleteReview:
    def test_delete_review_cascades_and_audits(self, client, monkeypatch, db):
        from datetime import datetime, timezone

        from app.models import Judgment, Review

        _enable_admin(monkeypatch)
        review = Review(user_id="anonymous", task_type="concept_review", artifact_bundle={}, status="completed", target_title="待删评审")
        db.add(review)
        db.commit()
        db.refresh(review)
        db.add(Judgment(review_id=review.id, user_id="anonymous", claim="x", predicted_at=datetime.now(timezone.utc)))
        db.commit()

        r = client.delete(f"/api/admin/reviews/{review.id}", headers=_headers())
        assert r.status_code == 200

        assert db.query(Review).filter(Review.id == review.id).count() == 0
        assert db.query(Judgment).filter(Judgment.review_id == review.id).count() == 0

        entries = client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]
        assert any(e["action"] == "review.delete" and e["target"] == review.id for e in entries)

    def test_delete_missing_review_404(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        r = client.delete("/api/admin/reviews/nope", headers=_headers())
        assert r.status_code == 404
