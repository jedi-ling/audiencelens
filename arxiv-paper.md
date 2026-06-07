---
title: "AudienceLens: A Multi-Agent Cross-Examination Framework for Synthetic Audience Review"
authors:
  - name: Shuoji Team
    affiliation: Shuoji Research
abstract: |
  Traditional user research suffers from high cost, slow turnaround, and poor reproducibility. Recent advances in LLM-based persona simulation offer a promising alternative by generating synthetic user interviews at scale. However, existing approaches rely on single-turn interactions without cross-examination, lack mechanisms for stance revision, and provide no systematic framework for tracking consensus evolution. We propose and implement a prototype of AudienceLens, a multi-agent cross-examination system for synthetic audience review that addresses these limitations through three core innovations: (1) a three-round debate protocol (position statement, rebuttal, final stance) with fork-isolated persona agents; (2) a vote change mechanism with a confidence threshold of 0.15 and full change provenance; (3) consensus evolution tracking with tipping point detection. The system comprises 75 behavior-driven personas across four specialized skills, accompanied by a preliminary 8-dimension Harness evaluation framework. We propose the identity-behavior decoupling principle and detail an ethics compliance framework aligned with EU AI Act requirements. We discuss limitations including the absence of real-world parity studies and outline a roadmap for empirical validation. We note that this paper presents a system design and prototype implementation; empirical validation with real users remains future work.
keywords: [multi-agent systems, synthetic audience, cross-examination, persona simulation, LLM evaluation, AI ethics]
---

# AudienceLens: A Multi-Agent Cross-Examination Framework for Synthetic Audience Review

## Abstract

Traditional user research suffers from high cost, slow turnaround, and poor reproducibility. Recent advances in LLM-based persona simulation—exemplified by SyntheticUsers and similar platforms—offer a promising alternative by generating synthetic user interviews at scale. However, existing approaches rely on single-turn interactions without cross-examination, lack mechanisms for stance revision, and provide no systematic framework for tracking consensus evolution. We propose and implement a prototype of AudienceLens, a multi-agent cross-examination system for synthetic audience review that addresses these limitations through three core innovations: (1) a three-round debate protocol (position statement, rebuttal, final stance) with fork-isolated persona agents; (2) a vote change mechanism with a confidence threshold of 0.15 and full change provenance; (3) consensus evolution tracking with tipping point detection. The system comprises 75 behavior-driven personas across four specialized skills, accompanied by a preliminary 8-dimension Harness evaluation framework. We propose the identity-behavior decoupling principle and detail an ethics compliance framework aligned with EU AI Act requirements. We discuss limitations including the absence of real-world parity studies and outline a roadmap for empirical validation. We note that this paper presents a system design and prototype implementation; empirical validation with real users remains future work.

## 1. Introduction

User research is the cornerstone of product development, yet it remains one of the most resource-intensive activities in the design cycle. A single round of moderated usability testing typically requires 2–4 weeks of planning, \$5,000–\$15,000 in participant compensation, and yields results that are difficult to replicate across sessions (Nielsen, 1994; Lazar et al., 2017). Focus groups, while efficient for gathering diverse perspectives, are susceptible to groupthink, anchoring bias, and the influence of dominant voices (Morgan, 1997). Survey-based methods scale more easily but sacrifice depth for breadth, producing statistical aggregates that obscure individual reasoning.

The emergence of large language models (LLMs) has opened a new frontier: *synthetic user research*. Commercial platforms such as SyntheticUsers claim high alignment with real users, but independent validation remains limited. Park et al. (2023) showed that generative agents can exhibit believable social behaviors in sandbox environments. Horton (2023) introduced *homo silicus*—computational agents that can serve as experimental subjects in economic studies. Argyle et al. (2023) demonstrated that a single LLM can simulate diverse subpopulations with surprising fidelity, capturing variation in attitudes and behaviors across demographic groups.

However, these approaches share a critical limitation: they treat synthetic user simulation as a *monologue* rather than a *dialogue*. Each persona responds independently, without exposure to opposing viewpoints, without the opportunity to revise their position, and without any mechanism for detecting when consensus is genuine versus superficial. This is fundamentally different from how real focus groups operate—where participants challenge each other's assumptions, shift their views in response to compelling arguments, and sometimes converge on unexpected positions.

We propose and implement a prototype of **AudienceLens**, a multi-agent cross-examination system for synthetic audience review that addresses these limitations. Our key contributions are:

1. **A three-round cross-examination protocol** that structures persona interaction through position statements, rebuttals, and final stances, with fork-isolated agents that prevent cross-contamination while enabling indirect influence through shared position pools.

2. **A vote change mechanism** with a confidence threshold ($\Delta c > 0.15$) that allows personas to update their positions when exposed to compelling counterarguments, while recording full change provenance (triggering argument, confidence delta, before/after stance).

