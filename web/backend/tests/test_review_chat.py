"""报告出来后真对话的回归：追问评审团 / 跟具体人格聊，两条 thread 各自持久化上下文。

此前"多轮"只是拼接文本给无状态的意图解析用，报告产出后没有任何追问入口——
这里测的是新增的 /api/v2/reviews/{id}/chat，验证：上下文真的带进了后续请求
（不是每次从零开始），以及跟人格聊时人设真的进了 prompt。"""

import time

import pytest


@pytest.fixture(autouse=True)
def _cleanup_anonymous_key(db):
    """整个测试会话共用一个 sqlite 文件、不按测试回滚（见 conftest.py），
    save_user_key(db, "anonymous", ...) 是 upsert，不清理就会让后面断言
    "anonymous 没有 key" 的测试（如 test_v1_engine_hardening）跟着失败。"""
    yield
    from app.services import key_service

    key_service.delete_user_key(db, "anonymous")
    # 追问现在会给 anonymous 记 UsageRecord（见 TestChatQuotaAndUsage）。整个会话共用
    # 一个 sqlite 文件，不清就会污染别处"anonymous 用量为 0/未超额"的断言。
    from app.models import UsageRecord

    db.query(UsageRecord).filter(UsageRecord.user_id == "anonymous").delete()
    db.commit()


def _server_key(model=None):
    """伪造一个 source="server" 的解析结果——追问配额只对平台 key 生效，
    而测试里建评审用的是 BYOK key，必须显式换掉才测得到配额分支。"""
    from app.services.key_service import ResolvedKey

    return ResolvedKey(
        key="sk-ant-platform", source="server", provider="anthropic", model=model, api_base=None
    )


def _fake_result():
    return {
        "report": {
            "executive_summary": {
                "primary_recommendation": "谨慎推进",
                "release_risk": "中",
                "evidence_quality": "中",
            },
            "priority_fixes": [{"title": "定价不清晰", "severity": "high", "why_it_matters": "转化率低"}],
            "persona_notes": [
                {"persona_id": "P01-indie-core-operator", "persona_name": "林岚", "primary_stance": "观望"}
            ],
        },
        "markdown": "# r",
        "html": "",
        "calibration": {},
        "simulated": False,
        "cost_summary": {"total_cost": 0.1, "persona_count": 1, "skipped_count": 0},
    }


def _poll_job_until_terminal(client, job_id, timeout=15.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        resp = client.get("/api/jobs/{0}".format(job_id))
        job = resp.json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.1)
    raise AssertionError("job 未到终态: {0}".format(job))


def _make_completed_review(client, db, monkeypatch, key="sk-ant-chat-test"):
    from app.services import key_service

    import runner.cli

    monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
    key_service.save_user_key(db, "anonymous", key)

    r = client.post(
        "/api/v2/reviews",
        json={
            "task_type": "concept_review",
            "artifact": {"title": "t", "materials": [{"type": "text", "text": "x"}]},
            "persona_pack": "game-core",
        },
    )
    assert r.status_code == 202
    review_id = r.json()["review_id"]
    _poll_job_until_terminal(client, r.json()["job_id"])
    return review_id


