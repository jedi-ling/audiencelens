---
title: "AudienceLens: A Multi-Agent Cross-Examination Framework for Synthetic Audience Review"
authors:
  - name: Ling Yuanyi
    affiliation: Independent
abstract: |
  Traditional user research suffers from high cost, slow turnaround, and poor reproducibility. Recent advances in LLM-based persona simulation offer a promising alternative by generating synthetic user interviews at scale, but they also make it cheap to produce plausible-sounding "user feedback" that is grounded in nothing. We present AudienceLens, an open-source prototype for synthetic audience review whose implemented contributions are constraint mechanisms rather than simulation fidelity: (1) three-level evidence provenance — every claim is labelled `direct`, `inferred`, or `gap`, and a validator rejects any persona output whose inferred share exceeds 40%; (2) structural identity-behavior decoupling — demographic fields (gender, age, region) are removed from the persona payload before it reaches the model, so demographic-causal reasoning is unavailable rather than merely discouraged; (3) an 8-dimension Harness rubric whose thresholds live in a single configuration file read at runtime and ship with an explicit "prototype threshold, not empirically validated" annotation; (4) a **single-round** cross-examination protocol that does issue live rebuttal calls, in two tiers — one moderated rebuttal call in `standard` mode, per-persona re-invocation in `full` mode — with opponent identity withheld (arguments are addressed only by anonymous IDs), stance changes adjudicated **in code** by comparing pre- and post-rebuttal (stance, confidence) against a threshold $\theta_{\text{change}} = 0.15$ that is now read from configuration, and mode labelling that falls back to `derived_summary` and records the reason when a rebuttal call fails. We still specify, but have not implemented, the full three-round protocol with early termination, persuasion scoring, consensus-evolution tracking, and tipping-point detection. The release ships 72 behavior-driven personas across 11 packs and 14 task types. We discuss limitations including the absence of real-world parity studies, and outline a roadmap covering both the unimplemented mechanisms and their empirical validation.
keywords: [multi-agent systems, synthetic audience, cross-examination, persona simulation, LLM evaluation, AI ethics]
---

# AudienceLens: A Multi-Agent Cross-Examination Framework for Synthetic Audience Review

## Abstract

Traditional user research suffers from high cost, slow turnaround, and poor reproducibility. Recent advances in LLM-based persona simulation—exemplified by SyntheticUsers and similar platforms—offer a promising alternative by generating synthetic user interviews at scale. They also make it cheap to produce plausible-sounding "user feedback" that is grounded in nothing, which is the failure mode this work targets.

We present **AudienceLens**, an open-source prototype for synthetic audience review. Its implemented contributions are constraint mechanisms rather than simulation fidelity:

1. **Three-level evidence provenance with a hard cap.** Every claim in a persona output is labelled `direct`, `inferred`, or `gap`, and a validator rejects any output whose `inferred` share exceeds 40%.
2. **Structural identity-behavior decoupling.** Demographic fields (gender, age, region) are removed from the persona payload before it is serialised into the prompt, so demographic-causal reasoning is *unavailable to the model*, not merely discouraged by instruction.
3. **An 8-dimension Harness evaluation rubric** whose thresholds live in a single configuration file that the code reads at runtime and that ships with an explicit "prototype threshold, not empirically validated" annotation.
4. **A single-round cross-examination protocol with code-adjudicated stance changes.** Personas are re-invoked to rebut opposing arguments, and the rebuttal is real: a model call is issued, its output is parsed, and a stance change is recorded only when code confirms that the stance text changed *and* $|\Delta c| \geq \theta_{\text{change}}$, with $\theta_{\text{change}}$ read from `src/config/aggregation-rules.yaml`. Model self-reports of having changed position are not trusted. Two tiers ship: `standard` mode performs **one moderated rebuttal call** covering all controversy points, and `full` mode re-invokes **each involved persona separately** (true multi-agent rebuttal). `quick` mode does not run cross-examination at all.

We additionally **specify, but have not implemented**, the remainder of the protocol: the full three-round structure with early termination on convergence, persuasion scoring across the whole panel, consensus-evolution classification, and tipping-point detection. What executes today is one rebuttal round between the two most-opposed personas per controversy point, not a three-round panel-wide debate. Section 4.6 states the implementation status of each specified mechanism.

A fourth mechanism sits between these two categories and we state its boundary precisely. **The cross-examination protocol now executes a live rebuttal round.** In `standard` mode the system issues one moderated rebuttal call covering all controversy points; in `full` mode each persona involved in a controversy is re-invoked separately with its own identity card and the opponent's argument stripped of any attribution. Stance changes are decided by code — the stance text must actually differ *and* the confidence delta must reach $\theta_{\text{change}} = 0.15$, read from configuration — and a model claiming to have changed its mind is not sufficient. What remains unimplemented is the *rest* of the specification: the second and third rounds, early termination on convergence, panel-wide persuasion scoring, consensus-evolution classification, and tipping-point detection. The runtime distinguishes the three states it can be in (`derived_summary`, `moderated_rebuttal`, `multi_agent_rebuttal`) and falls back to the first, with the failure recorded, whenever a rebuttal call fails or its output cannot be parsed.

The release ships 72 behavior-driven personas across 11 YAML packs and 14 task types. We propose the identity-behavior decoupling principle and describe AI Act–informed design considerations. We discuss limitations including the absence of real-world parity studies, and outline a roadmap covering both the unimplemented mechanisms and their empirical validation. Empirical validation with real users remains future work for *all* components, implemented and specified alike.

## 1. Introduction

User research is the cornerstone of product development, yet it remains one of the most resource-intensive activities in the design cycle. Moderated usability testing means recruiting, scheduling and compensating participants, and its small-sample results are hard to replicate across sessions (Nielsen, 1994; Lazar et al., 2017). Focus groups, while efficient for gathering diverse perspectives, are susceptible to groupthink, anchoring bias, and the influence of dominant voices (Morgan, 1997). Survey-based methods scale more easily but sacrifice depth for breadth, producing statistical aggregates that obscure individual reasoning.

The emergence of large language models (LLMs) has opened a new frontier: *synthetic user research*. Commercial platforms such as SyntheticUsers claim high alignment with real users, but independent validation remains limited. Park et al. (2023) showed that generative agents can exhibit believable social behaviors in sandbox environments. Horton et al. (2023) proposed treating LLMs as *Homo silicus*—implicit computational models of humans that can be placed in economic experiments. Argyle et al. (2023) demonstrated that a single LLM can simulate diverse subpopulations with surprising fidelity, capturing variation in attitudes and behaviors across demographic groups.

However, these approaches share a critical limitation: they treat synthetic user simulation as a *monologue* rather than a *dialogue*. Each persona responds independently, without exposure to opposing viewpoints, without the opportunity to revise their position, and without any mechanism for detecting when consensus is genuine versus superficial. This is fundamentally different from how real focus groups operate—where participants challenge each other's assumptions, shift their views in response to compelling arguments, and sometimes converge on unexpected positions.

We present **AudienceLens**, an open-source prototype for synthetic audience review. We separate what the current release (v0.3.0) actually executes from what it only specifies, because that distinction determines what a reader can rely on.

**Implemented contributions.**

1. **Three-level evidence provenance with a hard inferred-evidence cap.** Every claim in a persona output carries a `direct` / `inferred` / `gap` label, and a validator rejects outputs whose `inferred` share exceeds 40% (`src/runner/validator.py`). This is enforced in code, not requested in a prompt.

2. **Structural identity-behavior decoupling.** Demographic attributes are stripped from the persona record before serialisation: only a fixed `CORE_FIELDS` allowlist (behavior profile, motivations, decision rules, quit/continue triggers, first-scan focus) is injected into the prompt. The model never sees gender, age, or region, so demographic-causal reasoning is structurally unavailable rather than merely prohibited. A two-layer stereotype detector (regex first pass, plus an optional LLM judge when an API key is configured) inspects the output as a second line of defence.

3. **An 8-dimension Harness evaluation rubric** with thresholds declared in a single runtime-read configuration file (`src/harness/thresholds.yaml`) that ships with a machine-readable "prototype threshold, not empirically validated" annotation. We describe it as a *post-hoc scorecard, not a gate*: it is disabled by default, runs after a review completes, and does not filter, block, or re-run any persona output.

4. **An open-source implementation** (MIT) with CLI, Python API, MCP server, web, and Docker entry points, shipping 72 behavior-driven personas across 11 YAML packs and 14 task types, with presets for six model providers.

**Design contribution, partially implemented.**

5. **A cross-examination protocol with confidence-gated, code-adjudicated stance revision.** One rebuttal round executes, in two tiers (Section 3.3): `standard` performs a single moderated rebuttal call, `full` re-invokes each involved persona. Vote changes and change provenance are populated from parsed model output but *decided* in Python — the stance text must change and $|\Delta c| \geq \theta_{\text{change}}$ must hold, with $\theta_{\text{change}} = 0.15$ read from `src/config/aggregation-rules.yaml` (Section 3.4). Claimed changes that fail the gate are retained separately as `suppressed_changes` rather than discarded silently.

**Design contributions still specified but not implemented.**

6. **The remaining two rounds of the three-round structure**, early termination on convergence, and panel-wide persuasion scoring (Section 3.3). What runs is one rebuttal round between the two most-opposed personas per controversy point; the other panel members are not asked to score arguments.

7. **Consensus-evolution classification into four patterns and tipping-point detection** (Sections 3.5–3.6). Neither exists: the identifiers `consensus_strength`, `converging`, `oscillating`, `tipping_point`, and `cascade_point` appear nowhere under `src/`, and the system holds no cross-round state to compare. Section 4.6 records this per mechanism.

**Normative contribution.**

8. **The identity-behavior decoupling principle**: the position that persona judgments must be causally traceable to behavioral profiles and motivations, never to demographic attributes (gender, age, region, MBTI). Contribution 2 is its implemented enforcement.

