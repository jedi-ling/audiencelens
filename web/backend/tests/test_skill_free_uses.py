# -*- coding: utf-8 -*-
"""高级技能的免费体验次数 + 用完降级。

产品口径：高级技能（默认只有红队）每个账号免费 N 次，用完不挡人——
降级成普通评审，报告照出，但**必须如实告知**。

这类"降级"机制最危险的失败模式不是拦错人，而是**说了降级却没真降**
（提示回了、参数照原样跑）或者反过来**真降了却不吭声**。后者正是这个仓库
反复要根除的静默降级：用户以为产品本来就这样。所以下面每条都同时断言
"落库的值变了"和"提示说出来了"。
"""

import pytest

from app.config import settings
from app.models import Review
from app.services import skill_quota_service


@pytest.fixture(autouse=True)
def _skill_quota_on(monkeypatch):
    monkeypatch.setattr(settings, "skill_free_uses", 2)
    monkeypatch.setattr(settings, "premium_skills", {"red_team_audience"})
    monkeypatch.setattr(settings, "anonymous_user_id", "anon-skill")
    yield


def _past_review(db, user_id, *, skill=None, red_team=False, key_source="server"):
    db.add(Review(
        user_id=user_id, task_type="concept_review", artifact_bundle={},
        skill_type=skill, enable_red_team=red_team, key_source=key_source,
        mode="standard", status="completed",
    ))
    db.commit()


class TestCounting:
    def test_counts_skill_type_uses(self, db):
        for _ in range(2):
            _past_review(db, "u1", skill="red_team_audience")
        assert skill_quota_service.used_count(db, "u1", "red_team_audience") == 2

    def test_counts_the_independent_red_team_toggle_too(self, db):
        """红队有两条入口：skill_type 和与它正交的 enable_red_team 开关。

        只算一条的话，用户把技能选成受众面板、再打开红队开关，就能无限用。
        """
        _past_review(db, "u2", skill="audience_panel", red_team=True)
        assert skill_quota_service.used_count(db, "u2", "red_team_audience") == 1

    def test_byok_history_not_counted(self, db):
        """反向对照：用自己 key 跑的不该扣免费次数。"""
        for _ in range(5):
            _past_review(db, "u3", skill="red_team_audience", key_source="byok")
        assert skill_quota_service.used_count(db, "u3", "red_team_audience") == 0

    def test_legacy_null_key_source_not_counted(self, db):
        """老数据 key_source 是 NULL（当时确实不知道花的谁的钱）。

        宁可少算也不能凭空扣掉老用户的免费次数——把 NULL 当成 server 是编造。
        """
        _past_review(db, "u4", skill="red_team_audience", key_source=None)
        assert skill_quota_service.used_count(db, "u4", "red_team_audience") == 0


class TestUsesLeft:
    def test_counts_down(self, db):
        assert skill_quota_service.uses_left(db, "c1", "red_team_audience") == 2
        _past_review(db, "c1", skill="red_team_audience")
        assert skill_quota_service.uses_left(db, "c1", "red_team_audience") == 1

    def test_never_negative(self, db):
        for _ in range(5):
            _past_review(db, "c2", skill="red_team_audience")
        assert skill_quota_service.uses_left(db, "c2", "red_team_audience") == 0

    def test_byok_unlimited(self, db):
        assert skill_quota_service.uses_left(db, "c3", "red_team_audience", "byok") is None

    def test_anonymous_bucket_unlimited(self, db):
        """共享匿名桶按它计次 = 全站一共只能用 N 次，是全局故障不是限流。"""
        assert skill_quota_service.uses_left(db, "anon-skill", "red_team_audience") is None

    def test_non_premium_skill_unlimited(self, db):
        assert skill_quota_service.uses_left(db, "c4", "audience_panel") is None

    def test_negative_config_disables(self, db, monkeypatch):
        monkeypatch.setattr(settings, "skill_free_uses", -1)
        for _ in range(9):
            _past_review(db, "c5", skill="red_team_audience")
        assert skill_quota_service.uses_left(db, "c5", "red_team_audience") is None


