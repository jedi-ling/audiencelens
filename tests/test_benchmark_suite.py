import json

import pytest

from tools.benchmark_suite import paired_bootstrap_ci, run_manifest


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _reference(issue):
    return {"reviewers": [{"id": "h1", "stance": "negative", "key_issues": [issue], "scores": {"clarity": 2}}]}


def _candidate(issue, stance="negative", cost=0.2):
    return {"reviews": [{"persona_id": "p1", "primary_stance": stance, "key_issues": [{"title": issue}], "scores": {"clarity": 2}}], "benchmark_meta": {"cost_usd": cost, "duration_minutes": 2}}


def test_suite_aggregates_cases_and_paired_delta(tmp_path):
    cases = []
    for i, issue in enumerate(("onboarding tutorial", "high pricing"), 1):
        _write(tmp_path / f"r{i}.json", _reference(issue))
        _write(tmp_path / f"a{i}.json", _candidate(issue, cost=0.4))
        _write(tmp_path / f"b{i}.json", _candidate("pretty visuals", "positive", 0.02))
        cases.append({"id": f"case-{i}", "reference": f"r{i}.json", "candidates": {"audiencelens": f"a{i}.json", "single_prompt": f"b{i}.json"}})
    manifest = {"name": "test-suite", "target_method": "audiencelens", "baseline_method": "single_prompt", "cases": cases}
    _write(tmp_path / "manifest.json", manifest)
    result = run_manifest(str(tmp_path / "manifest.json"))
    assert result["case_count"] == 2
    assert result["methods"][0]["method"] == "audiencelens"
    assert result["paired_comparison"]["mean_delta"] > 0
    assert result["paired_comparison"]["conclusion"] == "target_better"
    assert result["low_confidence"] is True
    assert result["methods"][0]["mean_cost_usd"] == 0.4


def test_bootstrap_is_deterministic():
    assert paired_bootstrap_ci([0.1, 0.2, 0.3]) == paired_bootstrap_ci([0.1, 0.2, 0.3])


def test_manifest_requires_cases(tmp_path):
    _write(tmp_path / "manifest.json", {"cases": []})
    with pytest.raises(ValueError, match="非空 cases"):
        run_manifest(str(tmp_path / "manifest.json"))


def test_suite_requires_same_methods_in_every_case(tmp_path):
    _write(tmp_path / "r.json", _reference("tutorial"))
    _write(tmp_path / "a.json", _candidate("tutorial"))
    _write(tmp_path / "b.json", _candidate("visuals"))
    manifest = {"cases": [
        {"id": "one", "reference": "r.json", "candidates": {"audiencelens": "a.json", "single_prompt": "b.json"}},
        {"id": "two", "reference": "r.json", "candidates": {"audiencelens": "a.json", "single_prompt": "b.json", "expert_quick": "b.json"}},
    ]}
    _write(tmp_path / "manifest.json", manifest)
    with pytest.raises(ValueError, match="方法集合"):
        run_manifest(str(tmp_path / "manifest.json"))
