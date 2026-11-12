# Observation: cross-examination changed no vote in the three samples

Date: 2026-11-04 · Model: `claude-sonnet-5-5` · Mode: `standard` (one moderated rebuttal call)
Data: `cross_examination` in each `report.json` of the 2026-11-04 samples, now kept in `docs/evaluation/runs/2026-11-04-pre-quote-field/`. No new runs were made for this note.

*Later note (2026-11-12):* the samples were regenerated with a new evidence schema. In the three new reports (`examples/reports/`) cross-examination again changed no vote: 8 disputes, all rebuttals parsed, largest confidence movement 8 points (θ is 15), no stance text changed. The table and hypotheses below describe the 2026-11-04 runs.

## What the reports record

| Sample | Disputes | Rebuttals parsed | Δconfidence per rebuttal (points) | Stance changes claimed | Vote changes |
|---|---|---|---|---|---|
| steam-page-abyss-echo | 2 | 4 / 4 | −2, 0, 0, 0 | 0 | 0 |
| saas-pricing-cloud-notes | 3 | 5 / 5 | 0, 0, 0, 0, 0 | 0 | 0 |
| startup-pitch-cloud-accounting | 1 | 3 / 3 | 0, 0, −2 | 0 | 0 |

- The largest movement was |Δconfidence| = 2 points. A vote change needs 15 (θ = `confidence_change_threshold: 0.15` in `src/config/aggregation-rules.yaml`).
- `suppressed_changes` is empty in all three reports. That list records rebuttals whose stance text changed but whose confidence moved less than θ. Because it is empty, **no persona changed its stance text at all**. `_decide_change` (`src/runner/cross_exam.py`) needs both a stance change and |Δconfidence| ≥ θ. With these outputs, any lower θ, including 0, would still record zero vote changes.
- Three samples with one round each is far too small to support a general conclusion. This is an observation, not a result.

## Possible explanations (hypotheses only, none tested)

Context: in `standard` mode no persona is re-invoked. One moderator call (`SECTION:moderated` in `src/templates/cross-exam-prompt.md`) writes both rebuttals for every dispute. It sees each side's current stance and confidence, and the prompt says that both sides keeping their stance is "completely normal and common" and that change must not be manufactured.

1. **Anchoring.** The moderator is shown each side's current stance and confidence, and is told to copy the stance verbatim when it does not change. Showing the starting value may anchor the updated one. In `full` mode each persona is re-invoked with its own profile and decision rules; those could anchor it as well, in a different way.
2. **Single moderated round.** One call argues both sides, so neither side is defended by a separate invocation, and there is only one exchange. Per-persona rebuttals (`full` mode) might behave differently. Multi-round debate is designed but not implemented.
3. **The prompt's guard against fake progress is too strong.** The instruction above was added on purpose, so that rebuttals would not invent changes. It may also suppress real ones.
4. **θ too high.** θ = 0.15 is an uncalibrated engineering guess. The recorded data argues against this as the *only* cause, because no stance text changed (see above). θ would matter for runs where stances do move.
5. **The disputes are real disagreements of taste or risk tolerance, not of fact.** In that case a rebuttal has nothing to correct, and stable votes are the expected outcome.

## How to test them

`audiencelens cross-exam-ablation` (`src/harness/cross_exam_ablation.py`) runs the persona panel **once**, then branches the same persona outputs into `none` / `moderated` / `multi_agent` rebuttal conditions. Cross-examination is therefore the only variable. It reports priority-fix churn, vote changes and suppressed changes per condition, and needs an API key.

- Hypothesis 2 (moderated vs per-persona rebuttal): compare `moderated` with `multi_agent` directly.
- Hypotheses 1, 3 and 5: compare the per-condition `vote_changes` / `suppressed_changes` counts the ablation reports. The rebuttal text itself is in the `cross_examination` section of an ordinary report. If stances stay put under both rebuttal forms on material with clear factual disputes, that points to anchoring or the prompt. Separating those two needs a prompt variant, which the ablation does not provide; it would be a change to `cross-exam-prompt.md`, measured with the same harness.
- Hypothesis 4: θ is not a condition in the ablation. It can be checked offline, with no API calls, by re-applying `_decide_change` with other θ values to the recorded rebuttals. That only becomes informative once some stances actually move.
- Multiple rounds cannot be tested until they are implemented.

The ablation can falsify ("cross-examination changed nothing, so it is pure cost"). It cannot show that a changed report is a better one. See the docstring of `cross_exam_ablation.py` and [docs/product-validation.md](../product-validation.md).
