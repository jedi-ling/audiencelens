import ast
import json
import os

import pytest
import yaml

from runner.persona_agent import (
    BASE_SCORE_DIMENSIONS,
    TASK_SCORE_DIMENSIONS,
    TASK_STANCE_ENUM,
    estimate_cost,
    parse_persona_output,
    render_prompt,
    score_dimensions_for,
    select_model,
    stance_enum_for,
)
from runner.task_types import VALID_TASK_TYPES

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "persona-prompt.md")
BUDGET_PATH = os.path.join(PROJECT_ROOT, "src", "config", "budget.yaml")
BACKEND_SERVICES_PATH = os.path.join(
    PROJECT_ROOT, "web", "backend", "app", "services", "__init__.py"
)


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


class TestRenderPromptSplit:
    """render_prompt_split 是 render_prompt 的可缓存版本（见该函数头部注释）：
    拆成 (shared, user) 两段而不是拼成一份。这里验证的核心不变量只有一条——
    shared 段绝不能混入任何 persona 相关字段，否则每位人格的 shared 文本就不再
    逐字相同，Prompt Caching 永远 miss，整项优化白做。"""

    TEMPLATE_DIR = os.path.dirname(TEMPLATE_PATH)

    def test_shared_is_byte_identical_across_different_personas(self, sample_persona):
        """这是缓存能命中的唯一前提：换一个人格，shared 文本必须一字不差。"""
        from runner.persona_agent import render_prompt_split

        other_persona = {**sample_persona, "id": "P02-other", "name": "阿宁", "mbti": "ENFP"}

        shared_a, user_a = render_prompt_split(
            sample_persona, "steam_page_review", "某独立游戏Steam页面", self.TEMPLATE_DIR
        )
        shared_b, user_b = render_prompt_split(
            other_persona, "steam_page_review", "某独立游戏Steam页面", self.TEMPLATE_DIR
        )

        assert shared_a == shared_b
        assert user_a != user_b

    def test_shared_carries_task_and_artifact_not_persona_identity(self, sample_persona):
        from runner.persona_agent import render_prompt_split

        bundle = {"materials": [{"type": "text", "description": "核心玩法说明"}]}
        shared, user = render_prompt_split(
            sample_persona, "demo_first_play", "某独立游戏Demo", self.TEMPLATE_DIR, bundle
        )

        assert "demo_first_play" in shared
        assert "核心玩法说明" in shared
        # 身份字段一个都不该漏进 shared——漏一个就是缓存 miss 的根因
        assert "P01-indie-core-operator" not in shared
        assert "林岚" not in shared
        assert "INTJ" not in shared

    def test_user_carries_persona_identity_and_questions(self, sample_persona):
        from runner.persona_agent import render_prompt_split

        shared, user = render_prompt_split(
            sample_persona, "steam_page_review", "某独立游戏Steam页面", self.TEMPLATE_DIR
        )

        assert "P01-indie-core-operator" in user
        assert "林岚" in user
        assert "INTJ" in user
        assert "独特性" in user  # must_comment_on 项
        assert "若15秒内看不到核心钩子，不加愿望单" in user  # primary_decision_rule

    def test_combining_both_parts_still_covers_everything_render_prompt_covers(self, sample_persona):
        """拆分不能丢内容：把两段拼起来，该有的东西一件不少。"""
        from runner.persona_agent import render_prompt_split

        shared, user = render_prompt_split(
            sample_persona, "steam_page_review", "某独立游戏Steam页面", self.TEMPLATE_DIR
        )
        combined = shared + "\n\n" + user

        for expected in (
            "P01-indie-core-operator", "林岚", "核心独立探索者", "INTJ",
            "作为林岚", "独特性", "核心循环证据",
            "若15秒内看不到核心钩子，不加愿望单", "steam_page_review", "某独立游戏Steam页面",
        ):
            assert expected in combined

    def test_image_materials_stay_out_of_shared_go_into_user_content_blocks(self, sample_persona):
        """Anthropic 的 system 参数只接受纯文本块，图片必须留在 user 内容里。"""
        from runner.persona_agent import render_prompt_split

        bundle = {
            "materials": [
                {"type": "text", "description": "文字材料"},
                {"type": "image", "image_data": "data:image/png;base64,QUJD"},
            ]
        }
        shared, user = render_prompt_split(
            sample_persona, "steam_page_review", "某独立游戏Steam页面", self.TEMPLATE_DIR, bundle
        )

        assert isinstance(shared, str)
        assert isinstance(user, list)
        assert user[0]["type"] == "text"
        assert user[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}


