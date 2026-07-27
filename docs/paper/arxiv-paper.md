---
title: "AudienceLens: A Multi-Agent Cross-Examination Framework for Synthetic Audience Review"
authors:
  - name: 熵呓工作室
    affiliation: 熵呓工作室
abstract: |
  Traditional user research suffers from high cost, slow turnaround, and poor reproducibility. Recent advances in LLM-based persona simulation offer a promising alternative by generating synthetic user interviews at scale, but they also make it cheap to produce plausible-sounding "user feedback" that is grounded in nothing. We present AudienceLens, an open-source prototype for synthetic audience review whose implemented contributions are constraint mechanisms rather than simulation fidelity: (1) three-level evidence provenance — every claim is labelled `direct`, `inferred`, or `gap`, and a validator rejects any persona output whose inferred share exceeds 40%; (2) structural identity-behavior decoupling — demographic fields (gender, age, region) are removed from the persona payload before it reaches the model, so demographic-causal reasoning is unavailable rather than merely discouraged; (3) an 8-dimension Harness rubric whose thresholds live in a single configuration file read at runtime and ship with an explicit "prototype threshold, not empirically validated" annotation. We additionally specify, but have not implemented, a three-round cross-examination protocol with a confidence-gated vote-change mechanism and consensus-evolution tracking; in the current release (v0.3.0) the cross-examination section of a report is a summary derived from single-round persona outputs, and the runtime marks it as such (`mode: "derived_summary"`, `is_live_debate: false`, empty `vote_changes`). The release ships 66 behavior-driven personas across 10 packs and 14 task types. We discuss limitations including the absence of real-world parity studies, and outline a roadmap covering both the unimplemented mechanisms and their empirical validation.
keywords: [multi-agent systems, synthetic audience, cross-examination, persona simulation, LLM evaluation, AI ethics]
---

# AudienceLens: A Multi-Agent Cross-Examination Framework for Synthetic Audience Review

## Abstract

Traditional user research suffers from high cost, slow turnaround, and poor reproducibility. Recent advances in LLM-based persona simulation—exemplified by SyntheticUsers and similar platforms—offer a promising alternative by generating synthetic user interviews at scale. They also make it cheap to produce plausible-sounding "user feedback" that is grounded in nothing, which is the failure mode this work targets.

We present **AudienceLens**, an open-source prototype for synthetic audience review. Its implemented contributions are constraint mechanisms rather than simulation fidelity:

1. **Three-level evidence provenance with a hard cap.** Every claim in a persona output is labelled `direct`, `inferred`, or `gap`, and a validator rejects any output whose `inferred` share exceeds 40%.
2. **Structural identity-behavior decoupling.** Demographic fields (gender, age, region) are removed from the persona payload before it is serialised into the prompt, so demographic-causal reasoning is *unavailable to the model*, not merely discouraged by instruction.
3. **An 8-dimension Harness evaluation rubric** whose thresholds live in a single configuration file that the code reads at runtime and that ships with an explicit "prototype threshold, not empirically validated" annotation.

We additionally **specify, but have not implemented**, a three-round cross-examination protocol (position statement, rebuttal, final stance) with a confidence-gated vote-change mechanism ($\theta_{\text{change}} = 0.15$), change provenance, consensus-evolution classification, and tipping-point detection. In the current release (v0.3.0) no live multi-agent rebuttal is executed: the cross-examination section of a generated report is a summary derived from the single-round persona outputs, and the runtime labels it `mode: "derived_summary"`, `is_live_debate: false`, with an empty `vote_changes` list. Section 4.6 states the implementation status of each specified mechanism.

The release ships 66 behavior-driven personas across 10 YAML packs and 14 task types. We propose the identity-behavior decoupling principle and describe AI Act–informed design considerations. We discuss limitations including the absence of real-world parity studies, and outline a roadmap covering both the unimplemented mechanisms and their empirical validation. Empirical validation with real users remains future work for *all* components, implemented and specified alike.

## 1. Introduction

User research is the cornerstone of product development, yet it remains one of the most resource-intensive activities in the design cycle. A single round of moderated usability testing typically requires 2–4 weeks of planning, \$5,000–\$15,000 in participant compensation, and yields results that are difficult to replicate across sessions (Nielsen, 1994; Lazar et al., 2017). Focus groups, while efficient for gathering diverse perspectives, are susceptible to groupthink, anchoring bias, and the influence of dominant voices (Morgan, 1997). Survey-based methods scale more easily but sacrifice depth for breadth, producing statistical aggregates that obscure individual reasoning.

The emergence of large language models (LLMs) has opened a new frontier: *synthetic user research*. Commercial platforms such as SyntheticUsers claim high alignment with real users, but independent validation remains limited. Park et al. (2023) showed that generative agents can exhibit believable social behaviors in sandbox environments. Horton (2023) introduced *homo silicus*—computational agents that can serve as experimental subjects in economic studies. Argyle et al. (2023) demonstrated that a single LLM can simulate diverse subpopulations with surprising fidelity, capturing variation in attitudes and behaviors across demographic groups.

However, these approaches share a critical limitation: they treat synthetic user simulation as a *monologue* rather than a *dialogue*. Each persona responds independently, without exposure to opposing viewpoints, without the opportunity to revise their position, and without any mechanism for detecting when consensus is genuine versus superficial. This is fundamentally different from how real focus groups operate—where participants challenge each other's assumptions, shift their views in response to compelling arguments, and sometimes converge on unexpected positions.

