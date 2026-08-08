"""数据自主权回归：导出我的数据 / 彻底删除我的账号。

这是"凭什么相信你不拿我的东西"唯一能被用户亲手验证的答案，所以这两条
链路的正确性要求比一般功能更高：导出不能漏、删除不能假删、也不能顺手
把别人的数据一起删了。

## 这套测试为什么全部重写过（重要）

初版把两个接口全部按**匿名身份**测，而匿名恰恰是唯一一条会出人命的路径：
AL_AUTH_ENABLED=false（默认值）时每个请求都拿到同一个共享
settings.anonymous_user_id，全实例评审的 user_id 也都是它，于是
delete_user_data(db, "anonymous") 匹配到的是**全库所有人的数据**。
任何访客不用登录不用密码就能清空整个实例。

初版里确实有一个叫 test_does_not_touch_other_users_data 的用例，但它
造的"别人"用了 user_id="someone-else" —— 而在默认形态下真正的"别人"
根本不长那样，所有人都叫 anonymous。**测试覆盖了一个不存在的威胁模型，
于是一路绿灯地放行了漏洞。**

所以现在：正常路径一律用真实注册账号测（"我的数据"只有在有独立身份时
才成立），并补上 TestAnonymousIsRejected 直接盯住那条真实威胁。
"""

import time
import uuid

import pytest


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    """开鉴权。数据自主权的正常路径只有在"有独立身份"时才成立。"""
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


@pytest.fixture
def user_client(client):
    """注册一个真实账号并带上它的 token —— 之后所有请求都是"这个人"发的。

    邮箱每次唯一：库在同一个测试模块内是共享的，固定邮箱会在第二个用例
    就撞上"该邮箱已注册"。
    """
    email = f"owner-{uuid.uuid4().hex[:12]}@example.com"
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    client.headers.update({"Authorization": f"Bearer {payload['token']}"})
    client.user_id = payload["user"]["id"]
    client.password = "password123"
    return client


def _fake_result():
    return {
        "report": {
            "executive_summary": {"primary_recommendation": "观望"},
            "priority_fixes": [],
            "persona_notes": [{"persona_id": "P01", "persona_name": "林岚", "primary_stance": "观望"}],
        },
        "markdown": "# r",
        "html": "",
        "calibration": {},
        "simulated": False,
        "cost_summary": {
            "total_cost": 0.1,
            "persona_count": 1,
            "skipped_count": 0,
            "total_input_tokens": 100,
            "total_output_tokens": 50,
        },
    }


def _poll(client, job_id, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.1)
    raise AssertionError("job 未到终态")


def _make_review(client, db, monkeypatch, title="导出验证"):
    from app.services import key_service

    import runner.cli

    monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
    key_service.save_user_key(db, client.user_id, "sk-ant-export-test")
    r = client.post(
        "/api/v2/reviews",
        json={
            "task_type": "concept_review",
            "artifact": {"title": title, "materials": [{"type": "text", "text": "我的原始材料"}]},
            "persona_pack": "game-core",
        },
    )
    assert r.status_code == 202, r.text
    _poll(client, r.json()["job_id"])
    return r.json()["review_id"]


def _seed_persona_output(db, review_id, persona_id="P01"):
    """造一条带内容的人格输出——伦理报告是按它逐条算出来的。"""
    from app.models import PersonaOutput

    po = PersonaOutput(
        review_id=review_id,
        persona_id=persona_id,
        persona_name="林岚",
        status="completed",
        output_json={"key_points": ["因为她是女性，所以只关心故事"]},
    )
    db.add(po)
    db.commit()
    return po


