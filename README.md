<div align="center">

# AudienceLens

**Multi-Agent Synthetic Audience Review System with Cross-Examination**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](web/backend/requirements.txt)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](web/frontend/package.json)
[![Tests](https://img.shields.io/badge/Tests-180+-success.svg)](tests/)

**基于合成人格的多代理交叉质询评审系统 · Python CLI + FastAPI + React**

[English](#english) · [中文](#中文)

</div>

---

<a id="english"></a>

## Overview

AudienceLens is a **full-stack synthetic audience review system** that simulates diverse player personas to evaluate games, products, and creative projects — before committing resources to real user testing.

Unlike simply asking ChatGPT for feedback, AudienceLens:
1. Runs **multiple behavior-driven personas in isolation** (75+ across 8 packs)
2. Applies **structured cross-examination** on top-3 controversies
3. Tracks **stance revisions** with full provenance (who changed, why, which argument)
4. Validates output through **8-dimension quality Harness**
5. Enforces **ethical constraints** — stereotype detection, evidence tiering, mandatory disclaimers

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
| **Cross-Examination** | `cross_exam.py` | Extract top-3 controversies (by severity variance, with SequenceMatcher dedup); opposing personas rebut; stance revision if Δc >0.15 |
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

**8 Persona Packs (75+ personas total):**

| Pack | File | Personas |
|---|---|---|
| Game Core | `game-core.yaml` | 16 core game personas (explorer, systems theorist, action feel, narrative, visual, casual, novice, cozy, Steam browser, TapTap scout, creator, publisher scout, price-sensitive, toxic skeptic, competitor veteran) |
| Competitive Esport | `competitive-esport.yaml` | Rank climber, speedrun challenger, team coordinator, esport spectator, mod competitor |
| Family Casual | `family-casual.yaml` | Party socialite, cozy relaxer, nostalgia retro, generational bridge |
| Indie Creative | `indie-creative.yaml` | Creativity seeker, indie rhythm fanatic, visual atmosphere lover |
| Mobile F2P | `mobile-f2p.yaml` | Mobile monthly card, mobile ad tolerant, hypercasual passerby, free lunch hunter, fragmented whale |
| VR Immersive | `vr-immersive.yaml` | VR motion sensitive, presence seeker, VR fitness player, social VR resident |
| Accessibility | `accessibility.yaml` | Color vision aid, cognitive load sensitive, motor accessibility, hearing accessibility |
| Educational Serious | `educational-serious.yaml` | Teacher evaluator, parent gatekeeper, lifelong learner, special needs learner, parent-child creator |

### 3. Cross-Examination — Structured Debate Protocol

Traditional "let the most disagreeing personas argue" often produces unproductive extreme-vs-extreme noise. AudienceLens uses a structured protocol:

1. **Controversy Extraction** — Extract top-3 controversies from all persona outputs, ranked by severity variance, with SequenceMatcher deduplication
2. **Opposing Rebuttals** — For each controversy, personas on opposite sides write evidence-based arguments
3. **Persuasion Scoring** — All personas score each argument's persuasiveness
4. **Stance Revision** — If confidence change exceeds 0.15, persona may update stance
5. **Full Provenance** — System records: who changed, why, which argument triggered it, confidence before/after

### 4. Task Types — 10 Review Scenarios

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

### 5. Web Application — Full-Stack Implementation

| Layer | Tech Stack | Key Features |
|---|---|---|
| **Backend** | FastAPI + SQLite + WebSocket | 25+ API endpoints, 9 WebSocket events, 4 core services |
| **Frontend** | React 19 + TypeScript + Tailwind + shadcn/ui + Recharts | 12 pages, 7 components, 2 Zustand stores |
| **Services** | PersonaService, ReviewService, LLMService, EthicsService | Multi-model gateway (Claude/GPT/DeepSeek/Ollama), stereotype detection, ethics compliance |
| **Real-time** | WebSocket (9 event types) | Live review progress, persona-by-persona results |
| **Deployment** | Docker Compose | Frontend (Nginx) + Backend (Uvicorn) |

**3 Review Modes:**

| Mode | Personas | Cross-Exam | Calibration | Use Case |
|---|---|---|---|---|
| Quick | 3 | No | No | Rapid scan |
| Standard | 4–6 | Yes | No | Balanced review |
| Full | 6–8 | Yes | Yes | Complete analysis |

### 6. Quality Harness — 8-Dimension Evaluation

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
| **Identity-Behavior Decoupling** | Gender/age/region are weak style modifiers only — never causal predictors |
| **MBTI De-authorization** | MBTI modifies expression style only — never core judgment logic |
| **Evidence Tiering** | `[direct]` / `[inferred]` / `[gap]` — inferred capped at 40% |
| **No Fabrication** | Personas must not invent missing features, plot, multiplayer, monetization |
| **Mandatory Disclaimer** | Every report: "AI-generated synthetic review — not real user research" |
| **Stereotype Detection** | EthicsService with 10+ detection rules for demographic stereotyping |

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
# Install dependencies
pip install -r requirements.txt

# Set your API key first
# Linux/macOS
export ANTHROPIC_API_KEY=your-key
# Windows PowerShell: $env:ANTHROPIC_API_KEY="your-key"
# Windows CMD: set ANTHROPIC_API_KEY=your-key

# Run a review
python -m runner.cli steam_page_review examples/steam-page-sample/artifact.json
```

> ⚠️ **Without an API key, the CLI falls back to simulation mode**: all persona outputs are pre-built placeholder data with **zero review value**. It only verifies that the pipeline runs — never use simulated results for any decision. The CLI and all generated reports carry a prominent warning when this mode is active.

**Quality & experiment commands** (unified CLI):

```bash
# Stereotype-detection benchmark on a 30-case labeled set (offline regex layer)
python -m src.cli stereotype-eval
# Add the LLM review layer (requires ANTHROPIC_API_KEY)
python -m src.cli stereotype-eval --llm

# Persona-differentiation ablation: full vs no_behavior vs bare (requires API key)
python -m src.cli ablation concept_review examples/steam-page-sample/artifact.json --limit 4 --output ablation.json
```

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
│   │   ├── cross_exam.py              #   Structured cross-examination
│   │   ├── aggregator.py              #   Rule-driven report aggregation
│   │   └── calibration.py             #   Quality calibration check
│   ├── personas/                      # 8 persona packs (75+ personas)
│   ├── presets/                       # Panel presets per task type
│   ├── schemas/                       # JSON Schema (persona, output, report)
│   ├── templates/                     # Prompt + report templates
│   └── config/                        # Aggregation rules + budget config
├── web/
│   ├── backend/                       # FastAPI backend
│   │   └── app/
│   │       ├── api/                   #   25+ REST endpoints
│   │       ├── services/              #   4 core services
│   │       ├── models/                #   SQLAlchemy models
│   │       ├── schemas/               #   Pydantic schemas
│   │       └── websocket/             #   9 WebSocket events
│   └── frontend/                      # React frontend
│       └── src/
│           ├── pages/                 #   12 pages
│           ├── components/            #   7 components
│           └── store/                 #   2 Zustand stores
├── tests/                             # 180+ TDD tests
├── examples/                          # 7 sample artifacts
├── docs/                              # Documentation
├── requirements.txt
└── pytest.ini
```

---

## Testing

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

**180+ tests — all passing**

---

## Roadmap

| Version | Focus | Status |
|---|---|---|
| v0.1 | MVP — 16 personas, 6 task types, CLI runner, cross-examination, 3-layer validation | Done |
| **v0.2** | **Harness Edition — 8-dim quality gate, ethics service, 75+ personas, Web UI** | **Current** |
| v0.3 | Human parity study, golden output regression, auto evidence tier detection | Planned |
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

## Made by Shuoji Team

---

<a id="中文"></a>

## 概述

AudienceLens 是一个**全栈合成观众评审系统**，模拟多元玩家人格对游戏、产品和创意项目进行评审——在投入真人测试资源之前。

与直接问 ChatGPT 不同，AudienceLens：
1. **隔离运行**多个行为驱动人格（8个Pack共75+个人格）
2. 对 top-3 争议点执行**结构化交叉质询**
3. 追踪**立场修正**的完整溯源链（谁改了、为什么改、被哪个论据说服）
4. 通过**8维质量 Harness** 验证输出
5. 强制**伦理约束**——刻板印象检测、证据分级、强制免责声明

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
| **交叉质询** | `cross_exam.py` | 提取top-3争议点（按severity方差排序，SequenceMatcher去重）；对立人格反驳；置信度变化>0.15可修正立场 |
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

**8个人格Pack（75+人格）：**

| Pack | 文件 | 人格 |
|---|---|---|
| 游戏核心 | `game-core.yaml` | 16个核心游戏人格（探索者、推演党、手感党、沉浸党、氛围党、碎片玩家、新手、治愈社交、Steam浏览者、TapTap口碑、创作者、发行侦察、价格敏感、毒舌怀疑、竞品老兵） |
| 竞技电竞 | `competitive-esport.yaml` | 冲分玩家、速通挑战者、团队协调者、电竞观众、Mod竞技者 |
| 家庭休闲 | `family-casual.yaml` | 派对社交、治愈放松、怀旧复古、代际桥梁 |
| 独立创意 | `indie-creative.yaml` | 创意探索者、独立节奏狂、视觉氛围爱好者 |
| 移动免费 | `mobile-f2p.yaml` | 月卡党、广告容忍者、超休闲路人、白嫖猎人、碎片鲸鱼 |
| VR沉浸 | `vr-immersive.yaml` | VR晕动敏感、临场感追求者、VR健身玩家、社交VR居民 |
| 无障碍 | `accessibility.yaml` | 色觉辅助、认知负荷敏感、运动无障碍、听觉无障碍 |
| 教育严肃 | `educational-serious.yaml` | 教师评估者、家长守门人、终身学习者、特殊需求学习者、亲子共创者 |

### 3. 交叉质询 — 结构化辩论协议

传统"让分歧最大的两个人格互问"容易变成极端对立的无意义争吵。AudienceLens 使用结构化协议：

1. **争议提取** — 从所有人格输出中提取top-3争议点，按severity方差排序，SequenceMatcher去重
2. **对立反驳** — 对每个争议点，持相反立场的人格写基于证据的论证
3. **说服力评分** — 所有人格对每段论证评分
4. **立场修正** — 置信度变化超过0.15时，人格可更新立场
5. **完整溯源** — 系统记录：谁改了、为什么改、被哪个论点触发、置信度前后变化

### 4. 任务类型 — 10种评审场景

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

### 5. Web应用 — 全栈实现

| 层 | 技术栈 | 核心功能 |
|---|---|---|
| **后端** | FastAPI + SQLite + WebSocket | 25+ API端点、9个WebSocket事件、4个核心服务 |
| **前端** | React 19 + TypeScript + Tailwind + shadcn/ui + Recharts | 12个页面、7个组件、2个Zustand Store |
| **服务** | PersonaService、ReviewService、LLMService、EthicsService | 多模型网关(Claude/GPT/DeepSeek/Ollama)、刻板印象检测、伦理合规 |
| **实时** | WebSocket（9种事件类型） | 实时评审进度、逐人格结果展示 |
| **部署** | Docker Compose | 前端(Nginx) + 后端(Uvicorn) |

**3种评审模式：**

| 模式 | 人格数 | 交叉质询 | 校准 | 适用场景 |
|---|---|---|---|---|
| 快速 | 3 | 否 | 否 | 快速扫描 |
| 标准 | 4–6 | 是 | 否 | 均衡评审 |
| 完整 | 6–8 | 是 | 是 | 完整分析 |

### 6. 质量 Harness — 8维评估

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
| **身份-行为解耦** | 性别/年龄/地域仅作为弱风格修饰符——绝不作为因果预测因子 |
| **MBTI去权** | MBTI仅修饰表达风格——不推导核心判断逻辑 |
| **证据分级** | `[direct]` / `[inferred]` / `[gap]` — 推断证据上限40% |
| **禁止脑补** | 人格不得编造缺失的功能、剧情、联机或商业化细节 |
| **强制免责** | 每份报告包含"AI生成的合成评审——非真实用户研究" |
| **刻板印象检测** | EthicsService含10+条检测规则 |

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
# 安装依赖
pip install -r requirements.txt

# 先设置 API Key
# Linux/macOS
export ANTHROPIC_API_KEY=your-key
# Windows PowerShell: $env:ANTHROPIC_API_KEY="your-key"
# Windows CMD: set ANTHROPIC_API_KEY=your-key

# 运行评审
python -m runner.cli steam_page_review examples/steam-page-sample/artifact.json
```

> ⚠️ **未设置 API Key 时，CLI 会退回模拟模式**：所有人格输出均为预制占位数据，**没有任何评审价值**，仅用于验证流水线能否跑通。请勿将模拟结果用于任何决策——该模式下 CLI 与所有生成的报告都会带有醒目警告。

**质量与实验命令**（统一 CLI）：

```bash
# 刻板印象检测评测：30条标注集（离线正则层）
python -m src.cli stereotype-eval
# 加上 LLM 复审层（需 ANTHROPIC_API_KEY）
python -m src.cli stereotype-eval --llm

# 人格分化消融实验：full vs no_behavior vs bare（需 API Key）
python -m src.cli ablation concept_review examples/steam-page-sample/artifact.json --limit 4 --output ablation.json
```

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
│   │   ├── cross_exam.py              #   结构化交叉质询
│   │   ├── aggregator.py              #   规则驱动报告聚合
│   │   └── calibration.py             #   质量校准检查
│   ├── personas/                      # 8个人格Pack（75+人格）
│   ├── presets/                       # 各任务类型面板预设
│   ├── schemas/                       # JSON Schema（人格、输出、报告）
│   ├── templates/                     # Prompt + 报告模板
│   └── config/                        # 聚合规则 + 预算配置
├── web/
│   ├── backend/                       # FastAPI 后端
│   │   └── app/
│   │       ├── api/                   #   25+ REST端点
│   │       ├── services/              #   4个核心服务
│   │       ├── models/                #   SQLAlchemy模型
│   │       ├── schemas/               #   Pydantic模型
│   │       └── websocket/             #   9个WebSocket事件
│   └── frontend/                      # React 前端
│       └── src/
│           ├── pages/                 #   12个页面
│           ├── components/            #   7个组件
│           └── store/                 #   2个Zustand Store
├── tests/                             # 180+ TDD测试
├── examples/                          # 7个示例素材
├── docs/                              # 文档
├── requirements.txt
└── pytest.ini
```

---

## 测试

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

**180+ 测试全部通过**

---

## 路线图

| 版本 | 重点 | 状态 |
|---|---|---|
| v0.1 | MVP — 16个人格、6种任务类型、CLI引擎、交叉质询、三层校验 | 已完成 |
| **v0.2** | **Harness版 — 8维质量门控、伦理服务、75+人格、Web UI** | **当前** |
| v0.3 | 人类对照研究、黄金输出回归、证据分级自动检测 | 计划中 |
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
