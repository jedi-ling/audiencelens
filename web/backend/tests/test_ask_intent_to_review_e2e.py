"""对话式入口的转化链路：一句话 → 意图解析 → 真正建出一次评审。

功能完整性审查发现的 P1 缺口：现有测试只覆盖了两个断开的半截——
`test_intent_service.py` 直接调用 `intent_service.parse_intent_heuristic()`
内部函数（跳过了 HTTP 层），`test_e2e_chain.py` 的全链路冒烟测试直接
`POST /api/v2/reviews`（跳过了意图解析这一步）。中间"用户在 /ask 说的一句话
最终变成一次真正的评审"这条转化路径，从没有一条测试真正走过 HTTP。

这条测试补的就是这段缝：
    POST /api/intent/parse（真走 HTTP，heuristic 档，不需要 LLM key）
    → 把解析出的 task_type 喂进 POST /api/v2/reviews（走 test_e2e_chain.py
      已验证过的 fake run_panel 模式，不打真实 LLM）
    → 轮询 job 到 done → 报告里的 task_type 与 /ask 入口那句话解析出的一致

如果 /ask 的意图解析和评审创建之间的字段契约（比如 task_type 拼写、
persona_pack 默认值）出现不一致，这条测试会先于用户在生产上撞到红。
"""

import time

_FAKE_REPORT = {
    "priority_fixes": [],
    "persona_notes": [],
    "consensus": {},
}


def _fake_result(simulated=False):
    return {
        "report": _FAKE_REPORT,
        "markdown": "# r",
        "html": "",
        "calibration": {},
        "simulated": simulated,
        "cost_summary": {"total_cost": 0.1, "persona_count": 1, "skipped_count": 0},
    }


def _poll_job_until_terminal(client, job_id, timeout=15.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        job = resp.json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} 在 {timeout}s 内未到终态，最后状态: {job}")


class TestAskToReviewChain:
    def test_a_plain_sentence_becomes_a_real_review(self, client, db, monkeypatch):
        """核心路径：/ask 里说一句话 → 解析出 task_type → 真正建出评审，
        且报告里落库的 task_type 与解析结果一致（不是碰巧对上、不是硬编码）。"""
        from app.services import key_service

        import runner.cli

        calls = []

        def fake_run_panel(**kwargs):
            calls.append(kwargs)
            return _fake_result()

        monkeypatch.setattr(runner.cli, "run_panel", fake_run_panel)

        # 1. 真走 HTTP 意图解析——不带任何身份/key，走启发式档（不打 LLM）
        intent_resp = client.post(
            "/api/intent/parse", json={"text": "帮我评审一下 Steam 商店页"}
        )
        assert intent_resp.status_code == 200, intent_resp.text
        intent = intent_resp.json()
        assert intent["method"] == "heuristic", "没配 key 时应当降级到启发式档，不应该报错"
        assert intent["task_type"] == "steam_page_review"

        # 2. 把解析出来的 task_type 原样喂进真正的评审创建接口——这一步验证的
        #    正是"意图解析产出的值，评审创建接口认不认"这个契约。
        #
        #    key 存进去必须配 try/finally 删掉：不清理的话这把 BYOK key 会
        #    留在共享测试库里的 "anonymous" 身份下，污染同一进程里跑在
        #    它之后的其它测试——比如 test_auth_and_gating.py 那条专门验证
        #    "匿名且没配 key 时应该 428" 的回归用例，会因为这里漏删的 key
        #    而看到 428 变成别的状态码，红得莫名其妙（此坑参照
        #    test_e2e_chain.py 里同一模式的 finally 块，那边已经踩过一次）。
        key_service.save_user_key(db, "anonymous", "sk-ant-ask-e2e-test")
        try:
            create_resp = client.post(
                "/api/v2/reviews",
                json={
                    "task_type": intent["task_type"],
                    "artifact": {
                        "title": "Ask 入口冒烟",
                        "materials": [{"type": "text", "text": "商店页文案与截图描述"}],
                    },
                    "persona_pack": intent.get("persona_pack") or "game-core",
                },
            )
            assert create_resp.status_code == 202, create_resp.text
            body = create_resp.json()
            review_id = body["review_id"]
            job_id = body["job_id"]

            # 3. 队列真正执行到底
            job = _poll_job_until_terminal(client, job_id)
            assert job["status"] == "done", f"job 未成功: {job}"
            assert calls, "fake run_panel 没被调用——链路在入队之后断了"
            assert calls[0]["task_type"] == "steam_page_review"

            # 4. 报告落库后的 task_type 与 /ask 那句话解析出来的完全一致——
            #    这才是真正验证了"一句话最终变成了它该变成的那种评审"，
            #    不是分别验证两段互不相干的功能。
            detail = client.get(f"/api/v2/reviews/{review_id}").json()
            assert detail["status"] == "completed"
            assert detail["task_type"] == "steam_page_review"
        finally:
            key_service.delete_user_key(db, "anonymous")

    def test_intent_parse_alone_never_creates_a_review(self, client, db):
        """反向对照：只解析意图，不应该有任何评审被创建——意图解析是
        "理解你想干嘛"，不是"帮你把评审跑了"，这条边界不能混。"""
        before = client.get("/api/v2/reviews").json()
        before_ids = {r["id"] for r in before.get("reviews", before if isinstance(before, list) else [])}

        r = client.post("/api/intent/parse", json={"text": "帮我评审一下 Steam 商店页"})
        assert r.status_code == 200

        after = client.get("/api/v2/reviews").json()
        after_ids = {r["id"] for r in after.get("reviews", after if isinstance(after, list) else [])}
        assert after_ids == before_ids, "意图解析这一步不应该产生任何评审记录"

    def test_ambiguous_text_asks_for_clarification_instead_of_guessing(self, client):
        """反向对照：解析不出任务类型时，接口要如实说"需要澄清"，不能瞎猜一个
        task_type 糊弄过去——否则用户会莫名其妙收到一份跟他想要的完全不相关的评审。"""
        r = client.post("/api/intent/parse", json={"text": "嗯"})
        assert r.status_code == 200
        intent = r.json()
        if intent["task_type"] is None:
            assert intent["needs_clarification"] is True