class TestAnonymousIsRejected:
    """匿名身份不是"某个人"，是所有人共用的桶——这两个接口必须拒绝它。

    这一组是上面文档注释里那个漏洞的直接回归，删掉任何一条都等于把洞放回去。
    """

    @pytest.fixture(autouse=True)
    def _auth_off(self, monkeypatch):
        """覆盖掉 _auth_on：这里要复现的正是**默认配置**（不开鉴权）下的形态。"""
        from app.config import settings

        monkeypatch.setattr(settings, "auth_enabled", False)
        yield

    def test_anonymous_cannot_export(self, client):
        r = client.get("/api/auth/me/export")
        assert r.status_code == 400
        # 不能把别人的材料原文吐出来
        assert "我的原始材料" not in r.text

    def test_anonymous_cannot_delete(self, client):
        r = client.post("/api/auth/me/delete", json={"confirm": "删除我的账号"})
        assert r.status_code == 400

    def test_anonymous_delete_does_not_wipe_the_instance(self, client, db, monkeypatch):
        """这是那个漏洞的核心场景：默认配置下所有评审的 user_id 都是 anonymous，
        一次匿名删号请求曾经会把整个实例清空。"""
        from app.config import settings
        from app.models import Review

        # 造几条"别人的"评审——注意它们的 user_id 就是共享的 anonymous，
        # 这才是默认形态下"别人"真正的样子（初版测试用 someone-else，模型错了）
        ids = []
        for i in range(3):
            rv = Review(
                user_id=settings.anonymous_user_id,
                task_type="concept_review",
                status="completed",
                artifact_bundle={"title": f"其他访客的评审{i}"},
            )
            db.add(rv)
            db.commit()
            ids.append(rv.id)

        r = client.post("/api/auth/me/delete", json={"confirm": "删除我的账号"})
        assert r.status_code == 400, "匿名删号必须被拒绝"

        for rid in ids:
            assert (
                db.query(Review).filter(Review.id == rid).first() is not None
            ), "其他访客的评审被删掉了——实例级数据销毁漏洞回归了"


class TestExport:
    def test_export_includes_own_content(self, user_client, db, monkeypatch):
        review_id = _make_review(user_client, db, monkeypatch)

        data = user_client.get("/api/auth/me/export").json()
        assert data["export_version"] == 2
        ids = [r["id"] for r in data["reviews"]]
        assert review_id in ids
        mine = next(r for r in data["reviews"] if r["id"] == review_id)
        # 用户自己上传的原始材料是"我的东西"的核心，必须给全
        assert "我的原始材料" in str(mine["artifact_bundle"])
        assert mine["report_json"] is not None

    def test_export_never_leaks_key_plaintext(self, user_client, db, monkeypatch):
        """导出文件常被随手丢进下载目录/发邮件，绝不能成为密钥泄露的新渠道。"""
        _make_review(user_client, db, monkeypatch)

        raw = user_client.get("/api/auth/me/export").text
        assert "sk-ant-export-test" not in raw
        data = user_client.get("/api/auth/me/export").json()
        assert data["api_keys"], "应当列出 key 的元信息"
        assert all("key_ciphertext" not in k for k in data["api_keys"])

    def test_export_only_returns_my_own_reviews(self, user_client, db, monkeypatch):
        """导出是"我的"数据，不是"全部"数据——别人的评审一条都不能出现。"""
        from app.models import Review

        _make_review(user_client, db, monkeypatch)

        other = Review(
            user_id="someone-else",
            task_type="concept_review",
            status="completed",
            artifact_bundle={"title": "别人的机密项目"},
        )
        db.add(other)
        db.commit()

        raw = user_client.get("/api/auth/me/export").text
        assert "别人的机密项目" not in raw

    def test_export_includes_follow_up_chat(self, user_client, db, monkeypatch):
        review_id = _make_review(user_client, db, monkeypatch)

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: ("回复内容", 5, 2))
        user_client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "我的追问"})

        data = user_client.get("/api/auth/me/export").json()
        mine = next(r for r in data["reviews"] if r["id"] == review_id)
        contents = [m["content"] for m in mine["follow_up_chat"]]
        assert "我的追问" in contents
        # 导出给本人看，不该套用匿名体验版的裁剪
        assert "回复内容" in contents


