#!/usr/bin/env python3
"""AudienceLens Parity Check — 合成评审 vs 真人评审一致性验证"""

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone


STANCE_MAP = {
    "positive": "positive",
    "negative": "negative",
    "neutral": "neutral",
    "mixed": "neutral",
    "cautiously_optimistic": "positive",
    "skeptical": "negative",
    "enthusiastic": "positive",
    "dismissive": "negative",
    "undecided": "neutral",
    "wait_and_see": "neutral",
    "concerned": "negative",
    "impressed": "positive",
    "disappointed": "negative",
    "hopeful": "positive",
    "frustrated": "negative",
    "intrigued": "positive",
    "indifferent": "neutral",
    "worried": "negative",
    "excited": "positive",
    "confused": "neutral",
}

WEIGHTS = {
    "thematic_overlap": 0.30,
    "score_correlation": 0.25,
    "stance_alignment": 0.25,
    "depth_alignment": 0.20,
}

SYNTHETICUSERS_BENCHMARK = {"low": 0.85, "high": 0.92}


def normalize_text(text):
    if not text:
        return ""
    return text.lower().strip()


def extract_tokens(text):
    if not text:
        return set()
    words = normalize_text(text).split()
    return set(w for w in words if len(w) > 2)


def jaccard_similarity(set_a, set_b):
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def map_stance(raw_stance):
    if not raw_stance:
        return "neutral"
    key = normalize_text(raw_stance).replace(" ", "_").replace("-", "_")
    return STANCE_MAP.get(key, "neutral")


