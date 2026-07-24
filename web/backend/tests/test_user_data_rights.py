"""数据自主权回归：导出我的数据 / 彻底删除我的账号。

这是"凭什么相信你不拿我的东西"唯一能被用户亲手验证的答案，所以这两条
链路的正确性要求比一般功能更高：导出不能漏、删除不能假删、也不能顺手
把别人的数据一起删了。
"""

import time

import pytest


@pytest.fixture(autouse=True)
def _cleanup_anonymous_key(db):
    yield
    from app.services import key_service

    key_service.delete_user_key(db, "anonymous")


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
    key_service.save_user_key(db, "anonymous", "sk-ant-export-test")
    r = client.post(
        "/api/v2/reviews",
        json={
            "task_type": "concept_review",
            "artifact": {"title": title, "materials": [{"type": "text", "text": "我的原始材料"}]},
            "persona_pack": "game-core",
        },
    )
    assert r.status_code == 202
    _poll(client, r.json()["job_id"])
    return r.json()["review_id"]


class TestExport:
    def test_export_includes_own_content(self, client, db, monkeypatch):
        review_id = _make_review(client, db, monkeypatch)

        data = client.get("/api/auth/me/export").json()
        assert data["export_version"] == 1
        ids = [r["id"] for r in data["reviews"]]
        assert review_id in ids
        mine = next(r for r in data["reviews"] if r["id"] == review_id)
        # 用户自己上传的原始材料是"我的东西"的核心，必须给全
        assert "我的原始材料" in str(mine["artifact_bundle"])
        assert mine["report_json"] is not None

    def test_export_never_leaks_key_plaintext(self, client, db, monkeypatch):
        """导出文件常被随手丢进下载目录/发邮件，绝不能成为密钥泄露的新渠道。"""
        _make_review(client, db, monkeypatch)

        raw = client.get("/api/auth/me/export").text
        assert "sk-ant-export-test" not in raw
        data = client.get("/api/auth/me/export").json()
        assert data["api_keys"], "应当列出 key 的元信息"
        assert all("key_ciphertext" not in k for k in data["api_keys"])

    def test_export_includes_follow_up_chat(self, client, db, monkeypatch):
        review_id = _make_review(client, db, monkeypatch)

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: ("回复内容", 5, 2))
        client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "我的追问"})

        data = client.get("/api/auth/me/export").json()
        mine = next(r for r in data["reviews"] if r["id"] == review_id)
        contents = [m["content"] for m in mine["follow_up_chat"]]
        assert "我的追问" in contents
        # 导出给本人看，不该套用匿名体验版的裁剪
        assert "回复内容" in contents


class TestDeleteAccount:
    def test_requires_exact_confirm_phrase(self, client, db, monkeypatch):
        _make_review(client, db, monkeypatch)
        r = client.post("/api/auth/me/delete", json={"confirm": "随便写点什么"})
        assert r.status_code == 400
        # 没删成——数据还在
        assert client.get("/api/auth/me/export").json()["reviews"]

    def test_deletes_content_and_reports_counts(self, client, db, monkeypatch):
        review_id = _make_review(client, db, monkeypatch)

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: ("回复", 5, 2))
        client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "追问"})

        r = client.post("/api/auth/me/delete", json={"confirm": "删除我的账号"})
        assert r.status_code == 200
        stats = r.json()["detail"]
        assert stats["reviews_deleted"] >= 1
        assert stats["api_keys_deleted"] >= 1

        # 真删了，不是假删
        from app.models import Review, ReviewChatMessage, UserApiKey

        assert db.query(Review).filter(Review.id == review_id).first() is None
        assert (
            db.query(ReviewChatMessage).filter(ReviewChatMessage.review_id == review_id).count() == 0
        )
        assert db.query(UserApiKey).filter(UserApiKey.user_id == "anonymous").count() == 0

    def test_billing_records_anonymized_not_deleted(self, client, db, monkeypatch):
        """计费流水是财务事实源，不物理删除，但要切断到人的关联——
        隐私政策必须同口径写明，假称'全部彻底删除'一查就穿帮。"""
        from app.models import UsageRecord

        _make_review(client, db, monkeypatch)
        before = db.query(UsageRecord).filter(UsageRecord.user_id == "anonymous").count()
        assert before >= 1

        client.post("/api/auth/me/delete", json={"confirm": "删除我的账号"})

        # 原 user_id 下查不到了
        assert db.query(UsageRecord).filter(UsageRecord.user_id == "anonymous").count() == 0
        # 但记录本身还在（挂在墓碑 id 下）
        tombstoned = (
            db.query(UsageRecord).filter(UsageRecord.user_id.like("deleted-%")).count()
        )
        assert tombstoned >= before

    def test_does_not_touch_other_users_data(self, client, db, monkeypatch):
        """删自己不能顺手删别人——这是删除功能最危险的失败模式。"""
        from app.models import Review

        _make_review(client, db, monkeypatch)

        other = Review(
            user_id="someone-else",
            task_type="concept_review",
            status="completed",
            artifact_bundle={"title": "别人的评审"},
        )
        db.add(other)
        db.commit()
        other_id = other.id

        client.post("/api/auth/me/delete", json={"confirm": "删除我的账号"})

        assert db.query(Review).filter(Review.id == other_id).first() is not None