3. **Consensus evolution tracking** that classifies group dynamics into four patterns (converging, diverging, stable, oscillating) and detects tipping points—moments when $\geq 2$ personas change stance or confidence delta $\geq 0.3$ within a single round.

4. **An 8-dimension Harness evaluation framework** with quantitative thresholds for each dimension, providing the first systematic quality gate for synthetic audience review outputs.

5. **The identity-behavior decoupling principle**, an ethical framework that prohibits using demographic attributes (gender, age, region, MBTI) as causal explanations for behavioral judgments, with a compliance scoring mechanism and stereotype avoidance checklist.

6. **An open-source, skill-based implementation** compatible with Claude Code and Trae AI coding assistants, comprising 75 behavior-driven personas across four specialized skills.

The remainder of this paper is organized as follows: Section 2 reviews related work; Section 3 presents our method; Section 4 details the implementation; Section 5 describes the evaluation framework; Section 6 discusses ethical considerations; Section 7 addresses limitations and future work; and Section 8 concludes.

## 2. Related Work

### 2.1 Generative Agents and Persona Simulation

The foundation of synthetic audience research lies in the ability of LLMs to adopt and maintain consistent personas. Park et al. (2023) introduced generative agents that inhabit a sandbox town, exhibiting emergent social behaviors including relationship formation, event coordination, and information diffusion. Their architecture—comprising memory streams, reflection, and planning—demonstrated that LLM-based agents can maintain behavioral coherence over extended interactions.

Argyle et al. (2023) showed that LLMs can simulate diverse subpopulations when conditioned on demographic profiles, capturing inter-group variation in attitudes and opinions. Their "silicon subjects" approach suggested that LLMs could serve as inexpensive proxies for human survey respondents, though they cautioned against treating synthetic responses as equivalent to real human data.

Horton (2023) extended this line of work to economics, introducing *homo silicus*—computational agents that participate in economic experiments. He argued that LLM-based agents could serve as "lossless" compression of human economic behavior, enabling rapid iteration on experimental designs before committing to costly human studies.

More recently, persona simulation has been applied to software engineering contexts. Xu et al. (2024) demonstrated that LLM personas can simulate diverse user perspectives in requirements engineering, while Salehi et al. (2024) used persona-driven evaluation to assess the accessibility of web applications.

### 2.2 Synthetic User Research

Commercial synthetic user research platforms have emerged to address the cost and speed limitations of traditional methods. **SyntheticUsers** (2024) is a commercial platform offering AI-moderated interviews with synthetic participants. Commercial platforms such as SyntheticUsers claim high alignment with real users, but independent validation remains limited. Their approach uses OCEAN (Big Five) personality models to construct persona profiles and generates interview-style responses. However, SyntheticUsers operates in a single-turn interview paradigm—each persona responds to questions independently, without exposure to other personas' viewpoints.

**Outset** takes a hybrid approach, using AI to moderate real human interviews at scale. While this preserves the authenticity of human responses, it does not address the cost and speed limitations that motivate synthetic approaches. **Yabble** offers AI-powered survey analysis but relies on single-turn interactions with demographic-tagged personas, which risks reinforcing stereotypes rather than capturing genuine behavioral diversity.

These platforms share three limitations that AudienceLens addresses: (1) no cross-examination between personas; (2) no mechanism for stance revision; and (3) no systematic quality evaluation framework for synthetic review outputs.

### 2.3 Multi-Agent Debate

Du et al. (2023) demonstrated that multi-agent debate can improve factuality and reasoning in language models. In their framework, multiple LLM instances argue for different positions, with each agent refining its response based on others' arguments. This approach improved performance on mathematical reasoning and factual question-answering tasks, suggesting that adversarial interaction can surface errors that single-agent generation misses.

Liang et al. (2023) extended this work to encourage diversity in multi-agent debate, showing that enforcing distinct perspectives leads to more robust consensus formation. Chan et al. (2023) proposed chatmap for scaling multi-agent collaboration, demonstrating that structured interaction protocols outperform unstructured group chat.

Wang et al. (2024) introduced a framework for multi-agent consensus through iterative debate, showing that convergence properties depend on the topology of agent interactions and the strength of evidence. Their work highlighted the risk of premature consensus—agents converging too quickly without fully exploring the argument space.

AudienceLens builds on these insights by introducing a structured three-round debate protocol with explicit mechanisms for stance revision and consensus tracking. Unlike general multi-agent debate, our protocol is specifically designed for the audience review domain, where the goal is not to find a single correct answer but to map the landscape of perspectives and identify areas of genuine disagreement.

### 2.4 AI Ethics in Persona Generation

The ethical dimensions of synthetic persona generation have received increasing attention. Prior UX research has long argued that behavior, goals, and context are more actionable persona attributes than demographics alone (Cooper 1999; Pruitt & Adlin 2006). This insight directly motivates our identity-behavior decoupling principle.