class TestGeneralFollowUp:
    def test_followup_uses_report_context_and_persists_history(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch)

        captured_prompts = []

        def fake_chat_completion(**kw):
            captured_prompts.append(kw["prompt"])
            return ("这是回复", 10, 5)

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", fake_chat_completion)

        r1 = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "为什么定价扣分？"})
        assert r1.status_code == 200
        assert r1.json()["reply"]["role"] == "assistant"
        assert r1.json()["reply"]["content"] == "这是回复"
        assert "定价不清晰" in captured_prompts[0]  # 报告内容真的进了 prompt

        r2 = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "那怎么改？"})
        assert r2.status_code == 200
        # 第二轮的 prompt 里带着第一轮的问答——不是每次从零开始
        assert "为什么定价扣分" in captured_prompts[1]
        assert "这是回复" in captured_prompts[1]

        listed = client.get(f"/api/v2/reviews/{review_id}/chat").json()["messages"]
        assert len(listed) == 4  # 2轮 * (user+assistant)

    def test_review_not_completed_rejects_chat(self, client, db, monkeypatch):
        from app.services import key_service

        import runner.cli

        monkeypatch.setattr(runner.cli, "run_panel", lambda **kw: _fake_result())
        key_service.save_user_key(db, "anonymous", "sk-ant-pending-test")

        from app.models import Review

        review = Review(
            user_id="anonymous", task_type="concept_review", status="pending", artifact_bundle={}
        )
        db.add(review)
        db.commit()

        r = client.post(f"/api/v2/reviews/{review.id}/chat", json={"message": "还没跑完就问"})
        assert r.status_code == 400


class TestPersonaChat:
    def test_persona_chat_grounds_with_persona_profile(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-persona-chat")

        captured_prompts = []

        def fake_chat_completion(**kw):
            captured_prompts.append(kw["prompt"])
            return ("我觉得还行", 10, 5)

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", fake_chat_completion)

        r = client.post(
            f"/api/v2/reviews/{review_id}/chat",
            json={"message": "你为啥观望？", "persona_id": "P01-indie-core-operator"},
        )
        assert r.status_code == 200
        prompt = captured_prompts[0]
        assert "林岚" in prompt or "P01-indie-core-operator" in prompt
        assert "观望" in prompt  # 该人格当时的评审意见真的带进去了

        # 单独的 thread：跟评审团整体聊的历史查不到这条
        general = client.get(f"/api/v2/reviews/{review_id}/chat").json()["messages"]
        assert general == []
        persona_thread = client.get(
            f"/api/v2/reviews/{review_id}/chat?persona_id=P01-indie-core-operator"
        ).json()["messages"]
        assert len(persona_thread) == 2

    def test_unknown_persona_id_rejected(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-unknown-persona")
        r = client.post(
            f"/api/v2/reviews/{review_id}/chat",
            json={"message": "hi", "persona_id": "P99-not-real"},
        )
        assert r.status_code == 400


class TestAnonymousChatGating:
    """匿名用户能追问，但只给回复的体验版——完整内容已存进历史，
    登录后同一条 thread 直接展示完整版，不需要重新问一遍。"""

    def test_anonymous_reply_is_truncated_with_full_length(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-gate-test")

        long_reply = "这是一段足够长的真实回复内容，" * 10
        import runner.llm_client

        monkeypatch.setattr(
            runner.llm_client, "chat_completion", lambda **kw: (long_reply, 10, 5)
        )

        r = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "追问一下"})
        assert r.status_code == 200
        reply = r.json()["reply"]
        assert reply["is_gated"] is True
        assert len(reply["content"]) < len(long_reply)
        assert reply["full_length"] == len(long_reply)

    def test_stored_message_keeps_full_content_regardless_of_gating(self, client, db, monkeypatch):
        """裁剪只发生在返回给这次请求的内容——数据库里存的必须是完整回复，
        否则用户登录后"看完整"其实还是看不到。"""
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-gate-test2")

        long_reply = "完整未裁剪的真实回复内容，" * 10
        import runner.llm_client

        monkeypatch.setattr(
            runner.llm_client, "chat_completion", lambda **kw: (long_reply, 10, 5)
        )
        client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "追问一下"})

        from app.models import ReviewChatMessage

        stored = (
            db.query(ReviewChatMessage)
            .filter(ReviewChatMessage.review_id == review_id, ReviewChatMessage.role == "assistant")
            .one()
        )
        assert stored.content == long_reply  # 库里是完整内容，不是裁剪后的

    def test_short_reply_not_gated(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-gate-test3")

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: ("短回复", 5, 2))

        r = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "问"})
        reply = r.json()["reply"]
        assert reply["is_gated"] is False
        assert reply["content"] == "短回复"

    def test_user_own_question_never_gated(self, client, db, monkeypatch):
        """裁的是 AI 答了什么，用户自己发的问题原样保留（否则连自己问过什么都看不全）。"""
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-gate-test4")

        long_reply = "很长的回复内容，" * 15
        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: (long_reply, 10, 5))

        long_question = "这是我提出的一个比较长的追问问题内容，" * 5
        client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": long_question})

        listed = client.get(f"/api/v2/reviews/{review_id}/chat").json()["messages"]
        user_msg = next(m for m in listed if m["role"] == "user")
        assert user_msg["content"] == long_question
        assert user_msg["is_gated"] is False


