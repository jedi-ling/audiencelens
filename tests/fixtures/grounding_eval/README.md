# Grounding evaluation set

A small labelled set for measuring the evidence-grounding check
(`validate_evidence_grounding` in `src/runner/validator.py`): given one `direct` evidence entry
and the material it claims to come from, should the entry be accepted as grounded?

No model was called to build it. Rebuild with `python tests/fixtures/grounding_eval/build_set.py`
(`--check` verifies `items.jsonl` is up to date).

## Files

| File | What it is |
|---|---|
| `items.jsonl` | The set: one JSON object per line (generated; do not edit by hand) |
| `build_set.py` | Builder: the hand-written constructed items, the construction asserts, the split |
| `real_items.jsonl` | Real model-written entries with a hand-assigned `real_kind` (input to the builder) |
| `materials/en_*.md` | Three short English materials written for this set (fictional products) |
| `materials/zh_pitch_litebooks.extracted.txt` | Text of `test-materials/02_创业BP_云会计SaaS.pdf` as the app's PDF extractor returns it, so the set can be scored without a PDF library |

The Chinese materials are the existing fictional ones in `test-materials/` (03, 04, 05, and the
02 pitch deck for real items).

## Item fields

`id`, `split` (`dev` / `test`), `lang` (`zh` / `en`), `source` (`constructed` / `real`),
`shape` (`content` / `quote`, see below), `category` (1–8, `q1`–`q8`, or `null` for real mixed
items), `category_name`, `label` (`grounded` / `not_grounded` / `mixed` / `grounded_by_rule`),
`material` (repo-relative path), `content`, and for quote-shaped items `quote`.

Two shapes, because the evidence schema changed while this set was in use:

- `shape: "content"` — the whole entry is in `content`, as the model wrote it before the
  `quote` field existed. Scored the way old stored outputs are re-checked: the rule falls back
  to `content`.
- `shape: "quote"` — `quote` (text copied from the material) and `content` (the persona's
  comment) are separate. Scored the way the engine checks new outputs: only `quote` is
  compared with the material, and a `direct` entry without one is not grounded. Constructed items may also carry `built_from`, `difference`, `framing`,
`fabricated_part`. Real items carry `real_kind`, `origin` and
`accepted_by_rule_at_generation` (what the any-fragment rule said when the run was made).

## Constructed items, content shape (160: 8 categories × 2 languages × 10)

Labels follow from how each item is built, and the builder asserts the construction.

| # | Category | Label | How it is built |
|---|---|---|---|
| 1 | `verbatim` | grounded | A span copied from the material (asserted to be a substring) |
| 2 | `verbatim_punctuation_variant` | grounded | A verbatim span with only punctuation, quote-mark, full-/half-width, case or whitespace changes (asserted: original is a substring, variant is not) |
| 3 | `framing_plus_verbatim` | grounded | A verbatim span inside a short neutral framing such as 页面写着「…」 or `The page says "…"`. Each of the 20 framings is used exactly once, so no framing appears in both dev and test |
| 4 | `half_true` | not grounded | A verbatim span followed by a made-up addition |
| 5 | `paraphrase_judgement` | not grounded | A reworded summary carrying the reviewer's opinion |
| 6 | `absence_claim` | not grounded | "The page never mentions X". A statement about what is missing cannot be a quote; it belongs under `gap` |
| 7 | `fabricated` | not grounded | A made-up claim |
| 8 | `number_changed` | not grounded | A verbatim span with exactly one figure altered (asserted: original is a substring, altered is not) |

"Not grounded" always means "should not be accepted as a `direct` (quoted) entry". It does not
mean the statement is false: several paraphrases and absence claims are true.

## Quote-shaped constructed items (160: 8 categories × 2 languages × 10)

Built from the same hand-written pieces, paired with a comment (or a made-up claim) written for
the same material.