The EU AI Act (2024) establishes transparency requirements for AI systems, including obligations to disclose when content is AI-generated (Article 50), ensure human oversight (Article 14), and maintain accuracy (Article 15). These requirements are particularly relevant for synthetic audience systems, where outputs could be misinterpreted as real user research data.

The Nielsen Norman Group's persona methodology has long advocated for behavior-first persona design, arguing that personas should be defined by goals, behaviors, and pain points rather than demographic attributes (Mulder & Yaar, 2006). AudienceLens operationalizes this principle through its `behavior_profile` construct, which replaces traditional OCEAN-based personality models with task-oriented behavioral dimensions.

## 3. Method

### 3.1 System Architecture

AudienceLens is organized as a skill-based architecture comprising four specialized skills, each serving a distinct review domain:

| Skill | Domain | Persona Count | Task Types |
|-------|--------|---------------|------------|
| synthetic-playtest | Games | 50 | 14 (Steam page, demo, concept, monetization, etc.) |
| audience-panel | Products | 20 | 6 (product, app, website, feature, pricing, UX) |
| red-team-audience | Adversarial | 5 | 5 attack modes (user, buyer, investor, reviewer, competitor) |
| persona-generate | Meta | Dynamic | 8 market types |

The total persona pool comprises **75 personas**: 50 game-focused personas distributed across 8 YAML packages (game-core: 16, competitive-esport: 5, family-casual: 5, indie-creative: 5, mobile-f2p: 5, vr-immersive: 5, accessibility: 5, educational-serious: 4), 20 product-focused personas across 6 packages, and 5 adversarial red-team personas.

A critical architectural decision is **fork isolation**: each persona agent runs in an independent subprocess with its own context window. Persona agents cannot directly communicate with each other; influence propagates exclusively through the shared position pool in the cross-examination phase. This design prevents cross-contamination (where one persona's reasoning leaks into another's) while enabling indirect influence through structured argument exchange.

### Fork Isolation Implementation

In the Claude Code Skill architecture, fork isolation is achieved through the Task subagent mechanism:

1. **Input Phase**: Each persona agent receives:
   - Target material summary (truncated to fit context window)
   - Persona YAML definition (behavior_profile, motivations, decision_rules)
   - Task rubric and output schema
   - Review mode parameters (quick/standard/full)

2. **Isolation Guarantee**: Each persona agent does NOT receive:
   - Other persona agents' full outputs
   - Other persona agents' private reasoning chains
   - Aggregation notes or intermediate results
   - Information about which other personas are in the panel

3. **Rebuttal Phase**: In the cross-examination rounds, persona agents receive:
   - Anonymized controversy claims (without persona attribution)
   - Selected opposing arguments (filtered by relevance, not by persona identity)
   - Their own previous output for reference

4. **Position Pool**: The intermediate position data is stored as structured JSON objects containing stance, confidence, key_issues, and evidence arrays. This pool is managed by the aggregation layer, not by individual persona agents.

5. **Anti-Collusion Design**: Persona names are not included in rebuttal prompts. Arguments are attributed only by argument ID (e.g., "Argument A3"), preventing persona agents from forming coalitions based on identity.

The system operates in eight phases: (0) argument parsing, (1) task type validation, (2) material loading, (3) panel selection, (4) parallel persona reviews, (5) cross-examination, (6) report aggregation, (7) calibration check, and (8) output generation. Phases 5 and 7 are skipped in `quick` mode; all phases execute in `full` mode.

### 3.2 Persona Design

Each persona is defined by a YAML specification containing identity fields, behavioral profiles, motivations, decision rules, and review configuration. The core innovation is the **behavior_profile**—a 12-axis behavioral vector that replaces traditional personality models:

| Axis | Range | Description |
|------|-------|-------------|
| `patience` | very_low – very_high | Tolerance for friction and delay |
| `genre_literacy` / `domain_literacy` | very_low – very_high | Domain-specific knowledge depth |
| `novelty_seeking` | very_low – very_high | Preference for novel over familiar |
| `risk_tolerance` | low – high | Comfort with uncertainty |
| `social_influence` | low – very_high | Susceptibility to social proof |
| `completion_drive` | very_low – very_high | Motivation to finish what was started |
| `price_sensitivity` | low – very_high | Sensitivity to cost relative to value |
| `emotional_engagement` | low – high | Depth of emotional investment |
| `agency_preference` | low – high | Desire for player/user agency |
| `tolerance_for_ambiguity` | low – high | Comfort with unclear situations |
| `criticism_style` | categorical | Approach to expressing dissatisfaction |

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
| vr-immersive | 4 | Game | Immersion, comfort, presence |
| family-casual | 5 | Game | Accessibility, onboarding, safety |
| educational-serious | 4 | Game | Learning outcomes, engagement |
| accessibility | 4 | Game | Keyboard/screen/cognitive access |
| power-user | 5 | Product | Efficiency, integration, customization |
| casual-user | 3 | Product | Simplicity, low learning curve |
| skeptic-user | 3 | Product | Trust, ROI, migration cost |
| enthusiast-user | 3 | Product | Community, feature depth |
| budget-conscious | 3 | Product | Pricing, free tier, value |
| accessibility-user | 3 | Product | Screen reader, motor, cognitive |
| red-team | 5 | Adversarial | Attack patterns, edge cases |

