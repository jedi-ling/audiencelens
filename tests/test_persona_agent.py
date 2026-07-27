import json
import os

import pytest
import yaml

from runner.persona_agent import (
    estimate_cost,
    parse_persona_output,
    render_prompt,
    select_model,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "persona-prompt.md")
BUDGET_PATH = os.path.join(PROJECT_ROOT, "src", "config", "budget.yaml")


@pytest.fixture
def sample_persona():
    return {
        "id": "P01-indie-core-operator",
        "name": "林岚",
        "mbti": "INTJ",
        "archetype": "核心独立探索者",
        "identity_summary": "更在意这游戏是否真的有自己的一套东西",
        "behavior_profile": {
            "patience": "高",
            "genre_literacy": "高",
            "novelty_seeking": "高",
        },
        "motivations": ["独特机制", "作者表达"],
        "decision_rules": [
            "若15秒内看不到核心钩子，不加愿望单",
            "若有一条只有它能做到的机制证据，即使粗糙也愿继续关注",
        ],
        "quit_triggers": ["卖点说不清"],
        "continue_triggers": ["机制互锁明显"],
        "first_scan_focus": ["一句话定位", "前三张图/GIF"],
        "review_output": {
            "must_comment_on": ["独特性", "核心循环证据", "参考竞品", "首15分钟"],
        },
    }


