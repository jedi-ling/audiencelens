# AudienceLens

**Open-source multi-agent synthetic audience review skill pack by Shuoji Team.**

AudienceLens lets Claude Code / Cursor / OpenCode style AI agents summon different audience personas to review games, products, landing pages, DevLogs, startup ideas, and creative projects before real user testing.

AudienceLens is not just a prompt pack. v0.2 adds a lightweight **Harness** layer for testing persona quality, report structure, grounding, actionability, and ethical use of demographic/personality attributes.

## Positioning

CCGS-style frameworks simulate internal production roles: creative director, technical director, producer, designer, programmer, QA.

AudienceLens simulates external audience roles: core player, casual player, Steam browser, streamer, visual-first player, system-depth player, story player, toxic reviewer, monetization-sensitive player, publisher scout.

CCGS asks: **How should this game be built?**  
AudienceLens asks: **How will different people understand, like, reject, misunderstand, or criticize this project?**

## Skills

| Skill | Purpose |
|---|---|
| `/synthetic-playtest` | Game-focused synthetic player panel |
| `/audience-panel` | General product / app / landing-page audience review |
| `/red-team-audience` | Harsh objection and failure-mode simulation |
| `/persona-generate` | Generate reusable persona panels as YAML |

## Harness Edition

The Harness checks:

1. Persona differentiation
2. Input grounding
3. Actionability
4. Segment conflict
5. Risk detection
6. Ethical persona use
7. Report structure
8. Calibration honesty

## Quick Start

Copy `.claude/skills` and `.claude/docs` into a Claude Code project.

```bash
/synthetic-playtest examples/game-demo-review-input.md --focus onboarding --panel mixed
/audience-panel examples/landing-page-review-input.md --focus positioning
/red-team-audience examples/game-demo-review-input.md --intensity high
```

## Persona Ethics

Gender, age range, region, and MBTI-like traits are weak style/context modifiers only. They must not be treated as deterministic predictors of behavior.

Behavior must be grounded in motivation, domain knowledge, patience, platform habits, decision rules, quit triggers, continue triggers, and input evidence.

## Hosted Version

Open source edition = full control.  
Shuoji hosted edition = lower friction, managed model calls, visual reports, report history, version comparison, private/public sharing, advanced player panels.

Platform feature name: **朔纪 AI 玩家评审团**  
Powered by AudienceLens · 朔纪团队出品

## Disclaimer

Synthetic audience feedback is not a substitute for real user research. Use it for blind-spot detection, hypothesis generation, pre-screening, critique preparation, and next-test planning.

## Made by Shuoji Team
