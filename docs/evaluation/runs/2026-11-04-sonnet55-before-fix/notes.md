# 2026-11-04 — Claude Sonnet 5.5, before the repair-turn fix

**This is evaluation evidence, not a sample report.** It is the first real run of the
engine on `claude-sonnet-5-5`, kept because it shows how the validator behaves when a model
changes underneath it. It is not linked from `/samples`.

| | |
|---|---|
| Input | `test-materials/03_steam商店页_深渊回响.md` (fictional Steam store page) |
| Task / pack / depth | `steam_page_review` / `game-core` / `standard` |
| Model | `claude-sonnet-5-5` |
| App commit | `f2a1268` (forced `tool_choice` already disabled for 5.5 models) |
| Cost / tokens | $0.2716 · 82,360 in / 15,092 out (see `meta.json`) |
| Result | **2 of 6 personas passed validation**; the report was marked degraded; cross-examination did not run (no qualifying dispute among the two survivors) |

Files: `report.json` (the engine's report, unedited) and `meta.json`. The Markdown/HTML
renderings were not kept.

## Failures

| Persona | Validator verdict |
|---|---|
| P06-visual-atmosphere-lover | hallucination — 33% of `direct` evidence not found in the material (threshold 30%) |
| P10-steam-wishlist-browser | hallucination — 40% |
| P16-competitor-loyal-veteran | schema_failure — `scores`, `key_issues` missing |
| P01-indie-core-operator | schema_failure — same |

## Cause (from a diagnostic re-run with `AUDIENCELENS_DEBUG_RUNS=1`)

The diagnostic re-run (same input, $0.2646) reproduced the pattern (3 of 6 passed) and
captured the raw responses:

- **schema_failure** — every persona *did* call `submit_review`; nothing went to plain text.
  The failing persona's tool input was malformed: `evidence` was a **string** beginning with
  `<parameter name="content">…` (tool-call markup leaked into a JSON value), the first evidence
  item's fields appeared at the top level, and everything after it — `scores`, `key_issues`,
  the triggers — was missing. Sonnet 5.5 does not accept forced `tool_choice`, so the request
  runs with `tool_choice: auto` and the API does not reject the malformed input. Re-sending the
  identical prompt reproduced the same broken input on all four attempts; on three of them the
  model also emitted two `tool_use` blocks.
- **hallucination** — the flagged `direct` quotes are paraphrases and summaries mixed with the
  persona's own judgement (4-character overlap with the source: 0–21%), plus a few
  "the page never mentions X" statements that belong under `gap` / `inferred`. None were
  translations, and NFKC (full-/half-width) normalisation does not change any verdict, so these
  are **not** normalisation false positives. The 30% threshold was left unchanged.

## Fix

- One **repair turn** per persona instead of identical re-sends: the previous response is replayed
  unchanged, every `tool_use` gets an `is_error` `tool_result` carrying the validator's errors
  (missing fields, or the exact quotes that were not found verbatim, with "quote exact text or
  mark it `inferred` / `gap`"), and the model is asked to call `submit_review` once more
  (`src/runner/llm_client.py::_repair_messages`, `src/runner/cli.py::_repair_feedback`).
- `src/config/budget.yaml`: `max_retries_per_persona: 1`,
  `retry_on: [transport_error, schema_failure, hallucination]`. The retry is billed.
- Tests: `tests/test_persona_repair.py`.
