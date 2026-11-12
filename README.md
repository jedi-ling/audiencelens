<div align="center">

# AudienceLens

**A panel of independent AI personas reviews your product, then argues out its sharpest disagreements — with every claim tagged by evidence.**

[![CI](https://github.com/jedi-ling/audiencelens/actions/workflows/ci.yml/badge.svg)](https://github.com/jedi-ling/audiencelens/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)](pyproject.toml)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](web/frontend/package.json)

English · [中文](README_zh.md) · [日本語](README_ja.md)

</div>

- **What it is** — a multi-agent *synthetic audience review* system: a Python engine, a FastAPI + React web app, a CLI and an MCP server. You give it a Steam page, a pricing page, a pitch deck or a game concept; it returns a structured report of risks, disagreements and fixes.
- **Who it's for** — indie developers and small product teams who want a cheap, fast pre-screen *before* spending money on real user research.
- **What's different** — personas review in isolation (no herding), only the top-3 genuine disagreements are cross-examined, vote changes are decided by code rather than by an LLM judge, and every piece of evidence is tagged `direct` / `inferred` / `gap` with a hard 40% cap on inference.

> **AudienceLens is not a substitute for real user research.** Its output is synthetic. There is no validated accuracy data yet — see [Validation status](#validation-status).

---

## Screenshots

![Conversational review entry](docs/images/en/hero.png)
![Sample reports page](docs/images/en/samples.png)
![Review report](docs/images/en/report.png)

<sub>English UI. The report body is Chinese because the engine currently generates reports in Chinese only.</sub>

---

## Sample reports

Real engine runs on fictional product material. The model output is unedited; the stylesheet of
each `report.html` was updated after a CSS fix, and nothing else in the files was changed
(`examples/reports/`; also browsable on the app's `/samples` page). Standard depth, model
`claude-sonnet-5-5`, 2026-11-11 and 2026-11-12, semantic de-duplication on; cost is the app's own
accounting. Each folder's `meta.json` records the run and `persona_outputs.json` holds the
validated persona outputs.

| Report | Input | Personas passed | `direct` entries grounded | Cross-examination | Cost |
|---|---|---|---|---|---|
| [Steam store page — 深渊回响](examples/reports/steam-page-abyss-echo/report.md) | `test-materials/03_steam商店页_深渊回响.md` (`steam_page_review`, `game-core`) | 4 of 6 | 25 of 25 | 2 disputes, one rebuttal round each | $0.35 |
| [SaaS pricing page — 云笔记订阅](examples/reports/saas-pricing-cloud-notes/report.md) | `test-materials/04_定价页_云笔记订阅.md` (`pricing_page_review`, `general-consumer`) | 5 of 5 | 36 of 36 | 3 disputes, one rebuttal round each | $0.30 |
| [Startup pitch — 轻账 LiteBooks](examples/reports/startup-pitch-cloud-accounting/report.md) | `test-materials/02_创业BP_云会计SaaS.pdf` (`pitch_review`, `startup-panel`) | 6 of 6 | 42 of 42 | 3 disputes, one rebuttal round each | $0.51 |

The Steam sample was generated at commit `af4e8c8`, the other two after the fix that resolves the persona pack from the task type (`939e8ca`); for the pitch sample, cross-examination was run as a second step on the same validated outputs (`runner.cli.run_panel_from_outputs`).

"Grounded" means the entry's `quote` is text from the material; the comment written beside it is
not checked. The two Steam personas that did not pass were lost to malformed tool input, not to
the grounding check. Three runs on one model are not a pass rate. The first samples (2026-11-04,
before evidence entries had a `quote` field) are kept as evidence in
[docs/evaluation/runs/2026-11-04-pre-quote-field/](docs/evaluation/runs/2026-11-04-pre-quote-field/notes.md);
the before/after comparison is in [docs/evaluation/grounding-check.md](docs/evaluation/grounding-check.md).

No vote changed in any rebuttal: the largest confidence movement was 8 points against the
15-point threshold. Why some personas fail validation, and why cross-examination needed the
semantic backend, is written up in [docs/evaluation/](docs/evaluation/).

---

## Architecture

```mermaid
flowchart TB
    subgraph Frontend["Frontend"]
        FE["Web app<br/>React 19 + Vite + TypeScript"]
        AD["Admin panel<br/>React + Vite"]
    end
    subgraph Backend["Backend · FastAPI (web/backend)"]
        API["REST API + WebSocket progress"]
        Q["In-process review queue"]
    end
    subgraph Engine["Engine · src/runner, src/harness"]
        PS["Panel selection"]
        PP["Independent persona panels"]
        V["3-layer validation"]
        CX["Cross-examination<br/>(top-3 disputes)"]
        AG["Rule-driven aggregation"]
        EV["8-dimension evaluator<br/>(optional, post-hoc)"]
    end
    subgraph Providers["Providers & DB"]
        subgraph LLM["LLM providers"]
            AN["Anthropic<br/>(native API)"]
            OC["OpenAI-compatible<br/>(DeepSeek, Kimi, Qwen, GLM, ...)"]
            OL["Ollama<br/>(local)"]
        end
        DB[("SQLite (dev)<br/>PostgreSQL (prod)")]
    end

    FE --> API
    AD --> API
    API --> Q --> PS --> PP --> V --> CX --> AG --> EV
    PP --> LLM
    CX --> LLM
    API --> DB
```

The same engine runs behind the CLI (`audiencelens`), the Python API (`runner.cli.run_panel`), the MCP server (`audiencelens-mcp`) and the web app. Deeper write-ups: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and the methodology paper [docs/paper/arxiv-paper.md](docs/paper/arxiv-paper.md).

**By the numbers** (each one is recomputed from the repo by `tests/test_public_claims.py`, which fails if this file drifts):
72 behavior-driven personas across 11 packs, 14 task types; the backend has 121 route handlers, 28 service modules and 7 emitted WebSocket event types; the frontend has 25 page components and 16 components.

---

## How a review runs

1. **Panel selection** — `src/runner/panel_selector.py` picks personas for the task type and always includes a designated dissenter. Panel size depends on the mode (`quick` / `standard` / `full`).
2. **Independent persona panels** — each persona reviews the material on its own, in parallel (`run_panel` in `src/runner/cli.py`). No persona sees another persona's output or identity before step 4.
3. **Validation** — `src/runner/validator.py` checks every output: JSON schema → role consistency → evidence grounding. An output that fails can be retried (`src/config/budget.yaml`); if it still fails it is **excluded** from the report and listed in `failed_personas`.
4. **Disagreement extraction** — `extract_controversy_points` in `src/runner/cross_exam.py` merges near-identical issues across personas (semantic similarity via `src/runner/similarity.py`, falling back to string similarity), then ranks them by the **variance of severity** between personas and keeps the top 3. Points everyone already agrees on are never debated.
5. **Cross-examination, one rebuttal round per dispute** — the two most opposed personas on each point get the other side's argument back, labelled only `A1` / `B1`. In `standard` mode one moderated call writes both rebuttals; in `full` mode each persona is re-invoked separately; `quick` skips this step.
6. **Vote change decided by code** — `_decide_change` in `src/runner/cross_exam.py` records a stance change only if the stance text actually changed **and** `|Δconfidence| ≥ θ`, where θ is `confidence_change_threshold: 0.15` in `src/config/aggregation-rules.yaml`. The model saying "I changed my mind" counts for nothing; rejected changes are kept as `suppressed_changes`.
7. **Evidence levels** — every claim carries `direct` (quoted from the material), `inferred`, or `gap` (information that is missing). `MAX_INFERRED_RATIO = 0.4` in `src/runner/validator.py` caps inference at 40% per persona.
8. **Aggregation** — `src/runner/aggregator.py` turns the validated outputs into consensus, disagreements, prioritised fixes and a release-risk level, in JSON, Markdown and HTML.

Only one rebuttal round is implemented. Multi-round debate, early termination and consensus tracking are designed but **not** implemented (see the paper, §3).

---

## Key design decisions

### 1. Independent panels before any cross-talk
**Decision.** Personas never see each other during the first pass; the prompt is split into a byte-identical shared part (task, materials, rules) and a per-persona part (`render_prompt_split` in `src/runner/persona_agent.py`), run in parallel by `run_panel` (`src/runner/cli.py`).
**Why.** Anchoring and herding are the classic focus-group failure; a single LLM asked to "play six users" converges on one voice.
**Trade-off.** No emergent consensus, and cost grows linearly with panel size. The shared prefix is sent as a cacheable system block to soften that.

### 2. Vote changes decided by code, not by an LLM judge
**Decision.** After the rebuttal, the model only reports a new stance and confidence; whether that is a "change" is computed in `_decide_change` (`src/runner/cross_exam.py`) against θ from `src/config/aggregation-rules.yaml`.
**Why.** An LLM judge is another unaudited opinion, and models happily claim to have been persuaded. A deterministic rule is reproducible and inspectable.
**Trade-off.** θ = 0.15 is an engineering guess, not a calibrated value; subtle but real changes below θ are dropped (and kept visibly as `suppressed_changes`). `audiencelens cross-exam-ablation` (`src/harness/cross_exam_ablation.py`) exists to measure this; no result is published yet.

### 3. Evidence-level tagging with a hard inference cap
**Decision.** Every claim is tagged `direct` / `inferred` / `gap`; outputs whose inferred share exceeds `MAX_INFERRED_RATIO` (`src/runner/validator.py`) fail validation and are excluded. A `direct` entry has to carry a `quote`, text copied from the material, next to the persona's own comment in `content`. Only the quote is checked: after normalising punctuation, character width, case and whitespace, at least 80% of it must be covered by runs of text that appear in the material (runs of at least 4 CJK characters or 3 Latin words), and every number in it must sit inside such a run (`src/config/grounding.yaml`). A `direct` entry without a quote counts as not grounded. A persona fails when 30% or more of its `direct` entries are not grounded.
**Why.** The cheapest failure of synthetic research is plausible-sounding feedback grounded in nothing. Making the evidence type explicit lets a reader discount it, and `gap` turns "I don't know" into a useful output.
**Trade-off.** The tags are self-reported by the model; only the `quote` of `direct` evidence is checked against the source text, and the check measures quoting, not truth: the comment beside a quote is not checked at all, and an accurate paraphrase cannot be `direct`. The 40% cap can also reject outputs that were reasonable. The coverage rule replaced an earlier one that accepted an entry if any single fragment matched, a weakness found by an external review. On a small labelled set with constructed labels, false accepts on the held-out split went from 43 of 69 to 1 of 69, with 1 false reject of 27 under both rules ([docs/evaluation/grounding-check.md](docs/evaluation/grounding-check.md)).

---

## Privacy & ethics

- **Per-visitor guest isolation.** Every unauthenticated visitor gets their own guest identity, carried by a signed, HttpOnly, SameSite=Lax cookie (Secure in production) — see `resolve_guest_identity` in `web/backend/app/deps.py`. Conversations, reviews, projects, usage and CDK balance are scoped to it; the claim-after-login flow moves only that guest's records. 22 isolation tests live in `web/backend/tests/test_guest_isolation.py`. Legacy rows from before this fix can be quarantined with `web/backend/scripts/quarantine_anonymous.py` (dry-run by default, deletes nothing).
- **Demographic fields stripped before prompting.** Only the whitelisted `CORE_FIELDS` of a persona (behavior profile, decision rules, triggers, …) are serialised into the prompt (`_minify_persona` in `src/runner/persona_agent.py`); audience fields such as age band or region never reach the model. `check_identity_behavior_decoupling` in `src/runner/validator.py` flags identity-based reasoning in the output, and a 50-case labelled stereotype benchmark ships with the harness.
- **BYOK keys encrypted at rest.** Stored API keys are encrypted with Fernet (`cryptography`) using a key derived from `AL_ENCRYPTION_KEY`, which is separate from the session-signing secret (`web/backend/app/core/security.py`). The UI only ever shows masked keys.
- **Labelled as synthetic.** Reports carry a mandatory "AI-generated synthetic review, not real user research" notice; see [ETHICS.md](ETHICS.md).

---

## Tech stack

| Layer | Technology |
|---|---|
| Engine | Python 3.11, Jinja2 prompt templates, jsonschema, PyYAML, Click CLI |
| LLM access | Anthropic SDK (native `/v1/messages`) + an OpenAI-compatible HTTP client (`src/runner/llm_client.py`) |
| Backend | FastAPI, SQLAlchemy, WebSocket progress, in-process job queue |
| Database | SQLite (development), PostgreSQL 16 (production; CI runs the backend suite on both) |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Zustand, Recharts, three.js |
| Admin | React + Vite, Vitest |
| Deployment | Docker Compose + Caddy (automatic HTTPS), or bare-metal systemd + nginx ([web/DEPLOY.md](web/DEPLOY.md)) |
| CI | GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) |

---

## Quickstart

### CLI (Anthropic key)

```bash
pip install -e .                      # registers the `audiencelens` command
export ANTHROPIC_API_KEY=...          # your own key
audiencelens run synthetic-playtest steam_page_review examples/steam-page-sample/artifact.json
```

Without `ANTHROPIC_API_KEY` the CLI runs in **simulation mode**: every persona output is placeholder data with zero review value, and the report says so prominently.

### Web app (local, bring your own key)

```bash
# backend → http://127.0.0.1:8001
cd web/backend
pip install -r requirements.txt
python run.py

# frontend (second terminal) → open the URL Vite prints
cd web/frontend
npm install
npm run dev
```

With the default `AL_AUTH_ENABLED=false` the app runs in single-user mode. Open **Settings → API keys** and add either an Anthropic key or any **OpenAI-compatible** provider (DeepSeek, Kimi, Qwen, GLM, … — presets are in `OPENAI_COMPATIBLE_PRESETS` in `src/runner/llm_client.py`). Configuration reference: [.env.example](.env.example) (names only) and [docs/MAINTENANCE.md](docs/MAINTENANCE.md).

### Semantic de-duplication (needed for cross-examination)

Cross-examination only debates issues that several personas raised, so differently worded versions
of the same issue have to be merged. That needs the Chinese embedding model in
`src/runner/similarity.py`; the Docker image installs it by default. For a local setup:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers   # downloads BAAI/bge-small-zh-v1.5 (~93 MB) on first use
```

Without it the engine falls back to string similarity and the report says so explicitly
("Semantic dedup not installed — cross-examination may not trigger"); see
[docs/evaluation/dedup-fallback-finding.md](docs/evaluation/dedup-fallback-finding.md).

### Ollama (local models)

Pick the **Ollama** preset (`http://localhost:11434/v1`) as an OpenAI-compatible provider and enter the model you have pulled. From Python, pass `provider="openai_compatible"`, `api_base=...` and `model_override=...` to `run_panel`.

> **SSRF guard.** The backend refuses loopback and private-network `api_base` addresses (`assert_api_base_is_safe` in `web/backend/app/api/platform.py`) unless it runs in single-user mode (`AL_AUTH_ENABLED=false`) on a non-production host. A local Ollama therefore works for local use only, never on a multi-tenant deployment. Review quality depends heavily on the model; small local models often fail the structured-output validation.

### Docker

```bash
cd web
cp .env.production.example .env      # then set AL_CORS_ORIGINS and AL_JWT_SECRET at minimum
docker compose up
```

---

## Tests

```bash
python -m pytest tests/ -q                          # core engine
(cd web/backend && python -m pytest tests/ -q)      # backend (SQLite; CI also runs it on PostgreSQL)
(cd web/frontend && npm run build)                  # i18n check + TypeScript + Vite build
(cd web/admin && npx vitest run)                    # admin panel unit tests
```

Measured 2026-11-04 (default requirements, as in CI): core 1863 passed / 9 skipped · backend 944 passed / 1 skipped · admin vitest 35 passed; with the optional semantic backend installed, 3 more core tests run instead of skipping.

CI ([ci.yml](.github/workflows/ci.yml)) runs all of the above on every push and pull request, plus a PostgreSQL 16 backend job, a skill-mirror consistency check and a YAML parse check.

---

## Validation status

**No validated accuracy data yet.** Nothing in this repository shows that AudienceLens predicts what real users will say, or that cross-examination improves a review. The methodology for finding out is written down but not yet executed:

- [docs/benchmark-protocol.md](docs/benchmark-protocol.md) — blind comparison against a single-prompt baseline and a quick human review
- [docs/pilot-playbook.md](docs/pilot-playbook.md) — Steam store-page pilot with real projects
- [docs/product-validation.md](docs/product-validation.md) — decision-value metrics (usefulness, decision change, adoption)
- [docs/parity-data-collection-plan.md](docs/parity-data-collection-plan.md) — collecting paired real-user reference data

An early demo example ("Cyber Scavenger") was **retracted** because its numbers could not be reproduced from the system as built; the paper explains why in [§4.5 On the Absence of a Case Study](docs/paper/arxiv-paper.md#45-on-the-absence-of-a-case-study).

<!-- TODO(evaluation): add an "Evaluation results" section once the benchmark protocol has been run on real projects. Do not add numbers before then. -->

---

## Known limitations

- **Synthetic ≠ real users.** Personas are prompts over a language model; they can be confidently wrong in ways real users never would be.
- **LLM bias.** Outputs inherit the underlying model's biases. Stereotype checks reduce but do not remove this, and different providers give materially different reviews.
- **Cost scales with panel size.** Each persona is a separate model call, and `full` mode adds one rebuttal call per involved persona.
- **No platform key is offered.** Hosted use is bring-your-own-key only; the plan / quota / CDK machinery exists in code but is not funded.
- **Some persona outputs fail validation.** The validator rejects paraphrases labelled `direct` and malformed submissions; one repair turn recovers many of them, not all (see the sample outcomes above).
- **The grounding check measures quoting, not truth.** A `direct` entry passes when its `quote` is the material's own words; nothing checks the comment written beside it or that the quote is used fairly, and `inferred` entries are not checked against the material at all. In five live runs on one model, all 177 `direct` entries from the personas that passed carried a quote the rule accepts; that is a handful of runs, not a rate ([docs/evaluation/grounding-check.md](docs/evaluation/grounding-check.md)).
- **Malformed tool input still costs repair turns and personas.** In those five runs, 22 repair turns were spent on submissions with damaged structure, and 2 of 28 personas were lost to it.
- **Single debate round.** Further rounds, early termination and consensus tracking are designed but not implemented; θ is uncalibrated.
- **Reports are generated in Chinese only for now** (`SUPPORTED_REPORT_LANGS = zh-CN`). English output requires the `output_lang` path described in [docs/I18N_CONTRACT.md](docs/I18N_CONTRACT.md) §10, which is not yet implemented.

---

## Development note

AudienceLens was built by Ling Yuanyi with AI-assisted development (Claude Code, Codex, Trae, Qoder, Kimi). Design, code review and verification — including the test suites, the claim checks in `tests/test_public_claims.py` and the retraction of unreproducible results — are the author's.

## License

[MIT](LICENSE) © 2026 Ling Yuanyi

## Author

**Ling Yuanyi** — GitHub [@jedi-ling](https://github.com/jedi-ling)
