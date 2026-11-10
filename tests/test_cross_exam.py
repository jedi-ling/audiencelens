import json
import os

import pytest

from runner.cross_exam import (
    LIMITATION_DERIVED,
    build_debate_sides,
    extract_controversy_points,
    find_opposing_stances,
    load_cross_exam_rules,
    load_prompt_sections,
    parse_cross_exam_output,
    render_cross_exam_prompt,
    render_rebuttal_prompt,
    run_cross_exam_protocol,
)
from runner.similarity import get_issue_similarity

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "cross-exam-prompt.md")
RULES_PATH = os.path.join(PROJECT_ROOT, "src", "config", "aggregation-rules.yaml")

# 全部人格名——"提示词里不许出现人格名"这条底线要按整份名单校验，
# 而不是只抽查一个名字。
ALL_PERSONA_NAMES = ("林岚", "周策", "韩岳")


@pytest.fixture
def sim():
    """统一用字面量相似度：测试不该因为 embedding 模型在不在而结果不同。"""
    return get_issue_similarity(force_lexical=True)


@pytest.fixture
def persona_outputs():
    return [
        {
            "persona_id": "P01",
            "persona_name": "林岚",
            "primary_stance": "加愿望单",
            "key_issues": [
                {"title": "核心循环不清晰", "severity": "high", "why_it_matters": "无法判断玩法", "suggested_fix": "补充实机"},
                {"title": "美术风格独特", "severity": "low", "why_it_matters": "视觉吸引力", "suggested_fix": "保持"},
            ],
        },
        {
            "persona_id": "P02",
            "persona_name": "周策",
            "primary_stance": "不加",
            "key_issues": [
                {"title": "核心循环不清晰", "severity": "critical", "why_it_matters": "系统无法闭环", "suggested_fix": "重新设计"},
                {"title": "美术风格独特", "severity": "medium", "why_it_matters": "视觉不错但不是核心", "suggested_fix": "配合系统"},
            ],
        },
        {
            "persona_id": "P03",
            "persona_name": "韩岳",
            "primary_stance": "观望",
            "key_issues": [
                {"title": "核心循环不清晰", "severity": "medium", "why_it_matters": "看不出来", "suggested_fix": "给demo"},
            ],
        },
    ]


@pytest.fixture
def duel_outputs():
    """两人一议题、严重度对立的最小对局，置信度写死便于算 θ 边界。

    severity high(3) vs critical(4) → pro=P02（认为更严重），con=P01。
    对应论据编号：A1=P02、B1=P01。
    """
    return [
        {
            "persona_id": "P01",
            "persona_name": "林岚",
            "primary_stance": "加愿望单",
            "confidence": 0.5,
            "key_issues": [
                {"title": "核心循环不清晰", "severity": "high", "why_it_matters": "看不出玩法闭环", "suggested_fix": "补充实机"},
            ],
        },
        {
            "persona_id": "P02",
            "persona_name": "周策",
            "primary_stance": "不加",
            "confidence": 0.5,
            "key_issues": [
                {"title": "核心循环不清晰", "severity": "critical", "why_it_matters": "系统无法闭环", "suggested_fix": "重新设计"},
            ],
        },
    ]


@pytest.fixture
def duel_controversy(duel_outputs, sim):
    return extract_controversy_points(duel_outputs, top_n=1, similarity=sim)


@pytest.fixture
def persona_outputs_no_controversy():
    return [
        {
            "persona_id": "P01",
            "persona_name": "林岚",
            "primary_stance": "加愿望单",
            "key_issues": [
                {"title": "核心循环不清晰", "severity": "high", "why_it_matters": "a", "suggested_fix": "b"},
            ],
        },
        {
            "persona_id": "P02",
            "persona_name": "周策",
            "primary_stance": "加愿望单",
            "key_issues": [
                {"title": "核心循环不清晰", "severity": "high", "why_it_matters": "c", "suggested_fix": "d"},
            ],
        },
    ]


@pytest.fixture
def persona_outputs_single():
    return [
        {
            "persona_id": "P01",
            "persona_name": "林岚",
            "primary_stance": "加愿望单",
            "key_issues": [
                {"title": "核心循环不清晰", "severity": "high", "why_it_matters": "a", "suggested_fix": "b"},
            ],
        },
    ]


