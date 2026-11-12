"""Measure a grounding rule on tests/fixtures/grounding_eval/items.jsonl. No model calls.

    python scripts/eval_grounding.py                          # current validator, both splits
    python scripts/eval_grounding.py --rule legacy            # the old any-fragment rule
    python scripts/eval_grounding.py --split dev --sweep      # parameter grid, dev split only
    python scripts/eval_grounding.py --out-md x.md --out-json x.json

Rules
  validator  validate_evidence_grounding as it is in src/runner/validator.py right now
  legacy     a frozen copy of the any-fragment rule that shipped until 2026-11 (kept here so the
             baseline stays reproducible after the validator changed)

Scoring, per item: the rule accepts or rejects one `direct` entry against its material.
  precision          accepted items that are labelled grounded / all accepted (scored items)
  recall             grounded items accepted / grounded items
  false-accept rate  not-grounded items accepted / not-grounded items
  false-reject rate  grounded items rejected / grounded items
Items labelled `mixed` (real quote + commentary in one field) and `grounded_by_rule` (real
quote, fabricated claim in the comment: a known limit) are not scored; their accept rate is listed.

Two item shapes: "content" (the whole entry in `content`, as before the quote field existed;
checked with the content fallback) and "quote" (`quote` + `content`; only `quote` is checked).
"""
import argparse
import itertools
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
ITEMS = os.path.join(ROOT, "tests", "fixtures", "grounding_eval", "items.jsonl")

from runner import validator  # noqa: E402

_LEGACY_SPLIT = re.compile(r"[\s,，。.!！?？、：:；;()（）\[\]【】「」『』“”‘’《》〈〉—–\-+*]+")


def legacy_any_fragment(content: str, material: str) -> bool:
    """The rule before the coverage rule: any one fragment longer than 1 char found in the material."""
    return any(len(t) > 1 and t in material for t in _LEGACY_SPLIT.split(content))


def legacy_rule(item: dict) -> bool:
    """The old validator only ever looked at `content`, whatever other fields an entry had."""
    return legacy_any_fragment(item["content"], item["_material"])


def current_validator(item: dict, config=None) -> bool:
    """Items in the pre-quote-field shape ("content") are checked the way old stored outputs are
    (content fallback). Quote-shaped items go through the engine's path: `quote` only, and a
    missing quote is ungrounded."""
    entry = {"inference_level": "direct", "content": item["content"]}
    if "quote" in item:
        entry["quote"] = item["quote"]
    result = validator.validate_evidence_grounding(
        {"evidence": [entry]}, [item["_material"]], config=config,
        allow_content_fallback=item.get("shape", "content") == "content",
    )
    return not result["ungrounded_evidence"]


def load_items():
    with open(ITEMS, encoding="utf-8") as f:
        items = [json.loads(line) for line in f]
    cache = {}
    for it in items:
        path = it["material"]
        if path not in cache:
            with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                cache[path] = f.read()
        it["_material"] = cache[path]
    return items


def _rate(num, den):
    return None if den == 0 else round(num / den, 4)


def score(rows):
    """rows: iterable of (label, accepted)."""
    tp = fn = fp = tn = mixed = mixed_acc = 0
    for label, accepted in rows:
        if label == "grounded":
            tp += accepted
            fn += not accepted
        elif label == "not_grounded":
            fp += accepted
            tn += not accepted
        else:
            mixed += 1
            mixed_acc += accepted
    return {
        "n": tp + fn + fp + tn, "grounded": tp + fn, "not_grounded": fp + tn,
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "precision": _rate(tp, tp + fp), "recall": _rate(tp, tp + fn),
        "false_accept_rate": _rate(fp, fp + tn), "false_reject_rate": _rate(fn, tp + fn),
        "mixed": mixed, "mixed_accepted": mixed_acc, "mixed_accept_rate": _rate(mixed_acc, mixed),
    }


def groups_for(it):
    src, lang = it["source"], it["lang"]
    if it.get("shape") == "quote":
        if it["label"] == "grounded_by_rule":
            return ["quote shape · real quote, fabricated comment (known limit, not scored)"]
        return ["quote shape · all scored items", f"quote shape · {lang}",
                f"quote shape · {it['category']} {it['category_name']} · {lang}",
                f"quote shape · {it['category']} {it['category_name']} · zh+en"]
    out = ["all scored items", f"{src} · all", f"{src} · {lang}"]
    if it["label"] == "mixed":
        return [f"{src} · quote + commentary (mixed, not scored)"]
    if src == "constructed":
        out.append(f"constructed · {it['category']} {it['category_name']} · {lang}")
        out.append(f"constructed · {it['category']} {it['category_name']} · zh+en")
    else:
        out.append(f"real · {it['real_kind']}")
    return out


