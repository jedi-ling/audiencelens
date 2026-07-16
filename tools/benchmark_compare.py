"""统一基线比较：多个候选评审方法对同一份真人研究参考答案评分。"""

import hashlib
import json
from pathlib import Path

from tools.parity_check import compute_parity


def _fingerprint(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def _has_candidate_content(payload) -> bool:
    if isinstance(payload, list):
        return len(payload) > 0
    if not isinstance(payload, dict):
        return False
    if isinstance(payload.get("reviews"), list):
        return len(payload["reviews"]) > 0
    if isinstance(payload.get("persona_notes"), list):
        return len(payload["persona_notes"]) > 0
    return bool(payload.get("key_issues") or payload.get("scores") or payload.get("primary_stance"))


def compare_methods(candidates: dict, reference: dict) -> dict:
    """返回排序、相对增益和盲测标识；不允许把参考答案当候选。"""
    if len(candidates) < 2:
        raise ValueError("至少需要两个候选方法才能比较")
    if not reference.get("reviewers"):
        raise ValueError("参考数据必须包含非空 reviewers")
    if reference.get("collected_after_candidates_frozen") is False:
        raise ValueError("参考数据尚未确认在候选封存后收集")

    reference_fp = _fingerprint(reference)
    rows = []
    seen = set()
    for method, payload in candidates.items():
        name = method.strip()
        if not name or name in seen:
            raise ValueError("候选方法名称不能为空或重复")
        seen.add(name)
        fp = _fingerprint(payload)
        if fp == reference_fp:
            raise ValueError(f"候选 {name} 与参考答案相同，疑似数据泄漏")
        if not _has_candidate_content(payload):
            raise ValueError(f"候选 {name} 没有可评分的 reviews/persona_notes")
        parity = compute_parity(payload, reference)
        meta = payload.get("benchmark_meta", {}) if isinstance(payload, dict) else {}
        rows.append({
            "method": name,
            "blind_id": f"candidate-{fp[:6]}",
            "overall_score": parity["overall_score"],
            "dimensions": {d["key"]: d["score"] for d in parity["dimensions"]},
            "cost_usd": meta.get("cost_usd"),
            "duration_minutes": meta.get("duration_minutes"),
        })

    rows.sort(key=lambda r: r["overall_score"], reverse=True)
    best = rows[0]["overall_score"]
    for i, row in enumerate(rows, 1):
        row["rank"] = i
        row["gap_to_best"] = round(row["overall_score"] - best, 4)

    scores = [r["overall_score"] for r in rows]
    return {
        "reference_fingerprint": reference_fp,
        "reference_sample_size": len(reference["reviewers"]),
        "low_confidence": len(reference["reviewers"]) < 10,
        "winner": rows[0]["method"],
        "score_spread": round(max(scores) - min(scores), 4),
        "methods": rows,
    }


def load_candidate(spec: str):
    if "=" not in spec:
        raise ValueError("候选格式应为 name=path.json")
    name, path = spec.split("=", 1)
    with open(Path(path), "r", encoding="utf-8") as f:
        return name, json.load(f)
