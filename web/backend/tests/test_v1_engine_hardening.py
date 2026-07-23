"""v1 评审引擎（ReviewService.run_review，Wizard/直接调 /api/reviews 的旧链路）加固回归。

此前的三个真问题（来自 2026-07-23 功能链路审计，均已逐一核实）：
  1. 直接读 os.environ 的 ANTHROPIC_API_KEY——用户在设置页存的 BYOK key 完全无效；
  2. 没有环境变量时静默把 _build_simulated_output 的占位数据当真实报告入库；
  3. WS 广播用 {type: ...} 老信封，前端 ws.ts 按 payload.event 判终态，永远判不到。

现在：key 走 key_service.resolve_key（与 v2 同源），无 key 直接 failed 绝不模拟，
WS 信封统一为 {event, data}。
"""

import sys
import time
from unittest.mock import patch

sys.path.insert(0, "src")


def _create_v1_review(client):
    r = client.post(
        "/api/reviews",
        json={
            "task_type": "concept_review",
            "artifact_bundle": {
                "title": "v1 加固验证",
                "materials": [{"type": "核心循环说明", "description": "探索-战斗-成长"}],
            },
        },
    )
    assert r.status_code == 200
    return r.json()["id"]


def _wait_terminal(client, review_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = client.get(f"/api/reviews/{review_id}").json()
        if detail["status"] in ("completed", "failed"):
            return detail
        time.sleep(0.1)
    raise AssertionError(f"review {review_id} 未到终态")


class TestV1RefusesSimulatedData:
    def test_no_key_marks_failed_instead_of_storing_simulated(self, client, monkeypatch):
        """无 key 时必须 failed + 明确错误信息——绝不把模拟占位数据当报告入库。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        review_id = _create_v1_review(client)
        detail = _wait_terminal(client, review_id)
        assert detail["status"] == "failed"
        # 报告字段必须为空——不能有任何模拟内容混进来
        assert not detail.get("report_json") or "error" in (detail.get("report_json") or {})


class TestV1UsesByokKey:
    def test_llm_call_receives_resolved_byok_key(self, client, db, monkeypatch):
        """v1 引擎的 LLM 调用必须拿到 key_service 解析出的 BYOK key/provider/api_base，
        而不是环境变量。"""
        from app.services import key_service

        key_service.save_user_key(
            db, "anonymous", "sk-byok-v1-test",
            provider="anthropic", api_base="https://relay.example.com/anthropic",
        )
        calls = []

        def fake_chat(**kwargs):
            calls.append(kwargs)
            raise RuntimeError("short-circuit")  # 拿到调用参数即达成目的，无需真跑

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", fake_chat)
        # run_review 内部是 from runner.llm_client import chat_completion（函数级导入），
        # 补丁打在模块属性上即可生效

        review_id = _create_v1_review(client)
        _wait_terminal(client, review_id)

        assert calls, "chat_completion 未被调用——v1 引擎没走统一 LLM 出口"
        assert calls[0]["api_key"] == "sk-byok-v1-test"
        assert calls[0]["provider"] == "anthropic"
        assert calls[0]["api_base"] == "https://relay.example.com/anthropic"


class TestMaterialExtractorByok:
    def test_no_resolved_key_skips_ai_never_touches_env(self, monkeypatch):
        """没解析到 key 时 AI 档直接跳过（走 fallback），即使环境变量里有 key 也不偷用。"""
        from app.services import MaterialExtractor

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-should-not-be-used")
        result = MaterialExtractor._extract_with_ai("concept_review", "some text", ["一句话pitch"])
        assert result is None

    def test_resolved_key_flows_into_chat_completion(self, monkeypatch):
        from app.services import MaterialExtractor
        from app.services.key_service import ResolvedKey

        calls = []

        def fake_chat(**kwargs):
            calls.append(kwargs)
            return ('{"title": "T", "materials": {"一句话pitch": "x"}}', 10, 5)

        with patch("runner.llm_client.chat_completion", side_effect=fake_chat):
            resolved = ResolvedKey(
                key="sk-extract-test", source="byok", provider="openai_compatible",
                model="deepseek-v4-pro", api_base="https://api.deepseek.com",
            )
            result = MaterialExtractor._extract_with_ai(
                "concept_review", "文档内容", ["一句话pitch"], resolved=resolved
            )

        assert result == {"title": "T", "materials": {"一句话pitch": "x"}}
        assert calls[0]["api_key"] == "sk-extract-test"
        assert calls[0]["provider"] == "openai_compatible"
        assert calls[0]["model"] == "deepseek-v4-pro"
