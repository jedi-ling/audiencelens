# Finding: the string-similarity fallback silently disables cross-examination on Chinese input

Date: 2026-11-04 · Model: `claude-sonnet-5-5` · Inputs: the three fictional samples in `examples/reports/`

## What happened

None of the three sample reviews (Steam page, SaaS pricing page, startup pitch) ran
cross-examination. Cross-examination only debates an issue that **at least two personas raised**
with **different severities**, and "the same issue" is decided by `src/runner/similarity.py`:

- with `sentence-transformers` installed: Chinese embedding model `BAAI/bge-small-zh-v1.5`,
  cosine > 0.65 (the semantic backend);
- without it: `difflib.SequenceMatcher` ratio > 0.7 (the string fallback).

The sample runs had only the string fallback. It merged **0 of 61** issues across the three runs.
Personas describe the same problem with different words (e.g. "没有胶囊图、截图和预告片" ("no capsule art, screenshots or trailer") /
"没有首屏视觉证据：无 GIF、预告片、截图" ("no first-screen visual evidence: no GIF, trailer or screenshots") / "零实机、零预告" ("zero gameplay footage, zero trailer")), so every issue stayed a single-persona
view with zero severity variance, and the reports only said "no significant disagreement".

## Offline comparison (same validated persona outputs, no API calls, thresholds unchanged)

| Sample | Personas / issues | String fallback (current default before the fix) | Semantic (bge-small-zh, > 0.65) | Character 2–3-gram Jaccard > 0.20 | > 0.25 / 0.30 / 0.35 |
|---|---|---|---|---|---|
| steam-page-abyss-echo | 4 / 19 | 0 groups · **0 disputes** | 4 groups · **2 disputes** | 0 · 0 | 0 · 0 |
| saas-pricing-cloud-notes | 5 / 25 | 0 groups · **0 disputes** | 6 groups · **6 disputes** (top-3 kept) | 1 · 1 | 0 · 0 |
| startup-pitch-cloud-accounting | 3 / 17 | 0 groups · **0 disputes** | 1 group · **1 dispute** | 0 · 0 | 0 · 0 |

"Groups" are issues raised by two or more personas after merging; "disputes" are the groups with
severity variance > 0, which is what `filter_genuine_controversies` keeps. Every semantic merge
was read by hand: all are genuine same-issue merges, one is borderline (a team-credibility group in
the Steam sample also absorbed a "process and pricing promises lack backing" issue).

The character n-gram fallback is **not sufficient**: it merged one correct pair at the loosest
threshold and nothing above it. Character overlap is low even when the meaning is the same.

## What changed

- `web/backend/Dockerfile`: semantic dedup is on by default (CPU-only torch, model pre-downloaded
  at build time, no runtime Hub access). Size impact: `docs/MAINTENANCE.md` → 语义去重 (the "semantic dedup" section).
- When the string fallback is in use, reports now say so explicitly in JSON (`report.dedup`),
  Markdown and HTML: "Semantic dedup not installed — cross-examination may not trigger."
- The three samples were resumed from their validated persona outputs with the semantic backend
  (`runner.cli.run_panel_from_outputs`, cross-exam only, standard mode). Cross-examination ran in
  all three: 2 / 3 / 1 disputes, every rebuttal parsed (no failures, no truncation), total
  $0.0720 for the three rebuttal calls. No vote changed: the largest confidence movement was 2
  points against a threshold of 15 (θ = 0.15). What that does and does not tell us:
  [cross-exam-observation.md](cross-exam-observation.md).
- Still open (docs/MAINTENANCE.md §10): a deterministic issue-category fallback for deployments
  without the semantic model, and making the model name configurable.
