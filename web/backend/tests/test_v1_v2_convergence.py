"""POST /api/reviews（v1 形状）与 POST /api/v2/reviews 必须是同一条执行路径。

背景：这两个端点以前各有一套评审实现——v1 走
`ReviewService.run_review`（web/backend/app/services/__init__.py 里近 400 行，
自己选人、自己调模型、自己做交叉质询、自己聚合），v2 走
`runner.cli.run_panel`。同一件事两套代码的代价是实测出来的：本轮审计 62 条
发现里，「v2 修了 v1 没修」这一种形状反复出现（calibration 落库、BYOK、
降级契约、交叉质询过滤…）。

现在 v1 只保留 API 形状（200 + 完整 Review 实体），执行交给
review_service.enqueue_review → runner.cli.run_panel，与 v2 逐字同源。
run_review 已删除。

这个文件替换了原来的 tests/test_v1_engine_hardening.py。那个文件里
「v1 的交叉质询与引擎链路产出一致」那一整组用例在收敛之后是同义反复
（v1 就是引擎链路），它们对应的行为由引擎自己的测试套守着
（tests/test_cross_exam.py、tests/test_cost_and_failure_honesty.py）。
那个文件里**不**属于 v1 引擎的部分（匿名裁剪、BYOK 抽取、非游戏任务类型选人）
原样搬到了本文件下半部分，不能因为删实现顺手把覆盖也删了。
"""

import time

import pytest


# ---------------------------------------------------------------------------
# 公共夹具与工具
# ---------------------------------------------------------------------------

ANON = "anonymous"


@pytest.fixture
def anon_key(db):
    """给两条链路一把可解析的 BYOK key，用完删掉。

    必须显式删：库是整个测试会话共用的，留下的 key 会让别的文件里
    「无 key 应当 428」那类用例莫名其妙地变绿。
    """
    from app.services import key_service

    key_service.save_user_key(db, ANON, "sk-convergence-test")
    yield "sk-convergence-test"
    key_service.delete_user_key(db, ANON)


@pytest.fixture
def no_key(db):
    """确保当前身份**没有**任何可解析的 key（别的用例可能留了一把）。"""
    from app.services import key_service

    key_service.delete_user_key(db, ANON)
    yield
    key_service.delete_user_key(db, ANON)


SECRET = "仅登录可见的角色原话与深度分析"


def _fake_report(secret: str = "") -> dict:
    """一份形状齐全的报告：执行摘要 + 两条优先修复项 + 一位人格的详细意见。

    secret 塞在「体验版一定会裁掉」的位置（第二条优先修复项 + 角色原话），
    不放第一条——体验版有意保留第一条当诱饵（见 gate_report_for_anonymous），
    拿它当泄露证据是在测一个设计上不存在的要求。
    """
    return {
        "meta": {"task_type": "concept_review"},
        "executive_summary": {
            "release_risk": "medium",
            "primary_recommendation": "先把前 15 分钟的引导压短",
        },
        "priority_fixes": [
            {"title": "引导偏长", "severity": "critical", "why_it_matters": "试玩用户会退款"},
            {
                "title": secret or "美术风格不统一",
                "severity": "low",
                "why_it_matters": secret or "信任感会打折",
            },
        ],
        "persona_notes": [
            {
                "persona_id": "P01-indie-core-operator",
                "persona_name": "林岚",
                "primary_stance": "观望",
                "confidence": 0.6,
                "voice_sample": secret or "核心循环有东西，但前 15 分钟太磨人。",
                "key_issues": [
                    {
                        "title": "引导偏长",
                        "severity": "critical",
                        "why_it_matters": "摸不到核心循环",
                    }
                ],
            }
        ],
        "consensus": {"agreement_level": 0.5},
    }


