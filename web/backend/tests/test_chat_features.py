"""对话页三项新能力的落库/生效验证：插入技能、呼叫角色、长期评审项目。

三者都通过 /api/v2/reviews（AskPage 实际调用的创建接口）验证，而不是只测
schema 能不能收字段——插入技能要真的改 prompt 材料，呼叫角色要真的传到
run_panel，这两个此前都不生效（技能是纯展示，selected_personas 在 v2 链路
完全没被读取），本文件专门盯这两个"字段存在但没用"的回归。"""

import time

_FAKE_REPORT = {"priority_fixes": [], "persona_notes": [], "consensus": {}}


def _fake_result():
    return {
        "report": _FAKE_REPORT,
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


class TestSkillHintInjection:
    def test_red_team_audience_injects_hint_material(self, client, db, monkeypatch):
        from app.services import key_service

        import runner.cli

        calls = []

        def fake_run_panel(**kwargs):
            calls.append(kwargs)
            return _fake_result()

        monkeypatch.setattr(runner.cli, "run_panel", fake_run_panel)
        key_service.save_user_key(db, "anonymous", "sk-ant-test")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "定价页", "materials": [{"type": "text", "text": "核心玩法"}]},
                "skill_type": "red_team_audience",
            },
        )
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        _poll_job_until_terminal(client, job_id)

        assert calls, "run_panel 没被调用"
        materials = calls[0]["artifact_bundle"]["materials"]
        assert materials[0]["type"] == "text"
        assert "红队" in materials[0]["text"]
        # 原始材料还在，技能提示只是插进去，不是替换
        assert any(m.get("text") == "核心玩法" for m in materials)

    def test_no_skill_type_leaves_materials_untouched(self, client, db, monkeypatch):
        from app.services import key_service

        import runner.cli

        calls = []
        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: (calls.append(kw), _fake_result())[1])
        key_service.save_user_key(db, "anonymous", "sk-ant-test2")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "定价页2", "materials": [{"type": "text", "text": "核心玩法2"}]},
            },
        )
        assert r.status_code == 202
        _poll_job_until_terminal(client, r.json()["job_id"])
        materials = calls[0]["artifact_bundle"]["materials"]
        assert materials == [{"type": "text", "text": "核心玩法2"}]


class TestSelectedPersonasReachEngine:
    def test_selected_personas_passed_through_to_run_panel(self, client, db, monkeypatch):
        """曾经的真 bug：v2 链路的 selected_personas 字段以前压根没被 create_review_v2
        接收，也没有传给 run_panel——呼叫角色这个功能落库了但对实际执行零效果。"""
        from app.services import key_service

        import runner.cli

        calls = []
        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: (calls.append(kw), _fake_result())[1])
        key_service.save_user_key(db, "anonymous", "sk-ant-test3")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "t", "materials": [{"type": "text", "text": "x"}]},
                "persona_pack": "game-core",
                "selected_personas": ["P01-indie-core-operator", "P02-systems-theorycrafter"],
            },
        )
        assert r.status_code == 202
        _poll_job_until_terminal(client, r.json()["job_id"])
        assert calls[0]["selected_personas"] == ["P01-indie-core-operator", "P02-systems-theorycrafter"]


class TestProjectKeyGrouping:
    def test_project_key_stored_and_returned(self, client, db, monkeypatch):
        from app.services import key_service

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
        key_service.save_user_key(db, "anonymous", "sk-ant-test4")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "t2", "materials": [{"type": "text", "text": "y"}]},
                "project_key": "新手引导优化",
            },
        )
        assert r.status_code == 202
        review_id = r.json()["review_id"]

        listed = client.get("/api/reviews").json()
        row = next(x for x in listed if x["id"] == review_id)
        assert row["project_key"] == "新手引导优化"