The remainder of this paper is organized as follows: Section 2 reviews related work; Section 3 presents our method, including both implemented and specified-only mechanisms; Section 4 details the implementation and, in Section 4.6, its status against the specification; Section 5 describes the evaluation framework; Section 6 discusses ethical considerations; Section 7 addresses limitations and future work; and Section 8 concludes.

## 2. Related Work

### 2.1 Generative Agents and Persona Simulation

The foundation of synthetic audience research lies in the ability of LLMs to adopt and maintain consistent personas. Park et al. (2023) introduced generative agents that inhabit a sandbox town, exhibiting emergent social behaviors including relationship formation, event coordination, and information diffusion. Their architecture—comprising memory streams, reflection, and planning—demonstrated that LLM-based agents can maintain behavioral coherence over extended interactions.

Argyle et al. (2023) showed that LLMs can simulate diverse subpopulations when conditioned on demographic profiles, capturing inter-group variation in attitudes and opinions. Their "silicon samples", built by conditioning the model on sociodemographic backstories from real survey participants, suggested that LLMs could serve as inexpensive proxies for human respondents; they named the property that makes this work "algorithmic fidelity" and treated it as something to be demonstrated for each use rather than assumed.

Horton et al. (2023) extended this line of work to economics, proposing that LLMs be treated as *Homo silicus*—implicit computational models of humans that can be given endowments, information and preferences and then placed in economic scenarios. They suggested piloting experimental designs in silico before committing to costly human studies, while stressing that any particular Homo silicus is wrong, even if useful.

### 2.2 Synthetic User Research

Commercial synthetic user research platforms have emerged to address the cost and speed limitations of traditional methods. **SyntheticUsers** (2024) is a commercial platform offering AI-moderated interviews with synthetic participants. Commercial platforms such as SyntheticUsers claim high alignment with real users, but independent validation remains limited. Liu et al. (2026) found that simulated users struggle to reproduce the communication frictions real users bring to multi-turn conversations, so evaluations built on them can look better than real performance.

**Outset** takes a hybrid approach, using AI to moderate real human interviews at scale. While this preserves the authenticity of human responses, it does not address the cost and speed limitations that motivate synthetic approaches. **Yabble** offers AI-powered survey analysis but relies on single-turn interactions with demographic-tagged personas, which risks reinforcing stereotypes rather than capturing genuine behavioral diversity.

These platforms share three limitations: (1) no cross-examination between personas; (2) no mechanism for stance revision; and (3) no systematic quality evaluation framework for synthetic review outputs. AudienceLens addresses (3) with an implemented evaluation rubric (Section 3.7). It now addresses (1) and (2) with one implemented rebuttal round and a code-adjudicated stance-revision gate (Sections 3.3–3.4), while the multi-round and consensus-tracking parts of the specification remain unimplemented (Sections 3.5–3.6, status in Section 4.6).

### 2.3 Multi-Agent Debate

Du et al. (2024) demonstrated that multi-agent debate can improve factuality and reasoning in language models. In their framework, several model instances each propose an answer, then read each other's responses and revise their own over several rounds until they reach a common answer. This improved performance on mathematical reasoning and factual question-answering tasks, suggesting that interaction between instances can surface errors that single-agent generation misses.

Liang et al. (2024) targeted a failure mode of self-reflection they call Degeneration-of-Thought—once a model is confident in an answer, it stops producing new ideas—with a framework in which agents argue "tit for tat" and a judge manages the debate. Chan et al. (2024) built ChatEval, a multi-agent referee team that discusses and evaluates generated text, and found that giving every agent the same role description degrades performance.

Wu et al. (2025) ran a controlled study of multi-agent debate on logic puzzles with verifiable answers. Reasoning strength and group diversity were the dominant drivers of debate success; structural parameters such as debate order or confidence visibility gave limited gains; and majority pressure suppressed independent correction.

AudienceLens builds on these insights with a structured rebuttal protocol designed for the audience review domain, where the goal is not to find a single correct answer but to map the landscape of perspectives and identify areas of genuine disagreement. One rebuttal round is implemented and executes real model calls (Section 3.3); the multi-round debate structure and the consensus-tracking layer described in Sections 3.5–3.6 remain specification only (Section 4.6). Two limits on how this should be read. First, one round of rebuttal is not the multi-round debate studied by Du et al. (2024) or Wu et al. (2025), and their findings do not transfer to it. Second, we have run no experiment on our own protocol either — Section 5.0 states the design of the study that would be needed. Readers should therefore treat the debate literature cited above as motivation for our design, not as evidence about AudienceLens's outputs.

### 2.4 AI Ethics in Persona Generation

The ethical dimensions of synthetic persona generation have received increasing attention. Prior UX research has long argued that behavior, goals, and context are more actionable persona attributes than demographics alone (Cooper 1999; Pruitt & Adlin 2006). This insight directly motivates our identity-behavior decoupling principle.

The EU AI Act (2024) establishes transparency requirements for AI systems, including obligations to disclose when content is AI-generated (Article 50) and, for high-risk systems, requirements for human oversight (Article 14) and accuracy and robustness (Article 15). These requirements are particularly relevant for synthetic audience systems, where outputs could be misinterpreted as real user research data.

Practitioner persona guides have long advocated for behavior-first persona design, arguing that personas should be defined by goals, behaviors, and pain points rather than demographic attributes (Mulder & Yaar, 2006). AudienceLens operationalizes this principle through its `behavior_profile` construct, which replaces traditional OCEAN-based personality models with task-oriented behavioral dimensions.

## 3. Method

### 3.1 System Architecture

The persona pool comprises **72 personas across 11 YAML packages**, serving **14 task types**. All counts below can be verified against `src/personas/` and the single authoritative registry `VALID_TASK_TYPES` in `src/runner/task_types.py`:

| Persona domain | Packages | Personas | Task types served |
|---|---|---|---|
| Game | 8 (`game-core` 17, `mobile-f2p` 7, `competitive-esport` 5, `family-casual` 5, `indie-creative` 5, `accessibility` 4, `educational-serious` 4, `vr-immersive` 4) | 51 | 10 (`steam_page_review`, `demo_first_play`, `concept_review`, `monetization_review`, `looking_for_party_post`, `update_announcement_review`, `devlog_review`, `kickstarter_review`, `localization_review`, `discord_community_review`) |
| Launch / compliance | 1 (`launch-compliance` 5) | 5 | cross-domain (store submission, age rating, privacy compliance, device compatibility, refund/churn) |
| General product | 1 (`general-consumer` 8) | 8 | 3 (`product_feedback_review`, `pricing_page_review`, `onboarding_review`) |
| Startup / pitch | 1 (`startup-panel` 8) | 8 | 1 (`pitch_review`) |
| **Total** | **11** | **72** | **14** |

Three review skills (`synthetic-playtest`, `audience-panel`, `red-team-audience`) and one meta-skill (`persona-generate`) are defined as skill-pack front-ends over this pool. Two clarifications are needed here, because earlier descriptions of this system were inaccurate on both points. First, **`red-team-audience` has no persona pack of its own**: no red-team personas ship in `src/personas/`, and "red team" exists only as a skill-level framing over the existing pool, not as a distinct set of persona definitions. Second, `persona-generate` is an LLM-driven authoring workflow specified in a skill Markdown file, not a code path; the personas it produces are new YAML packs, not runtime entities.

A key architectural property is **context isolation** between personas. Each persona review is an independent, stateless model call dispatched from a thread pool (`concurrent.futures.ThreadPoolExecutor` in `src/runner/cli.py`); a call receives only its own persona payload, the target material, and the task rubric. No conversation state, reasoning trace, or intermediate result is shared between persona calls. This prevents cross-contamination, where one persona's reasoning leaks into another's. Note that we describe threads with per-call prompt construction, not OS subprocesses; the isolation guarantee comes from the calls being stateless and independently prompted, not from process boundaries.

Isolation is preserved, not abandoned, in the rebuttal round. A persona re-invoked to rebut receives one opposing argument — its content, its severity rating, and the stance and confidence attached to it — and nothing that identifies its author: no persona name, no id, no archetype (Section 3.1, item 5). Influence therefore propagates only through the position pool, in the sense that what crosses between personas is a position, never an identity or a conversation history.

### Context Isolation Implementation

All five items below describe implemented behaviour. Item 3 is scoped carefully: one rebuttal round runs, not the three-round structure of the original specification (Section 4.6).

1. **Input Phase** *(implemented)*: Each persona agent receives:
   - Target material summary (truncated to fit context window)
   - Persona YAML definition (behavior_profile, motivations, decision_rules)
   - Task rubric and output schema
   - Review mode parameters (quick/standard/full)

   Demographic fields are excluded at this step: only the `CORE_FIELDS` allowlist is serialised (Section 6.1).

2. **Isolation Guarantee** *(implemented)*: Each persona agent does NOT receive:
   - Other persona agents' full outputs
   - Other persona agents' private reasoning chains
   - Aggregation notes or intermediate results
   - Information about which other personas are in the panel

3. **Rebuttal Phase** *(implemented, one round)*: In `full` mode each persona involved in a controversy point is re-invoked with its own identity card, its own recorded argument, and the single opposing argument for that point — the latter labelled only by an anonymous ID. In `standard` mode a single moderated call receives all controversy points with both sides of each rendered anonymously. In both tiers the persona is asked for a rebuttal plus an updated stance and confidence. One round only; the specified second and third rounds are not executed.

4. **Position Pool** *(implemented as an aggregation input)*: Persona outputs are stored as structured JSON objects containing stance, confidence, key_issues, and evidence arrays, and are consumed by the aggregation layer rather than by individual persona agents. The rebuttal round reads this pool a second time to construct the opposing arguments it sends back out.

