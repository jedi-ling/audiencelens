"""Copy the generated sample reports into the frontend's static files.

examples/reports/<slug>/ is the source of truth (report.html / report.json /
report.md / meta.json, produced by a real engine run — never edited by hand).
The /samples page needs the HTML report and a little metadata as static files,
and the frontend Docker build only sees web/frontend/, so the copies live in
web/frontend/public/sample-reports/ and are committed. This script keeps them
identical; tests/test_sample_reports.py runs it with --check.

Usage:
    python scripts/sync_sample_reports.py           # write the copies + index.json
    python scripts/sync_sample_reports.py --check   # exit 1 if they are out of date
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "examples", "reports")
DST = os.path.join(ROOT, "web", "frontend", "public", "sample-reports")
COPIED = ("report.html", "meta.json")  # persona_outputs.json stays in examples/ only


def expected_files() -> dict:
    """published path (relative to DST) -> bytes"""
    out = {}
    index = []
    for slug in sorted(os.listdir(SRC)):
        folder = os.path.join(SRC, slug)
        if not os.path.isfile(os.path.join(folder, "meta.json")):
            continue
        for name in COPIED:
            with open(os.path.join(folder, name), "rb") as f:
                out[f"{slug}/{name}"] = f.read()
        with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(folder, "report.json"), encoding="utf-8") as f:
            report = json.load(f)
        degradation = report.get("degradation") or {}
        index.append({
            "slug": slug,
            "title": (report.get("meta") or {}).get("target") or slug,
            "task_type": meta["task_type"],
            "persona_pack": meta["persona_pack"],
            "model_id": meta["model_id"],
            "date": meta["date"],
            "cost_usd": meta["cost_usd"],
            "personas_passed": degradation.get("succeeded_count"),
            "personas_attempted": degradation.get("attempted_count"),
            "cross_exam_ran": bool((report.get("cross_examination") or {}).get("is_live_debate")),
            "disputes": len((report.get("cross_examination") or {}).get("disputes") or []),
            "dedup_method": meta.get("dedup_method"),
        })
    out["index.json"] = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    want = expected_files()
    stale = []
    for rel, data in want.items():
        path = os.path.join(DST, rel)
        try:
            with open(path, "rb") as f:
                same = f.read() == data
        except FileNotFoundError:
            same = False
        if not same:
            stale.append(rel)
            if not args.check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
    if args.check and stale:
        print("out of date: " + ", ".join(stale) + " — run scripts/sync_sample_reports.py")
        return 1
    print(f"{len(want)} files {'checked' if args.check else 'in sync'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