def evaluate(items, fn, splits=("dev", "test")):
    report = {}
    for split in splits:
        buckets = {}
        for it in items:
            if it["split"] != split:
                continue
            accepted = bool(fn(it))
            for g in groups_for(it):
                buckets.setdefault(g, []).append((it["label"], accepted))
        report[split] = {g: score(rows) for g, rows in sorted(buckets.items())}
    return report


def _pct(v):
    return "–" if v is None else f"{v * 100:.0f}%"


def to_markdown(report, title):
    lines = [f"### {title}", ""]
    for split, groups in report.items():
        lines += [f"**{split} split**", "",
                  "| Group | Grounded | Not grounded | Precision | Recall | False-accept | False-reject |",
                  "|---|---|---|---|---|---|---|"]
        for g, s in groups.items():
            if s["n"] == 0:
                lines.append(f"| {g} | – | – | – | – | accepted {s['mixed_accepted']}/{s['mixed']} | – |")
                continue
            fa = f"{_pct(s['false_accept_rate'])} ({s['fp']}/{s['not_grounded']})" if s["not_grounded"] else "–"
            fr = f"{_pct(s['false_reject_rate'])} ({s['fn']}/{s['grounded']})" if s["grounded"] else "–"
            lines.append(f"| {g} | {s['grounded']} | {s['not_grounded']} | {_pct(s['precision'])} | "
                         f"{_pct(s['recall'])} | {fa} | {fr} |")
        lines.append("")
    return "\n".join(lines)


def sweep(items):
    """Grid over the coverage rule's parameters on the DEV split only."""
    base = validator.load_grounding_config()
    rows = []
    grid = itertools.product((3, 4, 5, 6), (2, 3, 4), (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95), (True, False))
    for cjk, latin, thr, nums in grid:
        cfg = dict(base, min_span_cjk_chars=cjk, min_span_latin_words=latin,
                   coverage_threshold=thr, require_numbers_covered=nums)
        rep = evaluate(items, lambda it: current_validator(it, cfg), splits=("dev",))["dev"]
        a, c, r = rep["all scored items"], rep["constructed · all"], rep.get("real · all", {})
        mixed = rep.get("real · quote + commentary (mixed, not scored)", {})
        rows.append({"min_span_cjk_chars": cjk, "min_span_latin_words": latin, "coverage_threshold": thr,
                     "require_numbers_covered": nums,
                     "errors": a["fp"] + a["fn"], "fp": a["fp"], "fn": a["fn"],
                     "constructed_fp": c["fp"], "constructed_fn": c["fn"],
                     "real_fp": r.get("fp"), "real_fn": r.get("fn"),
                     "mixed_accepted": mixed.get("mixed_accepted"), "mixed": mixed.get("mixed")})
    rows.sort(key=lambda x: (x["errors"], x["fp"], -x["coverage_threshold"]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rule", choices=("validator", "legacy"), default="validator")
    ap.add_argument("--split", choices=("dev", "test", "both"), default="both")
    ap.add_argument("--sweep", action="store_true", help="parameter grid on the dev split (never on test)")
    ap.add_argument("--out-md")
    ap.add_argument("--out-json")
    args = ap.parse_args()
    items = load_items()

    if args.sweep:
        rows = sweep(items)
        for r in rows[:25]:
            print(json.dumps(r))
        if args.out_json:
            with open(args.out_json, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=1)
        return 0

    fn = legacy_rule if args.rule == "legacy" else current_validator
    splits = ("dev", "test") if args.split == "both" else (args.split,)
    report = evaluate(items, fn, splits)
    title = {"legacy": "Any-fragment rule (before)", "validator": "Current validator"}[args.rule]
    md = to_markdown(report, title)
    print(md)
    if args.out_md:
        with open(args.out_md, "w", encoding="utf-8") as f:
            f.write(md + "\n")
    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump({"rule": args.rule, "report": report}, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
