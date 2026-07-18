---
name: audience-panel
description: "Run a synthetic audience panel against a product, document, landing page, startup idea, feature proposal, or app concept. Includes Harness self-check."
argument-hint: "[path-or-topic] [--focus first-impression|adoption|conversion|pricing|ux|positioning|retention] [--panel general|consumer|saas|education|enterprise] [--count 4-12] [--output path] [--harness on|off]"
user-invocable: true
allowed-tools: Read, Glob, Grep, Write, Task, AskUserQuestion
model: sonnet
---

# Audience Panel Skill

Run a synthetic audience review for apps, SaaS, landing pages, product docs, README files, startup ideas, communities, education products, and platform features.

## Flow

1. Parse arguments.
2. Read target material.
3. Extract project assumptions.
4. Generate or select 6-12 personas.
5. Run independent persona reviews.
6. Synthesize consensus, disagreement, risk, opportunity.
7. Generate report using `.claude/docs/templates/audience-panel-report.md`.
8. Run Harness self-check unless `--harness off`.
9. Save or output report.

## Persona Rules

Each persona must include context, motivation, decision criteria, patience level, domain knowledge, purchase attitude, objections, review style, and failure mode.

Gender, age, region, and MBTI-like traits are optional weak modifiers only.

## Critical Failures

- No concrete reference to input.
- Generic advice only.
- No segment disagreement.
- No actionable recommendation.
- Demographic stereotyping.
- No disclaimer.