We present **AudienceLens**, an open-source prototype for synthetic audience review. We separate what the current release (v0.3.0) actually executes from what it only specifies, because that distinction determines what a reader can rely on.

**Implemented contributions.**

1. **Three-level evidence provenance with a hard inferred-evidence cap.** Every claim in a persona output carries a `direct` / `inferred` / `gap` label, and a validator rejects outputs whose `inferred` share exceeds 40% (`src/runner/validator.py`). This is enforced in code, not requested in a prompt.

2. **Structural identity-behavior decoupling.** Demographic attributes are stripped from the persona record before serialisation: only a fixed `CORE_FIELDS` allowlist (behavior profile, motivations, decision rules, quit/continue triggers, first-scan focus) is injected into the prompt. The model never sees gender, age, or region, so demographic-causal reasoning is structurally unavailable rather than merely prohibited. A two-layer stereotype detector (regex first pass, plus an optional LLM judge when an API key is configured) inspects the output as a second line of defence.

3. **An 8-dimension Harness evaluation rubric** with thresholds declared in a single runtime-read configuration file (`src/harness/thresholds.yaml`) that ships with a machine-readable "prototype threshold, not empirically validated" annotation. We describe it as a *post-hoc scorecard, not a gate*: it is disabled by default, runs after a review completes, and does not filter, block, or re-run any persona output.

4. **An open-source implementation** (MIT) with CLI, Python API, MCP server, web, and Docker entry points, shipping 66 behavior-driven personas across 10 YAML packs and 14 task types, with presets for six model providers.

**Design contribution, specified but not implemented.**

5. **A three-round cross-examination protocol** (position statement, rebuttal, final stance) with a confidence-gated vote-change mechanism ($\Delta c > \theta_{\text{change}}$, $\theta_{\text{change}} = 0.15$), full change provenance, consensus-evolution classification into four patterns, and tipping-point detection. Sections 3.3–3.6 give the specification; **Section 4.6 documents that none of it executes in v0.3.0.** In brief: the cross-examination block in a generated report is a summary derived from the single-round persona outputs, labelled `mode: "derived_summary"` and `is_live_debate: false` by the runtime itself; `vote_changes` is always empty and the reported confidence delta is hard-coded to zero; $\theta_{\text{change}} = 0.15$ exists only in a configuration file and in prompt text, with no Python module reading it; and consensus-evolution and tipping-point detection have no implementation at all.

**Normative contribution.**

6. **The identity-behavior decoupling principle**: the position that persona judgments must be causally traceable to behavioral profiles and motivations, never to demographic attributes (gender, age, region, MBTI). Contribution 2 is its implemented enforcement.

The remainder of this paper is organized as follows: Section 2 reviews related work; Section 3 presents our method, including both implemented and specified-only mechanisms; Section 4 details the implementation and, in Section 4.6, its status against the specification; Section 5 describes the evaluation framework; Section 6 discusses ethical considerations; Section 7 addresses limitations and future work; and Section 8 concludes.

## 2. Related Work

### 2.1 Generative Agents and Persona Simulation

The foundation of synthetic audience research lies in the ability of LLMs to adopt and maintain consistent personas. Park et al. (2023) introduced generative agents that inhabit a sandbox town, exhibiting emergent social behaviors including relationship formation, event coordination, and information diffusion. Their architecture—comprising memory streams, reflection, and planning—demonstrated that LLM-based agents can maintain behavioral coherence over extended interactions.

Argyle et al. (2023) showed that LLMs can simulate diverse subpopulations when conditioned on demographic profiles, capturing inter-group variation in attitudes and opinions. Their "silicon subjects" approach suggested that LLMs could serve as inexpensive proxies for human survey respondents, though they cautioned against treating synthetic responses as equivalent to real human data.

Horton (2023) extended this line of work to economics, introducing *homo silicus*—computational agents that participate in economic experiments. He argued that LLM-based agents could serve as "lossless" compression of human economic behavior, enabling rapid iteration on experimental designs before committing to costly human studies.

More recently, persona simulation has been applied to software engineering contexts. Xu et al. (2024) demonstrated that LLM personas can simulate diverse user perspectives in requirements engineering, while Salehi et al. (2024) used persona-driven evaluation to assess the accessibility of web applications.

### 2.2 Synthetic User Research

Commercial synthetic user research platforms have emerged to address the cost and speed limitations of traditional methods. **SyntheticUsers** (2024) is a commercial platform offering AI-moderated interviews with synthetic participants. Commercial platforms such as SyntheticUsers claim high alignment with real users, but independent validation remains limited. Their approach uses OCEAN (Big Five) personality models to construct persona profiles and generates interview-style responses. However, SyntheticUsers operates in a single-turn interview paradigm—each persona responds to questions independently, without exposure to other personas' viewpoints.

**Outset** takes a hybrid approach, using AI to moderate real human interviews at scale. While this preserves the authenticity of human responses, it does not address the cost and speed limitations that motivate synthetic approaches. **Yabble** offers AI-powered survey analysis but relies on single-turn interactions with demographic-tagged personas, which risks reinforcing stereotypes rather than capturing genuine behavioral diversity.

