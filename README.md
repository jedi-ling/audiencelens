<div align="center">

# AudienceLens

**Multi-Agent Synthetic Audience Review System with Cross-Examination**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB.svg)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](web/backend/requirements.txt)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](web/frontend/package.json)
[![Tests](https://img.shields.io/badge/Tests-750+-success.svg)](tests/)

**基于合成人格的多代理交叉质询评审系统 · Python CLI + FastAPI + React**

[English](#english) · [中文](#中文)

</div>

---

<a id="english"></a>

## Overview

AudienceLens is a **full-stack synthetic audience review system** that simulates diverse player personas to evaluate games, products, and creative projects — before committing resources to real user testing.

Unlike simply asking ChatGPT for feedback, AudienceLens:
1. Runs **multiple behavior-driven personas in isolation** (66 across 10 packs)
2. Extracts the **top-3 controversies** across persona outputs and runs **one live rebuttal round** on them — arbitrated in `standard` mode, per-persona in `full` mode, skipped in `quick` (see §3 for exactly what each tier does)
3. Enforces **ethical constraints** — stereotype detection, evidence tiering (`inferred` hard-capped at 40%), mandatory disclaimers
4. Ships an optional **8-dimension quality scorecard** — post-hoc scoring, off by default; it grades a finished review, it does not gate or re-run one

> **AudienceLens is not a substitute for real user research.** It is a pre-screening and stress-testing tool for discovering the most obvious issues before investing in human testing.

---

## Feature Categories

### 1. Runner Engine — Pipeline Architecture

The core execution engine is a 7-stage pipeline in `src/runner/`:

| Stage | Module | Function |
|---|---|---|
| **Panel Selection** | `panel_selector.py` | Select personas by task type; guarantee dissenter inclusion (auto-append P15 if missing) |
| **Evidence Pre-check** | `evidence_precheck.py` | Filter out personas with <30% evidence coverage for required evidence types |
| **Persona Execution** | `persona_agent.py` | Render 5-segment prompt (Persona Card → MBTI Boundary → Identity-Behavior Decoupling → Task → Evidence Rules); parse structured output |
| **3-Layer Validation** | `validator.py` | Schema validation (Draft7Validator) → Role consistency (must_comment_on ≥80%, inferred ≤40%) → Evidence grounding (hallucination <30%) |
| **Cross-Examination** | `cross_exam.py` | Extract top-3 controversies (by severity variance, semantic dedup with lexical fallback); pair the most opposed personas and run **one rebuttal round** against the model. `mode` is one of `derived_summary` / `moderated_rebuttal` / `multi_agent_rebuttal`, and `is_live_debate` is true only for the latter two — see §3 |
| **Rule-Driven Aggregation** | `aggregator.py` | Compute consensus, disagreements, priority fixes (severity × persona weight × affected count); release risk assessment |
| **Calibration Check** | `calibration.py` | Role consistency rate, perspective coverage (Jaccard ≥0.3), hallucination rate, stability |

### 2. Persona System — 12-Axis Behavioral Vectors

Personas are defined by **behavioral vectors**, not demographic labels. SCOPE research shows demographics explain only 1.5% of behavioral variance.

| Axis | Description |
|---|---|
| `patience` | Time tolerance for slow-burn content |
| `genre_literacy` | Domain knowledge depth |
| `novelty_seeking` | Preference for innovation vs. convention |
| `risk_tolerance` | Comfort with uncertainty (EA/crowdfunding) |
| `social_influence` | Reliance on reviews/community sentiment |
| `completion_drive` | Drive to complete all content/achievements |
| `price_sensitivity` | Price-value sensitivity |
| `emotional_engagement` | Emotional investment level |
| `agency_preference` | Preference for guidance vs. free exploration |
| `tolerance_for_ambiguity` | Comfort with unclear systems/narratives |
| `platform_loyalty` | Platform attachment strength |
| `criticism_style` | Constructive vs. harsh feedback tendency |

**10 Persona Packs (66 personas total):**

| Pack | File | # | Personas |
|---|---|---|---|
| Game Core | `game-core.yaml` | 16 | Indie core operator, systems theorycrafter, challenge hunter, story immersion seeker, completionist collector, visual atmosphere lover, casual mobile drop-in, first-time novice, cozy social sharer, Steam wishlist browser, TapTap comment scout, streamer creator, publisher scout, price-sensitive buyer, toxic skeptic, competitor-loyal veteran |
| Competitive Esport | `competitive-esport.yaml` | 5 | Rank climber, speedrun challenger, team coordinator, esport spectator, mod competitor |
| Family Casual | `family-casual.yaml` | 5 | Parent-child creator, party socialite, cozy relaxer, nostalgia retro, generational bridge |
| Indie Creative | `indie-creative.yaml` | 5 | Indie connoisseur, creativity seeker, culture consumer, indie narrative designer, indie rhythm fanatic |
| Mobile F2P | `mobile-f2p.yaml` | 7 | Fragmented whale, free lunch hunter, social-driven mobile, anime aesthete, hypercasual passerby, mobile monthly card, mobile ad tolerant |
| VR Immersive | `vr-immersive.yaml` | 4 | VR motion sensitive, presence seeker, VR fitness player, social VR resident |
| Accessibility | `accessibility.yaml` | 4 | Color vision aid, cognitive load sensitive, motor accessibility, hearing accessibility |
| Educational Serious | `educational-serious.yaml` | 4 | Teacher evaluator, parent gatekeeper, lifelong learner, special needs learner |
| General Consumer | `general-consumer.yaml` | 8 | Value-conscious buyer, skeptical reviewer, B2B decision maker, first-time user, power user, word-of-mouth sharer, accessibility user, competitor-loyal switcher |
| Startup Panel | `startup-panel.yaml` | 8 | Angel investor, VC associate, industry analyst, tech-DD engineer, early-adopter customer, incubator screener, unit-economics skeptic, devil's advocate |

> Non-game personas live in the last two packs (16 of 66). There is **no red-team persona pack** — "red team" is a skill hint applied to an existing panel, not a set of personas.

### 3. Cross-Examination — Controversy Extraction + One Live Rebuttal Round

Traditional "let the most disagreeing personas argue" often produces unproductive extreme-vs-extreme noise. AudienceLens narrows the debate to the points that are actually contested, then makes the personas defend them:

1. **Controversy Extraction** — Extract top-3 controversies from all persona outputs, ranked by severity variance, deduplicated semantically (`similarity.py`) with a SequenceMatcher fallback. Points where everyone already agrees are filtered out before any call is made — the system does not manufacture a disagreement to look busy
2. **Opposing Stance Pairing** — For each controversy, pick the two personas holding the most opposed positions and surface each side's own wording as the pro/con argument, labelled `A1` / `B1`
3. **Rebuttal Round** — Send those arguments back to the model and collect a rebuttal plus an updated stance and confidence for each side
4. **Code-Adjudicated Vote Changes** — A stance change is recorded only if the stance text actually changed **and** `|Δconfidence| ≥ θ`, with `θ` read from `src/config/aggregation-rules.yaml` (0.15 today). A model asserting it changed its mind is not enough. Rejected claims are kept in `suppressed_changes` with the reason
5. **Honest Labeling** — `mode` is `derived_summary` / `moderated_rebuttal` / `multi_agent_rebuttal`, `is_live_debate` is true only when a rebuttal was actually parsed, and a `limitation` string shipped in the report spells out in plain language which tier ran

**The three tiers are not equivalent, and the difference matters more than the shared label:**

| Mode | Rebuttal calls | What actually happens |
|---|---|---|
| `quick` | 0 | Not run at all |
| `standard` | 1 | **One arbitrated round.** A single call writes both sides' rebuttals from a moderator's vantage point. It is a real rebuttal; it is **not** each persona speaking independently |
| `full` | 1 per involved persona | **True multi-agent rebuttal.** Each persona is re-invoked with its own persona card and the opponent's argument stripped of attribution |

**Opponent anonymity.** The prompt template has no persona-name slot at all, arguments are addressed only by ID, and the renderer additionally scrubs persona names out of argument *text*. Scope, stated precisely: what is guaranteed is that **no persona sees another persona's identity**. In `full` mode on the engine path a persona does still receive its own card (name included) so it argues in its own voice; the web v1 path strips even that.

**When a rebuttal call fails**, the failure is not swallowed: `mode` falls back to `derived_summary`, the reason lands in `failures[]` and in the report's `limitation`, and the rest of the review is produced as normal. Rebuttal tokens and cost are billed into the review totals and broken out separately under `cost_summary["cross_exam"]`.

> **Still designed but not implemented — do not cite these as capabilities:** the second and third debate rounds, early termination on convergence, panel-wide persuasion scoring (only the two most-opposed personas per point participate, and no 1–5 persuasiveness score is computed anywhere), consensus-evolution tracking, and tipping-point detection. `consensus_strength`, `converging`, `oscillating`, `tipping_point`, and `cascade_point` appear in zero source files. **And the implemented round has not been evaluated:** we have no measurement showing it makes a review better, and θ=0.15 is an engineering guess that is now consequential rather than validated.
>
> **One precise exception, so this stays honest in the other direction.** The above describes the **Python engine** — the path behind the CLI, the Python package, the MCP server, and the hosted Web app, i.e. everything most users touch. The **skill packs** (`.claude/skills/`, `.trae/skills/`) are a different path: there, an LLM coding agent reads `SKILL.md` and performs Phase 5 itself, including the persuasion scoring and the θ=0.15 stance update. So the skill path may do more than the engine does — but it is an agent following Markdown instructions, with **no code enforcing it, no schema validating it, and no test covering it**. It is not deterministic and it is not a guarantee. Do not cite the skill path as evidence for the engine, or vice versa.

### 4. Task Types — 14 Review Scenarios

| Task Type | Use Case |
|---|---|
| `steam_page_review` | Store page information architecture, visual communication, trust signals |
| `demo_first_play` | Onboarding friction, game feel, first 15-minute experience |
| `concept_review` | Core loop, differentiation, feasibility |
| `monetization_review` | Pricing, pay boundaries, value perception |
| `looking_for_party_post` | Community copy, virality, social appeal |
| `update_announcement_review` | Patch notes, trust reinforcement, retention signals |
| `devlog_review` | Development narrative, community engagement |
| `kickstarter_review` | Campaign page, reward tiers, backer trust |
| `localization_review` | Translation quality, cultural adaptation |
| `discord_community_review` | Community management, tone, engagement patterns |
| `product_feedback_review` | General product feedback collection and interpretation (not game-specific) |
| `pricing_page_review` | Pricing tiers, value communication, trust signals (not game-specific) |
| `onboarding_review` | First-run experience, activation friction (not game-specific) |
| `pitch_review` | Startup BP / pitch deck / grant application, from investor and due-diligence angles |

The single source of truth is `src/runner/task_types.py::VALID_TASK_TYPES`; anything not in that list is rejected with a 400.

### 5. Web Application — Full-Stack Implementation

| Layer | Tech Stack | Key Features |
|---|---|---|
| **Backend** | FastAPI + SQLite + WebSocket | 83 route handlers (`grep -c '^@router\.' app/api/*.py`, 2026-07), 6 emitted WebSocket event types, 18 service modules |
| **Frontend** | React 19 + TypeScript + Tailwind + shadcn/ui + Recharts | 18 pages + landing page, 7 components, 3 Zustand stores |
| **Services** | 18 modules in `app/services/` (key / quota / job / intent / ledger / CDK / chat / mail / plan / admin-settings / audit-log / auth-token / ethics / evaluation / report-gating / review / user-data / validation), plus `PersonaService` / `ReviewService` / `MaterialExtractor` defined in `services/__init__.py` | Anthropic native SDK + OpenAI-compatible HTTP (OpenAI / DeepSeek / Kimi / Qwen / GLM / Ollama presets), stereotype detection, ethics compliance |
| **Real-time** | WebSocket (6 event types emitted) | Live review progress, persona-by-persona results |
| **Deployment** | Docker Compose | Frontend (Nginx) + Backend (Uvicorn) |

**3 Review Modes** (`MODE_CONFIG` in `src/runner/cli.py`):

| Mode | Personas | Cross-Exam | Calibration | Use Case |
|---|---|---|---|---|
| Quick | up to 3 | No | No | Rapid scan |
| Standard | up to 6 | 1 arbitrated rebuttal call | No | Balanced review |
| Full | up to 8 | 1 call per involved persona | Yes | Complete analysis |

### 6. Quality Harness — 8-Dimension Scorecard

> **Read this before citing it.** The harness is a **post-hoc scorecard**, not a gate. On the web path `enable_evaluation` defaults to **false**, and when enabled it runs *after* the review is finished: it scores the report, it never blocks, filters, or re-runs a persona output. The eight thresholds live in `src/harness/thresholds.yaml` and the code ships them with `"threshold_note": "原型阈值，未经实证验证"` (prototype thresholds, not empirically validated).

| # | Dimension | What It Checks |
|---|---|---|
| 1 | **Persona Differentiation** | Are personas producing distinct perspectives? |
| 2 | **Input Grounding** | Is feedback anchored in actual materials? |
| 3 | **Actionability** | Are there concrete P0/P1/P2 fixes? |
| 4 | **Segment Conflict** | Are disagreements surfaced? |
| 5 | **Risk Detection** | Are critical risks identified? |
| 6 | **Ethical Persona Use** | No demographic stereotypes? |
| 7 | **Report Structure** | All required sections present? |
| 8 | **Calibration Honesty** | Findings framed as hypotheses, not predictions? |

### 7. Ethics Framework — Built-In Safeguards

| Principle | Implementation |
|---|---|
| **Identity-Behavior Decoupling** | Enforced **structurally, not by prompt instruction**: `persona_agent._minify_persona()` whitelists `CORE_FIELDS`, and `gender` / `age_range` / `region` are not on it. Those fields exist in the persona YAML but are stripped before the prompt is built, so the model is never given them to reason from — a property that survives paraphrase, model substitution, and long context in a way "please ignore demographics" does not. Residual risk stated honestly: the model may still infer demographics from `name` / `identity_summary` |
| **MBTI De-authorization** | MBTI modifies expression style only — never core judgment logic |
| **Evidence Tiering** | `[direct]` / `[inferred]` / `[gap]` — inferred capped at 40% |
| **No Fabrication** | Personas must not invent missing features, plot, multiplayer, monetization |
| **Mandatory Disclaimer** | Every report: "AI-generated synthetic review — not real user research" |
| **Stereotype Detection** | `EthicsService` with 10 built-in regex rules for demographic stereotyping, plus any extra rules loaded from the harness rule set at startup. The engine side (`src/harness/stereotype_judge.py`) adds an optional LLM review layer, **off by default** |

### 8. Evidence System — Three-Tier Annotation

| Tier | Label | Rule |
|---|---|---|
| **Direct** | `[direct]` | Directly quoted from input materials — must be locatable |
| **Inferred** | `[inferred]` | Reasonable inference from persona's behavioral profile — capped at 40% of total evidence |
| **Gap** | `[gap]` | Information not provided — must write "unspecified", never fabricate |

---

## Quick Start

### CLI Mode

```bash
# Install the package (registers the `audiencelens` command)
pip install -e .

# Set your API key first
# Linux/macOS
export ANTHROPIC_API_KEY=your-key
# Windows PowerShell: $env:ANTHROPIC_API_KEY="your-key"
# Windows CMD: set ANTHROPIC_API_KEY=your-key

# Run a review
audiencelens run synthetic-playtest steam_page_review examples/steam-page-sample/artifact.json
```

> ⚠️ **Without an API key, the CLI falls back to simulation mode**: all persona outputs are pre-built placeholder data with **zero review value**. It only verifies that the pipeline runs — never use simulated results for any decision. The CLI and all generated reports carry a prominent warning when this mode is active.

**Quality & experiment commands:**

```bash
# Stereotype-detection benchmark on a 50-case labeled set (offline regex layer)
audiencelens stereotype-eval
# Add the LLM review layer (requires ANTHROPIC_API_KEY)
audiencelens stereotype-eval --llm

# Persona-differentiation ablation: full vs no_behavior vs bare (requires API key)
audiencelens ablation concept_review examples/steam-page-sample/artifact.json --limit 4 --output ablation.json

# Compare one case against the same post-hoc human-research reference
audiencelens benchmark-compare --reference reference.json \
  --candidate audiencelens=audiencelens.json \
  --candidate single_prompt=single-prompt.json \
  --candidate expert_quick=expert-quick.json

# Scaffold a non-overwriting real pilot case
audiencelens benchmark-init --dir ./pilot-data --case-id studio-001

# Aggregate multiple projects with paired bootstrap confidence intervals
audiencelens benchmark-suite --manifest benchmark-suite.json --output benchmark-result.json
```

The benchmark tooling is implemented, but no parity claim is made until enough real projects and post-hoc human-research references have been collected. See [benchmark protocol](docs/benchmark-protocol.md).

The offline stereotype regex regression set currently reports 50/50 correct. This is a small, developer-expanded regression set—not evidence of 100% real-world generalization. See the [dated experiment record](docs/experiments/stereotype-regex-baseline-2026-07-16.md).

> Prefer not to install? Every command also runs via `python -m src.cli <command> ...` from the repo root.

### MCP Integration (let AI assistants call AudienceLens)

Expose the review engine as MCP tools so any MCP-capable assistant (Claude Desktop, Claude Code, Cursor, Cherry Studio…) can invoke it.

```bash
pip install -e ".[mcp]"
```

Then add to your client's MCP config (Claude Desktop example, `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "audiencelens": {
      "command": "audiencelens-mcp",
      "env": { "ANTHROPIC_API_KEY": "your-key" }
    }
  }
}
```

Exposed tools:

| Tool | Purpose |
|---|---|
| `list_task_types` | Discover the 10 review task types |
| `list_persona_packs` / `list_personas` | Inspect available persona panels |
| `run_synthetic_review` | Run a full review; `artifact` accepts a file path, JSON string, or raw text |

> Reviews use a real LLM. If the server has no `ANTHROPIC_API_KEY`, `run_synthetic_review` returns a clear instruction instead of worthless placeholder data (pass `allow_simulation=true` to deliberately dry-run the pipeline).

### Web Mode

```bash
# Backend
cd web/backend
pip install -r requirements.txt
python run.py

