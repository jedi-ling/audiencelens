"""全链路 E2E 冒烟：发起评审 → 队列执行 → 报告落库 → 判断留档 → 用量记账。

用假 run_panel 替换真实 LLM 引擎，证明整条 Web 链路真的闭环：
    POST /api/v2/reviews (BYOK) → 202 入队
    → 后台 worker 执行（本测试注入 fake 引擎）
    → GET /api/jobs/{id} 轮询到 done
    → GET /api/v2/reviews/{id} 报告 + 成本落库
    → GET /api/ledger/judgments 预测留档
    → GET /api/usage 用量记账

以及负向安全网：simulated=True 的结果永远进不了正式库。
"""

import time

# 假引擎产出的报告：同时含 priority_fixes（合议结论）与 persona key_issues，
# 用于验证两条来源的判断都被留档。
_FAKE_REPORT = {
    "priority_fixes": [
        {
            "title": "新手引导太长会劝退",
            "severity": "high",
            "why_it_matters": "前 15 分钟流失窗口",
        }
    ],
    "persona_notes": [
        {
            "persona_id": "P01",
            "persona_name": "硬核玩家",
            "confidence": 0.8,
            "key_issues": [{"title": "难度曲线太陡", "severity": "medium"}],
        },
        {
            "persona_id": "P02",
            "persona_name": "休闲玩家",
            "confidence": 0.7,
            "key_issues": [{"title": "操作教学不直观", "severity": "low"}],
        },
    ],
    "consensus": {},
}


def _fake_result(simulated):
    return {
        "report": _FAKE_REPORT,
        "markdown": "# r",
        "html": "",
        "calibration": {},
        "simulated": simulated,
        "cost_summary": {"total_cost": 0.42, "persona_count": 3, "skipped_count": 0},
    }


def _create_review(client):
    r = client.post(
        "/api/v2/reviews",
        json={
            "task_type": "concept_review",
            "artifact": {
                "title": "E2E 冒烟概念",
                "materials": [{"type": "text", "text": "核心循环：探索-战斗-成长"}],
            },
        },
    )
    return r


def _poll_job_until_terminal(client, job_id, timeout=15.0):
    """每 0.1s 轮询一次 job，直到 done/failed/cancelled 或超时。"""
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        resp = client.get("/api/jobs/{0}".format(job_id))
        assert resp.status_code == 200
        job = resp.json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.1)
    raise AssertionError("job {0} 在 {1}s 内未到终态，最后状态: {2}".format(job_id, timeout, job))


class TestE2EChain:
    def test_full_chain_review_to_ledger_to_usage(self, client, db, monkeypatch):
        """正向链路：BYOK 发起 → 队列执行 → 报告/成本落库 → 判断留档 → 用量记账。"""
        # review_service 导入时已把仓库 src/ 挂进 sys.path
        from app.services import key_service, review_service  # noqa: F401

        import runner.cli

        calls = []

        def fake_run_panel(**kwargs):
            calls.append(kwargs)
            return _fake_result(simulated=False)

        # review_service 在执行时才 from runner.cli import run_panel，
        # 补丁打在模块属性上即可生效
        monkeypatch.setattr(runner.cli, "run_panel", fake_run_panel)

        key_service.save_user_key(db, "anonymous", "sk-ant-e2e-test")
        try:
            # 1. 发起评审：202 + BYOK 来源
            r = _create_review(client)
            assert r.status_code == 202
            body = r.json()
            assert body["key_source"] == "byok"
            review_id = body["review_id"]
            job_id = body["job_id"]

            # 2. 队列执行到 done
            job = _poll_job_until_terminal(client, job_id)
            assert job["status"] == "done", "job 未成功: {0}".format(job)
            assert calls, "fake run_panel 根本没被调用——链路没走到引擎"
            assert calls[0]["task_type"] == "concept_review"

            # 3. 报告 + 成本落库
            detail = client.get("/api/v2/reviews/{0}".format(review_id)).json()
            assert detail["status"] == "completed"
            assert detail["report"], "报告没落库"
            assert (
                detail["report"]["priority_fixes"][0]["title"] == "新手引导太长会劝退"
            )
            assert detail["total_cost_usd"] == 0.42
            assert detail["error_message"] is None

            # 4. 判断留档：priority_fixes 与各人格 key_issues 都进了台账
            lr = client.get("/api/ledger/judgments", params={"review_id": review_id})
            assert lr.status_code == 200
            judgments = lr.json()["judgments"]
            assert judgments, "判断台账为空——留档环节断了"
            claims = [j["claim"] for j in judgments]
            assert "新手引导太长会劝退" in claims  # 来自 priority_fixes
            assert "难度曲线太陡" in claims  # 来自 persona key_issues
            assert "操作教学不直观" in claims
            assert any(j["persona_id"] == "P01" for j in judgments)

            # 5. 用量记账：这 0.42 美元被如实记录
            usage = client.get("/api/usage").json()
            assert usage["cost_usd_total"] >= 0.42
        finally:
            key_service.delete_user_key(db, "anonymous")

    def test_simulated_result_never_reaches_final_records(self, client, db, monkeypatch):
        """负向安全网：引擎返回 simulated=True 时，任务必须 failed，假数据不入库。"""
        from app.services import key_service, review_service  # noqa: F401

        import runner.cli

        def fake_run_panel_simulated(**kwargs):
            return _fake_result(simulated=True)

        monkeypatch.setattr(runner.cli, "run_panel", fake_run_panel_simulated)

        key_service.save_user_key(db, "anonymous", "sk-ant-e2e-test")
        try:
            r = _create_review(client)
            assert r.status_code == 202
            review_id = r.json()["review_id"]
            job_id = r.json()["job_id"]

            # 任务以 failed 收场，错误信息如实说明是模拟数据被丢弃
            job = _poll_job_until_terminal(client, job_id)
            assert job["status"] == "failed"
            assert "模拟" in (job["error_message"] or "")

            # 评审状态 failed，报告字段为空——假数据没进正式结果
            detail = client.get("/api/v2/reviews/{0}".format(review_id)).json()
            assert detail["status"] == "failed"
            assert "模拟" in (detail["error_message"] or "")
            assert not detail["report"]

            # 判断台账也一条没留
            lr = client.get("/api/ledger/judgments", params={"review_id": review_id})
            assert lr.json()["judgments"] == []
        finally:
            key_service.delete_user_key(db, "anonymous")
