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


class TestModeReachesEngine:
    def test_mode_passed_through_to_run_panel(self, client, db, monkeypatch):
        """曾经的真 bug：v2 链路的 mode 只落库和展示，从没传给 run_panel——
        选"快速"实际跑的是全量流程，人数不减、交叉质证照跑、钱照花。"""
        from app.services import key_service

        import runner.cli

        calls = []
        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: (calls.append(kw), _fake_result())[1])
        key_service.save_user_key(db, "anonymous", "sk-ant-mode-test")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "m", "materials": [{"type": "text", "text": "x"}]},
                "mode": "quick",
            },
        )
        assert r.status_code == 202
        _poll_job_until_terminal(client, r.json()["job_id"])
        assert calls[0]["mode"] == "quick"


class TestV2DetailExposesChatFields:
    def test_detail_returns_skill_personas_project(self, client, db, monkeypatch):
        from app.services import key_service

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
        key_service.save_user_key(db, "anonymous", "sk-ant-detail-test")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "d", "materials": [{"type": "text", "text": "x"}]},
                "persona_pack": "game-core",
                "selected_personas": ["P01-indie-core-operator"],
                "skill_type": "red_team_audience",
                "project_key": "详情字段验证",
            },
        )
        assert r.status_code == 202
        review_id = r.json()["review_id"]

        detail = client.get("/api/v2/reviews/{0}".format(review_id)).json()
        assert detail["persona_pack"] == "game-core"
        assert detail["selected_personas"] == ["P01-indie-core-operator"]
        assert detail["skill_type"] == "red_team_audience"
        assert detail["project_key"] == "详情字段验证"


class TestEvaluationAutoRun:
    def test_enable_evaluation_triggers_full_evaluation_after_completion(self, client, db, monkeypatch):
        """Wizard"启用评估"开关的落点：此前该参数被 schema 静默丢弃从未生效。
        现在 v2 评审完成后自动调 EvaluationService.run_full_evaluation。"""
        from app.services import key_service
        from app.services.evaluation_service import EvaluationService

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
        eval_calls = []
        monkeypatch.setattr(
            EvaluationService, "run_full_evaluation",
            classmethod(lambda cls, session, rid: eval_calls.append(rid)),
        )
        key_service.save_user_key(db, "anonymous", "sk-ant-eval-test")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "e", "materials": [{"type": "text", "text": "x"}]},
                "enable_evaluation": True,
            },
        )
        assert r.status_code == 202
        review_id = r.json()["review_id"]
        _poll_job_until_terminal(client, r.json()["job_id"])
        assert eval_calls == [review_id], "enable_evaluation=True 却没有触发自动评估"

    def test_evaluation_not_run_when_disabled(self, client, db, monkeypatch):
        from app.services import key_service
        from app.services.evaluation_service import EvaluationService

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
        eval_calls = []
        monkeypatch.setattr(
            EvaluationService, "run_full_evaluation",
            classmethod(lambda cls, session, rid: eval_calls.append(rid)),
        )
        key_service.save_user_key(db, "anonymous", "sk-ant-eval-test2")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "e2", "materials": [{"type": "text", "text": "x"}]},
            },
        )
        assert r.status_code == 202
        _poll_job_until_terminal(client, r.json()["job_id"])
        assert eval_calls == []


class TestRedTeamStacking:
    def test_red_team_hint_stacks_on_top_of_other_skill(self, client, db, monkeypatch):
        """红队开关与技能选择独立：选了受众面板也能叠加对抗视角提示。"""
        from app.services import key_service

        import runner.cli

        calls = []
        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: (calls.append(kw), _fake_result())[1])
        key_service.save_user_key(db, "anonymous", "sk-ant-rt-test")

        r = client.post(
            "/api/v2/reviews",
            json={
                "task_type": "concept_review",
                "artifact": {"title": "rt", "materials": [{"type": "text", "text": "y"}]},
                "skill_type": "audience_panel",
                "enable_red_team": True,
            },
        )
        assert r.status_code == 202
        _poll_job_until_terminal(client, r.json()["job_id"])
        texts = [m.get("text", "") for m in calls[0]["artifact_bundle"]["materials"]]
        assert any("红队" in t for t in texts), "红队提示没叠加进材料"
        assert any("消费" in t for t in texts), "受众面板提示丢了"


class TestTaskTypeRegistry:
    def test_meta_and_engine_registry_aligned(self):
        """展示元数据与引擎单一注册表必须一致（此前多 4 个引擎不认的、
        少 4 个引擎支持的——模块导入时的 assert 是硬闸，这里是显式回归）。"""
        import sys

        sys.path.insert(0, "src")
        from runner.task_types import VALID_TASK_TYPES

        from app.services import TASK_TYPES
        from app.services.intent_service import VALID_TASK_TYPES as INTENT_TYPES

        assert set(TASK_TYPES) == set(VALID_TASK_TYPES)
        assert INTENT_TYPES is VALID_TASK_TYPES  # 同一个对象，不是又一份拷贝


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
