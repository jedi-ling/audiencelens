"""v1 评审引擎（ReviewService.run_review，Wizard/直接调 /api/reviews 的旧链路）加固回归。

此前的三个真问题（来自 2026-07-23 功能链路审计，均已逐一核实）：
  1. 直接读 os.environ 的 ANTHROPIC_API_KEY——用户在设置页存的 BYOK key 完全无效；
  2. 没有环境变量时静默把 _build_simulated_output 的占位数据当真实报告入库；
  3. WS 广播用 {type: ...} 老信封，前端 ws.ts 按 payload.event 判终态，永远判不到。

现在：key 走 key_service.resolve_key（与 v2 同源），无 key 直接 failed 绝不模拟，
WS 信封统一为 {event, data}。
"""

import sys
import time
from unittest.mock import patch

sys.path.insert(0, "src")


def _post_v1_review(client, selected_personas=None):
    """不断言状态码——给"无 key 应当 428"那条用例留出检查空间。

    selected_personas：默认预设在测试环境下只会跑 1 位人格，测"部分失败"
    必须显式点名多位，否则永远凑不出"一部分成功一部分失败"。
    """
    body = {
        "task_type": "concept_review",
        "artifact_bundle": {
            "title": "v1 加固验证",
            "materials": [{"type": "核心循环说明", "description": "探索-战斗-成长"}],
        },
    }
    if selected_personas:
        body["selected_personas"] = selected_personas
    return client.post("/api/reviews", json=body)


