"""跨案例基准套件：聚合质量、成本、耗时和配对增益置信区间。"""

import json
import random
import statistics
from pathlib import Path

from tools.benchmark_compare import compare_methods


def _load(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    fraction = pos - lo
    return ordered[lo] * (1 - fraction) + ordered[hi] * fraction


def paired_bootstrap_ci(deltas, iterations=2000, seed=42):
    """对案例级配对差值做确定性 bootstrap；小样本仍明确标低置信度。"""
    if not deltas:
        return {"mean_delta": None, "ci95": [None, None]}
    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        sample = [rng.choice(deltas) for _ in deltas]
        means.append(statistics.mean(sample))
    return {
        "mean_delta": round(statistics.mean(deltas), 4),
        "ci95": [round(_percentile(means, 0.025), 4), round(_percentile(means, 0.975), 4)],
    }


def run_suite(manifest: dict, base_dir: Path) -> dict:
    cases = manifest.get("cases") or []
    if not cases:
        raise ValueError("manifest 必须包含非空 cases")
    target = manifest.get("target_method", "audiencelens")
    baseline = manifest.get("baseline_method", "single_prompt")
    per_case, by_method = [], {}
    expected_methods = None

    for case in cases:
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            raise ValueError("每个案例必须有 id")
        reference = _load(base_dir / case["reference"])
        candidates = {name: _load(base_dir / path) for name, path in case["candidates"].items()}
        method_set = set(candidates)
        if expected_methods is None:
            expected_methods = method_set
        elif method_set != expected_methods:
            raise ValueError(f"案例 {case_id} 的候选方法集合与其他案例不一致")
        if target not in candidates or baseline not in candidates:
            raise ValueError(f"案例 {case_id} 缺少 target/baseline 方法")
        result = compare_methods(candidates, reference)
        scores = {row["method"]: row["overall_score"] for row in result["methods"]}
        per_case.append({
            "case_id": case_id,
            "winner": result["winner"],
            "reference_sample_size": result["reference_sample_size"],
            "scores": scores,
            "target_delta_vs_baseline": round(scores[target] - scores[baseline], 4),
        })
        for row in result["methods"]:
            bucket = by_method.setdefault(row["method"], {"scores": [], "costs": [], "durations": [], "wins": 0})
            bucket["scores"].append(row["overall_score"])
            if row["cost_usd"] is not None:
                bucket["costs"].append(float(row["cost_usd"]))
            if row["duration_minutes"] is not None:
                bucket["durations"].append(float(row["duration_minutes"]))
            bucket["wins"] += int(row["overall_score"] == result["methods"][0]["overall_score"])

    methods = []
    for method, bucket in by_method.items():
        mean_score = statistics.mean(bucket["scores"])
        mean_cost = statistics.mean(bucket["costs"]) if bucket["costs"] else None
        methods.append({
            "method": method,
            "case_count": len(bucket["scores"]),
            "mean_score": round(mean_score, 4),
            "score_stdev": round(statistics.stdev(bucket["scores"]), 4) if len(bucket["scores"]) > 1 else 0.0,
            "win_rate": round(bucket["wins"] / len(cases), 4),
            "mean_cost_usd": round(mean_cost, 4) if mean_cost is not None else None,
            "mean_duration_minutes": round(statistics.mean(bucket["durations"]), 2) if bucket["durations"] else None,
            "quality_per_dollar": round(mean_score / mean_cost, 4) if mean_cost and mean_cost > 0 else None,
        })
    methods.sort(key=lambda row: row["mean_score"], reverse=True)
    deltas = [case["target_delta_vs_baseline"] for case in per_case]
    paired = paired_bootstrap_ci(deltas)
    paired.update({"target": target, "baseline": baseline})
    low, high = paired["ci95"]
    paired["conclusion"] = (
        "target_better" if low is not None and low > 0
        else "target_worse" if high is not None and high < 0
        else "inconclusive"
    )
    return {
        "suite_name": manifest.get("name", "unnamed-suite"),
        "case_count": len(cases),
        "low_confidence": len(cases) < 10,
        "methods": methods,
        "paired_comparison": paired,
        "cases": per_case,
    }


def run_manifest(path: str) -> dict:
    manifest_path = Path(path).resolve()
    return run_suite(_load(manifest_path), manifest_path.parent)