def _backend_task_types() -> dict:
    """读后端 services 的 TASK_TYPES 字面量，但**不 import 它**。

    import 会把 fastapi / sqlalchemy / pydantic-settings 全家桶拖进引擎测试环境
    （后端有自己的一套依赖和一条独立的测试门），而这里只需要一个字典字面量。
    用 ast 直接取，既没有依赖也没有导入副作用。
    """
    with open(BACKEND_SERVICES_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign):
            target = node.target
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "TASK_TYPES":
            return ast.literal_eval(node.value)
    raise AssertionError(f"{BACKEND_SERVICES_PATH} 里找不到 TASK_TYPES 字面量")


class TestTaskTableSingleSource:
    """立场词表 / 评分维度必须只有一套口径。

    此前是两套半：后端 services.TASK_TYPES 一套（前端 /api/task-types 展示的就是它），
    提示词里手写一套（只覆盖 10 个立场 + 4 个任务的维度，且与前者不一致），
    剩下 4 个任务类型两套都没有。后果是模型按 A 打分、报告页按 B 展示，
    创业面板的 8 个人格干脆自造 8 种立场说法，共识与分歧统计直接失效。

    现在提示词的词表来自 runner.persona_agent，值从 services 逐字复制。
    任何一边改了而另一边没跟上，下面这两条立刻红。
    """

    def test_stance_enum_matches_backend(self):
        backend = _backend_task_types()
        for task_type in VALID_TASK_TYPES:
            assert TASK_STANCE_ENUM[task_type] == backend[task_type]["stance_enum"], (
                f"{task_type} 的立场词表与后端 services.TASK_TYPES 不一致——"
                "两边必须逐字相同，否则模型输出的立场词在报告页上对不上号"
            )

    def test_score_dimensions_match_backend(self):
        backend = _backend_task_types()
        for task_type in VALID_TASK_TYPES:
            assert list(TASK_SCORE_DIMENSIONS[task_type]) == backend[task_type][
                "score_dimensions"
            ], (
                f"{task_type} 的评分维度与后端 services.TASK_TYPES 不一致——"
                "维度名对不上，跨人格分数就不可比"
            )

    def test_tables_cover_every_registered_task_type(self):
        assert set(TASK_STANCE_ENUM) == set(VALID_TASK_TYPES)
        assert set(TASK_SCORE_DIMENSIONS) == set(VALID_TASK_TYPES)
        assert len(VALID_TASK_TYPES) == 14

    def test_base_dimensions_are_the_two_schema_requires(self):
        assert list(BASE_SCORE_DIMENSIONS) == ["clarity", "trust"]
        # 释义不能是空壳：模型要靠它知道 1 分和 5 分分别是什么样
        assert all(len(desc) > 20 for desc in BASE_SCORE_DIMENSIONS.values())