def _fake_run_panel(calls: list, secret: str = ""):
    """替身引擎：记下调用参数，返回一份定型结果。

    记参数是这个文件的核心手段——「两个端点跑的是同一套引擎」这句话，
    只有把两边真正传给 run_panel 的东西摆在一起逐字比对才算证明。
    """

    def _run(**kwargs):
        calls.append(kwargs)
        return {
            "report": _fake_report(secret),
            "markdown": "# 报告\n\n> **⚠️ 降级提示会由引擎写在这里**\n",
            "html": "<html></html>",
            "calibration": {"coverage": {"pairwise_distances": {}}},
            "simulated": False,
            "cost_summary": {
                "total_cost": 0.34,
                "persona_count": 1,
                "skipped_count": 0,
                "total_input_tokens": 4200,
                "total_output_tokens": 1800,
            },
        }

    return _run


def _patch_engine(monkeypatch, calls, secret: str = ""):
    import runner.cli

    monkeypatch.setattr(runner.cli, "run_panel", _fake_run_panel(calls, secret))


V1_BODY = {
    "task_type": "concept_review",
    # 显式给 persona_pack：v1 的默认是 None、v2 的默认是 "game-core"。
    # 两者最终都落到同一个人格包文件，但只有显式写死才能让下面的
    # 「引擎入参逐字相同」断言测的是收敛本身，而不是两份默认值的巧合。
    "persona_pack": "game-core",
    "mode": "standard",
    "artifact_bundle": {
        "title": "收敛验证",
        # {type,text} 形态——v1 旧引擎只读 materials[].description，
        # 这种材料会被渲染成空字符串。收敛后由引擎统一处理。
        "materials": [{"type": "text", "text": "探索-战斗-成长"}],
    },
}

V2_BODY = {
    "task_type": V1_BODY["task_type"],
    "persona_pack": V1_BODY["persona_pack"],
    "mode": V1_BODY["mode"],
    "artifact": V1_BODY["artifact_bundle"],
}


def _post_v1(client, **over):
    body = dict(V1_BODY)
    body.update(over)
    return client.post("/api/reviews", json=body)


def _post_v2(client, **over):
    body = dict(V2_BODY)
    body.update(over)
    return client.post("/api/v2/reviews", json=body)


def _wait_terminal(client, review_id, timeout=15.0):
    deadline = time.time() + timeout
    detail = None
    while time.time() < deadline:
        detail = client.get(f"/api/reviews/{review_id}").json()
        if detail["status"] in ("completed", "failed"):
            return detail
        time.sleep(0.05)
    raise AssertionError(f"review {review_id} 未到终态：{detail}")


# ---------------------------------------------------------------------------
# 两条链路的行为一致性
# ---------------------------------------------------------------------------


