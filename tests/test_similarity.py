import pytest

from runner.similarity import (
    IssueSimilarity,
    get_issue_similarity,
    lexical_similarity,
)
from runner.cross_exam import extract_controversy_points


def _has_semantic_model():
    sim = get_issue_similarity()
    return sim.method == "semantic"


class TestLexicalSimilarity:
    def test_identical(self):
        assert lexical_similarity("新手引导太长", "新手引导太长") == 1.0

    def test_different(self):
        assert lexical_similarity("新手引导太长", "美术风格不统一") < 0.5

    def test_force_lexical(self):
        sim = get_issue_similarity(force_lexical=True)
        assert sim.method == "lexical"
        assert sim.threshold == 0.7
        assert sim.is_same_issue("付费墙太早", "付费墙太早出现")
        assert not sim.is_same_issue("付费墙太早", "缺少手柄支持")


class TestExtractWithInjectedSimilarity:
    def _outputs(self):
        return [
            {
                "persona_id": "P01",
                "key_issues": [
                    {"title": "新手引导太长", "severity": "high"},
                ],
            },
            {
                "persona_id": "P02",
                "key_issues": [
                    {"title": "新手引导太长", "severity": "low"},
                ],
            },
        ]

    def test_lexical_merges_identical_titles(self):
        sim = get_issue_similarity(force_lexical=True)
        points = extract_controversy_points(self._outputs(), similarity=sim)
        assert len(points) == 1
        assert len(points[0]["persona_views"]) == 2
        assert points[0]["dedup_method"] == "lexical"

    def test_dedup_method_recorded(self):
        points = extract_controversy_points(self._outputs())
        assert points[0]["dedup_method"] in ("semantic", "lexical")


@pytest.mark.skipif(
    not _has_semantic_model(),
    reason="sentence-transformers / bge-small-zh 模型不可用",
)
class TestSemanticSimilarity:
    def test_semantic_merges_paraphrases(self):
        sim = get_issue_similarity()
        # 措辞不同、语义相同：字符串相似度合不上，语义应能合上
        # 阈值 0.65 经 bge-small-zh 实测校准：新手引导太长太啰嗦 vs 教程阶段过于冗长 = 0.66
        assert sim.is_same_issue("新手引导太长太啰嗦", "教程阶段过于冗长")

    def test_semantic_merges_soft_paraphrases(self):
        sim = get_issue_similarity()
        # 闪退崩溃 vs 程序崩溃 = 0.69, 在 0.65 阈值下应命中
        assert sim.is_same_issue("闪退崩溃", "程序崩溃")

    def test_semantic_keeps_distinct_issues(self):
        sim = get_issue_similarity()
        assert not sim.is_same_issue("付费设计太激进", "缺少色盲辅助模式")


class TestEvaluatorSemanticDimension:
    """P1-3: evaluator persona_differentiation 应记录 dedup_method"""

    def test_persona_differentiation_records_dedup_method(self):
        from harness.evaluator import _evaluate_persona_differentiation
        report = {
            "persona_reviews": [
                {
                    "persona_id": "P01",
                    "key_issues": [
                        {"title": "新手引导太长", "severity": "high"},
                    ],
                },
                {
                    "persona_id": "P02",
                    "key_issues": [
                        {"title": "付费设计太激进", "severity": "medium"},
                    ],
                },
            ],
        }
        result = _evaluate_persona_differentiation(report, {})
        assert "dedup_method" in result["details"]
        assert result["details"]["dedup_method"] in ("semantic", "lexical")
