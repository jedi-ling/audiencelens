"""后台第二批端点：运营健康、任务聚合与运维操作、CDK 兑换记录、用户详情。

这批端点跟 test_admin.py 里那批的性质不同：那批大多是"把一张表读出来"，
这批带真正的业务判断（分位数、状态机、跨表核对），所以边界要单独钉。

重点守三件事：
  1. 状态机不能被绕过——cancel/force-fail 对 running 与终态的处理是有意为之的，
     不是随手写的 if。谁把它改松了（比如让 cancel 也能"取消"running），
     UI 上就会出现"已取消"但线程还在烧钱的假象。
  2. 用户详情不许漏密文。api_keys 只回 key_masked，这条要有反向断言。
  3. CDK 兑换记录要能暴露"码用掉了但次数没到账"——那正是它存在的理由。
"""

import pytest

from app.config import settings

ADMIN_TOKEN = "test-admin-token-ops"


@pytest.fixture(autouse=True)
def _cleanup(db):
    """本文件造的 Job/审计行都清掉——审计日志有独立断言的用例会自己数条数，
    留着上一个用例的残留会让那些断言变成薛定谔的。"""
    from app.models import AdminAuditLog, Job

    yield
    db.query(Job).filter(Job.ref_id.like("ops-%")).delete(synchronize_session=False)
    db.query(AdminAuditLog).delete()
    db.commit()


def _enable_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", ADMIN_TOKEN)


def _headers():
    return {"X-Admin-Token": ADMIN_TOKEN}


# ============================== 运营健康 ==============================