class TestChatWithImages:
    """追问带图链路：此前 chat 接口只收文字，前端附件栏里的截图被静默丢弃。
    现在 images（data URI）拼成多模态内容块进 chat_completion，历史里存
    [附图×N] 标记（不存原图，data URI 太大）。"""

    _PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="

    def test_images_reach_chat_completion_as_content_blocks(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-img-test")

        captured = []
        import runner.llm_client

        monkeypatch.setattr(
            runner.llm_client, "chat_completion",
            lambda **kw: (captured.append(kw["prompt"]), ("看到了", 10, 5))[1],
        )

        r = client.post(
            f"/api/v2/reviews/{review_id}/chat",
            json={"message": "怎么说这个", "images": [self._PNG]},
        )
        assert r.status_code == 200
        prompt = captured[0]
        # 带图时 prompt 是内容块列表：文字块 + 图片块
        assert isinstance(prompt, list)
        assert prompt[0]["type"] == "text"
        assert prompt[1] == {"type": "image_url", "image_url": {"url": self._PNG}}

    def test_stored_user_message_marks_image_count(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-img-test2")

        import runner.llm_client

        monkeypatch.setattr(runner.llm_client, "chat_completion", lambda **kw: ("好", 5, 2))
        client.post(
            f"/api/v2/reviews/{review_id}/chat",
            json={"message": "看图", "images": [self._PNG, self._PNG]},
        )

        from app.models import ReviewChatMessage

        stored = (
            db.query(ReviewChatMessage)
            .filter(ReviewChatMessage.review_id == review_id, ReviewChatMessage.role == "user")
            .one()
        )
        assert stored.content == "[附图×2] 看图"

    def test_no_images_keeps_plain_string_prompt(self, client, db, monkeypatch):
        # 不带图时 prompt 保持纯字符串——不要为了统一把所有请求都变成内容块
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-img-test3")

        captured = []
        import runner.llm_client

        monkeypatch.setattr(
            runner.llm_client, "chat_completion",
            lambda **kw: (captured.append(kw["prompt"]), ("好", 5, 2))[1],
        )
        client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "纯文字"})
        assert isinstance(captured[0], str)

    def test_non_image_uris_filtered_out(self, client, db, monkeypatch):
        # 只认 data:image/*——javascript:/http:/文本一律丢弃（不给注入面）
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-img-test4")

        captured = []
        import runner.llm_client

        monkeypatch.setattr(
            runner.llm_client, "chat_completion",
            lambda **kw: (captured.append(kw["prompt"]), ("好", 5, 2))[1],
        )
        client.post(
            f"/api/v2/reviews/{review_id}/chat",
            json={"message": "混入脏数据", "images": ["javascript:alert(1)", "http://evil/x.png"]},
        )
        assert isinstance(captured[0], str)  # 全被过滤 → 退回纯文字