def make_llm(response, record=None, tokens=None, exc=None):
    """构造假 llm_call。

    response 可以是字符串，也可以是 {argument_id: 响应} 的 dict（多智能体分支按
    persona_id 取）。tokens 给 (in, out) 时按 chat_completion 的原生三元组返回。
    """
    def llm_call(prompt, persona_id=""):
        if record is not None:
            record.append({"prompt": prompt, "persona_id": persona_id})
        if exc is not None:
            raise exc
        text = response(persona_id) if callable(response) else response
        if tokens is not None:
            return text, tokens[0], tokens[1]
        return text

    return llm_call


def moderated_response(a1_stance="不加", a1_conf=0.5, b1_stance="加愿望单", b1_conf=0.5):
    return json.dumps(
        [
            {
                "point_id": "C1",
                "rebuttals": [
                    {"argument_id": "A1", "rebuttal": "对方低估了系统风险", "stance_after": a1_stance, "confidence_after": a1_conf},
                    {"argument_id": "B1", "rebuttal": "对方夸大了闭环缺失", "stance_after": b1_stance, "confidence_after": b1_conf},
                ],
            }
        ],
        ensure_ascii=False,
    )


class TestExtractControversyPoints:
    def test_multiple_controversies(self, persona_outputs):
        result = extract_controversy_points(persona_outputs, top_n=3)
        assert len(result) >= 1
        first = result[0]
        assert "title" in first
        assert "severity_variance" in first
        assert "persona_views" in first
        assert first["severity_variance"] > 0

    def test_top_n_limits_results(self, persona_outputs):
        result = extract_controversy_points(persona_outputs, top_n=1)
        assert len(result) <= 1

    def test_no_controversy_all_agree(self, persona_outputs_no_controversy):
        result = extract_controversy_points(persona_outputs_no_controversy, top_n=3)
        for point in result:
            assert point["severity_variance"] == 0.0

    def test_single_persona(self, persona_outputs_single):
        result = extract_controversy_points(persona_outputs_single, top_n=3)
        for point in result:
            assert point["severity_variance"] == 0.0

    def test_severity_variance_ordering(self, persona_outputs):
        result = extract_controversy_points(persona_outputs, top_n=3)
        for i in range(len(result) - 1):
            assert result[i]["severity_variance"] >= result[i + 1]["severity_variance"]

    def test_persona_views_contain_ids(self, persona_outputs):
        result = extract_controversy_points(persona_outputs, top_n=3)
        for point in result:
            for view in point["persona_views"]:
                assert "persona_id" in view
                assert "severity" in view
                assert "title" in view

    def test_similar_titles_deduplicated(self):
        outputs = [
            {
                "persona_id": "P01",
                "persona_name": "林岚",
                "primary_stance": "加愿望单",
                "key_issues": [
                    {"title": "核心循环不清晰", "severity": "high", "why_it_matters": "a", "suggested_fix": "b"},
                ],
            },
            {
                "persona_id": "P02",
                "persona_name": "周策",
                "primary_stance": "不加",
                "key_issues": [
                    {"title": "核心循环不够清晰", "severity": "critical", "why_it_matters": "c", "suggested_fix": "d"},
                ],
            },
        ]
        result = extract_controversy_points(outputs, top_n=3)
        titles = [p["title"] for p in result]
        assert len(titles) == len(set(titles))

    def test_hierarchical_clustering_order_independent(self):
        """P1-4: 层次聚类结果不依赖输入顺序"""
        outputs_a = [
            {
                "persona_id": "P01",
                "key_issues": [
                    {"title": "新手引导太长", "severity": "high"},
                    {"title": "付费墙太早", "severity": "medium"},
                ],
            },
            {
                "persona_id": "P02",
                "key_issues": [
                    {"title": "付费墙太早", "severity": "critical"},
                    {"title": "新手引导太长", "severity": "low"},
                ],
            },
        ]
        outputs_b = list(reversed(outputs_a))
        sim = get_issue_similarity(force_lexical=True)
        result_a = extract_controversy_points(outputs_a, top_n=10, similarity=sim)
        result_b = extract_controversy_points(outputs_b, top_n=10, similarity=sim)
        titles_a = sorted(p["title"] for p in result_a)
        titles_b = sorted(p["title"] for p in result_b)
        assert titles_a == titles_b


