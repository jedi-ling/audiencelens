import pytest

from tools.benchmark_compare import compare_methods


REFERENCE = {
    "reviewers": [
        {"id": "h1", "stance": "negative", "key_issues": ["教程太长", "价格偏高"], "scores": {"clarity": 2}},
        {"id": "h2", "stance": "neutral", "key_issues": ["教程不清晰"], "scores": {"clarity": 3}},
    ]
}


def candidate(issue, stance="negative", cost=None):
    return {
        "reviews": [{
            "persona_id": "p1", "primary_stance": stance,
            "key_issues": [{"title": issue}], "scores": {"clarity": 2},
        }],
        "benchmark_meta": {"cost_usd": cost, "duration_minutes": 3},
    }


def test_compare_ranks_closer_method_first():
    result = compare_methods({
        "audiencelens": candidate("教程太长", cost=0.4),
        "single_prompt": candidate("画面漂亮", stance="positive", cost=0.02),
    }, REFERENCE)
    assert result["winner"] == "audiencelens"
    assert result["methods"][0]["rank"] == 1
    assert result["methods"][0]["cost_usd"] == 0.4
    assert result["low_confidence"] is True


def test_requires_multiple_candidates():
    with pytest.raises(ValueError, match="至少需要两个"):
        compare_methods({"only": candidate("教程太长")}, REFERENCE)


def test_rejects_reference_leakage():
    with pytest.raises(ValueError, match="数据泄漏"):
        compare_methods({"leak": REFERENCE, "other": candidate("价格偏高")}, REFERENCE)


def test_rejects_unfrozen_reference_and_empty_candidate():
    reference = {**REFERENCE, "collected_after_candidates_frozen": False}
    with pytest.raises(ValueError, match="候选封存"):
        compare_methods({"one": candidate("教程"), "two": candidate("价格")}, reference)
    with pytest.raises(ValueError, match="没有可评分"):
        compare_methods({"empty": {"reviews": []}, "other": candidate("价格")}, REFERENCE)