5. **Anonymised opponent attribution** *(implemented; the scope of the claim matters)*: Opposing arguments are addressed only by anonymous ID — `A1` for the side rating an issue more severe, `B1` for the side rating it less so — and the prompt instructs the model not to speculate about an argument's author. Anonymisation is not left to the template alone: the rendering layer also scrubs persona names out of the *body* of an argument, replacing them with a neutral placeholder, so a persona who wrote its own name into its reasoning does not leak it. The moderated prompt contains no persona name at all.

   We state the boundary exactly, because the earlier draft of this paper claimed the stronger property and the shipped code did not have it. What is guaranteed is that **no persona is shown another persona's identity**. In `full` mode a re-invoked persona still receives its own identity card — archetype, decision rules, and the rest — so that it argues in its own established voice rather than as a generic critic, but the `id` and `name` fields are removed from that card on both paths (the engine path and the web application's v1 review path), so no persona name appears anywhere in a rebuttal prompt. The residual gap is in the argument text rather than the card: name scrubbing replaces whole persona names only, so a persona that refers to itself by a short form or a role epithet inside its own reasoning can still leak through. The anti-collusion property we claim, and test, is the absence of *opponent* identity; we do not claim full self-anonymisation, since the rest of the card remains.

The system operates in nine phases, numbered 0–8: (0) argument parsing, (1) task type validation, (2) material loading, (3) panel selection, (4) parallel persona reviews, (5) cross-examination, (6) report aggregation, (7) calibration check, and (8) output generation. Phases 5 and 7 are skipped in `quick` mode; all phases execute in `full` mode. Phase 5 issues live rebuttal calls in `standard` and `full` modes and degrades to a derived summary, with the reason recorded, if those calls fail (Section 4.6).

### 3.2 Persona Design

Each persona is defined by a YAML specification containing identity fields, behavioral profiles, motivations, decision rules, and review configuration. The core innovation is the **behavior_profile**—a 12-axis behavioral vector that replaces traditional personality models:

All twelve axes are `required` in `src/schemas/persona-schema.json`, which also sets `additionalProperties: false`; the table below is the complete and exact axis list:

| # | Axis | Range | Description |
|---|------|-------|-------------|
| 1 | `patience` | very_low – very_high | Tolerance for friction and delay |
| 2 | `genre_literacy` | very_low – very_high | Domain-specific knowledge depth |
| 3 | `novelty_seeking` | very_low – very_high | Preference for novel over familiar |
| 4 | `risk_tolerance` | low – high | Comfort with uncertainty |
| 5 | `social_influence` | low – very_high | Susceptibility to social proof |
| 6 | `completion_drive` | very_low – very_high | Motivation to finish what was started |
| 7 | `price_sensitivity` | low – very_high | Sensitivity to cost relative to value |
| 8 | `criticism_style` | categorical | Approach to expressing dissatisfaction |
| 9 | `emotional_engagement` | low – high | Depth of emotional investment |
| 10 | `agency_preference` | low – high | Desire for player/user agency |
| 11 | `tolerance_for_ambiguity` | very_low – very_high | Comfort with unclear situations |
| 12 | `platform_loyalty` | very_low – high | Attachment to a specific platform or storefront |

The axis is named `genre_literacy` for every pack, including the non-game ones; there is no separate `domain_literacy` field.

This design departs from the OCEAN (Big Five) personality model. We argue that `behavior_profile` is better suited for review tasks for four reasons:

1. **Task orientation**: Review is a task-oriented behavior, not a social one. OCEAN dimensions like extraversion and agreeableness primarily describe social interaction patterns, which are largely irrelevant when personas evaluate artifacts independently. `behavior_profile` directly models task-relevant behaviors (patience, completion drive, risk tolerance), yielding higher information density per dimension.

2. **Predictive vs. descriptive**: OCEAN answers "what kind of person is this?" while `behavior_profile` answers "what will this persona do in a review task?" The latter directly serves output interpretability and traceability.

3. **Reduced collinearity**: In review contexts, OCEAN's conscientiousness and openness dimensions influence review behavior in highly similar ways (both manifest as attention to detail). `behavior_profile` decomposes these into finer-grained behavioral drivers (`completion_drive` vs. `novelty_seeking`), avoiding dimensional redundancy.

4. **Direct traceability**: Our ethics framework requires all judgments to be traceable to `behavior_profile` or `motivations`. Using OCEAN labels would introduce an indirect mapping layer, increasing the complexity of compliance auditing.

The mapping between OCEAN and `behavior_profile` is as follows: openness_to_experience maps to `novelty_seeking` + `tolerance_for_ambiguity`; conscientiousness maps to `completion_drive` + `patience`; extraversion maps to `social_influence`; agreeableness maps inversely to `emotional_engagement`; and neuroticism maps inversely to `risk_tolerance`.

Each persona also includes `decision_rules`—explicit conditional statements that govern judgment (e.g., "if the core hook is not visible within 15 seconds, do not wishlist"), `quit_triggers` and `continue_triggers` that define retention/attrition boundaries, and `evidence_types_needed` that specify what evidence the persona requires to form grounded judgments.

### Persona Taxonomy

| Package | Count | Domain | Key Behaviors |
|---------|-------|--------|---------------|
| game-core | 17 | Game | Core exploration, system analysis |
| mobile-f2p | 7 | Game | Monetization sensitivity, session design |
| indie-creative | 5 | Game | Innovation focus, aesthetic judgment |
| competitive-esport | 5 | Game | Skill ceiling, balance, fairness |
| family-casual | 5 | Game | Accessibility, onboarding, safety |
| vr-immersive | 4 | Game | Immersion, comfort, presence |
| educational-serious | 4 | Game | Learning outcomes, engagement |
| accessibility | 4 | Game | Keyboard/screen/cognitive access |
| general-consumer | 8 | Product | Everyday product/app evaluation, pricing, onboarding |
| startup-panel | 8 | Startup | Business plan, pitch deck, market and funding scrutiny |
| launch-compliance | 5 | Launch gate | Store submission, age rating, privacy law, device compatibility, refund/churn |
| **Total** | **72** | | |

Each persona is defined by a complete behavior_profile, motivations, decision_rules, quit_triggers, and continue_triggers. The 72-persona count reflects coverage across domains, not redundancy; Jaccard distance analysis (Section 5.2) measures actual differentiation. This is the complete inventory as of the v0.3.0 release: there is no red-team persona pack, and the product-facing pool is 16 personas in two packs, not the six finer-grained packs described in earlier drafts of this work.

### 3.3 Cross-Examination Protocol (Rounds 1–2 implemented; Round 3 and the multi-round structure specified only)

> **Implementation status.** Rounds 1 and 2 execute. Round 2 issues real model calls, and the runtime distinguishes three states in a `mode` field — `derived_summary`, `moderated_rebuttal`, `multi_agent_rebuttal` — with `is_live_debate` true only for the latter two, and only when a rebuttal result was actually parsed. Stance changes are populated and are adjudicated in code (Section 3.4), with $\theta_{\text{change}}$ read from `src/config/aggregation-rules.yaml`. **Round 3 as a separate model round, early termination, panel-wide persuasion scoring (Section 3.3), consensus-evolution classification (Section 3.5), and tipping-point detection (Section 3.6) are not implemented.** Section 4.6 gives the per-mechanism status. No *empirical* result is reported for any of this: the protocol runs, but we have not evaluated it (Section 5.0).

The cross-examination protocol is the core differentiator of AudienceLens. As specified, it proceeds in three rounds; we mark each round's status inline.

**Round 1: Position Statement** *(implemented)*. Each persona independently reviews the input material and produces a structured output including scores, key issues, evidence, and a primary stance. All outputs are collected into a shared position pool. Critically, personas are not aware of each other's existence at this stage—they evaluate the material in complete isolation.

**Round 2: Rebuttal** *(implemented, with two documented narrowings)*. The system extracts the top-$k$ controversy points from Round 1 outputs, ranked by the variance of severity ratings across personas, and for each point identifies the two personas holding the most opposed positions. Their own recorded wording becomes the pro and con argument, labelled `A`$k$ and `B`$k$. A rebuttal call is then issued and the model returns, per argument, a rebuttal plus an updated stance and confidence; a stance change is recorded only if the code-side gate of Section 3.4 accepts it.

Two narrowings against the original specification, both of which change what may be claimed. First, **only the two most-opposed personas per controversy point participate**; the specification had all $n$ personas score every argument's persuasiveness on a 1–5 scale, and no persuasiveness score is computed or stored anywhere in the implementation. Second, **two tiers exist and they are not equivalent.** In `standard` mode a *single* call is made from a moderator's vantage point, writing both sides' rebuttals in one pass — cheap, but not $n$ independent agents. Only `full` mode re-invokes each involved persona as its own model call, which is the configuration that merits the term multi-agent rebuttal. `quick` mode runs no cross-examination. The runtime's `mode` field records which of these actually happened, and the `limitation` string shipped inside every report spells out the difference in prose so that a reader of the report, not just of this paper, sees it.

**Round 3: Final Stance** *(not implemented as a separate round)*. The specification calls for a third model round in which each persona restates a final position. In the implementation the post-rebuttal stance returned in Round 2 *is* the final stance; there is no third call and no multi-round trajectory. The recorded provenance is therefore a two-point comparison (before, after), not a trajectory across three rounds.

The specified early-termination rule — stop when two consecutive rounds produce no stance changes — is moot in a single-round implementation and is not implemented.

Formally, let $P = \{p_1, p_2, \ldots, p_n\}$ be the set of personas. In Round 1, each $p_i$ produces output $o_i^{(1)} = (s_i^{(1)}, c_i^{(1)}, e_i^{(1)})$ where $s_i^{(1)}$ is the stance, $c_i^{(1)} \in [0,1]$ is the confidence, and $e_i^{(1)}$ is the evidence set. The controversy points $C = \{c_1, \ldots, c_k\}$ are extracted by:

$$C = \text{top-}k \left(\text{argsort}_{j} \left(\text{Var}(\{s_{1,j}^{(1)}, \ldots, s_{n,j}^{(1)}\})\right)\right)$$

where $s_{i,j}^{(1)}$ denotes persona $p_i$'s severity rating on issue $j$. In Round 2, each persona evaluates the persuasiveness of arguments for and against each controversy point, producing updated confidence $c_i^{(2)}$. A stance change is permitted when:

$$|c_i^{(2)} - c_i^{(1)}| \geq \theta_{\text{change}}$$

where $\theta_{\text{change}} = 0.15$. Two notes. First, $\theta_{\text{change}}$ is now **read at runtime** from `src/config/aggregation-rules.yaml` and applied by the code that decides whether a change counts; changing the file changes the system's behaviour, which was not true of earlier releases. Second, it remains an engineering parameter and **not an empirically validated one**: 0.15 was chosen by judgment, we have run no experiment to calibrate it, and it would need tuning per model and domain. Implementing a threshold is not the same as validating it, and we claim only the former. The implementation compares with $\geq$ rather than the strict $>$ of the original specification, using a small floating-point tolerance, so that a delta of exactly $\theta$ is counted rather than lost to representation error.

### 3.4 Vote Change Mechanism (implemented)

The vote change mechanism is designed to model realistic opinion dynamics while preventing cascading conformity. Key design choices:

**Confidence threshold.** A persona's stance change is recorded only when the stance text actually differs from its pre-rebuttal value *and* the confidence shift reaches $\theta_{\text{change}}$. This threshold was chosen to be large enough to filter out noise (minor fluctuations in LLM output probabilities) while small enough to capture genuine persuasion. We acknowledge this value is set by engineering judgment and plan to calibrate it through controlled experiments in future work. We do not interpret self-reported confidence as calibrated probability; LLM confidence scores may not reflect true epistemic uncertainty.

**The gate is in code, not in the prompt.** This is the design point we most want to draw out, because it is where a system of this kind is easiest to fake. The model is asked to report its updated stance and confidence; it is *not* asked whether it changed its mind, and any such self-report is not what the system acts on. `_decide_change()` compares the before and after values and applies the threshold itself. A model that returns prose to the effect of "position unchanged" alongside numerically identical values produces no vote change; a model that asserts it changed its position while moving confidence by less than $\theta$ produces no vote change either. The consequence is that the vote-change count in a report is a property of the numbers the model emitted, not of the model's willingness to describe itself as persuaded.

**Change provenance.** Every recorded stance change carries: the controversy point and topic, the argument ID that triggered it, the changing persona's real id and display name, the stance before and after, the confidence before and after, the signed delta, and the threshold in force for that run. Claimed changes that the gate rejects are not discarded — they are retained in a separate `suppressed_changes` array with the reason for suppression (below threshold, or stance updates disabled in configuration), so that a reader can distinguish "no persona was persuaded" from "personas claimed persuasion the system declined to count."

**Anti-collusion design.** Personas cannot directly communicate; influence propagates only through the position pool, which is intended to prevent the "echo chamber" effect and ensure that any stance change is driven by argument quality rather than social pressure. The supporting anonymisation property is now present and tested at the scope stated in Section 3.1, item 5: an opposing argument reaches a persona with its author's identity removed from both the metadata and the argument text. Two caveats remain and neither is minor. First, the property is *opponent* anonymity, not full anonymity: neither path puts any persona `id` or `name` in a rebuttal prompt, but a persona still sees the remaining fields of its own identity card, and name scrubbing in the argument text matches whole persona names only, so self-reference by a short form can still slip through. Second, the design has been exercised but not *evaluated*: we present no evidence that it achieves its stated aim of preventing identity-driven capitulation, only that the identity is absent from the prompt.

**No majority weighting.** The system does not weight personas by their agreement with the majority. A single persona holding a minority position is as valid as five personas in agreement—the value lies in understanding *why* they disagree, not in counting votes.

### 3.5 Consensus Evolution Tracking (specification; not implemented in v0.3.0)

> **Implementation status.** No consensus-evolution mechanism exists in the codebase, and implementing the rebuttal round did not add one. The identifiers `consensus_strength`, `converging`, `diverging`, `oscillating`, `tipping_point`, and `cascade_point` still do not appear anywhere under `src/` or under the web backend. What the system actually computes is a stance distribution over the Round 1 outputs in `src/runner/aggregator.py`, using a `consensus_threshold` of 0.7 read from `src/config/aggregation-rules.yaml`; the aggregator is not re-run on post-rebuttal stances. Individual stance changes are recorded (Section 3.4), but they are never aggregated into a consensus trajectory, and there is no divergence-hotspot or polarization output. The remainder of this subsection specifies what such a mechanism would compute.

Under the specification, after the three-round protocol completes the system would classify the group's consensus trajectory into one of four patterns:

| Pattern | Definition | Indicator |
|---------|-----------|-----------|
| **Converging** | Agreement increases across rounds | $\text{consensus\_strength}^{(3)} > \text{consensus\_strength}^{(1)}$ |
| **Diverging** | Agreement decreases across rounds | $\text{consensus\_strength}^{(3)} < \text{consensus\_strength}^{(1)}$ |
| **Stable** | Agreement remains approximately constant | $|\text{consensus\_strength}^{(3)} - \text{consensus\_strength}^{(1)}| < 0.1$ |
| **Oscillating** | Agreement fluctuates non-monotonically | Direction changes between rounds |

Consensus strength is defined as the proportion of personas sharing the modal stance:

$$\text{consensus\_strength}^{(r)} = \frac{|\{p_i : s_i^{(r)} = \text{mode}(S^{(r)})\}|}{n}$$

where $S^{(r)} = \{s_1^{(r)}, \ldots, s_n^{(r)}\}$ is the set of stances at round $r$.

We acknowledge that modal stance proportion is a coarse metric. Future versions should incorporate:

- **Confidence-weighted consensus**: Weight each persona's stance by its self-reported confidence, so high-confidence positions contribute more than low-confidence ones.
- **Segment-weighted disagreement**: Weight disagreements by persona segment relevance, so that a domain-expert persona's opposition carries more weight than a casual user's.
- **Minority report preservation**: Explicitly flag and preserve minority positions even when consensus is strong, as minority perspectives often identify risks missed by the majority.

The specification also calls for tracking **divergence hotspots**—issues where confidence changes are largest—and **polarization**, defined as the condition where the group splits into two roughly equal opposing camps rather than converging. Neither is implemented.

### 3.6 Tipping Point Detection (specification; not implemented in v0.3.0)

Tipping points are moments where the discussion trajectory changes qualitatively. The specification defines three types; **none of them is detected by the current implementation.** A flip point is in principle now computable — the system records stance changes — but nothing classifies or reports one; cascade and anchor points require the multi-round state that a single rebuttal round does not produce:

**Flip points** (red): A persona changes from one stance category to another (e.g., from "would buy" to "would not buy"). These would indicate that a counterargument was sufficiently compelling to overcome the persona's initial position.

**Cascade points** (amber): One persona's stance change triggers changes in other personas within the same round. These would indicate that the changing persona's reasoning provided a new frame that resonated with others.

**Anchor points** (green): A persona maintains their stance despite strong counterarguments. These would indicate deeply held positions that are resistant to persuasion, often tied to core behavioral traits (e.g., a persona with very high `price_sensitivity` refusing to endorse a product regardless of its features).

The proposed formal detection rule for tipping points is:

$$\text{TippingPoint}(r) = \begin{cases} \text{true} & \text{if } |\{p_i : s_i^{(r)} \neq s_i^{(r-1)}\}| \geq 2 \\ \text{true} & \text{if } \max_i |c_i^{(r)} - c_i^{(r-1)}| \geq 0.3 \\ \text{false} & \text{otherwise} \end{cases}$$

### 3.7 Harness Evaluation Framework

The Harness is an 8-dimension quality evaluation rubric that scores a completed synthetic review against quantitative thresholds. We define initial operational thresholds for prototype evaluation. These thresholds are not validated norms; they serve as engineering guardrails and should be calibrated through future empirical work.

Two properties of the implementation should be stated before the thresholds, because they bound what the Harness can be claimed to do:

- **It is a post-hoc scorecard, not a gate.** The evaluation is disabled by default (`enable_evaluation = False`) and, when enabled, runs *after* a review has completed. It does not filter, reject, block, or re-run any persona output, and a failing score does not prevent a report from being produced. Everything the Harness reports is diagnostic.
- **The thresholds are declared once and read at runtime.** All eight live in `src/harness/thresholds.yaml`, which the evaluator loads rather than hard-coding, and the file carries a `threshold_note` recording that they are prototype values that have not been empirically validated. The table below is a transcription of that file.

| # | Dimension | Core Question | Threshold |
|---|-----------|---------------|-----------|
| 1 | Actionability | Are recommendations specific and implementable? | $\geq 70\%$ of suggestions include concrete steps (prototype, not validated) |
| 2 | Input Grounding | Do arguments reference specific input material details? | $\geq 80\%$ of claims cite input evidence; direct evidence ratio $\geq 60\%$ (prototype, not validated) |
| 3 | Persona Differentiation | Do different personas produce genuinely different perspectives? | Mean Jaccard distance $\geq 0.3$ (prototype, not validated) |
| 4 | Stereotype Check | Are judgments based on behavioral profiles, not demographics? | Zero demographic-causal inference patterns (prototype, not validated) |
| 5 | Structural Integrity | Does the report contain all required sections? | 100% of required sections present (prototype, not validated) |
| 6 | Calibration Honesty | Are findings correctly labeled as hypotheses rather than facts? | 100% of hypotheses correctly annotated (prototype, not validated) |
| 7 | Risk Detection | Are critical risks identified? | $\geq 1$ critical/high severity issue identified (prototype, not validated) |
| 8 | Segment Conflict | Do persona segments exhibit meaningful disagreement? | $\geq 2$ meaningful disagreements (prototype, not validated) |