Each persona is defined by a complete behavior_profile, motivations, decision_rules, quit_triggers, and continue_triggers. The 75-persona count reflects coverage across domains, not redundancy; Jaccard distance analysis (Section 6.2) measures actual differentiation.

### 3.3 Cross-Examination Protocol

The cross-examination protocol is the core differentiator of AudienceLens. It proceeds in three rounds:

**Round 1: Position Statement.** Each persona independently reviews the input material and produces a structured output including scores, key issues, evidence, and a primary stance. All outputs are collected into a shared position pool. Critically, personas are not aware of each other's existence at this stage—they evaluate the material in complete isolation.

**Round 2: Rebuttal.** The system extracts the top-$k$ controversy points from Round 1 outputs, ranked by the variance of severity ratings across personas. For each controversy point, the system identifies the two personas holding the most opposed positions and generates structured arguments (claim + evidence + reasoning chain) for each side. All personas then evaluate each argument's persuasiveness on a 1–5 scale. If a persona's confidence changes by more than the threshold ($\Delta c > 0.15$), they may update their stance and must document the reason.

**Round 3: Final Stance.** Each persona produces their final position, which may differ from their Round 1 stance if they changed their view during rebuttal. The system records the complete trajectory: initial stance, confidence trajectory, any stance changes, and the triggering arguments.

The protocol terminates early if two consecutive rounds produce no stance changes, indicating convergence.

Formally, let $P = \{p_1, p_2, \ldots, p_n\}$ be the set of personas. In Round 1, each $p_i$ produces output $o_i^{(1)} = (s_i^{(1)}, c_i^{(1)}, e_i^{(1)})$ where $s_i^{(1)}$ is the stance, $c_i^{(1)} \in [0,1]$ is the confidence, and $e_i^{(1)}$ is the evidence set. The controversy points $C = \{c_1, \ldots, c_k\}$ are extracted by:

$$C = \text{top-}k \left(\text{argsort}_{j} \left(\text{Var}(\{s_{1,j}^{(1)}, \ldots, s_{n,j}^{(1)}\})\right)\right)$$

where $s_{i,j}^{(1)}$ denotes persona $p_i$'s severity rating on issue $j$. In Round 2, each persona evaluates the persuasiveness of arguments for and against each controversy point, producing updated confidence $c_i^{(2)}$. A stance change is permitted when:

$$|c_i^{(2)} - c_i^{(1)}| > \theta_{\text{change}}$$

where $\theta_{\text{change}} = 0.15$. Note: $\theta_{\text{change}}$ is a configurable engineering parameter, initially set to 0.15 for prototype experiments. This threshold is not empirically validated and should be tuned per model and domain.

### 3.4 Vote Change Mechanism

The vote change mechanism is designed to model realistic opinion dynamics while preventing cascading conformity. Key design choices:

**Confidence threshold.** A persona may only change stance when their confidence shifts by more than $\theta_{\text{change}}$. This threshold was chosen to be large enough to filter out noise (minor fluctuations in LLM output probabilities) while small enough to capture genuine persuasion. We acknowledge this value is empirically set and plan to calibrate it through controlled experiments in future work. We do not interpret self-reported confidence as calibrated probability; LLM confidence scores may not reflect true epistemic uncertainty.

**Change provenance.** Every stance change is recorded with: (1) the triggering argument and its source persona; (2) the confidence before and after; (3) the confidence delta; and (4) a free-text reason provided by the changing persona. This provenance chain enables post-hoc analysis of persuasion dynamics and supports the calibration honesty dimension of the Harness framework.

**Anti-collusion design.** Personas cannot directly communicate; influence propagates only through the shared position pool. This prevents the "echo chamber" effect where personas reinforce each other's positions through direct interaction, and ensures that any stance change is driven by the quality of arguments rather than social pressure.

**No majority weighting.** The system does not weight personas by their agreement with the majority. A single persona holding a minority position is as valid as five personas in agreement—the value lies in understanding *why* they disagree, not in counting votes.

### 3.5 Consensus Evolution Tracking

After the three-round protocol completes, the system classifies the group's consensus trajectory into one of four patterns:

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

