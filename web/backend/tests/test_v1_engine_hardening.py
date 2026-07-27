"""v1 评审引擎（ReviewService.run_review，Wizard/直接调 /api/reviews 的旧链路）加固回归。

此前的三个真问题（来自 2026-07-23 功能链路审计，均已逐一核实）：
  1. 直接读 os.environ 的 ANTHROPIC_API_KEY——用户在设置页存的 BYOK key 完全无效；
  2. 没有环境变量时静默把 _build_simulated_output 的占位数据当真实报告入库；
  3. WS 广播用 {type: ...} 老信封，前端 ws.ts 按 payload.event 判终态，永远判不到。

现在：key 走 key_service.resolve_key（与 v2 同源），无 key 直接 failed 绝不模拟，
WS 信封统一为 {event, data}。

交叉质询那一段的加固见文件末尾 TestV1CrossExamination（三个问题：失败被
`except Exception: pass` 吞掉、反驳 token 没计成本、产出形状与引擎链路不一致）。
"""

import json
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


# ---------------------------------------------------------------------------
# 交叉质询（cross-examination）
# ---------------------------------------------------------------------------
#
# 修复前的实际状态（逐条实跑核实过）：
#   1. 整段被 `except Exception: pass` 包着——反驳调用 401/超时/输出解析不了时，
#      报告跟"本来就没有争议点"长得完全一样，用户无从知道这一步跑过又挂了；
#   2. ce_in / ce_out 只加进 token 总数，**成本一分没算**，total_cost_usd
#      系统性低于实际支出（按成本扣的配额也少扣）；
#   3. 塞进 report["cross_examination"] 的是 parse_cross_exam_output 的**原始列表**，
#      而引擎链路给的是带 mode/limitation/vote_changes 的 dict——同一个概念两种形状，
#      前端得写两套读法（degradation 字段刚吃过这个亏）。
#
# 现在两条链路共用 runner.cross_exam.run_cross_exam_protocol。

CE_PERSONA_A_ID = "P01-indie-core-operator"
CE_PERSONA_B_ID = "P02-systems-theorycrafter"
CE_PERSONA_A_NAME = "林岚"  # 与 src/personas/game-core.yaml 一致
CE_PERSONA_B_NAME = "周策"

CE_ISSUE_ONBOARDING = "新手引导偏长"
CE_ISSUE_ART = "美术风格不统一"

# 两位人格对同样两个议题给出**相反**的严重度判定——这是 extract_controversy_points
# 挑得出争议点（severity_variance > 0）、双方都有可反驳论据的前提。
# A 的第二条论据里故意点了对方的名字，用来验证匿名化在 v1 这条链路上同样生效。
CE_OUTPUT_A = {
    "persona_id": CE_PERSONA_A_ID,
    "persona_name": CE_PERSONA_A_NAME,
    "primary_stance": "值得推进",
    "confidence": 0.8,
    "evidence_sufficiency": 0.7,
    "evidence": [],
    "missing_information": [],
    "voice_sample": "核心循环有东西，但前 15 分钟太磨人。",
    "key_issues": [
        {
            "title": CE_ISSUE_ONBOARDING,
            "severity": "critical",
            "why_it_matters": "前 15 分钟摸不到核心循环，试玩用户会直接退款",
            "suggested_fix": "把教程压到 3 分钟内",
        },
        {
            "title": CE_ISSUE_ART,
            "severity": "high",
            "why_it_matters": f"{CE_PERSONA_B_NAME}说风格差异无所谓，但四张图出自四个人之手，信任感会崩",
            "suggested_fix": "统一色板并重出主视觉",
        },
    ],
}

CE_OUTPUT_B = {
    "persona_id": CE_PERSONA_B_ID,
    "persona_name": CE_PERSONA_B_NAME,
    "primary_stance": "不值得",
    "confidence": 0.5,
    "evidence_sufficiency": 0.6,
    "evidence": [],
    "missing_information": [],
    "voice_sample": "系统深度不够，引导长短不是重点。",
    "key_issues": [
        {
            "title": CE_ISSUE_ONBOARDING,
            "severity": "low",
            "why_it_matters": "目标受众本来就习惯长引导，这不构成劝退点",
            "suggested_fix": "保持现状",
        },
        {
            "title": CE_ISSUE_ART,
            "severity": "low",
            "why_it_matters": "风格差异在这个品类里是常态，不值得为它推迟上线",
            "suggested_fix": "上线后再迭代",
        },
    ],
}