class TestTaskTableDriftGuard:
    """导入期断言必须真的会炸——否则它只是一行看起来很负责的注释。"""

    def test_missing_task_type_in_stance_table_fails(self, monkeypatch):
        from runner import persona_agent

        broken = dict(persona_agent.TASK_STANCE_ENUM)
        broken.pop("pitch_review")
        monkeypatch.setattr(persona_agent, "TASK_STANCE_ENUM", broken)
        with pytest.raises(AssertionError, match="TASK_STANCE_ENUM"):
            persona_agent._assert_task_tables_aligned()

    def test_missing_task_type_in_dimension_table_fails(self, monkeypatch):
        from runner import persona_agent

        broken = dict(persona_agent.TASK_SCORE_DIMENSIONS)
        broken.pop("onboarding_review")
        monkeypatch.setattr(persona_agent, "TASK_SCORE_DIMENSIONS", broken)
        with pytest.raises(AssertionError, match="TASK_SCORE_DIMENSIONS"):
            persona_agent._assert_task_tables_aligned()

    def test_schema_enum_drift_fails(self, monkeypatch, tmp_path):
        from runner import persona_agent

        stale = tmp_path / "output-schema.json"
        stale.write_text(
            json.dumps(
                {"properties": {"task_type": {"enum": VALID_TASK_TYPES[:10]}}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(persona_agent, "_SCHEMA_PATH", str(stale))
        with pytest.raises(AssertionError, match="output-schema.json"):
            persona_agent._assert_task_tables_aligned()


class TestRenderScoringGuidance:
    """提示词必须**明确写出**模型要交回什么分——此前 clarity / trust 两个词
    在提示词全文一次都没出现过，而 schema 要求它们必填。"""

    @pytest.mark.parametrize("task_type", VALID_TASK_TYPES)
    def test_base_dimensions_named_and_explained(self, sample_persona, task_type):
        result = render_prompt(sample_persona, task_type, "某评审对象", TEMPLATE_PATH)
        for dim, desc in BASE_SCORE_DIMENSIONS.items():
            assert dim in result
            assert desc in result

    @pytest.mark.parametrize("task_type", VALID_TASK_TYPES)
    def test_task_dimensions_named_and_explained(self, sample_persona, task_type):
        result = render_prompt(sample_persona, task_type, "某评审对象", TEMPLATE_PATH)
        for dim, desc in TASK_SCORE_DIMENSIONS[task_type].items():
            assert dim in result, f"{task_type} 缺维度 {dim}"
            assert desc in result, f"{task_type} 的维度 {dim} 没给释义"

    def test_other_task_dimensions_not_leaked(self, sample_persona):
        # 只注入本次要填的维度：铺 14 份清单会让模型在表里找错行（旧提示词就这样，
        # 它只列了 4 个任务的维度，其余 10 个任务的人格全靠自造）
        result = render_prompt(
            sample_persona, "pitch_review", "某BP", TEMPLATE_PATH
        )
        assert "market_potential" in result
        assert "wishlist_appeal" not in result
        assert "moment_to_moment_feel" not in result

    def test_unknown_task_type_says_so_instead_of_inventing(self, sample_persona):
        # 没预置词表就明说没有，不给模型一套编出来的维度/立场
        result = render_prompt(
            sample_persona, "not_a_registered_task", "某材料", TEMPLATE_PATH
        )
        assert "未预置专属评分维度" in result
        assert "未预置立场词表" in result
        # 基础维度任何任务都得填
        assert "clarity" in result and "trust" in result

    @pytest.mark.parametrize("task_type", VALID_TASK_TYPES)
    def test_skeleton_scores_are_prefilled_with_real_dimension_names(
        self, sample_persona, task_type
    ):
        result = render_prompt(sample_persona, task_type, "某评审对象", TEMPLATE_PATH)
        # 旧骨架就是这一行导致评分表恒为空
        assert '"scores": {"base": {}, "task_specific": {}}' not in result
        assert '"base": {"clarity": 3, "trust": 3}' in result
        for dim in score_dimensions_for(task_type):
            assert f'"{dim}": 3' in result

    def test_stance_line_is_the_task_specific_one(self, sample_persona):
        result = render_prompt(
            sample_persona, "pitch_review", "某BP", TEMPLATE_PATH
        )
        assert "值得跟进 / 不投 / 观望" in result
        # 别的任务类型的立场词表不该出现在这份提示词里（旧提示词把 10 份词表全铺出来）
        assert "继续试玩 / 退出 / 观望" not in result
        assert "增强信心 / 降低信心 / 无影响" not in result

    def test_stance_helpers_do_not_invent_for_unknown_task(self):
        assert stance_enum_for("not_a_registered_task") == []
        assert score_dimensions_for("not_a_registered_task") == []


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
        assert result == "claude-opus-5"

    def test_persona_with_sonnet_hint(self, budget_config):
        persona = {"model_hint": "sonnet"}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet-5"

    def test_persona_with_haiku_hint(self, budget_config):
        persona = {"model_hint": "haiku"}
        result = select_model(persona, budget_config)
        assert result == "claude-haiku-4-5-20251001"

    def test_persona_without_model_hint_uses_default(self, budget_config):
        persona = {}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet-5"

    def test_persona_with_none_model_hint_uses_default(self, budget_config):
        persona = {"model_hint": None}
        result = select_model(persona, budget_config)
        assert result == "claude-sonnet-5"


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

    def test_quote_is_its_own_field_not_an_alias_of_content(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({"evidence": [
            {"content": "流程长度写得具体", "inference_level": "direct", "quote": " 预计流程 12-15 小时 "},
            {"inference_level": "direct", "source_quote": "支持手柄与键鼠"},          # 别名；没写 content
            {"content": "大概率是小团队", "inference_level": "inferred", "quote": "不参与校验"},
            {"content": "页面写了流程", "inference_level": "direct"},                 # direct 缺 quote：原样留给校验器判
        ]})
        ev = out["evidence"]
        assert ev[0]["content"] == "流程长度写得具体" and ev[0]["quote"] == "预计流程 12-15 小时"
        # 只给了引用：content 用引用顶上（schema 要求非空），quote 照留
        assert ev[1]["content"] == ev[1]["quote"] == "支持手柄与键鼠"
        # inferred / gap 上的 quote 不保留——留着会让读者以为它被核对过
        assert "quote" not in ev[2]
        assert "quote" not in ev[3]
        assert all(set(e) <= {"content", "inference_level", "quote", "source_location", "inference_basis"} for e in ev)

    def test_prompt_states_the_quote_rule_and_schema_carries_the_field(self):
        import json
        for name in ("persona-prompt.md", "persona-prompt-shared.md"):
            with open(os.path.join("src", "templates", name), encoding="utf-8") as f:
                text = f.read()
            assert "能把材料原文一字不差地复制进 `quote`，才是 direct" in text
            assert '"quote": "<direct 必填' in text
        with open(os.path.join("src", "schemas", "output-schema.json"), encoding="utf-8") as f:
            item = json.load(f)["properties"]["evidence"]["items"]
        assert item["properties"]["quote"]["type"] == "string"
        # 不放进 JSON Schema 的 required：direct 缺 quote 由证据校验按"未落地"处理并点名回喂，
        # 否则它会先以 schema_failure 的名义出现，旧的已存输出也会整份变成 schema 不合法。
        assert "quote" not in item["required"]

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


class TestNormalizeScores:
    """评分是报告评分表的唯一数据来源，所以"模型确实给了分"这件事不能死在形状上。
    但缺的分绝不补——编一个分数出来，报告里会显示成"这个人格给了 3 分"。"""

    def test_non_integer_values_coerced_to_1_5_int(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({
            "scores": {
                "base": {"clarity": 4.4, "trust": "3"},
                "task_specific": {"a": "4/5", "b": "8/10", "c": "评分：5 分", "d": 7},
            }
        })
        assert out["scores"]["base"] == {"clarity": 4, "trust": 3}
        # 4/5 → 4；8/10 折算回五分制 → 4；带字的取数字 → 5；超上限夹到 5
        assert out["scores"]["task_specific"] == {"a": 4, "b": 4, "c": 5, "d": 5}

    def test_unreadable_score_is_dropped_not_invented(self):
        from runner.persona_agent import normalize_persona_output

        out = normalize_persona_output({
            "scores": {"base": {"clarity": 4, "trust": "N/A"},
                       "task_specific": {"a": "无法判断", "b": None, "c": True}}
        })
        # trust 读不出数字就让它缺席，schema 会如实报缺；不能塞个 3 冒充评分
        assert out["scores"]["base"] == {"clarity": 4}
        assert out["scores"]["task_specific"] == {}

    def test_extra_base_key_moved_to_task_specific(self):
        from runner.persona_agent import normalize_persona_output

        # schema 的 scores.base 是 additionalProperties:false，多一个键整份输出不合格；
        # 但那个键往往承载真实评分，直接丢掉等于丢内容
        out = normalize_persona_output({
            "scores": {"base": {"clarity": 4, "trust": 3, "appeal": 5},
                       "task_specific": {"fun": 2}}
        })
        assert out["scores"]["base"] == {"clarity": 4, "trust": 3}
        assert out["scores"]["task_specific"] == {"fun": 2, "appeal": 5}

    def test_base_dimensions_misplaced_in_task_specific_are_lifted(self):
        from runner.persona_agent import normalize_persona_output

        # 放错层会被报成"缺 clarity"，报告的横向对比列因此整列空掉
        out = normalize_persona_output({
            "scores": {"base": {}, "task_specific": {"clarity": 5, "trust": 2, "fun": 3}}
        })
        assert out["scores"]["base"] == {"clarity": 5, "trust": 2}
        assert out["scores"]["task_specific"] == {"fun": 3}

    def test_correct_scores_untouched(self):
        from runner.persona_agent import normalize_persona_output

        scores = {"base": {"clarity": 4, "trust": 5},
                  "task_specific": {"market_potential": 2}}
        out = normalize_persona_output({"scores": json.loads(json.dumps(scores))})
        assert out["scores"] == scores

    def test_normalized_scores_pass_schema(self):
        """归一化之后必须真的能过 schema——否则救回来的分照样进不了报告。"""
        from runner.persona_agent import normalize_persona_output
        from runner.validator import load_schema, validate_schema

        schema = load_schema(
            os.path.join(PROJECT_ROOT, "src", "schemas", "output-schema.json")
        )
        base_output = {
            "persona_id": "P01", "persona_name": "林岚", "persona_version": "0.1.0",
            "task_type": "pitch_review", "primary_stance": "观望",
            "confidence": 0.5, "evidence_sufficiency": 0.5,
            "evidence": [{"content": "有营收数字", "inference_level": "direct"}],
            "scores": {"base": {"clarity": "4", "trust": 3.4, "appeal": 5},
                       "task_specific": {"market_potential": "4/5"}},
            "key_issues": [{"severity": "medium", "title": "T",
                            "why_it_matters": "W", "suggested_fix": "F"}],
            "continue_triggers": [], "quit_triggers": [],
            "first_scan_observations": [], "must_comment_on_check": {},
            "missing_information": [], "voice_sample": "先看数据",
            "meta": {"caveats": ["仅基于 BP"], "is_synthetic": True},
        }
        out = normalize_persona_output(base_output)
        result = validate_schema(out, schema)
        assert result["valid"] is True, result["errors"]
        assert out["scores"]["base"] == {"clarity": 4, "trust": 3}
        assert out["scores"]["task_specific"] == {"market_potential": 4, "appeal": 5}

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