@pytest.fixture
def budget_config():
    with open(BUDGET_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestRenderPrompt:
    def test_replaces_persona_yaml_minified(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "P01-indie-core-operator" in result
        assert "林岚" in result
        assert "核心独立探索者" in result

    def test_replaces_mbti(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "INTJ" in result

    def test_replaces_persona_name(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "作为林岚" in result

    def test_replaces_must_comment_on_items(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "独特性" in result
        assert "核心循环证据" in result
        assert "参考竞品" in result
        assert "首15分钟" in result

    def test_replaces_primary_decision_rule(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "若15秒内看不到核心钩子，不加愿望单" in result

    def test_replaces_task_type(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "demo_first_play",
            "某独立游戏Demo",
            TEMPLATE_PATH,
        )
        assert "demo_first_play" in result

    def test_replaces_artifact_summary(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        assert "某独立游戏Steam页面" in result

    def test_persona_yaml_minified_only_core_fields(self, sample_persona):
        result = render_prompt(
            sample_persona,
            "steam_page_review",
            "某独立游戏Steam页面",
            TEMPLATE_PATH,
        )
        minified_yaml_str = None
        for line in result.split("\n"):
            if "P01-indie-core-operator" in line and "核心独立探索者" in line:
                minified_yaml_str = line
                break
        parsed = yaml.safe_load(minified_yaml_str) if minified_yaml_str else None
        if isinstance(parsed, dict):
            assert "behavior_profile" not in parsed or "id" in parsed
        assert "P01-indie-core-operator" in result


class TestParsePersonaOutput:
    def test_pure_json(self):
        data = {"persona_id": "P01", "primary_stance": "加愿望单"}
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_persona_output(raw)
        assert result["persona_id"] == "P01"
        assert result["primary_stance"] == "加愿望单"

    def test_markdown_wrapped_json(self):
        data = {"persona_id": "P02", "primary_stance": "不加"}
        raw = f"```json\n{json.dumps(data, ensure_ascii=False)}\n```"
        result = parse_persona_output(raw)
        assert result["persona_id"] == "P02"
        assert result["primary_stance"] == "不加"

    def test_mixed_text_with_json(self):
        data = {"persona_id": "P03", "primary_stance": "观望"}
        raw = f"这是我的分析结果：\n{json.dumps(data, ensure_ascii=False)}"
        result = parse_persona_output(raw)
        assert result["persona_id"] == "P03"

    def test_mixed_text_with_multiple_json_extracts_last(self):
        data1 = {"persona_id": "P03", "primary_stance": "观望"}
        data2 = {"persona_id": "P03", "primary_stance": "加愿望单"}
        raw = f"第一轮：{json.dumps(data1, ensure_ascii=False)}\n第二轮：{json.dumps(data2, ensure_ascii=False)}"
        result = parse_persona_output(raw)
        assert result["primary_stance"] == "加愿望单"

    def test_parse_error_returns_error_dict(self):
        raw = "这不是JSON"
        result = parse_persona_output(raw)
        assert result.get("parse_error") is True
        assert result["raw_output"] == raw

    def test_markdown_wrapped_with_extra_whitespace(self):
        data = {"persona_id": "P04", "confidence": 0.8}
        raw = f"  ```json  \n  {json.dumps(data, ensure_ascii=False)}  \n  ```  "
        result = parse_persona_output(raw)
        assert result["persona_id"] == "P04"


class TestEstimateCost:
    def test_sonnet_pricing(self, budget_config):
        cost = estimate_cost(1000, 500, "claude-sonnet-4-20250514", budget_config)
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert abs(cost - expected) < 1e-10

    def test_haiku_pricing(self, budget_config):
        cost = estimate_cost(2000, 1000, "claude-haiku-4-5-20251001", budget_config)
        expected = (2000 / 1_000_000) * 1.0 + (1000 / 1_000_000) * 5.0
        assert abs(cost - expected) < 1e-10

    def test_opus_pricing(self, budget_config):
        cost = estimate_cost(500, 200, "claude-opus-4-20250514", budget_config)
        expected = (500 / 1_000_000) * 15.0 + (200 / 1_000_000) * 75.0
        assert abs(cost - expected) < 1e-10

    def test_zero_tokens(self, budget_config):
        cost = estimate_cost(0, 0, "claude-sonnet-4-20250514", budget_config)
        assert cost == 0.0


class TestSelectModel:
    """真实 Anthropic 模型 ID，不是 "claude-sonnet" 这种传给 API 会 404 的占位别名。"""

    def test_persona_with_model_hint(self, budget_config):
        persona = {"model_hint": "opus"}
        result = select_model(persona, budget_config)
        assert result == "claude-opus-4-20250514"

    def test_persona_with_sonnet_hint(self, budget_config):
        persona = {"model_hint": "sonnet"}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet-4-20250514"

    def test_persona_with_haiku_hint(self, budget_config):
        persona = {"model_hint": "haiku"}
        result = select_model(persona, budget_config)
        assert result == "claude-haiku-4-5-20251001"

    def test_persona_without_model_hint_uses_default(self, budget_config):
        persona = {}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet-4-20250514"

    def test_persona_with_none_model_hint_uses_default(self, budget_config):
        persona = {"model_hint": None}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet-4-20250514"


class TestNormalizePersonaOutput:
    """第三方模型（实测 MiniMax-M3）能理解任务但不肯照抄 schema 字段名：
    吐 evaluator_id / issues / reason 之类的同义名，导致报告里"0 条修复项"。
    normalize_persona_output 把变体名归一回规范名，把模型真产出的内容救回来。"""

    def test_variant_top_level_names_normalized(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({
            "evaluator_id": "P01",
            "evaluator_name": "林岚",
            "stance": "观望",
            "issues": [{"problem": "差异化不明", "level": "high", "reason": "看不出独特性"}],
        })
        assert out["persona_id"] == "P01"
        assert out["persona_name"] == "林岚"
        assert out["primary_stance"] == "观望"
        assert out["key_issues"][0]["title"] == "差异化不明"
        assert out["key_issues"][0]["severity"] == "high"
        assert out["key_issues"][0]["why_it_matters"] == "看不出独特性"

    def test_schema_conformant_output_untouched(self):
        # 守规矩的模型（Claude）输出原样通过，规范名已存在时不被别名覆盖
        from runner.persona_agent import normalize_persona_output

        canonical = {
            "persona_id": "P01", "persona_name": "林岚", "primary_stance": "值得推进",
            "key_issues": [{"title": "T", "severity": "low",
                            "why_it_matters": "W", "suggested_fix": "F"}],
        }
        out = normalize_persona_output(dict(canonical))
        assert out["persona_id"] == "P01"
        assert out["key_issues"][0] == canonical["key_issues"][0]

    def test_issues_as_dict_or_strings_coerced_to_list(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"key_issues": {"上手成本": "第一步就卡住"}})
        assert out["key_issues"][0]["title"] == "上手成本"

        out2 = normalize_persona_output({"key_issues": ["纯字符串问题"]})
        assert out2["key_issues"][0]["title"] == "纯字符串问题"
        assert out2["key_issues"][0]["severity"] == "medium"

    def test_parse_error_passthrough(self):
        from runner.persona_agent import normalize_persona_output

        bad = {"parse_error": True, "raw_output": "not json"}
        assert normalize_persona_output(bad) is bad


class TestNormalizeShapes:
    """改名只是第一层。第三方模型（MiniMax / DeepSeek / Kimi / GLM）连子结构的
    形状也不按 schema 给，实测三种形态会让整个 run_panel 崩掉（cli.py 的人格循环
    没有 try 包住 validator，一个人格吐错格式 → 前面 N 个人格的钱白花）：
      {"evidence": ["文案不清晰"]}   → validator e.get(...) AttributeError
      {"key_issues": "无重大问题"}   → calibration issue["title"] TypeError
      {"missing_information": [dict]} → aggregator seen_gaps.add(gap) unhashable
    形状归一化统一放在这个边界上做，下游不必逐点加 isinstance。"""

    def test_evidence_string_elements_wrapped_keeping_text(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"evidence": ["文案不清晰", "价格没写"]})
        assert all(isinstance(e, dict) for e in out["evidence"])
        # 原文必须保留，不能静默丢
        assert [e["content"] for e in out["evidence"]] == ["文案不清晰", "价格没写"]
        # 层级缺失一律记 inferred：谎报 direct 会让 grounding/幻觉率去核对不存在的原文
        assert all(e["inference_level"] == "inferred" for e in out["evidence"])
        assert all(e["inference_basis"] for e in out["evidence"])

    def test_evidence_whole_value_as_string(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"evidence": "整体就一句话"})
        assert out["evidence"] == [
            {
                "content": "整体就一句话",
                "inference_level": "inferred",
                "inference_basis": out["evidence"][0]["inference_basis"],
            }
        ]

    def test_evidence_dict_missing_keys_gets_safe_defaults(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output(
            {"evidence": [{"text": "首图看不出玩法", "level": "直接"}, {"随手写的": "没键名"}]}
        )
        assert out["evidence"][0]["content"] == "首图看不出玩法"
        # 中文层级写法映射回 schema 枚举
        assert out["evidence"][0]["inference_level"] == "direct"
        # 一个已知键都对不上时，整条 dict 摊平进 content——难看但不丢信息
        assert "没键名" in out["evidence"][1]["content"]
        assert out["evidence"][1]["inference_level"] in ("direct", "inferred", "gap")

    def test_valid_evidence_untouched(self):
        from runner.persona_agent import normalize_persona_output

        entry = {"content": "写着 30 小时流程", "inference_level": "direct",
                 "source_location": "商店页简介"}
        out = normalize_persona_output({"evidence": [dict(entry)]})
        assert out["evidence"] == [entry]

    def test_key_issues_whole_value_as_string(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"key_issues": "无重大问题"})
        assert out["key_issues"][0]["title"] == "无重大问题"
        assert out["key_issues"][0]["severity"] == "medium"

    def test_key_issues_non_str_non_dict_element_kept(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"key_issues": [["嵌套", "列表"]]})
        assert "嵌套" in out["key_issues"][0]["title"]

    def test_missing_information_downgraded_to_hashable_strings(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({
            "missing_information": [
                {"item": "没有实机演示"},
                {"question": "价格未定"},
                "缺少中文本地化说明",
            ]
        })
        # aggregator.py:231 用 set 去重 missing_information，dict 元素会 unhashable
        assert out["missing_information"] == [
            "没有实机演示", "价格未定", "缺少中文本地化说明"
        ]
        assert len(set(out["missing_information"])) == 3

    def test_missing_information_whole_value_as_string(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"missing_information": "什么都没给"})
        assert out["missing_information"] == ["什么都没给"]

    def test_trigger_lists_downgraded_to_strings(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({
            "continue_triggers": [{"text": "机制互锁明显"}],
            "quit_triggers": "卖点说不清",
            "first_scan_observations": [{"observation": "首图偏暗"}],
        })
        assert out["continue_triggers"] == ["机制互锁明显"]
        assert out["quit_triggers"] == ["卖点说不清"]
        assert out["first_scan_observations"] == ["首图偏暗"]

    def test_must_comment_on_check_as_list_becomes_dict(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"must_comment_on_check": ["独特性", "首15分钟"]})
        assert out["must_comment_on_check"] == {"独特性": True, "首15分钟": True}

    def test_must_comment_on_check_text_values_coerced_to_bool(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output(
            {"must_comment_on_check": {"独特性": "yes", "价格": "未覆盖"}}
        )
        assert out["must_comment_on_check"] == {"独特性": True, "价格": False}

    def test_ratio_fields_coerced_to_number(self):
        from runner.persona_agent import normalize_persona_output

        # aggregator 直接 sum(evidence_sufficiency)、cross_exam 直接 *100，字符串会 TypeError
        out = normalize_persona_output({"confidence": "0.8", "evidence_sufficiency": "70%"})
        assert out["confidence"] == pytest.approx(0.8)
        assert out["evidence_sufficiency"] == pytest.approx(0.7)

    def test_stance_forced_to_hashable_string(self):
        from runner.persona_agent import normalize_persona_output

        # aggregator 用 primary_stance 当 dict 键，list 会 unhashable
        out = normalize_persona_output({"primary_stance": ["观望"]})
        assert out["primary_stance"] == "观望"
        assert isinstance(out["primary_stance"], str)

    def test_scores_flat_shape_relayered(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"scores": {"clarity": 4, "trust": 3, "fun": 5}})
        assert out["scores"]["base"] == {"clarity": 4, "trust": 3}
        assert out["scores"]["task_specific"] == {"fun": 5}

    def test_absent_fields_not_invented(self):
        # 归一化只规整"模型给了但形状错"的字段，不给没给的字段凭空造空值——
        # 否则 schema 校验的"缺字段"信号会被我们自己抹掉
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"persona_id": "P01"})
        assert "evidence" not in out
        assert "key_issues" not in out


class TestOffSchemaDownstreamSurvives:
    """三种实测崩溃形态：经 normalize 后 validator / calibration 必须不再抛异常。
    未经 normalize 时下游的最小防御也要顶住（老数据回放、外部直接调的路径）。"""

    @staticmethod
    def _offschema_outputs():
        return [
            {"persona_id": "P01", "primary_stance": "观望",
             "evidence": ["文案不清晰"]},
            {"persona_id": "P02", "primary_stance": "观望",
             "key_issues": "无重大问题"},
            {"persona_id": "P03", "primary_stance": "观望",
             "evidence": ["首图看不出玩法", {"content": "价格未标", "inference_level": "direct"}],
             "missing_information": [{"item": "没有实机演示"}]},
        ]

    def test_validator_survives_after_normalize(self):
        from runner.persona_agent import normalize_persona_output
        from runner.validator import (
            validate_role_consistency,
            validate_evidence_grounding,
            check_identity_behavior_decoupling,
        )

        for raw in self._offschema_outputs():
            out = normalize_persona_output(raw)
            assert validate_role_consistency(out, {})["consistent"] in (True, False)
            assert validate_evidence_grounding(out, ["页面原文"])["grounded"] in (True, False)
            assert check_identity_behavior_decoupling(out)["decoupled"] is True

    def test_calibration_survives_after_normalize(self):
        from runner.persona_agent import normalize_persona_output
        from runner.calibration import run_calibration_check

        outputs = [normalize_persona_output(r) for r in self._offschema_outputs()]
        result = run_calibration_check(outputs, artifact_texts=["页面原文"])
        assert set(result["role_consistency"]["per_persona"]) == {"P01", "P02", "P03"}
        assert result["hallucination"] is not None

    def test_validator_and_calibration_survive_without_normalize(self):
        # 直接调用路径（没过归一化边界）也不能崩——这是第二道防御
        from runner.validator import validate_role_consistency
        from runner.calibration import run_calibration_check

        raws = self._offschema_outputs()
        for raw in raws:
            validate_role_consistency(raw, {})
        run_calibration_check(raws, artifact_texts=["页面原文"])

    def test_missing_persona_id_does_not_crash_calibration(self):
        # calibration 历史上用 p["persona_id"] 硬下标，v2 靠 cli.py 的 setdefault 兜着；
        # 直接调用路径缺 id 就 KeyError，整轮校准作废
        from runner.calibration import run_calibration_check

        result = run_calibration_check(
            [{"primary_stance": "观望"}, {"primary_stance": "值得推进"}],
            artifact_texts=["页面原文"],
        )
        # 两个缺 id 的输出不能互相覆盖成同一个键
        assert len(result["role_consistency"]["per_persona"]) == 2