class TestBothEndpointsRunTheSameEngine:
    def test_engine_receives_identical_arguments(self, client, db, anon_key, monkeypatch):
        """**这是本文件最重要的一条**：同样入参下，两个端点交给 run_panel 的
        东西必须逐字相同。只要这条绿着，「v2 修了 v1 没修」就不可能再发生——
        因为根本没有第二个实现可以漏改。
        """
        calls = []
        _patch_engine(monkeypatch, calls)

        r1 = _post_v1(client)
        assert r1.status_code == 200, r1.text
        _wait_terminal(client, r1.json()["id"])

        r2 = _post_v2(client)
        assert r2.status_code == 202, r2.text
        _wait_terminal(client, r2.json()["review_id"])

        assert len(calls) == 2, f"两个端点各该调一次引擎，实际 {len(calls)} 次"
        v1_kwargs, v2_kwargs = calls

        # progress_callback 是闭包（对象地址不同），max_concurrency 读后台设置，
        # 这两个与「评审内容」无关，比对时排除；其余一个字都不能差。
        ignored = {"progress_callback", "max_concurrency"}
        v1_cmp = {k: v for k, v in v1_kwargs.items() if k not in ignored}
        v2_cmp = {k: v for k, v in v2_kwargs.items() if k not in ignored}
        assert v1_cmp == v2_cmp, f"v1={v1_cmp}\nv2={v2_cmp}"

        # 顺带钉住几个具体值，免得两边一起错了还互相印证
        assert v1_cmp["task_type"] == "concept_review"
        assert v1_cmp["mode"] == "standard"
        assert v1_cmp["api_key"] == anon_key
        # {type,text} 材料原样进引擎——v1 旧实现只认 description，这种材料变空串
        assert v1_cmp["artifact_bundle"]["materials"][0]["text"] == "探索-战斗-成长"

    def test_success_response_fields(self, client, db, anon_key, monkeypatch):
        """成功路径的对外形状：v1 仍是 200 + 完整 Review 实体（公开 API 不动），
        v2 仍是 202 + {review_id, job_id}；但两边落库的结果必须一致。
        """
        calls = []
        _patch_engine(monkeypatch, calls)

        r1 = _post_v1(client)
        assert r1.status_code == 200
        v1_created = r1.json()
        # v1 契约字段一个都不能少（外部调用方按这些字段读）
        for field in ("id", "task_type", "status", "created_at", "artifact_bundle",
                      "mode", "total_cost_usd", "persona_outputs"):
            assert field in v1_created, f"v1 响应缺字段 {field}"
        assert v1_created["status"] == "pending"

        r2 = _post_v2(client)
        assert r2.status_code == 202
        assert {"review_id", "job_id", "status", "websocket"} <= set(r2.json())

        v1_done = _wait_terminal(client, v1_created["id"])
        v2_done = _wait_terminal(client, r2.json()["review_id"])

        assert v1_done["status"] == v2_done["status"] == "completed"
        for field in ("report_json", "report_markdown", "calibration",
                      "total_cost_usd", "task_type", "mode"):
            assert v1_done[field] == v2_done[field], f"{field} 两条链路不一致"

    def test_unknown_task_type_rejected_by_both(self, client, db, anon_key, monkeypatch):
        """未知 task_type 必须在入口就 400，且不留下评审行。

        v1 此前完全不校验：未知类型会随机抓一批人格照跑照扣钱，
        或者要等到后台任务里 run_panel 抛 ValueError 才变成一条 failed 评审——
        用户拿到的是「跑失败了」而不是「你填错了」。
        """
        from app.models import Review

        calls = []
        _patch_engine(monkeypatch, calls)
        before = db.query(Review).count()

        r1 = _post_v1(client, task_type="no_such_task_type")
        r2 = _post_v2(client, task_type="no_such_task_type")

        assert r1.status_code == 400, r1.text
        assert r2.status_code == 400, r2.text
        assert calls == [], "被拒的请求不该调用引擎"
        db.expire_all()
        assert db.query(Review).count() == before, "被拒的请求不该留下评审行"

    def test_missing_key_rejected_by_both_with_428(self, client, db, no_key, monkeypatch):
        """无 key → 两条链路都是 428，且都不建评审行。

        绝不静默跑模拟数据：模拟结果没有评审价值，把它当报告入库比直接报错危险，
        因为用户会据此做决定。
        """
        from app.models import Review

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from app.config import settings

        monkeypatch.setattr(settings, "server_llm_key", "")
        before = db.query(Review).count()

        assert _post_v1(client).status_code == 428
        assert _post_v2(client).status_code == 428

        db.expire_all()
        assert db.query(Review).count() == before, "无 key 不该留下评审行"

    def test_v1_now_writes_judgments_and_usage_like_v2(
        self, client, db, anon_key, monkeypatch
    ):
        """收敛顺带补上的两件事：判断复利闭环（Judgment）与计量事实源（UsageRecord）。

        Judgment 是 v1 旧实现从来不写的——「判断复利」这个卖点对走
        POST /api/reviews 创建的评审永远是空的。现在两条链路共用
        review_service._execute_review，这一步自然覆盖到。
        """
        from app.models import Judgment, UsageRecord

        calls = []
        _patch_engine(monkeypatch, calls)

        review_id = _post_v1(client).json()["id"]
        assert _wait_terminal(client, review_id)["status"] == "completed"

        judgments = db.query(Judgment).filter(Judgment.review_id == review_id).all()
        assert judgments, "v1 创建的评审也必须落 Judgment，否则判断复利闭环是空的"

        rec = db.query(UsageRecord).filter(UsageRecord.review_id == review_id).one()
        assert rec.input_tokens == 4200
        assert rec.output_tokens == 1800

    def test_engine_failure_marks_failed_never_fabricates_a_clean_report(
        self, client, db, anon_key, monkeypatch
    ):
        """引擎挂了就是 failed，绝不产出一份「没发现风险」的报告，
        而且**失败原因必须在 v1 读路径上看得见**。

        这是本仓库最危险的一类缺陷：不崩、不报错，反而伪造一份干净结论。
        原因的可见性单列一条断言：ReviewResponse 里没有 error_message 字段
        （引擎把原因写在那一列），收敛时若不把它转译回 v1 契约里的
        report_json={"error": ...}，失败评审就会变成「status=failed，
        但为什么失败一个字都看不到」。三条读路径都得能看到。
        """
        import runner.cli

        def boom(**kwargs):
            raise RuntimeError("401 invalid api key")

        monkeypatch.setattr(runner.cli, "run_panel", boom)

        review_id = _post_v1(client).json()["id"]
        detail = _wait_terminal(client, review_id)
        assert detail["status"] == "failed"
        report = detail.get("report_json") or {}
        assert (report.get("executive_summary") or {}).get("release_risk") != "low"
        assert not report.get("priority_fixes")

        for path in (
            f"/api/reviews/{review_id}",
            f"/api/reviews/{review_id}/report",
            f"/api/reviews/{review_id}/result",
        ):
            body = client.get(path).json()
            reported = body.get("report_json") or {}
            assert "401 invalid api key" in (reported.get("error") or ""), path

    def test_simulated_result_is_never_persisted(self, client, db, anon_key, monkeypatch):
        """引擎回报 simulated=True（没检测到有效 key 时的自跑模式）时必须丢弃。"""
        import runner.cli

        calls = []
        base = _fake_run_panel(calls)

        def simulated(**kwargs):
            result = base(**kwargs)
            result["simulated"] = True
            return result

        monkeypatch.setattr(runner.cli, "run_panel", simulated)

        detail = _wait_terminal(client, _post_v1(client).json()["id"])
        assert detail["status"] == "failed"
        assert not (detail.get("report_json") or {}).get("priority_fixes")


