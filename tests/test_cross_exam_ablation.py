"""交叉质询消融的指标层测试。

全部离线：指标是纯函数，不需要 API Key。实验执行那一层要真实调用，
覆盖不到，所以这里守住的是"数字算得对不对"和"结论措辞有没有越界"。
"""

import pytest

from harness.cross_exam_ablation import (
    BASELINE_CONDITION,
    CONDITION_TO_REVIEW_MODE,
    build_verdict,
    consensus_delta,
    fix_list_delta,
    match_index,
    summarize_condition,
)
from runner.similarity import get_issue_similarity

SIM = get_issue_similarity()


def _report(fixes, agreed=None, disagreements=None):
    return {
        "priority_fixes": [
            {"priority": i + 1, "issue": t, "severity": "high"}
            for i, t in enumerate(fixes)
        ],
        "consensus": {"agreed_points": agreed or [], "questioned_points": []},
        "major_disagreements": [{"issue": d} for d in (disagreements or [])],
    }


# ---------------- match_index ----------------

def test_match_index_finds_identical():
    assert match_index("新手引导太长", ["定价偏高", "新手引导太长"], SIM) == 1


def test_match_index_returns_none_below_threshold():
    assert match_index("新手引导太长", ["服务器在澳洲"], SIM) is None


# ---------------- fix_list_delta ----------------

def test_identical_lists_have_zero_delta():
    titles = ["新手引导太长", "定价偏高", "缺少中文"]
    d = fix_list_delta(titles, titles, SIM)
    assert d["net_new"] == 0
    assert d["dropped"] == 0
    assert d["delta_ratio"] == 0.0
    assert d["rank_churn"] == 0.0
    assert d["matched"] == 3


def test_pure_reordering_is_churn_not_content_change():
    """只重排必须表现为 rank_churn>0 且 delta_ratio==0。

    这是本实验最关键的一条区分：交叉质询若只调了优先级顺序、没带来任何新结论，
    不能被读成"改变了报告"。
    """
    base = ["新手引导太长", "定价偏高", "缺少中文"]
    variant = ["缺少中文", "新手引导太长", "定价偏高"]
    d = fix_list_delta(base, variant, SIM)
    assert d["delta_ratio"] == 0.0
    assert d["net_new"] == 0
    assert d["dropped"] == 0
    assert d["rank_churn"] > 0


def test_added_item_counts_as_net_new():
    d = fix_list_delta(["新手引导太长"], ["新手引导太长", "服务器延迟高"], SIM)
    assert d["net_new"] == 1
    assert d["dropped"] == 0


def test_removed_item_counts_as_dropped():
    d = fix_list_delta(["新手引导太长", "服务器延迟高"], ["新手引导太长"], SIM)
    assert d["net_new"] == 0
    assert d["dropped"] == 1
    assert d["delta_ratio"] == 0.5


def test_empty_baseline_does_not_divide_by_zero():
    d = fix_list_delta([], ["新手引导太长"], SIM)
    assert d["net_new"] == 1
    assert d["delta_ratio"] == 1.0
    assert d["rank_churn"] == 0.0


def test_rank_churn_is_normalized_to_unit_interval():
    base = [f"议题{i}" for i in range(8)]
    d = fix_list_delta(base, list(reversed(base)), SIM)
    assert 0.0 <= d["rank_churn"] <= 1.0


# ---------------- consensus_delta ----------------

def test_consensus_delta_detects_moved_point():
    base = _report([], agreed=["核心循环有吸引力"], disagreements=[])
    variant = _report([], agreed=[], disagreements=["核心循环有吸引力"])
    d = consensus_delta(base, variant, SIM)
    assert d["agreed_removed"] == 1
    assert d["disagreement_added"] == 1


def test_consensus_delta_zero_when_unchanged():
    r = _report([], agreed=["核心循环有吸引力"], disagreements=["定价偏高"])
    assert all(v == 0 for v in consensus_delta(r, r, SIM).values())


# ---------------- verdict 措辞边界 ----------------

def _summary(net_new=0, dropped=0, churn=0.0, consensus=None):
    return {
        "priority_fixes": {
            "net_new": net_new, "dropped": dropped, "rank_churn": churn,
            "baseline_count": 3, "variant_count": 3, "matched": 3, "delta_ratio": 0.0,
        },
        "consensus": consensus or {
            "agreed_added": 0, "agreed_removed": 0,
            "disagreement_added": 0, "disagreement_removed": 0,
        },
    }


def test_verdict_no_change_is_a_definitive_negative():
    v = build_verdict({BASELINE_CONDITION: _summary(), "moderated": _summary()})
    assert v["unchanged_conditions"] == ["moderated"]
    assert "纯成本" in v["headline"]


def test_verdict_reshuffle_only_is_called_out_separately():
    v = build_verdict({BASELINE_CONDITION: _summary(), "moderated": _summary(churn=0.4)})
    assert v["reshuffle_only_conditions"] == ["moderated"]
    assert "只改变了优先级排序" in v["headline"]


def test_verdict_never_claims_improvement():
    """变了 ≠ 变好了。结论措辞不允许替读者做这个跳跃。"""
    v = build_verdict({BASELINE_CONDITION: _summary(), "moderated": _summary(net_new=2)})
    assert v["changed_conditions"] == ["moderated"]
    assert "不能证明" in v["headline"]
    for word in ("变好", "更好", "提升", "改善"):
        assert word not in v["headline"].replace("不能证明**变好了**", "")


def test_verdict_always_carries_single_sample_caveat():
    v = build_verdict({BASELINE_CONDITION: _summary(), "moderated": _summary(net_new=1)})
    assert "不可外推" in v["caveat"]


def test_baseline_itself_is_excluded_from_verdict():
    v = build_verdict({BASELINE_CONDITION: _summary(net_new=9)})
    assert v["changed_conditions"] == []
    assert v["unchanged_conditions"] == []


# ---------------- summarize_condition ----------------

def test_summarize_reports_suppressed_changes_for_theta_calibration():
    """suppressed_changes 必须透出：它是校准 θ=0.15 的唯一数据来源。"""
    base = _report(["新手引导太长"])
    ce = {
        "mode": "moderated_rebuttal", "is_live_debate": True,
        "points": [{"id": "C1"}],
        "vote_changes": [{"persona_id": "P01"}],
        "suppressed_changes": [{"persona_id": "P02"}, {"persona_id": "P03"}],
    }
    s = summarize_condition(base, base, ce, {"calls": 1, "cost": 0.012}, SIM)
    assert s["vote_changes"] == 1
    assert s["suppressed_changes"] == 2
    assert s["cost"]["calls"] == 1


def test_summarize_baseline_condition_has_no_debate():
    base = _report(["新手引导太长"])
    s = summarize_condition(base, base, None, {}, SIM)
    assert s["is_live_debate"] is False
    assert s["cost"]["calls"] == 0


# ---------------- 实验设计不变量 ----------------

def test_conditions_map_to_distinct_review_modes():
    """两个反驳条件必须落到不同档位，否则实验没有对比意义。"""
    assert set(CONDITION_TO_REVIEW_MODE.values()) == {"standard", "full"}


def test_baseline_is_required():
    from harness.cross_exam_ablation import run_cross_exam_ablation

    with pytest.raises(ValueError, match="必须含基线"):
        run_cross_exam_ablation(
            "concept_review", {"title": "x"},
            conditions=["moderated"], api_key="dummy",
        )