def _create_v1_review(client, selected_personas=None):
    r = _post_v1_review(client, selected_personas)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _wait_terminal(client, review_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = client.get(f"/api/reviews/{review_id}").json()
        if detail["status"] in ("completed", "failed"):
            return detail
        time.sleep(0.1)
    raise AssertionError(f"review {review_id} 未到终态")


class TestV1RefusesSimulatedData:
    def test_no_key_is_rejected_at_the_door(self, client, db, monkeypatch):
        """无 key 时直接 428，连评审行都不该建。

        契约变更说明：这条以前断言的是"建了评审再标 failed"。现在 v1 和 v2 一样
        挂了 resolve_llm_key 依赖，请求在入口就被 428 挡掉——比先建一条注定失败的
        评审再收尸更好（不留垃圾行、错误立刻可见、两条链路行为一致）。
        原本要守的底线"绝不把模拟数据当报告入库"守得更死了：什么都没建。
        """
        from app.models import Review

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        before = db.query(Review).count()

        r = _post_v1_review(client)
        assert r.status_code == 428, r.text

        assert db.query(Review).count() == before, "无 key 不该留下评审行"

    def test_key_present_but_llm_fails_marks_failed_never_simulated(
        self, client, db, monkeypatch
    ):
        """请求时有 key、但跑起来 LLM 挂了 —— 引擎那层安全网仍须生效。

        入口的 428 只能挡住"压根没配 key"；key 存在但失效/欠费/被封是另一类，
        只有引擎里那道网能兜。这条就是替原用例守住"绝不入库模拟数据"这个底线。
        """
        from app.services import key_service

        key_service.save_user_key(db, "anonymous", "sk-will-fail")

        import runner.llm_client

        def boom(**kwargs):
            raise RuntimeError("401 invalid api key")

        monkeypatch.setattr(runner.llm_client, "chat_completion", boom)

        review_id = _create_v1_review(client)
        detail = _wait_terminal(client, review_id)

        assert detail["status"] == "failed"
        # 报告字段必须为空——不能有任何模拟内容混进来
        assert not detail.get("report_json") or "error" in (detail.get("report_json") or {})

    def test_all_personas_failing_never_reports_low_risk(self, client, db, monkeypatch):
        """全员失败绝不能产出一份"无风险"报告。

        这是本仓库最危险的一类缺陷：不崩、不报错，反而伪造一份干净结论。
        以前的行为是 persona_outputs_data 为空 → aggregate_report([]) 给出
        release_risk="low" + 0 条修复项 → 状态还被无条件置成 completed，
        用户看到"评审团都看过了，没发现问题"，实际一个都没跑成。
        """
        from app.services import key_service

        key_service.save_user_key(db, "anonymous", "sk-all-fail")

        import runner.llm_client

        monkeypatch.setattr(
            runner.llm_client,
            "chat_completion",
            lambda **kw: (_ for _ in ()).throw(RuntimeError("401 invalid api key")),
        )

        review_id = _create_v1_review(client)
        detail = _wait_terminal(client, review_id)

        assert detail["status"] == "failed", "全员失败必须是 failed，不能是 completed"

        report = detail.get("report_json") or {}
        # 绝不能出现"低风险/无问题"这种被伪造出来的结论
        summary = report.get("executive_summary") or {}
        assert summary.get("release_risk") != "low"
        assert not report.get("priority_fixes")
        # 失败原因必须能看到（匿名也一样——裁剪不能把坏消息裁掉）
        assert report.get("error"), "失败评审必须留下可读的失败原因"

    def test_partial_failure_marks_report_degraded(self, client, db, monkeypatch):
        """部分失败可以出报告，但必须如实标注结论只据几位人格得出。

        为什么要绕开证据预检：真实链路是
        select_panel_by_mode → precheck_panel → valid_personas，
        而测试用的极简材料会让绝大多数人格因"缺所需证据"被预检跳过，
        默认只剩 1 位——凑不出"一部分成功一部分失败"。
        这里放行全部人格，把测试隔离到它真正要验的东西（降级标记）上，
        而不是顺带测预检的选人行为（那有它自己的测试）。
        """
        import app.services as services_mod
        from app.services import key_service

        key_service.save_user_key(db, "anonymous", "sk-partial")

        real_precheck = services_mod.precheck_panel

        def pass_all(selected, artifact_bundle):
            result = real_precheck(selected, artifact_bundle)
            return {**result, "valid_personas": list(selected)}

        monkeypatch.setattr(services_mod, "precheck_panel", pass_all)

        import runner.llm_client

        calls = {"n": 0}
        good = (
            '{"persona_id":"P01","primary_stance":"观望","key_issues":[],'
            '"evidence":[],"missing_information":[],"voice_sample":"还行"}'
        )

        def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] % 2 == 0:  # 一半成功一半失败
                raise RuntimeError("503 upstream busy")
            return (good, 10, 5)

        monkeypatch.setattr(runner.llm_client, "chat_completion", flaky)

        review_id = _create_v1_review(client)
        detail = _wait_terminal(client, review_id)

        assert detail["status"] == "completed"
        # 字段名和引擎链路 runner/cli.py 的 report["degradation"] 一致——
        # 两条链路同一口径，前端只写一套读法
        deg = (detail.get("report_json") or {}).get("degradation")
        assert deg, "部分失败必须带降级标记，否则等于把少数人的看法当评审团结论"
        assert deg["degraded"] is True
        assert deg["succeeded_count"] >= 1
        assert deg["attempted_count"] > deg["succeeded_count"]
        assert deg["failed_count"] == len(deg["failed_personas"])


