#!/usr/bin/env python3
"""AudienceLens Parity Check — CLI 集成版本（下划线命名）

导出 compute_parity(synthetic_data, human_data) -> dict 供 CLI 调用，
同时保留独立运行入口。
"""

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone


# ── 常量 ──────────────────────────────────────────────────────────────

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

DIMENSIONS = [
    {"name": "主题重叠", "key": "topic_overlap", "weight": 0.30},
    {"name": "评分相关性", "key": "score_correlation", "weight": 0.25},
    {"name": "立场对齐", "key": "stance_alignment", "weight": 0.25},
    {"name": "深度对齐", "key": "depth_alignment", "weight": 0.20},
]

WEIGHTS = {d["key"]: d["weight"] for d in DIMENSIONS}

SYNTHETICUSERS_BENCHMARK = {"low": 0.85, "high": 0.92}

PASS_THRESHOLD = 0.6


# ── 工具函数 ──────────────────────────────────────────────────────────

def normalize_text(text):
    if not text:
        return ""
    return text.lower().strip()


def extract_tokens(text):
    if not text:
        return set()
    normalized = normalize_text(text)
    tokens = set(re.findall(r"[a-z0-9_]{3,}", normalized))
    # 中文没有天然空格：对连续汉字生成 2/3-gram，使“教程太长”和
    # “教程长度过高”仍能共享“教程”，同时避免单字带来的虚假重叠。
    for segment in re.findall(r"[\u4e00-\u9fff]+", normalized):
        for size in (2, 3):
            if len(segment) >= size:
                tokens.update(segment[i:i + size] for i in range(len(segment) - size + 1))
    return tokens


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


# ── 数据解析 ──────────────────────────────────────────────────────────

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


# ── 维度计算 ──────────────────────────────────────────────────────────

def _compute_topic_overlap(synthetic, human):
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


def _compute_score_correlation(synthetic, human):
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


def _compute_stance_alignment(synthetic, human):
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


def _compute_depth_alignment(synthetic, human):
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


# ── 维度 key → 计算函数映射 ───────────────────────────────────────────

_DIMENSION_COMPUTERS = {
    "topic_overlap": _compute_topic_overlap,
    "score_correlation": _compute_score_correlation,
    "stance_alignment": _compute_stance_alignment,
    "depth_alignment": _compute_depth_alignment,
}


# ── SyntheticUsers 基准对比 ──────────────────────────────────────────

def _compare_with_benchmark(overall_score):
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
        "percentile_estimate": round(
            min(max((overall_score - 0.5) / 0.5, 0), 1) * 100, 1
        ),
    }


# ── 等级计算 ─────────────────────────────────────────────────────────

def _grade(score):
    if score >= 0.90:
        return "A"
    if score >= 0.80:
        return "B"
    if score >= 0.70:
        return "C"
    if score >= 0.60:
        return "D"
    return "F"


# ── 公开 API ─────────────────────────────────────────────────────────

def compute_parity(synthetic_data: dict, human_data: dict) -> dict:
    """计算合成评审与真人评审的一致性。

    Parameters
    ----------
    synthetic_data : dict
        合成评审数据（支持 AudienceLens 单评审、评审数组、聚合报告格式）。
    human_data : dict
        真人评审数据（需包含 ``reviewers`` 列表）。

    Returns
    -------
    dict
        包含 dimensions、overall_score、grade、synthetic_baseline 的结果字典。
    """

    synthetic = parse_synthetic(synthetic_data)
    human = parse_human(human_data)

    if not synthetic:
        raise ValueError("无法从 synthetic_data 中解析出合成评审者")
    if not human:
        raise ValueError("无法从 human_data 中解析出真人评审者")

    # 逐维度计算
    dim_results = []
    for dim in DIMENSIONS:
        key = dim["key"]
        computer = _DIMENSION_COMPUTERS[key]
        result = computer(synthetic, human)
        score = result["score"]
        dim_results.append({
            "name": dim["name"],
            "key": key,
            "weight": dim["weight"],
            "score": score,
            "passed": score >= PASS_THRESHOLD,
        })

    # 加权总分
    overall_score = round(
        sum(d["weight"] * d["score"] for d in dim_results), 4
    )

    # SyntheticUsers 基准对比
    synthetic_baseline = _compare_with_benchmark(overall_score)

    return {
        "dimensions": dim_results,
        "overall_score": overall_score,
        "grade": _grade(overall_score),
        "synthetic_baseline": synthetic_baseline,
    }


# ── CLI 入口 ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AudienceLens Parity Check — 合成评审 vs 真人评审一致性验证"
    )
    parser.add_argument(
        "--synthetic",
        required=True,
        help="AudienceLens 生成的 JSON 报告路径",
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

    result = compute_parity(synthetic_data, human_data)

    # 附加元信息用于 CLI 输出
    output = {
        "meta": {
            "tool": "AudienceLens Parity Check",
            "version": "2.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        **result,
    }

    output_json = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print("Report written to " + args.output, file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