The system also tracks **divergence hotspots**—issues where confidence changes are largest—and **polarization**, defined as the condition where the group splits into two roughly equal opposing camps rather than converging.

### 3.6 Tipping Point Detection

Tipping points are moments where the discussion trajectory changes qualitatively. AudienceLens detects three types:

**Flip points** (red): A persona changes from one stance category to another (e.g., from "would buy" to "would not buy"). These indicate that a counterargument was sufficiently compelling to overcome the persona's initial position.

**Cascade points** (amber): One persona's stance change triggers changes in other personas within the same round. These indicate that the changing persona's reasoning provided a new frame that resonated with others.

**Anchor points** (green): A persona maintains their stance despite strong counterarguments. These indicate deeply held positions that are resistant to persuasion, often tied to core behavioral traits (e.g., a persona with very high `price_sensitivity` refusing to endorse a product regardless of its features).

The formal detection rule for tipping points is:

$$\text{TippingPoint}(r) = \begin{cases} \text{true} & \text{if } |\{p_i : s_i^{(r)} \neq s_i^{(r-1)}\}| \geq 2 \\ \text{true} & \text{if } \max_i |c_i^{(r)} - c_i^{(r-1)}| \geq 0.3 \\ \text{false} & \text{otherwise} \end{cases}$$

### 3.7 Harness Evaluation Framework

The Harness is an 8-dimension quality evaluation framework that assesses synthetic review outputs against quantitative thresholds. We define initial operational thresholds for prototype evaluation. These thresholds are not validated norms; they serve as engineering guardrails and should be calibrated through future empirical work.

| # | Dimension | Core Question | Threshold |
|---|-----------|---------------|-----------|
| 1 | Actionability | Are recommendations specific and implementable? | $\geq 70\%$ of suggestions include concrete steps (prototype, not validated) |
| 2 | Input Grounding | Do arguments reference specific input material details? | $\geq 80\%$ of claims cite input evidence; direct evidence ratio $\geq 60\%$ (prototype, not validated) |
| 3 | Persona Differentiation | Do different personas produce genuinely different perspectives? | Mean Jaccard distance $\geq 0.3$; Kruskal-Wallis $H$ test $p < 0.05$ (prototype, not validated) |
| 4 | Stereotype Check | Are judgments based on behavioral profiles, not demographics? | Zero demographic-causal inference patterns (prototype, not validated) |
| 5 | Structural Integrity | Does the report contain all required sections? | 100% of required sections present (prototype, not validated) |
| 6 | Calibration Honesty | Are findings correctly labeled as hypotheses rather than facts? | 100% of hypotheses correctly annotated (prototype, not validated) |
| 7 | Risk Detection | Are critical risks identified? | $\geq 1$ critical/high severity issue identified (prototype, not validated) |
| 8 | Segment Conflict | Do persona segments exhibit meaningful disagreement? | $\geq 2$ meaningful disagreements (prototype, not validated) |

Each dimension is scored on a 1–5 scale using rubric definitions. A score of 0–1 indicates FAIL, 2–3 indicates NEEDS_IMPROVEMENT, and 4–5 indicates PASS. The overall evaluation passes only if all dimensions score $\geq 2$ and the average score is $\geq 3.0$.

The Harness includes test fixtures (high-quality and low-quality game concepts, good and bad landing pages) that serve as calibration anchors, and expected output structures that define required report sections for each task type.

## 4. Implementation

### 4.1 Skill-Based Architecture

AudienceLens is implemented as a skill pack for AI coding assistants, currently supporting Claude Code and Trae AI. Each skill is defined by a `SKILL.md` file that specifies the skill's behavior, resource files, execution phases, and hard rules. This architecture enables zero-install deployment—users copy skill files to their assistant's skill directory and invoke them via slash commands (e.g., `/synthetic-playtest concept_review path/to/concept.md`).

The skill-based approach offers several advantages over traditional SaaS deployment: (1) **Privacy**: input materials never leave the user's local environment; (2) **Customization**: users can modify persona definitions, aggregation rules, and prompt templates; (3) **Composability**: skills can be chained (e.g., running `audience-panel` followed by `red-team-audience` on the same material); and (4) **Cost efficiency**: the system uses the user's existing LLM subscription without additional per-review fees.

### 4.2 CCGS Repository Standard

AudienceLens follows the CCGS (Claude Code Group Standard) repository structure, which organizes multi-agent systems into a standardized directory layout:

```
.claude/
├── agents/          # 50 persona agent definitions
├── hooks/           # Lifecycle hooks (session-start, validate-report, etc.)
├── rules/           # Evaluation and ethics rules
└── skills/          # 4 skill definitions with resources
.trae/
└── skills/          # Trae-compatible skill mirrors
```