# ---------------------------------------------------------------------------
# 匿名裁剪（从 test_v1_engine_hardening.py 搬来，与引擎实现无关）
# ---------------------------------------------------------------------------


class TestAnonymousGatingOnV1ReadEndpoints:
    """匿名裁剪不能把「评审到底在不在跑」这个基本事实也裁掉，
    也不能漏掉任何一个会吐报告内容的 v1 端点——漏一条登录墙就等于没有。"""

    def test_anonymous_sees_personas_but_not_their_content(
        self, client, db, anon_key, monkeypatch
    ):
        calls = []
        _patch_engine(monkeypatch, calls, secret=SECRET)

        detail = _wait_terminal(client, _post_v1(client).json()["id"])
        assert detail["status"] == "completed"

        outputs = detail.get("persona_outputs") or []
        assert outputs, "匿名也必须能看到角色列表，否则进度页显示 0 位角色"
        assert all(po.get("persona_id") for po in outputs)
        assert all(po.get("status") for po in outputs)
        # 但每位角色的输出内容必须被裁掉
        assert all(po.get("output_json") is None for po in outputs)
        assert all(po.get("validation_result") is None for po in outputs)

    def test_no_v1_endpoint_leaks_full_report_to_anonymous(
        self, client, db, anon_key, monkeypatch
    ):
        """三条 v1 读路径必须**同时**裁剪。

        修复前的真实状态：裁剪只接在 /reviews/{id}/report 上，而且连它都从
        report_markdown 把全文漏了出去——前端显示「登录看完整」，换个端点全文到手。
        """
        calls = []
        _patch_engine(monkeypatch, calls, secret=SECRET)

        review_id = _post_v1(client).json()["id"]
        assert _wait_terminal(client, review_id)["status"] == "completed"

        for path in (
            f"/api/reviews/{review_id}",
            f"/api/reviews/{review_id}/report",
            f"/api/reviews/{review_id}/result",
        ):
            r = client.get(path)
            assert r.status_code == 200, path
            assert SECRET not in r.text, f"{path} 把完整报告漏给了匿名用户"