CE_PERSONA_PAYLOADS = [
    json.dumps(CE_OUTPUT_A, ensure_ascii=False),
    json.dumps(CE_OUTPUT_B, ensure_ascii=False),
]

# 仲裁式反驳的模型回包。刻意埋了三种情形：
#   A1 —— 立场原样照抄（不改票），但自报 "stance_changed": true：代码必须不采信；
#   B1 —— 立场真变且置信度 0.50→0.75（Δ=0.25 ≥ θ=0.15）：这才算一次改票；
#   B2 —— 立场真变但置信度只到 0.55（Δ=0.05 < θ）：进 suppressed_changes 不进 vote_changes。
CE_MODERATED_RESPONSE = json.dumps(
    [
        {
            "point_id": "C1",
            "rebuttals": [
                {
                    "argument_id": "A1",
                    "rebuttal": "退款数据来自别的品类，不能直接套到这里",
                    "stance_after": "值得推进",
                    "confidence_after": 0.85,
                    "stance_changed": True,
                },
                {
                    "argument_id": "B1",
                    "rebuttal": "确实没看首 15 分钟的流失曲线，这条站得住",
                    "stance_after": "值得推进",
                    "confidence_after": 0.75,
                },
            ],
        },
        {
            "point_id": "C2",
            "rebuttals": [
                {
                    "argument_id": "A2",
                    "rebuttal": "风格差异对信任的影响被高估了",
                    "stance_after": "值得推进",
                    "confidence_after": 0.8,
                },
                {
                    "argument_id": "B2",
                    "rebuttal": "主视觉确实该重做一版",
                    "stance_after": "值得推进",
                    "confidence_after": 0.55,
                },
            ],
        },
    ],
    ensure_ascii=False,
)

CE_TOKENS = (700, 250)
PERSONA_TOKENS = (10, 5)


def _ce_fake_chat(cross_exam_handler=None):
    """假 chat_completion，把"人格评审调用"和"交叉质询调用"分流。

    分流标记用 "argument_id"：交叉质询的两段提示词都要求模型回这个字段，而
    src/templates/persona-prompt.md 里既没有 "argument_id" 也没有"交叉质询"
    （已核实），所以不会误判。

    返回 (fake, calls)；calls["cross_exam"] 收下每一条真正发出去的反驳提示词，
    后面的匿名化断言直接读它——这比断言"渲染函数被调用了"实在得多。
    """
    calls = {"persona": [], "cross_exam": []}

    def fake(**kwargs):
        prompt = kwargs.get("prompt", "")
        if "argument_id" in prompt:
            calls["cross_exam"].append(prompt)
            if cross_exam_handler is not None:
                return cross_exam_handler(prompt)
            return (CE_MODERATED_RESPONSE, CE_TOKENS[0], CE_TOKENS[1])
        idx = len(calls["persona"])
        calls["persona"].append(prompt)
        return (CE_PERSONA_PAYLOADS[idx % len(CE_PERSONA_PAYLOADS)], *PERSONA_TOKENS)

    return fake, calls


def _run_v1_inline(db, monkeypatch, fake_chat, mode="standard"):
    """同步直跑 ReviewService.run_review，返回 Review 行。

    为什么不走 HTTP：匿名响应会把 report_json["cross_examination"] 整块裁成 None
    （见 report_gating.gate_report_for_anonymous），而这一组用例要验的正是那个区块
    的内容。直连引擎顺带去掉了后台任务轮询，用例是确定性的。

    绕开证据预检的理由同 test_partial_failure_marks_report_degraded：测试用的极简
    材料会让人格因"缺所需证据"被跳过，凑不出两位对立人格。
    """
    import app.services as services_mod
    from app.services import ReviewService, key_service

    key_service.save_user_key(db, "anonymous", f"sk-cross-exam-{mode}")

    real_precheck = services_mod.precheck_panel
    monkeypatch.setattr(
        services_mod,
        "precheck_panel",
        lambda sel, ab: {**real_precheck(sel, ab), "valid_personas": list(sel)},
    )

    import runner.llm_client

    monkeypatch.setattr(runner.llm_client, "chat_completion", fake_chat)

    svc = ReviewService(db)
    review = svc.create_review(
        task_type="concept_review",
        artifact_bundle={
            "title": "交叉质询验证",
            "materials": [{"type": "核心循环说明", "description": "探索-战斗-成长"}],
        },
        # 显式点名两位：默认预设只会跑 1 位，一个人格没有对立方，交叉质询无从发生
        selected_personas=[CE_PERSONA_A_ID, CE_PERSONA_B_ID],
        mode=mode,
    )
    svc.run_review(review.id)
    db.refresh(review)
    return review


