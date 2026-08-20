"""逐条验证「预埋线」是否真的通电——不是 TODO 注释，是能跑的链路。"""

import importlib

import pytest


# ============================== 健康检查 / 配置 ==============================

class TestHealth:
    def test_health_exposes_switches(self, client):
        """只暴露前端真的要用的四个开关。

        这条原来还断言 ratelimit_enabled / queue_backend / ledger_enabled
        必须存在。它们后来被移出公开响应了——/api/health 不鉴权，而前端
        （唯一消费点 session-store.ts）从没读过这三个；
        ratelimit_enabled=false + quota_enabled=false + server_key_present=true
        组合起来正是"这里可以免费无限调模型"的侦察信息。

        字段集的完整约束（不许多给 / 不许少给 / 白名单里的必须真有人读）
        在 test_health_config_parity.py 里，这里只保底钉住四个必需项。
        """
        r = client.get("/api/health")
        assert r.status_code == 200
        cfg = r.json()["config"]
        for k in ("auth_enabled", "key_mode", "quota_enabled", "server_key_present"):
            assert k in cfg, f"前端依赖 {k}，它必须留在 /api/health 里"

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
    def test_v2_request_accepts_adaptive_panel_switch(self):
        from app.api.platform import CreateReviewRequest

        body = CreateReviewRequest(
            task_type="concept_review",
            artifact={"title": "x", "materials": []},
            adaptive_panel=True,
        )
        assert body.adaptive_panel is True

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

    def test_explicit_predictions_take_priority_and_keep_verification_contract(self, db):
        from app.models import Judgment, Review
        from app.services import ledger_service

        report = {
            "predictions": [
                {
                    "prediction_id": "PRED-001",
                    "type": "intervention_hypothesis",
                    "claim": "修复首屏价格信息后，paid_conversion_rate 相较当前版本将提高",
                    "issue": "首屏没有价格",
                    "intervention": "首屏展示价格",
                    "target_metric": "paid_conversion_rate",
                    "direction": "increase",
                    "comparison": "treatment_vs_current_control",
                    "success_criterion": "treatment.paid_conversion_rate > control.paid_conversion_rate",
                    "verification_window": "14d",
                    "verification_method": "controlled_comparison",
                    "severity": "high",
                    "confidence": 0.7,
                    "confidence_basis": "synthetic_panel_heuristic_not_empirically_calibrated",
                    "affected_personas": ["P01", "P02"],
                    "evidence": "两位合成人格均无法判断价值",
                    "is_synthetic": True,
                }
            ],
            # predictions 存在时不能再把旧 priority_fix 重复落一次。
            "priority_fixes": [{"title": "首屏没有价格", "severity": "high"}],
        }
        rows = ledger_service.extract_judgments_from_report(report)
        assert len(rows) == 1
        assert rows[0]["evidence"]["target_metric"] == "paid_conversion_rate"

        review = Review(
            user_id="u-prediction-contract",
            task_type="pricing_page_review",
            artifact_bundle={},
            status="completed",
        )
        db.add(review)
        db.commit()
        assert ledger_service.record_judgments(db, review, report) == 1
        stored = db.query(Judgment).filter(Judgment.review_id == review.id).one()
        assert stored.evidence["verification_method"] == "controlled_comparison"
        assert stored.evidence["confidence_basis"].endswith("not_empirically_calibrated")

    def test_only_unverified_filters_before_the_limit(self, db):
        """**先截断再过滤会静默丢数据。**

        原实现是 SQL 里 `.limit(n)` 取最新 n 条，再在 Python 里跳过已回填的。
        于是"最新的都已回填、更早的还欠着"这个再正常不过的状态下，接口会返回
        空列表——而首页那张待验证追踪卡直接显示这个数，用户会看到「0 条待验证」
        然后以为自己回填完了。

        这里用 limit=2 复现同一形状（不必造 200 行）：3 条判断、最新 2 条已回填，
        问"未回填的有哪些"，正确答案是那 1 条最早的，不是空。
        """
        from datetime import datetime, timedelta, timezone

        from app.models import Judgment, Review
        from app.services import ledger_service

        review = Review(
            user_id="u-limit-order",
            task_type="concept_review",
            artifact_bundle={"title": "t"},
            status="completed",
        )
        db.add(review)
        db.flush()

        now = datetime.now(timezone.utc)
        ids = []
        for days_ago, claim in [(9, "最早·还欠着"), (2, "较新·已回填"), (1, "最新·已回填")]:
            j = Judgment(
                review_id=review.id,
                user_id="u-limit-order",
                claim=claim,
                predicted_at=now - timedelta(days=days_ago),
            )
            db.add(j)
            db.flush()
            ids.append(j.id)
        db.commit()

        ledger_service.verify_judgment(db, ids[1], "hit", "u-limit-order")
        ledger_service.verify_judgment(db, ids[2], "hit", "u-limit-order")

        rows = ledger_service.list_judgments(
            db, "u-limit-order", only_unverified=True, limit=2
        )["judgments"]

        assert len(rows) == 1, (
            "未回填的那条被 limit 挤掉了——截断发生在过滤之前。"
            f"实际返回 {len(rows)} 条：{[r['claim'] for r in rows]}"
        )
        assert rows[0]["claim"] == "最早·还欠着"

    def test_list_judgments_carries_review_context(self, db):
        """待验证追踪卡按项目分组，靠的是 list_judgments 随行带出的评审上下文。
        缺了这两个字段前端不会报错——所有判断会静默归进「未命名项目」一个组，
        追踪卡等于退化成一个总数，所以这里必须钉住。"""
        from app.models import Review
        from app.services import ledger_service

        review = Review(
            user_id="u-ledger-ctx",
            task_type="concept_review",
            artifact_bundle={"title": "t"},
            target_title="定价页 v2",
            project_key="官网改版",
            status="completed",
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        ledger_service.record_judgments(db, review, self._report())

        rows = ledger_service.list_judgments(db, "u-ledger-ctx", only_unverified=True)["judgments"]
        assert rows, "record_judgments 落了库，列表不该为空"
        assert all(r["project_key"] == "官网改版" for r in rows)
        assert all(r["review_title"] == "定价页 v2" for r in rows)

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

        judgments = ledger_service.list_judgments(db, "u-ledger")["judgments"]
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
        jid = ledger_service.list_judgments(db, "u-bad")["judgments"][0]["id"]
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
        jid = ledger_service.list_judgments(db, "owner")["judgments"][0]["id"]
        with pytest.raises(NotFound):
            ledger_service.verify_judgment(db, jid, "hit", "attacker")

    def test_ledger_endpoints(self, client):
        assert client.get("/api/ledger/judgments").status_code == 200
        assert client.get("/api/ledger/hit-rate").status_code == 200
        assert client.get("/api/ledger/calibration").status_code == 200
        assert client.get("/api/ledger/leaderboard").status_code == 200

    def test_confidence_calibration_uses_verified_outcomes(self, db):
        from app.models import Judgment, Outcome, Review
        from app.services import ledger_service

        review = Review(
            user_id="u-calibration",
            task_type="concept_review",
            artifact_bundle={},
            status="completed",
        )
        db.add(review)
        db.flush()
        samples = [(0.9, "hit"), (0.8, "miss"), (0.5, "partial"), (None, "hit")]
        for confidence, verdict in samples:
            judgment = Judgment(
                review_id=review.id,
                user_id="u-calibration",
                claim=f"claim-{confidence}-{verdict}",
                confidence=confidence,
            )
            db.add(judgment)
            db.flush()
            db.add(Outcome(judgment_id=judgment.id, verdict=verdict))
        db.commit()

        result = ledger_service.confidence_calibration(db, "u-calibration")
        assert result["verified_rows"] == 4
        assert result["sample_size"] == 3
        assert result["excluded_rows"] == 1
        assert result["mean_predicted_confidence"] == pytest.approx(0.733, abs=0.001)
        assert result["observed_hit_score"] == 0.5
        assert result["brier_score"] == pytest.approx(0.2167, abs=0.0001)
        assert result["expected_calibration_error"] is not None
        assert result["low_confidence"] is True
        assert "不具统计意义" in result["note"]


# ============================== 错误契约 ==============================

class TestErrorContract:
    def test_404_shape(self, client):
        r = client.get("/api/v2/reviews/does-not-exist")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"

    def test_request_id_header(self, client):
        r = client.get("/api/health")
        assert r.headers.get("X-Request-Id")
