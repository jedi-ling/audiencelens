# 2026-11-04 — the first three sample reports (before the `quote` field)

**These are evaluation evidence, not sample reports any more.** They were the published samples
from 2026-11-04 to 2026-11-12 and are no longer linked from `/samples`. The current samples are
in `examples/reports/`.

| Folder | Input | Task / pack | Personas passed | Cost |
|---|---|---|---|---|
| `steam-page-abyss-echo/` | `test-materials/03_steam商店页_深渊回响.md` | `steam_page_review` / `game-core` | 4 of 6 | $0.35 |
| `saas-pricing-cloud-notes/` | `test-materials/04_定价页_云笔记订阅.md` | `pricing_page_review` / `general-consumer` | 5 of 5 | $0.27 |
| `startup-pitch-cloud-accounting/` | `test-materials/02_创业BP_云会计SaaS.pdf` | `pitch_review` / `startup-panel` | 3 of 6 | $0.37 |

Model `claude-sonnet-5-5`, standard depth. Each folder is unchanged from when it was a sample:
`report.html` / `report.json` / `report.md`, `meta.json`, `persona_outputs.json`.

## Why they were replaced

They were generated under the first grounding rule, which accepted a `direct` evidence entry if
any single fragment of it appeared in the material. In these outputs the model wrote the quote
and its own comment into one field, `content`. When the rule was replaced by a coverage rule,
only 1 of the 12 personas in these reports still passed it:

| Sample | Personas in the report | Pass, rule at generation | Pass, coverage rule on `content` | `direct` entries grounded, old → new |
|---|---|---|---|---|
| steam-page-abyss-echo | 4 | 4 | 1 | 21/22 → 8/22 |
| saas-pricing-cloud-notes | 5 | 5 | 0 | 38/41 → 0/41 |
| startup-pitch-cloud-accounting | 3 | 3 | 0 | 16/21 → 1/21 |

Each `meta.json` records these numbers under `grounding_revalidation`
(`scripts/revalidate_samples.py` recomputes them; a test keeps them equal).

The evidence schema then got a separate `quote` field and the samples were regenerated. The full
account is in [../../grounding-check.md](../../grounding-check.md).

## What still refers to these files

- `tests/fixtures/grounding_eval/real_items.jsonl`: the 84 real `direct` entries in the
  grounding evaluation set come from these `persona_outputs.json` files.
- [../../cross-exam-observation.md](../../cross-exam-observation.md) and
  [../../dedup-fallback-finding.md](../../dedup-fallback-finding.md) describe these runs.
