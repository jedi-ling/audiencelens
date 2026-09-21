# -*- coding: utf-8 -*-
"""WebSocket 的 origin 白名单：既不能把开发环境挡在门外，也不能放开生产。

实测过的缺陷：白名单硬写着 `http://127.0.0.1:5173`，而本仓库的开发前端跑在
**5199**（.claude/launch.json 与 web/frontend/vite.config.ts，AL_PUBLIC_WEB_URL
也默认 http://localhost:5199）。于是本地开发的握手被 4001 关掉，前端静默退化
成轮询——"实时进度"这条链路在开发机上从来没真正通过电，而没有任何报错。

两件事必须同时成立，所以正反两侧都要钉：
  · 配置里写了的地址（含 localhost / 127.0.0.1 两种写法）要能连上；
  · 没写过的地址一律拒绝——这道白名单挡的是跨站 WebSocket 劫持，
    为了修开发体验把它放开等于把防护删掉。
"""

import pytest

from app.config import settings
from app.websocket import ALLOWED_WS_ORIGINS, _loopback_aliases


class TestAllowlistDerivation:
    def test_public_web_url_is_included(self):
        """邮件链接、CORS 判定都用这个字段表示"本站前端在哪"，
        WS 白名单却曾经不看它——同一个部署里两套"谁是自己人"的说法。"""
        assert settings.public_web_url.rstrip("/") in ALLOWED_WS_ORIGINS

    def test_both_loopback_spellings_are_allowed(self):
        """localhost 与 127.0.0.1 是同一个开发服务器，浏览器却当成两个 origin
        （Origin 头逐字符比对）。只写一种，另一种就会被 4001 关掉。"""
        port = settings.public_web_url.rsplit(":", 1)[-1]
        assert f"http://localhost:{port}" in ALLOWED_WS_ORIGINS
        assert f"http://127.0.0.1:{port}" in ALLOWED_WS_ORIGINS

    def test_cors_origins_are_included_with_aliases(self):
        for origin in settings.cors_origins:
            assert origin.rstrip("/") in ALLOWED_WS_ORIGINS

    def test_only_loopback_names_get_aliased(self):
        """别名只对回环名生效。生产域名一个字符都不放宽——
        否则这个"顺手兼容"就成了白名单上的一个洞。"""
        assert _loopback_aliases("https://audiencelens.example.com") == {
            "https://audiencelens.example.com"
        }
        assert _loopback_aliases("") == set()

    def test_trailing_slash_is_normalized(self):
        """AL_PUBLIC_WEB_URL 很容易被填成带尾斜杠的形式，而 Origin 头永远没有。
        不归一化的话，运维填对了地址也连不上。"""
        assert _loopback_aliases("http://localhost:5199/") == {
            "http://localhost:5199",
            "http://127.0.0.1:5199",
        }


class TestHandshake:
    @pytest.fixture
    def review_id(self, db):
        from app.models import Review

        review = Review(
            user_id=None, task_type="concept_review", artifact_bundle={"title": "x"},
            status="pending",
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        yield review.id
        db.query(Review).filter(Review.id == review.id).delete()
        db.commit()

    def test_dev_origin_handshake_succeeds(self, client, review_id):
        """这条就是当初实测被 4001 关掉的那一个。"""
        with client.websocket_connect(
            f"/ws/review/{review_id}", headers={"origin": "http://127.0.0.1:5199"}
        ) as ws:
            assert ws is not None

    def test_unknown_origin_is_still_rejected(self, client, review_id):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/ws/review/{review_id}", headers={"origin": "https://evil.example.com"}
            ):
                pass
        assert exc.value.code == 4001, "未知 origin 必须仍然被拒（跨站 WS 劫持）"