class TestApplyDegrades:
    def test_under_limit_keeps_the_skill(self, db):
        """反向对照：还有次数时绝不能降级，否则这个功能就把红队整个关掉了。"""
        skill, red, note = skill_quota_service.apply(
            db, "a1", "server", "red_team_audience", False
        )
        assert skill == "red_team_audience"
        assert note is None

    def test_exhausted_strips_the_skill_and_says_so(self, db):
        for _ in range(2):
            _past_review(db, "a2", skill="red_team_audience")
        skill, red, note = skill_quota_service.apply(
            db, "a2", "server", "red_team_audience", False
        )
        assert skill is None, "说降级了就必须真的把技能剥掉"
        assert note and "用完" in note, "真降了就必须告诉用户，不能静默"

    def test_exhausted_also_strips_the_independent_toggle(self, db):
        """选别的技能 + 单独打开红队开关，同样要被降级。

        漏掉这条的话，绕过方式简单到用户会自己发现：技能选受众面板，
        再把红队开关打开。
        """
        for _ in range(2):
            _past_review(db, "a3", skill="red_team_audience")
        skill, red, note = skill_quota_service.apply(
            db, "a3", "server", "audience_panel", True
        )
        assert skill == "audience_panel", "非高级技能不该被误伤"
        assert red is False, "红队开关必须被关掉"
        assert note is not None

    def test_byok_never_degraded(self, db):
        for _ in range(9):
            _past_review(db, "a4", skill="red_team_audience")
        skill, red, note = skill_quota_service.apply(
            db, "a4", "byok", "red_team_audience", True
        )
        assert skill == "red_team_audience"
        assert red is True
        assert note is None


class TestEndToEndThroughApi:
    """走真实接口，确认降级后的值**落进了库**，不是只回了一句提示。"""

    def _signup(self, client, email):
        client.post("/api/auth/register", json={"email": email, "password": "password123"})
        r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
        return r.json()["token"]

    def test_quota_endpoint_reports_remaining(self, client, monkeypatch):
        monkeypatch.setattr(settings, "auth_enabled", True)
        t = self._signup(client, "skillq@example.com")
        r = client.get("/api/skill-quota", headers={"Authorization": f"Bearer {t}"})
        assert r.status_code == 200
        body = r.json()
        assert body["skills"]["red_team_audience"] == 2
        assert body["free_uses"] == 2

    def test_degraded_review_persists_the_downgraded_value(self, client, db, monkeypatch):
        """最要紧的一条：库里存的必须是降级后的值。

        如果只把提示回给前端、Review 仍按原参数落库并跑 prompt，那就是
        "提示说降级了、实际没降"——比不做更糟，因为账面上还多收了一次。
        """
        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "quota_enabled", False)
        t = self._signup(client, "skilldeg@example.com")
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).json()
        uid = me["user_id"]
        for _ in range(2):
            _past_review(db, uid, skill="red_team_audience")

        r = client.post(
            "/api/v2/reviews",
            headers={"Authorization": f"Bearer {t}"},
            json={
                "task_type": "concept_review",
                "artifact": {"title": "t", "materials": []},
                "skill_type": "red_team_audience",
            },
        )
        # 无 key 时会 428（resolve_llm_key 是硬依赖），那说明还没走到降级逻辑；
        # 有 key 时应当 202 且带降级说明。两种都可接受，但不能是 500。
        assert r.status_code in (202, 428), r.text
        if r.status_code == 202:
            assert r.json()["skill_degraded"], "降级了必须在响应里说出来"
            rid = r.json()["review_id"]
            db.expire_all()
            row = db.query(Review).filter(Review.id == rid).first()
            assert row.skill_type is None, "落库的必须是降级后的值"
