import pytest

from src.runner.adaptive_panel import recommend_next_persona, score_candidate
from src.runner.panel_selector import DISTANCE_AXES


def _persona(pid, level="中", affinity=0.5, evidence=()):
    return {
        "id": pid,
        "behavior_profile": {axis: level for axis in DISTANCE_AXES},
        "task_affinity": {"concept_review": affinity},
        "evidence_types_needed": list(evidence),
    }


def test_candidate_score_exposes_each_component():
    selected = [_persona("selected", "很低")]
    candidate = _persona("candidate", "很高", 0.8, ["价格"])
    result = score_candidate(
        candidate, selected, "concept_review", unresolved_evidence=["价格", "团队"]
    )
    assert result["components"] == {
        "task_affinity": 0.8,
        "behavioral_novelty": 1.0,
        "evidence_gap_coverage": 0.5,
    }
    assert result["method"] == "marginal_value_proxy_v1"


def test_recommends_candidate_with_more_marginal_value():
    selected = [_persona("selected", "很低")]
    redundant = _persona("redundant", "很低", 0.9)
    novel = _persona("novel", "很高", 0.6, ["价格"])
    result = recommend_next_persona(
        [redundant, novel],
        selected,
        "concept_review",
        unresolved_evidence=["价格"],
    )
    assert result["should_continue"] is True
    assert result["recommended_persona_id"] == "novel"
    assert "not measured information gain" in result["limitation"]


def test_selected_personas_are_not_ranked_again():
    selected = [_persona("same", "很低")]
    result = recommend_next_persona(selected, selected, "concept_review")
    assert result["should_continue"] is False
    assert result["recommended_persona_id"] is None


def test_stops_below_threshold():
    candidate = _persona("weak", "中", affinity=0.0)
    result = recommend_next_persona(
        [candidate], [_persona("selected", "中")], "concept_review", min_score=0.1
    )
    assert result["best_score"] == 0.0
    assert result["should_continue"] is False


def test_invalid_weights_fail_loudly():
    with pytest.raises(ValueError, match="unknown adaptive-panel weights"):
        score_candidate(_persona("x"), [], "concept_review", weights={"magic": 1})
