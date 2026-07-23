"""Token 计数系统回归：引擎返回的真实 token 一路存到 Review/UsageRecord，
后台聚合能读到。此前 token 在 chat_completion 返回后只用来算钱就被丢掉，
Review/UsageRecord 都没有 token 列，后台只能看美元成本看不了 token 量。"""

import time

import pytest


@pytest.fixture(autouse=True)
def _cleanup_anonymous_key(db):
    yield
    from app.services import key_service

    key_service.delete_user_key(db, "anonymous")


def _fake_result_with_tokens():
    return {
        "report": {"priority_fixes": [], "persona_notes": [], "consensus": {}},
        "markdown": "# r",
        "html": "",
        "calibration": {},
        "simulated": False,
        "cost_summary": {
            "total_cost": 0.12,
            "persona_count": 3,
            "skipped_count": 0,
            "total_input_tokens": 4200,
            "total_output_tokens": 1800,
        },
    }


def _poll_job_until_terminal(client, job_id, timeout=15.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        job = client.get("/api/jobs/{0}".format(job_id)).json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.1)
    raise AssertionError("job 未到终态: {0}".format(job))


class TestTokensFlowIntoReview:
    def test_v2_review_persists_token_counts(self, client, db, monkeypatch):
        """cost_summary 里的 token 汇总要存进 Review，并在 v2 详情接口暴露。"""
        from app.services import key_service

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result_with_tokens())
        key_service.save_user_key(db, "anonymous", "sk-ant-tok-test")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "t", "materials": [{"type": "text", "text": "x"}]},
            },
        )
        assert r.status_code == 202
        review_id = r.json()["review_id"]
        _poll_job_until_terminal(client, r.json()["job_id"])

        detail = client.get(f"/api/v2/reviews/{review_id}").json()
        assert detail["input_tokens"] == 4200
        assert detail["output_tokens"] == 1800

    def test_usage_record_stores_tokens(self, client, db, monkeypatch):
        """token 要落进 UsageRecord（后台聚合的事实源）。"""
        from app.models import UsageRecord
        from app.services import key_service

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result_with_tokens())
        key_service.save_user_key(db, "anonymous", "sk-ant-tok-test2")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "u", "materials": [{"type": "text", "text": "x"}]},
            },
        )
        review_id = r.json()["review_id"]
        _poll_job_until_terminal(client, r.json()["job_id"])

        rec = (
            db.query(UsageRecord)
            .filter(UsageRecord.review_id == review_id)
            .one()
        )
        assert rec.input_tokens == 4200
        assert rec.output_tokens == 1800


class TestAdminAggregatesTokens:
    def test_overview_and_reviews_expose_tokens(self, client, db, monkeypatch):
        """后台 stats 概览的 24h token 总量 + 评审明细的 per-review token。"""
        import os

        from app.services import key_service

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result_with_tokens())
        key_service.save_user_key(db, "anonymous", "sk-ant-tok-test3")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "a", "materials": [{"type": "text", "text": "x"}]},
            },
        )
        review_id = r.json()["review_id"]
        _poll_job_until_terminal(client, r.json()["job_id"])

        admin_token = os.environ.get("AL_ADMIN_TOKEN")
        headers = {"X-Admin-Token": admin_token} if admin_token else {}

        stats_resp = client.get("/api/admin/stats", headers=headers)
        if stats_resp.status_code != 200:
            pytest.skip("后台未开放（未配置/不匹配 AL_ADMIN_TOKEN），跳过后台聚合断言")

        stats = stats_resp.json()
        assert stats["usage_24h"]["tokens_total"] >= 6000

        listing = client.get("/api/admin/reviews", headers=headers).json()
        row = next(x for x in listing["reviews"] if x["id"] == review_id)
        assert row["tokens_total"] == 6000
        assert row["input_tokens"] == 4200
