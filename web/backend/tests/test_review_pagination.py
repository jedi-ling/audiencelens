"""GET /api/reviews 的分页契约。

背景：后端一直是 offset/limit 分页、默认一页 20 条，但前端从不传参数、也没有
翻页 UI——用户跑到第 21 次评审之后，旧评审在界面上就等于消失了，还没有任何提示。
修法是给列表接口补一个 `X-Total-Count` 响应头，前端据此显示"共 N 条 / 已显示 M 条"
并翻页。这里锁住三件事：

  1. 头确实回了，且数值 == 该身份名下的真实总数（不是本页条数）
  2. offset/limit 真的翻得动，且分页只按身份算总数，不串号
  3. body 仍然是**数组**、仍然是瘦身字段——不能因为要加总数就把 body 换成信封
     （那会一次性打断所有既有调用方），也不能把上一轮的列表瘦身改回去
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _cleanup(db):
    from app.models import Review, User

    yield
    db.query(Review).delete()
    db.query(User).delete()
    db.commit()


def _seed(db, count, user_id="anonymous", title_prefix="评审"):
    """直接落库造历史数据——本文件测的是分页，不该顺带跑一遍评审引擎。

    created_at 逐条递增，配合接口的 created_at DESC 排序，序号大的排在前面，
    这样"第 2 页拿到的是更旧的那批"可以被精确断言。
    """
    from app.models import Review

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ids = []
    for i in range(count):
        row = Review(
            id=str(uuid.uuid4()),
            user_id=user_id,
            task_type="concept_review",
            target_title=f"{title_prefix}-{i:03d}",
            artifact_bundle={"title": f"{title_prefix}-{i:03d}", "materials": []},
            status="completed",
            created_at=base + timedelta(minutes=i),
        )
        db.add(row)
        ids.append(row.id)
    db.commit()
    return ids


class TestReviewListPagination:
    def test_total_count_header_is_full_total_not_page_size(self, client, db):
        """25 条数据、一页 20 条：头里必须是 25，否则前端算出的"还有几条"是错的。"""
        _seed(db, 25)

        r = client.get("/api/reviews")
        assert r.status_code == 200
        assert len(r.json()) == 20  # 后端默认 limit
        assert r.headers["X-Total-Count"] == "25"

    def test_offset_limit_walks_the_whole_list(self, client, db):
        """两页拼起来 == 全量，且没有重复、没有漏。
        这正是用户报的"第 21 条以后消失"——现在必须翻得到。"""
        _seed(db, 25)

        page1 = client.get("/api/reviews?offset=0&limit=20").json()
        page2 = client.get("/api/reviews?offset=20&limit=20").json()

        assert len(page1) == 20
        assert len(page2) == 5
        ids = [row["id"] for row in page1 + page2]
        assert len(set(ids)) == 25

        # created_at DESC：最新的（序号 024）在第一页首位，最旧的（000）在第二页末位
        assert page1[0]["target_title"] == "评审-024"
        assert page2[-1]["target_title"] == "评审-000"

    def test_empty_list_reports_zero(self, client):
        r = client.get("/api/reviews")
        assert r.json() == []
        assert r.headers["X-Total-Count"] == "0"

    def test_total_counts_only_my_reviews(self, client, db, monkeypatch):
        """总数必须和列表用同一个归属过滤——否则"共 N 条"里混进别人的评审，
        用户翻到底也凑不齐那个 N。"""
        monkeypatch.setattr(settings, "auth_enabled", True)

        assert client.post(
            "/api/auth/register", json={"email": "pager@example.com", "password": "password123"}
        ).status_code == 200
        token = client.post(
            "/api/auth/login", json={"email": "pager@example.com", "password": "password123"}
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/api/auth/me", headers=headers).json()

        _seed(db, 3, user_id=me["user_id"], title_prefix="我的")
        _seed(db, 7, user_id="someone-else", title_prefix="别人的")

        r = client.get("/api/reviews", headers=headers)
        assert r.headers["X-Total-Count"] == "3"
        assert all(row["target_title"].startswith("我的") for row in r.json())

    def test_body_stays_a_slim_array(self, client, db):
        """加总数没有把 body 换成 {items,total} 信封（会打断既有调用方），
        也没有把上一轮的列表瘦身改回去（列表不该带整份报告和 base64 材料）。"""
        _seed(db, 1)

        body = client.get("/api/reviews").json()
        assert isinstance(body, list)
        row = body[0]
        for leaked in ("artifact_bundle", "report_json", "report_markdown", "persona_outputs"):
            assert leaked not in row, f"列表响应又把 {leaked} 带回来了"