class TestFindOpposingStances:
    def test_finds_pro_and_con(self, persona_outputs):
        controversy = extract_controversy_points(persona_outputs, top_n=1)[0]
        result = find_opposing_stances(controversy, persona_outputs)
        assert "pro" in result
        assert "con" in result
        assert "persona_id" in result["pro"]
        assert "persona_id" in result["con"]
        assert "argument" in result["pro"]
        assert "argument" in result["con"]

    def test_pro_and_con_are_different_personas(self, persona_outputs):
        controversy = extract_controversy_points(persona_outputs, top_n=1)[0]
        result = find_opposing_stances(controversy, persona_outputs)
        assert result["pro"]["persona_id"] != result["con"]["persona_id"]

    def test_find_opposing_stances_accepts_similarity_param(self, persona_outputs):
        """P1-1: find_opposing_stances 应接受 similarity 参数并复用 IssueSimilarity"""
        sim = get_issue_similarity(force_lexical=True)
        controversy = extract_controversy_points(persona_outputs, top_n=1, similarity=sim)[0]
        result = find_opposing_stances(controversy, persona_outputs, similarity=sim)
        assert "pro" in result
        assert "con" in result


class TestBuildDebateSides:
    def test_assigns_anonymous_argument_ids(self, duel_outputs, duel_controversy, sim):
        debates = build_debate_sides(duel_controversy, duel_outputs, similarity=sim)
        assert len(debates) == 1
        d = debates[0]
        assert d["point_id"] == "C1"
        assert d["debatable"] is True
        assert [s["argument_id"] for s in d["sides"]] == ["A1", "B1"]
        # pro 是认为问题更严重的一方
        assert d["sides"][0]["persona_id"] == "P02"
        assert d["sides"][1]["persona_id"] == "P01"

    def test_single_persona_point_not_debatable(self, persona_outputs_single, sim):
        controversy = extract_controversy_points(persona_outputs_single, top_n=1, similarity=sim)
        debates = build_debate_sides(controversy, persona_outputs_single, similarity=sim)
        assert debates[0]["debatable"] is False
        assert debates[0]["skip_reason"]

    def test_point_without_views_does_not_crash(self, duel_outputs, sim):
        """persona_views 为空时 find_opposing_stances 会 IndexError，必须提前短路。"""
        debates = build_debate_sides(
            [{"title": "凭空出现的议题", "persona_views": []}], duel_outputs, similarity=sim
        )
        assert debates[0]["debatable"] is False
        assert debates[0]["sides"] == []


class TestRenderCrossExamPrompt:
    def test_renders_controversy_points(self, persona_outputs):
        controversy = extract_controversy_points(persona_outputs, top_n=2)
        result = render_cross_exam_prompt(controversy, persona_outputs, TEMPLATE_PATH)
        assert "核心循环不清晰" in result

    def test_prompt_contains_no_persona_names(self, persona_outputs):
        """底线 5：提示词里不许出现人格名，只能用论据编号指代。"""
        controversy = extract_controversy_points(persona_outputs, top_n=3)
        result = render_cross_exam_prompt(controversy, persona_outputs, TEMPLATE_PATH)
        for name in ALL_PERSONA_NAMES:
            assert name not in result
        assert "A1" in result and "B1" in result

    def test_persona_name_inside_argument_is_scrubbed(self, sim):
        outputs = [
            {
                "persona_id": "P01",
                "persona_name": "林岚",
                "primary_stance": "加愿望单",
                "key_issues": [
                    {"title": "核心循环不清晰", "severity": "high", "why_it_matters": "林岚认为这点不致命", "suggested_fix": "补实机"},
                ],
            },
            {
                "persona_id": "P02",
                "persona_name": "周策",
                "primary_stance": "不加",
                "key_issues": [
                    {"title": "核心循环不清晰", "severity": "critical", "why_it_matters": "周策坚持系统无法闭环", "suggested_fix": "重设计"},
                ],
            },
        ]
        controversy = extract_controversy_points(outputs, top_n=1, similarity=sim)
        result = render_cross_exam_prompt(controversy, outputs, TEMPLATE_PATH, similarity=sim)
        assert "林岚" not in result
        assert "周策" not in result
        assert "某位评审" in result

    def test_returns_empty_when_nothing_debatable(self, persona_outputs_single, sim):
        """没有可反驳的对立论据时返回空串，调用方据此不发调用。"""
        controversy = extract_controversy_points(persona_outputs_single, top_n=1, similarity=sim)
        result = render_cross_exam_prompt(controversy, persona_outputs_single, TEMPLATE_PATH, similarity=sim)
        assert result == ""

    def test_template_has_both_sections(self):
        sections = load_prompt_sections(TEMPLATE_PATH)
        assert "moderated" in sections
        assert "rebutter" in sections
        # 模板本身不许留人格名槽位
        assert "persona_name" not in sections["moderated"]
        assert "persona_name" not in sections["rebutter"]


