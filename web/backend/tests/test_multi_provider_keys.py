"""BYOK 多服务商支持："国产模型能不能用" + "测试连接按钮测的是不是真链路"。

覆盖：
  1. BYOK key 能保存 provider/model/api_base（非 Anthropic 档 model 必填）
  2. resolve_key 把这些字段透传出来（供 review_service 传给真实引擎）
  3. /api/keys/test 和 /api/admin/server-key/test 真的调用 runner.llm_client
     （mock 掉，不发真实网络请求），不是另一套摆设
  4. 图片上传返回 data URI，非法类型/超限被拒
"""

from unittest.mock import patch

import pytest

ADMIN_TOKEN = "test-admin-token-xyz"


def _admin_headers():
    return {"X-Admin-Token": ADMIN_TOKEN}


@pytest.fixture(autouse=True)
def _reset_keys(db):
    from app.models import UserApiKey

    yield
    db.query(UserApiKey).delete()
    db.commit()


class TestSaveKeyWithProvider:
    def test_anthropic_key_does_not_require_model(self, client):
        r = client.post("/api/keys", json={"api_key": "sk-ant-test-key"})
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "anthropic"
        assert body["model"] is None

    def test_openai_compatible_requires_model(self, client):
        r = client.post(
            "/api/keys",
            json={"api_key": "sk-deepseek-test", "provider": "openai_compatible"},
        )
        assert r.status_code == 400

    def test_openai_compatible_saves_model_and_base(self, client):
        r = client.post(
            "/api/keys",
            json={
                "api_key": "sk-deepseek-test",
                "provider": "openai_compatible",
                "model": "deepseek-chat",
                "api_base": "https://api.deepseek.com",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["model"] == "deepseek-chat"
        assert body["api_base"] == "https://api.deepseek.com"

    def test_list_keys_exposes_model_and_base(self, client):
        client.post(
            "/api/keys",
            json={
                "api_key": "sk-kimi-test",
                "provider": "openai_compatible",
                "model": "moonshot-v1-8k",
                "api_base": "https://api.moonshot.cn/v1",
            },
        )
        rows = client.get("/api/keys").json()["keys"]
        row = next(k for k in rows if k["provider"] == "openai_compatible")
        assert row["model"] == "moonshot-v1-8k"
        assert row["masked"]
        assert "sk-kimi-test" not in str(row)  # 绝不回显明文


class TestResolveKeyCarriesProviderConfig:
    def test_byok_deepseek_resolves_with_model_and_base(self, client, db):
        from app.services import key_service

        key_service.save_user_key(
            db, "anonymous", "sk-deepseek-real", provider="openai_compatible",
            model="deepseek-chat", api_base="https://api.deepseek.com",
        )
        resolved = key_service.resolve_key(db, "anonymous", provider="openai_compatible")
        assert resolved.source == "byok"
        assert resolved.model == "deepseek-chat"
        assert resolved.api_base == "https://api.deepseek.com"

    def test_anthropic_byok_has_no_model_override_by_default(self, client, db):
        from app.services import key_service

        key_service.save_user_key(db, "anonymous", "sk-ant-real", provider="anthropic")
        resolved = key_service.resolve_key(db, "anonymous", provider="anthropic")
        assert resolved.model is None  # 引擎会退回人格分级选型

    def test_default_anthropic_lookup_falls_back_to_users_only_saved_provider(self, client, db):
        """用户只填了 DeepSeek，没填 Anthropic：创建评审时 resolve_llm_key 内部仍按
        provider="anthropic" 默认值去查——不该因为这个硬编码默认值就报 428 llm_key_missing。
        """
        from app.services import key_service

        key_service.save_user_key(
            db, "anonymous", "sk-deepseek-only", provider="openai_compatible",
            model="deepseek-chat", api_base="https://api.deepseek.com",
        )
        resolved = key_service.resolve_key(db, "anonymous")  # 不传 provider，走默认值
        assert resolved.source == "byok"
        assert resolved.provider == "openai_compatible"
        assert resolved.model == "deepseek-chat"


class TestKeyTestEndpoint:
    def test_test_unsaved_key_calls_llm_client(self, client):
        with patch("runner.llm_client.test_connection") as mock_test:
            mock_test.return_value = {"connected": True, "model": "deepseek-chat", "sample": "pong"}
            r = client.post(
                "/api/keys/test",
                json={
                    "api_key": "sk-deepseek-fresh",
                    "provider": "openai_compatible",
                    "model": "deepseek-chat",
                    "api_base": "https://api.deepseek.com",
                },
            )
        assert r.status_code == 200
        assert r.json()["connected"] is True
        mock_test.assert_called_once()
        _, kwargs = mock_test.call_args
        assert kwargs["api_key"] == "sk-deepseek-fresh"
        assert kwargs["provider"] == "openai_compatible"

    def test_test_openai_compatible_without_model_rejected(self, client):
        r = client.post(
            "/api/keys/test",
            json={"api_key": "x", "provider": "openai_compatible"},
        )
        assert r.status_code == 400

    def test_test_already_saved_key_without_resending(self, client, db):
        from app.services import key_service

        key_service.save_user_key(
            db, "anonymous", "sk-deepseek-saved", provider="openai_compatible",
            model="deepseek-chat", api_base="https://api.deepseek.com",
        )
        with patch("runner.llm_client.test_connection") as mock_test:
            mock_test.return_value = {"connected": True, "model": "deepseek-chat", "sample": "ok"}
            r = client.post("/api/keys/test", json={"provider": "openai_compatible"})
        assert r.status_code == 200
        _, kwargs = mock_test.call_args
        assert kwargs["api_key"] == "sk-deepseek-saved"

    def test_test_with_no_saved_and_no_key_errors(self, client):
        r = client.post("/api/keys/test", json={"provider": "anthropic"})
        assert r.status_code == 400

    def test_test_reports_failure_without_500(self, client):
        with patch("runner.llm_client.test_connection") as mock_test:
            mock_test.return_value = {"connected": False, "error": "401 unauthorized"}
            r = client.post(
                "/api/keys/test",
                json={"api_key": "bad", "provider": "anthropic", "model": "claude-sonnet-4-20250514"},
            )
        assert r.status_code == 200
        assert r.json()["connected"] is False


class TestAdminServerKeyMultiProvider:
    def _enable_admin(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "admin_token", ADMIN_TOKEN)

    def test_set_server_key_with_provider(self, client, monkeypatch, db):
        self._enable_admin(monkeypatch)
        r = client.put(
            "/api/admin/server-key",
            json={
                "api_key": "sk-glm-platform",
                "provider": "openai_compatible",
                "model": "glm-4",
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
            },
            headers=_admin_headers(),
        )
        assert r.status_code == 200
        assert r.json()["model"] == "glm-4"

        from app.models import UserApiKey

        db.query(UserApiKey).delete()
        db.commit()

    def test_test_server_key_endpoint(self, client, monkeypatch, db):
        self._enable_admin(monkeypatch)
        client.put(
            "/api/admin/server-key",
            json={
                "api_key": "sk-glm-platform",
                "provider": "openai_compatible",
                "model": "glm-4",
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
            },
            headers=_admin_headers(),
        )
        with patch("runner.llm_client.test_connection") as mock_test:
            mock_test.return_value = {"connected": True, "model": "glm-4", "sample": "你好"}
            r = client.post(
                "/api/admin/server-key/test?provider=openai_compatible", headers=_admin_headers()
            )
        assert r.status_code == 200
        assert r.json()["connected"] is True

        from app.models import UserApiKey

        db.query(UserApiKey).delete()
        db.commit()

    def test_test_server_key_not_configured(self, client, monkeypatch):
        self._enable_admin(monkeypatch)
        r = client.post("/api/admin/server-key/test?provider=anthropic", headers=_admin_headers())
        assert r.status_code == 400


class TestImageUpload:
    def test_upload_image_returns_data_uri(self, client):
        import io

        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000a49444154789c6300010000050001"
        )
        r = client.post(
            "/api/uploads",
            files={"file": ("shot.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "image"
        assert body["image_data"].startswith("data:image/png;base64,")

    def test_upload_text_still_works(self, client):
        import io

        r = client.post(
            "/api/uploads",
            files={"file": ("notes.txt", io.BytesIO(b"hello world"), "text/plain")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "text"
        assert body["text"] == "hello world"

    def test_unsupported_extension_rejected(self, client):
        import io

        r = client.post(
            "/api/uploads",
            files={"file": ("virus.exe", io.BytesIO(b"x"), "application/octet-stream")},
        )
        assert r.status_code == 400
