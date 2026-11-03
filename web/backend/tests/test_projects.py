"""项目：对话的分组容器（CC Desktop 风格侧栏）。

每条正向断言配反向对照。只测"能建能查"的话，下面这些实现同样能全绿，
而它们各自都是致命的：
  · 不校验归属 —— 任何人凭 id 读走/改走别人的项目
  · 归属校验回 403 —— 等于确认 id 存在，可用来枚举
  · 删项目连对话一起删 —— 应该是解绑回到"未分组"，不是数据丢失
  · PATCH 对话时"不传 project_id"和"显式传 null"混为一谈 —— 前者不该
    动归属，后者应该移回未分组，语义完全不同
  · 匿名建的项目登录后不认领 —— 对话认领了但项目没认领，
    对话会指向一个新账号读不到的项目
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


def _new_project(client, token, name="我的项目"):
    headers = _h(token) if token else {}
    r = client.post("/api/v2/projects", json={"name": name}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _new_conv(client, token=None):
    headers = _h(token) if token else {}
    r = client.post("/api/v2/conversations", json={"title": None}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


class TestCRUD:
    def test_create_and_list(self, client):
        t = _signup(client, "proj-a@example.com")
        pid = _new_project(client, t, "移动端改版")
        lst = client.get("/api/v2/projects", headers=_h(t)).json()["projects"]
        assert [p["id"] for p in lst] == [pid]
        assert lst[0]["name"] == "移动端改版"
        # 空项目的对话数必须是可核对的 0，不能是缺失字段
        assert lst[0]["conversation_count"] == 0

    def test_rejects_empty_name(self, client):
        t = _signup(client, "proj-empty@example.com")
        r = client.post("/api/v2/projects", json={"name": "   "}, headers=_h(t))
        assert r.status_code in (400, 422)

    def test_rename(self, client):
        t = _signup(client, "proj-rename@example.com")
        pid = _new_project(client, t, "旧名字")
        r = client.patch(f"/api/v2/projects/{pid}", json={"name": "新名字"}, headers=_h(t))
        assert r.status_code == 200
        assert r.json()["name"] == "新名字"

    def test_conversation_count_reflects_real_moves(self, client):
        """这个数字必须是现查的，不能是创建时缓存下来就不再变的假值。"""
        t = _signup(client, "proj-count@example.com")
        pid = _new_project(client, t)
        cid = _new_conv(client, t)
        client.patch(f"/api/v2/conversations/{cid}", json={"project_id": pid}, headers=_h(t))
        lst = client.get("/api/v2/projects", headers=_h(t)).json()["projects"]
        assert next(p for p in lst if p["id"] == pid)["conversation_count"] == 1


class TestOwnershipIsolation:
    def test_other_user_cannot_read_list_contents(self, client):
        a = _signup(client, "proj-o-a@example.com")
        b = _signup(client, "proj-o-b@example.com")
        _new_project(client, a, "A 的项目")
        titles = [p["name"] for p in client.get("/api/v2/projects", headers=_h(b)).json()["projects"]]
        assert titles == []

    def test_other_user_cannot_rename(self, client):
        a = _signup(client, "proj-rn-a@example.com")
        b = _signup(client, "proj-rn-b@example.com")
        pid = _new_project(client, a, "原名")
        r = client.patch(f"/api/v2/projects/{pid}", json={"name": "改名"}, headers=_h(b))
        # 反向对照：这里若是 200，就是任何人凭 id 改走别人的项目
        assert r.status_code == 404
        # 且必须是 404 而不是 403——403 等于确认该 id 存在
        assert r.status_code != 403
        assert client.get("/api/v2/projects", headers=_h(a)).json()["projects"][0]["name"] == "原名"

    def test_other_user_cannot_delete(self, client):
        a = _signup(client, "proj-del-a@example.com")
        b = _signup(client, "proj-del-b@example.com")
        pid = _new_project(client, a)
        assert client.delete(f"/api/v2/projects/{pid}", headers=_h(b)).status_code == 404
        assert len(client.get("/api/v2/projects", headers=_h(a)).json()["projects"]) == 1

    def test_cannot_move_own_conversation_into_someone_elses_project(self, client):
        """把任意项目 id 绑到自己的对话上，就能顺着这条关联探测别人的项目 id。"""
        a = _signup(client, "proj-mv-a@example.com")
        b = _signup(client, "proj-mv-b@example.com")
        pid_a = _new_project(client, a, "A 的项目")
        cid_b = _new_conv(client, b)
        r = client.patch(
            f"/api/v2/conversations/{cid_b}", json={"project_id": pid_a}, headers=_h(b)
        )
        assert r.status_code == 404
        got = client.get(f"/api/v2/conversations/{cid_b}", headers=_h(b)).json()
        assert got["project_id"] is None


class TestConversationProjectAssignment:
    def test_omitted_field_does_not_touch_project(self, client):
        """不传 project_id 时不该动归属——只改标题的请求不能顺带把项目清空。"""
        t = _signup(client, "proj-omit@example.com")
        pid = _new_project(client, t)
        cid = _new_conv(client, t)
        client.patch(f"/api/v2/conversations/{cid}", json={"project_id": pid}, headers=_h(t))
        client.patch(f"/api/v2/conversations/{cid}", json={"title": "改个标题"}, headers=_h(t))
        got = client.get(f"/api/v2/conversations/{cid}", headers=_h(t)).json()
        assert got["project_id"] == pid, "只传 title 时项目归属被意外清空了"
        assert got["title"] == "改个标题"

    def test_explicit_null_moves_to_ungrouped(self, client):
        t = _signup(client, "proj-null@example.com")
        pid = _new_project(client, t)
        cid = _new_conv(client, t)
        client.patch(f"/api/v2/conversations/{cid}", json={"project_id": pid}, headers=_h(t))
        r = client.patch(
            f"/api/v2/conversations/{cid}", json={"project_id": None}, headers=_h(t)
        )
        assert r.status_code == 200
        assert r.json()["project_id"] is None

    def test_moving_into_nonexistent_project_is_404(self, client):
        t = _signup(client, "proj-404@example.com")
        cid = _new_conv(client, t)
        r = client.patch(
            f"/api/v2/conversations/{cid}", json={"project_id": "no-such-id"}, headers=_h(t)
        )
        assert r.status_code == 404
        assert client.get(f"/api/v2/conversations/{cid}", headers=_h(t)).json()["project_id"] is None


class TestDeletionUnlinksNotDeletes:
    def test_deleting_project_keeps_conversation_but_ungroups_it(self, client):
        t = _signup(client, "proj-keep@example.com")
        pid = _new_project(client, t)
        cid = _new_conv(client, t)
        client.patch(f"/api/v2/conversations/{cid}", json={"project_id": pid}, headers=_h(t))

        r = client.delete(f"/api/v2/projects/{pid}", headers=_h(t))
        assert r.status_code == 200
        assert r.json()["conversations_unlinked"] == 1

        # 反向对照：对话本身没有被删——如果实现错误地级联删除了对话，这里会 404
        got = client.get(f"/api/v2/conversations/{cid}", headers=_h(t))
        assert got.status_code == 200
        assert got.json()["project_id"] is None


class TestClaim:
    def test_anonymous_project_becomes_mine(self, client):
        pid = _new_project(client, None, "匿名期建的项目")
        t = _signup(client, "proj-claim@example.com")

        # 认领前：项目不在这个账号的列表里
        before = client.get("/api/v2/projects", headers=_h(t)).json()["projects"]
        assert all(p["id"] != pid for p in before)

        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"project_ids": [pid]},
            headers=_h(t),
        )
        assert r.status_code == 200
        assert r.json()["claimed_projects"] == [pid]

        after = client.get("/api/v2/projects", headers=_h(t)).json()["projects"]
        assert any(p["id"] == pid for p in after)

    def test_claiming_conversation_without_project_leaves_it_reachable(self, client):
        """认领对话与认领项目是独立两步——都做才不会出现"对话在、项目读不到"。"""
        pid = _new_project(client, None, "匿名项目")
        cid = _new_conv(client, None)
        client.patch(f"/api/v2/conversations/{cid}", json={"project_id": pid})

        t = _signup(client, "proj-claim2@example.com")
        # 只认领对话，不认领项目——复现"用户只点了认领对话"的场景
        client.post(
            "/api/auth/me/claim-reviews",
            json={"conversation_ids": [cid]},
            headers=_h(t),
        )
        got = client.get(f"/api/v2/conversations/{cid}", headers=_h(t)).json()
        # 以前这里是一个真实缺口：只认领对话时项目还留在匿名桶，从新账号查不到。
        # 现在认领搬的是当前游客名下的**全部**数据，对话和它的项目一起过来。
        assert got["project_id"] == pid
        proj_list = [p["id"] for p in client.get("/api/v2/projects", headers=_h(t)).json()["projects"]]
        assert pid in proj_list, "对话认领过来了，它所在的项目却查不到"

        # 现在把项目也认领上——两个都认领之后，归属才完全一致
        client.post(
            "/api/auth/me/claim-reviews",
            json={"project_ids": [pid]},
            headers=_h(t),
        )
        proj_list_after = [p["id"] for p in client.get("/api/v2/projects", headers=_h(t)).json()["projects"]]
        assert pid in proj_list_after

    def test_cannot_steal_another_users_project(self, client):
        a = _signup(client, "proj-steal-a@example.com")
        b = _signup(client, "proj-steal-b@example.com")
        pid = _new_project(client, a, "A 的")

        r = client.post(
            "/api/auth/me/claim-reviews",
            json={"project_ids": [pid]},
            headers=_h(b),
        )
        assert r.status_code == 200
        assert r.json()["claimed_projects"] == []
        assert pid in r.json()["rejected_projects"]
        assert client.get(f"/api/v2/projects", headers=_h(a)).json()["projects"][0]["id"] == pid


class TestExportAndDeletion:
    def test_export_includes_projects(self, client):
        t = _signup(client, "proj-export@example.com")
        _new_project(client, t, "要出现在导出里的项目")
        data = client.get("/api/auth/me/export", headers=_h(t)).json()
        assert "projects" in data
        assert any(p["name"] == "要出现在导出里的项目" for p in data["projects"])

    def test_deleting_account_removes_projects(self, client):
        t = _signup(client, "proj-acct-del@example.com")
        _new_project(client, t)
        _new_project(client, t)

        from app.api.platform import DELETE_CONFIRM_PHRASE

        r = client.post(
            "/api/auth/me/delete",
            json={"password": "password123", "confirm": DELETE_CONFIRM_PHRASE},
            headers=_h(t),
        )
        assert r.status_code == 200, r.text
        assert r.json()["detail"]["projects_deleted"] == 2
