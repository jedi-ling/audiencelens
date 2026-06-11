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
        assert sim.is_same_issue("新手引导太长太啰嗦", "教程阶段过于冗长")

    def test_semantic_keeps_distinct_issues(self):
        sim = get_issue_similarity()
        assert not sim.is_same_issue("付费设计太激进", "缺少色盲辅助模式")