These platforms share three limitations: (1) no cross-examination between personas; (2) no mechanism for stance revision; and (3) no systematic quality evaluation framework for synthetic review outputs. AudienceLens addresses (3) with an implemented evaluation rubric (Section 3.7) and offers a specification — but not yet an implementation — for (1) and (2) (Sections 3.3–3.6, status in Section 4.6).

### 2.3 Multi-Agent Debate

Du et al. (2023) demonstrated that multi-agent debate can improve factuality and reasoning in language models. In their framework, multiple LLM instances argue for different positions, with each agent refining its response based on others' arguments. This approach improved performance on mathematical reasoning and factual question-answering tasks, suggesting that adversarial interaction can surface errors that single-agent generation misses.

Liang et al. (2023) extended this work to encourage diversity in multi-agent debate, showing that enforcing distinct perspectives leads to more robust consensus formation. Chan et al. (2023) proposed chatmap for scaling multi-agent collaboration, demonstrating that structured interaction protocols outperform unstructured group chat.

Wang et al. (2024) introduced a framework for multi-agent consensus through iterative debate, showing that convergence properties depend on the topology of agent interactions and the strength of evidence. Their work highlighted the risk of premature consensus—agents converging too quickly without fully exploring the argument space.

AudienceLens builds on these insights by *specifying* a structured three-round debate protocol with explicit mechanisms for stance revision and consensus tracking. Unlike general multi-agent debate, the protocol is designed for the audience review domain, where the goal is not to find a single correct answer but to map the landscape of perspectives and identify areas of genuine disagreement. We stress that this protocol is a design contribution of this paper: the current implementation does not execute it (Section 4.6). Consequently we make no empirical claim about its behaviour, and readers should not treat the debate literature cited above as evidence for AudienceLens's outputs.

### 2.4 AI Ethics in Persona Generation

The ethical dimensions of synthetic persona generation have received increasing attention. Prior UX research has long argued that behavior, goals, and context are more actionable persona attributes than demographics alone (Cooper 1999; Pruitt & Adlin 2006). This insight directly motivates our identity-behavior decoupling principle.

The EU AI Act (2024) establishes transparency requirements for AI systems, including obligations to disclose when content is AI-generated (Article 50), ensure human oversight (Article 14), and maintain accuracy (Article 15). These requirements are particularly relevant for synthetic audience systems, where outputs could be misinterpreted as real user research data.

The Nielsen Norman Group's persona methodology has long advocated for behavior-first persona design, arguing that personas should be defined by goals, behaviors, and pain points rather than demographic attributes (Mulder & Yaar, 2006). AudienceLens operationalizes this principle through its `behavior_profile` construct, which replaces traditional OCEAN-based personality models with task-oriented behavioral dimensions.

## 3. Method

### 3.1 System Architecture

The persona pool comprises **66 personas across 10 YAML packages**, serving **14 task types**. All counts below can be verified against `src/personas/` and the single authoritative registry `VALID_TASK_TYPES` in `src/runner/task_types.py`:

| Persona domain | Packages | Personas | Task types served |
|---|---|---|---|
| Game | 8 (`game-core` 16, `mobile-f2p` 7, `competitive-esport` 5, `family-casual` 5, `indie-creative` 5, `accessibility` 4, `educational-serious` 4, `vr-immersive` 4) | 50 | 10 (`steam_page_review`, `demo_first_play`, `concept_review`, `monetization_review`, `looking_for_party_post`, `update_announcement_review`, `devlog_review`, `kickstarter_review`, `localization_review`, `discord_community_review`) |
| General product | 1 (`general-consumer` 8) | 8 | 3 (`product_feedback_review`, `pricing_page_review`, `onboarding_review`) |
| Startup / pitch | 1 (`startup-panel` 8) | 8 | 1 (`pitch_review`) |
| **Total** | **10** | **66** | **14** |

Three review skills (`synthetic-playtest`, `audience-panel`, `red-team-audience`) and one meta-skill (`persona-generate`) are defined as skill-pack front-ends over this pool. Two clarifications are needed here, because earlier descriptions of this system were inaccurate on both points. First, **`red-team-audience` has no persona pack of its own**: no red-team personas ship in `src/personas/`, and "red team" exists only as a skill-level framing over the existing pool, not as a distinct set of persona definitions. Second, `persona-generate` is an LLM-driven authoring workflow specified in a skill Markdown file, not a code path; the personas it produces are new YAML packs, not runtime entities.

A key architectural property is **context isolation** between personas. Each persona review is an independent, stateless model call dispatched from a thread pool (`concurrent.futures.ThreadPoolExecutor` in `src/runner/cli.py`); a call receives only its own persona payload, the target material, and the task rubric. No conversation state, reasoning trace, or intermediate result is shared between persona calls. This prevents cross-contamination, where one persona's reasoning leaks into another's. Note that we describe threads with per-call prompt construction, not OS subprocesses; the isolation guarantee comes from the calls being stateless and independently prompted, not from process boundaries. The "influence propagates through a shared position pool" property described in Section 3.3 belongs to the cross-examination specification and is not exercised in v0.3.0 (Section 4.6).

### Context Isolation Implementation

Items 1, 2, and 4 below describe the implemented pipeline. **Items 3 and 5 describe the cross-examination specification and are not executed in v0.3.0** (Section 4.6); they are stated here for completeness of the design.

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