# ---------------------------------------------------------------------------
# GET /api/rubric
# ---------------------------------------------------------------------------


class TestRubricEndpoint:
    def test_rubric_returns_dimensions(self, client):
        """这个端点此前 100% 500：RubricDimensionResponse 从未被导入
        （api/__init__.py 顶部那份 from app.schemas import (...) 里没有它），
        而 EvaluationService.load_rubrics 一定返回非空 dimensions（内置
        RUBRIC_SCORES 兜底），所以循环体必定执行 → NameError。
        """
        r = client.get("/api/rubric")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dimensions"], "dimensions 不该为空，否则这条测试证明不了 500 已经修好"
        first = body["dimensions"][0]
        assert first["dimension"]
        assert isinstance(first["scores"], dict) and first["scores"]
        assert isinstance(body["critical_failures"], list)


# ---------------------------------------------------------------------------
# 与评审引擎无关、但原本住在 test_v1_engine_hardening.py 里的覆盖
# ---------------------------------------------------------------------------


class TestMaterialExtractorByok:
    def test_no_resolved_key_skips_ai_never_touches_env(self, monkeypatch):
        """没解析到 key 时 AI 档直接跳过（走 fallback），即使环境变量里有 key 也不偷用。"""
        from app.services import MaterialExtractor

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-should-not-be-used")
        result = MaterialExtractor._extract_with_ai(
            "concept_review", "some text", ["一句话pitch"]
        )
        assert result is None

    def test_resolved_key_flows_into_chat_completion(self, monkeypatch):
        from unittest.mock import patch

        from app.services import MaterialExtractor
        from app.services.key_service import ResolvedKey

        calls = []

        def fake_chat(**kwargs):
            calls.append(kwargs)
            return ('{"title": "T", "materials": {"一句话pitch": "x"}}', 10, 5)

        with patch("runner.llm_client.chat_completion", side_effect=fake_chat):
            resolved = ResolvedKey(
                key="sk-extract-test",
                source="byok",
                provider="openai_compatible",
                model="deepseek-v4-pro",
                api_base="https://api.deepseek.com",
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
    而下方「人数不足补人」分支也用 random.sample。Python 的函数级名字绑定让 random
    在整个函数里都是局部名，正常路径上它从未被赋值。
    """

    def test_panel_selection_does_not_crash(self):
        from app.services import PersonaService

        for task_type in ("pitch_review", "product_feedback_review", "pricing_page_review"):
            panel = PersonaService.select_panel_by_mode(
                task_type=task_type,
                mode="standard",
                persona_pack="game-core",
                selected_personas=None,
            )
            assert panel, f"{task_type} 选不出任何人格"

    def test_pitch_review_runs_end_to_end(self, client, db, anon_key, monkeypatch):
        calls = []
        _patch_engine(monkeypatch, calls)

        r = _post_v1(
            client,
            task_type="pitch_review",
            artifact_bundle={
                "title": "我的创业 BP",
                "materials": [{"type": "text", "text": "AI 评审工具"}],
            },
        )
        assert r.status_code == 200, r.text
        detail = _wait_terminal(client, r.json()["id"])
        assert detail["status"] == "completed", detail.get("error_message")
        assert calls[0]["task_type"] == "pitch_review"
