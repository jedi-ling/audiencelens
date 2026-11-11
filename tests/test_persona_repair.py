"""人格交卷没过校验时的修复轮（2026-11-04 Sonnet 5.5 诊断之后加的）。

诊断结论（docs/evaluation/runs/2026-11-04-sonnet55-before-fix/notes.md）：
  · schema_failure：模型确实调用了提交工具，但工具输入是残缺的——evidence 被写成
    一段带 `<parameter name="content">` 标签的字符串，后面的 scores / key_issues
    整段丢失。原样重发 3 次，同一位人格每次交回同一种残缺输入。
  · hallucination：标成 direct 的"证据"其实是改写、概括或人格自己的判断，原文里
    找不到逐字出处——不是归一化（全角/半角、空白）造成的误报。

所以修复不是放宽校验，而是**把校验器的具体错误回喂给模型**，只给一次机会。
"""

import copy
import json
import sys

import pytest
import yaml

sys.path.insert(0, "src")

import runner.cli as cli  # noqa: E402
from runner.persona_agent import estimate_cost  # noqa: E402
from runner.validator import validate_evidence_grounding  # noqa: E402

MATERIAL = "《深渊回响》是一款黑白水墨风格的银河城探索游戏。你扮演一名失忆的潜水员。"
QUOTE_OK = "黑白水墨风格的银河城探索游戏"
QUOTE_BAD = "页面全程未提及任何同类作品"
MODEL = "claude-sonnet-5-5"