class TestRenderRebuttalPrompt:
    def test_rebutter_prompt_hides_both_identities(self, duel_outputs, duel_controversy, sim):
        debates = build_debate_sides(duel_controversy, duel_outputs, similarity=sim)
        d = debates[0]
        for side in d["sides"]:
            prompt = render_rebuttal_prompt(d, side, TEMPLATE_PATH)
            for name in ALL_PERSONA_NAMES:
                assert name not in prompt
            assert side["argument_id"] in prompt

    def test_missing_rebutter_section_raises(self, tmp_path, duel_outputs, duel_controversy, sim):
        legacy = tmp_path / "legacy-prompt.md"
        legacy.write_text("旧模板，只有一段正文", encoding="utf-8")
        debates = build_debate_sides(duel_controversy, duel_outputs, similarity=sim)
        with pytest.raises(ValueError):
            render_rebuttal_prompt(debates[0], debates[0]["sides"][0], str(legacy))


class TestLoadCrossExamRules:
    def test_reads_threshold_from_real_yaml(self):
        cfg = load_cross_exam_rules()
        assert cfg["threshold"] == 0.15
        assert cfg["source"].endswith("aggregation-rules.yaml")

    def test_reads_threshold_from_custom_yaml(self, tmp_path):
        path = tmp_path / "rules.yaml"
        path.write_text("cross_exam:\n  confidence_change_threshold: 0.42\n", encoding="utf-8")
        cfg = load_cross_exam_rules(rules_path=str(path))
        assert cfg["threshold"] == 0.42

    def test_prefers_caller_supplied_rules_dict(self):
        cfg = load_cross_exam_rules(rules={"cross_exam": {"confidence_change_threshold": 0.3}})
        assert cfg["threshold"] == 0.3
        assert cfg["source"] == "rules-dict"

    def test_missing_file_falls_back_and_says_so(self, tmp_path):
        cfg = load_cross_exam_rules(rules_path=str(tmp_path / "nope.yaml"))
        assert cfg["threshold"] == 0.15
        assert "fallback-default" in cfg["source"]


class TestDerivedSummaryBackwardCompat:
    def test_protocol_marks_derived_summary_not_live_debate(self, persona_outputs):
        controversy = extract_controversy_points(persona_outputs, top_n=1)
        result = run_cross_exam_protocol(persona_outputs, controversy)

        assert result["mode"] == "derived_summary"
        assert result["is_live_debate"] is False
        assert result["limitation"] == LIMITATION_DERIVED
        assert result["vote_changes"] == []
        # 没跑过任何一轮，就不该画出 Round 指示器
        assert result["rounds"] == []

    def test_derived_summary_still_emits_disputes(self, persona_outputs, sim):
        controversy = extract_controversy_points(persona_outputs, top_n=1, similarity=sim)
        result = run_cross_exam_protocol(persona_outputs, controversy, similarity=sim)
        assert result["disputes"]
        assert result["disputes"][0]["pro_args"][0]["point"]
        assert result["disputes"][0]["rebuttal_status"] == "skipped"

    def test_legacy_positional_num_rounds_does_not_break(self, persona_outputs, sim):
        """老签名第三个位置参数是 num_rounds；传整数不该被当成 llm_call。"""
        controversy = extract_controversy_points(persona_outputs, top_n=1, similarity=sim)
        result = run_cross_exam_protocol(persona_outputs, controversy, 3, similarity=sim)
        assert result["mode"] == "derived_summary"

    def test_unknown_mode_raises(self, persona_outputs):
        with pytest.raises(ValueError):
            run_cross_exam_protocol(persona_outputs, [], mode="live_debate_deluxe")

    def test_auto_mode_with_llm_picks_moderated_not_multi_agent(
        self, duel_outputs, duel_controversy, sim
    ):
        """不显式传 mode 时，有 llm_call 也只发**一次**仲裁式调用。

        锁死这一条是为了防止默认档位被悄悄改成 multi_agent：那一档的调用数随涉事
        人格数上升，没做过选择的调用方会按最贵的路径付钱而不自知。
        """
        record = []
        llm = make_llm(moderated_response(), record=record)
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )

        assert result["requested_mode"] == "moderated_rebuttal"
        assert result["mode"] == "moderated_rebuttal"
        assert len(record) == 1


