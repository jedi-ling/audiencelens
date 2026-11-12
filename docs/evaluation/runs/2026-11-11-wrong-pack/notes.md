# 2026-11-11 — two runs made with the wrong persona pack

**These are evaluation evidence, not sample reports.** They are not linked from `/samples`.

| | Pricing page | Pitch deck |
|---|---|---|
| Input | `test-materials/04_定价页_云笔记订阅.md` | `test-materials/02_创业BP_云会计SaaS.pdf` |
| Task type | `pricing_page_review` | `pitch_review` |
| Pack that should have been used | `general-consumer` | `startup-panel` |
| **Pack actually used** | **`game-core`** | **`game-core`** |
| Run id | `20261111-181503-pricing_page_review` | `20261111-181555-pitch_review` |
| Model / depth | `claude-sonnet-5-5` / standard | `claude-sonnet-5-5` / standard |
| App commit | `2a51751` | `2a51751` |
| Personas passed | 5 of 5 | 6 of 6 |
| Repair turns | 5, all for schema failures | 5, all for schema failures |
| Cost | $0.2667 | $0.3797 |

Files per run: `report.json`, `report.md`, `meta.json`, `persona_outputs.json` (unedited engine
output; `meta.json` was corrected afterwards to name the pack that was really used).

## What happened

The script that generated the runs did not pass a persona pack to the engine. `run_panel` then
fell back to `game-core` without saying so, and a pricing page and a pitch deck were reviewed by
game-player personas (P01, P16, …). The reports were generated normally and nothing flagged it;
it was noticed only because the per-persona table showed game personas.

The same mistake had happened once before, on 2026-11-04. The cause was fixed in commit
`939e8ca`: the default pack is now resolved from the task type
(`src/runner/task_types.py::DEFAULT_PACK_BY_TASK_TYPE`), an unregistered task type raises, and an
explicit pack that differs from the registered one logs a warning.

## Why these are not samples

The personas do not fit the material. A sample is supposed to show what the product does for
that kind of input, and here it shows game players commenting on SaaS pricing and on a funding
pitch. The findings themselves should not be read as a review of either document.

## What they still show

They are real engine runs with the evidence schema that has a separate `quote` field, so they
are valid evidence about one narrow question: does the model fill `quote` with exact text?

| | Pricing page | Pitch deck |
|---|---|---|
| `direct` / `inferred` / `gap` entries (passing personas) | 33 / 5 / 6 | 41 / 10 / 4 |
| Shares | 75% / 11% / 14% | 75% / 18% / 7% |
| Highest inferred share of any one persona | 17% | 27% |
| `direct` entries whose quote the coverage rule accepts | 33 of 33 | 41 of 41 |
| Attempts that failed on grounding | 0 | 0 |
| Attempts that failed on schema (malformed tool input) | 5 | 5 |

All ten schema failures were recovered by the single repair turn. These runs were made after
the change that treats a list field containing tool-call markup as a schema failure
(commit `2a51751`).

This is two runs on one model. It is not a rate, and it says nothing about whether the
comments written beside the quotes are accurate; those are not checked.
See [../../grounding-check.md](../../grounding-check.md).
