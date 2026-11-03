# -*- coding: utf-8 -*-
"""GET /api/reviews/{id}/result 的 HTML 报告必须真的能渲染出来。

这条链路整条死了很久：端点 import 的是 `runner.html_report`，而仓库里从来
没有这个模块（真实实现是 runner.aggregator.render_html_report）。ImportError
被一句 `except Exception: pass` 吞掉，于是 report_html 恒为 None，前端仍照常
摆着「导出 HTML」按钮、下发一张写着"尚未生成"的白页。

所以这里钉三件事：
  1. 正常路径真的产出 HTML（光断言"不报错"是不够的——原来的代码也不报错）；
  2. 渲染不出来时必须给出原因（html_error），不许再退回静默的 None；
  3. 匿名不给 HTML，但要说清是"要登录"而不是"报告坏了"。
"""

import uuid

import pytest

from app.config import settings
from app.models import Review


# 一份**完整**的 report_json。不能省字段：render_html_report 用
# report["consensus"] 这类硬下标取七个顶层键，缺一个就 KeyError。
# 这也正是匿名裁剪后的 json 渲染不出 HTML 的原因（见端点里的说明）。
FULL_REPORT = {
    "meta": {"task_type": "concept_review", "mode": "standard"},
    "executive_summary": {
        "primary_recommendation": "观望",
        "key_findings": ["一条发现"],
    },
    "consensus": [],
    "major_disagreements": [],
    "priority_fixes": [],
    "persona_notes": [
        {"persona_id": "P01", "persona_name": "林岚", "primary_stance": "观望"}
    ],
    "information_gaps": [],
    "next_human_test": [],
}


@pytest.fixture
def owner_client(client, monkeypatch):
    """一个真实登录账号——HTML 报告是完整报告的镜像，只对登录身份提供。"""
    monkeypatch.setattr(settings, "auth_enabled", True)
    email = f"html-{uuid.uuid4().hex[:12]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    payload = r.json()
    client.headers.update({"Authorization": f"Bearer {payload['token']}"})
    client.user_id = payload["user"]["id"]
    yield client
    client.headers.pop("Authorization", None)


def _make_completed(db, user_id):
    review = Review(
        user_id=user_id,
        task_type="concept_review",
        target_title="HTML 链路验证",
        artifact_bundle={"title": "HTML 链路验证", "materials": []},
        mode="standard",
        status="completed",
        report_json=FULL_REPORT,
        report_markdown="# 报告",
    )
    db.add(review)
    db.commit()
    return review


def test_render_html_report_is_importable_from_where_the_api_imports_it():
    """最直接的一条：模块路径写错过一次，就该有一条测试盯着它。

    单独列出来而不是只靠下面的端点测试，是因为 import 错误一旦再被
    某个 except 吞掉，端点测试的失败信息会变成"report_html 是 None"，
    看不出根因。
    """
    from runner.aggregator import render_html_report

    assert callable(render_html_report)


def test_result_endpoint_returns_real_html(owner_client, db):
    review = _make_completed(db, owner_client.user_id)
    body = owner_client.get(f"/api/reviews/{review.id}/result").json()

    assert body["html_error"] is None, body["html_error"]
    html = body["report_html"]
    assert html, "HTML 报告为空——这正是那条死链路的症状"
    # 断言它是渲染产物而不是任何占位串：模板渲染过就一定有 html 骨架
    assert "<html" in html.lower()


def test_render_failure_is_reported_not_swallowed(owner_client, db, monkeypatch):
    """渲染炸了要说原因。

    "拿不到 HTML" 和 "这份报告本来就没有 HTML" 在前端是两种完全不同的处理，
    只回一个 None 的话前端无从区分，只能继续把导出按钮亮着。
    """
    review = _make_completed(db, owner_client.user_id)

    import runner.aggregator

    def _boom(report, template_path):
        raise RuntimeError("模板变量对不上")

    monkeypatch.setattr(runner.aggregator, "render_html_report", _boom)

    body = owner_client.get(f"/api/reviews/{review.id}/result").json()
    assert body["report_html"] is None
    assert body["html_error"], "渲染失败被静默吞掉了"
    assert "模板变量对不上" in body["html_error"]


def test_anonymous_gets_a_reason_not_a_blank(client, db, monkeypatch):
    """匿名拿不到 HTML 是对的（它是整份报告的镜像，会绕过登录墙），
    但必须给一个**走得通的**解释，而不是留一片空白让人以为报告坏了：
      · 开认证 —— 指去登录；
      · 关认证（单机形态，页面没有登录入口）—— 如实说明该形态下不可用，
        不能指一条不存在的路（"登录后可查看"在这形态下是死路）。"""
    review = _make_completed(db, settings.anonymous_user_id)
    try:
        # 开认证时未登录访客是自己的游客，anonymous 行对他是 404（连解释都轮不到）
        monkeypatch.setattr(settings, "auth_enabled", True)
        assert client.get(f"/api/reviews/{review.id}/result").status_code == 404

        monkeypatch.setattr(settings, "auth_enabled", False)
        body = client.get(f"/api/reviews/{review.id}/result").json()
        assert body["report_html"] is None
        assert "登录" not in (body["html_error"] or "")
        assert "未开启账号体系" in (body["html_error"] or "")
    finally:
        db.delete(review)
        db.commit()