class TestAnonymousGatingKeepsProgressVisible:
    """匿名裁剪不能把"评审到底在不在跑"这个基本事实也裁掉。

    回归背景：给 v1 补匿名裁剪时我一度把 persona_outputs 整个清空，
    结果匿名用户在进度页全程看到"0 位角色"、跑完还是 0 ——正是这个仓库
    反复出现过的那个症状。付费墙该挡内容，不该挡事实。
    """

    def test_anonymous_sees_personas_but_not_their_content(self, client, db, monkeypatch):
        from app.services import key_service

        key_service.save_user_key(db, "anonymous", "sk-gate-progress")

        import runner.llm_client

        # voice_sample 是"这位角色的原话"——属于该被裁掉的角色视角内容。
        # 注意不要把待验证的秘密放进 key_issues：体验版**有意**保留第一条
        # 优先修复项当诱饵（见 gate_report_for_anonymous），放那儿本来就该露出来。
        good = (
            '{"persona_id":"P01","primary_stance":"观望","key_issues":'
            '[{"title":"引导偏长","severity":"medium","why_it_matters":"可能流失"}],'
            '"evidence":[],"missing_information":[],'
            '"voice_sample":"这句角色原话只有登录用户能看"}'
        )
        monkeypatch.setattr(
            runner.llm_client, "chat_completion", lambda **kw: (good, 10, 5)
        )

        review_id = _create_v1_review(client)
        detail = _wait_terminal(client, review_id)
        assert detail["status"] == "completed"

        outputs = detail.get("persona_outputs") or []
        assert outputs, "匿名也必须能看到角色列表，否则进度页显示 0 位角色"
        # 存在与状态可见——进度页要靠这些画"N 位角色，M 位已完成"
        assert all(po.get("persona_id") for po in outputs)
        assert all(po.get("status") for po in outputs)
        # 但每位角色的输出内容必须被裁掉
        assert all(po.get("output_json") is None for po in outputs)
        assert all(po.get("validation_result") is None for po in outputs)
        assert "这句角色原话只有登录用户能看" not in str(detail)

    def test_no_v1_endpoint_leaks_full_report_to_anonymous(self, client, db, monkeypatch):
        """三条 v1 读路径必须**同时**裁剪，漏一条登录墙就等于没有。

        这是修复前的真实状态：裁剪只接在 /reviews/{id}/report 上，而且连它
        都从 report_markdown 把全文漏了出去。匿名用户看到"登录看完整"，
        换个端点请求一下全文到手。这条测试把三个出口一起钉住。
        """
        import app.services as services_mod
        from app.services import key_service

        key_service.save_user_key(db, "anonymous", "sk-leak-check")

        real_precheck = services_mod.precheck_panel
        monkeypatch.setattr(
            services_mod,
            "precheck_panel",
            lambda sel, ab: {**real_precheck(sel, ab), "valid_personas": list(sel)},
        )

        import runner.llm_client

        # 秘密只放在"体验版一定会裁掉"的位置：角色原话，以及排在诱饵之后的低优先级项。
        # 不能放在最高严重度那条——体验版**有意**保留第一条优先修复项当诱饵
        # （见 gate_report_for_anonymous 的 priority_fixes[:1]），放那儿本来就该露出来，
        # 拿它当泄露证据是在测一个设计上不存在的要求。
        SECRET = "仅登录可见的角色原话与深度分析"
        good = (
            '{"persona_id":"P01","primary_stance":"观望","key_issues":'
            '[{"title":"引导偏长","severity":"critical","why_it_matters":"可能流失"},'
            '{"title":"' + SECRET + '","severity":"low","why_it_matters":"' + SECRET + '"}],'
            '"evidence":[],"missing_information":[],"voice_sample":"' + SECRET + '"}'
        )
        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: (good, 10, 5))

        review_id = _create_v1_review(client)
        assert _wait_terminal(client, review_id)["status"] == "completed"

        for path in (
            f"/api/reviews/{review_id}",
            f"/api/reviews/{review_id}/report",
            f"/api/reviews/{review_id}/result",
        ):
            r = client.get(path)
            assert r.status_code == 200, path
            assert SECRET not in r.text, f"{path} 把完整报告漏给了匿名用户"


class TestV1UsesByokKey:
    def test_llm_call_receives_resolved_byok_key(self, client, db, monkeypatch):
        """v1 引擎的 LLM 调用必须拿到 key_service 解析出的 BYOK key/provider/api_base，
        而不是环境变量。"""
        from app.services import key_service

        key_service.save_user_key(
            db, "anonymous", "sk-byok-v1-test",
            provider="anthropic", api_base="https://relay.example.com/anthropic",
        )
        calls = []

        def fake_chat(**kwargs):
            calls.append(kwargs)
            raise RuntimeError("short-circuit")  # 拿到调用参数即达成目的，无需真跑

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", fake_chat)
        # run_review 内部是 from runner.llm_client import chat_completion（函数级导入），
        # 补丁打在模块属性上即可生效

        review_id = _create_v1_review(client)
        _wait_terminal(client, review_id)

        assert calls, "chat_completion 未被调用——v1 引擎没走统一 LLM 出口"
        assert calls[0]["api_key"] == "sk-byok-v1-test"
        assert calls[0]["provider"] == "anthropic"
        assert calls[0]["api_base"] == "https://relay.example.com/anthropic"