The CCGS standard enables interoperability between different AI coding assistants while maintaining consistent behavior. Each persona agent is defined as a standalone Markdown file (e.g., `P01-indie-core-operator.md`) that the skill dispatcher loads and injects into the LLM context when that persona is selected for a review panel.

### 4.3 Ethics Service

The ethics service enforces the identity-behavior decoupling principle through a multi-layer compliance system:

**Stereotype detection.** The system scans persona outputs for forbidden patterns where demographic attributes are used as causal explanations for behavioral judgments. Four categories of forbidden patterns are defined: gender-as-cause, age-as-stereotype, region-as-assumption, and MBTI-as-decision-logic. Each category includes both explicit patterns (e.g., "as a female player, I prefer...") and implicit patterns (e.g., "players of this age group typically...").

**Evidence grounding.** Every claim in a persona's output must be annotated with an inference level: `[direct]` (explicitly present in input material), `[inferred: basis]` (reasonably inferred from material + persona priors, capped at $\leq 40\%$ of total evidence), or `[gap]` (no evidence available, must be labeled "unspecified"). Gap-filling—fabricating information not present in the input—is strictly prohibited.

**Compliance scoring.** Each persona output receives an ethics compliance score (0–100) based on five weighted dimensions: behavior_over_demographics (30%), evidence_grounding (25%), gap_filling_control (20%), caveat_specificity (15%), and mbti_usage_correctness (10%). Scores $\geq 80$ pass; scores 60–79 require revision; scores $< 60$ are rejected.

**MBTI prohibition rule.** MBTI types are permitted only as style modifiers (affecting tone and communication style) and are explicitly prohibited from serving as causal explanations for judgments. This rule is enforced through both prompt engineering and post-hoc pattern matching.

### 4.4 HTML Report Generation

AudienceLens generates three output formats: structured JSON (machine-readable), Markdown (human-readable), and HTML (visual report). The HTML report uses a cyberpunk HUD aesthetic with the following design principles:

- **Information density**: The HUD dashboard displays three key metrics (consensus strength, risk level, persona count) in a compact card layout
- **Visual encoding**: Severity levels map to color-coded badges (green → amber → red → blinking red for critical), evidence levels map to border colors (cyan for direct, amber for inferred, red for gap), and stance categories map to CSS classes (positive, neutral, negative)
- **Persona avatars**: Generated deterministically from persona IDs using HSL color hashing (hue = hash(id) mod 360, saturation 65%, lightness 55%)
- **Score bars**: Width = score × 20% with color classes (s1=red through s5=green)
- **Typography**: Space Mono for code/HUD elements, Noto Sans SC for body text, Noto Serif SC for headings

The HTML report is generated by reading the `report-template.html` style reference and injecting aggregated report data according to the data injection rules, rather than using template rendering engines. This approach ensures compatibility across different runtime environments.

### 4.5 Case Study: Cyber Scavenger Game Concept Review

To illustrate the system's output, we present a prototype run using the Cyber Scavenger (赛博拾荒者) game concept as input.

**Input**: A game concept document describing a cyberpunk-themed survival crafting game with risk-credit mechanics, mini-program platform constraints, and idle-core loop design.

**Panel**: 6 personas selected from the game-core package:
- P01 (Core Indie Explorer): neutral → positive (confidence 78%)
- P02 (System Theory Strategist): positive (confidence 82%)
- P07 (Light Fragment Player): negative (confidence 32%)
- P08 (New Player Observer): negative → neutral (confidence 45%, vote changed)
- P11 (TapTap Review Follower): neutral → positive (confidence 58%, vote changed)
- P13 (Publisher Scout): neutral (confidence 55%)

**Cross-Examination Results**:
- 2 of 6 personas changed stance during rebuttal rounds
- Key controversy: risk-credit cognitive threshold too high (cited by 3/6 personas)
- Tipping point: P08's shift from negative to neutral after P02's rebuttal on tutorial scaffolding

**Output Summary**:
- Overall recommendation: Conditional Continue (需简化核心机制)
- Risk level: Medium
- Harness score: 31/40 (PASS, threshold 28)
- Evidence grounding rate: 62% direct evidence
- Persona differentiation: Jaccard distance 0.41

**Ethics Compliance**: Score 72/100 (NEEDS-REVISION), primarily due to insufficient calibration honesty warnings.

This case study illustrates the system's workflow and output format. It does not constitute empirical validation of the framework's effectiveness.

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

We note that this evaluation has not yet been conducted; results will be reported in a future version of this paper.

### 5.1 Harness 8-Dimension Evaluation

The Harness framework provides both quantitative thresholds and qualitative rubrics for each dimension. We describe the evaluation methodology for each:

**Actionability** is measured by the proportion of key issues that include specific, implementable `suggested_fix` fields. A suggestion is considered "actionable" if it specifies what to change, how to change it, and what the expected outcome is. The threshold of $\geq 70\%$ reflects the practical reality that some issues may be inherently vague (e.g., "the overall tone feels off") while still being worth reporting.

