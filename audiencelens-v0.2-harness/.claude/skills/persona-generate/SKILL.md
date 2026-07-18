---
name: persona-generate
description: "Generate reusable synthetic persona panels as YAML for AudienceLens skills. Includes schema and ethics checks."
argument-hint: "[path-or-topic] [--count 4-12] [--market game|consumer|saas|education|enterprise|creator] [--output path]"
user-invocable: true
allowed-tools: Read, Glob, Grep, Write, AskUserQuestion
model: sonnet
---

# Persona Generate Skill

Generate reusable persona panels for synthetic audience review.

## Required Fields

Each persona must follow `personas/schemas/persona.schema.yaml`.

Required sections:

- identity
- demographics
- personality_modifiers
- behavioral_profile
- gaming_profile or product_profile
- motivations
- likes
- dislikes
- decision_rules
- quit_triggers
- continue_triggers
- first_scan_focus
- review_output

## Ethics Rules

- Do not use gender, age, region, or MBTI as deterministic causes.
- They may only influence voice, perspective diversity, and weak contextual framing.
- Behavior must be driven by motivation, context, domain knowledge, patience, and decision rules.

## Output

Generate valid YAML.
