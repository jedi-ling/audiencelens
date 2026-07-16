"""后台管理链路：认证门禁 + 运行时配置覆盖 + 平台 key + 系统概览/巡检。"""

import pytest

from app.config import settings

ADMIN_TOKEN = "test-admin-token-xyz"


@pytest.fixture(autouse=True)
def _reset_admin_state(monkeypatch, db):
    """每个用例结束都清掉覆盖值/平台 key，避免污染其他测试。"""
    from app.models import PlatformSetting, UserApiKey

    yield
    db.query(PlatformSetting).delete()
    db.query(UserApiKey).filter(UserApiKey.user_id == "__platform__").delete()
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


class TestPlansReadonly:
    def test_lists_three_tiers(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        plans = client.get("/api/admin/plans", headers=_headers()).json()["plans"]
        assert {p["id"] for p in plans} == {"free", "pro", "team"}


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

    def test_reviews_list_shape(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        db.add(Review(user_id="anonymous", task_type="steam_page_review", artifact_bundle={}, status="completed", target_title="巡检用例"))
        db.commit()
        rows = client.get("/api/admin/reviews", headers=_headers()).json()["reviews"]
        assert any(r["target_title"] == "巡检用例" for r in rows)
