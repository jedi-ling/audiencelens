"""钉住 Project（实体）与 Review.project_key（字符串标签）之间的单向桥接。

这是本仓刻意保留的"两套并存系统"，models/__init__.py 的 Project docstring
把设计写得很清楚，但**一条测试都没有守着它**——这正是它成为地雷的原因：
一份只存在于注释里的约定，下一个人完全可能当成 bug"顺手修掉"。

约定原文（models/__init__.py::Project）：
    · project_key —— Review 上的自由文本标签，靠字符串相同聚合
    · Project     —— 真实体，只挂在 Conversation 下
    · 对话创建评审时，把当时所在项目的名字顺手写进 review.project_key
    · 桥接是单向的，改项目名不会回填到已经生成的旧评审上
      （那些评审的 project_key 是一份独立的历史快照，不是实时视图）

三种可能的破坏方式，各自对应下面一组测试：

1. 有人觉得"改了项目名旧评审还显示旧名字是 bug"，于是加了回填逻辑。
   → 那会把历史快照改写成实时视图，语义完全不同（类似把发票地址改成
     用户当前地址）。TestRenameDoesNotBackfill 会红。

2. 有人重构 /ask 的评审创建流程时，把 project_key 那一行弄丢了。
   → 桥接断掉，从对话建的评审再也不进项目分组，而且**不报任何错**，
     只是历史页少了一个分组。TestBridgeWiringStillExists 会红。

3. 有人清理"没用的字段"时删掉了历史页的分组逻辑。
   → 桥接的消费端没了，写进去的 project_key 变成死数据。同上一组会红。

第 2、3 条的桥接实现在**前端**（AskPage.tsx 创建评审时拼 project_key），
后端测不到运行时行为，所以用源码断言——与本仓已有的
test_frontend_report_field_parity.py 等同一风格。
"""

import io
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FRONTEND_SRC = os.path.join(REPO_ROOT, "web", "frontend", "src")
ASK_PAGE = os.path.join(FRONTEND_SRC, "pages", "AskPage.tsx")
HISTORY_PAGE = os.path.join(FRONTEND_SRC, "pages", "ReviewHistoryPage.tsx")


def _read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


def _signup(client, email, password="password123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}
    ).json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


class TestRenameDoesNotBackfill:
    """改项目名不回填已生成的评审——这是有意的，不是遗漏。"""

    def test_renaming_project_leaves_existing_review_project_key_untouched(
        self, client, db
    ):
        from app.models import Review

        token = _signup(client, "bridge-rename@example.com")
        uid = client.get("/api/auth/me", headers=_h(token)).json()["user_id"]

        pid = client.post(
            "/api/v2/projects", json={"name": "猎户座"}, headers=_h(token)
        ).json()["id"]

        # 模拟"从属于该项目的对话里建了一次评审"——前端会把项目名写进 project_key
        review = Review(
            user_id=uid,
            task_type="concept_review",
            artifact_bundle={},
            status="completed",
            project_key="猎户座",
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        rid = review.id

        r = client.patch(
            f"/api/v2/projects/{pid}", json={"name": "天狼星"}, headers=_h(token)
        )
        assert r.status_code == 200
        assert r.json()["name"] == "天狼星"

        db.expire_all()
        assert db.get(Review, rid).project_key == "猎户座", (
            "改项目名把旧评审的 project_key 一起改了。这不是修 bug——"
            "project_key 是评审生成那一刻的历史快照（类似发票上的地址），"
            "不是项目名的实时视图。要改这个语义，先改 models 里 Project 的 docstring。"
        )

    def test_deleting_project_leaves_existing_review_project_key_untouched(
        self, client, db
    ):
        """删项目同理：已生成的评审保留它当时的分组名，不会变成"无项目"。"""
        from app.models import Review

        token = _signup(client, "bridge-del@example.com")
        uid = client.get("/api/auth/me", headers=_h(token)).json()["user_id"]
        pid = client.post(
            "/api/v2/projects", json={"name": "要被删掉的项目"}, headers=_h(token)
        ).json()["id"]

        review = Review(
            user_id=uid,
            task_type="concept_review",
            artifact_bundle={},
            status="completed",
            project_key="要被删掉的项目",
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        rid = review.id

        assert client.delete(f"/api/v2/projects/{pid}", headers=_h(token)).status_code == 200

        db.expire_all()
        assert db.get(Review, rid).project_key == "要被删掉的项目", (
            "删项目把历史评审的分组名也抹了——那些评审依然真实发生过，"
            "它们属于哪个项目是既成事实，不该随容器一起消失。"
        )


class TestProjectKeyRoundTrip:
    """project_key 原样存、原样回读——桥接的后端这一半。"""

    def test_project_key_survives_create_and_read(self, client, db):
        from app.models import Review

        token = _signup(client, "bridge-roundtrip@example.com")
        uid = client.get("/api/auth/me", headers=_h(token)).json()["user_id"]

        review = Review(
            user_id=uid,
            task_type="concept_review",
            artifact_bundle={},
            status="completed",
            project_key="移动端改版",
        )
        db.add(review)
        db.commit()
        db.refresh(review)

        # 两条读路径都要能拿到 —— 历史页走 v1，对话页走 v2
        v1 = client.get(f"/api/reviews/{review.id}", headers=_h(token)).json()
        v2 = client.get(f"/api/v2/reviews/{review.id}", headers=_h(token)).json()
        assert v1["project_key"] == "移动端改版"
        assert v2["project_key"] == "移动端改版", (
            "v2 详情端点没回 project_key —— 走 v2 的调用方看不到评审属于哪个项目"
        )


class TestBridgeWiringStillExists:
    """桥接的两端在前端源码里还接着。

    这两条是源码断言，不是运行时测试：桥接实现在前端，后端测不到。
    断言粒度刻意粗（只认关键标识符，不认具体写法），避免正常重构就误报。
    """

    def test_ask_page_still_writes_current_project_name_into_project_key(self):
        source = _read(ASK_PAGE)
        assert "activeProjectName" in source, (
            "AskPage.tsx 里没有 activeProjectName —— 桥接的写入端没了。"
            "从对话建的评审将不再带项目名，历史页的项目分组会静默消失。"
        )
        assert "project_key: activeProjectName()" in source, (
            "AskPage.tsx 创建评审时不再把当前项目名写进 project_key。"
            "这条线是 Project 实体与旧版评审历史分组之间唯一的桥——"
            "断了不会报错，只会让历史页少一个分组，很难被发现。"
        )

    def test_history_page_still_groups_by_project_key(self):
        source = _read(HISTORY_PAGE)
        assert "project_key" in source, (
            "ReviewHistoryPage.tsx 不再按 project_key 分组 —— 桥接的消费端没了，"
            "写进评审的 project_key 变成没人读的死数据。"
        )
