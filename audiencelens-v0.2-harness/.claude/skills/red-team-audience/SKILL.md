---
name: red-team-audience
description: "Run a harsh synthetic audience red-team review. Simulates skeptical users, toxic reviewers, buyers, investors, competitors, and churn-prone users."
argument-hint: "[path-or-topic] [--intensity low|medium|high] [--mode user|buyer|investor|reviewer|competitor|mixed] [--output path] [--harness on|off]"
user-invocable: true
allowed-tools: Read, Glob, Grep, Write, Task, AskUserQuestion
model: sonnet
---

# Red Team Audience Skill

Find objections, rejection reasons, harsh public criticisms, trust gaps, pricing backlash, and competitive attack angles.

## Rules

- Attack the product, not the creator.
- Separate valid criticism from noise.
- Do not fabricate facts.
- Do not use demographic or MBTI stereotypes.
- Identify what can be ignored.

## Default Red-Team Personas

1. Impatient first-time user
2. Price-sensitive buyer
3. Competitor loyalist
4. Toxic public reviewer
5. Practical operator
6. Investor / publisher skeptic
7. Privacy/security cautious user
8. Churn-prone user

## Output

Use `.claude/docs/templates/red-team-audience-report.md`.

Include most dangerous objection, most likely public criticism, must-fix list, messaging fixes, ignorable noise, countermeasures, revised positioning notes, and Harness self-check.
