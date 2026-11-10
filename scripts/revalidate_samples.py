"""Re-validate the stored sample persona outputs against the current grounding rule. Offline.

    python scripts/revalidate_samples.py            # markdown summary
    python scripts/revalidate_samples.py --json     # machine-readable

Reads examples/reports/<slug>/persona_outputs.json (the validated persona outputs each sample
was built from). It does not regenerate or modify any report. "Before" is the any-fragment rule
the samples were generated under (frozen copy in scripts/eval_grounding.py).
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "src"), os.path.join(ROOT, "scripts")]

from eval_grounding import legacy_any_fragment  # noqa: E402
from runner.validator import MAX_UNGROUNDED_DIRECT_SHARE, check_entry_grounding  # noqa: E402

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
        with open(os.path.join(ROOT, "examples", "reports", slug, "persona_outputs.json"), encoding="utf-8") as f:
            data = json.load(f)
        personas, flipped = [], []
        for persona in data["validated"]:
            direct = [e.get("content", "") for e in persona.get("evidence", [])
                      if isinstance(e, dict) and e.get("inference_level") == "direct"]
            before = [legacy_any_fragment(c, material) for c in direct]
            after = [check_entry_grounding(c, [material]) for c in direct]
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = revalidate()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
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
