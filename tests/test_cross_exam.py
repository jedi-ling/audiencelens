import json
import os

import pytest

from runner.cross_exam import (
    extract_controversy_points,
    find_opposing_stances,
    parse_cross_exam_output,
    render_cross_exam_prompt,
    run_cross_exam_protocol,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "cross-exam-prompt.md")


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
        from runner.similarity import get_issue_similarity
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
        from runner.similarity import get_issue_similarity
        sim = get_issue_similarity(force_lexical=True)
        controversy = extract_controversy_points(persona_outputs, top_n=1, similarity=sim)[0]
        result = find_opposing_stances(controversy, persona_outputs, similarity=sim)
        assert "pro" in result
        assert "con" in result


class TestRenderCrossExamPrompt:
    def test_renders_controversy_points(self, persona_outputs):
        controversy = extract_controversy_points(persona_outputs, top_n=2)
        result = render_cross_exam_prompt(controversy, persona_outputs, TEMPLATE_PATH)
        assert "核心循环不清晰" in result

    def test_renders_pro_and_con_names(self, persona_outputs):
        controversy = extract_controversy_points(persona_outputs, top_n=2)
        result = render_cross_exam_prompt(controversy, persona_outputs, TEMPLATE_PATH)
        assert "林岚" in result or "周策" in result or "韩岳" in result


class TestRunCrossExamProtocol:
    def test_protocol_marks_derived_summary_not_live_debate(self, persona_outputs):
        controversy = extract_controversy_points(persona_outputs, top_n=1)
        result = run_cross_exam_protocol(persona_outputs, controversy)

        assert result["mode"] == "derived_summary"
        assert result["is_live_debate"] is False
        assert "limitation" in result
        assert result["vote_changes"] == []


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