class TestModeratedRebuttal:
    def test_live_call_flips_mode_and_limitation(self, duel_outputs, duel_controversy, sim):
        record = []
        llm = make_llm(moderated_response(a1_stance="加愿望单", a1_conf=0.7), record=record, tokens=(120, 80))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )

        assert result["mode"] == "moderated_rebuttal"
        assert result["is_live_debate"] is True
        assert result["rounds"] == [{"round_num": 1, "is_current": True}]
        assert "no live multi-agent rebuttal" not in result["limitation"]
        assert "一次仲裁式反驳轮" in result["limitation"]
        # 口径不许含糊：不能让人以为每个人格各自反驳过
        assert "不是每个人格各自独立重新发言" in result["limitation"]
        assert len(record) == 1
        assert result["usage"]["calls"] == 1
        assert result["usage"]["input_tokens"] == 120
        assert result["usage"]["output_tokens"] == 80
        assert result["usage"]["token_counts_available"] is True

    def test_prompt_sent_to_model_has_no_persona_names(self, duel_outputs, duel_controversy, sim):
        record = []
        llm = make_llm(moderated_response(), record=record)
        run_cross_exam_protocol(duel_outputs, duel_controversy, llm_call=llm, similarity=sim)
        for name in ALL_PERSONA_NAMES:
            assert name not in record[0]["prompt"]

    def test_vote_change_is_computed_from_before_after(self, duel_outputs, duel_controversy, sim):
        # A1 = P02（原立场"不加"、置信度 0.5）→ 改成"加愿望单"、0.7，delta 0.2 ≥ θ
        llm = make_llm(moderated_response(a1_stance="加愿望单", a1_conf=0.7))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )

        assert len(result["vote_changes"]) == 1
        vc = result["vote_changes"][0]
        assert vc["argument_id"] == "A1"
        assert vc["persona_id"] == "P02"
        assert vc["persona_name"] == "周策"
        assert vc["from_stance"] == "不加"
        assert vc["to_stance"] == "加愿望单"
        assert vc["confidence_before"] == 0.5
        assert vc["confidence_after"] == 0.7
        assert vc["delta"] == pytest.approx(0.2)
        assert vc["reason"]
        # 旧报告模板读的字段仍在
        assert vc["before"] == "不加" and vc["after"] == "加愿望单"

    def test_no_change_is_a_normal_outcome(self, duel_outputs, duel_controversy, sim):
        """双方都不改是正常结果，不该被算成改票。"""
        llm = make_llm(moderated_response())
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["mode"] == "moderated_rebuttal"
        assert result["vote_changes"] == []
        assert result["suppressed_changes"] == []

    def test_confidence_delta_is_real_not_zero(self, duel_outputs, duel_controversy, sim):
        # 立场不变但置信度掉了：不算改票，但 confidence_changes 的 delta 必须是真值
        llm = make_llm(moderated_response(b1_conf=0.2))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        by_key = {c["persona_key"]: c for c in result["confidence_changes"]}
        assert by_key["P01"]["before"] == 50
        assert by_key["P01"]["after"] == 20
        assert by_key["P01"]["delta"] == -30
        assert result["vote_changes"] == []

    def test_confidence_changes_keeps_legacy_shape(self, duel_outputs, duel_controversy, sim):
        llm = make_llm(moderated_response())
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        row = result["confidence_changes"][0]
        # 报告模板把 persona_id 当展示标签渲染，历史如此
        assert row["persona_id"] == "林岚"
        assert isinstance(row["after"], int)
        assert isinstance(row["delta"], int)

    def test_rebuttal_text_lands_in_disputes(self, duel_outputs, duel_controversy, sim):
        llm = make_llm(moderated_response())
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        dispute = result["disputes"][0]
        assert dispute["rebuttal_status"] == "ok"
        assert dispute["pro_args"][0]["rebuttal"] == "对方低估了系统风险"
        assert dispute["con_args"][0]["rebuttal"] == "对方夸大了闭环缺失"

    def test_string_only_llm_marks_tokens_unavailable(self, duel_outputs, duel_controversy, sim):
        """llm_call 只回文本时 token 数拿不到——必须说出来，不能让成本统计悄悄偏低。"""
        llm = make_llm(moderated_response())
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["usage"]["token_counts_available"] is False
        assert "token" in result["limitation"]

    def test_dict_return_shape_accounted(self, duel_outputs, duel_controversy, sim):
        def llm(prompt, persona_id=""):
            return {"text": moderated_response(), "input_tokens": 10, "output_tokens": 5}

        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5
        assert result["usage"]["token_counts_available"] is True

    def test_markdown_wrapped_response_still_parsed(self, duel_outputs, duel_controversy, sim):
        llm = make_llm(f"这是我的判断：\n```json\n{moderated_response()}\n```")
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["mode"] == "moderated_rebuttal"


