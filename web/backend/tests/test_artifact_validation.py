"""创建评审时的材料包形状校验。

这条链路此前完全没有结构校验：artifact 只声明成 `dict`。形状写错时的实际
表现（实测踩过一次）是——

    POST /api/v2/reviews  {"artifact": {"text": "月费 99 元"}}
      → 200，评审入队
      → 跑到最后抛 AllPersonasFailedError
      → 错误消息：「本次没有任何人格进入评审（预设面板为空，或全部被证据
        预检跳过）」

那句话指向的是人格面板，而真正的原因是材料里根本没有 materials 数组
（evidence_precheck.load_evidence_types 只读这个键）。接入方会照着提示去查
人格配置，方向完全是错的；同时已经白占了一次配额，真跑起来还要产生模型费用。

所以这里守两件事：
  1. 错的形状必须在**入队前**被拒，且错误消息要说清楚该怎么改
  2. 对的形状不许被误伤——校验写紧了会把正常评审也挡掉，那比不校验更糟

最容易被忽略的是第 2 类里的图片材料：它没有 text 字段（正文在 image_data
里），一条"必须有 text"的规则会把所有带图评审全部挡死。
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    yield


def _token(client, email="artifact-validation@example.com"):
    """注册 + 登录 + 存一把 key。

    key 是必须的：resolve_llm_key 是 FastAPI 依赖，在**函数体之前**就执行，
    没有 key 时一律 428（"绝不返回模拟数据"）。不存 key 的话请求根本走不到
    材料校验那一步，测出来的全是 428——那样这个文件测的就不是它要测的东西。
    """
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "password123"}
    ).json()["token"]
    client.post(
        "/api/keys",
        json={"api_key": "sk-ant-artifact-validation-0123456789", "provider": "anthropic"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token


def _create(client, token, artifact, task_type="pricing_page_review"):
    return client.post(
        "/api/v2/reviews",
        json={"task_type": task_type, "artifact": artifact, "mode": "quick"},
        headers={"Authorization": f"Bearer {token}"},
    )


class TestRejectsBadShapes:
    """错的形状要当场拒，不能收下之后跑到最后才失败。"""

    def test_missing_materials_is_rejected_with_actionable_message(self, client):
        """**本文件的核心用例**：实测踩过的就是这一个。"""
        r = _create(client, _token(client), {"text": "月费 99 元"})
        assert r.status_code == 400, (
            "缺 materials 的材料包被收下了——评审会入队、占配额、跑到最后才失败，"
            "而错误消息会指向人格面板而不是材料形状。"
        )
        msg = r.json()["error"]["message"]
        # 错误消息必须能直接照着改，而不只是说"不合法"
        assert "materials" in msg
        assert '"type": "text"' in msg or '"text"' in msg, (
            f"错误消息没给出正确形状，接入方无从下手：{msg}"
        )

    def test_empty_materials_is_rejected(self, client):
        r = _create(client, _token(client), {"title": "x", "materials": []})
        assert r.status_code == 400

    def test_materials_not_a_list_is_rejected(self, client):
        r = _create(client, _token(client), {"materials": {"type": "text", "text": "x"}})
        assert r.status_code == 400

    def test_material_without_type_is_rejected(self, client):
        r = _create(client, _token(client), {"materials": [{"text": "月费 99 元"}]})
        assert r.status_code == 400
        assert "type" in r.json()["error"]["message"]

    def test_text_material_with_wrong_content_key_is_rejected(self, client):
        """用 content 而不是 text —— 这是最危险的一种写错。

        它能过证据预检（预检只看 type），于是人格照常被调起、照常计费，
        只是每个人拿到的正文都是空的，最后产出一份**基于空白的报告**。
        比直接失败更糟：没有任何地方会报错，而报告看起来是正常的。
        """
        r = _create(client, _token(client), {"materials": [{"type": "text", "content": "月费 99 元"}]})
        assert r.status_code == 400, (
            "用 content 当正文字段名被放行了——人格会收到空材料，"
            "照样调模型、照样计费，产出一份基于空白的报告，且全程无警告。"
        )
        assert "text" in r.json()["error"]["message"]

    def test_image_material_without_data_is_rejected(self, client):
        r = _create(client, _token(client), {"materials": [{"type": "image"}]})
        assert r.status_code == 400
        assert "image_data" in r.json()["error"]["message"]


class TestAcceptsValidShapes:
    """对的形状不许被误伤——校验写紧了比不校验更糟。"""

    def test_frontend_real_shape_is_accepted(self, client):
        """AskPage.tsx 真实发出的形状（materials 用 text 字段）。

        这条是防回归的关键：任何让它变红的校验改动，都意味着线上所有
        对话评审当场全挂。
        """
        r = _create(
            client,
            _token(client),
            {"title": "SaaS 定价页", "materials": [{"type": "text", "text": "月费 99 元，无免费版"}]},
        )
        # 202 = 异步入队（这条链路的正常成功码），402 = 配额用尽（形状是对的）
        assert r.status_code in (200, 201, 202, 402), (
            f"前端真实形状被拒了（{r.status_code}）：{r.text[:200]}"
        )

    def test_image_material_is_accepted_without_text(self, client):
        """图片材料没有 text 字段，正文在 image_data 里。

        一条"所有材料都必须有 text"的规则会把带图评审全部挡死——
        而带图正是这个产品的卖点之一（截图评审）。
        """
        r = _create(
            client,
            _token(client),
            {"materials": [{"type": "image", "image_data": "data:image/png;base64,iVBORw0KGgo="}]},
        )
        assert r.status_code != 400, f"图片材料被误伤了：{r.text[:200]}"

    def test_description_also_works_as_body(self, client):
        """引擎读的是 `description or text`，两个都算有正文。

        钉住这一点是因为 Wizard 链路与素材提取器产出的材料用的是 description。
        只认 text 会把那条链路挡掉。
        """
        r = _create(client, _token(client), {"materials": [{"type": "text", "description": "月费 99 元"}]})
        assert r.status_code != 400, f"description 形态被误伤了：{r.text[:200]}"

    def test_mixed_text_and_image_is_accepted(self, client):
        r = _create(
            client,
            _token(client),
            {
                "materials": [
                    {"type": "text", "text": "这是我的定价页"},
                    {"type": "image", "image_data": "data:image/png;base64,iVBORw0KGgo="},
                ]
            },
        )
        assert r.status_code != 400


class TestValidationHappensBeforeQuota:
    def test_bad_shape_does_not_consume_quota(self, client, monkeypatch):
        """形状错了不该白占一次配额。

        check_quota 在放行的瞬间就预留名额（_reserve_review_slot）。
        校验若放在它之后，用户传错一次形状就白白损失一次额度——
        而他根本没得到任何评审。
        """
        from app.services import quota_service

        called = {"n": 0}
        original = quota_service.check_quota

        def _spy(*a, **kw):
            called["n"] += 1
            return original(*a, **kw)

        monkeypatch.setattr(quota_service, "check_quota", _spy)

        r = _create(client, _token(client), {"text": "形状错的材料"})
        assert r.status_code == 400
        assert called["n"] == 0, (
            "材料形状校验发生在配额检查之后——传错形状会白占一次配额，"
            "而用户什么都没拿到。"
        )
