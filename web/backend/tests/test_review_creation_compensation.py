"""评审创建失败补偿 + persona_pack 显式校验（spec 3.5）。

1. 落库（db.commit）先于入队（enqueue_review）。入队失败此前返回 500，
   但 review 永久 pending、credits 已扣不退——用户花钱买的次数凭空消失。
   修复：入队失败时删除刚落库的 review（或标 failed），并走与后台收尸
   （db._settle_reaped_reviews）同一套幂等退款原语，钱先退回去再报 5xx。

2. persona_pack 拼错此前静默回落 game-core：用户选 A 包，跑的是 B 包，
   报告人格与所见不符。修复：入口校验，非法值显式 400。
"""

import pytest

from app.config import settings


def _enable_managed(monkeypatch):
    monkeypatch.setattr(settings, "key_mode", "managed")
    monkeypatch.setattr(settings, "server_llm_key", "sk-ant-server-key")


def _enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


@pytest.fixture
def credits_mode(monkeypatch):
    monkeypatch.setattr(settings, "quota_enabled", True)
    monkeypatch.setattr(settings, "quota_mode", "credits")


def _register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_payload(persona_pack="game-core"):
    return {
        "task_type": "concept_review",
        "artifact": {"title": "x", "materials": [{"type": "text", "text": "核心循环"}]},
        "persona_pack": persona_pack,
    }


def _user_id(db, email):
    from app.models import User

    return db.query(User).filter(User.email == email).one().id


class TestPersonaPackValidation:
    def test_unknown_persona_pack_returns_400(self, client, monkeypatch):
        """拼错的包名不再静默回落 game-core——用户选 A 包跑 B 包是功能缺陷。"""
        _enable_managed(monkeypatch)
        r = client.post("/api/v2/reviews", json=_create_payload(persona_pack="no-such-pack"))
        assert r.status_code == 400
        assert "no-such-pack" in r.json()["error"]["message"]

    def test_known_persona_packs_pass_through(self, client, monkeypatch):
        from app.services import review_service

        _enable_managed(monkeypatch)
        seen = []

        def fake_enqueue(*args, **kwargs):
            seen.append(kwargs.get("review_id"))
            return "job-fake"

        monkeypatch.setattr(review_service, "enqueue_review", fake_enqueue)
        for pack in ("game-core", "vr-immersive"):
            r = client.post("/api/v2/reviews", json=_create_payload(pack))
            assert r.status_code == 202, (pack, r.text)
        assert len(seen) == 2


class TestEnqueueFailureCompensation:
    """入队（create_job / submit）抛异常：review 必须被清理、已扣次数必须退回。"""

    @staticmethod
    def _boom(*args, **kwargs):
        raise RuntimeError("queue backend down")

    def test_credits_are_refunded_and_review_removed(self, client, db, monkeypatch, credits_mode):
        from app.models import CreditLedger, Review
        from app.services import cdk_service, review_service

        _enable_auth(monkeypatch)
        _enable_managed(monkeypatch)
        token = _register(client, "comp-credit@example.com")
        uid = _user_id(db, "comp-credit@example.com")
        db.add(CreditLedger(user_id=uid, delta=1, reason="cdk_redeem"))
        db.commit()
        assert cdk_service.credit_balance(db, uid) == 1

        monkeypatch.setattr(review_service, "enqueue_review", self._boom)
        r = client.post("/api/v2/reviews", json=_create_payload(), headers=_headers(token))
        assert r.status_code == 500, r.text

        db.expire_all()
        assert (
            db.query(Review).filter(Review.user_id == uid).count() == 0
        ), "入队失败后 review 应被删除，不能永久 pending"
        assert cdk_service.credit_balance(db, uid) == 1, "入队失败后已扣次数必须退回"

    def test_plan_mode_slot_is_released(self, client, db, monkeypatch):
        """plan 模式的日名额是入口占位，入队失败必须释放，否则用户被自己的
        失败请求挡在门外。占位释放后应能再次发起。"""
        from app.models import User
        from app.services import review_service

        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "plan")
        monkeypatch.setattr(settings, "quota_free_reviews_per_day", 1)
        monkeypatch.setattr(settings, "quota_free_cost_usd_per_day", 100.0)
        _enable_managed(monkeypatch)
        token = _register(client, "comp-plan@example.com")
        uid = _user_id(db, "comp-plan@example.com")

        monkeypatch.setattr(review_service, "enqueue_review", self._boom)
        r = client.post("/api/v2/reviews", json=_create_payload(), headers=_headers(token))
        assert r.status_code == 500, r.text

        # 占位已释放 → 名额恢复，再发起一次应该放行
        monkeypatch.setattr(
            review_service, "enqueue_review", lambda *a, **k: "job-ok"
        )
        r2 = client.post("/api/v2/reviews", json=_create_payload(), headers=_headers(token))
        assert r2.status_code == 202, r2.text
