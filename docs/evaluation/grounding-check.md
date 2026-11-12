# Evidence grounding check: from "any fragment" to coverage

2026-11-11, updated 2026-11-12. The evaluation-set numbers on this page involve no model calls.
The [live runs](#live-runs-2026-11-11-and-2026-11-12) section reports five real engine runs.

## The problem

Personas tag each piece of evidence `direct`, `inferred` or `gap`. `direct` means "quoted from
the material", and `validate_evidence_grounding` (`src/runner/validator.py`) is the only check
that compares those entries with the source text.

**An external review of the repository found that this check was much weaker than the README
implied.** Until this change the rule was: split the entry on whitespace and punctuation, and
accept it if *any one* fragment longer than one character is a substring of the material.
Two consequences, both confirmed with probes before any code was changed:

| Probe | Entry | Old rule |
|---|---|---|
| True quote + fabricated addition | 售价68元，并且官方承诺永久免费更新全部DLC (the material only says 售价68元) | accepted |
| English entry sharing only common words | "The developers admit the game is unfinished and refunds are refused" (the material shares "the", "is", "and") | accepted |

For English text the split is on spaces, so a single word such as "the" grounded the whole
entry. For Chinese the fragments are longer (text between punctuation), which made the old rule
stricter there, but a short matching clause still carried any amount of invented text.

## The evaluation set

`tests/fixtures/grounding_eval/` (details and limits in its `README.md`). This part of the page
uses its 277 content-shape items: `direct`-style entries with everything in one field, each
paired with a fictional material and labelled "should be accepted as a quote" or not. The 160
quote-shaped items added later are covered in [their own section](#the-quote-field-fixing-the-data-shape-instead-of-loosening-the-rule).

| | Items | dev | test |
|---|---|---|---|
| Constructed, 8 categories × zh/en × 10 | 160 | 96 | 64 |
| Real model output (zh), scored | 82 | 50 | 32 |
| Real model output (zh), "quote + commentary", not scored | 35 | 21 | 14 |

- **Constructed** categories: verbatim; verbatim with punctuation / width / whitespace / case
  differences; framing + verbatim (grounded); half-true; paraphrase with judgement; absence
  claim; fabricated; one number changed (not grounded). Labels follow from construction, and
  the builder asserts the construction.
- **Real** entries are what `claude-sonnet-5-5` wrote on 2026-11-04 for the three sample
  reviews (now in `docs/evaluation/runs/2026-11-04-pre-quote-field/`): every `direct` entry in
  their `persona_outputs.json` (84) and the entries
  the validator flagged in those runs (33). Each was read against its material by one person.
- **Mixed** real entries reproduce an exact quote and then add substantial commentary. Whether
  that is a `direct` entry is a policy question, so they are left out of the error rates and
  their accept rate is shown separately.
- 60% dev / 40% test inside each (source, category, language) group, by content hash.

`scripts/eval_grounding.py` scores a rule on the set. *False accept* = a not-grounded item
accepted; *false reject* = a grounded item rejected.

## The new rule

Per `direct` entry (`check_entry_grounding`):

1. **Normalise** entry and material: NFKC (full-width → half-width), case-fold, all quote marks
   to one, all dashes to one, whitespace collapsed. Tokenise: each CJK character is a token,
   each Latin word or number (`8,000`, `19.99`) is a token; punctuation is dropped.
2. **Drop a short lead-in** such as 页面写着： or `The page says "`, only when it ends at the
   entry's first colon or quote mark, is short, and contains a cue word from a small list.
3. **Cover** the entry with contiguous token runs that also occur in the material. A run counts
   only if it is long enough: 4 CJK characters, or 3 Latin words, or a proportional mix.
4. **Grounded** iff coverage ≥ 0.8 **and** every number in the entry lies inside a covered run.

The result also lists the uncovered parts, and the repair turn now tells the model which part of
each entry was not found instead of returning the whole entry.

Unchanged: a persona still fails when 30% or more of its `direct` entries are not grounded.

`hallucination_risk` keeps its key name for compatibility. It means **the share of a persona's
`direct` entries that are not grounded in the material** (0–1). It is not a probability of
hallucination: an accurate paraphrase counts as not grounded.

### Choosing the parameters (dev split only)

Values live in `src/config/grounding.yaml`. Grid on dev
(`python scripts/eval_grounding.py --split dev --sweep`; full output in
`docs/evaluation/grounding/dev-sweep.json`): minimum CJK span 3–6, minimum Latin span 2–4,
threshold 0.5–0.95, number check on/off. Cells are false accepts / false rejects out of 104 / 42
scored dev items, as a range over the 12 span settings.

| Threshold | Number check on | Number check off |
|---|---|---|
| 0.50 | 9–12 / 0 | 15–24 / 0 |
| 0.60 | 5–7 / 0 | 9–18 / 0 |
| 0.70 | 1–2 / 0 | 4–11 / 0 |
| 0.75 | **0 / 0** | 3–8 / 0 |
| 0.80 | **0 / 0** | 3–8 / 0 |
| 0.85 | 0 / 0–1 | 3–7 / 0–1 |
| 0.90 | 0 / 0–1 | 2–5 / 0–1 |
| 0.95 | 0 / 1 | 1–3 / 1 |

- **Number check: on.** Without it no threshold reaches zero errors, because a long quote with
  one altered figure is still 90%+ covered.
- **Threshold: 0.8.** With the number check on, 0.75 and 0.8 are error-free on dev for every
  span setting. 0.8 is the stricter of the two, so it tolerates less added text.
- **Span minimums: 4 CJK characters / 3 Latin words.** Dev does not separate the span settings
  at this threshold (all are error-free), so these are the middle of the grid and a prior
  rather than a fitted value: long enough that a common word pair does not count.

## Results

Counts are false accepts (FA) and false rejects (FR) over the items that can produce them.
Full tables: `docs/evaluation/grounding/baseline-any-fragment.md` and
`coverage-rule-test-run.md`.

### Dev split (used for tuning)

| Group | Any-fragment rule | Coverage rule |
|---|---|---|
| All scored items | FA 66/104 (63%), FR 2/42 (5%) | FA 0/104, FR 0/42 |
| Constructed, all | FA 42/60, FR 1/36 | FA 0/60, FR 0/36 |
| Constructed, zh | FA 12/30, FR 1/18 | FA 0/30, FR 0/18 |
| Constructed, en | FA 30/30, FR 0/18 | FA 0/30, FR 0/18 |
| 1 verbatim | FR 0/12 | FR 0/12 |
| 2 punctuation variant | FR 1/12 | FR 0/12 |
| 3 framing + verbatim | FR 0/12 | FR 0/12 |
| 4 half-true | FA 12/12 | FA 0/12 |
| 5 paraphrase + judgement | FA 6/12 (en 6/6, zh 0/6) | FA 0/12 |
| 6 absence claim | FA 6/12 (en 6/6, zh 0/6) | FA 0/12 |
| 7 fabricated | FA 6/12 (en 6/6, zh 0/6) | FA 0/12 |
| 8 number changed | FA 12/12 | FA 0/12 |
| Real, scored | FA 24/44, FR 1/6 | FA 0/44, FR 0/6 |
| Real, quote + commentary (not scored) | accepted 17/21 | accepted 0/21 |

Precision / recall on all scored dev items: 38% / 95% → 100% / 100%.

### Test split (held out; the coverage rule was run on it once)

| Group | Any-fragment rule | Coverage rule |
|---|---|---|
| All scored items | FA 43/69 (62%), FR 1/27 (4%) | FA 1/69 (1%), FR 1/27 (4%) |
| Constructed, all | FA 30/40, FR 1/24 | FA 0/40, FR 1/24 |
| Constructed, zh | FA 10/20, FR 1/12 | FA 0/20, FR 0/12 |
| Constructed, en | FA 20/20, FR 0/12 | FA 0/20, FR 1/12 |
| 1 verbatim | FR 0/8 | FR 0/8 |
| 2 punctuation variant | FR 1/8 | FR 0/8 |
| 3 framing + verbatim | FR 0/8 | FR 1/8 |
| 4 half-true | FA 8/8 | FA 0/8 |
| 5 paraphrase + judgement | FA 4/8 | FA 0/8 |
| 6 absence claim | FA 5/8 | FA 0/8 |
| 7 fabricated | FA 5/8 | FA 0/8 |
| 8 number changed | FA 8/8 | FA 0/8 |
| Real, scored | FA 13/29, FR 0/3 | FA 1/29, FR 0/3 |
| Real, quote + commentary (not scored) | accepted 13/14 | accepted 0/14 |

Precision / recall on all scored test items: 38% / 96% → 96% / 96%.

The two test errors:

- **False reject** — `In the devlog's own words: "Crafting also accounted for …"`. The
  apostrophe in "devlog's" was normalised to a quote mark and taken as the start of the quote,
  so the lead-in was not recognised. This was a bug, and it was fixed after the test run
  (an apostrophe between two Latin letters is no longer a delimiter). With the fix the test
  split shows FA 1/69, FR 0/27 (`coverage-rule-after-apostrophe-fix.md`), but that figure is
  **not** a clean held-out number, because the fix was made after seeing the test result.
  The table above is the single pre-fix run.
- **False accept** — a real entry that stitches three clauses of the pitch deck together with
  small rewordings (84% covered). It was labelled a restatement; the rule sees a quote.
  No parameter was changed for it.

## Effect on the sample reports of 2026-11-04

The three sample reports published at the time were generated under the old rule. They were
not edited; `scripts/revalidate_samples.py` re-checks their stored persona outputs offline.
(They have since been replaced as samples and are kept in
`docs/evaluation/runs/2026-11-04-pre-quote-field/`.)

| Sample | Personas in the report | Pass grounding, old rule | Pass grounding, coverage rule | `direct` entries grounded, old → new |
|---|---|---|---|---|
| steam-page-abyss-echo | 4 | 4 | 1 | 21/22 → 8/22 |
| saas-pricing-cloud-notes | 5 | 5 | 0 | 38/41 → 0/41 |
| startup-pitch-cloud-accounting | 3 | 3 | 0 | 16/21 → 1/21 |

**Only 1 of the 12 personas in those samples would pass the new rule as written.**
The reason is visible in the real items: of the 84 `direct` entries in the samples, 8 are
quotes. The rest are accurate-looking restatements, quotes with commentary attached, and
statements about what the page does not say. The old rule let almost all of them through; the
new rule does not. Each sample's `meta.json` carries these numbers under
`grounding_revalidation`, and a test keeps them equal to the script's output.

What this does and does not show:

- It shows how the model used the `direct` tag under the old rule, with a repair prompt that
  only fired for a few entries.
- It does **not** show what a live run under a stricter rule produces. That was measured
  later, after the data shape was changed: see the next two sections.

## The `quote` field: fixing the data shape instead of loosening the rule

The sample re-check above says the rule and the data did not fit: the model wrote the quote and
its own comment into one field, `content`, and the coverage rule then measured the comment as
if it were part of the quote. The fix is in the schema, not in the threshold.

- An evidence entry now has an optional `quote` (text copied verbatim from the material) next to
  `content` (the persona's observation, free text). For `direct` entries `quote` is required:
  the prompt gives one rule, "direct = you can copy the exact words into `quote`; if you cannot
  quote it, use inferred; if the material does not say it, use gap".
- The validator applies the same coverage rule, with the same parameters, **to `quote` only**.
  A `direct` entry with a missing or empty `quote` is not grounded. `content` is not checked.
- The repair turn names the entry and says whether its quote was missing or which part of the
  quote was not found.
- Outputs stored before the field existed have no `quote`; they are re-checked on `content`
  (`allow_content_fallback`, off in the engine), so the sample numbers above are unchanged.
- Reports carry the quote separately (`persona_notes[].evidence_top3_detail`) and render it as a
  quotation above the comment. One caveat for the HTML report: the template's stylesheet had
  three unclosed rules, dating from the first commits, that left the whole persona section
  unstyled in a browser. That was fixed on 2026-11-12, after the current samples were generated.
  Their stored `report.html` files then had only the `<style>` block replaced with the fixed
  stylesheet; everything outside it is byte-identical to the generated file (hashes in each
  `meta.json`, checked by a test). The Markdown reports show the quotations as block quotes.
- The report-level calibration metric named `hallucination` now calls the same function, so the
  gate and the metric cannot disagree about an entry.

`quote` is not required by the JSON Schema itself. A `direct` entry without it is caught by the
grounding check, which reports it by name; a schema error would have surfaced as an unrelated
`schema_failure` and made every stored output schema-invalid.

### Quote-shaped items (constructed, 160)

Parameters were not changed. Counts are false accepts (FA) and false rejects (FR).

| Group | dev: any-fragment | dev: coverage on `quote` | test: any-fragment | test: coverage on `quote` |
|---|---|---|---|---|
| All scored quote-shaped items | FA 36/60, FR 12/24 | FA 0/60, FR 0/24 | FA 24/40, FR 8/16 | FA 0/40, FR 0/16 |
| q1 verbatim quote + comment | FR 6/12 | FR 0/12 | FR 4/8 | FR 0/8 |
| q2 punctuation-variant quote + comment | FR 6/12 | FR 0/12 | FR 4/8 | FR 0/8 |
| q3 fabricated quote | FA 6/12 | FA 0/12 | FA 4/8 | FA 0/8 |
| q4 half-true quote | FA 6/12 | FA 0/12 | FA 4/8 | FA 0/8 |
| q5 quote with a changed number | FA 6/12 | FA 0/12 | FA 4/8 | FA 0/8 |
| q6 quote is a paraphrase | FA 6/12 | FA 0/12 | FA 4/8 | FA 0/8 |
| q7 quote missing | FA 12/12 | FA 0/12 | FA 8/8 | FA 0/8 |
| q8 real quote, fabricated comment (known limit, not scored) | accepted 7/12 | accepted 12/12 | accepted 4/8 | accepted 8/8 |

The any-fragment column is what the old validator would do with these entries: it never looked
at `quote`, only at `content`, so its verdict depends on the comment (in English it accepts
everything; in Chinese almost nothing). The content-shape tables earlier on this page are
unchanged by this step.

Full tables: `docs/evaluation/grounding/quote-field-coverage-rule.md` and
`quote-field-any-fragment.md`.

**q8 is the limit to keep in mind.** Splitting the fields makes the check precise about the
quote and silent about the comment: a real quote with an invented claim beside it passes, 20 of
20. The earlier coverage-on-content rule rejected some of these by accident and many honest
entries with them.

Whether the model actually fills `quote` with exact text is a separate question that the
constructed items cannot answer. The next section reports what happened in live runs.

## Live runs (2026-11-11 and 2026-11-12)

Five real engine runs with the `quote` field and the coverage rule on `quote`: standard depth,
`claude-sonnet-5-5`, semantic de-duplication on, cross-examination on, no hand edits. Three are
the current samples in `examples/reports/`. Two were run with the wrong persona pack by mistake
and are kept only as evidence (`docs/evaluation/runs/2026-11-11-wrong-pack/`).

### The three samples, before and after

"Before" is the 2026-11-04 sample of the same material; "after" is the current sample.

| | Steam store page | SaaS pricing page | Startup pitch |
|---|---|---|---|
| **Before** — personas passed (rule at the time) | 4 of 6 | 5 of 5 | 3 of 6 |
| Before — failures | 2 grounding | – | 2 grounding, 1 schema |
| Before — of those, pass coverage on `content` | 1 of 4 | 0 of 5 | 0 of 3 |
| Before — `direct` entries grounded, old rule → coverage on `content` | 21/22 → 8/22 | 38/41 → 0/41 | 16/21 → 1/21 |
| Before — repair turns / cost | 3 / $0.35 | 2 / $0.27 | 5 / $0.37 |
| **After** — personas passed | **4 of 6** | **5 of 5** | **6 of 6** |
| After — failures | 1 schema, 1 role drift (both malformed tool input) | – | – |
| After — `direct` entries grounded (coverage on `quote`) | **25/25** | **36/36** | **42/42** |
| After — `direct` / `inferred` / `gap` entries | 25 / 4 / 6 | 36 / 9 / 4 | 42 / 12 / 5 |
| After — shares | 71% / 11% / 17% | 73% / 18% / 8% | 71% / 20% / 8% |
| After — highest inferred share of one persona (cap 40%) | 12% | 25% | 25% |
| After — repair turns, all for schema failures | 4 | 4 | 4 |
| After — disputes cross-examined | 2 | 3 | 3 |
| After — cost | $0.35 | $0.30 | $0.51 |

Notes on reading this table:

- **It is not a controlled comparison.** Between "before" and "after" the schema, the prompt
  and the validator all changed, and so did two unrelated things: a list field that arrives as
  tool-call markup is now a schema failure with a repair turn (after the Steam run, before the
  other two), and the persona pack is resolved from the task type. The pitch sample going from
  3 of 6 to 6 of 6 cannot be attributed to the `quote` field alone.
- The Steam sample was generated at commit `af4e8c8`, the other two at `939e8ca`. For the pitch
  sample the persona stage reached the cost cap set for that run, so the engine skipped
  cross-examination; it was run afterwards on the same six validated outputs
  (`run_panel_from_outputs`). That is why it costs more than the others.
- The two Steam personas that failed did not fail on grounding. One submission had its fields
  scattered and then came back incomplete; the other's `evidence` was a string of tool-call
  markup, which at that commit was read as "100% inferred".
- In every run, on every attempt whose evidence could be parsed, the ungrounded share was 0.
  The grounding check never rejected anything.

### All five runs

| Run | Persona pack | Personas passed | `direct` entries grounded | Repair turns (all schema failures) |
|---|---|---|---|---|
| Steam store page (sample) | game-core | 4 of 6 | 25/25 | 4 |
| SaaS pricing page (sample) | general-consumer | 5 of 5 | 36/36 | 4 |
| Startup pitch (sample) | startup-panel | 6 of 6 | 42/42 | 4 |
| SaaS pricing page (wrong pack, evidence only) | game-core | 5 of 5 | 33/33 | 5 |
| Startup pitch (wrong pack, evidence only) | game-core | 6 of 6 | 41/41 | 5 |
| **Total** | | **26 of 28** | **177/177** | **22** |

The wrong-pack runs say nothing useful about the materials (game personas reviewing a pricing
page and a pitch), but they are real output under the same schema, so they count for the one
question asked here: when told to copy exact words into `quote`, did the model do it? In these
runs, yes, for every `direct` entry of every persona that passed.

### What these runs do not show

- **This is five runs on one model, three materials, one language. It is not a rate.** Nothing
  here says how often another model, another material or the same model on another day would
  put a paraphrase into `quote`.
- **The comments beside the quotes were not fact-checked**, by the rule or by anyone. 177
  grounded quotes means 177 accurate quotations, not 177 accurate observations.
- **Malformed tool input is still the main cost.** All 22 repair turns went to submissions with
  damaged structure, and both lost personas were lost to it. The `quote` field does nothing
  about that.
- The counts cover personas that passed. The two that failed contributed no evidence entries.

## Remaining limits

- **Coverage is not truth.** The check says how much of an entry is the material's own text.
  A verbatim quote can still be cherry-picked, taken out of context, or used to support a
  conclusion the material does not support.
- **The comment is not checked.** With the `quote` field, `content` is free text: a real quote
  can sit beside an invented claim and the entry passes (q8 above). Inside `quote`, up to 20% of
  the text may still be uncovered; the number check closes that only for figures.
- **The tags are self-reported.** Only entries the model chose to tag `direct` are checked.
  A fabricated claim tagged `inferred` is limited by the 40% cap and nothing else.
- **No semantic check.** A faithful paraphrase is rejected as `direct`, by design; nothing
  verifies that an `inferred` entry actually follows from the material, or that an absence
  claim under `gap` is true.
- **Labels are constructed.** 160 items were written by the same person who changed the rule,
  and the 117 real items were labelled by one reader. The set is small: a per-category cell in
  the test split has 8 items, so one error moves it by 12 points. Real items are Chinese only,
  one model, three materials. Zero errors on dev means "none in this set", not "none".
- **Cross-language evidence** (English quotes of Chinese material, or the reverse) has zero
  coverage and fails, as it did before.
- **Chinese numerals and spelled-out numbers** are not seen by the number check ("三名" vs
  "五名" is caught only through coverage).
- **Live evidence is thin.** Five runs, one model: see [what these runs do not
  show](#what-these-runs-do-not-show).
- **Old outputs stay as they are.** The 2026-11-04 samples predate the `quote` field and are
  only re-checked on `content`.

## Reproduce

```bash
python tests/fixtures/grounding_eval/build_set.py --check
python scripts/eval_grounding.py --rule legacy            # baseline
python scripts/eval_grounding.py --split dev --sweep      # parameter grid (dev only)
python scripts/eval_grounding.py                          # current rule, both item shapes
python scripts/revalidate_samples.py                      # current samples (quote) and the archived ones
```