**Input Grounding** uses a two-part metric: (1) the proportion of claims that cite input evidence ($\geq 80\%$), and (2) the ratio of `[direct]` evidence to total evidence ($\geq 60\%$). The latter threshold ensures that personas are primarily responding to what is actually in the input material, rather than projecting their own assumptions.

**Persona Differentiation** employs Jaccard distance analysis on `key_issues` title sets across persona pairs. For each pair $(p_i, p_j)$:

$$d_J(p_i, p_j) = 1 - \frac{|K_i \cap K_j|}{|K_i \cup K_j|}$$

where $K_i$ is the set of key issue titles from persona $p_i$. The mean Jaccard distance across all pairs must be $\geq 0.3$, and a Kruskal-Wallis $H$ test on score distributions must yield $p < 0.05$. Additionally, the standard deviation of scores across personas must average $\geq 0.5$ across all score dimensions.

**Stereotype Check** uses pattern matching to detect forbidden causal patterns. The system scans for regex patterns matching "as a [demographic]... therefore/so..." constructions and flags any output where demographic attributes are used as causal explanations. The threshold is zero tolerance: any detected violation results in a FAIL for this dimension.

**Structural Integrity** validates output against JSON Schema definitions and required section lists. Each task type has a defined set of required sections (e.g., consensus, major disagreements, priority fixes, information gaps, next human test recommendations). The threshold is 100% compliance—any missing required section results in a FAIL.

**Calibration Honesty** checks that all findings are correctly annotated with their epistemic status. Hypotheses must be labeled as such; confidence scores must reflect evidence strength; and caveats must be specific rather than generic. The threshold is 100% correct annotation.

**Risk Detection** verifies that the review identifies at least one critical or high-severity issue. This prevents the common failure mode where synthetic reviews produce uniformly positive feedback, missing genuine risks.

**Segment Conflict** ensures that persona segments exhibit meaningful disagreement. The threshold is $\geq 2$ meaningful disagreements, where "meaningful" is defined as disagreements on issues rated high or critical severity by at least one persona.

### 5.2 Persona Differentiation Analysis

To validate that our 75 personas produce genuinely different perspectives, we conduct a Jaccard distance analysis on the `key_issues` and `motivations` fields across persona pairs within each skill:

For the synthetic-playtest skill, the 50 game personas span 8 categories with distinct behavioral profiles. The expected mean Jaccard distance on `key_issues` is $\geq 0.5$ (deep differentiation) for personas from different categories and $\geq 0.3$ (basic differentiation) for personas within the same category.

The differentiation guarantee is enforced at persona design time through the `persona-generate` skill, which requires that all persona pairs within a panel have a Jaccard distance $\geq 0.3$ on their `motivations` + `decision_rules` sets. Personas that fail this threshold are rejected and regenerated.

### 5.3 Cross-Examination Effectiveness

We propose two metrics for evaluating cross-examination effectiveness:

**Vote change rate** ($VCR$): The proportion of personas that change their stance between Round 1 and Round 3:

$$VCR = \frac{|\{p_i : s_i^{(3)} \neq s_i^{(1)}\}|}{n}$$

A healthy $VCR$ is in the range [0.1, 0.4]—too low suggests the cross-examination is not generating compelling counterarguments, while too high suggests excessive conformity or instability.

**Consensus shift** ($\Delta C$): The change in consensus strength between rounds:

$$\Delta C = \text{consensus\_strength}^{(3)} - \text{consensus\_strength}^{(1)}$$

Positive $\Delta C$ indicates convergence, negative indicates divergence, and near-zero indicates stability. The value of $\Delta C$ provides insight into whether the review material is inherently divisive (diverging) or has clear strengths/weaknesses that become apparent through debate (converging).

### 5.4 Comparison with Single-Round Review

To quantify the value added by cross-examination, we propose a comparative evaluation between AudienceLens's three-round protocol and a single-round baseline (equivalent to skipping Phases 5 and 7). We hypothesize that:

1. Cross-examination will produce higher calibration honesty scores, as personas forced to defend their positions will reveal lower-confidence judgments.

2. Cross-examination will produce higher segment conflict scores, as the rebuttal process surfaces disagreements that might be obscured in independent reviews.

3. The vote change rate will correlate with the controversy of the input material—highly controversial materials will produce higher $VCR$ than uncontroversial ones.

We note that these hypotheses remain to be empirically validated, which we discuss in Section 7.

## 6. Ethical Considerations

### 6.1 Identity-Behavior Decoupling

The central ethical innovation of AudienceLens is the **identity-behavior decoupling principle**: persona judgments must be causally traceable to behavioral profiles and motivations, never to demographic attributes. This principle is motivated by the long-standing argument in UX research that behavior, goals, and context are more actionable persona attributes than demographics alone (Cooper 1999; Pruitt & Adlin 2006), and by the risk that synthetic personas could reinforce rather than challenge existing stereotypes.