class TestStatsHealth:
    def test_shape(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        b = client.get("/api/admin/stats/health?days=7", headers=_headers()).json()
        assert b["days"] == 7
        # series 是 days+1 个点（含今天），跟 /timeseries 的口径保持一致
        assert len(b["series"]) == 8
        assert set(b["duration_seconds"]) == {"sample_size", "p50", "p95", "avg", "max"}
        assert set(b["stuck"]) == {"threshold_minutes", "count", "jobs"}

    def test_days_is_clamped(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        assert client.get("/api/admin/stats/health?days=9999", headers=_headers()).json()["days"] == 90
        assert client.get("/api/admin/stats/health?days=0", headers=_headers()).json()["days"] == 1

    def test_success_rate_is_none_on_days_with_no_settled_reviews(self, client, monkeypatch):
        """没跑过东西的那天不能画成 100%。

        这条不是吹毛求疵：把空白天当满分，图上就是一条持续的绿线，
        真正开始掉成功率的那天反而看起来只是"从 100 掉下来一点"。
        """
        _enable_admin(monkeypatch)
        b = client.get("/api/admin/stats/health?days=90", headers=_headers()).json()
        for point in b["series"]:
            if point["completed"] + point["failed"] == 0:
                assert point["success_rate"] is None, (
                    f"{point['date']} 当天没有已结束的评审，success_rate 却是 "
                    f"{point['success_rate']}——空白天被当成了满分天。"
                )

    def test_success_rate_reflects_real_failures(self, client, monkeypatch, db):
        from app.models import Review

        _enable_admin(monkeypatch)
        made = []
        for status in ("completed", "completed", "failed"):
            r = Review(user_id="ops-health", task_type="concept_review",
                       artifact_bundle={}, status=status)
            db.add(r)
            made.append(r)
        db.commit()
        try:
            b = client.get("/api/admin/stats/health?days=1", headers=_headers()).json()
            assert b["totals"]["failed"] >= 1
            assert b["totals"]["success_rate"] is not None
            assert 0.0 <= b["totals"]["success_rate"] < 1.0, (
                "有失败的评审但整体成功率仍是满分——失败没有被计入"
            )
        finally:
            for r in made:
                db.delete(r)
            db.commit()

    def test_stuck_detects_old_queued_job(self, client, monkeypatch, db):
        """卡死判定：状态没到终态 + 创建时间超过阈值。"""
        from datetime import datetime, timedelta, timezone

        from app.models import Job

        _enable_admin(monkeypatch)
        old = Job(
            kind="review",
            ref_id="ops-stuck",
            status="running",
            created_at=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        db.add(old)
        db.commit()

        b = client.get(
            "/api/admin/stats/health?stuck_minutes=30", headers=_headers()
        ).json()
        hit = [j for j in b["stuck"]["jobs"] if j["ref_id"] == "ops-stuck"]
        assert hit, "跑了 3 小时还没终态的任务没被认成卡死"
        assert hit[0]["stuck_minutes"] >= 179

        # 阈值抬到 4 小时就不该再报——阈值真的在起作用，不是摆设
        b2 = client.get(
            "/api/admin/stats/health?stuck_minutes=240", headers=_headers()
        ).json()
        assert not [j for j in b2["stuck"]["jobs"] if j["ref_id"] == "ops-stuck"]

    def test_terminal_jobs_are_never_stuck(self, client, monkeypatch, db):
        from datetime import datetime, timedelta, timezone

        from app.models import Job

        _enable_admin(monkeypatch)
        db.add(Job(kind="review", ref_id="ops-done-old", status="done",
                   created_at=datetime.now(timezone.utc) - timedelta(days=5)))
        db.commit()
        b = client.get("/api/admin/stats/health", headers=_headers()).json()
        assert not [j for j in b["stuck"]["jobs"] if j["ref_id"] == "ops-done-old"], (
            "已完成的老任务被当成卡死了——卡死看的是状态，不是年龄"
        )


# ============================== 任务聚合 ==============================


class TestStatsJobs:
    def test_shape(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        b = client.get("/api/admin/stats/jobs", headers=_headers()).json()
        assert set(b) == {"days", "by_status", "by_kind", "failure_reasons", "runtime_seconds"}

    def test_failure_reasons_group_across_differing_ids(self, client, monkeypatch, db):
        """同类错误必须聚成一条。

        错误消息里带 review_id / 数量，不归一的话 3 次同种故障会散成
        3 个 count=1 的条目，Top 榜就完全没有信息量了。
        """
        from app.models import Job

        _enable_admin(monkeypatch)
        for i in range(3):
            db.add(Job(
                kind="review",
                ref_id=f"ops-fail-{i}",
                status="failed",
                error_message=f"评审 {i} 失败：调用 LLM 超时，重试 {i + 1} 次后放弃",
            ))
        db.commit()

        reasons = client.get("/api/admin/stats/jobs", headers=_headers()).json()["failure_reasons"]
        merged = [r for r in reasons if "超时" in r["signature"]]
        assert len(merged) == 1, f"同类错误没有聚合，散成了 {len(merged)} 条：{merged}"
        assert merged[0]["count"] == 3

    def test_failure_reasons_capped_at_ten(self, client, monkeypatch, db):
        from app.models import Job

        _enable_admin(monkeypatch)
        for i in range(15):
            db.add(Job(kind="review", ref_id=f"ops-many-{i}", status="failed",
                       error_message=f"互不相同的错误类型 {chr(65 + i)}"))
        db.commit()
        reasons = client.get("/api/admin/stats/jobs", headers=_headers()).json()["failure_reasons"]
        assert len(reasons) <= 10

    def test_only_failed_jobs_contribute_reasons(self, client, monkeypatch, db):
        from app.models import Job

        _enable_admin(monkeypatch)
        db.add(Job(kind="review", ref_id="ops-done-with-msg", status="done",
                   error_message="这条是 done 状态但带了历史错误消息"))
        db.commit()
        reasons = client.get("/api/admin/stats/jobs", headers=_headers()).json()["failure_reasons"]
        assert not [r for r in reasons if "历史错误消息" in r["signature"]]


# ============================== 任务运维操作 ==============================


class TestJobCancel:
    def test_cancel_queued_job(self, client, monkeypatch, db):
        from app.models import Job

        _enable_admin(monkeypatch)
        j = Job(kind="review", ref_id="ops-cancel-me", status="queued")
        db.add(j)
        db.commit()
        job_id = j.id

        r = client.post(f"/api/admin/jobs/{job_id}/cancel", headers=_headers())
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

        db.expire_all()
        assert db.get(Job, job_id).status == "cancelled", (
            "接口回了 cancelled 但库里没改——下一次刷新它又变回 queued"
        )

    def test_cancel_running_is_refused(self, client, monkeypatch, db):
        """进程内队列杀不掉正在跑的线程，所以不许假装取消成功。"""
        from app.models import Job

        _enable_admin(monkeypatch)
        j = Job(kind="review", ref_id="ops-cancel-running", status="running")
        db.add(j)
        db.commit()

        r = client.post(f"/api/admin/jobs/{j.id}/cancel", headers=_headers())
        assert r.status_code == 400
        assert "标记为失败" in r.json()["error"]["message"]

        db.expire_all()
        assert db.get(Job, j.id).status == "running", "被拒绝的取消却改了状态"

    @pytest.mark.parametrize("terminal", ["done", "failed", "cancelled"])
    def test_cancel_terminal_is_refused(self, client, monkeypatch, db, terminal):
        from app.models import Job

        _enable_admin(monkeypatch)
        j = Job(kind="review", ref_id=f"ops-term-{terminal}", status=terminal)
        db.add(j)
        db.commit()
        r = client.post(f"/api/admin/jobs/{j.id}/cancel", headers=_headers())
        assert r.status_code == 400

    def test_cancel_404(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        assert client.post(
            "/api/admin/jobs/no-such-job/cancel", headers=_headers()
        ).status_code == 404

    def test_cancel_is_audited(self, client, monkeypatch, db):
        from app.models import Job

        _enable_admin(monkeypatch)
        j = Job(kind="review", ref_id="ops-cancel-audit", status="queued")
        db.add(j)
        db.commit()
        client.post(f"/api/admin/jobs/{j.id}/cancel", headers=_headers())
        actions = [e["action"] for e in
                   client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]]
        assert "job.cancel" in actions


class TestJobForceFail:
    def test_force_fail_running_job(self, client, monkeypatch, db):
        from app.models import Job

        _enable_admin(monkeypatch)
        j = Job(kind="review", ref_id="ops-ff", status="running")
        db.add(j)
        db.commit()
        job_id = j.id

        r = client.post(f"/api/admin/jobs/{job_id}/force-fail", headers=_headers())
        assert r.status_code == 200
        assert r.json()["status"] == "failed"

        db.expire_all()
        row = db.get(Job, job_id)
        assert row.status == "failed"
        assert row.finished_at is not None, "推到终态却没有 finished_at，耗时统计会漏掉它"
        assert row.error_message, "强制失败没有留下原因，事后没人知道这是人为的还是真崩了"

    def test_force_fail_also_settles_the_linked_review(self, client, monkeypatch, db):
        """任务卡死时评审也卡着，用户前端会一直转圈。两边要一起收尾。"""
        from app.models import Job, Review

        _enable_admin(monkeypatch)
        review = Review(user_id="ops-ff-user", task_type="concept_review",
                        artifact_bundle={}, status="running")
        db.add(review)
        db.commit()
        db.refresh(review)
        rid = review.id

        j = Job(kind="review", ref_id=rid, status="running")
        db.add(j)
        db.commit()

        body = client.post(f"/api/admin/jobs/{j.id}/force-fail", headers=_headers()).json()
        assert body["review_updated"] == rid

        db.expire_all()
        assert db.get(Review, rid).status == "failed"
        assert db.get(Review, rid).error_message

        db.delete(db.get(Review, rid))
        db.commit()

    def test_force_fail_does_not_touch_a_completed_review(self, client, monkeypatch, db):
        """任务行卡住但评审其实已经跑完了——这时候不能把成品改成失败。"""
        from app.models import Job, Review

        _enable_admin(monkeypatch)
        review = Review(user_id="ops-ff-done", task_type="concept_review",
                        artifact_bundle={}, status="completed")
        db.add(review)
        db.commit()
        db.refresh(review)
        rid = review.id

        j = Job(kind="review", ref_id=rid, status="running")
        db.add(j)
        db.commit()

        body = client.post(f"/api/admin/jobs/{j.id}/force-fail", headers=_headers()).json()
        assert body["review_updated"] is None

        db.expire_all()
        assert db.get(Review, rid).status == "completed", (
            "把一份已经完成的评审改成了失败——用户会看到自己拿到过的报告变成错误页"
        )

        db.delete(db.get(Review, rid))
        db.commit()

    def test_force_fail_terminal_is_refused(self, client, monkeypatch, db):
        from app.models import Job

        _enable_admin(monkeypatch)
        j = Job(kind="review", ref_id="ops-ff-done-job", status="done")
        db.add(j)
        db.commit()
        assert client.post(
            f"/api/admin/jobs/{j.id}/force-fail", headers=_headers()
        ).status_code == 400

    def test_force_fail_is_audited(self, client, monkeypatch, db):
        from app.models import Job

        _enable_admin(monkeypatch)
        j = Job(kind="review", ref_id="ops-ff-audit", status="running")
        db.add(j)
        db.commit()
        client.post(f"/api/admin/jobs/{j.id}/force-fail", headers=_headers())
        actions = [e["action"] for e in
                   client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]]
        assert "job.force_fail" in actions


class TestNoRetryEndpoint:
    def test_retry_endpoint_deliberately_does_not_exist(self, client, monkeypatch):
        """重试是刻意不做的，不是漏做的。

        enqueue_review 只把 key_source 写进 payload，API key 显式传参不落库
        （review_service.py 里解释了原因：防止多 worker 之间串 key）。
        后台没有密钥，重试必然当场失败——一个注定失败的按钮比没有按钮更糟。
        谁哪天想加，先解决"密钥从哪来"，别只加路由。
        """
        _enable_admin(monkeypatch)
        r = client.post("/api/admin/jobs/whatever/retry", headers=_headers())
        assert r.status_code == 404


# ============================== CDK 兑换记录 ==============================


class TestCdkRedemptions:
    def _make_code(self, client, credits=5):
        return client.post(
            "/api/admin/cdk/generate",
            json={"count": 1, "credits": credits, "max_uses": 5},
            headers=_headers(),
        ).json()["codes"][0]

    def test_redemption_shows_up_with_code_and_user(self, client, monkeypatch, db):
        from app.services import cdk_service

        _enable_admin(monkeypatch)
        code = self._make_code(client)
        cdk_service.redeem(db, code_str=code, user_id="ops-redeemer")

        rows = client.get(
            f"/api/admin/cdk/redemptions?code={code}", headers=_headers()
        ).json()["redemptions"]
        assert len(rows) == 1
        assert rows[0]["user_id"] == "ops-redeemer"
        assert rows[0]["credits"] == 5

    def test_credited_in_ledger_matches_granted_credits(self, client, monkeypatch, db):
        """这一列是整个端点存在的理由：兑换记录有、流水没有 = 次数没到账。"""
        from app.services import cdk_service

        _enable_admin(monkeypatch)
        code = self._make_code(client, credits=7)
        cdk_service.redeem(db, code_str=code, user_id="ops-ledger-check")

        row = client.get(
            f"/api/admin/cdk/redemptions?code={code}", headers=_headers()
        ).json()["redemptions"][0]
        assert row["credited_in_ledger"] == 7, (
            "兑换记录里发了 7 次，但 credit_ledger 里对不上——"
            "这正是『兑了码没到账』的形态，这一列就是为了让它一眼可见"
        )

    def test_filter_by_user_id(self, client, monkeypatch, db):
        from app.services import cdk_service

        _enable_admin(monkeypatch)
        code = self._make_code(client)
        cdk_service.redeem(db, code_str=code, user_id="ops-alice")
        cdk_service.redeem(db, code_str=code, user_id="ops-bob")

        rows = client.get(
            "/api/admin/cdk/redemptions?user_id=ops-alice", headers=_headers()
        ).json()["redemptions"]
        assert rows and all(r["user_id"] == "ops-alice" for r in rows)

    def test_anonymous_redemption_is_not_dropped(self, client, monkeypatch, db):
        """访客兑换的 user_id 不在 users 表里。

        用 inner join 会把这批记录整个吞掉——而它们恰恰是最容易出问题、
        最需要被查到的一批（没有账号，用户自己也查不了）。
        """
        from app.services import cdk_service

        _enable_admin(monkeypatch)
        code = self._make_code(client)
        cdk_service.redeem(db, code_str=code, user_id="guest-not-a-real-user")

        rows = client.get(
            f"/api/admin/cdk/redemptions?code={code}", headers=_headers()
        ).json()["redemptions"]
        assert len(rows) == 1
        assert rows[0]["user_email"] is None

    def test_pagination(self, client, monkeypatch, db):
        from app.services import cdk_service

        _enable_admin(monkeypatch)
        code = self._make_code(client)
        for i in range(3):
            cdk_service.redeem(db, code_str=code, user_id=f"ops-page-{i}")

        p = client.get(
            f"/api/admin/cdk/redemptions?code={code}&limit=1&offset=0", headers=_headers()
        ).json()
        assert p["total"] == 3 and len(p["redemptions"]) == 1

    def test_requires_admin_token(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        assert client.get("/api/admin/cdk/redemptions").status_code == 401


# ============================== 用户详情 ==============================


class TestUserDetail:
    def _signup(self, client, email):
        monkey_pw = "password123"
        client.post("/api/auth/register", json={"email": email, "password": monkey_pw})
        token = client.post(
            "/api/auth/login", json={"email": email, "password": monkey_pw}
        ).json()["token"]
        uid = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user_id"]
        return uid, token

    @pytest.fixture(autouse=True)
    def _auth_on(self, monkeypatch):
        monkeypatch.setattr(settings, "auth_enabled", True)
        yield

    def test_shape(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        uid, _ = self._signup(client, "ops-detail@example.com")
        b = client.get(f"/api/admin/users/{uid}", headers=_headers()).json()
        assert set(b) >= {
            "id", "email", "plan", "is_active", "reviews",
            "usage_by_key_source", "api_keys", "credit_balance", "cdk_redemptions",
        }
        assert set(b["reviews"]) == {"by_status", "total", "recent"}

    def test_404_for_unknown_user(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        assert client.get("/api/admin/users/nope", headers=_headers()).status_code == 404

    def test_viewing_detail_is_audited(self, client, monkeypatch):
        """隐私政策原话："这类访问会记入后台审计日志"——这条测试守着这句话不是空话。

        列表页 (/users) 不含评审内容，不必记；这个端点会带出 recent 评审标题，
        属于政策里说的"查看内容"，必须留痕。
        """
        _enable_admin(monkeypatch)
        uid, _ = self._signup(client, "ops-audit-view@example.com")
        client.get(f"/api/admin/users/{uid}", headers=_headers())
        entries = client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]
        hit = [e for e in entries if e["action"] == "user.view_detail" and e["target"] == "ops-audit-view@example.com"]
        assert hit, "查看了用户详情，但审计日志里没有留痕"

    def test_404_does_not_get_audited(self, client, monkeypatch):
        """查不存在的用户不算"看到了内容"，不该污染审计日志。"""
        _enable_admin(monkeypatch)
        client.get("/api/admin/users/no-such-user", headers=_headers())
        entries = client.get("/api/admin/audit-log", headers=_headers()).json()["entries"]
        assert not [e for e in entries if e["action"] == "user.view_detail"]

    def test_never_returns_key_ciphertext(self, client, monkeypatch, db):
        """后台要能看到"这人配没配 BYOK"，但绝不能看到密钥本身。

        key_masked 是本来就给前端回显的字段；key_ciphertext 是密文，
        任何时候都不该出现在 HTTP 响应里。
        """
        import json as _json

        from app.services import key_service

        _enable_admin(monkeypatch)
        uid, _ = self._signup(client, "ops-key@example.com")
        key_service.save_user_key(db, uid, "sk-ant-supersecret-value-0123456789")
        try:
            raw = client.get(f"/api/admin/users/{uid}", headers=_headers()).text
            assert "supersecret" not in raw, "明文密钥出现在后台响应里"
            assert "key_ciphertext" not in raw, "密文字段被序列化进了响应"

            keys = _json.loads(raw)["api_keys"]
            assert len(keys) == 1
            assert keys[0]["key_masked"], "连脱敏回显都没有，后台无法确认这人配没配 key"
        finally:
            key_service.delete_user_key(db, uid)

    def test_reviews_and_usage_are_scoped_to_this_user(self, client, monkeypatch, db):
        """详情页串用户是最坏的一类 bug——运营会照着别人的数据做处置。"""
        from app.models import Review

        _enable_admin(monkeypatch)
        mine, _ = self._signup(client, "ops-mine@example.com")
        other, _ = self._signup(client, "ops-other@example.com")

        r1 = Review(user_id=mine, task_type="concept_review", artifact_bundle={},
                    status="completed", target_title="我的评审")
        r2 = Review(user_id=other, task_type="concept_review", artifact_bundle={},
                    status="completed", target_title="别人的评审")
        db.add_all([r1, r2])
        db.commit()

        try:
            b = client.get(f"/api/admin/users/{mine}", headers=_headers()).json()
            titles = [r["target_title"] for r in b["reviews"]["recent"]]
            assert "我的评审" in titles
            assert "别人的评审" not in titles, "用户详情串号了"
            assert b["reviews"]["total"] == 1
        finally:
            db.delete(r1)
            db.delete(r2)
            db.commit()

    def test_cdk_redemptions_appear_in_detail(self, client, monkeypatch, db):
        from app.services import cdk_service

        _enable_admin(monkeypatch)
        uid, _ = self._signup(client, "ops-cdk-detail@example.com")
        code = client.post(
            "/api/admin/cdk/generate",
            json={"count": 1, "credits": 3, "max_uses": 1},
            headers=_headers(),
        ).json()["codes"][0]
        cdk_service.redeem(db, code_str=code, user_id=uid)

        b = client.get(f"/api/admin/users/{uid}", headers=_headers()).json()
        assert [r["code"] for r in b["cdk_redemptions"]] == [code]
        assert b["credit_balance"] == 3


class TestUserListSorting:
    def test_sort_by_email_asc(self, client, monkeypatch):
        _enable_admin(monkeypatch)
        rows = client.get(
            "/api/admin/users?sort=email&order=asc&limit=200", headers=_headers()
        ).json()["users"]
        emails = [u["email"] for u in rows]
        assert emails == sorted(emails)

    def test_unknown_sort_field_is_rejected(self, client, monkeypatch):
        """按聚合列排序会得到"页内有序、跨页乱序"——比不能排更误导人，所以直接拒。"""
        _enable_admin(monkeypatch)
        r = client.get("/api/admin/users?sort=cost_usd_total", headers=_headers())
        assert r.status_code == 400
        assert "cost_usd_total" in r.json()["error"]["message"]

    def test_default_sort_is_unchanged(self, client, monkeypatch):
        """不传 sort 时行为必须和加排序之前一致（created_at desc）——
        这是个既有接口，静默改掉默认顺序会让前端分页错位。"""
        _enable_admin(monkeypatch)
        rows = client.get("/api/admin/users?limit=200", headers=_headers()).json()["users"]
        created = [u["created_at"] for u in rows if u["created_at"]]
        assert created == sorted(created, reverse=True)
