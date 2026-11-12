"""Re-check stored persona outputs against the current grounding rule. Offline, no model calls.

    python scripts/revalidate_samples.py            # markdown summary of both sets
    python scripts/revalidate_samples.py --json     # machine-readable

Two sets, and it never regenerates or edits a report:

  current   examples/reports/<slug>/persona_outputs.json — the published samples. Their evidence
            has a `quote` field; they are checked the way the engine checks new output
            (quote only, a direct entry without a quote is ungrounded).
  archived  docs/evaluation/runs/2026-11-04-pre-quote-field/<slug>/ — the samples generated
            under the any-fragment rule, before the `quote` field existed. "Before" is that
            rule (frozen copy in scripts/eval_grounding.py); "after" is the coverage rule
            applied to `content`, because these entries have no quote.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src"), os.path.join(ROOT, "scripts")]

from eval_grounding import legacy_any_fragment  # noqa: E402
from runner.validator import MAX_UNGROUNDED_DIRECT_SHARE, check_direct_entry  # noqa: E402

ARCHIVED_DIR = os.path.join("docs", "evaluation", "runs", "2026-11-04-pre-quote-field")
CURRENT_DIR = os.path.join("examples", "reports")

MATERIALS = {
    "steam-page-abyss-echo": "test-materials/03_steam商店页_深渊回响.md",
    "saas-pricing-cloud-notes": "test-materials/04_定价页_云笔记订阅.md",
    # text of test-materials/02_创业BP_云会计SaaS.pdf as the app's PDF extractor returns it
    "startup-pitch-cloud-accounting": "tests/fixtures/grounding_eval/materials/zh_pitch_litebooks.extracted.txt",
}


def revalidate():
    out = {}
    for slug, mat in MATERIALS.items():
        with open(os.path.join(ROOT, mat), encoding="utf-8") as f:
            material = f.read()
        with open(os.path.join(ROOT, ARCHIVED_DIR, slug, "persona_outputs.json"), encoding="utf-8") as f:
            data = json.load(f)
        personas, flipped = [], []
        for persona in data["validated"]:
            entries = [e for e in persona.get("evidence", [])
                       if isinstance(e, dict) and e.get("inference_level") == "direct"]
            direct = [e.get("content", "") for e in entries]
            before = [legacy_any_fragment(c, material) for c in direct]
            # These outputs predate the `quote` field, so the rule falls back to `content`.
            after = [check_direct_entry(e, [material], allow_content_fallback=True) for e in entries]
            n = len(direct)
            share_before = (before.count(False) / n) if n else 0.0
            share_after = (sum(1 for a in after if not a["grounded"]) / n) if n else 0.0
            personas.append({
                "persona_id": persona.get("persona_id"), "direct_entries": n,
                "ungrounded_before": before.count(False),
                "ungrounded_after": sum(1 for a in after if not a["grounded"]),
                "passes_before": share_before < MAX_UNGROUNDED_DIRECT_SHARE,
                "passes_after": share_after < MAX_UNGROUNDED_DIRECT_SHARE,
            })
            for c, b, a in zip(direct, before, after):
                if b != a["grounded"]:
                    flipped.append({"persona_id": persona.get("persona_id"), "content": c,
                                    "before": "grounded" if b else "ungrounded",
                                    "after": "grounded" if a["grounded"] else "ungrounded",
                                    "coverage": a["coverage"]})
        out[slug] = {
            "personas_in_report": len(personas),
            "pass_before": sum(p["passes_before"] for p in personas),
            "pass_after": sum(p["passes_after"] for p in personas),
            "direct_entries": sum(p["direct_entries"] for p in personas),
            "grounded_before": sum(p["direct_entries"] - p["ungrounded_before"] for p in personas),
            "grounded_after": sum(p["direct_entries"] - p["ungrounded_after"] for p in personas),
            "personas": personas, "flipped": flipped,
        }
    return out


def current_samples():
    """The published samples under the engine's own check: quote only, no content fallback."""
    out = {}
    for slug, mat in MATERIALS.items():
        with open(os.path.join(ROOT, mat), encoding="utf-8") as f:
            material = f.read()
        with open(os.path.join(ROOT, CURRENT_DIR, slug, "persona_outputs.json"), encoding="utf-8") as f:
            data = json.load(f)
        counts = {"direct": 0, "inferred": 0, "gap": 0}
        grounded = with_quote = 0
        max_inferred_share = 0.0
        for persona in data["validated"]:
            entries = [e for e in persona.get("evidence", []) if isinstance(e, dict)]
            inferred = 0
            for e in entries:
                level = e.get("inference_level")
                counts[level] = counts.get(level, 0) + 1
                inferred += level == "inferred"
                if level == "direct":
                    with_quote += bool(isinstance(e.get("quote"), str) and e["quote"].strip())
                    grounded += check_direct_entry(e, [material])["grounded"]
            if entries:
                max_inferred_share = max(max_inferred_share, inferred / len(entries))
        total = sum(counts.values())
        out[slug] = {
            "personas_passed": len(data["validated"]),
            "personas_attempted": len(data["validated"]) + len(data["failed"]),
            "failed": [f"{x['persona_id']}: {x['failure_reason']}" for x in data["failed"]],
            "direct_entries": counts["direct"], "inferred_entries": counts["inferred"], "gap_entries": counts["gap"],
            "direct_share": round(counts["direct"] / total, 4) if total else 0.0,
            "inferred_share": round(counts["inferred"] / total, 4) if total else 0.0,
            "gap_share": round(counts["gap"] / total, 4) if total else 0.0,
            "max_inferred_share_of_one_persona": round(max_inferred_share, 4),
            "direct_entries_with_quote": with_quote,
            "direct_entries_grounded": grounded,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = revalidate()
    current = current_samples()
    if args.json:
        print(json.dumps({"current": current, "archived": result}, ensure_ascii=False, indent=1))
        return 0
    print("Published samples (examples/reports), quote-only check\n")
    print("| Sample | Personas passed | direct / inferred / gap | `direct` entries grounded |")
    print("|---|---|---|---|")
    for slug, r in current.items():
        print(f"| {slug} | {r['personas_passed']} of {r['personas_attempted']} | "
              f"{r['direct_entries']} / {r['inferred_entries']} / {r['gap_entries']} | "
              f"{r['direct_entries_grounded']}/{r['direct_entries']} |")
    print("\nArchived 2026-11-04 samples (pre-quote-field), any-fragment rule vs coverage on content\n")
    print("| Sample | Personas in report | Pass grounding (old rule) | Pass grounding (coverage rule) | "
          "`direct` entries grounded, old → new |")
    print("|---|---|---|---|---|")
    for slug, r in result.items():
        print(f"| {slug} | {r['personas_in_report']} | {r['pass_before']} | {r['pass_after']} | "
              f"{r['grounded_before']}/{r['direct_entries']} → {r['grounded_after']}/{r['direct_entries']} |")
    for slug, r in result.items():
        print(f"\n{slug}: {len(r['flipped'])} entries flipped")
        for p in r["personas"]:
            print(f"  {p['persona_id']}: ungrounded {p['ungrounded_before']} → {p['ungrounded_after']} "
                  f"of {p['direct_entries']} direct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