Each dimension is scored on a 1–5 scale using rubric definitions. A score of 0–1 indicates FAIL, 2–3 indicates NEEDS_IMPROVEMENT, and 4–5 indicates PASS. Dimensions carry weights (stereotype check 1.5, calibration honesty 1.2, all others 1.0), and the overall result is a **weighted mean on the same 1–5 scale**; it passes only if every dimension scores $\geq 2$ and the weighted mean is $\geq 3.0$. There is no aggregate points-out-of-40 score; any such figure attributed to this system is not something the evaluator emits.

The Harness includes test fixtures (high-quality and low-quality game concepts, good and bad landing pages) that serve as calibration anchors, and expected output structures that define required report sections for each task type.

## 4. Implementation

### 4.1 Architecture and Entry Points

AudienceLens v0.3.0 is an MIT-licensed Python package (`audiencelens`) with the review engine under `src/runner/` and the evaluation rubric under `src/harness/`. It is reachable through five entry points: a command-line interface, a Python API, an MCP server, a web application (FastAPI backend), and a Docker image. Provider presets ship for six model vendors. On top of the engine, a skill-pack front-end is provided for AI coding assistants (Claude Code and Trae AI); each skill is defined by a `SKILL.md` file specifying behavior, resource files, execution phases, and hard rules, and is invoked via slash commands (e.g., `/synthetic-playtest concept_review path/to/concept.md`).

The local-first deployment offers several advantages over hosted SaaS: (1) **Privacy**: input materials never leave the user's local environment; (2) **Customization**: users can modify persona definitions, aggregation rules, and prompt templates; (3) **Composability**: skills can be chained (e.g., running `audience-panel` followed by `red-team-audience` on the same material); and (4) **Cost efficiency**: the system uses the user's own model credentials without additional per-review fees.

### 4.2 CCGS Repository Standard

AudienceLens follows the CCGS (Claude Code Group Standard) repository structure, which organizes multi-agent systems into a standardized directory layout:

```
.claude/
├── agents/          # 50 persona agent definitions (game pool)
├── hooks/           # Lifecycle hooks (session-start, validate-report, etc.)
├── launch.json
└── skills/          # 1 skill definition (synthetic-playtest) with resources
.trae/
├── documents/
├── skills/          # 4 skill mirrors (synthetic-playtest, audience-panel,
│                    #   red-team-audience, persona-generate)
└── specs/
```

Two corrections to earlier descriptions of this layout: there is no `.claude/rules/` directory — evaluation thresholds live in `src/harness/thresholds.yaml` and aggregation parameters in `src/config/aggregation-rules.yaml` — and `.claude/skills/` currently holds one skill, not four; the full set of four skill definitions exists only under `.trae/skills/`. Skill-pack coverage across the two assistants is therefore asymmetric.

Each persona agent is defined as a standalone Markdown file (e.g., `P01-indie-core-operator.md`) that the skill dispatcher loads and injects into the LLM context when that persona is selected for a review panel. Note that the 50 agent Markdown files mirror the game pool only; the canonical persona definitions used by the Python engine are the 11 YAML packs under `src/personas/`.

### 4.3 Ethics Service

The ethics service enforces the identity-behavior decoupling principle through a multi-layer compliance system:

**Stereotype detection.** The system scans persona outputs for forbidden patterns where demographic attributes are used as causal explanations for behavioral judgments. Detection has two layers. The first is a regex pass covering four categories — gender-as-cause, age-as-stereotype, region-as-assumption, and MBTI-as-decision-logic — with both explicit patterns (e.g., "as a female player, I prefer...") and implicit ones (e.g., "players of this age group typically..."), in Chinese and English. The second is an LLM judge that catches rephrased demographic-to-behavior inferences the regexes miss; it is **conditional on an API key being configured**, and when unavailable the system reports the count of unchecked outputs rather than silently treating them as clean.

**Evidence grounding.** Every claim in a persona's output must be annotated with an inference level: `[direct]` (explicitly present in input material), `[inferred: basis]` (reasonably inferred from material + persona priors, capped at $\leq 40\%$ of total evidence), or `[gap]` (no evidence available, must be labeled "unspecified"). Gap-filling—fabricating information not present in the input—is strictly prohibited.

**Compliance scoring.** The report carries an ethics compliance score in the range 0–100. We describe it precisely, because it is coarser than its numeric range suggests. The score is computed in `src/runner/aggregator.py` as $100 - 10 \times |V|$, clamped to $[0, 100]$, where $V$ is the set of identity-behavior decoupling violations found across all persona outputs. It therefore takes only multiples of ten, and its sole input is the decoupling check — it is *not* a weighted composite of five dimensions, and evidence grounding, gap-filling, caveat specificity, and MBTI usage are enforced elsewhere (by the validator and the Harness rubric) rather than folded into this number. Bands are: $\geq 80$ pass, $50$–$79$ needs revision, $< 50$ rejected. A five-dimension weighted composite (behavior_over_demographics 30%, evidence_grounding 25%, gap_filling_control 20%, caveat_specificity 15%, mbti_usage_correctness 10%) remains a design goal and is not implemented.

**MBTI prohibition rule.** MBTI types are permitted only as style modifiers (affecting tone and communication style) and are explicitly prohibited from serving as causal explanations for judgments. This rule is enforced through both prompt engineering and post-hoc pattern matching.

### 4.4 HTML Report Generation

AudienceLens generates three output formats: structured JSON (machine-readable), Markdown (human-readable), and HTML (visual report). The HTML report uses a cyberpunk HUD aesthetic with the following design principles:

- **Information density**: The HUD dashboard displays three key metrics (consensus strength, risk level, persona count) in a compact card layout
- **Visual encoding**: Severity levels map to color-coded badges (green → amber → red → blinking red for critical), evidence levels map to border colors (cyan for direct, amber for inferred, red for gap), and stance categories map to CSS classes (positive, neutral, negative)
- **Persona avatars**: Generated deterministically from persona IDs using HSL color hashing (hue = hash(id) mod 360, saturation 65%, lightness 55%)
- **Score bars**: Width = score × 20% with color classes (s1=red through s5=green)
- **Typography**: Space Mono for code/HUD elements, Noto Sans SC for body text, Noto Serif SC for headings

The HTML report is rendered by the aggregation layer from `report-template.html` using Jinja2 (`jinja2.Environment` with a `FileSystemLoader` in `src/runner/aggregator.py`); persona and cross-examination prompts are rendered from Handlebars-style Markdown templates that are converted to Jinja2 syntax before rendering.

### 4.5 On the Absence of a Case Study

Earlier versions of this paper included a worked example ("Cyber Scavenger game concept review") reporting a panel of six personas, two stance changes, a tipping point, a Harness score of 31/40 against a threshold of 28, and an ethics compliance score of 72/100. **We have removed it, and we state why rather than quietly dropping it.**

The numbers were not reproducible from the system as implemented. Two of them remain unreachable even now: the ethics compliance score can only take multiples of ten (Section 4.3), so 72 is not in its range, and the attributed cause — insufficient calibration honesty — is not among that score's inputs; and "31/40 (threshold 28)" is not a scale the evaluator emits, which reports a weighted mean in $[1,5]$ (Section 3.7). The tipping point remains undetectable, since no tipping-point detection exists (Section 3.6). The one figure that has since become *producible* is the stance-change count, now that the vote-change mechanism runs (Section 3.4) — but a producible number is not a recovered one. No input or output artifact from that run is archived in the repository, so the specific claim that two of six personas changed stance on that material is still unsupported, and we do not reinstate it.

We therefore report no example run. AudienceLens produces three output formats (structured JSON, Markdown, and HTML; Section 4.4), and a reader who wants to see one can generate it from the open-source repository. Publishing an archived, byte-reproducible example run — with the input material, the model and version used, and the full output tree committed alongside the paper — is straightforward and is planned for the next revision. Until then we prefer an absent example to an illustrative one.

### 4.6 Implementation Status: Specification vs. v0.3.0

Because this paper contains both implemented mechanisms and specified-only ones, we give a single table stating the status of each and the file a reader can check it against. This is the authoritative statement; where any prose elsewhere in the paper conflicts with it, this table governs.