class TestChatQuotaAndUsage:
    """追问此前是条漏钱的路：只有限流、没有配额校验，token 拿到就丢（`_in_tok`）。
    结果是配额耗尽的用户能对任意一条已完成评审狂发追问烧平台 key，而 UsageRecord
    里一分钱都看不到——那道按累计成本触发的硬闸因此永远不会被触发。"""

    @staticmethod
    def _patch_llm(monkeypatch, tokens=(1000, 500), reply="回复"):
        calls = []
        import runner.llm_client

        def fake(**kw):
            calls.append(kw)
            return (reply, tokens[0], tokens[1])

        monkeypatch.setattr(runner.llm_client, "chat_completion", fake)
        return calls

    @staticmethod
    def _chat_usage_rows(db, review_id):
        from app.models import UsageRecord

        return (
            db.query(UsageRecord)
            .filter(UsageRecord.review_id == review_id, UsageRecord.kind == "chat")
            .all()
        )

    def test_token_and_cost_land_in_usage_record(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-usage-1")
        self._patch_llm(monkeypatch, tokens=(1000, 500))

        r = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "追问"})
        assert r.status_code == 200

        rows = self._chat_usage_rows(db, review_id)
        assert len(rows) == 1
        row = rows[0]
        # 断的是数值真的记下来了，不是"有一行"
        assert row.input_tokens == 1000
        assert row.output_tokens == 500
        assert row.cost_usd > 0  # estimate_cost 按 budget.yaml 的定价算出来的真实成本
        assert row.key_source == "byok"
        assert row.persona_count == 0

    def test_cost_uses_engine_pricing_table(self, client, db, monkeypatch):
        """成本口径必须与引擎侧同源（persona_agent.estimate_cost + budget.yaml），
        不能在追问链路另写一套算法，否则计费报表两套数对不上。"""
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-usage-2")
        self._patch_llm(monkeypatch, tokens=(2000, 1000))

        client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "追问"})

        import yaml

        from app.config import settings
        from app.services import BUDGET_PATH
        from runner.persona_agent import estimate_cost

        with open(BUDGET_PATH, "r", encoding="utf-8") as f:
            budget_config = yaml.safe_load(f)
        expected = estimate_cost(2000, 1000, settings.intent_model, budget_config)
        assert expected > 0
        assert self._chat_usage_rows(db, review_id)[0].cost_usd == pytest.approx(expected)

    def test_chat_does_not_consume_a_review_count(self, client, db, monkeypatch):
        """追问只计成本、不计次数：一次追问比一次完整评审便宜一到两个数量级，
        按次数扣会让"问两句就把当天评审额度问没了"，而追问恰恰是该鼓励的行为。"""
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-usage-3")
        self._patch_llm(monkeypatch)

        from app.services import quota_service

        before = quota_service.usage_summary(db, "anonymous")["reviews_used"]
        for _ in range(3):
            assert (
                client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "再问"}).status_code
                == 200
            )
        after = quota_service.usage_summary(db, "anonymous")
        assert after["reviews_used"] == before  # 次数没动
        assert after["cost_usd_total"] > 0  # 但钱记上了

    def test_exhausted_quota_rejects_chat_without_calling_llm(self, client, db, monkeypatch):
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-quota-1")
        calls = self._patch_llm(monkeypatch)

        from app.config import settings
        from app.services import key_service, quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(key_service, "resolve_key", lambda db, uid, provider="anthropic": _server_key())
        # 一笔就烧穿 free 档 $1/天 的成本硬闸
        quota_service.record_usage(db, "anonymous", kind="review", key_source="server", cost_usd=5.0)

        r = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "还想问"})
        assert r.status_code == 402
        assert calls == []  # 拦在调模型之前，一分钱都没花

    def test_byok_user_unaffected_by_exhausted_quota(self, client, db, monkeypatch):
        """BYOK 花的是用户自己的钱，与 check_quota 一致地豁免——别把豁免改坏。"""
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-quota-2")
        self._patch_llm(monkeypatch)

        from app.config import settings
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        quota_service.record_usage(db, "anonymous", kind="review", key_source="server", cost_usd=5.0)

        # resolve_key 不打桩：测试用户存的是自己的 key → source="byok"
        r = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "我用自己的 key"})
        assert r.status_code == 200

    def test_credits_mode_blocks_at_zero_balance_but_never_consumes(self, client, db, monkeypatch):
        """credits 模式下 quota_service.check_quota 会原子扣 1 次余额——对一次追问
        收一次完整评审的价钱不合理。这里只校验"有没有余额"，放行也不扣。"""
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-quota-3")
        self._patch_llm(monkeypatch)

        from app.config import settings
        from app.models import CreditLedger
        from app.services import cdk_service, key_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")
        monkeypatch.setattr(key_service, "resolve_key", lambda db, uid, provider="anthropic": _server_key())

        # 余额 0 → 402
        assert (
            client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "问"}).status_code == 402
        )

        db.add(CreditLedger(user_id="anonymous", delta=2, reason="cdk_redeem"))
        db.commit()
        assert (
            client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "问"}).status_code == 200
        )
        assert cdk_service.credit_balance(db, "anonymous") == 2  # 放行了但没扣次数

        db.query(CreditLedger).filter(CreditLedger.user_id == "anonymous").delete()
        db.commit()

    def test_credits_mode_still_has_a_cost_ceiling_for_chat(self, client, db, monkeypatch):
        """"追问不扣次数"不能等于"追问不封顶"。

        credits 模式下 usage_summary 的 cost_usd_limit 恒为 None（该模式没有每日
        成本闸），如果只校验"余额 > 0"，那么持有 1 次余额的用户就能对平台 key
        无限追问——发一张 CDK 等于送一条不封顶的补全通道。这里锁死兜底闸。
        """
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-quota-4")
        calls = self._patch_llm(monkeypatch)

        from app.config import settings
        from app.models import CreditLedger
        from app.services import cdk_service, key_service, quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "credits")
        monkeypatch.setattr(key_service, "resolve_key", lambda db, uid, provider="anthropic": _server_key())

        db.add(CreditLedger(user_id="anonymous", delta=1, reason="cdk_redeem"))
        db.commit()
        # 余额还在，但平台 key 上已经烧穿了套餐日成本上限
        quota_service.record_usage(db, "anonymous", kind="chat", key_source="server", cost_usd=5.0)

        n_before = len(calls)
        r = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "继续刷"})
        assert r.status_code == 402
        assert len(calls) == n_before  # 拦在调模型之前
        # 拦是因为成本，不是因为没余额——余额一次都没被扣
        assert cdk_service.credit_balance(db, "anonymous") == 1

        db.query(CreditLedger).filter(CreditLedger.user_id == "anonymous").delete()
        db.commit()

    def test_usage_write_failure_does_not_break_chat_but_is_logged(
        self, client, db, monkeypatch
    ):
        """用户已经拿到回复了，记账失败不该把追问也弄失败；但绝不静默吞掉。"""
        review_id = _make_completed_review(client, db, monkeypatch, key="sk-ant-usage-fail")
        self._patch_llm(monkeypatch, reply="照样回你")

        from app.services import quota_service

        def boom(*a, **kw):
            raise RuntimeError("usage_records 写入炸了")

        monkeypatch.setattr(quota_service, "record_usage", boom)

        # 直接盯 chat_service 用的那个 logger——app 的 audiencelens logger 不向 root
        # 传播，caplog 抓不到（抓不到会让这条断言永远绿，等于没测）。
        from app.services import chat_service

        warnings = []
        monkeypatch.setattr(
            chat_service.logger, "warning", lambda msg, *a, **kw: warnings.append(msg % a)
        )

        r = client.post(f"/api/v2/reviews/{review_id}/chat", json={"message": "问"})
        assert r.status_code == 200
        assert r.json()["reply"]["content"] == "照样回你"
        assert self._chat_usage_rows(db, review_id) == []
        # 失败必须留痕：这个仓库正在系统性清除 `except Exception: pass`
        assert any("记 usage 失败" in m for m in warnings)
