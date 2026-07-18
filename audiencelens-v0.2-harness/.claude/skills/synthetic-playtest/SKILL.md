---
name: synthetic-playtest
description: "Run a synthetic player panel against a game concept, GDD, prototype notes, store page, build notes, or screenshot descriptions. Produces persona-specific player feedback, synthesis, and Harness self-check."
argument-hint: "[path-or-topic] [--focus onboarding|core-loop|fun|retention|monetization|store-page|difficulty|ui] [--panel mixed|steam|casual|hardcore|red-team] [--count 4-12] [--output path] [--harness on|off]"
user-invocable: true
allowed-tools: Read, Glob, Grep, Write, Task, AskUserQuestion
model: sonnet
---

# Synthetic Playtest Skill

## Purpose

Simulate early player feedback before a real playtest is available. Review game concepts, GDDs, prototype notes, build notes, screenshot descriptions, Steam/TapTap page drafts, tutorial flows, combat loops, economy loops, and UI drafts.

This skill must not claim to determine real fun or market success.

## Phase 1: Parse Arguments

Resolve target material, focus, panel, count, output path, and harness mode.

Defaults:

- focus: first-impression
- panel: mixed
- count: 8
- output: `production/research/synthetic-playtest-[date].md`
- harness: on

## Phase 2: Read Target Material

Extract:

- game name
- genre
- one-liner
- core fantasy
- core loop
- target platform
- target player
- current stage
- main systems
- screenshots / video description
- monetization model
- user questions
- main uncertainty

Do not invent missing facts. Mark unknown fields as `Unknown`.

## Phase 3: Extract Game Assumptions

Output a neutral summary before persona review:

```markdown
## Game Assumption Summary

- Genre:
- Core fantasy:
- Core loop:
- Target platform:
- Target player:
- Session length:
- Monetization:
- Main uncertainty:
```

## Phase 4: Select Persona Panel

Load panel from `.claude/docs/persona-panels/`.

Default mixed panel:

1. core_indie_player
2. casual_mobile_player
3. steam_browser
4. streamer_creator
5. system_depth_player
6. visual_first_player
7. story_immersion_player
8. toxic_reviewer

Gender, age, region, and MBTI-like traits may be used only as weak style/context modifiers. They must never be treated as deterministic causes.

## Phase 5: Run Independent Persona Reviews

Each persona must output:

```json
{
  "persona_id": "",
  "first_reaction": "",
  "what_i_understood": "",
  "what_confused_me": "",
  "what_attracted_me": "",
  "main_objection": "",
  "would_continue": "yes|maybe|no",
  "would_download_or_wishlist": "yes|maybe|no",
  "would_pay": "yes|maybe|no|not_applicable",
  "harsh_quote": "",
  "score": {
    "clarity": 0,
    "appeal": 0,
    "trust": 0,
    "novelty": 0,
    "conversion": 0
  },
  "top_fix": "",
  "confidence": "low|medium|high"
}
```

Rules:

- Personas must sound different because of behavior models, not shallow demographics.
- Reference concrete project details from the input.
- Avoid generic praise.
- Include one concrete fix per persona.

## Phase 6: Synthesize Findings

Aggregate:

- overall signal: weak / mixed / promising / strong
- strongest segments
- weakest segments
- consensus findings
- disagreements
- blockers
- opportunities
- P0 / P1 / P2 action items
- next real playtest questions

## Phase 7: Generate Report

Use `.claude/docs/templates/synthetic-playtest-report.md`.

## Phase 8: Recommend Next Actions

Route findings:

- onboarding confusion → revise tutorial / first 60 seconds
- weak store-page conversion → rewrite capsule, tags, short description, first screenshot
- lack of streamer appeal → create stronger visible stakes or shareable moments
- toxic reviewer attacks prototype feel → add proof of real gameplay
- system-depth player says shallow → strengthen mechanic combinations

## Phase 9: Harness Self-Check

If `--harness off` is not set, evaluate using `harness/rubrics/audience-review-rubric.md`.

Check:

1. Persona differentiation
2. Input grounding
3. Actionability
4. Segment conflict
5. Risk detection
6. Ethical persona use
7. Report structure
8. Calibration honesty

Critical failures:

- no disclaimer
- no P0/P1/P2 actions
- personas all sound the same
- feedback is not grounded in input
- uses gender/MBTI as deterministic stereotype
- claims real-world success prediction

If the report fails critical checks, revise it before final output.

## Phase 10: Save or Output

Ask before writing unless the user explicitly requested file output.

Verdict: COMPLETE.