class TestExportCoverage:
    """钉住"导出覆盖了哪些表"。

    为什么要有这一组：导出功能腐化的方式是静默的。加表的人只关心新功能，
    不会想起隐私页那句"删号前先导出留个备份"；而漏了一张表，导出照样返回 200，
    只是少了几类内容——用户照做之后删号，那些内容永久消失且从未出现在备份里。
    历史上这里就漏了判断留档、反馈、伦理报告、评估、上传图片、兑换与额度流水
    六大类，而当时的测试全绿。
    """

    def test_every_table_is_either_exported_or_explicitly_exempt(self):
        """新加一张表就必须在这里做一次显式决定，不能默默漏掉。

        这条断言的价值全在"新表默认是红的"：如果只断言
        EXPORTED_TABLES ⊆ 全部表，加表的人什么都不会察觉。
        """
        from app.models import Base
        from app.services import user_data_service as uds

        all_tables = set(Base.metadata.tables)
        declared = set(uds.EXPORTED_TABLES) | set(uds.EXPORT_EXEMPT_TABLES)

        undeclared = all_tables - declared
        assert not undeclared, (
            f"这些表既没进导出也没登记豁免：{sorted(undeclared)}。"
            "如果是用户内容就补进 export_user_data 并加入 EXPORTED_TABLES；"
            "如果不该导出，请在 EXPORT_EXEMPT_TABLES 里写明理由。"
        )
        stale = declared - all_tables
        assert not stale, f"这些表已不存在，请从声明里删掉：{sorted(stale)}"

    def test_exported_tables_actually_appear_in_the_payload(
        self, user_client, db, monkeypatch
    ):
        """光有名单不算数——每一类都要能在真实导出件里找到自己那行数据。

        用"造一行 → 断言它出现在导出里"的形式，而不是断言 key 存在：
        后者在实现退化成 `"judgments": []` 时依然是绿的，等于什么都没保证。
        """
        from app.models import (
            CdkCode,
            CdkRedemption,
            CreditLedger,
            EthicsReport,
            EvaluationResult,
            EvaluationScorecard,
            FeedbackAdoption,
            Judgment,
            Outcome,
            ReviewFeedback,
            UploadedFile,
        )

        review_id = _make_review(user_client, db, monkeypatch)
        uid = user_client.user_id

        judgment = Judgment(
            review_id=review_id, user_id=uid, claim="判断留档的独特内容",
            severity="high", confidence=0.8,
        )
        db.add(judgment)
        db.commit()
        db.add(Outcome(judgment_id=judgment.id, verdict="hit", note="事后验证的独特内容"))

        fb = ReviewFeedback(review_id=review_id, user_id=uid, useful=True, note="反馈的独特内容")
        db.add(fb)
        db.commit()
        db.add(FeedbackAdoption(feedback_id=fb.id, fix_title="被采纳建议的独特内容"))

        db.add(EvaluationResult(
            review_id=review_id, dimension="input_grounding", score=3,
            passed=True, details="评估细节的独特内容",
        ))
        db.add(EvaluationScorecard(review_id=review_id, overall_score=88, passed=True))
        db.add(EthicsReport(
            review_id=review_id, persona_id="P01", passed=False, score=40,
            violations_json=[{"quote": "伦理摘录的独特内容"}],
        ))
        db.add(UploadedFile(
            user_id=uid, filename="上传图片的独特内容.png",
            media_type="image/png", ext=".png", byte_size=123,
        ))

        code = CdkCode(code="EXPORT-COVERAGE-CODE", credits=5)
        db.add(code)
        db.commit()
        db.add(CdkRedemption(code_id=code.id, user_id=uid, credits=5))
        db.add(CreditLedger(user_id=uid, delta=5, reason="cdk_redeem", ref_id=code.id))
        db.commit()

        raw = user_client.get("/api/auth/me/export").text
        for needle in [
            "判断留档的独特内容",
            "事后验证的独特内容",
            "反馈的独特内容",
            "被采纳建议的独特内容",
            "评估细节的独特内容",
            "伦理摘录的独特内容",
            "上传图片的独特内容.png",
            "EXPORT-COVERAGE-CODE",
        ]:
            assert needle in raw, f"导出件里找不到 {needle}"

        data = user_client.get("/api/auth/me/export").json()
        mine = next(r for r in data["reviews"] if r["id"] == review_id)
        assert mine["evaluation"]["overall_score"] == 88
        assert data["credit_ledger"], "额度流水一条都没有"
        # 评审参数：没有它们，导出件无法回答"这次是怎么跑的"
        assert "persona_pack" in mine and "selected_personas" in mine

    def test_export_still_hides_credential_material(self, user_client, db, monkeypatch):
        """补齐导出范围不能顺手把凭据也导出去——auth_tokens 是明确豁免的。"""
        from app.services import user_data_service as uds

        assert "auth_tokens" in uds.EXPORT_EXEMPT_TABLES
        assert "auth_tokens" not in uds.EXPORTED_TABLES

        _make_review(user_client, db, monkeypatch)
        data = user_client.get("/api/auth/me/export").json()
        assert "auth_tokens" not in data