| # | Category | Label | `quote` | `content` |
|---|---|---|---|---|
| q1 | `quote_verbatim_plus_comment` | grounded | verbatim span | a paraphrase with judgement |
| q2 | `quote_variant_plus_comment` | grounded | verbatim with punctuation / width / case / whitespace changes | a paraphrase with judgement |
| q3 | `quote_fabricated` | not grounded | a made-up claim | plausible comment |
| q4 | `quote_half_true` | not grounded | verbatim span + made-up addition | plausible comment |
| q5 | `quote_number_changed` | not grounded | verbatim span with one figure altered | plausible comment |
| q6 | `quote_is_paraphrase` | not grounded | a paraphrase with judgement | neutral sentence |
| q7 | `quote_missing` | not grounded | (absent) | a verbatim span |
| q8 | `quote_ok_comment_fabricated` | **grounded_by_rule** | verbatim span | a made-up claim |

**q8 is a known limit, not a success case.** The quote is real, the comment asserts something
the material does not say, and the rule accepts the entry because comments are not
fact-checked. These 20 items are excluded from the error rates and their accept rate is listed
separately, so the limit stays visible in every run.

## Real items (117, all Chinese)

Entries the model actually wrote on 2026-11-04 (claude-sonnet-5-5) for the three sample reviews:

- **84** — every `direct` entry in the three sample reports of that date
  (`docs/evaluation/runs/2026-11-04-pre-quote-field/*/persona_outputs.json`; they were the
  published samples until 2026-11-12).
- **33** — entries the validator flagged as ungrounded in the same runs and in the diagnostic
  re-run described in `docs/evaluation/runs/2026-11-04-sonnet55-before-fix/notes.md`. That
  folder records only the percentages, not the quote text, so these come from the local debug
  captures of those runs (`AUDIENCELENS_DEBUG_RUNS=1`), which are not otherwise in the repo.
  Only the entry text is copied.

Each was read against its material and given a `real_kind`:

| `real_kind` | Label | Rule used when reading |
|---|---|---|
| `verbatim` | grounded | The whole entry is material text |
| `framing_plus_verbatim` | grounded | A short neutral lead-in, then material text |
| `restatement_or_judgement` | not grounded | Facts reworded or compressed, usually with the persona's opinion; or opinion only |
| `absence_claim` | not grounded | Mainly a statement of what the material does not say |
| `quote_plus_commentary` | **mixed** | Reproduces a complete clause or list item of the material exactly, or explicitly quotes at least ~6 characters of it, and adds substantial commentary or absence claims |

**Mixed items are excluded from precision / recall / false-accept / false-reject.** Whether a
long comment built around an exact quote should count as `direct` is a policy choice, not a fact
about the entry, so the evaluation reports the accept rate on them separately.

## Split

60% dev / 40% test inside every (source, category, language) group, ordered by the SHA-256 of
the content. Thresholds and span lengths may only be chosen on dev. Test is reported once.

## Limits

- Labels are **by construction and by one author's reading**, not large-scale human annotation.
  There is no second annotator and no agreement figure.
- The constructed items were written by the same author who then changed the rule. They are
  cleaner and shorter than what the model writes; real `direct` entries are mostly long
  restatements with commentary (see the real-item counts). Read the constructed and real numbers
  separately.
- The boundary between `quote_plus_commentary` and `restatement_or_judgement` is a judgement
  call on some real items. Borderline cases were put in `mixed`, which keeps them out of the
  scored metrics.
- Real items are Chinese only, from one model and three materials. English coverage is
  constructed only.
- 437 items, with 4–6 per constructed cell in each split: per-category rates move in steps of
  17–25 points per item. They show direction, not precise rates.
- There are no real quote-shaped items yet: no model output with a `quote` field existed when
  the quote-shaped items were added. The quote-shaped numbers are constructed only.
- The set measures quote matching. It says nothing about whether a grounded entry is true,
  relevant or fairly interpreted.