# Frontend (in another terminal)
cd web/frontend
npm install
npm run dev
```

### Docker

```bash
cd web
docker-compose up
```

### Programmatic API

```python
from runner.cli import run_panel
import json

with open('examples/steam-page-sample/artifact.json') as f:
    artifact = json.load(f)

result = run_panel(task_type='steam_page_review', artifact_bundle=artifact)
print(result['markdown'])       # Markdown report
print(result['report'])         # JSON report
print(result['calibration'])    # Calibration results
```

---

## Repository Structure

```
audiencelens/
├── src/
│   ├── runner/                        # Pipeline engine (7 stages)
│   │   ├── cli.py                     #   CLI entry + core orchestration
│   │   ├── panel_selector.py          #   Panel selection + dissenter guarantee
│   │   ├── evidence_precheck.py       #   Evidence coverage filtering
│   │   ├── persona_agent.py           #   Prompt rendering + output parsing
│   │   ├── validator.py               #   3-layer validation
│   │   ├── cross_exam.py              #   Controversy extraction + rebuttal round
│   │   ├── aggregator.py              #   Rule-driven report aggregation
│   │   └── calibration.py             #   Quality calibration check
│   ├── personas/                      # 10 persona packs (66 personas)
│   ├── presets/                       # Panel presets per task type
│   ├── schemas/                       # JSON Schema (persona, output, report)
│   ├── templates/                     # Prompt + report templates
│   └── config/                        # Aggregation rules + budget config
├── web/
│   ├── backend/                       # FastAPI backend
│   │   └── app/
│   │       ├── api/                   #   83 route handlers (v1 + platform + admin)
│   │       ├── services/              #   18 service modules
│   │       ├── models/                #   SQLAlchemy models
│   │       ├── schemas/               #   Pydantic schemas
│   │       └── websocket/             #   6 WebSocket event types
│   └── frontend/                      # React frontend
│       └── src/
│           ├── pages/                 #   18 pages + landing page
│           ├── components/            #   7 components
│           └── store/                 #   3 Zustand stores
├── tests/                             # Engine test suite (see Testing)
├── examples/                          # 7 sample artifacts
├── docs/                              # Documentation
├── requirements.txt
└── pytest.ini
```

---

## Testing

```bash
# Engine suite
pip install -r requirements.txt
python -m pytest tests/ -q

