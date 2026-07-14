"""逐条验证「预埋线」是否真的通电——不是 TODO 注释，是能跑的链路。"""

import importlib

import pytest


# ============================== 健康检查 / 配置 ==============================

class TestHealth:
    def test_health_exposes_switches(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        cfg = r.json()["config"]
        for k in (
            "auth_enabled",
            "key_mode",
            "quota_enabled",
            "ratelimit_enabled",
            "queue_backend",
            "ledger_enabled",
        ):
            assert k in cfg

    def test_health_never_leaks_secret(self, client):
        body = client.get("/api/health").text
        assert "sk-" not in body
        assert "server_llm_key" not in body  # 只暴露 server_key_present 布尔


# ============================== 身份（默认匿名）==============================

class TestIdentity:
    def test_anonymous_by_default(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["is_anonymous"] is True
        assert r.json()["user_id"] == "anonymous"

    def test_register_blocked_when_auth_disabled(self, client):
        r = client.post(
            "/api/auth/register",
            json={"email": "a@b.com", "password": "12345678"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "bad_request"


# ============================== 认证原语 ==============================

class TestSecurityPrimitives:
    def test_password_roundtrip(self):
        from app.core.security import hash_password, verify_password

        h = hash_password("correct horse battery")
        assert verify_password("correct horse battery", h)
        assert not verify_password("wrong", h)

    def test_jwt_roundtrip_and_tamper(self):
        from app.core.security import create_token, decode_token

        t = create_token("user-1", "s3cret", 60)
        assert decode_token(t, "s3cret")["sub"] == "user-1"
        with pytest.raises(ValueError):
            decode_token(t, "other-secret")

    def test_jwt_expired(self):
        from app.core.security import create_token, decode_token

        t = create_token("u", "s", -1)
        with pytest.raises(ValueError):
            decode_token(t, "s")

    def test_key_encryption_roundtrip(self):
        from app.core.security import decrypt_secret, encrypt_secret, mask_key

        blob = encrypt_secret("sk-ant-abcdefghijklmnop", "master")
        assert "sk-ant" not in blob  # 密文里不该有明文
        assert decrypt_secret(blob, "master") == "sk-ant-abcdefghijklmnop"
        with pytest.raises(ValueError):
            decrypt_secret(blob, "wrong-master")
        assert mask_key("sk-ant-abcdefghijklmnop").endswith("mnop")


# ============================== BYOK key 解析链 ==============================

class TestKeyResolution:
    def test_byok_missing_key_raises_428(self, db, monkeypatch):
        from app.config import settings
        from app.core.errors import LLMKeyMissing
        from app.services import key_service

        monkeypatch.setattr(settings, "key_mode", "byok")
        with pytest.raises(LLMKeyMissing) as e:
            key_service.resolve_key(db, "nobody")
        assert e.value.status_code == 428

    def test_byok_user_key_wins(self, db, monkeypatch):
        from app.config import settings
        from app.services import key_service

        monkeypatch.setattr(settings, "key_mode", "byok")
        key_service.save_user_key(db, "u-byok", "sk-ant-user-key")
        resolved = key_service.resolve_key(db, "u-byok")
        assert resolved.key == "sk-ant-user-key"
        assert resolved.source == "byok"

    def test_managed_uses_server_key(self, db, monkeypatch):
        from app.config import settings
        from app.services import key_service

        monkeypatch.setattr(settings, "key_mode", "managed")
        monkeypatch.setattr(settings, "server_llm_key", "sk-ant-server")
        resolved = key_service.resolve_key(db, "u-any")
        assert resolved.source == "server"

    def test_hybrid_falls_back_to_server(self, db, monkeypatch):
        from app.config import settings
        from app.services import key_service

        monkeypatch.setattr(settings, "key_mode", "hybrid")
        monkeypatch.setattr(settings, "server_llm_key", "sk-ant-server")
        resolved = key_service.resolve_key(db, "u-no-key-here")
        assert resolved.source == "server"

    def test_rotation_deactivates_old(self, db, monkeypatch):
        from app.config import settings
        from app.services import key_service

        monkeypatch.setattr(settings, "key_mode", "byok")
        key_service.save_user_key(db, "u-rot", "sk-ant-old")
        key_service.save_user_key(db, "u-rot", "sk-ant-new")
        assert key_service.resolve_key(db, "u-rot").key == "sk-ant-new"


# ============================== 评审入口：无 key 必须拒绝 ==============================

class TestReviewGuards:
    def test_create_review_without_key_returns_428(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "key_mode", "byok")
        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "x", "materials": [{"type": "t", "text": "核心循环"}]},
            },
        )
        assert r.status_code == 428
        assert r.json()["error"]["code"] == "llm_key_missing"
        # 关键：绝不返回模拟数据，而是明确要求配置 key
        assert "模拟" in r.json()["error"]["message"]

    def test_unknown_task_type_rejected(self, client, db, monkeypatch):
        from app.config import settings
        from app.services import key_service

        monkeypatch.setattr(settings, "key_mode", "byok")
        key_service.save_user_key(db, "anonymous", "sk-ant-test")
        r = client.post(
            "/api/v2/reviews",
            json={"task_type": "nope", "artifact": {"title": "x", "materials": []}},
        )
        assert r.status_code == 400
        key_service.delete_user_key(db, "anonymous")


# ============================== 意图解析（对话式入口）==============================

class TestIntent:
    def test_heuristic_steam_page(self):
        from app.services.intent_service import parse_intent_heuristic

        r = parse_intent_heuristic("帮我看看这个 Roguelike 的 Steam 商店页够不够打")
        assert r.task_type == "steam_page_review"
        assert r.method == "heuristic"
        assert r.confidence > 0.5

    def test_heuristic_monetization_and_mode(self):
        from app.services.intent_service import parse_intent_heuristic

        r = parse_intent_heuristic("全面看看我的付费设计，付费墙会不会太早")
        assert r.task_type == "monetization_review"
        assert r.mode == "full"

    def test_heuristic_picks_pack(self):
        from app.services.intent_service import parse_intent_heuristic

        r = parse_intent_heuristic("我这个手游的月卡定价合理吗")
        assert r.persona_pack == "mobile-f2p"

    def test_ambiguous_asks_for_clarification(self):
        from app.services.intent_service import parse_intent_heuristic

        r = parse_intent_heuristic("帮我看看")
        assert r.needs_clarification is True
        assert r.clarifying_question

    def test_endpoint_degrades_without_key(self, client):
        r = client.post("/api/intent/parse", json={"text": "评审我的 Steam 页面"})
        assert r.status_code == 200
        body = r.json()
        assert body["task_type"] == "steam_page_review"
        assert body["method"] == "heuristic"  # 如实声明降级了


# ============================== 上传 ==============================

class TestUpload:
    def test_upload_text(self, client):
        r = client.post(
            "/api/uploads",
            files={"file": ("concept.md", "核心循环是探索-战斗-成长".encode(), "text/markdown")},
        )
        assert r.status_code == 200
        assert "核心循环" in r.json()["text"]

    def test_upload_rejects_bad_ext(self, client):
        r = client.post(
            "/api/uploads", files={"file": ("evil.exe", b"MZ", "application/octet-stream")}
        )
        assert r.status_code == 400


# ============================== 配额 / 用量 ==============================

class TestQuota:
    def test_usage_endpoint(self, client):
        r = client.get("/api/usage")
        assert r.status_code == 200
        assert "reviews_used" in r.json()

    def test_byok_never_counts_against_quota(self, db, monkeypatch):
        from app.config import settings
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_free_reviews_per_day", 1)
        for _ in range(5):
            quota_service.record_usage(db, "u-byok-q", cost_usd=1.0, key_source="byok")
        # BYOK 花的是用户自己的钱 —— 不该被限
        quota_service.check_quota(db, "u-byok-q", key_source="byok")

    def test_server_key_hits_quota(self, db, monkeypatch):
        from app.config import settings
        from app.core.errors import QuotaExceeded
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_free_reviews_per_day", 2)
        for _ in range(2):
            quota_service.record_usage(db, "u-srv-q", cost_usd=0.01, key_source="server")
        with pytest.raises(QuotaExceeded):
            quota_service.check_quota(db, "u-srv-q", key_source="server")

    def test_usage_recorded_even_when_quota_off(self, db, monkeypatch):
        """关键：配额没开也要记账 —— 否则等你想收费时没有历史数据。"""
        from app.config import settings
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", False)
        quota_service.record_usage(db, "u-off", cost_usd=0.5, key_source="server")
        s = quota_service.usage_summary(db, "u-off")
        assert s["cost_usd_total"] >= 0.5


# ============================== 限流 ==============================

class TestRateLimit:
    def test_token_bucket_blocks_after_limit(self):
        from app.core.ratelimit import InMemoryTokenBucket

        b = InMemoryTokenBucket()
        assert all(b.allow("k", 3, 60) for _ in range(3))
        assert not b.allow("k", 3, 60)

    def test_buckets_are_per_key(self):
        from app.core.ratelimit import InMemoryTokenBucket

        b = InMemoryTokenBucket()
        for _ in range(3):
            b.allow("a", 3, 60)
        assert b.allow("b", 3, 60)  # 另一个 key 不受影响


# ============================== 任务队列 ==============================

class TestJobQueue:
    def test_job_lifecycle(self):
        import time

        from app.services import job_service

        done = []
        job_id = job_service.create_job(kind="review", ref_id="r-1")
        job_service.get_backend().submit(job_id, lambda: done.append(1))

        for _ in range(50):
            job = job_service.get_job(job_id)
            if job["status"] in ("done", "failed"):
                break
            time.sleep(0.05)
        assert done == [1]
        assert job_service.get_job(job_id)["status"] == "done"

    def test_job_failure_is_recorded(self):
        import time

        from app.services import job_service

        def boom():
            raise RuntimeError("炸了")

        job_id = job_service.create_job(kind="review", ref_id="r-2")
        job_service.get_backend().submit(job_id, boom)

        for _ in range(50):
            job = job_service.get_job(job_id)
            if job["status"] in ("done", "failed"):
                break
            time.sleep(0.05)
        job = job_service.get_job(job_id)
        assert job["status"] == "failed"
        assert "炸了" in job["error_message"]


# ============================== 判断复利闭环 ==============================

class TestLedger:
    def _report(self):
        return {
            "priority_fixes": [
                {"title": "新手引导太长会劝退", "severity": "high", "why_it_matters": "前15分钟"},
                {"title": "定价偏高", "severity": "medium"},
            ],
            "persona_notes": [
                {
                    "persona_id": "P14",
                    "confidence": 0.8,
                    "key_issues": [{"title": "价格超出心理预期", "severity": "high"}],
                }
            ],
        }

    def test_extract_judgments(self):
        from app.services.ledger_service import extract_judgments_from_report

        rows = extract_judgments_from_report(self._report())
        claims = [r["claim"] for r in rows]
        assert "新手引导太长会劝退" in claims
        assert "价格超出心理预期" in claims
        assert any(r["persona_id"] == "P14" for r in rows)

    def test_record_and_verify_and_hit_rate(self, db):
        from app.models import Review
        from app.services import ledger_service

        review = Review(
            user_id="u-ledger",
            task_type="concept_review",
            artifact_bundle={"title": "t"},
            status="completed",
        )
        db.add(review)
        db.commit()
        db.refresh(review)

        n = ledger_service.record_judgments(db, review, self._report())
        assert n == 3

        judgments = ledger_service.list_judgments(db, "u-ledger")
        assert len(judgments) == 3
        assert all(j["outcome"] is None for j in judgments)  # 尚未验证

        # 真人测试回来：两条说中、一条没发生
        ledger_service.verify_judgment(db, judgments[0]["id"], "hit", "u-ledger")
        ledger_service.verify_judgment(db, judgments[1]["id"], "hit", "u-ledger")
        ledger_service.verify_judgment(db, judgments[2]["id"], "miss", "u-ledger")

        stats = ledger_service.hit_rate(db, "u-ledger")
        assert stats["hit"] == 2
        assert stats["miss"] == 1
        assert stats["hit_rate"] == round(2 / 3, 3)
        # 诚实：样本太少必须标注
        assert stats["low_confidence"] is True
        assert "不具统计意义" in stats["note"]

    def test_verify_rejects_bad_verdict(self, db):
        from app.core.errors import BadRequest
        from app.models import Review
        from app.services import ledger_service

        review = Review(user_id="u-bad", task_type="concept_review", artifact_bundle={}, status="completed")
        db.add(review)
        db.commit()
        ledger_service.record_judgments(db, review, self._report())
        jid = ledger_service.list_judgments(db, "u-bad")[0]["id"]
        with pytest.raises(BadRequest):
            ledger_service.verify_judgment(db, jid, "maybe", "u-bad")

    def test_cannot_verify_others_judgment(self, db):
        from app.core.errors import NotFound
        from app.models import Review
        from app.services import ledger_service

        review = Review(user_id="owner", task_type="concept_review", artifact_bundle={}, status="completed")
        db.add(review)
        db.commit()
        ledger_service.record_judgments(db, review, self._report())
        jid = ledger_service.list_judgments(db, "owner")[0]["id"]
        with pytest.raises(NotFound):
            ledger_service.verify_judgment(db, jid, "hit", "attacker")

    def test_ledger_endpoints(self, client):
        assert client.get("/api/ledger/judgments").status_code == 200
        assert client.get("/api/ledger/hit-rate").status_code == 200
        assert client.get("/api/ledger/leaderboard").status_code == 200


# ============================== 错误契约 ==============================

class TestErrorContract:
    def test_404_shape(self, client):
        r = client.get("/api/v2/reviews/does-not-exist")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"

    def test_request_id_header(self, client):
        r = client.get("/api/health")
        assert r.headers.get("X-Request-Id")
