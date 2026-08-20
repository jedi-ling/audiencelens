"""项目记忆层：同 project_key 的历史判断带进下一次评审。

这一层直接往**每个人格的提示词**里注入内容，所以隔离性不是"最好有"而是
硬要求：一旦串号，用户 A 未发布的产品结论会出现在用户 B 的评审上下文里。
本文件里 TestIsolation 那一组就是为这件事存在的。

另一组重点是 TestVerdictFiltering——被真人测试回填为 miss 的判断不再带入。
这条是整个判断闭环唯一真正"付钱"的地方：没有它，回填按钮就只是给校准曲线
喂数据的可选动作，没人有理由去点。
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Judgment, Outcome, Review
from app.services import project_memory_service as pms


def _mk_review(db, user_id, project_key, **kw):
    r = Review(
        user_id=user_id,
        task_type="concept_review",
        artifact_bundle={"materials": [{"type": "text", "text": "x"}]},
        project_key=project_key,
        status="completed",
        **kw,
    )
    db.add(r)
    db.flush()
    return r


def _mk_judgment(db, review, claim, severity=None, verdict=None, days_ago=0):
    j = Judgment(
        review_id=review.id,
        user_id=review.user_id,
        claim=claim,
        severity=severity,
        predicted_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(j)
    db.flush()
    if verdict is not None:
        db.add(Outcome(judgment_id=j.id, verdict=verdict))
    db.flush()
    return j


class TestIsolation:
    """跨用户绝不串号——这一层写进的是别人的提示词，串了就是数据泄漏。"""

    def test_other_users_judgments_never_carried(self, db):
        # 两个用户用了**完全相同**的 project_key。project_key 是自由文本，
        # 撞名不是边缘情况，是必然会发生的事（"官网改版""定价页"）。
        mine = _mk_review(db, "u-mem-a", "同名项目")
        theirs = _mk_review(db, "u-mem-b", "同名项目")
        _mk_judgment(db, mine, "我自己的历史判断")
        _mk_judgment(db, theirs, "别人的机密结论")
        db.commit()

        material, meta = pms.build_project_memory(db, "u-mem-a", "同名项目")

        assert material is not None
        assert "我自己的历史判断" in material["text"]
        assert "别人的机密结论" not in material["text"]
        assert meta["carried"] == 1

    def test_anonymous_identity_gets_no_memory(self, db):
        """关掉认证时所有访客共用 "anonymous"，带记忆等于互相读提示词。"""
        r = _mk_review(db, "anonymous", "匿名项目")
        _mk_judgment(db, r, "匿名留下的判断")
        db.commit()

        material, meta = pms.build_project_memory(db, "anonymous", "匿名项目")

        assert material is None
        assert meta["carried"] == 0
        assert meta["reason"] == "anonymous_identity"

    def test_different_project_key_not_carried(self, db):
        a = _mk_review(db, "u-mem-c", "项目甲")
        b = _mk_review(db, "u-mem-c", "项目乙")
        _mk_judgment(db, a, "甲的判断")
        _mk_judgment(db, b, "乙的判断")
        db.commit()

        material, _ = pms.build_project_memory(db, "u-mem-c", "项目甲")
        assert "甲的判断" in material["text"]
        assert "乙的判断" not in material["text"]


class TestVerdictFiltering:
    """回填结果决定带不带——闭环真正的收口。"""

    def test_miss_is_excluded(self, db):
        r = _mk_review(db, "u-mem-d", "验证项目")
        _mk_judgment(db, r, "被证伪的判断", verdict="miss")
        _mk_judgment(db, r, "还没验证的判断")
        db.commit()

        material, meta = pms.build_project_memory(db, "u-mem-d", "验证项目")

        assert "被证伪的判断" not in material["text"]
        assert "还没验证的判断" in material["text"]
        assert meta["carried"] == 1

    @pytest.mark.parametrize("verdict", ["hit", "partial", "unknown"])
    def test_non_miss_verdicts_still_carried(self, db, verdict):
        """只有 miss 是"这事没发生"。hit 说明问题真实存在（是否已修是另一回事），
        partial / unknown 都还没定论，都该继续带。"""
        key = f"验证项目-{verdict}"
        r = _mk_review(db, "u-mem-e", key)
        _mk_judgment(db, r, f"{verdict} 的判断", verdict=verdict)
        db.commit()

        material, meta = pms.build_project_memory(db, "u-mem-e", key)
        assert material is not None
        assert f"{verdict} 的判断" in material["text"]
        assert meta["carried"] == 1

    def test_miss_on_newest_copy_kills_the_whole_claim(self, db):
        """**多代理审计实测复现的真 bug 的回归测试。**

        同一句 claim 在多次评审里被反复提出（这是常态，注释里自己写的），
        用户在**最新**那条上回填了 miss。第一版实现是"先过滤 miss、再去重"：
        最新那条先被剔除，更旧的未验证副本顶上来成为去重赢家，于是被证伪的
        判断照样进了每个人格的提示词——而且顶着"尚未验证"的标签，因为那条
        旧行确实没有 Outcome。设计红线第 1 条被静默绕过。

        现在的顺序是"先去重（保留最新）、再过滤 miss"，所以一句 claim 带不带，
        只看它最新那条的回填结论。
        """
        key = "红线绕过项目"
        old = _mk_review(db, "u-mem-miss", key)
        new = _mk_review(db, "u-mem-miss", key)
        _mk_judgment(db, old, "CLAIM-X", days_ago=5)                 # 旧副本，未验证
        _mk_judgment(db, new, "CLAIM-X", days_ago=1, verdict="miss")  # 最新，已证伪
        db.commit()

        material, meta = pms.build_project_memory(db, "u-mem-miss", key)

        assert material is None, (
            "被证伪的判断经由同文旧副本重新注入了提示词——"
            f"实际带入 {meta.get('carried')} 条：{(material or {}).get('text')}"
        )
        assert meta["carried"] == 0

    def test_miss_on_older_copy_does_not_kill_a_still_open_claim(self, db):
        """反向：旧副本被判 miss、最新那条仍未验证时，问题还是要带入。
        否则一次误判会让这条问题永远消失。"""
        key = "反向项目"
        old = _mk_review(db, "u-mem-miss2", key)
        new = _mk_review(db, "u-mem-miss2", key)
        _mk_judgment(db, old, "CLAIM-Y", days_ago=5, verdict="miss")
        _mk_judgment(db, new, "CLAIM-Y", days_ago=1)
        db.commit()

        material, meta = pms.build_project_memory(db, "u-mem-miss2", key)
        assert meta["carried"] == 1
        assert "CLAIM-Y" in material["text"]

    def test_verified_verdict_is_labelled_in_text(self, db):
        """已被真人测试确认的判断，权重明显不同于未验证的，提示词里必须区分。"""
        r = _mk_review(db, "u-mem-f", "标注项目")
        _mk_judgment(db, r, "确认发生过的问题", verdict="hit")
        _mk_judgment(db, r, "还没人验过的问题")
        db.commit()

        material, _ = pms.build_project_memory(db, "u-mem-f", "标注项目")
        assert "真人测试已确认发生" in material["text"]
        assert "尚未验证" in material["text"]


class TestShaping:
    def test_no_project_key_is_noop(self, db):
        material, meta = pms.build_project_memory(db, "u-mem-g", None)
        assert material is None
        assert meta["reason"] == "no_project_key"

        material, meta = pms.build_project_memory(db, "u-mem-g", "   ")
        assert material is None
        assert meta["reason"] == "no_project_key"

    def test_no_history_is_noop(self, db):
        material, meta = pms.build_project_memory(db, "u-mem-h", "空项目")
        assert material is None
        assert meta["reason"] == "no_open_judgments"

    def test_capped_and_severity_ordered(self, db):
        """名额有限时先带严重的——材料会进每个人格的提示词，是按人数付费的。"""
        r = _mk_review(db, "u-mem-i", "超量项目")
        for i in range(pms.MAX_CARRIED_JUDGMENTS + 5):
            _mk_judgment(db, r, f"低危问题{i}", severity="low")
        _mk_judgment(db, r, "致命问题", severity="critical")
        db.commit()

        material, meta = pms.build_project_memory(db, "u-mem-i", "超量项目")

        assert meta["carried"] == pms.MAX_CARRIED_JUDGMENTS
        assert "致命问题" in material["text"]

    def test_repeated_claim_deduped(self, db):
        """同一个问题连着三版都被提出来，恰恰说明它还没修——但只该占一个名额，
        不该把 8 条名额全填成同一句话的历次副本。"""
        key = "复读项目"
        for n in range(3):
            r = _mk_review(db, "u-mem-j", key)
            _mk_judgment(db, r, "移动端适配缺失", days_ago=3 - n)
        db.commit()

        material, meta = pms.build_project_memory(db, "u-mem-j", key)
        assert meta["carried"] == 1
        assert material["text"].count("移动端适配缺失") == 1

    def test_exclude_review_id_drops_own_judgments(self, db):
        """自己的判断不能带进自己——否则重跑同一次评审会自我循环。"""
        r = _mk_review(db, "u-mem-k", "自排除项目")
        _mk_judgment(db, r, "本次自己的判断")
        db.commit()

        material, _ = pms.build_project_memory(
            db, "u-mem-k", "自排除项目", exclude_review_id=r.id
        )
        assert material is None

    def test_material_is_flagged_as_context_not_evidence(self, db):
        """带 is_context 的材料不参与证据类型统计——见 evidence_precheck。
        漏了这个标记，历史材料会被当成"万能证据"，把整道证据预检关掉。"""
        r = _mk_review(db, "u-mem-l", "标记项目")
        _mk_judgment(db, r, "某条判断")
        db.commit()

        material, _ = pms.build_project_memory(db, "u-mem-l", "标记项目")
        assert material["is_context"] is True
        assert material["type"] != "text"

    def test_prompt_forbids_citing_history_as_direct_evidence(self, db):
        """历史结论不是本次材料。提示词必须明说，否则人格会拿上一版的结论
        当 direct 证据引用——validator 拦不住（它只比对材料原文，而历史
        确实在材料里），只能靠指令约束。"""
        r = _mk_review(db, "u-mem-m", "口径项目")
        _mk_judgment(db, r, "某条判断")
        db.commit()

        material, _ = pms.build_project_memory(db, "u-mem-m", "口径项目")
        assert "direct" in material["text"]
        assert "背景信息" in material["text"]


class TestBundleAttachment:
    """attach_to_bundle 是两条评审链路（v1 / v2）唯一的接入点。"""

    def test_no_project_key_leaves_bundle_untouched(self, db):
        """没开项目时连元数据都不该挂。

        这条是踩出来的：第一版实现无条件挂 project_memory 元数据，
        test_v1_v2_convergence::test_engine_receives_identical_arguments 立刻红了
        ——v2 挂了、v1 没挂，两个端点交给引擎的 bundle 不再逐字段相同。
        顺带还有个成本问题：那段 {"carried":0,...} 会被写进**每一条**
        Review.artifact_bundle 永久留着，而它什么信息都不提供。
        """
        original = {"materials": [{"type": "text", "text": "正文"}]}
        out = pms.attach_to_bundle(db, original, "u-mem-o", None)

        assert out == original
        assert "project_memory" not in out

    def test_project_key_without_history_still_reports_reason(self, db):
        """用户明确开了项目却没拿到记忆时，reason 才有信息量。"""
        out = pms.attach_to_bundle(
            db, {"materials": [{"type": "text", "text": "正文"}]}, "u-mem-p", "全新项目"
        )
        assert out["project_memory"]["carried"] == 0
        assert out["project_memory"]["reason"] == "no_open_judgments"
        assert len(out["materials"]) == 1  # 没有历史就绝不插空材料占 token

    def test_history_appended_after_current_materials(self, db):
        """本次材料必须排在历史前面——人格先读要评的东西，历史是补充。"""
        r = _mk_review(db, "u-mem-q", "顺序项目")
        _mk_judgment(db, r, "历史判断")
        db.commit()

        out = pms.attach_to_bundle(
            db, {"materials": [{"type": "text", "text": "本次正文"}]}, "u-mem-q", "顺序项目"
        )

        assert len(out["materials"]) == 2
        assert out["materials"][0]["text"] == "本次正文"
        assert out["materials"][-1]["is_context"] is True
        assert out["project_memory"]["carried"] == 1

    def test_does_not_mutate_caller_bundle(self, db):
        r = _mk_review(db, "u-mem-r", "不改原件项目")
        _mk_judgment(db, r, "历史判断")
        db.commit()

        original = {"materials": [{"type": "text", "text": "正文"}]}
        pms.attach_to_bundle(db, original, "u-mem-r", "不改原件项目")

        assert len(original["materials"]) == 1
        assert "project_memory" not in original


class TestQueryCost:
    """这段代码跑在**评审创建的同步请求路径**上（还是 async def，阻塞事件循环）。
    查询次数必须是有界的常数，不能随项目历史线性增长。"""

    def _count_sql(self, db, fn):
        from sqlalchemy import event

        engine = db.get_bind()
        n = []

        def _before(conn, cursor, statement, params, context, many):
            n.append(statement)

        event.listen(engine, "before_cursor_execute", _before)
        try:
            fn()
        finally:
            event.remove(engine, "before_cursor_execute", _before)
        return n

    def test_query_count_is_constant_regardless_of_history_size(self, db):
        """第一版是 2 × (1 + N)：build_project_memory 把整个查询跑两遍，
        且 r.outcome 是 lazy 关系，逐行触发一次 SELECT。多代理审计实测
        800 条判断 = 1602 条 SQL / 约 1 秒。现在是 contains_eager + 单次查询。"""
        key = "成本项目"
        r = _mk_review(db, "u-mem-cost", key)
        for i in range(40):
            j = _mk_judgment(db, r, f"问题{i}", severity="medium")
            if i % 2 == 0:
                db.add(Outcome(judgment_id=j.id, verdict="hit"))
        db.commit()
        db.expire_all()

        stmts = self._count_sql(
            db, lambda: pms.build_project_memory(db, "u-mem-cost", key)
        )

        assert len(stmts) <= 2, (
            f"40 条历史判断发出了 {len(stmts)} 条 SQL——N+1 或重复查询回来了：\n"
            + "\n".join(s[:120] for s in stmts[:12])
        )

    def test_no_project_key_does_not_touch_the_database(self, db):
        """绝大多数评审请求没有 project_key。它们一条 SQL 都不该为此多跑。"""
        stmts = self._count_sql(
            db,
            lambda: pms.attach_to_bundle(
                db, {"materials": [{"type": "text", "text": "x"}]}, "u-mem-cost2", None
            ),
        )
        assert stmts == [], f"没有 project_key 却查了库：{stmts}"


class TestInjectedMaterialsAreAttributable:
    """系统注入的材料必须能和用户提交的材料区分开。

    这一组守的是一个**先前就存在**的 bug：AskPage.openReviewConversation 取
    materials 里第一条 type=="text" 当作"用户当时说的话"，而 apply_skill_hint
    正好把技能提示插在 0 号位、type 也是 "text"——于是用了技能的历史评审点开后，
    显示的是那段系统提示词。项目记忆让这件事更值得修：注入源现在有两个了。
    """

    def test_skill_hint_is_marked_injected(self):
        from app.services import apply_skill_hint

        out = apply_skill_hint(
            {"materials": [{"type": "text", "text": "用户原话"}]}, "red_team_audience"
        )
        assert out["materials"][0]["is_injected"] is True
        assert out["materials"][1].get("is_injected") is not True

        first_real = next(
            m for m in out["materials"] if m.get("type") == "text" and not m.get("is_injected")
        )
        assert first_real["text"] == "用户原话"

    def test_skill_hint_keeps_text_type_for_evidence_precheck(self):
        """技能提示刻意**不**加 is_context：它现在的 type="text" 命中
        FREEFORM_EVIDENCE_TYPES，是部分材料包能过证据预检的原因。
        改那个是另一件事，改动前这条测试会先红。"""
        from app.services import apply_skill_hint

        out = apply_skill_hint({"materials": []}, "red_team_audience")
        assert out["materials"][0]["type"] == "text"
        assert out["materials"][0].get("is_context") is not True

    def test_memory_material_is_both_context_and_injected(self, db):
        r = _mk_review(db, "u-mem-mark", "标记项目2")
        _mk_judgment(db, r, "某条判断")
        db.commit()

        material, _ = pms.build_project_memory(db, "u-mem-mark", "标记项目2")
        assert material["is_context"] is True   # 引擎：不算证据
        assert material["is_injected"] is True  # 前端：不是用户提交的


class TestLedgerDisabled:
    def test_returns_reason_when_ledger_off(self, db, monkeypatch):
        """ledger 关掉时没有判断可带。要和"这个项目确实没历史"区分开——
        前者是部署选择，后者是数据状态，混在一起用户会以为记忆坏了。"""
        from app.config import settings

        monkeypatch.setattr(settings, "ledger_enabled", False)
        material, meta = pms.build_project_memory(db, "u-mem-n", "任意项目")
        assert material is None
        assert meta["reason"] == "ledger_disabled"


class TestEndToEndThroughApi:
    """整条链路的真实证明：第一次评审的结论，第二次评审时真的到了引擎手上。

    上面那些用例测的都是 service 层。它们全绿也不能保证接口真的接上了——
    "写了个函数但没人调"正是这个仓库反复踩过的失败形态（enable_evaluation
    被 schema 静默丢弃、project_key 从来没被读回，都是这一种）。所以这里
    走真实的 HTTP 端点，并把引擎替换成记录参数的替身，直接看它收到了什么。
    """

    def _token(self, client, email):
        client.post("/api/auth/register", json={"email": email, "password": "password123"})
        token = client.post(
            "/api/auth/login", json={"email": email, "password": "password123"}
        ).json()["token"]
        client.post(
            "/api/keys",
            json={"api_key": "sk-ant-project-memory-0123456789", "provider": "anthropic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        return token

    def test_first_reviews_findings_reach_the_second_reviews_engine_call(
        self, client, monkeypatch
    ):
        import time

        from app.config import settings

        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "ledger_enabled", True)

        calls = []

        def _fake_run_panel(**kwargs):
            calls.append(kwargs)
            return {
                "report": {
                    "meta": {"task_type": "concept_review"},
                    "executive_summary": {"release_risk": "high"},
                    "priority_fixes": [
                        {
                            "title": "新手引导超过 15 分钟",
                            "severity": "critical",
                            "why_it_matters": "试玩用户会退款",
                        }
                    ],
                    "persona_notes": [],
                },
                "markdown": "# 报告",
                "html": "<html></html>",
                "calibration": {"coverage": {"pairwise_distances": {}}},
                "simulated": False,
                "cost_summary": {
                    "total_cost": 0.1,
                    "persona_count": 1,
                    "skipped_count": 0,
                    "total_input_tokens": 100,
                    "total_output_tokens": 50,
                },
            }

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", _fake_run_panel)

        token = self._token(client, "project-memory-e2e@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        body = {
            "task_type": "concept_review",
            "persona_pack": "game-core",
            "mode": "quick",
            "project_key": "我的游戏",
            "artifact": {
                "title": "第一版",
                "materials": [{"type": "text", "text": "探索-战斗-成长"}],
            },
        }

        r1 = client.post("/api/v2/reviews", json=body, headers=headers)
        assert r1.status_code == 202, r1.text

        # 等第一次评审跑完并把预测落库，否则第二次自然读不到东西
        deadline = time.time() + 15
        rid = r1.json()["review_id"]
        while time.time() < deadline:
            if client.get(f"/api/reviews/{rid}", headers=headers).json()["status"] in (
                "completed",
                "failed",
            ):
                break
            time.sleep(0.05)

        body2 = dict(body, artifact={"title": "第二版", "materials": body["artifact"]["materials"]})
        r2 = client.post("/api/v2/reviews", json=body2, headers=headers)
        assert r2.status_code == 202, r2.text

        deadline = time.time() + 15
        rid2 = r2.json()["review_id"]
        while time.time() < deadline:
            if client.get(f"/api/reviews/{rid2}", headers=headers).json()["status"] in (
                "completed",
                "failed",
            ):
                break
            time.sleep(0.05)

        assert len(calls) == 2, f"引擎应被调用两次，实际 {len(calls)}"

        first_bundle = calls[0]["artifact_bundle"]
        second_bundle = calls[1]["artifact_bundle"]

        # 第一次没有历史可带
        assert first_bundle["project_memory"]["carried"] == 0
        assert all(m.get("is_context") is not True for m in first_bundle["materials"])

        # 第二次：第一次那条 critical 结论真的进了引擎入参
        assert second_bundle["project_memory"]["carried"] == 1
        memory = [m for m in second_bundle["materials"] if m.get("is_context") is True]
        assert len(memory) == 1, "历史材料没有进 bundle——记忆层等于没接上"
        assert "新手引导超过 15 分钟" in memory[0]["text"]
        assert "我的游戏" in memory[0]["text"]


class TestEnginePrecheckContract:
    """引擎侧的配合：is_context 材料必须被证据类型统计跳过。

    这条放在后端测试里是因为契约的两端一端在 src/runner、一端在 web/backend，
    只测单边的话，任何一边改了标记名另一边都不会红。
    """

    def test_context_material_does_not_grant_freeform_bypass(self):
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.runner.evidence_precheck import load_evidence_types

        bundle = {
            "materials": [
                {"type": "截图", "description": "一张图"},
                {
                    "type": pms.MEMORY_MATERIAL_TYPE,
                    "description": "历史",
                    "is_context": True,
                },
            ]
        }
        types = load_evidence_types(bundle)

        assert types == ["截图"]
        assert pms.MEMORY_MATERIAL_TYPE not in types

    def test_normal_materials_still_counted(self):
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.runner.evidence_precheck import load_evidence_types

        bundle = {"materials": [{"type": "text"}, {"type": "定价页"}]}
        assert load_evidence_types(bundle) == ["text", "定价页"]
