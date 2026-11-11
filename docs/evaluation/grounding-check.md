# Evidence grounding check: from "any fragment" to coverage

2026-11-11. No model was called for anything on this page.

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
  reviews: every `direct` entry in `examples/reports/*/persona_outputs.json` (84) and the entries
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

## Effect on the stored sample reports

The three sample reports were generated under the old rule and are **not** regenerated or
edited. `scripts/revalidate_samples.py` re-checks their stored persona outputs offline:

| Sample | Personas in the report | Pass grounding, old rule | Pass grounding, coverage rule | `direct` entries grounded, old → new |
|---|---|---|---|---|
| steam-page-abyss-echo | 4 | 4 | 1 | 21/22 → 8/22 |
| saas-pricing-cloud-notes | 5 | 5 | 0 | 38/41 → 0/41 |
| startup-pitch-cloud-accounting | 3 | 3 | 0 | 16/21 → 1/21 |

**Only 1 of the 12 personas in the published samples would pass the new rule as written.**
The reason is visible in the real items: of the 84 `direct` entries in the samples, 8 are
quotes. The rest are accurate-looking restatements, quotes with commentary attached, and
statements about what the page does not say. The old rule let almost all of them through; the
new rule does not. Each sample's `meta.json` carries these numbers under
`grounding_revalidation`, and a test keeps them equal to the script's output.

What this does and does not show:

- It shows how the model used the `direct` tag under the old rule, with a repair prompt that
  only fired for a few entries.
- It does **not** show what a live run under the new rule would produce. In a live run a
  failing persona gets one repair turn that now names the uncovered part of each entry, and
  the model can re-tag restatements as `inferred`. How often that succeeds has not been
  measured, because this change made no model calls. Until it is measured, expect more repair
  turns (each one is billed) and possibly more excluded personas than the samples show.
- Moving restatements to `inferred` also pushes against the separate 40% cap on inferred
  evidence, so the two checks now pull on each other.

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
  quotation above the comment.
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

**Not measured yet:** whether the model fills `quote` correctly in a live run. That needs model
calls and is the next step; nothing on this page is evidence about it.

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
- **Old outputs stay as they are.** The three stored samples predate the `quote` field and are
  only re-checked on `content`.

## Reproduce

```bash
python tests/fixtures/grounding_eval/build_set.py --check
python scripts/eval_grounding.py --rule legacy            # baseline
python scripts/eval_grounding.py --split dev --sweep      # parameter grid (dev only)
python scripts/eval_grounding.py                          # current rule, both item shapes
python scripts/revalidate_samples.py                      # effect on the stored samples
```
