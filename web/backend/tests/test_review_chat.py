"""报告出来后真对话的回归：追问评审团 / 跟具体人格聊，两条 thread 各自持久化上下文。

此前"多轮"只是拼接文本给无状态的意图解析用，报告产出后没有任何追问入口——
这里测的是新增的 /api/v2/reviews/{id}/chat，验证：上下文真的带进了后续请求
（不是每次从零开始），以及跟人格聊时人设真的进了 prompt。"""

import time

import pytest


@pytest.fixture(autouse=True)
def _cleanup_anonymous_key(db):
    """整个测试会话共用一个 sqlite 文件、不按测试回滚（见 conftest.py），
    save_user_key(db, "anonymous", ...) 是 upsert，不清理就会让后面断言
    "anonymous 没有 key" 的测试（如 test_v1_engine_hardening）跟着失败。"""
    yield
    from app.services import key_service

    key_service.delete_user_key(db, "anonymous")


def _fake_result():
    return {
        "report": {
            "executive_summary": {
                "primary_recommendation": "谨慎推进",
                "release_risk": "中",
                "evidence_quality": "中",
            },
            "priority_fixes": [{"title": "定价不清晰", "severity": "high", "why_it_matters": "转化率低"}],
            "persona_notes": [
                {"persona_id": "P01-indie-core-operator", "persona_name": "林岚", "primary_stance": "观望"}
            ],
        },
        "markdown": "# r",
        "html": "",
        "calibration": {},
        "simulated": False,
        "cost_summary": {"total_cost": 0.1, "persona_count": 1, "skipped_count": 0},
    }


def _poll_job_until_terminal(client, job_id, timeout=15.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        resp = client.get("/api/jobs/{0}".format(job_id))
        job = resp.json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.1)
    raise AssertionError("job 未到终态: {0}".format(job))


def _make_completed_review(client, db, monkeypatch, key="sk-ant-chat-test"):
    from app.services import key_service

    import runner.cli

    monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
    key_service.save_user_key(db, "anonymous", key)

    r = client.post(
        "/api/v2/reviews",
        json={
            "task_type": "concept_review",
            "artifact": {"title": "t", "materials": [{"type": "text", "text": "x"}]},
            "persona_pack": "game-core",
        },
    )
    assert r.status_code == 202
    review_id = r.json()["review_id"]
    _poll_job_until_terminal(client, r.json()["job_id"])
    return review_id


class TestGeneralFollowUp:
    def test_followup_uses_report_context_and_persists_history(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch)

        captured_prompts = []

        def fake_chat_completion(**kw):
            captured_prompts.append(kw["prompt"])
            return ("这是回复", 10, 5)

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", fake_chat_completion)

        r1 = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "为什么定价扣分？"})
        assert r1.status_code == 200
        assert r1.json()["reply"]["role"] == "assistant"
        assert r1.json()["reply"]["content"] == "这是回复"
        assert "定价不清晰" in captured_prompts[0]  # 报告内容真的进了 prompt

        r2 = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "那怎么改？"})
        assert r2.status_code == 200
        # 第二轮的 prompt 里带着第一轮的问答——不是每次从零开始
        assert "为什么定价扣分" in captured_prompts[1]
        assert "这是回复" in captured_prompts[1]

        listed = client.get(f"/api/v2/reviews/{review_id}/chat").json()["messages"]
        assert len(listed) == 4  # 2轮 * (user+assistant)

    def test_review_not_completed_rejects_chat(self, client, db, monkeypatch):
        from app.services import key_service

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
        key_service.save_user_key(db, "anonymous", "sk-ant-pending-test")

        from app.models import Review

        review = Review(
            user_id="anonymous", task_type="concept_review", status="pending", artifact_bundle={}
        )
        db.add(review)
        db.commit()

        r = client.post(f"/api/v2/reviews/{review.id}/chat", json={"message": "还没跑完就问"})
        assert r.status_code == 400


class TestPersonaChat:
    def test_persona_chat_grounds_with_persona_profile(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-persona-chat")

        captured_prompts = []

        def fake_chat_completion(**kw):
            captured_prompts.append(kw["prompt"])
            return ("我觉得还行", 10, 5)

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", fake_chat_completion)

        r = client.post(
            f"/api/v2/reviews/{review_id}/chat",
            json={"message": "你为啥观望？", "persona_id": "P01-indie-core-operator"},
        )
        assert r.status_code == 200
        prompt = captured_prompts[0]
        assert "林岚" in prompt or "P01-indie-core-operator" in prompt
        assert "观望" in prompt  # 该人格当时的评审意见真的带进去了

        # 单独的 thread：跟评审团整体聊的历史查不到这条
        general = client.get(f"/api/v2/reviews/{review_id}/chat").json()["messages"]
        assert general == []
        persona_thread = client.get(
            f"/api/v2/reviews/{review_id}/chat?persona_id=P01-indie-core-operator"
        ).json()["messages"]
        assert len(persona_thread) == 2

    def test_unknown_persona_id_rejected(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-unknown-persona")
        r = client.post(
            f"/api/v2/reviews/{review_id}/chat",
            json={"message": "hi", "persona_id": "P99-not-real"},
        )
        assert r.status_code == 400