class TestDeleteAccount:
    def test_requires_exact_confirm_phrase(self, user_client, db, monkeypatch):
        _make_review(user_client, db, monkeypatch)
        r = user_client.post(
            "/api/auth/me/delete",
            json={"confirm": "随便写点什么", "password": user_client.password},
        )
        assert r.status_code == 400
        # 没删成——数据还在
        assert user_client.get("/api/auth/me/export").json()["reviews"]

    def test_requires_correct_password(self, user_client, db, monkeypatch):
        """光有 token 不够——token 可能是被人捡到的。"""
        _make_review(user_client, db, monkeypatch)
        r = user_client.post(
            "/api/auth/me/delete",
            json={"confirm": "删除我的账号", "password": "wrong-password"},
        )
        assert r.status_code == 401
        assert user_client.get("/api/auth/me/export").json()["reviews"]

    def test_deletes_content_and_reports_counts(self, user_client, db, monkeypatch):
        review_id = _make_review(user_client, db, monkeypatch)
        uid = user_client.user_id

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: ("回复", 5, 2))
        user_client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "追问"})

        r = user_client.post(
            "/api/auth/me/delete",
            json={"confirm": "删除我的账号", "password": user_client.password},
        )
        assert r.status_code == 200, r.text
        stats = r.json()["detail"]
        assert stats["reviews_deleted"] >= 1
        assert stats["api_keys_deleted"] >= 1

        # 真删了，不是假删
        from app.models import Review, ReviewChatMessage, UserApiKey

        assert db.query(Review).filter(Review.id == review_id).first() is None
        assert (
            db.query(ReviewChatMessage).filter(ReviewChatMessage.review_id == review_id).count() == 0
        )
        assert db.query(UserApiKey).filter(UserApiKey.user_id == uid).count() == 0

    def test_billing_records_anonymized_not_deleted(self, user_client, db, monkeypatch):
        """计费流水是财务事实源，不物理删除，但要切断到人的关联——
        隐私政策必须同口径写明，假称'全部彻底删除'一查就穿帮。"""
        from app.models import UsageRecord

        _make_review(user_client, db, monkeypatch)
        uid = user_client.user_id
        before = db.query(UsageRecord).filter(UsageRecord.user_id == uid).count()
        assert before >= 1

        user_client.post(
            "/api/auth/me/delete",
            json={"confirm": "删除我的账号", "password": user_client.password},
        )

        # 原 user_id 下查不到了
        assert db.query(UsageRecord).filter(UsageRecord.user_id == uid).count() == 0
        # 但记录本身还在（挂在墓碑 id 下）
        tombstoned = db.query(UsageRecord).filter(UsageRecord.user_id.like("deleted-%")).count()
        assert tombstoned >= before

    def test_ethics_reports_are_deleted_with_the_account(self, user_client, db, monkeypatch):
        """伦理报告的 violations_json 里含用户内容摘录 —— 删号后必须一行不剩。

        这条曾经是隐私政策的漏网之鱼：EthicsReport 没有归属列，写进去就
        再也删不掉，账号删了摘录还留在库里。
        """
        from app.models import EthicsReport, PersonaOutput
        from app.services.ethics_service import EthicsService

        review_id = _make_review(user_client, db, monkeypatch)
        _seed_persona_output(db, review_id, "P90")
        EthicsService.get_ethics_reports_for_review(db, review_id)
        assert db.query(EthicsReport).filter(EthicsReport.review_id == review_id).count() >= 1

        r = user_client.post(
            "/api/auth/me/delete",
            json={"confirm": "删除我的账号", "password": user_client.password},
        )
        assert r.status_code == 200, r.text
        assert r.json()["detail"]["ethics_reports_deleted"] >= 1

        db.expire_all()
        assert db.query(EthicsReport).filter(EthicsReport.review_id == review_id).count() == 0
        assert db.query(PersonaOutput).filter(PersonaOutput.review_id == review_id).count() == 0

    def test_does_not_touch_other_users_data(self, user_client, db, monkeypatch):
        """删自己不能顺手删别人——这是删除功能最危险的失败模式。"""
        from app.models import Review

        _make_review(user_client, db, monkeypatch)

        other = Review(
            user_id="someone-else",
            task_type="concept_review",
            status="completed",
            artifact_bundle={"title": "别人的评审"},
        )
        db.add(other)
        db.commit()
        other_id = other.id

        user_client.post(
            "/api/auth/me/delete",
            json={"confirm": "删除我的账号", "password": user_client.password},
        )

        assert db.query(Review).filter(Review.id == other_id).first() is not None