# Platform suite
cd web/backend && python -m pytest tests/ -q
```

**756 automated tests pass, 1 skipped** — 453 engine (`tests/`) + 303 platform
(`web/backend/tests/`), measured 2026-07. The counts move with development; run the
two commands above rather than trusting this number. The 1 skipped test is skipped,
not passing — it is counted separately on purpose.

---

## Roadmap

| Version | Focus | Status |
|---|---|---|
| v0.1 | MVP — 16 personas, 6 task types, CLI runner, controversy extraction, 3-layer validation | Done |
| v0.2 | Harness Edition — 8-dim scorecard, ethics service, expanded persona set, Web UI | Done |
| **v0.3** | **66 personas / 10 packs, 14 task types, SaaS platform (auth / quota / admin / CDK), multimodal input, plus one live cross-examination rebuttal round with code-adjudicated vote changes** | **Current** |
| v0.4 | **Evaluate the rebuttal round, then extend it** — A/B the three tiers (§3) to find out whether rebuttal improves a review at all, calibrate θ_change against data, then add rounds 2–3 with cross-round state so consensus evolution and tipping points become computable | Planned — see the §3 caveat for what does not exist today |
| v0.5 | Human-parity benchmark with real cohort data (tooling exists, cohort data pending) | Planned |
| v1.0 | Big-Five replacement for MBTI, dynamic panel generation, cost-aware model routing | Planned |

---

## Disclaimer

**Synthetic audience feedback is not a substitute for real user research.** Use it for:
- Blind-spot detection
- Hypothesis generation
- Pre-screening before real testing
- Critique preparation
- Next-test planning

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Made by 熵呓工作室

---

<a id="中文"></a>

## 概述

AudienceLens 是一个**全栈合成观众评审系统**，模拟多元玩家人格对游戏、产品和创意项目进行评审——在投入真人测试资源之前。

与直接问 ChatGPT 不同，AudienceLens：
1. **隔离运行**多个行为驱动人格（10 个 Pack 共 66 个人格）
2. 从人格输出中提取 **top-3 争议点**，并对它们跑**一轮真实的反驳**——`standard` 档是仲裁式、`full` 档逐人格、`quick` 档不跑（每档到底做了什么见 §3）
3. 强制**伦理约束**——刻板印象检测、证据三级标注（`inferred` 硬上限 40%）、强制免责声明
4. 提供可选的 **8 维质量打分卡**——事后打分、默认关闭；它给已完成的报告打分，不拦截、不重跑

> **AudienceLens 不能替代真实用户研究。** 它是一个预筛与压力测试工具，用于在投入真人测试资源之前发现最明显的问题。

---

## 功能分类

### 1. Runner 引擎 — 流水线架构

核心执行引擎是 `src/runner/` 中的7阶段流水线：

| 阶段 | 模块 | 功能 |
|---|---|---|
| **面板选择** | `panel_selector.py` | 按任务类型选择人格；保证反对者存在（缺P15自动追加） |
| **证据预检** | `evidence_precheck.py` | 过滤证据覆盖度 <30% 的人格 |
| **人格执行** | `persona_agent.py` | 渲染五段式 Prompt（人格卡→MBTI边界→身份-行为解耦→任务→证据规则）；解析结构化输出 |
| **三层校验** | `validator.py` | Schema校验(Draft7Validator) → 角色一致性(must_comment_on≥80%, inferred≤40%) → 证据接地(幻觉<30%) |
| **交叉质询** | `cross_exam.py` | 提取 top-3 争议点（按 severity 方差排序，语义去重 + SequenceMatcher 回退）；配对立场最对立的人格，对模型跑**一轮反驳**。`mode` 取 `derived_summary` / `moderated_rebuttal` / `multi_agent_rebuttal` 三者之一，只有后两种时 `is_live_debate` 才为真——见 §3 |
| **规则聚合** | `aggregator.py` | 计算共识、分歧、优先修复项（severity×人格权重×影响人数）；发布风险评估 |
| **校准检查** | `calibration.py` | 角色一致性率、视角覆盖度(Jaccard≥0.3)、幻觉率、稳定性 |

### 2. 人格系统 — 12轴行为向量

人格由**行为向量**定义，而非人口统计标签。SCOPE研究表明人口统计仅解释1.5%的行为方差。

| 行为轴 | 说明 |
|---|---|
| `patience` | 时间容忍度（慢热内容能否接受） |
| `genre_literacy` | 领域知识（是否熟悉这类游戏） |
| `novelty_seeking` | 创新偏好（喜欢尝新还是守成） |
| `risk_tolerance` | 不确定性容忍（EA/众筹是否放心） |
| `social_influence` | 社会证据依赖（看重评价/社区口碑） |
| `completion_drive` | 完成驱动（会不会肝全成就） |
| `price_sensitivity` | 价格敏感度 |
| `emotional_engagement` | 情感投入度 |
| `agency_preference` | 能动性偏好（喜欢引导还是自由探索） |
| `tolerance_for_ambiguity` | 模糊容忍度 |
| `platform_loyalty` | 平台忠诚度 |
| `criticism_style` | 批评风格 |

**10 个人格 Pack（共 66 个人格）：**

| Pack | 文件 | 数量 | 人格 |
|---|---|---|---|
| 游戏核心 | `game-core.yaml` | 16 | 独立核心操作者、系统推演党、挑战猎人、剧情沉浸党、收集完成党、视觉氛围党、碎片手游党、首次新手、治愈社交分享者、Steam 心愿单浏览者、TapTap 口碑侦察、主播创作者、发行侦察、价格敏感买家、毒舌怀疑者、竞品忠诚老兵 |
| 竞技电竞 | `competitive-esport.yaml` | 5 | 冲分玩家、速通挑战者、团队协调者、电竞观众、Mod 竞技者 |
| 家庭休闲 | `family-casual.yaml` | 5 | 亲子共创者、派对社交、治愈放松、怀旧复古、代际桥梁 |
| 独立创意 | `indie-creative.yaml` | 5 | 独立品鉴者、创意探索者、文化消费者、独立叙事设计者、独立节奏狂 |
| 移动免费 | `mobile-f2p.yaml` | 7 | 碎片鲸鱼、白嫖猎人、社交驱动手游、二次元审美、超休闲路人、月卡党、广告容忍者 |
| VR沉浸 | `vr-immersive.yaml` | 4 | VR 晕动敏感、临场感追求者、VR 健身玩家、社交 VR 居民 |
| 无障碍 | `accessibility.yaml` | 4 | 色觉辅助、认知负荷敏感、运动无障碍、听觉无障碍 |
| 教育严肃 | `educational-serious.yaml` | 4 | 教师评估者、家长守门人、终身学习者、特殊需求学习者 |
| 通用消费 | `general-consumer.yaml` | 8 | 价值敏感买家、怀疑型评测者、B2B 决策者、首次使用者、资深用户、口碑传播者、无障碍用户、竞品转换者 |
| 创业评审 | `startup-panel.yaml` | 8 | 天使投资人、VC 投资经理、行业分析师、技术尽调工程师、早期尝鲜客户、孵化器筛选人、单位经济怀疑者、专职唱反调 |

> 非游戏人格集中在最后两个 Pack（66 个中的 16 个）。**不存在红队人格包**——"红队"是套在既有面板上的技能提示，不是一组人格。

### 3. 交叉质询 — 争议点提取 + 一轮真实反驳

传统"让分歧最大的两个人格互问"容易变成极端对立的无意义争吵。AudienceLens 先把辩论收窄到真正有分歧的那几个点，再让人格为它们辩护：

1. **争议提取** — 从所有人格输出中提取 top-3 争议点，按 severity 方差排序，语义去重（`similarity.py`）+ SequenceMatcher 回退。所有人本来就一致的点会在发调用之前被滤掉——系统不会为了"看起来在干活"而制造一场对立
2. **对立立场配对** — 对每个争议点，挑出立场最对立的两个人格，把各自的原话作为正反论据摆出来，编号 `A1` / `B1`
3. **反驳轮次** — 把这些论据发回给模型，收回每一方的反驳，外加更新后的立场与置信度
4. **改票由代码判定** — 只有立场文字确实变了**且** `|Δconfidence| ≥ θ` 时才记为一次改票，`θ` 从 `src/config/aggregation-rules.yaml` 读取（现在是 0.15）。模型自己声称"我改主意了"不算数。被否决的声称保留在 `suppressed_changes` 里并附原因
5. **诚实标注** — `mode` 取 `derived_summary` / `moderated_rebuttal` / `multi_agent_rebuttal`，只有确实解析到反驳时 `is_live_debate` 才为真；随报告下发的 `limitation` 字段会用白话写清这次跑的是哪一档

**三档并不等价，这个区别比它们共用的那个名字更重要：**

| 模式 | 反驳调用次数 | 实际发生了什么 |
|---|---|---|
| `quick` | 0 | 完全不跑 |
| `standard` | 1 | **一轮仲裁式反驳。** 一次调用从主持人视角写完双方的反驳。它确实是一轮真反驳；但它**不是**每个人格各自独立发言 |
| `full` | 每位涉事人格各 1 次 | **真多智能体反驳。** 每位人格带着自己的人格卡被重新调用，对手论据已被剥掉署名 |

**对手匿名。** 提示词模板里根本没有人格名槽位，论据只用编号指代，渲染层还会把人格名从论据*正文*里洗掉。范围要说准：已保证的是**任何人格都看不到另一位人格的身份**。`full` 档在引擎链路上，人格仍会拿到自己的卡（含自己的名字），好让它用自己的口吻立论；Web v1 链路连这一份也剥掉了。

**反驳调用失败时**不会被吞：`mode` 回落 `derived_summary`，原因写进 `failures[]` 与报告的 `limitation`，评审其余部分照常产出。反驳的 token 与成本会计入评审总账，并在 `cost_summary["cross_exam"]` 里单列。

> **仍然只有设计、没有实现——请勿当作能力引用：** 第二、三轮辩论，收敛后提前终止，全员说服力评分（每个点只有最对立的两位人格参与，任何地方都不计算 1–5 的说服力分），共识演化追踪，临界点检测。`consensus_strength`、`converging`、`oscillating`、`tipping_point`、`cascade_point` 在源码里 0 处命中。**而且已实现的这一轮没有被评估过：** 我们没有任何测量能表明它让评审变好了；θ=0.15 是一个工程判断值，它现在有后果，但仍未经验证。
>
> **一个必须说清的例外，免得反过来也失真。** 上面说的是 **Python 引擎**——也就是 CLI、Python 包、MCP Server、托管 Web 应用背后的那条链路，绝大多数用户碰到的就是它。**技能包**（`.claude/skills/`、`.trae/skills/`）是另一条链路：在那里由 LLM 编码代理读取 `SKILL.md` 并**自己执行** Phase 5，包括说服力评分和 θ=0.15 的立场更新。所以技能链路可能比引擎做得更多——但那是一个代理在遵循 Markdown 指令，**没有任何代码强制它、没有 schema 校验它、也没有测试覆盖它**，不确定、不可保证。请勿拿技能链路给引擎背书，反之亦然。

### 4. 任务类型 — 14 种评审场景

| 任务类型 | 适用场景 |
|---|---|
| `steam_page_review` | 商店页信息架构、视觉传达、信任信号 |
| `demo_first_play` | 上手摩擦、手感、首15分钟体验 |
| `concept_review` | 核心循环、差异化、可行性 |
| `monetization_review` | 定价、付费边界、价值感知 |
| `looking_for_party_post` | 社区文案、传播性、社交吸引力 |
| `update_announcement_review` | 版本日志、信任强化、留存信号 |
| `devlog_review` | 开发叙事、社区参与 |
| `kickstarter_review` | 众筹页面、奖励层级、支持者信任 |
| `localization_review` | 翻译质量、文化适配 |
| `discord_community_review` | 社区管理、语气、参与模式 |
| `product_feedback_review` | 通用产品反馈的收集与解读（非游戏向） |
| `pricing_page_review` | 价格档位、价值传达、信任信号（非游戏向） |
| `onboarding_review` | 首次使用体验、激活环节的摩擦（非游戏向） |
| `pitch_review` | 创业 BP / 路演材料 / 申报书，从投资与尽调视角评审 |

唯一事实源是 `src/runner/task_types.py::VALID_TASK_TYPES`；不在该列表里的一律 400 拒绝。

### 5. Web应用 — 全栈实现

| 层 | 技术栈 | 核心功能 |
|---|---|---|
| **后端** | FastAPI + SQLite + WebSocket | 83 个路由处理函数（`grep -c '^@router\.' app/api/*.py`，2026-07 实测）、6 种实际发出的 WebSocket 事件、18 个服务模块 |
| **前端** | React 19 + TypeScript + Tailwind + shadcn/ui + Recharts | 18 个页面 + 落地页、7 个组件、3 个 Zustand Store |
| **服务** | `app/services/` 下 18 个模块（密钥 / 配额 / 任务 / 意图 / 留档 / CDK / 对话 / 邮件 / 套餐 / 后台设置 / 审计日志 / 认证令牌 / 伦理 / 评估 / 报告门禁 / 评审 / 用户数据 / 校验），外加定义在 `services/__init__.py` 里的 `PersonaService` / `ReviewService` / `MaterialExtractor` | Anthropic 原生 SDK + OpenAI 兼容 HTTP（OpenAI / DeepSeek / Kimi / 通义千问 / 智谱 GLM / Ollama 预设）、刻板印象检测、伦理合规 |
| **实时** | WebSocket（实际发出 6 种事件） | 实时评审进度、逐人格结果展示 |
| **部署** | Docker Compose | 前端(Nginx) + 后端(Uvicorn) |

**3 种评审模式**（`src/runner/cli.py` 的 `MODE_CONFIG`）：

| 模式 | 人格数 | 交叉质询 | 校准 | 适用场景 |
|---|---|---|---|---|
| 快速 | 最多 3 | 否 | 否 | 快速扫描 |
| 标准 | 最多 6 | 1 次仲裁式反驳调用 | 否 | 均衡评审 |
| 完整 | 最多 8 | 每位涉事人格各 1 次 | 是 | 完整分析 |

### 6. 质量 Harness — 8 维打分卡

> **引用它之前请先读这段。** Harness 是**事后打分卡，不是门控**。Web 链路上 `enable_evaluation` 默认为 **false**，即便开启也是在评审**跑完之后**运行：它给报告打分，从不拦截、过滤或重跑任何人格输出。八个阈值在 `src/harness/thresholds.yaml`，代码里随分数一起下发 `"threshold_note": "原型阈值，未经实证验证"`。

| # | 维度 | 检查内容 |
|---|---|---|
| 1 | **人格差异化** | 人格是否产出不同视角？ |
| 2 | **输入依据** | 反馈是否锚定在实际材料上？ |
| 3 | **可操作性** | 是否有具体的P0/P1/P2修复项？ |
| 4 | **群体冲突** | 分歧是否被暴露？ |
| 5 | **风险检测** | 关键风险是否被识别？ |
| 6 | **伦理人格使用** | 是否无人口统计刻板印象？ |
| 7 | **报告结构** | 所有必需段落是否完整？ |
| 8 | **校准诚实度** | 发现是否定位为假设而非预测？ |

### 7. 伦理框架 — 内置安全机制

| 原则 | 实现 |
|---|---|
| **身份-行为解耦** | **从结构上切断，而不是靠提示词叮嘱**：`persona_agent._minify_persona()` 按 `CORE_FIELDS` 白名单裁剪，`gender` / `age_range` / `region` 不在白名单里。这三个字段在人格 YAML 里确实存在，但在拼 Prompt 之前就被剥掉了——模型根本拿不到它们可推理。这个性质能扛住改写、换模型、长上下文，"请忽略人口统计"这类指令扛不住。残余风险如实写明：模型仍可能从 `name` / `identity_summary` 反推出人口统计信息 |
| **MBTI去权** | MBTI仅修饰表达风格——不推导核心判断逻辑 |
| **证据分级** | `[direct]` / `[inferred]` / `[gap]` — 推断证据上限40% |
| **禁止脑补** | 人格不得编造缺失的功能、剧情、联机或商业化细节 |
| **强制免责** | 每份报告包含"AI生成的合成评审——非真实用户研究" |
| **刻板印象检测** | `EthicsService` 内置 10 条人口统计刻板印象正则规则，另可在启动时从 harness 规则集加载附加规则。引擎侧（`src/harness/stereotype_judge.py`）另加一层可选的 LLM 复审，**默认关闭** |

### 8. 证据系统 — 三级标注

| 级别 | 标签 | 规则 |
|---|---|---|
| **直接** | `[direct]` | 直接引用输入材料——必须可定位 |
| **推断** | `[inferred]` | 基于人格行为画像的合理推断——不超过总证据的40% |
| **缺口** | `[gap]` | 信息未提供——必须写"未指定"，禁止编造 |

---

## 快速开始

### CLI模式

```bash
# 安装本包（注册 `audiencelens` 命令）
pip install -e .

# 先设置 API Key
# Linux/macOS
export ANTHROPIC_API_KEY=your-key
# Windows PowerShell: $env:ANTHROPIC_API_KEY="your-key"
# Windows CMD: set ANTHROPIC_API_KEY=your-key

# 运行评审
audiencelens run synthetic-playtest steam_page_review examples/steam-page-sample/artifact.json
```

> ⚠️ **未设置 API Key 时，CLI 会退回模拟模式**：所有人格输出均为预制占位数据，**没有任何评审价值**，仅用于验证流水线能否跑通。请勿将模拟结果用于任何决策——该模式下 CLI 与所有生成的报告都会带有醒目警告。

**质量与实验命令：**

```bash
# 刻板印象检测评测：30条标注集（离线正则层）
audiencelens stereotype-eval
# 加上 LLM 复审层（需 ANTHROPIC_API_KEY）
audiencelens stereotype-eval --llm

# 人格分化消融实验：full vs no_behavior vs bare（需 API Key）
audiencelens ablation concept_review examples/steam-page-sample/artifact.json --limit 4 --output ablation.json
```

> 不想安装？所有命令也可在仓库根目录用 `python -m src.cli <命令> ...` 运行。

### MCP 接入（让 AI 助手自己调用 AudienceLens）

把评审引擎暴露为 MCP 工具，任何支持 MCP 的助手（Claude 桌面版、Claude Code、Cursor、Cherry Studio 等）都能直接调用。

```bash
pip install -e ".[mcp]"
```

然后在客户端的 MCP 配置里添加（以 Claude 桌面版 `claude_desktop_config.json` 为例）：

```json
{
  "mcpServers": {
    "audiencelens": {
      "command": "audiencelens-mcp",
      "env": { "ANTHROPIC_API_KEY": "你的-key" }
    }
  }
}
```

暴露的工具：

| 工具 | 作用 |
|---|---|
| `list_task_types` | 列出 10 种评审任务类型 |
| `list_persona_packs` / `list_personas` | 查看可用的人格面板 |
| `run_synthetic_review` | 运行完整评审；`artifact` 支持文件路径 / JSON 字符串 / 纯文本 |

> 评审使用真实 LLM。若 server 未配置 `ANTHROPIC_API_KEY`，`run_synthetic_review` 会返回明确提示而非无价值的占位数据（如需空跑流水线可传 `allow_simulation=true`）。

### Web模式

```bash
# 后端
cd web/backend
pip install -r requirements.txt
python run.py

# 前端（另一个终端）
cd web/frontend
npm install
npm run dev
```

### Docker

```bash
cd web
docker-compose up
```

### 程序化调用

```python
from runner.cli import run_panel
import json

with open('examples/steam-page-sample/artifact.json') as f:
    artifact = json.load(f)

result = run_panel(task_type='steam_page_review', artifact_bundle=artifact)
print(result['markdown'])       # Markdown 报告
print(result['report'])         # JSON 报告
print(result['calibration'])    # 校准结果
```

---

## 仓库结构

```
audiencelens/
├── src/
│   ├── runner/                        # 流水线引擎（7阶段）
│   │   ├── cli.py                     #   CLI入口 + 核心编排
│   │   ├── panel_selector.py          #   面板选择 + 反对者保证
│   │   ├── evidence_precheck.py       #   证据覆盖度过滤
│   │   ├── persona_agent.py           #   Prompt渲染 + 输出解析
│   │   ├── validator.py               #   三层校验
│   │   ├── cross_exam.py              #   争议点提取 + 反驳轮次
│   │   ├── aggregator.py              #   规则驱动报告聚合
│   │   └── calibration.py             #   质量校准检查
│   ├── personas/                      # 10个人格Pack（66个人格）
│   ├── presets/                       # 各任务类型面板预设
│   ├── schemas/                       # JSON Schema（人格、输出、报告）
│   ├── templates/                     # Prompt + 报告模板
│   └── config/                        # 聚合规则 + 预算配置
├── web/
│   ├── backend/                       # FastAPI 后端
│   │   └── app/
│   │       ├── api/                   #   83个路由处理函数（v1 + 平台 + 后台）
│   │       ├── services/              #   18个服务模块
│   │       ├── models/                #   SQLAlchemy模型
│   │       ├── schemas/               #   Pydantic模型
│   │       └── websocket/             #   6种WebSocket事件
│   └── frontend/                      # React 前端
│       └── src/
│           ├── pages/                 #   18个页面 + 落地页
│           ├── components/            #   7个组件
│           └── store/                 #   3个Zustand Store
├── tests/                             # 引擎测试套件（见「测试」一节）
├── examples/                          # 7个示例素材
├── docs/                              # 文档
├── requirements.txt
└── pytest.ini
```

---

## 测试

```bash
# 引擎套件
pip install -r requirements.txt
python -m pytest tests/ -q

# 平台套件
cd web/backend && python -m pytest tests/ -q
```

**756 项自动化测试通过、1 项 skipped** —— 引擎 453（`tests/`）+ 平台 303（`web/backend/tests/`），2026-07 实测。这个数字会随开发变动，请以上面两条命令的实际输出为准。那 1 项是 **skipped，不是通过**，所以单独列出、不并进"全绿"。

---

## 路线图

| 版本 | 重点 | 状态 |
|---|---|---|
| v0.1 | MVP — 16个人格、6种任务类型、CLI引擎、争议点提取、三层校验 | 已完成 |
| v0.2 | Harness版 — 8维打分卡、伦理服务、人格集扩充、Web UI | 已完成 |
| **v0.3** | **66人格 / 10个Pack、14种任务类型、SaaS 平台（认证 / 配额 / 后台 / CDK）、多模态输入，外加一轮真实的交叉质询反驳、改票由代码判定** | **当前** |
| v0.4 | **先评估这轮反驳，再扩展它**——A/B 三档（见 §3）看反驳到底有没有让评审变好、用数据校准 θ_change，然后补上第 2–3 轮与跨轮状态，使共识演化与临界点变得可计算 | 计划中——今天不存在什么，见 §3 的说明 |
| v0.5 | 真人对照 benchmark（工具链已就绪，真人数据待积累） | 计划中 |
| v1.0 | Big-Five替代MBTI、动态面板生成、成本感知模型路由 | 计划中 |

---

## 免责声明

**合成观众反馈不能替代真实用户研究。** 适用于：
- 盲点检测
- 假设生成
- 真实测试前的预筛选
- 评审准备
- 下一步测试规划

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

## 朔纪团队出品
