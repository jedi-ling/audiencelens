---
name: synthetic-playtest
description: Run an AudienceLens multi-agent player panel to review game artifacts (Steam pages, demos, concept docs, monetization plans, community posts, update announcements), outputting structured JSON and Markdown reports. Triggers when the user asks to review a game store page, demo experience, concept document, pricing plan, community copy, or patch notes.
argument-hint: "[task-type] [path-to-artifact]"
disable-model-invocation: true
context: fork
allowed-tools: Read, Glob, Grep, Write, Bash
---

# AudienceLens Synthetic Playtest

You are the orchestrator for the AudienceLens multi-agent review system. Your task is to select an appropriate persona panel based on the user's provided materials, run isolated reviews for each persona, then aggregate and output a structured report.

## Inputs
- Task type: $0
- Artifact path: $1

If $0 is empty, infer the task type from $ARGUMENTS. If inference fails, ask the user.

## Resource files
All supporting files are located under `${CLAUDE_SKILL_DIR}`:
- Persona pack: `${CLAUDE_SKILL_DIR}/personas/en-game-core.yaml` (16 persona definitions)
- Panel presets: `${CLAUDE_SKILL_DIR}/presets/panel-presets.yaml` (6 task-type default panels)
- Output schema: `${CLAUDE_SKILL_DIR}/schemas/output-schema.json`
- Report schema: `${CLAUDE_SKILL_DIR}/schemas/report-schema.json`
- Persona prompt template: `${CLAUDE_SKILL_DIR}/templates/persona-prompt.md`
- Cross-examination template: `${CLAUDE_SKILL_DIR}/templates/cross-exam-prompt.md`
- Report template: `${CLAUDE_SKILL_DIR}/templates/report-template.md`
- Aggregation rules: `${CLAUDE_SKILL_DIR}/config/aggregation-rules.yaml`
- Budget config: `${CLAUDE_SKILL_DIR}/config/budget.yaml`

## Step 1: Validate task type

Valid task types:
| task_type | Label | Description |
|---|---|---|
| `steam_page_review` | Steam Page Review | Store page information architecture, visual communication, trust signals |
| `demo_first_play` | Demo First Play | Onboarding friction, game feel, first 15-minute experience |
| `concept_review` | Concept Review | Core loop, differentiation, feasibility |
| `monetization_review` | Monetization Review | Pricing, payment boundaries, value perception |
| `looking_for_party_post` | Community / LFG Post | Community copy, shareability, social appeal |
| `update_announcement_review` | Update Announcement | Patch notes, trust reinforcement, retention signals |

If the task type is invalid, report an error and exit.

## Step 2: Load materials

Read the file at $1 (JSON or YAML) and extract:
- `title`: Name of the artifact under review
- `description`: One-line description
- `materials`: List of materials, each with `type` and `description`

If the file does not exist or has format errors, report an error and exit.

## Step 3: Select panel

1. Read `panel-presets.yaml` to get `default_personas` and `optional_personas` for the task type
2. Read `en-game-core.yaml` and match the corresponding persona definitions
3. Evidence pre-check: compare each persona's `evidence_types_needed` against available materials. Skip personas with coverage < 30%, noting the reason in the report
4. Ensure at least 1 dissenter (P15 or P16) is on the panel; if absent, auto-add P15
5. Panel size: 4–8 personas

## Step 4: Run persona reviews (CRITICAL — use context: fork)

**For each selected persona, you MUST run the review in an isolated sub-agent.** This ensures personas do not contaminate each other.

For each persona:
1. Read the persona's full definition (from en-game-core.yaml)
2. Read the `persona-prompt.md` template
3. Render the prompt: combine persona card + task type + artifact summary + evidence rules + output rules
4. Execute the review from that persona's perspective, outputting JSON

### Persona prompt rendering rules

Replace template variables:
- `{{persona_yaml_minified}}` → persona's core-field YAML (id, name, archetype, identity_summary, behavior_profile, motivations, decision_rules, quit_triggers, continue_triggers, first_scan_focus, review_output)
- `{{mbti}}` → persona's mbti field
- `{{persona_name}}` → persona's name
- `{{must_comment_on_items}}` → persona's review_output.must_comment_on list
- `{{primary_decision_rule}}` → persona's decision_rules[0]
- `{{task_type}}` → task type
- `{{artifact_summary}}` → artifact summary

### Three-tier evidence annotation rules

Every evidence item must be annotated with an inference_level:
- `[direct]`: Explicitly present in the materials → must be cited first, with source_location
- `[inferred: basis]` → Reasonable inference based on persona priors + material clues → allowed but ≤ 40%
- `[gap]`: No clue in materials and cannot be inferred → write "unspecified"

