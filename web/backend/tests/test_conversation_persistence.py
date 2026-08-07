"""对话持续化：评审**之前**那段来回澄清必须活过刷新。

在此之前这一层完全不存在。用户在对话页说清"我想评审什么"的全部内容存在
前端的 useState/useRef 里，刷新即永久丢失——丢的恰恰是他投入描述最多、
最不愿意重打一遍的部分。当时唯一的"恢复"是从 artifact_bundle 里挑一条
文本伪造出一个用户气泡（AskPage.tsx:290-308），时间戳还是 Date.now()。

每条正向断言都配了反向对照。只测"存进去能读出来"的话，下面这些实现同样能
全绿，而它们各自都是致命的：
  · 不校验归属 —— 任何人凭 id 读走别人的对话
  · 归属校验回 403 —— 等于确认 id 存在，可用来枚举
  · seq 由前端算 —— 并发提交时两条消息挤在同一个位置，对话读起来前言不搭后语
  · 批量 delete() 删对话 —— 绕过级联，消息成孤儿行留在库里
  · 删账号不带对话 —— 用户资料删了，他打的字还在
"""

import pytest


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


def _signup(client, email, password="password123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _new_conv(client, token, title=None):
    r = client.post("/api/v2/conversations", json={"title": title}, headers=_h(token))
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _say(client, token, cid, role, content, meta=None):
    return client.post(
        f"/api/v2/conversations/{cid}/messages",
        json={"role": role, "content": content, "meta": meta},
        headers=_h(token),
    )


class TestSurvivesReload:
    """核心承诺：关掉页面再回来，说过的话还在。"""

    def test_messages_persist_in_order(self, client):
        t = _signup(client, "conv-order@example.com")
        cid = _new_conv(client, t)
        for i, (role, text) in enumerate(
            [
                ("user", "帮我看看这个定价页"),
                ("assistant", "好的，这个页面主要面向哪类客户？"),
                ("user", "中小团队，月付 $29"),
                ("assistant", "明白了，我按 SaaS 定价页来组评审团"),
            ]
        ):
            assert _say(client, t, cid, role, text).status_code == 200

        got = client.get(f"/api/v2/conversations/{cid}", headers=_h(t)).json()
        assert [m["content"] for m in got["messages"]] == [
            "帮我看看这个定价页",
            "好的，这个页面主要面向哪类客户？",
            "中小团队，月付 $29",
            "明白了，我按 SaaS 定价页来组评审团",
        ]
        # seq 必须严格递增。靠 created_at 排序会在同毫秒写入时随机颠倒，
        # 把一问一答读成一答一问。
        assert [m["seq"] for m in got["messages"]] == [1, 2, 3, 4]

    def test_seq_is_server_assigned_not_client(self, client):
        """前端就算把 seq 塞进请求体也不该被采信——它算不对。"""
        t = _signup(client, "conv-seq@example.com")
        cid = _new_conv(client, t)
        r = client.post(
            f"/api/v2/conversations/{cid}/messages",
            json={"role": "user", "content": "第一条", "seq": 999},
            headers=_h(t),
        )
        assert r.status_code == 200
        assert r.json()["seq"] == 1, "服务端应忽略前端传来的 seq"

    def test_card_payload_survives(self, client):
        """卡片类消息要能原样还原，不能只剩纯文本。"""
        t = _signup(client, "conv-meta@example.com")
        cid = _new_conv(client, t)
        meta = {"kind": "review_card", "review_id": "r-1", "personas": 12}
        assert _say(client, t, cid, "assistant", "评审已完成", meta).status_code == 200
        got = client.get(f"/api/v2/conversations/{cid}", headers=_h(t)).json()
        assert got["messages"][0]["meta"] == meta

    def test_title_taken_from_first_user_message(self, client):
        t = _signup(client, "conv-title@example.com")
        cid = _new_conv(client, t)
        _say(client, t, cid, "user", "帮我评审 Steam 商店页")
        _say(client, t, cid, "user", "补充一句：是横版动作游戏")
        lst = client.get("/api/v2/conversations", headers=_h(t)).json()["conversations"]
        assert lst[0]["title"] == "帮我评审 Steam 商店页", "标题应取首条用户消息，不该被后续覆盖"


class TestOwnershipIsolation:
    def test_other_user_cannot_read(self, client):
        a = _signup(client, "conv-a@example.com")
        b = _signup(client, "conv-b@example.com")
        cid = _new_conv(client, a)
        _say(client, a, cid, "user", "A 的商业机密")

        r = client.get(f"/api/v2/conversations/{cid}", headers=_h(b))
        # 反向对照：这里若是 200，就是任何人凭 id 读走别人的对话
        assert r.status_code == 404
        # 且必须是 404 而不是 403——403 等于确认"该 id 存在但不属于你"，
        # 可以被用来枚举他人对话 id
        assert r.status_code != 403

    def test_other_user_cannot_write(self, client):
        a = _signup(client, "conv-w-a@example.com")
        b = _signup(client, "conv-w-b@example.com")
        cid = _new_conv(client, a)
        assert _say(client, b, cid, "user", "注入").status_code == 404
        # 确认真的没写进去，而不是只回了个 404
        got = client.get(f"/api/v2/conversations/{cid}", headers=_h(a)).json()
        assert got["messages"] == []

    def test_other_user_cannot_delete(self, client):
        a = _signup(client, "conv-d-a@example.com")
        b = _signup(client, "conv-d-b@example.com")
        cid = _new_conv(client, a)
        assert client.delete(f"/api/v2/conversations/{cid}", headers=_h(b)).status_code == 404
        assert client.get(f"/api/v2/conversations/{cid}", headers=_h(a)).status_code == 200

    def test_list_only_shows_own(self, client):
        a = _signup(client, "conv-l-a@example.com")
        b = _signup(client, "conv-l-b@example.com")
        _new_conv(client, a, "A 的对话")
        _new_conv(client, b, "B 的对话")
        titles = [
            c["title"] for c in client.get("/api/v2/conversations", headers=_h(b)).json()["conversations"]
        ]
        assert titles == ["B 的对话"]

    def test_cannot_link_someone_elses_review(self, client):
        """把任意 review_id 绑到自己的对话上，就能顺着这条关联去拉他人报告。"""
        a = _signup(client, "conv-link-a@example.com")
        b = _signup(client, "conv-link-b@example.com")
        from app.db import SessionLocal
        from app.models import Review

        db = SessionLocal()
        try:
            rv = Review(
                id="rv-not-yours",
                user_id="someone-else",
                task_type="pricing_page",
                artifact_bundle={},
                status="completed",
            )
            db.add(rv)
            db.commit()
        finally:
            db.close()

        cid = _new_conv(client, b)
        r = client.patch(
            f"/api/v2/conversations/{cid}",
            json={"review_id": "rv-not-yours"},
            headers=_h(b),
        )
        assert r.status_code == 404
        assert client.get(f"/api/v2/conversations/{cid}", headers=_h(b)).json()["review_id"] is None
        assert a  # 保持 fixture 语义完整


class TestDeletionCascades:
    def test_deleting_conversation_removes_messages(self, client):
        t = _signup(client, "conv-cascade@example.com")
        cid = _new_conv(client, t)
        _say(client, t, cid, "user", "会被一起删掉的内容")

        from app.db import SessionLocal
        from app.models import ConversationMessage

        db = SessionLocal()
        try:
            assert (
                db.query(ConversationMessage).filter_by(conversation_id=cid).count() == 1
            ), "前置条件不成立：消息根本没写进去，后面的断言证明不了级联"
        finally:
            db.close()

        assert client.delete(f"/api/v2/conversations/{cid}", headers=_h(t)).status_code == 200

        db = SessionLocal()
        try:
            # 反向对照：批量 delete() 的实现会让这里留下孤儿消息行
            assert db.query(ConversationMessage).filter_by(conversation_id=cid).count() == 0
        finally:
            db.close()

    def test_deleting_account_removes_conversations(self, client):
        t = _signup(client, "conv-acct@example.com")
        cid = _new_conv(client, t)
        _say(client, t, cid, "user", "删号后不该留在库里的内容")

        from app.api.platform import DELETE_CONFIRM_PHRASE

        r = client.post(
            "/api/auth/me/delete",
            json={"password": "password123", "confirm": DELETE_CONFIRM_PHRASE},
            headers=_h(t),
        )
        assert r.status_code == 200, r.text
        # 统计数嵌在 detail 下（接口回的是 {deleted, detail:{...}}）
        stats = r.json()["detail"]
        assert stats.get("conversations_deleted") == 1
        assert stats.get("conversation_messages_deleted") == 1

        from app.db import SessionLocal
        from app.models import Conversation, ConversationMessage

        db = SessionLocal()
        try:
            assert db.query(Conversation).filter_by(id=cid).count() == 0
            assert db.query(ConversationMessage).filter_by(conversation_id=cid).count() == 0
        finally:
            db.close()


class TestExportIncludesConversations:
    def test_export_contains_conversation_text(self, client):
        """"导出我的全部数据"不含对话就是一句不实描述。"""
        t = _signup(client, "conv-export@example.com")
        cid = _new_conv(client, t)
        _say(client, t, cid, "user", "这句话必须出现在导出里")

        data = client.get("/api/auth/me/export", headers=_h(t)).json()
        assert "conversations" in data, "导出结构里根本没有 conversations 这一节"
        texts = [m["content"] for c in data["conversations"] for m in c["messages"]]
        assert "这句话必须出现在导出里" in texts


class TestLimits:
    def test_rejects_absurdly_long_message(self, client):
        """一次粘贴整本 BP 就能把单行撑到几 MB，之后每次打开都要全量拉回。"""
        t = _signup(client, "conv-len@example.com")
        cid = _new_conv(client, t)
        assert _say(client, t, cid, "user", "x" * 100_001).status_code == 422
        # 反向对照：确认上限之内是放行的，别把闸门设成"什么都不让过"
        assert _say(client, t, cid, "user", "x" * 5_000).status_code == 200

    def test_rejects_unknown_role(self, client):
        t = _signup(client, "conv-role@example.com")
        cid = _new_conv(client, t)
        assert _say(client, t, cid, "wheel", "提权").status_code == 422