def _ce_block(review) -> dict:
    block = (review.report_json or {}).get("cross_examination")
    assert isinstance(block, dict), (
        "cross_examination 必须是协议核心那个 dict。曾经这里是 "
        "parse_cross_exam_output 的原始列表，与引擎链路两种形状。"
    )
    return block


class TestV1CrossExamination:
    def test_moderated_rebuttal_actually_runs_and_says_so_honestly(self, db, monkeypatch):
        """standard 档：真发了一次仲裁式反驳调用，且口径不夸大。

        底线：is_live_debate 只在真的拿到反驳结果时为 True，且必须能看出这是
        **一次仲裁式反驳轮**、不是"每个人格各自独立重新发言"。
        """
        fake, calls = _ce_fake_chat()
        review = _run_v1_inline(db, monkeypatch, fake)

        assert review.status == "completed", review.error_message
        assert len(calls["cross_exam"]) == 1, "standard 档应当恰好发 1 次反驳调用"

        block = _ce_block(review)
        assert block["mode"] == "moderated_rebuttal"
        assert block["is_live_debate"] is True
        assert block["requested_mode"] == "moderated_rebuttal"
        # 措辞不许含糊：既要说清是仲裁式，也要把"不是每人各自发言"写明
        assert "一次仲裁式反驳轮" in block["limitation"]
        assert "不是每个人格各自独立重新发言" in block["limitation"]
        # 派生摘要那句英文声明只属于 derived_summary，跑了反驳就不许再出现
        assert "no live multi-agent rebuttal was executed" not in block["limitation"]
        assert block["usage"]["calls"] == 1
        assert block["usage"]["token_counts_available"] is True
        # rounds 反映实际轮次，不再是恒定 3 个假 Round 指示器
        assert len(block["rounds"]) == 1

        # 反驳正文要能落进报告结构里（前端才渲染得出来）
        disputes = block["disputes"]
        assert disputes and all(d["rebuttal_status"] == "ok" for d in disputes)
        assert any(a["rebuttal"] for d in disputes for a in d["pro_args"])

    def test_vote_changes_are_computed_by_code_not_claimed_by_model(self, db, monkeypatch):
        """改票是代码比出来的：立场文字真变 **且** |Δ置信度| ≥ θ。

        三条都在同一份模型回包里验：
          · A1 自报 stance_changed=true 但立场原样照抄 → 不算改票；
          · B1 立场真变且 Δ=0.25 ≥ θ=0.15 → 算，且 θ 是从 aggregation-rules.yaml 读的；
          · B2 立场真变但 Δ=0.05 < θ → 只进 suppressed_changes。
        """
        fake, _calls = _ce_fake_chat()
        review = _run_v1_inline(db, monkeypatch, fake)
        block = _ce_block(review)

        # θ 真的被读取并执行（这个值以前全仓库零读取点）
        assert block["threshold"] == 0.15
        assert block["threshold_source"] == "rules-dict"
        assert block["allow_stance_update"] is True

        changes = block["vote_changes"]
        assert len(changes) == 1, f"只有 B1 达阈值，实际 {[c['argument_id'] for c in changes]}"
        change = changes[0]
        assert change["argument_id"] == "B1"
        # persona_id 是**真 id**，人名单独放 persona_name（报告模板据此显示人名）
        assert change["persona_id"] == CE_PERSONA_B_ID
        assert change["persona_name"] == CE_PERSONA_B_NAME
        assert change["from_stance"] == "不值得"
        assert change["to_stance"] == "值得推进"
        assert abs(change["delta"] - 0.25) < 1e-6
        assert change["threshold"] == 0.15

        # 模型自报的改票不算数
        assert "A1" not in [c["argument_id"] for c in changes]

        suppressed = block["suppressed_changes"]
        assert [s["argument_id"] for s in suppressed] == ["B2"]
        assert "未达阈值" in suppressed[0]["suppressed_reason"]

        # 置信度变化是真算的百分点，不是硬编码 0
        by_key = {c["persona_key"]: c for c in block["confidence_changes"]}
        assert set(by_key) == {CE_PERSONA_A_ID, CE_PERSONA_B_ID}
        assert by_key[CE_PERSONA_B_ID]["before"] == 50
        assert by_key[CE_PERSONA_B_ID]["delta"] == (
            by_key[CE_PERSONA_B_ID]["after"] - by_key[CE_PERSONA_B_ID]["before"]
        )

    def test_cross_exam_tokens_and_cost_are_billed(self, db, monkeypatch):
        """反驳是真花钱的调用：token 和成本都得进账。

        以前只把 token 加进总数、成本一分没算——用户账面上的 total_cost_usd
        比实际支出低，按成本扣的配额也少扣。本仓库刚修过一批同类"花了钱账上
        看不到"的问题，这条把交叉质询这笔钉住。
        """
        from app.models import UsageRecord
        from app.services import BUDGET_PATH
        from runner.persona_agent import estimate_cost

        import yaml as _yaml

        fake, calls = _ce_fake_chat()
        review = _run_v1_inline(db, monkeypatch, fake)

        persona_calls = len(calls["persona"])
        assert persona_calls == 2
        assert review.input_tokens == persona_calls * PERSONA_TOKENS[0] + CE_TOKENS[0]
        assert review.output_tokens == persona_calls * PERSONA_TOKENS[1] + CE_TOKENS[1]

        with open(BUDGET_PATH, "r", encoding="utf-8") as f:
            budget_config = _yaml.safe_load(f)
        ce_cost = estimate_cost(
            CE_TOKENS[0], CE_TOKENS[1], budget_config["default_model"], budget_config
        )
        assert ce_cost > 0, "价目表里没有默认模型的话这条用例证明不了任何事"

        persona_cost = sum(po.cost_usd or 0.0 for po in review.persona_outputs)
        assert review.total_cost_usd > persona_cost, "交叉质询的成本没进总账"
        assert abs(review.total_cost_usd - (persona_cost + ce_cost)) < 1e-9

        # 计量事实源（后台 token/成本报表读的是这张表）也必须包含这笔
        record = (
            db.query(UsageRecord).filter(UsageRecord.review_id == review.id).one()
        )
        assert record.input_tokens == review.input_tokens
        assert record.output_tokens == review.output_tokens
        assert abs(record.cost_usd - review.total_cost_usd) < 1e-9

    def test_cross_exam_failure_is_reported_not_swallowed(self, db, monkeypatch):
        """反驳挂了：评审照样 completed，但报告里必须看得见"这一步没完成，以及为什么"。

        这条替换的正是 `except Exception: pass`。那个模式在本仓库出过事故——
        全盘失败被输出成一份"没发现风险"的报告。交叉质询失败不该让整份评审作废，
        但绝不能静默。
        """
        def boom(_prompt):
            raise RuntimeError("503 upstream busy")

        fake, calls = _ce_fake_chat(cross_exam_handler=boom)
        review = _run_v1_inline(db, monkeypatch, fake)

        assert review.status == "completed", review.error_message
        assert len(calls["cross_exam"]) == 1, "该发的调用还是要发，只是失败了"

        block = _ce_block(review)
        # 关键：跑失败了就得如实回落，绝不允许无条件 is_live_debate=True
        assert block["mode"] == "derived_summary"
        assert block["is_live_debate"] is False
        # requested_mode 留着落差，看得出"本来要跑仲裁式反驳"
        assert block["requested_mode"] == "moderated_rebuttal"
        assert block["failures"], "失败必须留痕"
        assert "503 upstream busy" in block["failures"][0]["error"]
        assert "未能完成" in block["limitation"]
        assert "503 upstream busy" in block["limitation"]
        assert block["vote_changes"] == [], "没发生反驳就不许有人改票"
        assert all(d["rebuttal_status"] == "failed" for d in block["disputes"])
        assert all(d["rebuttal_error"] for d in block["disputes"])

        # 报告其余部分照出——失败的只是交叉质询这一段
        report = review.report_json
        assert report["executive_summary"]["primary_recommendation"]
        assert report["priority_fixes"]
        assert review.report_markdown

    def test_quick_mode_does_not_run_cross_exam(self, db, monkeypatch):
        """quick 档不跑交叉质询：一次调用都不许发，也不出这个区块。

        mode_config["cross_examination"] 是 False，这是用户为"快"付的代价，
        不能因为"反正都写好了"就顺手跑掉一笔钱。
        """
        fake, calls = _ce_fake_chat()
        review = _run_v1_inline(db, monkeypatch, fake, mode="quick")

        assert review.status == "completed", review.error_message
        assert calls["cross_exam"] == []
        assert (review.report_json or {}).get("cross_examination") is None
        assert review.input_tokens == len(calls["persona"]) * PERSONA_TOKENS[0]

    def test_full_mode_runs_multi_agent_rebuttal_with_anonymous_prompts(
        self, db, monkeypatch
    ):
        """full 档：每位涉事人格各被重新调用一次，且提示词里不出现任何人格名。

        两件事一起验：
          1. mode 是 multi_agent_rebuttal，调用次数 = 争议点数 × 2（这才配叫多智能体反驳）；
          2. 每条反驳提示词都带上了"你是谁"，但**不带人格名**——名字一露出来，
             模型就容易按身份结盟或让位，反驳就不再是对论据的检验。
             A 的论据正文里本来写了对方的名字，渲染层必须把它洗掉。
        """
        def per_persona(prompt):
            # 提示词里的 "被编号为论据 A1" 就是这次该反驳的论据编号
            import re

            match = re.search(r"被编号为论据 ([AB]\d+)", prompt)
            assert match, prompt[:200]
            return (
                json.dumps(
                    {
                        "argument_id": match.group(1),
                        "rebuttal": "对方对影响范围的估计缺少同品类数据支撑",
                        "stance_after": "观望",
                        "confidence_after": 0.3,
                    },
                    ensure_ascii=False,
                ),
                120,
                60,
            )

        fake, calls = _ce_fake_chat(cross_exam_handler=per_persona)
        review = _run_v1_inline(db, monkeypatch, fake, mode="full")

        assert review.status == "completed", review.error_message
        block = _ce_block(review)
        assert block["mode"] == "multi_agent_rebuttal"
        assert block["is_live_debate"] is True

        debatable = [d for d in block["disputes"] if d["rebuttal_status"] != "skipped"]
        assert len(calls["cross_exam"]) == 2 * len(debatable) >= 2
        assert block["usage"]["calls"] == len(calls["cross_exam"])

        for prompt in calls["cross_exam"]:
            assert "[你的身份]" in prompt, "没带身份的话这就只是 N 次匿名调用"
            for name in (CE_PERSONA_A_NAME, CE_PERSONA_B_NAME):
                assert name not in prompt, f"反驳提示词里出现了人格名 {name}"
            # 论据只用匿名编号指代
            assert "论据" in prompt

        # 名字被洗成占位词，而不是被整段删掉（删掉会让论据不知所云）
        arg_texts = [a["point"] for d in block["disputes"] for a in d["pro_args"]]
        assert any("某位评审" in t for t in arg_texts)

    def test_full_mode_completes_and_persists_calibration(self, db, monkeypatch):
        """full 档能真的跑完——这是多智能体反驳有没有意义的前提。

        修复前 v1 的 full 档只要有 ≥2 位人格就 100% 失败，而且是在最后一步：
        run_calibration_check 的 coverage.pairwise_distances 用 (id1, id2) 元组做键，
        JSON 列存不了 → 整条 UPDATE 抛 TypeError("keys must be str, ...") → 被
        run_review 外层 except 接住 → 评审标 failed，错误信息跟评审毫无关系。
        （只有 full 档跑校准，而已有用例从没在 v1 上跑过 full，所以一直没暴露。）
        现在元组键在落库前洗成 "id1|id2"，见 services._json_safe。
        """
        fake, _calls = _ce_fake_chat(
            cross_exam_handler=lambda _p: (CE_MODERATED_RESPONSE, *CE_TOKENS)
        )
        review = _run_v1_inline(db, monkeypatch, fake, mode="full")

        assert review.status == "completed", review.error_message
        assert review.calibration, "full 档必须留下校准结果"
        pairwise = review.calibration["coverage"]["pairwise_distances"]
        assert pairwise, "两位人格之间应当有一条两两距离"
        assert all(isinstance(k, str) for k in pairwise), "键必须是字符串才存得进 JSON 列"
        # 落库后能原样读回来（json 列真的存下去了，不是靠 ORM 缓存看起来有值）
        json.dumps(review.calibration)

    def test_output_structure_matches_engine_chain(self, db, monkeypatch):
        """**最重要的一条**：v1 与引擎链路产出同一种结构，字段名和语义完全一致。

        做法是拿同样的输入直接跑一遍协议核心（引擎链路调的就是它），逐字比对。
        这样既钉住"v1 没有自己再包一层/改名/丢字段"，又不会在协议核心日后新增
        字段时误报——两边一起变。

        本仓库刚吃过"同一概念两条链路两种结构"的苦（degradation 字段），
        cross_examination 不能再来一次。
        """
        from app.services import CROSS_EXAM_PROMPT_PATH, RULES_PATH
        from runner.aggregator import load_aggregation_rules
        from runner.cross_exam import extract_controversy_points, run_cross_exam_protocol
        from runner.persona_agent import normalize_persona_output, parse_persona_output

        fake, _calls = _ce_fake_chat()
        review = _run_v1_inline(db, monkeypatch, fake)
        block = _ce_block(review)

        # 复现 v1 喂给协议核心的输入：人格按 selected_personas 的包内顺序串行跑，
        # 所以输出顺序就是 [A, B]
        persona_outputs = [
            normalize_persona_output(parse_persona_output(raw)) for raw in CE_PERSONA_PAYLOADS
        ]
        expected = run_cross_exam_protocol(
            persona_outputs,
            extract_controversy_points(persona_outputs),
            llm_call=lambda prompt, persona_id="": (
                CE_MODERATED_RESPONSE, CE_TOKENS[0], CE_TOKENS[1]
            ),
            mode="moderated_rebuttal",
            template_path=CROSS_EXAM_PROMPT_PATH,
            rules=load_aggregation_rules(RULES_PATH),
        )

        # 协议约定的字段一个都不能少（显式列出，改契约时这条会先炸）
        for key in (
            "mode", "is_live_debate", "requested_mode", "limitation",
            "threshold", "threshold_source", "allow_stance_update",
            "rounds", "disputes", "vote_changes", "suppressed_changes",
            "confidence_changes", "failures", "usage",
        ):
            assert key in block, f"cross_examination 缺字段 {key}"

        assert set(block) == set(expected), "v1 与引擎链路的字段集合必须一致"
        assert block == expected, "同样输入下两条链路必须产出逐字相同的区块"

    def test_report_template_can_render_the_block(self, db, monkeypatch):
        """区块得落进现有报告结构里——报告页读的那几个字段名都在。

        vote_changes 里同时保留了旧模板的 before/after 别名，
        新增的 rebuttal / rebuttal_status 也挂在 disputes 上。
        """
        fake, _calls = _ce_fake_chat()
        review = _run_v1_inline(db, monkeypatch, fake)
        block = _ce_block(review)

        for dispute in block["disputes"]:
            assert {"point_id", "topic", "pro_args", "con_args"} <= set(dispute)
            for arg in dispute["pro_args"] + dispute["con_args"]:
                assert {"argument_id", "point", "persona_id", "severity", "rebuttal"} <= set(arg)

        for change in block["vote_changes"]:
            # 旧模板读 before/after，新报告读 from_stance/to_stance，两套都在
            assert change["before"] == change["from_stance"]
            assert change["after"] == change["to_stance"]

        for row in block["confidence_changes"]:
            # 这个位置历史上放展示名（模板直接当标签渲染），真 id 在 persona_key
            assert row["persona_id"] in (CE_PERSONA_A_NAME, CE_PERSONA_B_NAME)
            assert isinstance(row["delta"], int)
