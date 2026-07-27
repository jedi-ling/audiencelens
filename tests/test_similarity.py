import pytest

from runner.similarity import (
    IssueSimilarity,
    get_issue_similarity,
    has_polarity_conflict,
    lexical_similarity,
    polarity_profile,
)
from runner.cross_exam import extract_controversy_points


def _has_semantic_model():
    sim = get_issue_similarity()
    return sim.method == "semantic"


# ---------------------------------------------------------------------------
# 极性冲突保护的两组回归用例
# ---------------------------------------------------------------------------
# 第一组：语义相反，词法相似度却高于 LEXICAL_THRESHOLD=0.7，修复前会被错误合并。
OPPOSITE_PAIRS = [
    ("价格太高", "价格太低"),                    # ratio 0.750
    ("美术风格不统一", "美术风格很统一"),          # ratio 0.857
    ("战斗手感差", "战斗手感好"),                 # ratio 0.800
    ("教程太长", "教程太短"),                    # ratio 0.750
    ("音效不够丰富", "音效很丰富"),               # ratio 0.727
    ("difficulty too high", "difficulty too low"),  # ratio 0.811
]

# 第二组：方向一致的同义/近义表述，极性保护绝不能把它们拆开。
SAME_DIRECTION_PAIRS = [
    ("价格太高", "定价偏贵"),
    ("新手引导太啰嗦", "教程过于冗长"),
    ("战斗手感差", "打击感很弱"),
    ("美术风格不统一", "美术风格杂乱"),  # 同向：两者都在说"不统一"
    ("combat feels bad", "combat feels weak"),
]


class TestPolarityConflictDetection:
    """极性否决：词法/语义再像，方向相反就不许合并。"""

    @pytest.mark.parametrize("a,b", OPPOSITE_PAIRS)
    def test_opposites_are_flagged(self, a, b):
        assert has_polarity_conflict(a, b), f"{a} / {b} 应判为极性冲突"
        assert has_polarity_conflict(b, a), "极性冲突判定必须对称"

    @pytest.mark.parametrize("a,b", OPPOSITE_PAIRS)
    def test_opposites_would_merge_without_guard(self, a, b):
        """记录 bug 本体：这些反义对的字符串相似度确实高于阈值。

        断言它，是为了保证这组用例始终在真正考验极性否决——
        而不是因为相似度本来就不达标而"碰巧"通过。
        """
        sim = get_issue_similarity(force_lexical=True)
        assert lexical_similarity(a, b) > sim.threshold
        assert sim.is_same_issue(a, b, check_polarity=False) is True

    @pytest.mark.parametrize("a,b", OPPOSITE_PAIRS)
    def test_opposites_not_same_issue_lexical(self, a, b):
        sim = get_issue_similarity(force_lexical=True)
        assert not sim.is_same_issue(a, b)

    @pytest.mark.parametrize("a,b", SAME_DIRECTION_PAIRS)
    def test_same_direction_not_flagged(self, a, b):
        assert not has_polarity_conflict(a, b), f"{a} / {b} 方向一致，不该被否决"
        assert not has_polarity_conflict(b, a)

    @pytest.mark.parametrize("a,b", SAME_DIRECTION_PAIRS)
    def test_same_direction_verdict_unchanged(self, a, b):
        """极性保护不得改变同向对的合并结论（开/关 guard 结果必须一致）。"""
        sim = get_issue_similarity(force_lexical=True)
        assert sim.is_same_issue(a, b) == sim.is_same_issue(a, b, check_polarity=False)

    @pytest.mark.parametrize(
        "a,b",
        [
            ("没有手柄支持", "有手柄支持"),      # 没有X vs 有X
            ("缺少存档功能", "存档功能"),        # 缺少X vs X
            ("no controller support", "controller support"),
            ("打击感不足", "打击感很强"),        # 后置否定
            ("手感不错", "手感很差"),
            ("难度太高", "难度太简单"),          # 换说法的反向
            ("剧情无聊", "剧情有趣"),
            ("统一性不足", "美术风格很统一"),
        ],
    )
    def test_extra_opposites_flagged(self, a, b):
        assert has_polarity_conflict(a, b)

    @pytest.mark.parametrize(
        "a,b",
        [
            ("付费墙太早", "付费墙太早出现"),     # 无极性词，纯扩写
            ("教程不清晰", "教程模糊"),          # 否定 vs 反义词，同向
            ("引导不友好", "引导很差"),          # 同上
            ("价格不高", "价格低"),
            ("难度太高", "难度偏高"),
            ("闪退崩溃", "程序崩溃"),
            ("art style is inconsistent", "art style is messy"),
        ],
    )
    def test_extra_same_direction_not_flagged(self, a, b):
        assert not has_polarity_conflict(a, b)


class TestPolarityProfile:
    """否定词必须能翻转极性，否则"不X vs X"这类最常见的反向表达会漏判。"""

    def test_plain_term(self):
        assert polarity_profile("美术风格很统一")["coherence"] == {"consistent"}

    def test_pre_negation_flips(self):
        assert polarity_profile("美术风格不统一")["coherence"] == {"messy"}

    def test_degree_negation_flips(self):
        assert polarity_profile("音效不够丰富")["amount"] == {"few"}

    def test_post_negation_flips(self):
        assert polarity_profile("统一性不足")["coherence"] == {"messy"}

    def test_english_negation_flips(self):
        assert polarity_profile("the pacing is not good")["quality"] == {"bad"}

    def test_neutral_noun_not_a_pole(self):
        # "难度"是维度名词，不该被读成"难"这个方向
        assert "difficulty" not in polarity_profile("难度太高")

    def test_no_polarity_words_yields_empty(self):
        assert polarity_profile("缺少手柄支持") == {}


class TestPolarityGuardAppliesToSemanticTier:
    """语义模型对反义句同样会给高分，所以否决必须在两个档都生效。"""

    def test_veto_beats_perfect_score(self):
        class AlwaysIdentical(IssueSimilarity):
            def similarity(self, a, b):
                return 1.0

        sim = AlwaysIdentical(force_lexical=True)
        sim.method = "semantic"
        sim.threshold = 0.65
        assert not sim.is_same_issue("价格太高", "价格太低")
        assert sim.is_same_issue("价格太高", "定价偏贵")

    def test_guard_can_be_disabled(self):
        sim = get_issue_similarity(force_lexical=True, check_polarity=False)
        assert sim.check_polarity is False
        assert sim.is_same_issue("价格太高", "价格太低")


class TestPolarityGuardInAggregation:
    """端到端：对立意见不该被塞进同一个聚类。"""

    def test_opposite_titles_stay_separate(self):
        outputs = [
            {"persona_id": "P01", "key_issues": [{"title": "价格太高", "severity": "high"}]},
            {"persona_id": "P02", "key_issues": [{"title": "价格太低", "severity": "high"}]},
        ]
        sim = get_issue_similarity(force_lexical=True)
        points = extract_controversy_points(outputs, similarity=sim)
        titles = {p["title"] for p in points}
        assert titles == {"价格太高", "价格太低"}
        for p in points:
            assert len(p["persona_views"]) == 1


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
