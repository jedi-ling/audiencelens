# AudienceLens Code Wiki

> 基于合成人格（Synthetic Persona）的多代理游戏评审系统 — 完整代码文档
>
> 版本：v2.0 | 更新：2026-06-04 | 基于源码分析生成

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [目录结构](#3-目录结构)
4. [核心模块详解](#4-核心模块详解)
   - 4.1 [Runner 引擎（src/runner/）](#41-runner-引擎srcrunner)
   - 4.2 [Persona 人格系统（src/personas/）](#42-persona-人格系统srcpersonas)
   - 4.3 [配置系统（src/config/）](#43-配置系统srcconfig)
   - 4.4 [Schema 校验（src/schemas/）](#44-schema-校验srcschemas)
   - 4.5 [Prompt 模板（src/templates/）](#45-prompt-模板srctemplates)
   - 4.6 [Web 后端（web/backend/）](#46-web-后端webbackend)
   - 4.7 [Web 前端（web/frontend/）](#47-web-前端webfrontend)
5. [评审执行流程](#5-评审执行流程)
6. [数据模型](#6-数据模型)
7. [API 接口文档](#7-api-接口文档)
8. [依赖关系](#8-依赖关系)
9. [项目运行方式](#9-项目运行方式)
10. [测试体系](#10-测试体系)
11. [伦理与安全机制](#11-伦理与安全机制)
12. [扩展与二次开发指南](#12-扩展与二次开发指南)

---

## 1. 项目概述

**AudienceLens** 是一个基于合成人格的多代理游戏评审系统。它使用行为驱动的 AI 人格面板，对独立游戏的 Steam 商店页、Demo、概念稿、商业化方案、社区文案和版本公告进行多视角评审，输出结构化的 JSON / Markdown / HTML 报告。

### 核心定位

- **不是**玩家研究工具，**不能**替代真人测试
- **是**预筛与压力测试工具，用于在投入真人测试资源之前发现最明显的问题
- **是**快速迭代工具，支持多轮快速评审

### 核心特性

| 特性 | 说明 |
|---|---|
| 行为驱动人格库 | 12 个行为轴刻画 persona，而非传统身份标签 |
| 10 种任务类型 | 覆盖 Steam 页、Demo、概念、商业化、社区、更新公告、众筹、Discord、开发日志、本地化 |
| 证据三级标注 | `[direct]` / `[inferred]` / `[gap]`，禁止脑补 |
| 焦点争议点质询 | 提取 top-3 争议点，正反论证 + 说服力评分 |
| 三层校验 | Schema 校验 + 角色一致性 + 证据接地 |
| 8 维度评估 | persona_differentiation / input_grounding / actionability 等 |
| 伦理合规 | 刻板印象检测、身份-行为解耦、MBTI 去权 |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      Browser                             │
│   React 19 + TypeScript + Tailwind CSS + shadcn/ui      │
│   Vite dev server (:5173)                                │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend                         │
│   uvicorn (:8000)                                        │
│   ┌──────────────┐  ┌───────────────┐  ┌──────────────┐ │
│   │  REST API    │  │  WebSocket    │  │  Background  │ │
│   │  /api/*      │  │  /ws/review/* │  │  Tasks       │ │
│   └──────────────┘  └───────────────┘  └──────┬───────┘ │
│                                                │         │
│   ┌────────────────────────────────────────────▼───────┐ │
│   │           src/runner/ (核心评审引擎)                │ │
│   │  panel_selector → evidence_precheck →              │ │
│   │  persona_agent → validator → cross_exam →          │ │
│   │  aggregator → calibration → cli                    │ │
│   └────────────────────────────────────────────────────┘ │
│                                                          │
│   ┌──────────────────┐  ┌─────────────────────────────┐ │
│   │  LLM Service     │  │  Ethics Service              │ │
│   │  (多模型网关)     │  │  (刻板印象检测)              │ │
│   └──────────────────┘  └─────────────────────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              SQLite / PostgreSQL                          │
│   reviews, persona_outputs, evaluation_results,          │
│   evaluation_scorecards, ethics_reports                  │
└─────────────────────────────────────────────────────────┘
```

### 架构分层

| 层级 | 职责 | 技术栈 |
|---|---|---|
| 前端展示层 | UI 交互、评审创建、报告可视化 | React 19 + TypeScript + Tailwind + shadcn/ui |
| API 网关层 | REST API + WebSocket 实时通信 | FastAPI + uvicorn |
| 业务服务层 | 评审编排、Persona 管理、LLM 调用、伦理检测 | Python (services/) |
| 核心引擎层 | 面板选择、Prompt 渲染、输出校验、质询、聚合、校准 | Python (src/runner/) |
| 数据持久层 | 评审记录、Persona 输出、评估结果 | SQLAlchemy + SQLite |

---

## 3. 目录结构

```
多人评审系统/
├── src/                              # 核心源码
│   ├── runner/                       # 评审引擎（CLI + 核心逻辑）
│   │   ├── cli.py                    # CLI 入口 + run_panel 编排
│   │   ├── panel_selector.py         # 面板选择 + 行为距离计算
│   │   ├── evidence_precheck.py      # 证据完整性预检
│   │   ├── persona_agent.py          # 单 persona 代理（Prompt 渲染 + 输出解析）
│   │   ├── validator.py              # 三层校验（Schema + 角色 + 证据）
│   │   ├── cross_exam.py             # 焦点争议点质询
│   │   ├── aggregator.py             # 规则驱动聚合 + 报告渲染
│   │   ├── calibration.py            # 校准 harness
│   │   └── __init__.py
│   ├── personas/                     # Persona 定义（8 个 Pack）
│   │   ├── game-core.yaml            # 首发 16 人格（核心玩家类型）
│   │   ├── competitive-esport.yaml   # 竞技电竞 Pack
│   │   ├── family-casual.yaml        # 家庭休闲 Pack
│   │   ├── indie-creative.yaml       # 独立创意 Pack
│   │   ├── mobile-f2p.yaml           # 移动免费 Pack
│   │   ├── vr-immersive.yaml         # VR 沉浸 Pack
│   │   ├── accessibility.yaml        # 无障碍 Pack
│   │   └── educational-serious.yaml  # 教育严肃 Pack
│   ├── presets/
│   │   └── panel-presets.yaml        # 10 种任务默认面板配置
│   ├── config/
│   │   ├── budget.yaml               # 成本配置 + 模型定价
│   │   └── aggregation-rules.yaml    # 聚合规则
│   ├── schemas/
│   │   ├── persona-schema.json       # Persona YAML 校验 Schema
│   │   ├── output-schema.json        # 单 persona 输出 Schema
│   │   └── report-schema.json        # 聚合报告 Schema
│   ├── templates/
│   │   ├── persona-prompt.md         # 五段式 Persona Prompt 模板
│   │   ├── cross-exam-prompt.md      # 交叉质询 Prompt 模板
│   │   ├── report-template.md        # Markdown 报告模板
│   │   └── report-template.html      # HTML 报告模板
│   └── __init__.py
├── web/                              # Web 应用
│   ├── backend/                      # FastAPI 后端
│   │   ├── app/
│   │   │   ├── main.py               # FastAPI 入口 + 生命周期
│   │   │   ├── api/__init__.py       # REST API 路由（全部端点）
│   │   │   ├── models/__init__.py    # SQLAlchemy 数据模型
│   │   │   ├── schemas/__init__.py   # Pydantic 请求/响应 Schema
│   │   │   ├── services/
│   │   │   │   ├── __init__.py       # PersonaService + ReviewService + MaterialExtractor
│   │   │   │   ├── llm_service.py    # 多模型 LLM 网关
│   │   │   │   ├── ethics_service.py # 伦理合规检测
│   │   │   │   └── evaluation_service.py # 8 维度评估
│   │   │   └── websocket/__init__.py # WebSocket 实时通信
│   │   ├── data/                     # SQLite 数据库文件
│   │   └── Dockerfile
│   ├── frontend/                     # React 前端
│   │   ├── src/
│   │   │   ├── App.tsx               # 路由定义
│   │   │   ├── pages/                # 页面组件
│   │   │   ├── components/           # UI 组件
│   │   │   ├── store/                # Zustand 状态管理
│   │   │   ├── lib/                  # 工具函数 + API 客户端
│   │   │   └── temp/                 # 临时 persona 数据
│   │   ├── vite.config.ts
│   │   ├── nginx.conf
│   │   └── Dockerfile
│   └── docker-compose.yml            # Docker 编排
├── tests/                            # 测试套件
│   ├── test_aggregator.py
│   ├── test_calibration.py
│   ├── test_cli.py
│   ├── test_cross_exam.py
│   ├── test_evidence_precheck.py
│   ├── test_panel_selector.py
│   ├── test_persona_agent.py
│   └── test_validator.py
├── examples/                         # 示例评审材料
│   ├── concept-sample/
│   ├── demo-sample/
│   ├── devlog-sample/
│   ├── kickstarter-sample/
│   ├── localization-sample/
│   ├── steam-page-sample/
│   └── discord-community-sample/
├── .claude/                          # Claude Code 集成
│   ├── agents/                       # 43+ 个 Agent persona 定义（.md）
│   ├── skills/synthetic-playtest/    # Claude Code Skill 定义
│   └── hooks/                        # 生命周期钩子
├── .trae/                            # Trae IDE 集成
│   ├── documents/                    # PRD + 技术架构文档
│   └── skills/                       # Trae Skill 定义
├── audiencelens-v0.2-harness/        # 评估 Harness
│   └── audiencelens-v0.2-harness/
│       ├── harness/                  # 评估器 + 评分标准
│       ├── personas/                 # Harness 专用 persona
│       └── docs/                     # 方法论文档
├── tools/
│   └── parity-check.py              # 一致性检查工具
├── requirements.txt                  # Python 依赖
├── pytest.ini                        # 测试配置
├── ETHICS.md                         # 伦理使用指南
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
└── README.md
```

---

## 4. 核心模块详解

### 4.1 Runner 引擎（src/runner/）

Runner 是 AudienceLens 的核心评审引擎，采用流水线架构，各模块职责清晰、可独立测试。

#### 4.1.1 cli.py — CLI 入口与编排

**源文件**：[cli.py](file:///c:/Users/Administrator/Desktop/多人评审系统/src/runner/cli.py)

**常量**：

| 名称 | 值 | 说明 |
|---|---|---|
| `VALID_TASK_TYPES` | 6 种任务类型列表 | CLI 支持的任务类型白名单 |

| 函数 | 签名 | 说明 |
|---|---|---|
| `load_artifact_bundle` | `(path: str) -> dict` | 加载评审材料包（支持 JSON/YAML，自动按扩展名判断） |
| `_build_simulated_output` | `(persona: dict, task_type: str) -> dict` | 构建模拟输出（无 API Key 时使用），包含 persona_id、stance、evidence、scores、key_issues 等 |
| `run_single_persona` | `(persona, task_type, artifact_summary, artifact_texts, config, artifact_bundle) -> dict` | 运行单个 persona 评审：选择模型 → 渲染 Prompt → 调用 Anthropic API 或模拟 → 解析输出 → 返回结果+成本 |
| `run_panel` | `(task_type, artifact_bundle, personas_path?, presets_path?, ...) -> dict` | **核心编排函数**：面板选择 → 预检 → 逐 persona 评审 → 校验 → 质询 → 聚合 → 校准 → 渲染报告 |
| `main` | `() -> None` | CLI 入口，argparse 解析参数，输出 JSON + Markdown + HTML 三种格式报告 |

**`run_panel` 执行流程：**

```
load_personas → load_presets → load_budget → load_rules → load_schema
    ↓
select_panel(task_type, personas, presets)
    ↓
precheck_panel(panel, artifact_bundle) → 过滤证据不足的 persona
    ↓
for each persona: run_single_persona → validate_output
    ↓
extract_controversy_points → render_cross_exam_prompt → 交叉质询
    ↓
aggregate_report → render_markdown_report → render_html_report
    ↓
run_calibration_check → 返回完整结果
```

#### 4.1.2 panel_selector.py — 面板选择

| 函数 | 说明 |
|---|---|
| `load_personas(yaml_path)` | 从 YAML 文件加载 persona 列表 |
| `load_presets(yaml_path)` | 从 YAML 文件加载面板预设 |
| `select_panel(task_type, personas, presets, ...)` | 根据任务类型选择默认面板，确保包含反对者（P15/P16） |
| `compute_behavioral_distance(p1, p2)` | 计算两个 persona 的行为距离（11 轴加权） |
| `ensure_diversity(selected, min_distance)` | 检查面板多样性，返回冗余对 |

**行为轴映射：**

| 轴名 | 级别 | 映射 |
|---|---|---|
| patience | 5 级 | 很低=1, 低=2, 中=3, 高=4, 很高=5 |
| genre_literacy | 5 级 | 同上 |
| novelty_seeking | 5 级 | 同上 |
| risk_tolerance | 3 级 | 低=1, 中=2, 高=3 |
| social_influence | 4 级 | 低=1, 中=2, 高=3, 很高=4 |
| completion_drive | 5 级 | 很低=1 ... 很高=5 |
| price_sensitivity | 5 级 | 同上 |
| emotional_engagement | 3 级 | 低=1, 中=2, 高=3 |
| agency_preference | 3 级 | 同上 |
| tolerance_for_ambiguity | 3 级 | 同上 |
| platform_loyalty | 3 级 | 同上 |

**反对者保证机制：** 如果默认面板中没有 P15（毒舌怀疑型）或 P16（竞品对标老兵），自动追加 P15。

#### 4.1.3 evidence_precheck.py — 证据完整性预检

| 函数 | 说明 |
|---|---|
| `load_evidence_types(artifact_bundle)` | 从材料包中提取所有证据类型 |
| `_fuzzy_match(needed_type, available_types)` | 模糊匹配证据类型（子串 + 字符重叠） |
| `check_evidence_coverage(persona, available_types)` | 检查单个 persona 的证据覆盖度 |
| `precheck_panel(personas, artifact_bundle)` | 预检整个面板，过滤证据不足的 persona |

**覆盖度阈值：** `coverage_ratio >= 0.3` 视为证据充分，低于此值的 persona 被跳过。

#### 4.1.4 persona_agent.py — 单 Persona 代理

| 函数 | 说明 |
|---|---|
| `_minify_persona(persona)` | 精简 persona 字典为核心字段，序列化为 YAML |
| `_convert_handlebars_to_jinja2(template_str)` | 将 Handlebars 模板语法转换为 Jinja2 |
| `render_prompt(persona, task_type, artifact_summary, template_path, artifact_bundle)` | 渲染 persona 评审 Prompt |
| `parse_persona_output(raw_output)` | 解析 LLM 原始输出为 JSON（支持代码块提取 + 括号匹配） |
| `estimate_cost(input_tokens, output_tokens, model, budget_config)` | 估算单次 API 调用成本 |
| `select_model(persona, budget_config)` | 根据 persona 的 model_hint 选择模型 |

**模型选择逻辑：**

| model_hint | 选择的模型 |
|---|---|
| `haiku` | claude-haiku（低成本） |
| `sonnet` | claude-sonnet（默认） |
| `opus` | claude-opus（高质量） |
| 无 | budget_config.default_model |

**Prompt 渲染流程：** 读取 persona-prompt.md 模板 → Handlebars → Jinja2 转换 → 注入 persona YAML + 任务类型 + 材料详情 → 输出完整 Prompt。

#### 4.1.5 validator.py — 三层校验

| 函数 | 说明 |
|---|---|
| `load_schema(schema_path)` | 加载 JSON Schema |
| `validate_schema(output, schema)` | **第一层：Schema 校验**（Draft7Validator） |
| `validate_role_consistency(output, persona)` | **第二层：角色一致性校验**（must_comment_on 覆盖率 ≥ 80%，inferred 比例 ≤ 40%） |
| `validate_evidence_grounding(output, artifact_texts)` | **第三层：证据接地校验**（direct 证据必须在材料中可定位，幻觉风险 < 30%） |
| `validate_output(output, persona, schema, artifact_texts)` | 三层校验统一入口 |
| `check_identity_behavior_decoupling(output)` | 身份-行为解耦检查（检测"因为性别所以..."类表述） |

**校验通过条件：** `schema_valid AND role_consistent AND evidence_grounded`

#### 4.1.6 cross_exam.py — 焦点争议点质询

| 函数 | 说明 |
|---|---|
| `extract_controversy_points(persona_outputs, top_n=3)` | 提取 top-N 争议点（按 severity 方差排序） |
| `find_opposing_stances(controversy_point, persona_outputs)` | 找到争议点的正反方 persona |
| `render_cross_exam_prompt(controversy_points, persona_outputs, template_path)` | 渲染交叉质询 Prompt |
| `parse_cross_exam_output(raw_output)` | 解析交叉质询输出 |

**争议点提取算法：**
1. 收集所有 persona 的 key_issues
2. 用 SequenceMatcher 合并相似问题（相似度 > 0.7）
3. 计算每个合并问题的 severity 方差
4. 按方差降序排列，取 top-N

#### 4.1.7 aggregator.py — 规则驱动聚合

| 函数 | 说明 |
|---|---|
| `load_aggregation_rules(rules_path)` | 加载聚合规则 YAML |
| `compute_consensus(persona_outputs, threshold=0.7)` | 计算共识（立场分布 + 阈值判定） |
| `compute_disagreements(persona_outputs)` | 计算主要分歧 |
| `compute_priority_fixes(persona_outputs, rules)` | 计算优先修复项（severity_boost × weight × affected_count） |
| `aggregate_report(persona_outputs, task_type, target, rules, ...)` | **核心聚合函数**，生成完整报告 JSON |
| `render_markdown_report(report, template_path)` | 渲染 Markdown 报告 |
| `render_html_report(report, template_path)` | 渲染 HTML 报告（含 stance 分类、avatar 颜色、评分条） |

**报告结构：**

```json
{
  "meta": { "task_type", "target", "build_version", "is_synthetic": true },
  "executive_summary": { "primary_recommendation", "release_risk", "evidence_quality" },
  "consensus": { "agreed_points", "questioned_points" },
  "major_disagreements": [...],
  "priority_fixes": [...],
  "persona_notes": [...],
  "information_gaps": [...],
  "next_human_test": { "suggested_tasks", "recruit_types", "next_materials" }
}
```

**发布风险判定：**

| 条件 | 风险等级 |
|---|---|
| critical + high 问题 ≥ 2 | critical |
| critical + high 问题 = 1 | high |
| 存在 medium 问题 | medium |
| 其他 | low |

#### 4.1.8 calibration.py — 校准 Harness

| 函数 | 说明 |
|---|---|
| `compute_role_consistency_rate(persona_outputs)` | 角色一致性率（must_comment_on 覆盖率） |
| `compute_coverage_score(persona_outputs)` | 视角覆盖度（Jaccard 距离均值） |
| `compute_hallucination_rate(persona_outputs, artifact_texts)` | 幻觉率（direct 证据无法在材料中定位的比例） |
| `compute_rerun_stability(outputs_run1, outputs_run2)` | 重跑稳定性（立场一致率 ≥ 80%） |
| `run_calibration_check(persona_outputs, artifact_texts, previous_outputs)` | 统一校准入口 |

**校准通过条件：** `role_consistency.average >= 0.8 AND coverage.average_distance >= 0.3`

---

### 4.2 Persona 人格系统（src/personas/）

#### Persona Pack 列表

| Pack 文件 | 分类 | 说明 |
|---|---|---|
| game-core.yaml | player-type | 首发 16 人格，覆盖核心玩家类型 |
| competitive-esport.yaml | player-type | 竞技电竞玩家 |
| family-casual.yaml | player-type | 家庭休闲玩家 |
| indie-creative.yaml | player-type | 独立创意玩家 |
| mobile-f2p.yaml | platform | 移动端免费玩家 |
| vr-immersive.yaml | platform | VR 沉浸玩家 |
| accessibility.yaml | special | 无障碍需求玩家 |
| educational-serious.yaml | special | 教育严肃游戏用户 |

#### Persona 数据结构（以 P01 为例）

```yaml
- id: P01-indie-core-operator
  name: 林岚
  gender: 女
  age_range: 25-32
  region: 中国华东
  language: [zh-CN, en-US]
  mbti: INTJ
  archetype: 核心独立探索者
  identity_summary: 更在意"这游戏是否真的有自己的一套东西"
  behavior_profile:          # 12 个行为轴
    patience: 高
    genre_literacy: 高
    novelty_seeking: 高
    risk_tolerance: 中
    social_influence: 低
    completion_drive: 中
    price_sensitivity: 中
    criticism_style: 分析直给
    emotional_engagement: 中
    agency_preference: 高
    tolerance_for_ambiguity: 高
    platform_loyalty: 中
  task_affinity:             # 任务亲和度（0-1）
    concept_review: 1.0
    steam_page_review: 0.7
    ...
  evidence_types_needed: [核心循环说明, 实机视频, 竞品对比]
  model_hint: sonnet
  motivations: [...]
  likes: [...]
  dislikes: [...]
  decision_rules: [...]      # 核心决策逻辑
  quit_triggers: [...]       # 退出触发条件
  continue_triggers: [...]   # 继续触发条件
  first_scan_focus: [...]    # 首次浏览关注点
  review_output:
    tone: 冷静分析
    strictness: 4
    must_comment_on: [独特性, 核心循环证据, 参考竞品, 首15分钟]
    avoid: [泛泛鼓励, 替开发者脑补内容]
```

#### 额外 Persona 来源

- **`.claude/agents/*.md`**：43+ 个 Markdown 格式的 persona 定义，由 Claude Code 使用
- **`.trae/skills/synthetic-playtest/personas/*.yaml`**：Trae IDE 专用 persona Pack

---

### 4.3 配置系统（src/config/）

#### budget.yaml — 成本配置

```yaml
max_cost_per_run_usd: 2.0
default_model: claude-sonnet
fallback_model: claude-haiku
premium_model: claude-opus
model_pricing:
  claude-haiku:  { input_per_mtok: 0.25,  output_per_mtok: 1.25 }
  claude-sonnet: { input_per_mtok: 3.0,   output_per_mtok: 15.0 }
  claude-opus:   { input_per_mtok: 15.0,  output_per_mtok: 75.0 }
retry:
  max_retries_per_persona: 3
  retry_on: [schema_failure, role_drift, hallucination]
  alert_on: [low_disagreement, time_drift]
```

#### aggregation-rules.yaml — 聚合规则

```yaml
consensus_threshold: 0.7
severity_boost: { critical: 2.0, high: 1.5, medium: 1.0, low: 0.5 }
cross_exam:
  max_controversy_points: 3
  confidence_change_threshold: 0.15
  allow_stance_update: true
```

---

### 4.4 Schema 校验（src/schemas/）

| Schema 文件 | 用途 |
|---|---|
| persona-schema.json | Persona YAML 定义校验 |
| output-schema.json | 单 persona 评审输出校验（24 个必填字段） |
| report-schema.json | 聚合报告校验 |

**output-schema.json 关键字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| persona_id | string | Persona 标识 |
| primary_stance | string | 主要立场（按 task_type 枚举约束） |
| confidence | number 0-1 | 立场确信度 |
| evidence_sufficiency | number 0-1 | 证据充分度 |
| evidence | array | 证据列表（content + inference_level + source_location） |
| scores.base | {clarity, trust} | 基础评分维度（1-5） |
| scores.task_specific | object | 任务特定评分维度（1-5） |
| key_issues | array | 关键问题（severity + title + why_it_matters + suggested_fix） |
| must_comment_on_check | object | 必须评论项覆盖检查 |
| voice_sample | string | 1-2 句角色原声评价 |
| meta.is_synthetic | boolean(true) | 合成标记（恒为 true） |

---

### 4.5 Prompt 模板（src/templates/）

#### persona-prompt.md — 五段式 Prompt

```
[PERSONA CARD]           → 注入精简 persona YAML
[MBTI USAGE BOUNDARY]    → MBTI 仅修饰表达风格，不推导判断
[IDENTITY-BEHAVIOR DECOUPLING] → 禁止身份因果推导
[TASK]                   → 任务类型 + 评审对象 + 材料详情
[EVIDENCE RULES]         → 三级标注规则 + 禁止脑补
[OUTPUT RULES]           → JSON 输出格式 + 立场枚举 + 评分维度
```

#### cross-exam-prompt.md — 交叉质询 Prompt

```
[CONTEXT]                → 争议点列表（正方/反方观点）
[TASK]                   → 每个 persona 独立评分 + 立场更新判定
[OUTPUT RULES]           → JSON 格式 + confidence 变化阈值 0.15
```

---

### 4.6 Web 后端（web/backend/）

#### main.py — FastAPI 入口

**源文件**：[main.py](file:///c:/Users/Administrator/Desktop/多人评审系统/web/backend/app/main.py)

- **数据库配置**：SQLite，路径 `web/backend/data/reviews.db`
- **生命周期管理**：启动时 `init_db()` + 加载 PersonaService + 加载 EvaluationService + 加载 EthicsService + 初始化 WebSocket 事件循环
- **安全中间件**：`SecurityHeadersMiddleware` — `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: strict-origin-when-cross-origin`、`Permissions-Policy: camera=(), microphone=(), geolocation=()`
- **CORS 配置**：允许 `localhost:5173/5175`
- **数据库迁移**：`_migrate_add_mode_column()` — 自动检测并添加 mode 列
- **应用版本**：`FastAPI(title="AudienceLens Review API", version="0.2.0")`

| 函数 | 说明 |
|---|---|
| `init_db()` | 创建数据库目录 + 建表 + 执行迁移 |
| `_migrate_add_mode_column()` | 检测 reviews 表是否缺少 mode 列，自动 ALTER TABLE |
| `lifespan(app)` | FastAPI 生命周期上下文管理器，启动时初始化所有服务 |
| `health_check()` | `GET /api/health` 健康检查端点 |

#### api/__init__.py — REST API 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/reviews | 创建评审（后台异步执行） |
| GET | /api/reviews | 列出评审（分页） |
| GET | /api/reviews/:id | 获取评审详情 |
| DELETE | /api/reviews/:id | 删除评审 |
| GET | /api/reviews/:id/report | 获取报告 |
| GET | /api/reviews/:id/result | 获取完整结果（含 HTML） |
| GET | /api/personas | 列出所有 persona |
| GET | /api/personas/packs | 列出 persona packs |
| GET | /api/personas/packs/:pack | 按 pack 列出 persona |
| GET | /api/personas/:id | 获取单个 persona |
| GET | /api/task-types | 列出任务类型 |
| GET | /api/review-modes | 列出评审模式 |
| GET | /api/presets | 列出面板预设 |
| GET | /api/examples | 列出示例材料 |
| POST | /api/extract-materials | 从文件提取评审材料 |
| GET | /api/settings/llm/formats | 列出 LLM API 格式 |
| GET | /api/settings/llm/presets | 列出 LLM 预设 |
| POST | /api/settings/llm | 保存 LLM 配置 |
| POST | /api/settings/llm/test | 测试 LLM 连接 |
| POST | /api/evaluations/:id | 运行评估 |
| GET | /api/evaluations/:id | 获取评估结果 |
| GET | /api/evaluations/:id/ethics | 获取伦理报告 |
| GET | /api/skills | 列出技能类型 |
| POST | /api/generate-personas | 生成 persona |
| GET | /api/rubric | 获取评分标准 |
| GET | /api/health | 健康检查 |

#### services/__init__.py — 核心服务

**PersonaService：**
- `load_all_personas()` — 从 `src/personas/*.yaml` 加载
- `load_agents_from_md()` — 从 `.claude/agents/*.md` 解析
- `load_trae_personas()` — 从 `.trae/skills/` 加载
- `get_all_personas()` — 合并三个来源
- `select_panel_by_mode()` — 根据评审模式选择面板
- `generate_personas()` — AI 生成 persona（有 API Key 时用 Claude，否则回退模板）

**ReviewService：**
- `create_review()` — 创建评审记录
- `run_review()` — **核心评审执行**（后台任务）
  - 逐 persona 调用 LLM → WebSocket 推送进度
  - 交叉质询 → 聚合 → 校准
  - 渲染 Markdown + HTML 报告

**MaterialExtractor：**
- `extract()` — 从上传文件提取评审材料
- `_extract_with_ai()` — AI 提取（Claude API）
- `_extract_fallback()` — 回退提取（正则/模板）

#### services/llm_service.py — 多模型 LLM 网关

**支持的 API 格式：**

| 格式 | 说明 | 适用模型 |
|---|---|---|
| anthropic | Anthropic 原生 Messages API | Claude 系列 |
| openai_compatible | OpenAI 兼容 Chat Completions API | GPT、DeepSeek、Ollama 等 |

**内置预设：** Anthropic Claude / OpenAI GPT / DeepSeek / Ollama 本地

**评审模式：**

| 模式 | Persona 数量 | 交叉质询 | 校准 | 说明 |
|---|---|---|---|---|
| quick | 3 | ❌ | ❌ | 快速初筛 |
| standard | 4-6 | ✅ | ❌ | 日常评审 |
| full | 6-8 | ✅ | ✅ | 正式评审 |

#### services/ethics_service.py — 伦理合规检测

- 10+ 条刻板印象检测规则（中英文）
- 从 `harness/evaluators/stereotype-check.md` 动态加载额外规则
- 评估 persona 输出的伦理合规性，生成 EthicsReport
- 计算面板差异化程度（Jaccard 距离）

#### services/evaluation_service.py — 8 维度评估

| 维度 | 说明 | 评分范围 |
|---|---|---|
| persona_differentiation | Persona 差异化程度 | 0-3 |
| input_grounding | 输入依据程度 | 0-3 |
| actionability | 可操作性 | 0-3 |
| segment_conflict | 群体冲突程度 | 0-3 |
| risk_detection | 风险检测程度 | 0-3 |
| ethical_persona_use | 伦理 persona 使用 | 0-3 |
| report_structure | 报告结构完整性 | 0-3 |
| calibration_honesty | 校准诚实度 | 0-3 |

**关键失败条件：** lacks disclaimer / has no P0/P1/P2 / uses stereotypes / not grounded / claims prediction

#### websocket/__init__.py — WebSocket 实时通信

- `ConnectionManager` 管理连接池
- Origin 白名单防跨站劫持
- `broadcast_sync()` 从后台线程安全推送

**WebSocket 事件：**

| 事件 | 说明 |
|---|---|
| persona_started | Persona 开始评审 |
| persona_completed | Persona 完成评审 |
| persona_failed | Persona 评审失败 |
| cross_exam_started | 交叉质询开始 |
| cross_exam_completed | 交叉质询完成 |
| aggregation_started | 聚合开始 |
| aggregation_completed | 聚合完成 |
| review_completed | 评审完成 |
| review_failed | 评审失败 |

---

### 4.7 Web 前端（web/frontend/）

#### 技术栈

| 技术 | 版本 | 用途 |
|---|---|---|
| React | 19.2+ | UI 框架 |
| TypeScript | 6.x | 类型安全 |
| Vite | 8.x | 构建工具 |
| Tailwind CSS | 4.x | 样式 |
| shadcn/ui | latest | 组件库 |
| Recharts | 3.x | 图表（雷达图、饼图） |
| React Router | 7.x | 路由 |
| Zustand | 5.x | 状态管理 |

#### 页面路由

| 路径 | 页面 | 说明 |
|---|---|---|
| / | HomePage | 首页（产品介绍 + 快速开始） |
| /review/new | CreateReviewPage | 创建评审 |
| /review/:id | ReviewProgressPage | 评审进度（实时 WebSocket） |
| /review/:id/report | ReportPage | 完整报告 |
| /personas | PersonasPage | Persona 浏览 |
| /task-types | TaskTypesPage | 任务类型说明 |
| /tutorial | TutorialPage | 教程 |
| /settings | SettingsPage | 设置（API Key、LLM 配置） |
| /privacy | PrivacyPage | 隐私政策 |
| /skills | SkillSelectPage | 技能选择 |
| /evaluations/:id | EvaluationPage | 评估结果 |

#### 关键组件

| 组件 | 说明 |
|---|---|
| PersonaRadarChart | 12 轴行为雷达图 |
| PersonaCard | Persona 详情卡片 |
| TaskTypeCard | 任务类型卡片 |
| CalibrationGauge | 校准指标仪表盘 |
| SeverityBadge | 严重程度徽章 |
| ParticleConstellation | 粒子星座动效 |

---

## 5. 评审执行流程

### 完整流程图

```
用户提交评审请求
    │
    ▼
创建 Review 记录 (status=pending)
    │
    ▼
后台任务启动 ──────────────────────────────────────────
    │
    ▼
PersonaService.select_panel_by_mode()
    │  根据 task_type + mode 选择 persona 面板
    ▼
precheck_panel() → 过滤证据不足的 persona
    │
    ▼
┌─── for each persona ────────────────────────────┐
│   │                                               │
│   ▼                                               │
│   render_prompt() → 渲染 persona 评审 Prompt      │
│   │                                               │
│   ▼                                               │
│   LLM API 调用 (或模拟输出)                        │
│   │                                               │
│   ▼                                               │
│   parse_persona_output() → 解析 JSON 输出          │
│   │                                               │
│   ▼                                               │
│   validate_output() → 三层校验                     │
│   │                                               │
│   ▼                                               │
│   WebSocket 推送 persona_completed                 │
│                                                   │
└───────────────────────────────────────────────────┘
    │
    ▼ (如果 mode 包含交叉质询)
extract_controversy_points() → 提取 top-3 争议点
    │
    ▼
render_cross_exam_prompt() → 渲染质询 Prompt
    │
    ▼
LLM API 调用 → parse_cross_exam_output()
    │
    ▼
WebSocket 推送 cross_exam_completed
    │
    ▼
aggregate_report() → 生成报告 JSON
    │
    ▼
render_markdown_report() + render_html_report()
    │
    ▼ (如果 mode 包含校准)
run_calibration_check()
    │
    ▼
更新 Review 记录 (status=completed)
    │
    ▼
WebSocket 推送 review_completed
```

---

## 6. 数据模型

### SQLAlchemy 模型

#### Review（评审）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String (UUID) | 主键 |
| task_type | String | 任务类型 |
| target_title | String | 评审对象名称 |
| artifact_bundle | JSON | 材料包 |
| persona_pack | String | 使用的 Pack |
| selected_personas | JSON | 选中的 persona ID 列表 |
| mode | String | 评审模式 (quick/standard/full) |
| status | String | 状态 (pending/running/completed/failed) |
| created_at | DateTime | 创建时间 |
| completed_at | DateTime | 完成时间 |
| total_cost_usd | Float | 总成本 |
| report_json | JSON | 报告 JSON |
| report_markdown | Text | 报告 Markdown |
| calibration | JSON | 校准结果 |

#### PersonaOutput（Persona 输出）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String (UUID) | 主键 |
| review_id | String (FK) | 关联 Review |
| persona_id | String | Persona 标识 |
| persona_name | String | Persona 名称 |
| status | String | 状态 |
| output_json | JSON | 输出 JSON |
| validation_result | JSON | 校验结果 |
| cost_usd | Float | 成本 |
| started_at | DateTime | 开始时间 |
| completed_at | DateTime | 完成时间 |

#### EvaluationResult（评估结果）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String (UUID) | 主键 |
| review_id | String (FK) | 关联 Review |
| dimension | String | 评估维度 |
| score | Integer | 评分 (0-3) |
| passed | Boolean | 是否通过 |
| details | Text | 评估详情 |
| evaluated_at | DateTime | 评估时间 |

#### EvaluationScorecard（评分卡）

| 字段 | 类型 | 说明 |
|---|---|---|
| review_id | String (FK, PK) | 关联 Review |
| overall_score | Integer | 总评分 (0-100) |
| passed | Boolean | 是否通过 |
| results_json | JSON | 各维度结果 |
| critical_failures_json | JSON | 关键失败列表 |

#### EthicsReport（伦理报告）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String (UUID) | 主键 |
| persona_id | String | Persona 标识 |
| passed | Boolean | 是否通过 |
| score | Integer | 评分 (0-100) |
| violations_json | JSON | 违规列表 |
| stereotype_risk | String | 刻板印象风险 (low/medium/high) |

---

## 7. API 接口文档

### 评审相关

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/reviews` | 创建评审，body: `{task_type, artifact_bundle, persona_pack?, selected_personas?, mode?}` |
| `GET` | `/api/reviews?offset=0&limit=20` | 列出评审 |
| `GET` | `/api/reviews/:id` | 获取评审详情 |
| `DELETE` | `/api/reviews/:id` | 删除评审 |
| `GET` | `/api/reviews/:id/report` | 获取报告 JSON + Markdown + 校准 |
| `GET` | `/api/reviews/:id/result` | 获取完整结果（含 HTML） |

### Persona 相关

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/personas` | 列出所有 persona |
| `GET` | `/api/personas/packs` | 列出 packs |
| `GET` | `/api/personas/packs/:pack` | 按 pack 列出 persona |
| `GET` | `/api/personas/:id` | 获取单个 persona |

### 配置相关

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/task-types` | 列出任务类型 |
| `GET` | `/api/review-modes` | 列出评审模式 |
| `GET` | `/api/presets` | 列出面板预设 |
| `GET` | `/api/examples` | 列出示例材料 |

### LLM 设置

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/settings/llm/formats` | 列出 API 格式 |
| `GET` | `/api/settings/llm/presets` | 列出 LLM 预设 |
| `POST` | `/api/settings/llm` | 保存 LLM 配置 |
| `POST` | `/api/settings/llm/test` | 测试连接 |

### 评估相关

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/evaluations/:id` | 运行评估 |
| `GET` | `/api/evaluations/:id` | 获取评估结果 |
| `GET` | `/api/evaluations/:id/ethics` | 获取伦理报告 |
| `GET` | `/api/rubric` | 获取评分标准 |

### WebSocket

| 端点 | 说明 |
|---|---|
| `WS /ws/review/:id` | 评审实时进度推送 |

### 其他

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/extract-materials` | 从文件提取材料 |
| `POST` | `/api/generate-personas` | 生成 persona |
| `GET` | `/api/skills` | 列出技能类型 |
| `GET` | `/api/health` | 健康检查 |

---

## 8. 依赖关系

### Python 依赖（requirements.txt）

| 包 | 版本 | 用途 |
|---|---|---|
| anthropic | ≥0.40.0 | Claude API 客户端 |
| pyyaml | ≥6.0 | YAML 解析 |
| jsonschema | ≥4.21.0 | JSON Schema 校验 |
| rich | ≥13.7.0 | CLI 美化输出 |
| jinja2 | ≥3.1.3 | 模板渲染 |
| pytest | ≥8.0.0 | 测试框架 |
| pytest-asyncio | ≥0.23.0 | 异步测试 |

### Web 后端额外依赖

| 包 | 用途 |
|---|---|
| fastapi | Web 框架 |
| uvicorn | ASGI 服务器 |
| sqlalchemy | ORM |
| litellm | 多模型 LLM 网关 |
| python-socketio / websockets | WebSocket |

### Web 前端依赖

| 包 | 用途 |
|---|---|
| react@19.2+ | UI 框架 |
| typescript@6.x | 类型安全 |
| vite@8.x | 构建工具 |
| tailwindcss@4.x | 样式 |
| shadcn/ui | 组件库 |
| recharts@3.x | 图表 |
| react-router@7.x | 路由 |
| zustand@5.x | 状态管理 |

### 模块间依赖关系

```
cli.py ──────→ panel_selector.py ──→ personas/*.yaml
   │                │
   │                ▼
   │          evidence_precheck.py
   │                │
   │                ▼
   ├───────→ persona_agent.py ──→ templates/persona-prompt.md
   │                │
   │                ▼
   ├───────→ validator.py ──→ schemas/output-schema.json
   │                │
   │                ▼
   ├───────→ cross_exam.py ──→ templates/cross-exam-prompt.md
   │                │
   │                ▼
   ├───────→ aggregator.py ──→ config/aggregation-rules.yaml
   │                │           templates/report-template.md
   │                │           templates/report-template.html
   │                ▼
   └───────→ calibration.py

web/backend/app/services/__init__.py ──→ runner/* (全部模块)
web/backend/app/services/llm_service.py ──→ runner/persona_agent.py, runner/cross_exam.py
web/backend/app/services/ethics_service.py ──→ harness/evaluators/stereotype-check.md
web/backend/app/services/evaluation_service.py ──→ harness/evaluators/*, harness/rubrics/*
```

---

## 9. 项目运行方式

### 方式1：Python CLI

```bash
# 安装依赖
pip install -r requirements.txt

# 模拟模式（无需 API Key）
python -m runner.cli steam_page_review examples/steam-page-sample/artifact.json

# 真实 API 模式
set ANTHROPIC_API_KEY=your-api-key
python -m runner.cli steam_page_review examples/steam-page-sample/artifact.json

# 指定输出目录
python -m runner.cli steam_page_review examples/steam-page-sample/artifact.json --output-dir ./reports
```

### 方式2：Web 应用（开发模式）

```bash
# 后端
cd web/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install fastapi uvicorn sqlalchemy litellm anthropic pyyaml jsonschema jinja2
uvicorn app.main:app --reload --port 8000

# 前端（新终端）
cd web/frontend
npm install
npm run dev
```

### 方式3：Docker Compose

```bash
cd web
docker-compose up -d
```

### 方式4：Claude Code Skill

```bash
# 安装 Skill
Expand-Archive synthetic-playtest.skill.zip -DestinationPath .claude/skills/synthetic-playtest/

# 在 Claude Code 中调用
/synthetic-playtest steam_page_review examples/steam-page-sample/artifact.json
```

### 方式5：程序化调用

```python
from runner.cli import run_panel
import json

with open('examples/steam-page-sample/artifact.json') as f:
    artifact = json.load(f)

result = run_panel(
    task_type='steam_page_review',
    artifact_bundle=artifact
)

print(result['markdown'])
print(result['report'])
print(result['calibration'])
```

---

## 10. 测试体系

### 测试文件

| 文件 | 测试模块 |
|---|---|
| test_aggregator.py | aggregator.py |
| test_calibration.py | calibration.py |
| test_cli.py | cli.py |
| test_cross_exam.py | cross_exam.py |
| test_evidence_precheck.py | evidence_precheck.py |
| test_panel_selector.py | panel_selector.py |
| test_persona_agent.py | persona_agent.py |
| test_validator.py | validator.py |

### 运行测试

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

### 测试配置（pytest.ini）

测试使用 pytest 框架，支持 pytest-asyncio 异步测试。

---

## 11. 伦理与安全机制

### 行为约束

| 机制 | 说明 |
|---|---|
| 证据三级标注 | `[direct]` / `[inferred]` / `[gap]`，inferred ≤ 40% |
| 禁止脑补 | 不得替开发者脑补缺失功能、剧情、联机、商业化细节 |
| 身份-行为解耦 | 禁止"因为性别/年龄所以..."类因果推导 |
| MBTI 去权 | MBTI 仅修饰表达风格，不推导核心判断 |
| Demographics 正交化 | 每个敏感属性值至少出现在两个不同 archetype |

### 安全措施

| 措施 | 位置 |
|---|---|
| 安全响应头 | main.py — SecurityHeadersMiddleware |
| CORS 白名单 | main.py — CORSMiddleware |
| WebSocket Origin 验证 | websocket/__init__.py |
| API Key Base64 编码 | llm_service.py |
| 文件上传限制 | api/__init__.py — 10MB + 扩展名白名单 + 路径穿越防护 |
| 刻板印象检测 | ethics_service.py — 10+ 条正则规则 |

### 伦理报告

每份报告必须包含：
1. **Synthetic Banner** — 不得删除或弱化
2. **Limitations & Caveats** — 限制声明
3. **"合成评审"标注** — 任何对外展示中明确标注

---

## 12. 扩展与二次开发指南

### 添加新 Persona

1. 在 `src/personas/` 对应 Pack YAML 中添加 persona 定义
2. 确保包含 12 个行为轴 + decision_rules + quit/continue triggers
3. 在 `src/presets/panel-presets.yaml` 中配置默认面板
4. 运行测试确保校验通过

### 添加新任务类型

1. 在 `src/runner/cli.py` 的 `VALID_TASK_TYPES` 中添加
2. 在 `src/presets/panel-presets.yaml` 中配置默认面板
3. 在 `src/templates/persona-prompt.md` 中添加立场枚举和评分维度
4. 在 `src/schemas/output-schema.json` 的 task_type enum 中添加
5. 在 `web/backend/app/services/__init__.py` 的 `TASK_TYPES` 中添加

### 添加新 LLM 提供商

1. 在 `web/backend/app/services/llm_service.py` 的 `API_FORMATS` 中添加格式
2. 在 `API_PRESETS` 中添加预设
3. litellm 会自动处理兼容格式

### 添加新评估维度

1. 在 `web/backend/app/services/evaluation_service.py` 的 `RUBRIC_DIMENSIONS` 中添加
2. 在 `RUBRIC_SCORES` 中定义 0-3 评分标准
3. 实现 `_eval_<dimension>()` 方法
4. 在 `evaluate_dimension()` 中添加分支

---

## 附录：10 种任务类型速查

| 任务类型 | 中文名 | 立场枚举 | 评分维度 |
|---|---|---|---|
| steam_page_review | Steam页评审 | 加愿望单/不加/观望 | differentiation, value_for_money, wishlist_appeal |
| demo_first_play | Demo首玩 | 继续试玩/退出/观望 | retention_potential, onboarding_friendliness, moment_to_moment_feel |
| concept_review | 概念评审 | 值得推进/不值得/观望 | differentiation, retention_potential, aesthetic_coherence |
| monetization_review | 商业化评审 | 会买/不买/观望 | value_for_money, fairness, transparency |
| looking_for_party_post | 找搭子帖 | 会转发/不会/观望 | social_appeal, friction_to_join, shareability |
| update_announcement_review | 更新公告 | 增强信心/降低信心/无影响 | communication_clarity, trust_reinforcement, retention_signal |
| kickstarter_review | 众筹页评审 | 会支持/不会/观望 | trust_building, value_perception, urgency_communication, community_mobilization |
| discord_community_review | 社区运营评审 | 会加入/不会/观望 | community_atmosphere, developer_engagement, information_value, organization_governance |
| devlog_review | 开发日志评审 | 增强期待/降低期待/无影响 | transparency, information_density, expectation_management, narrative_appeal |
| localization_review | 本地化评审 | 文化适配良好/存在问题/观望 | text_accuracy, cultural_adaptation, ui_adaptation, terminology_consistency, contextual_fidelity |