3. **Rebuttal Phase** *(specified; not implemented)*: In the specified cross-examination rounds, persona agents would receive anonymized controversy claims, selected opposing arguments filtered by relevance, and their own previous output for reference. No such round is executed in v0.3.0.

4. **Position Pool** *(implemented as an aggregation input)*: Persona outputs are stored as structured JSON objects containing stance, confidence, key_issues, and evidence arrays, and are consumed by the aggregation layer rather than by individual persona agents. In v0.3.0 this pool is read only once, after the single review round.

5. **Anonymised attribution** *(specified; the shipped prompt template does the opposite)*: The design intent is that persona names be excluded from rebuttal prompts and arguments attributed only by argument ID (e.g., "Argument A3"), so that agents cannot form coalitions based on identity. **We must report that the shipped template does not do this.** `src/templates/cross-exam-prompt.md` interpolates `{{pro_persona_name}}` and `{{con_persona_name}}` directly into the prompt body. Since no rebuttal round is executed, this template is never sent to a model in v0.3.0 and the discrepancy has no effect on current outputs — but the anonymisation property must not be claimed as a validity guarantee of this system, and we do not claim it.

The system operates in nine phases, numbered 0–8: (0) argument parsing, (1) task type validation, (2) material loading, (3) panel selection, (4) parallel persona reviews, (5) cross-examination, (6) report aggregation, (7) calibration check, and (8) output generation. Phases 5 and 7 are skipped in `quick` mode; all phases execute in `full` mode. Phase 5 in `full` mode produces a derived summary rather than a live debate (Section 4.6).

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

This design departs from the OCEAN (Big Five) personality model used by SyntheticUsers. We argue that `behavior_profile` is better suited for review tasks for four reasons:

1. **Task orientation**: Review is a task-oriented behavior, not a social one. OCEAN dimensions like extraversion and agreeableness primarily describe social interaction patterns, which are largely irrelevant when personas evaluate artifacts independently. `behavior_profile` directly models task-relevant behaviors (patience, completion drive, risk tolerance), yielding higher information density per dimension.

2. **Predictive vs. descriptive**: OCEAN answers "what kind of person is this?" while `behavior_profile` answers "what will this persona do in a review task?" The latter directly serves output interpretability and traceability.

3. **Reduced collinearity**: In review contexts, OCEAN's conscientiousness and openness dimensions influence review behavior in highly similar ways (both manifest as attention to detail). `behavior_profile` decomposes these into finer-grained behavioral drivers (`completion_drive` vs. `novelty_seeking`), avoiding dimensional redundancy.

4. **Direct traceability**: Our ethics framework requires all judgments to be traceable to `behavior_profile` or `motivations`. Using OCEAN labels would introduce an indirect mapping layer, increasing the complexity of compliance auditing.

The mapping between OCEAN and `behavior_profile` is as follows: openness_to_experience maps to `novelty_seeking` + `tolerance_for_ambiguity`; conscientiousness maps to `completion_drive` + `patience`; extraversion maps to `social_influence`; agreeableness maps inversely to `emotional_engagement`; and neuroticism maps inversely to `risk_tolerance`.

Each persona also includes `decision_rules`—explicit conditional statements that govern judgment (e.g., "if the core hook is not visible within 15 seconds, do not wishlist"), `quit_triggers` and `continue_triggers` that define retention/attrition boundaries, and `evidence_types_needed` that specify what evidence the persona requires to form grounded judgments.

### Persona Taxonomy

| Package | Count | Domain | Key Behaviors |
|---------|-------|--------|---------------|
| game-core | 16 | Game | Core exploration, system analysis |
| mobile-f2p | 7 | Game | Monetization sensitivity, session design |
| indie-creative | 5 | Game | Innovation focus, aesthetic judgment |
| competitive-esport | 5 | Game | Skill ceiling, balance, fairness |
| family-casual | 5 | Game | Accessibility, onboarding, safety |
| vr-immersive | 4 | Game | Immersion, comfort, presence |
| educational-serious | 4 | Game | Learning outcomes, engagement |
| accessibility | 4 | Game | Keyboard/screen/cognitive access |
| general-consumer | 8 | Product | Everyday product/app evaluation, pricing, onboarding |
| startup-panel | 8 | Startup | Business plan, pitch deck, market and funding scrutiny |
| **Total** | **66** | | |

Each persona is defined by a complete behavior_profile, motivations, decision_rules, quit_triggers, and continue_triggers. The 66-persona count reflects coverage across domains, not redundancy; Jaccard distance analysis (Section 5.2) measures actual differentiation. This is the complete inventory as of the v0.3.0 release: there is no red-team persona pack, and the product-facing pool is 16 personas in two packs, not the six finer-grained packs described in earlier drafts of this work.

### 3.3 Cross-Examination Protocol (specification; not implemented in v0.3.0)

> **Implementation status.** Sections 3.3 through 3.6 specify a protocol that the current release does not execute. There is no live multi-agent rebuttal: no LLM call is made for cross-examination, `vote_changes` is always empty, the reported confidence delta is hard-coded to zero, and $\theta_{\text{change}}$ is read by no code path. Section 4.6 gives the per-mechanism status. Everything in these four sections should be read as a design proposal, not as a description of system behaviour, and no result reported anywhere in this paper depends on it.