class TestFailureHonesty:
    def test_exception_falls_back_to_derived_without_raising(self, duel_outputs, duel_controversy, sim):
        llm = make_llm("", exc=RuntimeError("429 rate limited"))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )

        assert result["mode"] == "derived_summary"
        assert result["is_live_debate"] is False
        assert result["failures"]
        assert "429 rate limited" in result["failures"][0]["error"]
        # 失败要在报告里说出来，不能静默
        assert "未能完成" in result["limitation"]
        assert "429 rate limited" in result["limitation"]
        assert result["vote_changes"] == []
        assert result["disputes"][0]["rebuttal_status"] == "failed"

    def test_unparseable_output_falls_back(self, duel_outputs, duel_controversy, sim):
        llm = make_llm("我觉得双方都有道理，就不写 JSON 了。")
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["mode"] == "derived_summary"
        assert result["failures"]
        assert "未能完成" in result["limitation"]

    def test_whole_output_is_a_json_string(self, duel_outputs, duel_controversy, sim):
        llm = make_llm('"双方均不改变立场"')
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["mode"] == "derived_summary"
        assert result["failures"]

    def test_requested_live_without_llm_call_is_reported(self, duel_outputs, duel_controversy, sim):
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, mode="moderated_rebuttal", similarity=sim
        )
        assert result["mode"] == "derived_summary"
        assert result["is_live_debate"] is False
        assert "未注入 llm_call" in result["limitation"]

    def test_no_debatable_point_skips_call(self, persona_outputs_single, sim):
        controversy = extract_controversy_points(persona_outputs_single, top_n=1, similarity=sim)
        called = []
        llm = make_llm(moderated_response(), record=called)
        result = run_cross_exam_protocol(
            persona_outputs_single, controversy, llm_call=llm, similarity=sim
        )
        assert called == []
        assert result["mode"] == "derived_summary"
        assert result["usage"]["calls"] == 0
        assert "没有可反驳的对立论据" in result["limitation"]

    def test_unmatched_argument_id_does_not_crash(self, duel_outputs, duel_controversy, sim):
        llm = make_llm(json.dumps(
            [{"point_id": "C1", "rebuttals": [{"argument_id": "Z9", "rebuttal": "x", "confidence_after": 0.9}]}],
            ensure_ascii=False,
        ))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["mode"] == "derived_summary"
        assert result["failures"]

    def test_missing_fields_do_not_crash(self, duel_outputs, duel_controversy, sim):
        """只给编号、不给立场和置信度：当作没变，不编数字。"""
        llm = make_llm(json.dumps(
            [{"point_id": "C1", "rebuttals": [{"argument_id": "A1", "rebuttal": "只写了反驳"}]}],
            ensure_ascii=False,
        ))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["mode"] == "moderated_rebuttal"
        assert result["vote_changes"] == []
        by_key = {c["persona_key"]: c for c in result["confidence_changes"]}
        assert by_key["P02"]["delta"] == 0

    def test_weird_field_types_are_normalized(self, duel_outputs, duel_controversy, sim):
        """字段别名 + 百分数 + 数字型立场：归一化后照样能算。"""
        llm = make_llm(json.dumps(
            [{
                "controversy_point_id": "C1",
                "persona_evaluations": [
                    {"arg_id": "论据 A1", "counter_argument": "反驳", "new_stance": "加愿望单", "new_confidence": "80%"},
                ],
            }],
            ensure_ascii=False,
        ))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["mode"] == "moderated_rebuttal"
        assert len(result["vote_changes"]) == 1
        assert result["vote_changes"][0]["confidence_after"] == 0.8

    def test_non_dict_items_are_ignored(self, duel_outputs, duel_controversy, sim):
        llm = make_llm(json.dumps(["随便一句话", 42], ensure_ascii=False))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["mode"] == "derived_summary"
        assert result["failures"]