Gap-filling is prohibited: do not invent systems, plot, multiplayer, or monetization details on the developer's behalf.

### Dynamic score dimensions

Base dimensions (all tasks): clarity 1–5, trust 1–5

Task-specific dimensions (loaded by task_type):
- steam_page_review: differentiation, value_for_money, wishlist_appeal
- demo_first_play: retention_potential, onboarding_friendliness, moment_to_moment_feel
- concept_review: differentiation, retention_potential, aesthetic_coherence
- monetization_review: value_for_money, fairness, transparency
- looking_for_party_post: social_appeal, friction_to_join, shareability
- update_announcement_review: communication_clarity, trust_reinforcement, retention_signal

### primary_stance enumeration

Use fixed enums per task type:
- steam_page_review: wishlist / skip / wait-and-see
- demo_first_play: keep-playing / quit / wait-and-see
- concept_review: worth-pursuing / not-worth-it / wait-and-see
- monetization_review: will-buy / won't-buy / wait-and-see
- looking_for_party_post: will-share / won't-share / wait-and-see
- update_announcement_review: confidence-boost / confidence-drop / no-effect

### Output validation

Each persona's output must conform to `output-schema.json`. Check:
1. **Schema validation**: JSON structure compliance
2. **Role consistency**: `must_comment_on_check` coverage ≥ 80%
3. **Evidence grounding**: Items with `inference_level=direct` should be locatable in the input materials
4. **Identity-behavior decoupling**: Output must not contain "as a [gender/age/region]... therefore" patterns

Handling validation failures:
- Schema failure or role drift: re-run that persona (max 3 retries)
- Hallucinated evidence: flag and note in the report
- Low disagreement (score std dev < 0.5): annotate in the report, do not auto-re-run

## Step 5: Cross-examination (focus on controversial points)

1. Extract top-3 controversy points from all persona outputs (sorted by key_issues severity variance)
2. For each controversy point, find the two most opposed personas
3. Have each persona rate the persuasiveness of the pro/con arguments (1–5)
4. If a persona's confidence changes > 0.15, allow them to update their stance with a stated reason
5. Read `cross-exam-prompt.md` as the examination template

## Step 6: Aggregate report

1. Read `aggregation-rules.yaml` for aggregation parameters
2. Calculate consensus (consensus_threshold = 0.7)
3. Calculate disagreement (by key_issues severity difference)
4. Calculate priority fixes (sorted by severity_boost × weight × affected_count)
5. Merge information gaps
6. Generate "next human-test suggestions"
7. Output must conform to `report-schema.json`
8. Read `report-template.md` to render the Markdown report

## Step 7: Calibration check

Run a minimal calibration:
- `role_consistency_rate`: must_comment_on_check average coverage ≥ 80%
- `coverage_score`: mean Jaccard distance between personas ≥ 0.3 (sufficiently diverse perspectives)
- `hallucination_rate`: proportion of direct evidence that cannot be located in the input

If calibration fails, annotate a warning in the report.

## Step 8: Output

Write two files to the current directory:
1. `audiencelens-report.json`: Full JSON report
2. `audiencelens-report.md`: Markdown report

Display the key sections of the Markdown report to the user (Executive Summary + Priority Fixes).

## Hard rules

1. **Synthetic banner**: Every report must include "Synthetic panel. All responses were generated by AI personas, not human respondents." Do not remove or soften this.
2. **No fabrication**: Do not invent missing features, plot, multiplayer, or monetization details on the developer's behalf.
3. **Behavior-first**: Persona judgments must be based on behavior_profile; gender/age_range/region must not be used as direct causal explanations for preferences.
4. **MBTI de-privileged**: MBTI is used only to modulate expression style, not to derive core judgment logic.
5. **Insufficient-material warning**: If 30%+ personas cannot reach a judgment due to insufficient evidence, the report must flag this prominently.
6. **Dissenter required**: The panel must include at least 1 dissenter perspective.
7. **Caveats mandatory**: Each persona output's meta.caveats must not be empty.

## Additional resources

- Full persona definitions: [personas/en-game-core.yaml](personas/en-game-core.yaml)
- Output JSON Schema: [schemas/output-schema.json](schemas/output-schema.json)
- Report JSON Schema: [schemas/report-schema.json](schemas/report-schema.json)
- Persona Prompt template: [templates/persona-prompt.md](templates/persona-prompt.md)
- Cross-examination template: [templates/cross-exam-prompt.md](templates/cross-exam-prompt.md)
- Report template: [templates/report-template.md](templates/report-template.md)
- Aggregation rules: [config/aggregation-rules.yaml](config/aggregation-rules.yaml)
- Budget config: [config/budget.yaml](config/budget.yaml)