The cross-examination protocol is the core *intended* differentiator of AudienceLens. As specified, it proceeds in three rounds:

**Round 1: Position Statement.** Each persona independently reviews the input material and produces a structured output including scores, key issues, evidence, and a primary stance. All outputs are collected into a shared position pool. Critically, personas are not aware of each other's existence at this stage—they evaluate the material in complete isolation.

**Round 2: Rebuttal.** The system extracts the top-$k$ controversy points from Round 1 outputs, ranked by the variance of severity ratings across personas. For each controversy point, the system identifies the two personas holding the most opposed positions and generates structured arguments (claim + evidence + reasoning chain) for each side. All personas then evaluate each argument's persuasiveness on a 1–5 scale. If a persona's confidence changes by more than the threshold ($\Delta c > 0.15$), they may update their stance and must document the reason.

**Round 3: Final Stance.** Each persona produces their final position, which may differ from their Round 1 stance if they changed their view during rebuttal. The system records the complete trajectory: initial stance, confidence trajectory, any stance changes, and the triggering arguments.

The protocol terminates early if two consecutive rounds produce no stance changes, indicating convergence.

Formally, let $P = \{p_1, p_2, \ldots, p_n\}$ be the set of personas. In Round 1, each $p_i$ produces output $o_i^{(1)} = (s_i^{(1)}, c_i^{(1)}, e_i^{(1)})$ where $s_i^{(1)}$ is the stance, $c_i^{(1)} \in [0,1]$ is the confidence, and $e_i^{(1)}$ is the evidence set. The controversy points $C = \{c_1, \ldots, c_k\}$ are extracted by:

$$C = \text{top-}k \left(\text{argsort}_{j} \left(\text{Var}(\{s_{1,j}^{(1)}, \ldots, s_{n,j}^{(1)}\})\right)\right)$$

where $s_{i,j}^{(1)}$ denotes persona $p_i$'s severity rating on issue $j$. In Round 2, each persona evaluates the persuasiveness of arguments for and against each controversy point, producing updated confidence $c_i^{(2)}$. A stance change is permitted when:

$$|c_i^{(2)} - c_i^{(1)}| > \theta_{\text{change}}$$

where $\theta_{\text{change}} = 0.15$. Note: $\theta_{\text{change}}$ is a proposed engineering parameter, set to 0.15 for the specification. It is not empirically validated and would need to be tuned per model and domain. In the current codebase the value appears only in `src/config/aggregation-rules.yaml` and in prompt text; no Python module reads it, so it is presently inert.

### 3.4 Vote Change Mechanism (specification; not implemented in v0.3.0)

The vote change mechanism is designed to model realistic opinion dynamics while preventing cascading conformity. Key design choices:

**Confidence threshold.** A persona may only change stance when their confidence shifts by more than $\theta_{\text{change}}$. This threshold was chosen to be large enough to filter out noise (minor fluctuations in LLM output probabilities) while small enough to capture genuine persuasion. We acknowledge this value is empirically set and plan to calibrate it through controlled experiments in future work. We do not interpret self-reported confidence as calibrated probability; LLM confidence scores may not reflect true epistemic uncertainty.

**Change provenance.** Under the specification, every stance change would be recorded with: (1) the triggering argument and its source persona; (2) the confidence before and after; (3) the confidence delta; and (4) a free-text reason provided by the changing persona. Such a provenance chain would enable post-hoc analysis of persuasion dynamics. In v0.3.0 the `vote_changes` array in the cross-examination result is constructed empty and never populated, and the `delta` field of every `confidence_changes` entry is hard-coded to 0, so no provenance data is produced.

**Anti-collusion design.** Personas cannot directly communicate; under the specification, influence would propagate only through the shared position pool, which is intended to prevent the "echo chamber" effect and ensure that any stance change is driven by argument quality rather than social pressure. We note two caveats. First, the corresponding argument-anonymisation property is not present in the shipped prompt template (Section 3.1, item 5). Second, because no rebuttal round runs, this design has never been exercised and we present no evidence that it achieves its aim.

**No majority weighting.** The system does not weight personas by their agreement with the majority. A single persona holding a minority position is as valid as five personas in agreement—the value lies in understanding *why* they disagree, not in counting votes.

### 3.5 Consensus Evolution Tracking (specification; not implemented in v0.3.0)

> **Implementation status.** No consensus-evolution mechanism exists in the codebase. The identifiers `consensus_strength`, `converging`, `diverging`, `oscillating`, `tipping_point`, and `cascade_point` do not appear anywhere under `src/`. What the system actually computes is a *single-round* stance distribution in `src/runner/aggregator.py`, using a `consensus_threshold` of 0.7 read from `src/config/aggregation-rules.yaml`. There is no multi-round trajectory to classify, and no divergence-hotspot or polarization output. The remainder of this subsection specifies what such a mechanism would compute.

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

Tipping points are moments where the discussion trajectory changes qualitatively. The specification defines three types; **none of them is detected by the current implementation**, which has no cross-round state to compare:

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

Each persona agent is defined as a standalone Markdown file (e.g., `P01-indie-core-operator.md`) that the skill dispatcher loads and injects into the LLM context when that persona is selected for a review panel. Note that the 50 agent Markdown files mirror the game pool only; the canonical persona definitions used by the Python engine are the 10 YAML packs under `src/personas/`.

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