| Mechanism | Section | Status in v0.3.0 | Where to verify |
|---|---|---|---|
| Three-level evidence labelling (`direct`/`inferred`/`gap`) | 4.3 | **Implemented** | `src/runner/validator.py` |
| 40% inferred-evidence cap, enforced by rejection | 4.3 | **Implemented** | `src/runner/validator.py` |
| Demographic fields withheld from the model prompt | 6.1 | **Implemented** | `CORE_FIELDS` in `src/runner/persona_agent.py` |
| Stereotype detection, regex layer | 6.2 | **Implemented** | `src/harness/stereotype_judge.py` |
| Stereotype detection, LLM judge layer | 6.2 | **Implemented, conditional on an API key** | `src/harness/stereotype_judge.py` |
| 8-dimension Harness rubric and thresholds | 3.7 | **Implemented**; off by default, post-hoc, non-blocking | `src/harness/thresholds.yaml`, `src/harness/evaluator.py` |
| Single-round consensus (modal stance vs. threshold 0.7) | 3.5 | **Implemented** | `src/runner/aggregator.py`, `src/config/aggregation-rules.yaml` |
| Ethics compliance score | 4.3 | **Implemented** as $100 - 10\lvert V\rvert$, single input | `src/runner/aggregator.py` |
| Context isolation between persona calls | 3.1 | **Implemented** (stateless per-call prompts, thread pool) | `src/runner/cli.py` |
| Live rebuttal round, `standard` mode (one moderated call) | 3.3 | **Implemented.** Runtime returns `mode: "moderated_rebuttal"`, `is_live_debate: true`. The `limitation` string states in prose that this is one arbitrated round, not each persona speaking independently. | `src/runner/cross_exam.py`, `src/runner/cli.py`, `web/backend/app/services/__init__.py` |
| Live rebuttal round, `full` mode (each involved persona re-invoked) | 3.3 | **Implemented.** Runtime returns `mode: "multi_agent_rebuttal"`. One call per persona per controversy point. | `src/runner/cross_exam.py`, `src/runner/cli.py` |
| Honest mode labelling and fallback on failure | 3.3 | **Implemented.** `is_live_debate` is true only when a rebuttal was actually parsed; exceptions, unparseable output, and mismatched argument IDs fall back to `derived_summary` with the reason in `limitation` and an entry in `failures[]`. Failures are surfaced in the report, not swallowed. | `src/runner/cross_exam.py` |
| Rounds 2 and 3 as separate model rounds; early termination on convergence | 3.3 | **Not implemented.** Exactly one rebuttal round runs; the post-rebuttal stance is the final stance. `rounds` reflects what actually ran and is `[]` in derived mode. | `src/runner/cross_exam.py` |
| Panel-wide persuasion scoring (all personas rate each argument 1–5) | 3.3 | **Not implemented.** Only the two most-opposed personas per controversy point participate; no persuasiveness score is computed or stored. | `src/templates/cross-exam-prompt.md` |
| Vote-change mechanism and change provenance | 3.4 | **Implemented and adjudicated in code.** `vote_changes` is populated only when the stance text changed *and* $\lvert\Delta c\rvert \geq \theta$; model self-reports are not trusted. Rejected claims are kept in `suppressed_changes` with a reason. Confidence deltas are computed, not hard-coded. | `src/runner/cross_exam.py` |
| Confidence threshold $\theta_{\text{change}} = 0.15$ | 3.3 | **Read at runtime** and applied by the change gate; the effective value and its source are reported in the output. Still **not empirically validated**. | `src/config/aggregation-rules.yaml`, `src/runner/cross_exam.py` |
| Cross-examination token and cost accounting | 4.1 | **Implemented.** Rebuttal calls are counted and billed into the review's totals; when a caller returns no token counts the output flags this and the `limitation` says the cost figure may be low. | `src/runner/cli.py`, `web/backend/app/services/__init__.py` |
| Consensus evolution across rounds (converging / diverging / stable / oscillating) | 3.5 | **Not implemented.** None of these identifiers exists under `src/` or the web backend. | — |
| Tipping-point and cascade-point detection | 3.6 | **Not implemented.** Neither identifier exists under `src/`. | — |
| Opponent anonymisation in rebuttal prompts | 3.1 | **Implemented.** Arguments are addressed by anonymous ID only; the template has no persona-name slot, and the renderer scrubs persona names out of argument text. **Scope: opponent identity only** — a persona still sees the remaining fields of its own identity card, but `id` and `name` are stripped on both the engine and web v1 paths, so no persona name appears in a rebuttal prompt. | `src/templates/cross-exam-prompt.md`, `src/runner/cross_exam.py`, `src/runner/cli.py` |
| Kruskal-Wallis test / score standard-deviation check | 5.1 | **Not implemented.** The differentiation dimension computes Jaccard distance only; the project has no statistical-testing dependency. | `src/harness/evaluator.py` |
| Warning when $>30\%$ of personas are skipped for insufficient evidence | 6.5 | **Not implemented.** A degradation banner exists but triggers on model-call failures, not on evidence-based skips. | `src/runner/cli.py` |
| Automated regression suite | — | **Implemented**: 453 engine tests and 303 backend tests (1 skipped) pass as of 2026-07; counts move with development, so run the suites rather than trusting the number. | `tests/`, `web/backend/tests/` |

## 5. Evaluation

### 5.0 Planned Evaluation Design

To validate the effectiveness of cross-examination, we plan the following controlled experiment:

**Design**: A/B comparison between review with and without the rebuttal round. Because two rebuttal tiers now ship, the natural design is three arms rather than two.

**Protocol**:
- **Group A (Baseline)**: Each persona independently reviews the target material and produces a single review output, with no interaction between personas. Corresponds to `quick` mode, or to any mode whose rebuttal call fails and falls back to a derived summary.
- **Group B (Moderated rebuttal)**: Independent reviews followed by one moderated rebuttal call across all controversy points. Corresponds to `standard` mode.
- **Group C (Multi-agent rebuttal)**: Independent reviews followed by re-invoking each involved persona separately. Corresponds to `full` mode. Distinguishing B from C matters: B costs one extra call regardless of panel size and C costs one per involved persona, so the interesting question is whether C buys anything commensurate.

**Materials**: 4 standard fixtures (2 high-quality, 2 low-quality inputs) spanning game concepts and product landing pages.

**Metrics**: Harness 8-dimension scores, persona differentiation (Jaccard distance), actionability ratio, risk detection coverage, and human evaluator preference ratings.

**Hypothesis**: Groups B and C will show higher persona differentiation, better risk detection, and more actionable recommendations than Group A, at the cost of increased token usage, with C exceeding B by a margin that may not justify its cost.

**This evaluation has not been conducted.** It is now *runnable* — all three arms correspond to shipping configurations, and the rebuttal calls are billed and counted so the cost side of the comparison is directly measurable — but running an experiment and having run one are different things, and we report no result. Everything in Sections 5.3 and 5.4 remains a proposal.

### 5.1 Harness 8-Dimension Evaluation

The Harness framework provides both quantitative thresholds and qualitative rubrics for each dimension. We describe the evaluation methodology for each:

**Actionability** is measured by the proportion of key issues that include specific, implementable `suggested_fix` fields. A suggestion is considered "actionable" if it specifies what to change, how to change it, and what the expected outcome is. The threshold of $\geq 70\%$ reflects the practical reality that some issues may be inherently vague (e.g., "the overall tone feels off") while still being worth reporting.

**Input Grounding** uses a two-part metric: (1) the proportion of claims that cite input evidence ($\geq 80\%$), and (2) the ratio of `[direct]` evidence to total evidence ($\geq 60\%$). The latter threshold ensures that personas are primarily responding to what is actually in the input material, rather than projecting their own assumptions.

**Persona Differentiation** employs Jaccard distance analysis on `key_issues` title sets across persona pairs. For each pair $(p_i, p_j)$:

$$d_J(p_i, p_j) = 1 - \frac{|K_i \cap K_j|}{|K_i \cup K_j|}$$

where $K_i$ is the set of key issue titles from persona $p_i$. The mean Jaccard distance across all pairs must be $\geq 0.3$. This is the whole of the implemented check: **the evaluator performs no statistical hypothesis test**. Earlier descriptions of this dimension specified a Kruskal-Wallis $H$ test at $p < 0.05$ and a mean across-persona score standard deviation of $\geq 0.5$; neither is implemented, and the project has no statistical-computing dependency that would support them. Adding a significance test is desirable — a mean Jaccard distance alone cannot distinguish genuine perspective diversity from noise — but until it exists we make no distributional claim.

**Stereotype Check** uses pattern matching to detect forbidden causal patterns. The system scans for regex patterns matching "as a [demographic]... therefore/so..." constructions and flags any output where demographic attributes are used as causal explanations. The threshold is zero tolerance: any detected violation results in a FAIL for this dimension.

**Structural Integrity** validates output against JSON Schema definitions and required section lists. Each task type has a defined set of required sections (e.g., consensus, major disagreements, priority fixes, information gaps, next human test recommendations). The threshold is 100% compliance—any missing required section results in a FAIL.

**Calibration Honesty** checks that all findings are correctly annotated with their epistemic status. Hypotheses must be labeled as such; confidence scores must reflect evidence strength; and caveats must be specific rather than generic. The threshold is 100% correct annotation.

**Risk Detection** verifies that the review identifies at least one critical or high-severity issue. This prevents the common failure mode where synthetic reviews produce uniformly positive feedback, missing genuine risks.

**Segment Conflict** ensures that persona segments exhibit meaningful disagreement. The threshold is $\geq 2$ meaningful disagreements, where "meaningful" is defined as disagreements on issues rated high or critical severity by at least one persona.

### 5.2 Persona Differentiation Analysis

To assess whether the 72 personas produce genuinely different perspectives, the system computes a Jaccard distance over the `key_issues` titles across persona pairs in a panel (Section 5.1). The 51 game personas span 8 packs with distinct behavioral profiles; the target mean Jaccard distance on `key_issues` is $\geq 0.5$ (deep differentiation) for personas from different packs and $\geq 0.3$ (basic differentiation) for personas within the same pack.

These targets are design intentions. We have not run this analysis over the shipped persona set and report no measured differentiation figures.

A differentiation criterion is also stated at persona *design* time: the `persona-generate` skill instructs that all persona pairs within a panel reach a Jaccard distance $\geq 0.3$ on their `motivations` + `decision_rules` sets, and that personas failing it be regenerated. We must be precise about the strength of this: `persona-generate` is a skill Markdown file executed by an LLM agent, so the criterion is an instruction the agent is asked to follow, **not a programmatic gate**. It should not be read as a guarantee about any persona pack in the repository.

### 5.3 Cross-Examination Effectiveness (proposed metrics; one now computable, neither measured)

We propose two metrics for evaluating cross-examination effectiveness. We state them so that the planned experiment in Section 5.0 is well-defined, and we distinguish which of them the implementation can now produce.

**Vote change rate** ($VCR$): The proportion of personas that change their stance between the pre- and post-rebuttal position. With a single rebuttal round the superscript $(3)$ of the original specification is the post-rebuttal stance:

$$VCR = \frac{|\{p_i : s_i^{(\text{post})} \neq s_i^{(\text{pre})}\}|}{n}$$

This quantity is computable from a shipped run — the numerator is the length of `vote_changes` and every entry carries its own before/after pair — but we have measured it on nothing. A caveat specific to our implementation: the denominator is the panel size while only the two most-opposed personas per controversy point are ever given the chance to change, so $VCR$ as defined is bounded well below 1 and is not comparable across panels of different sizes without normalising by the number of participating personas.

A healthy $VCR$ is in the range [0.1, 0.4]—too low suggests the cross-examination is not generating compelling counterarguments, while too high suggests excessive conformity or instability.

**Consensus shift** ($\Delta C$): The change in consensus strength between rounds:

$$\Delta C = \text{consensus\_strength}^{(3)} - \text{consensus\_strength}^{(1)}$$

Positive $\Delta C$ indicates convergence, negative indicates divergence, and near-zero indicates stability. The value of $\Delta C$ provides insight into whether the review material is inherently divisive (diverging) or has clear strengths/weaknesses that become apparent through debate (converging). **This one is not computable today**: consensus strength is calculated over the Round 1 stance distribution only and the aggregator is never re-run on post-rebuttal stances (Section 3.5), so the second term does not exist. Producing it requires re-aggregating after the rebuttal round, which is a small change we have not made.

### 5.4 Comparison with Single-Round Review

To quantify the value added by cross-examination, we propose a comparative evaluation between the implemented rebuttal tiers and a no-rebuttal baseline (equivalent to skipping Phases 5 and 7); Section 5.0 gives the three arms. The comparison is now mechanically runnable and has not been run. We hypothesize that:

1. Cross-examination will produce higher calibration honesty scores, as personas forced to defend their positions will reveal lower-confidence judgments.

2. Cross-examination will produce higher segment conflict scores, as the rebuttal process surfaces disagreements that might be obscured in independent reviews.

3. The vote change rate will correlate with the controversy of the input material—highly controversial materials will produce higher $VCR$ than uncontroversial ones.

We note that these hypotheses remain to be empirically validated, which we discuss in Section 7.

## 6. Ethical Considerations

### 6.1 Identity-Behavior Decoupling

The central ethical innovation of AudienceLens is the **identity-behavior decoupling principle**: persona judgments must be causally traceable to behavioral profiles and motivations, never to demographic attributes. This principle is motivated by the long-standing argument in UX research that behavior, goals, and context are more actionable persona attributes than demographics alone (Cooper 1999; Pruitt & Adlin 2006), and by the risk that synthetic personas could reinforce rather than challenge existing stereotypes.

In practice, this means that while persona *definitions* may carry demographic attributes (gender, age range, region), those attributes serve only to diversify the authored pool. They are explicitly prohibited from serving as causal explanations for preferences or judgments.

The enforcement is structural rather than instructional, and this is the point we most want to make about it. When a persona is prepared for a model call, `_minify_persona` serialises only a fixed `CORE_FIELDS` allowlist — `id`, `name`, `archetype`, `identity_summary`, `behavior_profile`, `motivations`, `decision_rules`, `quit_triggers`, `continue_triggers`, `first_scan_focus`, `review_output`. Gender, age, and region are not in that list, so **the model is never shown them**. A persona cannot write "as a female player, I prefer narrative games" on the basis of its own record, because it does not have that record; any preference it expresses has to come from the `behavior_profile` (e.g., high `emotional_engagement` plus high `novelty_seeking`), which is what the allowlist does contain.

We draw the distinction deliberately. A prompt that instructs a model not to reason from demographics is a request the model may or may not honour, and it degrades silently under paraphrase, model substitution, or a long context. Removing the fields from the payload changes what is possible rather than what is asked for, and it holds regardless of which model is behind the call. The residual risk is that a model infers demographics from a persona's name or `identity_summary`; the stereotype detector (Section 6.2) is the second line of defence against that, and it is a detector, not a guarantee.

### 6.2 Stereotype Detection

The stereotype detection system operates at two levels:

**Generation time** *(instruction, not a code gate)*: The `persona-generate` skill defines an ethics check phase (Phase 5) that scans generated personas for forbidden patterns, and its hard rules state that a FAIL may not be skipped. Because the skill is a Markdown specification executed by an LLM agent, this is a mandatory *instruction* rather than a programmatic barrier; we describe it as such and do not claim it is non-bypassable.

**Output time** *(implemented in code)*: Each persona's review output is scanned for forbidden causal patterns by the regex layer, and, when an API key is configured, by an LLM judge that catches rephrased demographic-to-behavior inferences. Detected violations feed the identity-behavior decoupling count that drives the ethics compliance score (Section 4.3) and the stereotype-check dimension of the Harness (Section 3.7). We note the limits of the current enforcement: the compliance score subtracts ten points per violation and is reported alongside the review, and the Harness dimension is a post-hoc score — neither suppresses or regenerates the offending output. A severity taxonomy (CRITICAL / HIGH / MEDIUM / LOW) with differentiated enforcement actions is a design goal and is not implemented.

### 6.3 MBTI Prohibition Rule

We treat MBTI labels as **optional fictional voice-shaping tags** rather than psychometric constructs. Following Pittenger (2005), we acknowledge that MBTI lacks robust psychometric validity. In AudienceLens, MBTI tags may appear in persona definitions solely as narrative flavoring for communication style (e.g., "communicates in structured, analytical language"), but are explicitly prohibited from serving as causal explanations for behavior or decision-making.

### 6.4 AI Act-Informed Design Considerations

AudienceLens is designed with reference to the EU AI Act. The following articles are addressed:

- **Article 50 (Transparency)**: Every report includes a prominent "AI-generated synthetic review, not real user research data" banner. This declaration cannot be removed or weakened.
- **Article 13 (Transparency of systems)**: The methodology, limitations, and validation status are publicly documented. AudienceLens explicitly labels its validation status as "pending validation" rather than "validated."
- **Article 14 (Human oversight)**: Every report includes "next human test recommendations," guiding users toward real-world validation.
- **Article 15 (Accuracy)**: The Harness 8-dimension framework provides a systematic accuracy assessment.
- **Article 12 (Record-keeping)**: Every persona output includes persona ID, version, and timestamp for traceability.

We do not claim legal compliance; these considerations reflect design intent rather than certified conformance.

### 6.5 Transparency and Calibration Honesty

A core design principle of AudienceLens is **calibration honesty**: the system must not overstate its capabilities or the reliability of its outputs. This manifests in several ways:

1. **Validation status transparency**: The system explicitly labels its outputs as "synthetic review, not real user research" and its validation status as "pending" rather than claiming accuracy rates that have not been independently verified.

2. **Confidence calibration**: Persona confidence scores are required to reflect evidence strength. A persona that lacks sufficient evidence must report low confidence rather than fabricating a confident judgment.

3. **Gap acknowledgment**: When input materials are insufficient for a persona to form a judgment, an evidence pre-check skips that persona and the skipped count is carried through to the report. A separate degradation banner is added when personas fail during the run, stating how many completed and that the conclusions rest only on those. We correct an earlier claim here: there is **no** rule that adds a prominent warning specifically when more than 30% of personas are skipped for insufficient evidence. The banner's trigger is failure count, not skip proportion. A skip-proportion warning would be a reasonable addition and is not present.

4. **Caveat specificity**: Each persona output must include at least one specific caveat (e.g., "this review is based on store page screenshots only; no hands-on demo was available, so手感 assessments are speculative"). Generic caveats like "for reference only" are rejected.

## 7. Limitations and Future Work

### 7.0 The Cross-Examination Protocol Runs, But Only One Round Of It, And It Has Not Been Evaluated

The headline mechanism now executes. Sections 3.3 and 3.4 describe a rebuttal round that issues real model calls in two tiers and a stance-revision gate applied in code; Section 4.6 records which parts of the original specification that covers. Three limitations follow, and we would rather state them plainly than let the word "implemented" carry more weight than it should.

**One round, not three.** What runs is: independent reviews, then one rebuttal exchange between the two most-opposed personas per controversy point, then done. There is no second exchange, no separate final-stance round, no early termination on convergence, and no panel-wide persuasion scoring. Anyone reading "multi-agent debate" as *iterated* debate — the setting in which the results of Du et al. (2024) and Wu et al. (2025) were obtained — will be reading in more than is there.

**Two tiers that are not equally deserving of the name.** `standard` mode, which is the default for most users, is a *single* moderated call that writes both sides' rebuttals from one vantage point. It is genuinely a rebuttal round, and it is genuinely not $n$ independent agents. Only `full` mode re-invokes each persona. We have kept this distinction in the runtime's own `limitation` string rather than only in this paper, precisely because the cheaper tier is the one most likely to be mistaken for the expensive one.

**No evaluation.** Implementing a mechanism is not evidence that it improves anything. We have not measured whether the rebuttal round increases persona differentiation, surfaces risks a single round misses, or merely adds cost and a veneer of deliberation. The vote-change count a report displays is a faithful record of what the models emitted; it is not evidence that the changes were epistemically warranted. Section 5.0 gives the experiment that would settle this, and it has not been run.

Consequently, AudienceLens's *validated* value remains where it was: in constraining synthetic review output — evidence provenance with a rejection threshold, demographics withheld from the model, a declared and annotated evaluation rubric. The rebuttal round is a working mechanism awaiting evidence, not a demonstrated improvement.

**Future work**: Evaluate what now exists (Section 5.0) before extending it. Then add the remaining rounds with cross-round state, so that consensus trajectory and tipping points become computable, and calibrate $\theta_{\text{change}}$ against data rather than judgment.

### 7.1 No Real-World Parity Study