class TestThresholdBoundary:
    def _run(self, duel_outputs, duel_controversy, sim, conf_after, rules_path=None):
        llm = make_llm(moderated_response(a1_stance="加愿望单", a1_conf=conf_after))
        return run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim, rules_path=rules_path
        )

    def test_delta_exactly_equal_to_theta_counts(self, duel_outputs, duel_controversy, sim):
        # 0.65 - 0.5 = 0.15，正好等于 θ；浮点误差不许把它判成不足
        result = self._run(duel_outputs, duel_controversy, sim, 0.65)
        assert len(result["vote_changes"]) == 1
        assert result["vote_changes"][0]["delta"] == pytest.approx(0.15)

    def test_delta_just_below_theta_is_suppressed(self, duel_outputs, duel_controversy, sim):
        # 0.64 - 0.5 = 0.14 < θ：模型说改了也不算改票，但要留痕说明为什么不算
        result = self._run(duel_outputs, duel_controversy, sim, 0.64)
        assert result["vote_changes"] == []
        assert len(result["suppressed_changes"]) == 1
        suppressed = result["suppressed_changes"][0]
        assert "未达阈值" in suppressed["suppressed_reason"]
        assert suppressed["to_stance"] == "加愿望单"

    def test_threshold_comes_from_yaml(self, tmp_path, duel_outputs, duel_controversy, sim):
        """改 yaml 里的 θ，判定结果必须跟着变——证明这个值真的被代码读了。"""
        path = tmp_path / "rules.yaml"
        path.write_text("cross_exam:\n  confidence_change_threshold: 0.5\n", encoding="utf-8")

        loose = self._run(duel_outputs, duel_controversy, sim, 0.7)  # θ=0.15 → 改票
        strict = self._run(duel_outputs, duel_controversy, sim, 0.7, rules_path=str(path))

        assert len(loose["vote_changes"]) == 1
        assert loose["threshold"] == 0.15
        assert strict["vote_changes"] == []
        assert strict["threshold"] == 0.5
        assert "0.5" in strict["limitation"]
        assert str(path) == strict["threshold_source"]

    def test_allow_stance_update_false_blocks_changes(self, tmp_path, duel_outputs, duel_controversy, sim):
        path = tmp_path / "rules.yaml"
        path.write_text(
            "cross_exam:\n  confidence_change_threshold: 0.15\n  allow_stance_update: false\n",
            encoding="utf-8",
        )
        result = self._run(duel_outputs, duel_controversy, sim, 0.9, rules_path=str(path))
        assert result["vote_changes"] == []
        assert "allow_stance_update=false" in result["suppressed_changes"][0]["suppressed_reason"]

    def test_unchanged_marker_is_not_a_flip(self, duel_outputs, duel_controversy, sim):
        """模型写"保持不变"而不是照抄立场时，不能当成改票。"""
        llm = make_llm(moderated_response(a1_stance="保持不变", a1_conf=0.9))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm, similarity=sim
        )
        assert result["vote_changes"] == []
        assert result["suppressed_changes"] == []


class TestMultiAgentRebuttal:
    def test_each_persona_is_re_invoked(self, duel_outputs, duel_controversy, sim):
        record = []

        def response(persona_id):
            arg_id = "A1" if persona_id == "P02" else "B1"
            return json.dumps(
                {"argument_id": arg_id, "rebuttal": "我的反驳", "stance_after": "观望", "confidence_after": 0.8},
                ensure_ascii=False,
            )

        llm = make_llm(response, record=record, tokens=(50, 30))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm,
            mode="multi_agent_rebuttal", similarity=sim,
        )

        assert result["mode"] == "multi_agent_rebuttal"
        assert result["is_live_debate"] is True
        assert result["usage"]["calls"] == 2
        assert result["usage"]["input_tokens"] == 100
        assert sorted(r["persona_id"] for r in record) == ["P01", "P02"]
        assert "双方各重新发起了一次独立调用" in result["limitation"]
        assert result["disputes"][0]["rebuttal_status"] == "ok"
        # 两位都改了立场且 delta 0.3 ≥ θ
        assert len(result["vote_changes"]) == 2

    def test_partial_failure_keeps_mode_and_reports(self, duel_outputs, duel_controversy, sim):
        def llm(prompt, persona_id=""):
            if persona_id == "P01":
                raise RuntimeError("timeout")
            return json.dumps(
                {"argument_id": "A1", "rebuttal": "我的反驳", "stance_after": "不加", "confidence_after": 0.5},
                ensure_ascii=False,
            )

        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm,
            mode="multi_agent_rebuttal", similarity=sim,
        )
        assert result["mode"] == "multi_agent_rebuttal"
        assert len(result["failures"]) == 1
        assert result["failures"][0]["argument_id"] == "B1"
        # 单边反驳不许显示成"完成"
        assert result["disputes"][0]["rebuttal_status"] == "partial"
        assert "反驳未完整完成" in result["limitation"]

    def test_all_sides_failing_falls_back(self, duel_outputs, duel_controversy, sim):
        llm = make_llm("", exc=RuntimeError("boom"))
        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm,
            mode="multi_agent_rebuttal", similarity=sim,
        )
        assert result["mode"] == "derived_summary"
        assert result["is_live_debate"] is False
        assert len(result["failures"]) == 2
        assert "boom" in result["limitation"]

    def test_llm_without_persona_id_param_still_works(self, duel_outputs, duel_controversy, sim):
        """注入方可能只接受 prompt 一个参数——不该因为传 persona_id 就炸。"""
        def llm(prompt):
            return json.dumps(
                {"rebuttal": "反驳", "stance_after": "观望", "confidence_after": 0.9},
                ensure_ascii=False,
            )

        result = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=llm,
            mode="multi_agent_rebuttal", similarity=sim,
        )
        assert result["mode"] == "multi_agent_rebuttal"
        assert result["usage"]["calls"] == 2