class TestMaterialExtractorByok:
    def test_no_resolved_key_skips_ai_never_touches_env(self, monkeypatch):
        """没解析到 key 时 AI 档直接跳过（走 fallback），即使环境变量里有 key 也不偷用。"""
        from app.services import MaterialExtractor

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-should-not-be-used")
        result = MaterialExtractor._extract_with_ai("concept_review", "some text", ["一句话pitch"])
        assert result is None

    def test_resolved_key_flows_into_chat_completion(self, monkeypatch):
        from app.services import MaterialExtractor
        from app.services.key_service import ResolvedKey

        calls = []

        def fake_chat(**kwargs):
            calls.append(kwargs)
            return ('{"title": "T", "materials": {"一句话pitch": "x"}}', 10, 5)

        with patch("runner.llm_client.chat_completion", side_effect=fake_chat):
            resolved = ResolvedKey(
                key="sk-extract-test", source="byok", provider="openai_compatible",
                model="deepseek-v4-pro", api_base="https://api.deepseek.com",
            )
            result = MaterialExtractor._extract_with_ai(
                "concept_review", "文档内容", ["一句话pitch"], resolved=resolved
            )

        assert result == {"title": "T", "materials": {"一句话pitch": "x"}}
        assert calls[0]["api_key"] == "sk-extract-test"
        assert calls[0]["provider"] == "openai_compatible"
        assert calls[0]["model"] == "deepseek-v4-pro"


class TestNonGameTaskTypesActuallyWork:
    """pitch_review / product_feedback_review / pricing_page_review 三个非游戏任务类型
    此前 100% 失败——用户提交一份创业 BP，拿到的是
    `local variable 'random' referenced before assignment`。

    根因：PersonaService.select_panel_by_mode 里 `import random` 写在 except 块内，
    而下方"人数不足补人"分支也用 random.sample。Python 的函数级名字绑定让 random
    在整个函数里都是局部名，正常路径上它从未被赋值。
    触发条件正是"预设人选不在当前包里 → 选出人数少于下限 → 需要补人"，
    而这三个任务类型的预设人选恰好都不在默认 game-core 包中。

    这三个正是 BP 里当作产品扩张主打的"3 种产品向 + 1 种创业项目评审"。
    """

    def test_panel_selection_does_not_crash(self):
        from app.services import PersonaService

        for task_type in ("pitch_review", "product_feedback_review", "pricing_page_review"):
            panel = PersonaService.select_panel_by_mode(
                task_type=task_type, mode="standard",
                persona_pack="game-core", selected_personas=None,
            )
            assert panel, f"{task_type} 选不出任何人格"

    def test_pitch_review_runs_end_to_end(self, client, db, monkeypatch):
        """跑通到底。绕开证据预检的理由同 test_partial_failure_marks_report_degraded：
        测试用的极简材料会让人格因"缺所需证据"被全部跳过，那测的是预检不是本 bug。"""
        import app.services as services_mod
        from app.services import key_service

        key_service.save_user_key(db, "anonymous", "sk-pitch-regression")

        real_precheck = services_mod.precheck_panel
        monkeypatch.setattr(
            services_mod,
            "precheck_panel",
            lambda sel, ab: {**real_precheck(sel, ab), "valid_personas": list(sel)},
        )

        import runner.llm_client

        good = (
            '{"persona_id":"P01","primary_stance":"观望","key_issues":'
            '[{"title":"缺少单位经济","severity":"high","why_it_matters":"投资人会问"}],'
            '"evidence":[],"missing_information":[],"voice_sample":"再想想"}'
        )
        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: (good, 10, 5))

        r = client.post(
            "/api/reviews",
            json={
                "task_type": "pitch_review",
                "artifact_bundle": {
                    "title": "我的创业 BP",
                    "materials": [{"type": "一句话pitch", "description": "AI 评审工具"}],
                },
            },
        )
        assert r.status_code == 200, r.text
        detail = _wait_terminal(client, r.json()["id"])
        assert detail["status"] == "completed", detail.get("report_json")