The most significant limitation of AudienceLens is the absence of a controlled study comparing synthetic review outputs to real user research data. Commercial platforms such as SyntheticUsers claim high alignment with real users, but independent validation remains limited. We have designed the parity-check tool with a four-dimensional weighted scoring system (topic overlap: 0.30, score correlation: 0.25, stance alignment: 0.25, depth alignment: 0.20), but have not yet collected the real-user data necessary to compute these scores.

**Future work**: We plan to partner with academic institutions to conduct a controlled parity study, comparing AudienceLens outputs to real focus group results on identical materials. This study will establish baseline accuracy rates and identify systematic biases in synthetic review.

### 7.2 No Video/Voice Modality

Current personas evaluate text-based and image-based materials only. They cannot interact with live products, watch video content with audio, or experience immersive environments. This limits the system's applicability for evaluating interactive experiences, gameplay feel, or audio-visual impact.

**Future work**: Multi-modal persona evaluation, where personas can process video, audio, and interactive content. This requires integration with multi-modal LLM capabilities and potentially with browser automation tools for live product interaction.

### 7.3 No SOC 2 Certification

AudienceLens does not hold SOC 2 certification, which may limit its adoption in enterprise contexts where data handling compliance is required. The current skill-based architecture processes data locally (within the user's AI coding assistant), which mitigates some data handling concerns, but does not provide the formal assurance that SOC 2 certification offers.

**Future work**: SOC 2 Type II certification for a hosted version of AudienceLens, targeting enterprise customers who require formal compliance guarantees.

### 7.4 Empirically Set Thresholds

Several thresholds in the system (consensus threshold of 0.7, Jaccard distance threshold of 0.3, evidence coverage threshold, and the eight Harness thresholds) are set based on engineering judgment rather than empirical optimization. They may not be optimal, and we make no claim that they are. The confidence change threshold of 0.15 is now read and applied by the code (Section 3.3), which makes it consequential rather than inert — and therefore makes its lack of validation matter more, not less. Every stance change a report shows or withholds depends on a number nobody has tested.

**Future work**: Controlled experiments to calibrate these thresholds, using both synthetic and real-user data. We plan to use a grid search approach, varying each threshold independently and measuring the impact on Harness evaluation scores and parity metrics.

### 7.5 Over-Convergence Risk

Multi-agent debate systems are susceptible to over-convergence, where all agents converge to the same position regardless of the input quality. This risk is particularly acute when the underlying LLM has strong priors about what constitutes "good" or "bad" design. Both forms of the risk now apply to AudienceLens. The first is a shared model prior producing similar independent reviews across nominally different personas, which the Jaccard differentiation check is meant to surface but which we have not measured (Section 5.2). The second is capitulation during rebuttal, which the implemented protocol now genuinely exposes the system to. Three design choices are intended to mitigate it — opponent anonymity, prompts that state explicitly that holding one's position is a normal and common outcome, and a code-side gate that refuses to record a change the numbers do not support — and **none of the three has been shown to work.** We can demonstrate that the opponent's name is absent from the prompt and that the gate rejects sub-threshold changes; we cannot demonstrate that personas are not conforming for reasons the gate cannot see.

**Future work**: Investigation of convergence dynamics in the cross-examination protocol, including analysis of whether anchor points (personas resistant to persuasion) effectively prevent over-convergence, and whether the confidence threshold needs to be adaptive rather than fixed.

### 7.6 Scalability

The current system supports panels of 3–8 personas. Scaling to larger panels introduces computational costs and coordination challenges. The rebuttal round makes this concrete: `standard` mode adds exactly one call regardless of panel size, while `full` mode adds one call per persona per controversy point, so the marginal cost of the multi-agent tier grows with both. Rebuttal calls are counted and billed into the review's totals, and are reported separately in the cost summary, so the tradeoff is at least visible — but the system does not optimise it, and we have no evidence about which tier is worth its price (Section 5.0). The budget configuration file allows users to set token limits.

**Future work**: Adaptive panel sizing based on input complexity, and investigation of whether smaller panels with more targeted persona selection can achieve comparable quality to larger panels.

## 8. Conclusion

We have presented AudienceLens, an open-source prototype for synthetic audience review, and we have been explicit throughout about which of its mechanisms execute and which are specifications awaiting implementation.

What the system does best is constrain synthetic review output. Three mechanisms carry that weight. Evidence provenance is mandatory and enforced: every claim carries a `direct` / `inferred` / `gap` label, and a validator rejects outputs whose inferred share exceeds 40%, so a persona cannot pad a review with plausible invention and have it pass. Identity-behavior decoupling is structural rather than instructional: demographic fields are removed from the payload before it reaches the model, so demographic-causal reasoning is unavailable rather than discouraged — a property that survives a change of model, which a prompt instruction does not. And the 8-dimension Harness rubric keeps its thresholds in a single runtime-read file that ships annotated as unvalidated prototype values, so a reader can check every number in Section 3.7 against one file and see that the system does not claim more for them than we do.

A fourth mechanism has moved from specification to implementation since the previous version of this paper, and we describe the move precisely because the previous version was written to correct an overclaim. The cross-examination protocol now issues live rebuttal calls: `standard` mode makes one moderated call, `full` mode re-invokes each involved persona, `quick` mode makes none. Opposing arguments arrive stripped of their author's identity. Stance changes are decided by code comparing before and after against a configured threshold, not by asking the model whether it was persuaded, and changes the gate rejects are preserved as suppressed rather than dropped. When a rebuttal call fails, the runtime falls back to a derived summary and says why, in the report itself.

What the system still does not do is equally important, and implementing one round has not licensed the broader claim. The second and third rounds, early termination, panel-wide persuasion scoring, consensus-evolution classification, and tipping-point detection remain specifications; the identifiers for the last two appear nowhere in the codebase. Nor has the implemented round been evaluated: we report no measurement of whether it improves a review, and $\theta_{\text{change}} = 0.15$ is now consequential without being validated. We have not reinstated the worked example that earlier versions carried, because no artifact of that run is archived, and a number becoming producible is not the same as it becoming supported.

The remaining limitations are the familiar ones and we do not minimise them: no parity study against real user research, no multi-modal evaluation, no measured persona differentiation over the shipped pool, and thresholds set by engineering judgment rather than experiment. We think a narrow claim that survives a reader running `grep` over the repository is worth more than a broad one that does not — and that principle applies to what we have just built as firmly as it applied to what we had not.

AudienceLens is open-source under the MIT license, with CLI, Python, MCP, web, and Docker entry points, and ships 72 behavior-driven personas across 11 packs and 14 task types. We invite the research community to use, evaluate, and extend the system — including by implementing the protocol specified here — and we welcome collaborations for real-world validation studies.

## References

1. Argyle, L. P., Busby, E. C., Fulda, N., Gubler, J. R., Rytting, C., & Wingate, D. (2023). Out of one, many: Using language models to simulate human samples. *Political Analysis*, 31(3), 337–351. https://doi.org/10.1017/pan.2023.2

2. Chan, C.-M., Chen, W., Su, Y., Yu, J., Xue, W., Zhang, S., Fu, J., & Liu, Z. (2024). ChatEval: Towards better LLM-based evaluators through multi-agent debate. *The Twelfth International Conference on Learning Representations (ICLR 2024)*. arXiv:2308.07201.

3. Cooper, A. (1999). *The Inmates Are Running the Asylum*. Sams.

4. Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2024). Improving factuality and reasoning in language models through multiagent debate. *Proceedings of the 41st International Conference on Machine Learning (ICML 2024)*, PMLR 235, 11733–11763.

5. European Parliament and Council. (2024). Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (Artificial Intelligence Act). *Official Journal of the European Union*, L, 2024/1689.

6. Horton, J. J., Filippas, A., & Manning, B. S. (2023). *Large language models as simulated economic agents: What can we learn from Homo silicus?* (NBER Working Paper No. 31122). National Bureau of Economic Research. https://www.nber.org/papers/w31122

7. Lazar, J., Feng, J. H., & Hochheiser, H. (2017). *Research Methods in Human-Computer Interaction* (2nd ed.). Morgan Kaufmann.

8. Liang, T., He, Z., Jiao, W., Wang, X., Wang, Y., Wang, R., Yang, Y., Shi, S., & Tu, Z. (2024). Encouraging divergent thinking in large language models through multi-agent debate. *Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing (EMNLP 2024)*, 17889–17904.

9. Liu, Y. L., Yun, H., Roosta, T., & Xiao, Z. (2026). Synthetic users, real differences: An evaluation framework for user simulation in multi-turn conversations. arXiv:2605.02624.

10. Morgan, D. L. (1997). *Focus Groups as Qualitative Research* (2nd ed.). Sage Publications.

11. Mulder, S., & Yaar, Z. (2006). *The User Is Always Right: A Practical Guide to Creating and Using Personas for the Web*. New Riders.

12. Nielsen, J. (1994). *Usability Engineering*. Morgan Kaufmann.

13. Outset. (2024). AI-moderated interview platform [Commercial product]. https://outset.ai

14. Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)*. https://doi.org/10.1145/3586183.3606763

15. Pittenger, D. J. (2005). Cautionary comments regarding the Myers-Briggs Type Indicator. *Consulting Psychology Journal: Practice and Research*, 57(3), 210–221. https://doi.org/10.1037/1065-9293.57.3.210

16. Pruitt, J., & Adlin, T. (2006). *The Persona Lifecycle: Keeping People in Mind Throughout Product Design*. Morgan Kaufmann.

17. Synthetic Users. (2024). AI-moderated synthetic user research platform [Commercial product]. https://syntheticusers.com

18. Wu, H., Li, Z., & Li, L. (2025). Can LLM agents really debate? A controlled study of multi-agent debate in logical reasoning. arXiv:2511.07784.

19. Yabble. (2024). AI-powered survey and research platform [Commercial product]. https://yabble.com