class TestParseCrossExamOutput:
    def test_single_object(self):
        data = {
            "controversy_point_id": "1",
            "persona_evaluations": [{"persona_id": "P01", "pro_argument_score": 4}],
        }
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_cross_exam_output(raw)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["controversy_point_id"] == "1"

    def test_array_output(self):
        data = [
            {
                "controversy_point_id": "1",
                "persona_evaluations": [{"persona_id": "P01", "pro_argument_score": 4}],
            },
            {
                "controversy_point_id": "2",
                "persona_evaluations": [{"persona_id": "P02", "pro_argument_score": 3}],
            },
        ]
        raw = json.dumps(data, ensure_ascii=False)
        result = parse_cross_exam_output(raw)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_markdown_wrapped_json(self):
        data = [
            {
                "controversy_point_id": "1",
                "persona_evaluations": [{"persona_id": "P01", "pro_argument_score": 4}],
            }
        ]
        raw = f"```json\n{json.dumps(data, ensure_ascii=False)}\n```"
        result = parse_cross_exam_output(raw)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_parse_error_returns_empty_list(self):
        raw = "这不是JSON"
        result = parse_cross_exam_output(raw)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_non_string_input_does_not_crash(self):
        assert parse_cross_exam_output(None) == []
        assert parse_cross_exam_output(12345) == []


class TestConfidenceRescaleIsVisible:
    """0–1 之外的置信度照旧按量纲还原，但换算必须留痕（warning + usage 计数）。"""

    def test_values_and_behaviour_unchanged(self):
        from runner.cross_exam import _coerce_confidence
        assert _coerce_confidence(0.8) == 0.8
        assert _coerce_confidence("80%") == 0.8
        assert _coerce_confidence(8) == 0.8
        assert _coerce_confidence(85) == 0.85
        assert _coerce_confidence("0.4") == 0.4
        assert _coerce_confidence(None, 0.5) == 0.5
        assert _coerce_confidence(True) is None

    def test_rescale_logs_a_warning_and_in_range_values_do_not(self, caplog):
        import logging
        from runner.cross_exam import _coerce_confidence
        with caplog.at_level(logging.WARNING, logger="runner.cross_exam"):
            _coerce_confidence(0.8)
            _coerce_confidence("80%")
            assert caplog.records == []
            _coerce_confidence(8)
            _coerce_confidence(85)
        messages = [r.getMessage() for r in caplog.records]
        assert len(messages) == 2
        assert "0-10" in messages[0] and "0-100" in messages[1]

    def test_rescaled_flag(self):
        from runner.cross_exam import _confidence_was_rescaled
        assert _confidence_was_rescaled(8) is True
        assert _confidence_was_rescaled("72") is True
        assert _confidence_was_rescaled(0.8) is False
        assert _confidence_was_rescaled("80%") is False
        assert _confidence_was_rescaled(None) is False

    def test_run_summary_counts_rescaled_rebuttal_confidences(self, duel_outputs, duel_controversy, sim):
        clean = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=make_llm(moderated_response(b1_conf=0.2)), similarity=sim
        )
        assert clean["usage"]["confidence_values_rescaled"] == 0
        rescaled = run_cross_exam_protocol(
            duel_outputs, duel_controversy, llm_call=make_llm(moderated_response(b1_conf=20)), similarity=sim
        )
        assert rescaled["usage"]["confidence_values_rescaled"] == 1
        # 行为不变：20 仍按百分制还原成 0.20
        by_key = {c["persona_key"]: c for c in rescaled["confidence_changes"]}
        assert by_key["P01"]["after"] == 20