The numbers were not reproducible from the system as implemented. Three of them were not merely unverified but unreachable: the ethics compliance score can only take multiples of ten (Section 4.3), so 72 is not in its range, and the attributed cause — insufficient calibration honesty — is not among that score's inputs; the "2 of 6 personas changed stance" figure depends on the vote-change mechanism, which produces an empty result set (Section 3.4); and "31/40 (threshold 28)" is not a scale the evaluator emits, which reports a weighted mean in $[1,5]$ (Section 3.7). No input or output artifact from that run is archived in the repository. Presenting such figures — even under a disclaimer that they do not constitute empirical validation — would still tell a reader that the system performs cross-examination and tipping-point detection, which is the specific misreading this paper is trying to prevent.

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
| Live three-round rebuttal between personas | 3.3 | **Not implemented.** Runtime returns `mode: "derived_summary"`, `is_live_debate: false`, and a `limitation` string stating no live rebuttal was executed. The rendered cross-examination prompt is never sent to a model. | `src/runner/cross_exam.py`, `src/runner/cli.py` |
| Vote-change mechanism and change provenance | 3.4 | **Not implemented.** `vote_changes` is always empty; every confidence `delta` is hard-coded to 0. | `src/runner/cross_exam.py` |
| Confidence threshold $\theta_{\text{change}} = 0.15$ | 3.3 | **Inert.** Present in a YAML file and in prompt text; no Python module reads it. | `src/config/aggregation-rules.yaml` |
| Consensus evolution across rounds (converging / diverging / stable / oscillating) | 3.5 | **Not implemented.** None of these identifiers exists under `src/`. | — |
| Tipping-point and cascade-point detection | 3.6 | **Not implemented.** Neither identifier exists under `src/`. | — |
| Argument anonymisation in rebuttal prompts | 3.1 | **Not implemented, and the shipped template does the opposite** (interpolates persona names). Unexercised, since no rebuttal runs. | `src/templates/cross-exam-prompt.md` |
| Kruskal-Wallis test / score standard-deviation check | 5.1 | **Not implemented.** The differentiation dimension computes Jaccard distance only; the project has no statistical-testing dependency. | `src/harness/evaluator.py` |
| Warning when $>30\%$ of personas are skipped for insufficient evidence | 6.5 | **Not implemented.** A degradation banner exists but triggers on model-call failures, not on evidence-based skips. | `src/runner/cli.py` |
| Automated regression suite | — | **Implemented**: 394 engine tests and 294 backend tests (1 skipped) pass as of the v0.3.0 tag; counts move with development. | `tests/`, `web/backend/tests/` |

## 5. Evaluation

### 5.0 Planned Evaluation Design

To validate the effectiveness of cross-examination, we plan the following controlled experiment:

**Design**: A/B comparison between single-round review and three-round cross-examination.

**Protocol**:
- **Group A (Baseline)**: Each persona independently reviews the target material and produces a single review output, with no interaction between personas.
- **Group B (Cross-Examination)**: Personas first produce independent reviews, then engage in three rounds of cross-examination (position statement, rebuttal, final stance), with vote-change tracking.

**Materials**: 4 standard fixtures (2 high-quality, 2 low-quality inputs) spanning game concepts and product landing pages.

**Metrics**: Harness 8-dimension scores, persona differentiation (Jaccard distance), actionability ratio, risk detection coverage, and human evaluator preference ratings.

**Hypothesis**: Group B will show higher persona differentiation, better risk detection, and more actionable recommendations than Group A, at the cost of increased token usage.

This evaluation has not been conducted. It also cannot be conducted against v0.3.0 as released: Group B requires a live cross-examination implementation, which does not exist (Section 4.6). Implementing the protocol is therefore a prerequisite for this experiment, not merely a step in running it.

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

To assess whether the 66 personas produce genuinely different perspectives, the system computes a Jaccard distance over the `key_issues` titles across persona pairs in a panel (Section 5.1). The 50 game personas span 8 packs with distinct behavioral profiles; the target mean Jaccard distance on `key_issues` is $\geq 0.5$ (deep differentiation) for personas from different packs and $\geq 0.3$ (basic differentiation) for personas within the same pack.

These targets are design intentions. We have not run this analysis over the shipped persona set and report no measured differentiation figures.

A differentiation criterion is also stated at persona *design* time: the `persona-generate` skill instructs that all persona pairs within a panel reach a Jaccard distance $\geq 0.3$ on their `motivations` + `decision_rules` sets, and that personas failing it be regenerated. We must be precise about the strength of this: `persona-generate` is a skill Markdown file executed by an LLM agent, so the criterion is an instruction the agent is asked to follow, **not a programmatic gate**. It should not be read as a guarantee about any persona pack in the repository.

### 5.3 Cross-Examination Effectiveness (proposed metrics; not computable in v0.3.0)

We propose two metrics for evaluating cross-examination effectiveness. Neither can be computed from the current implementation, since both require the multi-round stance data that v0.3.0 does not produce (Section 4.6). We state them so that the planned experiment in Section 5.0 is well-defined.

**Vote change rate** ($VCR$): The proportion of personas that change their stance between Round 1 and Round 3:

