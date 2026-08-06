# -*- coding: utf-8 -*-
"""入队失败时的计费补偿——v1 与 v2 必须一致。

check_quota 在**放行的瞬间**就扣了钱：CDK 次数原子扣减、日名额占位、
终身 token 额度占位。如果紧接着的入队炸了，这三样都必须还回去，
否则用户什么都没得到、额度还少了一截。

v2 一直有这段补偿，v1 是**裸调用** —— 又一个"v2 修了 v1 没修"。
这个形状在本仓库出现过太多次，所以这里两条路各测一遍，而不是只测修好的那条。
"""

import pytest

from app.config import settings
from app.services import cdk_service, quota_service


@pytest.fixture(autouse=True)
def _quota_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "quota_enabled", True)
    monkeypatch.setattr(settings, "quota_mode", "credits")
    monkeypatch.setattr(settings, "quota_tokens_total", 10_000_000)
    monkeypatch.setattr(settings, "quota_tokens_per_review_estimate", 150_000)
    yield


@pytest.fixture
def _boom(monkeypatch):
    """让入队必炸，并给一把假的平台 key。

    假 key 是必须的：没有 key 时 resolve_llm_key 会在**扣费之前**就 428，
    整条路径根本走不到入队那一步——测试会 skip，而 skip 的测试什么也没证明。
    key 永远不会被真的用来发请求（入队在此之前就抛了）。
    """
    from app.services import key_service, review_service

    def boom(*a, **kw):
        raise RuntimeError("queue is down")

    monkeypatch.setattr(review_service, "enqueue_review", boom)
    monkeypatch.setattr(
        key_service,
        "resolve_key",
        lambda db, user_id, provider="anthropic": key_service.ResolvedKey(
            key="sk-fake-never-used", source="server", provider="anthropic",
            model=None, api_base=None,
        ),
    )


def _account(client, db, email):
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    tok = client.post(
        "/api/auth/login", json={"email": email, "password": "password123"}
    ).json()["token"]
    uid = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["user_id"]
    rows = cdk_service.generate_codes(db, count=1, credits=5)
    cdk_service.redeem(db, rows[0].code, uid)
    return tok, uid


def _payload_v2():
    return {
        "task_type": "concept_review",
        "artifact": {"title": "t", "materials": [{"type": "text", "text": "x"}]},
    }


def _payload_v1():
    return {
        "task_type": "concept_review",
        "artifact_bundle": {"title": "t", "materials": [{"type": "text", "text": "x"}]},
        "mode": "standard",
    }


class TestCompensation:
    @pytest.mark.parametrize(
        "path,payload_fn",
        [("/api/v2/reviews", _payload_v2), ("/api/reviews", _payload_v1)],
        ids=["v2", "v1"],
    )
    def test_credits_and_token_hold_are_returned(
        self, client, db, monkeypatch, _boom, path, payload_fn
    ):
        tok, uid = _account(db=db, client=client, email=f"comp{path.count('v2')}@example.com")
        before_credits = cdk_service.credit_balance(db, uid)
        before_tokens = quota_service.tokens_used(db, uid)

        r = client.post(path, headers={"Authorization": f"Bearer {tok}"}, json=payload_fn())
        # 无 key 时是 428（还没走到扣费），那种情况这条测试没意义
        assert r.status_code >= 500, f"入队炸了就该报错，实际 {r.status_code}"

        db.expire_all()
        assert cdk_service.credit_balance(db, uid) == before_credits, (
            "入队失败必须退还 CDK 次数——用户什么都没得到"
        )
        assert quota_service.tokens_used(db, uid) == before_tokens, (
            "入队失败必须释放终身 token 占位，否则它会在 TTL 内一直吃着额度"
        )
