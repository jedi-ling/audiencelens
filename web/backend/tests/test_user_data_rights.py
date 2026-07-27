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
        assert data["export_version"] == 1
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