$$VCR = \frac{|\{p_i : s_i^{(3)} \neq s_i^{(1)}\}|}{n}$$

A healthy $VCR$ is in the range [0.1, 0.4]—too low suggests the cross-examination is not generating compelling counterarguments, while too high suggests excessive conformity or instability.

**Consensus shift** ($\Delta C$): The change in consensus strength between rounds:

$$\Delta C = \text{consensus\_strength}^{(3)} - \text{consensus\_strength}^{(1)}$$

Positive $\Delta C$ indicates convergence, negative indicates divergence, and near-zero indicates stability. The value of $\Delta C$ provides insight into whether the review material is inherently divisive (diverging) or has clear strengths/weaknesses that become apparent through debate (converging).

### 5.4 Comparison with Single-Round Review

To quantify the value added by cross-examination, we propose a comparative evaluation between the specified three-round protocol and a single-round baseline (equivalent to skipping Phases 5 and 7). This comparison is contingent on the protocol first being implemented (Section 4.6). We hypothesize that:

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

### 7.0 The Cross-Examination Protocol Is Not Implemented

The most consequential limitation of this work is that its headline mechanism does not run. Sections 3.3–3.6 specify a three-round debate protocol, a confidence-gated vote-change mechanism, consensus-evolution classification, and tipping-point detection; Section 4.6 documents that v0.3.0 implements none of them. What the system does today is a single round of isolated persona reviews followed by aggregation, with a cross-examination report section derived from those single-round outputs and labelled as derived by the runtime itself.

This bounds the contribution of the paper honestly. AudienceLens's implemented value is in *constraining* synthetic review output — evidence provenance with a rejection threshold, demographics withheld from the model, a declared and annotated evaluation rubric — not in multi-agent deliberation. Readers evaluating whether to build on this system should treat Sections 3.3–3.6 as a specification they would have to implement, and should not cite this work as evidence about the behaviour of multi-agent debate.

**Future work**: Implement the protocol. Concretely, this requires wiring the already-rendered cross-examination prompt to a model call, populating `vote_changes` from parsed model output, making $\theta_{\text{change}}$ a read parameter rather than a dormant configuration key, and adding cross-round state so that consensus trajectory and tipping points become computable. The specification and the prompt template already exist; the missing piece is execution and the evaluation that would follow it (Section 5.0).

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

Several thresholds in the system (consensus threshold of 0.7, Jaccard distance threshold of 0.3, evidence coverage threshold, and the eight Harness thresholds) are set based on engineering judgment rather than empirical optimization. They may not be optimal, and we make no claim that they are. The confidence change threshold of 0.15 is a further case: it is not merely unvalidated but currently unused, since no code path reads it (Section 4.6).

**Future work**: Controlled experiments to calibrate these thresholds, using both synthetic and real-user data. We plan to use a grid search approach, varying each threshold independently and measuring the impact on Harness evaluation scores and parity metrics.

### 7.5 Over-Convergence Risk

Multi-agent debate systems are susceptible to over-convergence, where all agents converge to the same position regardless of the input quality. This risk is particularly acute when the underlying LLM has strong priors about what constitutes "good" or "bad" design. Two points follow. In v0.3.0 the risk does not arise from debate, because no debate occurs; it arises instead from a shared model prior producing similar single-round reviews across nominally different personas, which the Jaccard differentiation check is meant to surface but which we have not measured (Section 5.2). Once the protocol of Section 3.3 is implemented, the debate form of the risk applies, and the isolation design is intended to mitigate it — but that mitigation is untested, and we make no claim that it works.

**Future work**: Investigation of convergence dynamics in the cross-examination protocol, including analysis of whether anchor points (personas resistant to persuasion) effectively prevent over-convergence, and whether the confidence threshold needs to be adaptive rather than fixed.

### 7.6 Scalability

The current system supports panels of 3–8 personas. Scaling to larger panels introduces computational costs (each persona requires a separate LLM call) and coordination challenges (more controversy points to process in cross-examination). The budget configuration file allows users to set token limits, but the system does not currently optimize for cost-quality tradeoffs.

**Future work**: Adaptive panel sizing based on input complexity, and investigation of whether smaller panels with more targeted persona selection can achieve comparable quality to larger panels.

## 8. Conclusion

We have presented AudienceLens, an open-source prototype for synthetic audience review, and we have been explicit throughout about which of its mechanisms execute and which are specifications awaiting implementation.

What the system does today is constrain synthetic review output rather than simulate deliberation. Three mechanisms carry that weight. Evidence provenance is mandatory and enforced: every claim carries a `direct` / `inferred` / `gap` label, and a validator rejects outputs whose inferred share exceeds 40%, so a persona cannot pad a review with plausible invention and have it pass. Identity-behavior decoupling is structural rather than instructional: demographic fields are removed from the payload before it reaches the model, so demographic-causal reasoning is unavailable rather than discouraged — a property that survives a change of model, which a prompt instruction does not. And the 8-dimension Harness rubric keeps its thresholds in a single runtime-read file that ships annotated as unvalidated prototype values, so a reader can check every number in Section 3.7 against one file and see that the system does not claim more for them than we do.