def rank_values(values):
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda x: (x[1], x[0]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and indexed[j + 1][1] == indexed[j][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def spearman_correlation(x, y):
    if len(x) != len(y):
        raise ValueError("Lists must have equal length")
    n = len(x)
    if n < 2:
        return 0.0
    rx = rank_values(x)
    ry = rank_values(y)
    d_sq_sum = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    denom = n * (n ** 2 - 1)
    if denom == 0:
        return 0.0
    rho = 1.0 - (6.0 * d_sq_sum / denom)
    return max(-1.0, min(1.0, rho))


def chi_square_distance(dist_a, dist_b):
    categories = set(dist_a.keys()) | set(dist_b.keys())
    if not categories:
        return 0.0
    total_a = sum(dist_a.values())
    total_b = sum(dist_b.values())
    if total_a == 0 or total_b == 0:
        return 0.0
    chi_sq = 0.0
    for cat in categories:
        ea = dist_a.get(cat, 0) / total_a
        eb = dist_b.get(cat, 0) / total_b
        expected = (ea + eb) / 2.0
        if expected > 0:
            chi_sq += (ea - eb) ** 2 / expected
    return chi_sq


def distribution_similarity(dist_a, dist_b):
    chi = chi_square_distance(dist_a, dist_b)
    return 1.0 / (1.0 + chi)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_synthetic(data):
    reviewers = []
    if isinstance(data, list):
        items = data
    elif "persona_notes" in data:
        notes = data["persona_notes"]
        items = []
        for note in notes:
            item = {
                "persona_id": note.get("persona_id", ""),
                "persona_name": note.get("persona_name", ""),
                "primary_stance": note.get("stance", "neutral"),
                "key_issues": [{"title": t} for t in note.get("top_issues", [])],
                "scores": {"base": {}},
                "evidence": [{"content": e} for e in note.get("evidence_top3", [])],
            }
            items.append(item)
    elif "reviews" in data:
        items = data["reviews"]
    else:
        items = [data]

    for item in items:
        stance = item.get("primary_stance", "neutral")
        raw_issues = item.get("key_issues", [])
        issue_titles = []
        for iss in raw_issues:
            if isinstance(iss, str):
                issue_titles.append(iss)
            elif isinstance(iss, dict):
                issue_titles.append(iss.get("title", ""))

        raw_scores = item.get("scores", {})
        flat_scores = {}
        if isinstance(raw_scores, dict):
            base = raw_scores.get("base", {})
            if isinstance(base, dict):
                flat_scores.update(base)
            task_sp = raw_scores.get("task_specific", {})
            if isinstance(task_sp, dict):
                flat_scores.update(task_sp)
            if "base" not in raw_scores and "task_specific" not in raw_scores:
                flat_scores.update(raw_scores)

        raw_evidence = item.get("evidence", [])
        evidence_items = []
        for ev in raw_evidence:
            if isinstance(ev, str):
                evidence_items.append({"content": ev, "inference_level": "direct"})
            elif isinstance(ev, dict):
                evidence_items.append(ev)

        reviewers.append({
            "id": item.get("persona_id", ""),
            "name": item.get("persona_name", ""),
            "stance": map_stance(stance),
            "stance_raw": stance,
            "key_issues": [t for t in issue_titles if t],
            "scores": flat_scores,
            "evidence": evidence_items,
            "evidence_sufficiency": item.get("evidence_sufficiency", 0.5),
            "confidence": item.get("confidence", 0.5),
        })

    return reviewers


def parse_human(data):
    reviewers = []
    for r in data.get("reviewers", []):
        raw_issues = r.get("key_issues", [])
        issue_list = []
        for iss in raw_issues:
            if isinstance(iss, str):
                issue_list.append(iss)
            elif isinstance(iss, dict):
                issue_list.append(iss.get("title", ""))

        raw_scores = r.get("scores", {})
        flat_scores = {}
        if isinstance(raw_scores, dict):
            flat_scores.update(raw_scores)

        stance = r.get("stance", "neutral")
        depth = r.get("depth", None)
        evidence_detail = r.get("evidence_detail", None)

        reviewers.append({
            "id": r.get("id", ""),
            "stance": map_stance(stance),
            "stance_raw": stance,
            "key_issues": [t for t in issue_list if t],
            "scores": flat_scores,
            "evidence": [],
            "evidence_sufficiency": 0.5,
            "confidence": 0.5,
            "depth": depth,
            "evidence_detail": evidence_detail,
        })

    return reviewers


def compute_thematic_overlap(synthetic, human):
    if not synthetic or not human:
        return {"score": 0.0, "details": {}}

    all_syn_tokens = set()
    for r in synthetic:
        for issue in r["key_issues"]:
            all_syn_tokens |= extract_tokens(issue)

    all_human_tokens = set()
    for r in human:
        for issue in r["key_issues"]:
            all_human_tokens |= extract_tokens(issue)

    overall_jaccard = jaccard_similarity(all_syn_tokens, all_human_tokens)

    per_pair_scores = []
    for sr in synthetic:
        sr_tokens = set()
        for issue in sr["key_issues"]:
            sr_tokens |= extract_tokens(issue)
        best_score = 0.0
        for hr in human:
            hr_tokens = set()
            for issue in hr["key_issues"]:
                hr_tokens |= extract_tokens(issue)
            score = jaccard_similarity(sr_tokens, hr_tokens)
            best_score = max(best_score, score)
        per_pair_scores.append(best_score)

    avg_best_match = statistics.mean(per_pair_scores) if per_pair_scores else 0.0
    combined = 0.5 * overall_jaccard + 0.5 * avg_best_match

    overlap_tokens = all_syn_tokens & all_human_tokens
    syn_only = all_syn_tokens - all_human_tokens
    human_only = all_human_tokens - all_syn_tokens

    return {
        "score": round(combined, 4),
        "details": {
            "overall_jaccard": round(overall_jaccard, 4),
            "avg_best_match": round(avg_best_match, 4),
            "shared_themes": sorted(overlap_tokens)[:20],
            "synthetic_only_themes": sorted(syn_only)[:20],
            "human_only_themes": sorted(human_only)[:20],
            "synthetic_issue_count": sum(len(r["key_issues"]) for r in synthetic),
            "human_issue_count": sum(len(r["key_issues"]) for r in human),
        },
    }


def compute_score_correlation(synthetic, human):
    syn_scores = {}
    for r in synthetic:
        for dim, val in r["scores"].items():
            if isinstance(val, (int, float)):
                syn_scores.setdefault(dim, []).append(val)

    human_scores = {}
    for r in human:
        for dim, val in r["scores"].items():
            if isinstance(val, (int, float)):
                human_scores.setdefault(dim, []).append(val)

    common_dims = set(syn_scores.keys()) & set(human_scores.keys())

    if not common_dims:
        syn_means = {}
        for dim, vals in syn_scores.items():
            if vals:
                syn_means[dim] = round(statistics.mean(vals), 2)
        human_means = {}
        for dim, vals in human_scores.items():
            if vals:
                human_means[dim] = round(statistics.mean(vals), 2)
        return {
            "score": 0.0,
            "details": {
                "common_dimensions": [],
                "per_dimension": {},
                "synthetic_avg_scores": syn_means,
                "human_avg_scores": human_means,
                "note": "No common score dimensions found between synthetic and human data",
            },
        }

    per_dim = {}
    rho_values = []

    for dim in sorted(common_dims):
        s_vals = syn_scores[dim]
        h_vals = human_scores[dim]
        s_mean = statistics.mean(s_vals) if s_vals else 0
        h_mean = statistics.mean(h_vals) if h_vals else 0

        s_padded = s_vals + [s_mean] * max(0, len(h_vals) - len(s_vals))
        h_padded = h_vals + [h_mean] * max(0, len(s_vals) - len(h_vals))

        min_len = min(len(s_padded), len(h_padded))
        if min_len >= 2:
            rho = spearman_correlation(s_padded[:min_len], h_padded[:min_len])
        else:
            rho = 0.0

        rho_values.append(rho)
        per_dim[dim] = {
            "spearman_rho": round(rho, 4),
            "synthetic_mean": round(s_mean, 2),
            "synthetic_n": len(s_vals),
            "human_mean": round(h_mean, 2),
            "human_n": len(h_vals),
        }

    avg_rho = statistics.mean(rho_values) if rho_values else 0.0
    normalized = (avg_rho + 1.0) / 2.0

    return {
        "score": round(normalized, 4),
        "details": {
            "common_dimensions": sorted(common_dims),
            "per_dimension": per_dim,
            "average_spearman_rho": round(avg_rho, 4),
            "note": "Score normalized from [-1,1] to [0,1] range",
        },
    }


def compute_stance_alignment(synthetic, human):
    syn_dist = Counter(r["stance"] for r in synthetic)
    human_dist = Counter(r["stance"] for r in human)

    for cat in ["positive", "neutral", "negative"]:
        syn_dist.setdefault(cat, 0)
        human_dist.setdefault(cat, 0)

    similarity = distribution_similarity(dict(syn_dist), dict(human_dist))

    syn_total = sum(syn_dist.values())
    human_total = sum(human_dist.values())

    syn_pct = {k: round(v / syn_total, 4) for k, v in syn_dist.items()} if syn_total else {}
    human_pct = {k: round(v / human_total, 4) for k, v in human_dist.items()} if human_total else {}

    return {
        "score": round(similarity, 4),
        "details": {
            "synthetic_distribution": dict(syn_dist),
            "human_distribution": dict(human_dist),
            "synthetic_percentages": syn_pct,
            "human_percentages": human_pct,
            "dominant_synthetic": syn_dist.most_common(1)[0][0] if syn_dist else "N/A",
            "dominant_human": human_dist.most_common(1)[0][0] if human_dist else "N/A",
        },
    }


def compute_depth_alignment(synthetic, human):
    syn_depths = []
    for r in synthetic:
        evidence = r.get("evidence", [])
        direct_count = sum(1 for e in evidence if e.get("inference_level") == "direct")
        total_evidence = len(evidence)
        avg_evidence_len = 0.0
        if total_evidence > 0:
            lengths = [len(e.get("content", "")) for e in evidence]
            avg_evidence_len = statistics.mean(lengths)

        depth_score = (
            0.4 * min(total_evidence / 5.0, 1.0)
            + 0.3 * (direct_count / max(total_evidence, 1))
            + 0.2 * min(avg_evidence_len / 200.0, 1.0)
            + 0.1 * r.get("evidence_sufficiency", 0.5)
        )
        syn_depths.append(depth_score)

    human_depths = []
    for r in human:
        explicit_depth = r.get("depth", None)
        if explicit_depth is not None and isinstance(explicit_depth, (int, float)):
            human_depths.append(min(max(explicit_depth, 0), 1))
            continue

        explicit_detail = r.get("evidence_detail", None)
        if explicit_detail is not None and isinstance(explicit_detail, (int, float)):
            human_depths.append(min(max(explicit_detail, 0), 1))
            continue

        issue_count = len(r.get("key_issues", []))
        score_count = len(r.get("scores", {}))
        has_stance = 1 if r.get("stance_raw") else 0

        depth_score = (
            0.4 * min(issue_count / 5.0, 1.0)
            + 0.3 * min(score_count / 4.0, 1.0)
            + 0.3 * has_stance
        )
        human_depths.append(depth_score)

    if not syn_depths or not human_depths:
        return {"score": 0.0, "details": {}}

    syn_mean = statistics.mean(syn_depths)
    human_mean = statistics.mean(human_depths)

    diff = abs(syn_mean - human_mean)
    alignment = 1.0 - min(diff, 1.0)

    syn_var = statistics.variance(syn_depths) if len(syn_depths) > 1 else 0.0
    human_var = statistics.variance(human_depths) if len(human_depths) > 1 else 0.0

    return {
        "score": round(alignment, 4),
        "details": {
            "synthetic_avg_depth": round(syn_mean, 4),
            "human_avg_depth": round(human_mean, 4),
            "depth_difference": round(diff, 4),
            "synthetic_depth_variance": round(syn_var, 4),
            "human_depth_variance": round(human_var, 4),
            "synthetic_n": len(syn_depths),
            "human_n": len(human_depths),
        },
    }


def compute_overall_parity(metrics):
    weighted_sum = (
        WEIGHTS["thematic_overlap"] * metrics["thematic_overlap"]["score"]
        + WEIGHTS["score_correlation"] * metrics["score_correlation"]["score"]
        + WEIGHTS["stance_alignment"] * metrics["stance_alignment"]["score"]
        + WEIGHTS["depth_alignment"] * metrics["depth_alignment"]["score"]
    )
    return round(weighted_sum, 4)


def compare_with_benchmark(overall_score):
    bench_low = SYNTHETICUSERS_BENCHMARK["low"]
    bench_high = SYNTHETICUSERS_BENCHMARK["high"]
    bench_mid = (bench_low + bench_high) / 2.0

    if overall_score >= bench_high:
        status = "exceeds_benchmark"
        gap = round(overall_score - bench_high, 4)
    elif overall_score >= bench_mid:
        status = "within_benchmark"
        gap = round(overall_score - bench_mid, 4)
    elif overall_score >= bench_low:
        status = "below_benchmark_mid"
        gap = round(overall_score - bench_low, 4)
    else:
        status = "below_benchmark"
        gap = round(overall_score - bench_low, 4)

    return {
        "syntheticusers_range": f"{bench_low:.0%}-{bench_high:.0%}",
        "syntheticusers_low": bench_low,
        "syntheticusers_high": bench_high,
        "audience_lens_score": overall_score,
        "comparison_status": status,
        "gap_from_low": gap,
        "percentile_estimate": round(min(max((overall_score - 0.5) / 0.5, 0), 1) * 100, 1),
    }


def _generate_recommendations(metrics, overall):
    recs = []

    thematic = metrics["thematic_overlap"]["score"]
    if thematic < 0.5:
        syn_only = metrics["thematic_overlap"]["details"].get("synthetic_only_themes", [])
        human_only = metrics["thematic_overlap"]["details"].get("human_only_themes", [])
        if human_only:
            recs.append({
                "area": "thematic_overlap",
                "priority": "high",
                "message": (
                    "Human reviewers raised themes not covered by synthetic: "
                    + str(human_only[:5])
                    + ". Consider adding these to persona prompts."
                ),
            })
        if syn_only:
            recs.append({
                "area": "thematic_overlap",
                "priority": "medium",
                "message": (
                    "Synthetic raised themes not found in human reviews: "
                    + str(syn_only[:5])
                    + ". Verify if these are hallucinated concerns."
                ),
            })

    score_corr = metrics["score_correlation"]["score"]
    if score_corr < 0.5:
        per_dim = metrics["score_correlation"]["details"].get("per_dimension", {})
        weak_dims = [d for d, info in per_dim.items() if info.get("spearman_rho", 0) < 0]
        if weak_dims:
            recs.append({
                "area": "score_correlation",
                "priority": "high",
                "message": (
                    "Negative correlation on dimensions: "
                    + str(weak_dims)
                    + ". Synthetic scores diverge from human judgment here."
                ),
            })

    stance = metrics["stance_alignment"]["score"]
    if stance < 0.6:
        syn_dom = metrics["stance_alignment"]["details"].get("dominant_synthetic", "N/A")
        human_dom = metrics["stance_alignment"]["details"].get("dominant_human", "N/A")
        recs.append({
            "area": "stance_alignment",
            "priority": "medium",
            "message": (
                "Stance mismatch: synthetic tends " + syn_dom
                + ", human tends " + human_dom
                + ". Review persona calibration for bias."
            ),
        })

    depth = metrics["depth_alignment"]["score"]
    if depth < 0.6:
        syn_avg = metrics["depth_alignment"]["details"].get("synthetic_avg_depth", 0)
        human_avg = metrics["depth_alignment"]["details"].get("human_avg_depth", 0)
        if syn_avg < human_avg:
            recs.append({
                "area": "depth_alignment",
                "priority": "medium",
                "message": (
                    "Synthetic reviews are shallower (avg {:.2f}) than human (avg {:.2f}). "
                    "Enrich evidence generation prompts."
                ).format(syn_avg, human_avg),
            })
        else:
            recs.append({
                "area": "depth_alignment",
                "priority": "low",
                "message": (
                    "Synthetic reviews are deeper (avg {:.2f}) than human (avg {:.2f}). "
                    "May include unnecessary detail."
                ).format(syn_avg, human_avg),
            })

    if overall >= 0.85:
        recs.append({
            "area": "overall",
            "priority": "info",
            "message": "Overall parity is strong. Results are suitable for decision-making with standard caveats.",
        })
    elif overall >= 0.70:
        recs.append({
            "area": "overall",
            "priority": "info",
            "message": "Overall parity is moderate. Use synthetic insights as directional guidance, validate critical findings with human data.",
        })
    else:
        recs.append({
            "area": "overall",
            "priority": "high",
            "message": "Overall parity is low. Do not rely on synthetic results alone. Significant persona recalibration recommended.",
        })

    return recs


def generate_report(synthetic_data, human_data):
    synthetic = parse_synthetic(synthetic_data)
    human = parse_human(human_data)

    if not synthetic:
        print("Error: No synthetic reviewers could be parsed", file=sys.stderr)
        sys.exit(1)
    if not human:
        print("Error: No human reviewers could be parsed", file=sys.stderr)
        sys.exit(1)

    metrics = {
        "thematic_overlap": compute_thematic_overlap(synthetic, human),
        "score_correlation": compute_score_correlation(synthetic, human),
        "stance_alignment": compute_stance_alignment(synthetic, human),
        "depth_alignment": compute_depth_alignment(synthetic, human),
    }

    overall = compute_overall_parity(metrics)
    benchmark = compare_with_benchmark(overall)

    report = {
        "meta": {
            "tool": "AudienceLens Parity Check",
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "summary": {
            "overall_parity_score": overall,
            "parity_grade": (
                "A" if overall >= 0.90
                else "B" if overall >= 0.80
                else "C" if overall >= 0.70
                else "D" if overall >= 0.60
                else "F"
            ),
            "weights": WEIGHTS,
        },
        "metrics": metrics,
        "benchmark_comparison": benchmark,
        "sample_info": {
            "synthetic_reviewer_count": len(synthetic),
            "human_reviewer_count": len(human),
            "synthetic_ids": [r["id"] for r in synthetic if r["id"]],
            "human_ids": [r["id"] for r in human if r["id"]],
        },
        "recommendations": _generate_recommendations(metrics, overall),
    }

    return report


def main():
    parser = argparse.ArgumentParser(
        description="AudienceLens Parity Check — 合成评审 vs 真人评审一致性验证"
    )
    parser.add_argument(
        "--synthetic",
        required=True,
        help="AudienceLens 生成的 JSON 报告路径（支持单评审、评审数组、聚合报告）",
    )
    parser.add_argument(
        "--human",
        required=True,
        help="真人评审数据路径（JSON 格式）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出报告路径（默认输出到 stdout）",
    )

    args = parser.parse_args()

    synthetic_data = load_json(args.synthetic)
    human_data = load_json(args.human)

    report = generate_report(synthetic_data, human_data)

    output_json = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print("Report written to " + args.output, file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