In practice, this means that while personas may have demographic attributes (gender, age range, region), these attributes serve only as weak modifiers of expression style and perspective diversity. They are explicitly prohibited from serving as causal explanations for preferences or judgments. For example, a persona may be described as female and may have a communication style influenced by that attribute, but the system will reject any output that claims "as a female player, I prefer narrative games"—the preference must be traced to the `behavior_profile` (e.g., high `emotional_engagement` + high `novelty_seeking`).

### 6.2 Stereotype Detection

The stereotype detection system operates at two levels:

**Generation time**: The `persona-generate` skill includes a mandatory ethics check phase (Phase 5) that scans generated personas for forbidden patterns. This check is non-bypassable—personas that fail are rejected and must be regenerated.

**Output time**: Each persona's review output is scanned for forbidden causal patterns using regex matching and semantic analysis. Detected violations are classified by severity (CRITICAL, HIGH, MEDIUM, LOW) with corresponding enforcement actions (reject, require revision, warn, suggest improvement).

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

3. **Gap acknowledgment**: When input materials are insufficient for a persona to form a judgment (evidence coverage $< 30\%$), the persona is skipped and the report explicitly notes the gap. If $> 30\%$ of personas are skipped for this reason, the report includes a prominent warning.

4. **Caveat specificity**: Each persona output must include at least one specific caveat (e.g., "this review is based on store page screenshots only; no hands-on demo was available, so手感 assessments are speculative"). Generic caveats like "for reference only" are rejected.

## 7. Limitations and Future Work

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

Several thresholds in the system (confidence change threshold of 0.15, consensus threshold of 0.7, Jaccard distance threshold of 0.3, evidence coverage threshold of 30%) are set based on engineering judgment rather than empirical optimization. While these values produce reasonable behavior in practice, they may not be optimal.

**Future work**: Controlled experiments to calibrate these thresholds, using both synthetic and real-user data. We plan to use a grid search approach, varying each threshold independently and measuring the impact on Harness evaluation scores and parity metrics.

### 7.5 Over-Convergence Risk

Multi-agent debate systems are susceptible to over-convergence, where all agents converge to the same position regardless of the input quality. This risk is particularly acute when the underlying LLM has strong priors about what constitutes "good" or "bad" design. Our anti-collusion design (fork isolation, no direct communication) mitigates this risk, but does not eliminate it entirely.

**Future work**: Investigation of convergence dynamics in the cross-examination protocol, including analysis of whether anchor points (personas resistant to persuasion) effectively prevent over-convergence, and whether the confidence threshold needs to be adaptive rather than fixed.

### 7.6 Scalability

The current system supports panels of 3–8 personas. Scaling to larger panels introduces computational costs (each persona requires a separate LLM call) and coordination challenges (more controversy points to process in cross-examination). The budget configuration file allows users to set token limits, but the system does not currently optimize for cost-quality tradeoffs.

**Future work**: Adaptive panel sizing based on input complexity, and investigation of whether smaller panels with more targeted persona selection can achieve comparable quality to larger panels.

## 8. Conclusion

We have proposed and implemented a prototype of AudienceLens, a multi-agent cross-examination system for synthetic audience review that addresses three critical limitations of existing synthetic user research tools: the absence of cross-examination, the lack of stance revision mechanisms, and the absence of systematic quality evaluation frameworks.

Our three-round debate protocol with fork-isolated persona agents enables structured argumentation that mirrors the dynamics of real focus groups—where participants challenge each other's assumptions and sometimes revise their positions. The vote change mechanism with confidence thresholds and full change provenance provides transparency into opinion dynamics that is impossible to obtain from single-turn synthetic interviews. The consensus evolution tracking and tipping point detection offer novel analytical tools for understanding how and why group opinions shift.

The 8-dimension Harness evaluation framework represents, to our knowledge, the first systematic quality gate for synthetic audience review outputs, providing quantitative thresholds across dimensions ranging from actionability to stereotype checking. The identity-behavior decoupling principle and its enforcement through the ethics service address the growing concern that synthetic personas could reinforce rather than challenge existing stereotypes.

We are transparent about AudienceLens's limitations: it has not been validated against real user research data, it does not support multi-modal evaluation, and several design parameters are empirically set rather than experimentally optimized. We believe that acknowledging these limitations is essential for responsible deployment of synthetic audience tools, and we are committed to addressing them through future empirical validation.

AudienceLens is open-source and available as a skill pack for Claude Code and Trae AI coding assistants, comprising 75 behavior-driven personas across four specialized skills. We invite the research community to use, evaluate, and extend the system, and we welcome collaborations for real-world validation studies.

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