What the system does not do is equally important. The three-round cross-examination protocol, the vote-change mechanism, consensus-evolution classification, and tipping-point detection are specifications in this paper, not behaviours of the release. The runtime says so itself — it labels its own cross-examination output as derived rather than debated — and Section 4.6 records the status of each mechanism against the file where it can be verified. We have removed the worked example that earlier versions of this paper carried, because its figures were not reproducible and two of them depended on mechanisms that do not exist.

The remaining limitations are the familiar ones and we do not minimise them: no parity study against real user research, no multi-modal evaluation, no measured persona differentiation over the shipped pool, and thresholds set by engineering judgment rather than experiment. The result is a narrower paper than its earlier drafts. We think a narrow claim that survives a reader running `grep` over the repository is worth more than a broad one that does not.

AudienceLens is open-source under the MIT license, with CLI, Python, MCP, web, and Docker entry points, and ships 66 behavior-driven personas across 10 packs and 14 task types. We invite the research community to use, evaluate, and extend the system — including by implementing the protocol specified here — and we welcome collaborations for real-world validation studies.

## References

1. Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)*, 1–22. ✅ Reliable; peer-reviewed venue.

2. Argyle, L. P., Busby, E. C., Fulda, N., Gubler, J. R., Rytting, C., & Wingate, D. (2023). Out of one, many: Using language models to simulate human samples. *Political Analysis*, 31(3), 337–351. ✅ Reliable; peer-reviewed venue.

3. Horton, J. J. (2023). Homo silicus: A new kind of social scientist. *SSRN Electronic Journal*. https://doi.org/10.2139/ssrn.4434769 ✅ Retained; note corrected subtitle "A New Kind of Social Scientist."

4. Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2023). Improving factuality and reasoning in language models through multiagent debate. *Proceedings of the 40th International Conference on Machine Learning (ICML '23)*. ✅ Reliable; peer-reviewed venue.

5. Liang, T., Chen, Z., He, J., Wang, M., Zhou, Y., & Zhang, Z. (2023). Encouraging divergent thinking in large language models through multi-agent debate. *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*. ⚠️ <!-- TODO: verify venue and exact title -->

6. SyntheticUsers. (2024). SyntheticUsers: AI-moderated synthetic user research platform [Commercial product]. https://syntheticusers.com ⚠️ Commercial citation; not peer-reviewed. Should not be cited as academic evidence.

7. ~~Mancini, T., et al. (2024). SCOPE: Demographics explain minimal behavioral variance in user research.~~ ❌ Specific 1.5% figure removed; replaced with domain consensus references (Cooper 1999; Pruitt & Adlin 2006). The SCOPE study's specific quantitative claims could not be independently verified.

8. European Parliament and Council. (2024). Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (Artificial Intelligence Act), Article 50. *Official Journal of the European Union*. ✅ Updated to correct article number (Article 50, not Article 52).

9. Pittenger, D. J. (2005). Cautionary comments regarding the Myers-Briggs Type Indicator. *Consulting Psychology Journal: Practice and Research*, 57(3), 210–221. ✅ Reliable; peer-reviewed venue.

10. Wang, Z., Mao, S., & Wang, W. (2024). Multi-agent consensus through iterative debate with convergence guarantees. *Proceedings of the AAAI Conference on Artificial Intelligence*. ⚠️ <!-- TODO: verify venue and exact title -->

11. Xu, Y., Wang, S., & Li, Z. (2024). Persona-driven requirements engineering with large language models. *IEEE Transactions on Software Engineering*, 50(4), 892–910. ⚠️ <!-- TODO: verify venue and exact title -->

12. Salehi, N., Kaur, J., & Bernstein, M. S. (2024). Persona-based accessibility evaluation using large language models. *Proceedings of the ACM on Human-Computer Interaction*, 8(CSCW1), 1–28. ⚠️ <!-- TODO: verify venue and exact title -->

13. Nielsen, J. (1994). *Usability Engineering*. Morgan Kaufmann.

14. Lazar, J., Feng, J. H., & Hochheiser, H. (2017). *Research Methods in Human-Computer Interaction*. Morgan Kaufmann.

15. Morgan, D. L. (1997). *Focus Groups as Qualitative Research* (2nd ed.). Sage Publications.

16. Mulder, S., & Yaar, Z. (2006). *The User Is Always Right: A Practical Guide to Creating and Using Personas for the Web*. New Riders.

17. Chan, C.-M., Chen, W., Su, Y., Yu, J., Xue, W., Zhang, S., Fu, J., & Liu, P. (2023). Chatmap: Scaling large language model-based multi-agent collaboration. *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*.

18. Outset. (2024). AI-moderated interview platform [Commercial product]. https://outset.ai

19. Yabble. (2024). AI-powered survey and research platform [Commercial product]. https://yabble.com

**References added per audit:**

20. Cooper, A. (1999). *The Inmates Are Running the Asylum*. SAMS. ✅ Domain consensus reference for behavior-first persona design.

21. Pruitt, J., & Adlin, T. (2006). *The Persona Lifecycle: Keeping People in Mind Throughout Product Design*. Morgan Kaufmann. ✅ Domain consensus reference for behavior-first persona design.

22. RealSim (2026). Synthetic users, real differences. *arXiv preprint arXiv:2605.02624*. ⚠️ Pre-print; provides independent assessment of synthetic user alignment claims.

23. Can LLM agents really debate? (2025). *arXiv preprint arXiv:2511.07784*. ⚠️ Pre-print; relevant to cross-examination protocol validity.