class TestEthicsReadIsSideEffectFree:
    """GET 只读接口不该有写副作用。

    此前 GET /api/evaluations/{id}/ethics 每调一次就把该评审下每个人格
    重新算一遍并 add+commit：前端每打开一次伦理页写 N 行，刷 10 次 10×N 行。
    """

    def test_repeated_get_does_not_grow_the_table(self, user_client, db, monkeypatch):
        from app.models import EthicsReport

        review_id = _make_review(user_client, db, monkeypatch)
        _seed_persona_output(db, review_id, "P90")
        _seed_persona_output(db, review_id, "P91")

        def _rows():
            db.expire_all()
            return db.query(EthicsReport).filter(EthicsReport.review_id == review_id).count()

        first = user_client.get(f"/api/evaluations/{review_id}/ethics")
        assert first.status_code == 200, first.text
        assert {"P90", "P91"} <= {x["persona_id"] for x in first.json()}
        after_first = _rows()
        assert after_first == len(first.json())

        for _ in range(3):
            r = user_client.get(f"/api/evaluations/{review_id}/ethics")
            assert r.status_code == 200
            # 结果本身也要稳定：同样两条，id 不变（不是每次新造一份）
            assert [x["persona_id"] for x in r.json()] == [x["persona_id"] for x in first.json()]
            assert [x["id"] for x in r.json()] == [x["id"] for x in first.json()]

        assert _rows() == after_first, "只读接口仍在写库——幂等回归失效了"

    def test_new_persona_output_still_gets_evaluated(self, user_client, db, monkeypatch):
        """幂等不等于"算一次就再也不算"：后来才补上的人格输出仍要被评估。"""
        from app.models import EthicsReport

        review_id = _make_review(user_client, db, monkeypatch)
        _seed_persona_output(db, review_id, "P90")
        before = user_client.get(f"/api/evaluations/{review_id}/ethics").json()
        assert "P91" not in {x["persona_id"] for x in before}

        _seed_persona_output(db, review_id, "P91")
        body = user_client.get(f"/api/evaluations/{review_id}/ethics").json()
        assert {"P90", "P91"} <= {x["persona_id"] for x in body}
        assert len(body) == len(before) + 1
        db.expire_all()
        assert (
            db.query(EthicsReport).filter(EthicsReport.review_id == review_id).count() == len(body)
        )

    def test_legacy_rows_without_review_id_do_not_break_the_endpoint(
        self, user_client, db, monkeypatch
    ):
        """老库里残留的无归属行（review_id 为空）不能让接口崩，也不能被误当成
        某个评审的结果返回。"""
        from app.models import EthicsReport

        review_id = _make_review(user_client, db, monkeypatch)
        _seed_persona_output(db, review_id, "P90")

        legacy = EthicsReport(
            review_id=None,
            persona_id="P90",
            passed=False,
            score=0,
            violations_json=[{"severity": "high", "rule": "legacy", "detail": "老数据"}],
            stereotype_risk="high",
        )
        db.add(legacy)
        db.commit()

        r = user_client.get(f"/api/evaluations/{review_id}/ethics")
        assert r.status_code == 200, r.text
        assert legacy.id not in {x["id"] for x in r.json()}, "无归属的老行被当成了本评审的结果"
        assert "P90" in {x["persona_id"] for x in r.json()}


class TestEthicsMigration:
    def test_migration_is_repeatable_and_purges_orphans(self, tmp_path):
        """手写迁移必须重复执行安全；老库（无 review_id 列 + 孤儿行）能升级。"""
        import sqlalchemy
        from sqlalchemy import text

        from app import db as db_module

        db_file = tmp_path / "legacy.sqlite"
        old_engine = sqlalchemy.create_engine(
            f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
        )
        with old_engine.connect() as conn:
            # 老形态：ethics_reports 没有 review_id 列
            conn.execute(text("CREATE TABLE reviews (id VARCHAR PRIMARY KEY)"))
            conn.execute(
                text(
                    "CREATE TABLE ethics_reports ("
                    "id VARCHAR PRIMARY KEY, persona_id VARCHAR, passed BOOLEAN, "
                    "score INTEGER, violations_json TEXT, stereotype_risk VARCHAR, "
                    "created_at DATETIME)"
                )
            )
            for i in range(3):
                conn.execute(
                    text(
                        "INSERT INTO ethics_reports (id, persona_id, violations_json) "
                        "VALUES (:i, 'P01', '[]')"
                    ),
                    {"i": f"legacy-{i}"},
                )
            conn.commit()
        old_engine.dispose()

        engine = sqlalchemy.create_engine(
            f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
        )
        original = db_module.engine
        db_module.engine = engine
        try:
            db_module._legacy_migrations()
            with engine.connect() as conn:
                cols = {
                    r[1] for r in conn.execute(text("PRAGMA table_info(ethics_reports)")).fetchall()
                }
                assert "review_id" in cols
                # 孤儿行含用户内容摘录却无法归属、无法按承诺删除——迁移时清掉
                assert conn.execute(text("SELECT COUNT(*) FROM ethics_reports")).scalar() == 0

            # 再跑一次不能炸（重复执行安全）
            db_module._legacy_migrations()
            db_module._legacy_migrations()
        finally:
            db_module.engine = original
            engine.dispose()