@pytest.fixture
def budget():
    with open("src/config/budget.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def persona():
    with open("src/personas/game-core.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["personas"][0]


@pytest.fixture
def schema():
    return cli.load_schema("src/schemas/output-schema.json")


def _valid_output(persona, quote=QUOTE_OK):
    out = cli._build_simulated_output(persona, "steam_page_review")
    out.pop("meta", None)
    for ev in out.get("evidence") or []:
        ev["content"] = "我的观察：" + quote[:12]
        ev["quote"] = quote
        ev["inference_level"] = "direct"
    return out


class FakeModel:
    """按顺序交回预设的输出；记下每次调用的 kwargs。"""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        blocks = kwargs.get("response_blocks")
        if blocks is not None:
            blocks.append({"type": "tool_use", "id": f"toolu_{len(self.calls)}", "name": "submit_review", "input": item})
        return json.dumps(item, ensure_ascii=False), 1000, 500


def _run(monkeypatch, fake, persona, budget, schema):
    monkeypatch.setattr(cli, "chat_completion", fake)
    monkeypatch.setattr(cli, "_backoff_sleep", lambda *a, **k: None)
    config = {"budget": budget, "persona_prompt_path": "src/templates/persona-prompt.md"}
    return cli.run_single_persona(
        persona, "steam_page_review", "summary", [MATERIAL], config,
        {"title": "深渊回响", "materials": [{"type": "text", "text": MATERIAL}]},
        api_key="test-key", provider="anthropic", model_override=MODEL,
        retry_settings=cli._retry_settings(budget), output_schema=schema,
    )


def test_fixture_output_is_valid(persona, schema):
    """前提：测试用的"好答卷"本身能过三层校验，否则下面的断言没有意义。"""
    v = cli.validate_output(_valid_output(persona), persona, schema, [MATERIAL])
    assert cli._validation_failure_reason(v) is None, v


def test_missing_fields_get_one_repair_turn_with_the_errors(monkeypatch, persona, budget, schema):
    broken = {k: v for k, v in _valid_output(persona).items() if k not in ("scores", "key_issues")}
    fake = FakeModel([broken, _valid_output(persona)])
    r = _run(monkeypatch, fake, persona, budget, schema)

    assert len(fake.calls) == 2
    assert fake.calls[0]["repair"] is None
    repair = fake.calls[1]["repair"]
    assert "scores" in repair["feedback"] and "key_issues" in repair["feedback"]
    # 回放的是上一次的原始响应块，不是重新编一个
    assert repair["assistant_content"][0]["id"] == "toolu_1"
    assert cli._validation_failure_reason(r["validation"]) is None
    assert r["retries"] == 1 and r["retry_reasons"] == ["schema_failure"]


def test_hallucination_retry_feeds_back_the_ungrounded_quotes(monkeypatch, persona, budget, schema):
    fake = FakeModel([_valid_output(persona, QUOTE_BAD), _valid_output(persona)])
    r = _run(monkeypatch, fake, persona, budget, schema)

    feedback = fake.calls[1]["repair"]["feedback"]
    assert QUOTE_BAD in feedback
    assert "inferred" in feedback and "逐字" in feedback
    assert cli._validation_failure_reason(r["validation"]) is None
    assert r["retry_reasons"] == ["hallucination"]


def test_retry_cap_is_one_per_persona(monkeypatch, persona, budget, schema):
    bad = _valid_output(persona, QUOTE_BAD)
    fake = FakeModel([copy.deepcopy(bad), copy.deepcopy(bad), copy.deepcopy(bad)])
    r = _run(monkeypatch, fake, persona, budget, schema)

    assert len(fake.calls) == 2, "超过 1 次重试就是在烧钱"
    assert r["retries"] == 1
    assert cli._validation_failure_reason(r["validation"]) == "hallucination"


def test_both_attempts_are_billed(monkeypatch, persona, budget, schema):
    fake = FakeModel([_valid_output(persona, QUOTE_BAD), _valid_output(persona)])
    r = _run(monkeypatch, fake, persona, budget, schema)

    one = estimate_cost(1000, 500, MODEL, budget, cache_breakdown={})
    assert r["cost"] == pytest.approx(2 * one)
    assert r["input_tokens"] == 2000 and r["output_tokens"] == 1000


def test_transport_retry_is_a_plain_resend(monkeypatch, persona, budget, schema):
    from runner.llm_client import LLMCallError

    fake = FakeModel([LLMCallError("overloaded", retryable=True), _valid_output(persona)])
    r = _run(monkeypatch, fake, persona, budget, schema)

    assert len(fake.calls) == 2
    assert fake.calls[1]["repair"] is None
    assert r["retry_reasons"] == ["transport_error"]


def test_retry_config_and_grounding_threshold_unchanged(budget):
    retry = budget["retry"]
    assert retry["max_retries_per_persona"] == 1
    assert set(retry["retry_on"]) == {"transport_error", "schema_failure", "hallucination"}

    def evidence(n_bad, n_total=10):
        items = [{"content": "观察", "quote": QUOTE_BAD if i < n_bad else QUOTE_OK, "inference_level": "direct"}
                 for i in range(n_total)]
        return validate_evidence_grounding({"evidence": items}, [MATERIAL])

    # 30% 门槛不动：恰好 30% 不算落地，20% 算
    assert evidence(3)["grounded"] is False
    assert evidence(2)["grounded"] is True


def test_repair_turn_replays_blocks_and_answers_every_tool_use():
    from runner.llm_client import STRUCTURED_OUTPUT_TOOL_NAME, _repair_messages

    previous = [
        {"type": "thinking", "thinking": "", "signature": "sig-abc"},
        {"type": "tool_use", "id": "toolu_a", "name": STRUCTURED_OUTPUT_TOOL_NAME, "input": {}},
        {"type": "tool_use", "id": "toolu_b", "name": STRUCTURED_OUTPUT_TOOL_NAME, "input": {}},
    ]
    msgs = _repair_messages([{"role": "user", "content": "原始提示"}],
                            {"assistant_content": previous, "feedback": "缺 scores"})

    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"] == previous, "上一次的响应块（含 thinking 签名）必须原样回放"
    results = [b for b in msgs[2]["content"] if b["type"] == "tool_result"]
    assert [b["tool_use_id"] for b in results] == ["toolu_a", "toolu_b"]
    assert all(b["is_error"] for b in results)
    assert msgs[2]["content"][-1]["type"] == "text"


def test_repair_without_previous_blocks_appends_feedback():
    from runner.llm_client import _repair_messages

    msgs = _repair_messages([{"role": "user", "content": "原始提示"}], {"feedback": "请重新提交"})
    assert len(msgs) == 1 and msgs[0]["content"].endswith("请重新提交")


def test_hallucination_feedback_names_the_uncovered_part(monkeypatch, persona, budget, schema):
    # 覆盖率规则：一句真引用后面接一句原文没有的话。回喂里要点名的是**没找到的那一段**，
    # 而不是只把整条甩回去——模型才知道该删哪半句。
    half_true = QUOTE_OK + "，并且首发支持四人联机"
    fake = FakeModel([_valid_output(persona, half_true), _valid_output(persona)])
    r = _run(monkeypatch, fake, persona, budget, schema)

    feedback = fake.calls[1]["repair"]["feedback"]
    assert half_true in feedback          # 被点名的是 quote 原文
    assert "evidence 第 1 条" in feedback  # 并且说清是哪一条
    uncovered_line = next(ln for ln in feedback.splitlines() if ln.strip().startswith("原文里找不到的部分"))
    assert "首发支持四人联机" in uncovered_line
    assert QUOTE_OK not in uncovered_line
    assert r["retry_reasons"] == ["hallucination"]
    assert cli._validation_failure_reason(r["validation"]) is None


def test_true_quote_plus_fabrication_no_longer_passes_grounding():
    # 外部评审的探针：旧规则下只要有一个片段命中，整条就算落地。
    out = validate_evidence_grounding(
        {"evidence": [{"content": "观察", "quote": QUOTE_OK + "，并且首发支持四人联机", "inference_level": "direct"}]}, [MATERIAL])
    assert out["grounded"] is False
    assert out["hallucination_risk"] == 1.0  # 键名兼容保留；含义是未落地条目占比


# ---- 工具输入损坏：evidence 是一段工具调用标记字符串，不是列表（2026-11-11 实测 P15） ----

MARKUP_EVIDENCE = '\n<invoke name="x"></invoke>\n'


def test_markup_string_evidence_is_schema_failure_not_role_drift(persona, schema):
    broken = _valid_output(persona)
    broken["evidence"] = MARKUP_EVIDENCE
    from runner.persona_agent import normalize_persona_output

    out = normalize_persona_output(copy.deepcopy(broken))
    assert out["evidence"] == MARKUP_EVIDENCE, "不得被归一化成一条 inferred 证据"
    v = cli.validate_output(out, persona, schema, [MATERIAL])
    assert cli._validation_failure_reason(v) == "schema_failure"
    errors = v["details"]["schema"]["errors"]
    assert errors[0].startswith("evidence: 收到的是一段含工具调用标记的字符串")
    assert not any("is not of type" in e and e.startswith("evidence") for e in errors), "不回显那段标记"
    assert "<invoke" not in errors[0].split("——")[0]


def test_markup_string_evidence_gets_the_normal_repair_turn(monkeypatch, persona, budget, schema):
    broken = _valid_output(persona)
    broken["evidence"] = MARKUP_EVIDENCE
    fake = FakeModel([broken, _valid_output(persona)])
    r = _run(monkeypatch, fake, persona, budget, schema)

    assert len(fake.calls) == 2
    assert r["retry_reasons"] == ["schema_failure"]
    feedback = fake.calls[1]["repair"]["feedback"]
    assert "evidence: 收到的是一段含工具调用标记的字符串" in feedback
    assert cli._validation_failure_reason(r["validation"]) is None


def test_markup_string_key_issues_is_handled_the_same_way(persona, schema):
    broken = _valid_output(persona)
    broken["key_issues"] = '<parameter name="title">标题</parameter>'
    from runner.persona_agent import normalize_persona_output

    v = cli.validate_output(normalize_persona_output(broken), persona, schema, [MATERIAL])
    assert cli._validation_failure_reason(v) == "schema_failure"
    assert any(e.startswith("key_issues: 收到的是一段含工具调用标记的字符串") for e in v["details"]["schema"]["errors"])


def test_plain_sentence_evidence_is_still_wrapped_not_rejected():
    # 只有带工具调用标记的字符串才算"损坏"。整个字段写成一句普通的话仍按原口径包成一条证据。
    from runner.persona_agent import normalize_persona_output

    out = normalize_persona_output({"evidence": "整体就一句话"})
    assert out["evidence"][0]["content"] == "整体就一句话"
    assert out["evidence"][0]["inference_level"] == "inferred"


def test_well_formed_over_inferred_output_is_still_role_drift(monkeypatch, persona, budget, schema):
    # 40% 上限和 role_drift 的口径不动：形状完好、但推断确实过多的答卷照旧是 role_drift，
    # 而且照旧不重试（retry_on 里没有 role_drift）。
    over = _valid_output(persona)
    over["evidence"] = (
        [{"content": "观察", "quote": QUOTE_OK, "inference_level": "direct"}]
        + [{"content": f"推断 {i}", "inference_level": "inferred", "inference_basis": "经验"} for i in range(4)]
    )
    v = cli.validate_output(copy.deepcopy(over), persona, schema, [MATERIAL])
    assert cli.blocking_schema_errors(v["details"]["schema"]["errors"]) == []
    assert cli._validation_failure_reason(v) == "role_drift"
    assert any("推断过度" in issue for issue in v["details"]["role"]["issues"])

    fake = FakeModel([over, _valid_output(persona)])
    r = _run(monkeypatch, fake, persona, budget, schema)
    assert len(fake.calls) == 1, "role_drift 不在 retry_on 里，不应触发修复轮"
    assert cli._validation_failure_reason(r["validation"]) == "role_drift"
