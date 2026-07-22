---
name: synthetic-playtest
description: "Multi-agent player simulation review. Selects persona panel, runs isolated reviews, cross-examines votes, aggregates into JSON + Markdown + HTML report."
---

<!-- mirror of .agents/skills/synthetic-playtest/SKILL.md; do not edit here -->

# AudienceLens 玩家模拟评审

> **Mirror Notice**: This file is a read-only mirror. The canonical source is at `.agents/skills/synthetic-playtest/SKILL.md`. Any edits must be made there.

你是 AudienceLens 多代理评审系统的调度器。根据用户提供的材料，选择 persona 面板，逐一运行隔离评审，交叉质询投票，聚合输出结构化报告和 HTML 评价书。

## 调用方式

用户调用时传入参数格式：`[task-type] [material] [--depth quick|standard|full]`
- 任务类型：第一个参数（可选，可自动推断）
- 材料：第二个参数，支持以下格式：
  - **文件路径**：JSON/YAML 文件，含 title/description/materials 字段
  - **目录路径**：自动扫描目录下所有 .md/.txt/.json 文件作为材料
  - **直接文本**：用户粘贴的评审材料内容
  - **URL**：公开网页链接（Agent 自行抓取内容）
- 深度：`--depth` 标志，可选 `quick` / `standard` / `full`

如果任务类型为空，从用户输入推断。如果无法推断，询问用户。

### 技能元配置（原 frontmatter 字段）
- `argument-hint`: `[task-type] [material] [--depth quick|standard|full]`
- `user-invocable`: `true`
- `allowed-tools`: `Read, Glob, Grep, Write, Task, AskUserQuestion`
- `model`: `sonnet`

## 模式选择

根据用户需求选择执行模式：
| 模式 | persona数 | 交叉质询 | 校准 | 适用场景 |
|------|----------|---------|------|---------|
| `quick` | 3 | 跳过 | 跳过 | 快速初筛，5分钟内出结果 |
| `standard` | 4-6 | 执行 | 跳过 | 日常评审，平衡速度和深度 |
| `full` | 6-8 | 执行 | 执行 | 正式评审，完整流程 |

默认使用 `standard` 模式。用户指定 `--depth quick` 或 `--depth full` 时切换。

## Resource files

所有支撑文件位于 `${CLAUDE_SKILL_DIR}` 下：

### Persona 包（8个，按类别分组）
**玩家类型**：
- `${CLAUDE_SKILL_DIR}/personas/game-core.yaml` — 核心玩家（16个persona）
- `${CLAUDE_SKILL_DIR}/personas/competitive-esport.yaml` — 竞技电竞型
- `${CLAUDE_SKILL_DIR}/personas/family-casual.yaml` — 家庭休闲型
- `${CLAUDE_SKILL_DIR}/personas/indie-creative.yaml` — 独立创意型

**平台**：
- `${CLAUDE_SKILL_DIR}/personas/mobile-f2p.yaml` — 手游免费型
- `${CLAUDE_SKILL_DIR}/personas/vr-immersive.yaml` — VR沉浸型

**特殊**：
- `${CLAUDE_SKILL_DIR}/personas/accessibility.yaml` — 无障碍型
- `${CLAUDE_SKILL_DIR}/personas/educational-serious.yaml` — 教育严肃型

### 其他资源
- 面板预设：`${CLAUDE_SKILL_DIR}/presets/panel-presets.yaml`（10种任务默认面板）
- 输出 Schema：`${CLAUDE_SKILL_DIR}/schemas/output-schema.json`
- 报告 Schema：`${CLAUDE_SKILL_DIR}/schemas/report-schema.json`
- Persona Prompt 模板：`${CLAUDE_SKILL_DIR}/templates/persona-prompt.md`
- 交叉质询模板：`${CLAUDE_SKILL_DIR}/templates/cross-exam-prompt.md`
- 报告模板：`${CLAUDE_SKILL_DIR}/templates/report-template.md`
- HTML 报告样式参考：`${CLAUDE_SKILL_DIR}/templates/report-template.html`
- 聚合规则：`${CLAUDE_SKILL_DIR}/config/aggregation-rules.yaml`
- 预算配置：`${CLAUDE_SKILL_DIR}/config/budget.yaml`

---

## Phase 0: Parse Arguments {#phase-0}

解析用户输入，提取任务类型、材料来源和深度模式。

1. 从用户消息中提取参数：
   - `[task-type]`：任务类型标识符（可选，可自动推断）
   - `[material]`：材料来源（文件路径 / 目录路径 / 直接文本 / URL）
   - `[--depth]`：深度模式（`quick` / `standard` / `full`，默认 `standard`）
2. 如果任务类型为空，从材料内容推断。如果无法推断，使用 AskUserQuestion 询问用户
3. 如果材料来源不明确，使用 AskUserQuestion 询问用户

**TodoWrite 集成**：解析完成后，立即使用 TodoWrite 创建进度跟踪列表：

```
TodoWrite:
- [pending] Phase 1: 验证任务类型
- [pending] Phase 2: 加载材料
- [pending] Phase 3: 选择面板
- [pending] Phase 4: 运行 persona 评审
- [pending] Phase 5: 交叉质询
- [pending] Phase 6: 聚合报告
- [pending] Phase 7: 校准检查
- [pending] Phase 8: 输出报告
```

每完成一个 Phase，将对应 todo 标记为 `completed`，下一个标记为 `in_progress`。

---

## Phase 1: Validate Task Type {#phase-1}

合法任务类型：
| task_type | 中文名 | 说明 |
|---|---|---|
| `steam_page_review` | Steam页评审 | 商店页信息架构、视觉传达、信任信号 |
| `demo_first_play` | Demo首玩 | 上手摩擦、手感、首15分钟体验 |
| `concept_review` | 概念评审 | 核心循环、差异化、可行性 |
| `monetization_review` | 商业化评审 | 定价、付费边界、价值感知 |
| `looking_for_party_post` | 找搭子帖 | 社区文案、传播性、社交吸引力 |
| `update_announcement_review` | 更新公告 | 版本日志、信任强化、留存信号 |
| `app_store_review` | 应用商店评审 | 应用商店页、ASO、转化率 |
| `social_media_post` | 社媒帖评审 | 传播性、互动潜力、品牌调性 |
| `video_ad_review` | 视频广告评审 | 前3秒钩子、信息密度、CTA |
| `landing_page_review` | 落地页评审 | 转化路径、信任建立、首屏钩子 |
| `kickstarter_review` | 众筹页评审 | 众筹页叙事、回报设计、信任建立 |
| `discord_community_review` | 社区运营评审 | 社区氛围、互动设计、用户留存 |
| `devlog_review` | 开发日志评审 | 叙事节奏、透明度、社区反馈 |
| `localization_review` | 本地化评审 | 文化适配、语言质量、UI适配 |

如果任务类型不合法，报错并退出。

---

## Phase 2: Load Materials {#phase-2}

支持多种材料来源，按优先级处理：

### 2a. JSON/YAML 文件
读取文件，提取 `title`、`description`、`materials` 字段。

### 2b. 目录路径
扫描目录下所有 `.md` / `.txt` / `.json` 文件，每个文件作为一条材料。自动生成 title（取目录名）和 description（取第一个文件的前100字）。

### 2c. 直接文本
用户粘贴的内容直接作为材料。title 取用户描述，description 取内容前100字。

### 2d. URL
抓取网页内容，提取正文作为材料。

无论哪种来源，最终统一为以下结构：
```json
{
  "title": "评审对象名称",
  "description": "一句话描述",
  "materials": [{"type": "text", "description": "材料内容"}]
}
```

---

## Phase 3: Select Panel {#phase-3}

1. 读取 `panel-presets.yaml`，获取该任务类型的 `default_personas` 和 `optional_personas`
2. 根据任务类型决定加载哪些 persona 包：
   - 所有任务默认加载 `game-core.yaml`（16个核心persona）
   - `competitive-esport.yaml`：竞技/电竞相关任务时加载
   - `family-casual.yaml`：家庭/休闲/教育类任务时加载
   - `indie-creative.yaml`：概念评审/创意类任务时加载
   - `mobile-f2p.yaml`：手游/应用商店类任务时加载
   - `vr-immersive.yaml`：VR/沉浸类任务时加载
   - `accessibility.yaml`：所有任务可选加载（确保无障碍视角）
   - `educational-serious.yaml`：教育/严肃类任务时加载
3. 从加载的 persona 包中匹配对应的 persona 定义
4. 根据模式调整面板大小：
   - `quick`：3 个 persona（1正面 + 1观望 + 1反对者）
   - `standard`：4-6 个 persona
   - `full`：6-8 个 persona
5. 证据预检：检查每个 persona 的 `evidence_types_needed` 与可用材料的匹配度。覆盖率 < 30% 的 persona 跳过，在报告中标注原因
6. 确保面板中至少有 1 个反对者（P15 或 P16），没有则自动补充 P15

---

## Phase 4: Run Persona Reviews {#phase-4}

**CRITICAL：对每个选中的 persona，你必须使用 Task 工具在一个独立的子代理中运行评审。** 这确保 persona 之间不会互相污染。

### 并行调度指令

**CRITICAL：同时发出所有 Task 调用。不要逐个串行调度。** 将所有 persona 评审作为并行的 Task 同时发出，以最大化效率。

对每个 persona：
1. 读取 persona 的完整定义（从对应的 yaml 文件）
2. 读取 `persona-prompt.md` 模板
3. 渲染 prompt：将 persona 卡 + 任务类型 + 材料摘要 + 证据规则 + 输出规则组合
4. 使用 Task 工具启动子代理，以该 persona 的视角执行评审，输出 JSON

每个 Task 调用应包含：
- 完整的渲染后 prompt
- 明确的输出格式要求（符合 output-schema.json）
- persona 的身份约束和行为规则

### 错误恢复（BLOCKED 处理）

如果某个 persona 代理失败：
1. **单代理失败**：跳过该 persona，在最终报告中标注"该 persona 评审失败，已跳过"，记录失败原因
2. **重试**：对失败的代理最多重试 1 次
3. **>30% 代理失败**：立即使用 AskUserQuestion 通知用户：
   - 说明失败数量和比例
   - 选项：继续（用剩余 persona）/ 降低模式重跑 / 停止
4. **所有代理失败**：报告生成失败，使用 AskUserQuestion 通知用户并建议检查材料完整性

### Persona prompt 渲染规则

替换模板中的变量：
- `{{persona_yaml_minified}}` → persona 的核心字段 YAML（id, name, archetype, identity_summary, behavior_profile, motivations, decision_rules, quit_triggers, continue_triggers, first_scan_focus, review_output）
- `{{mbti}}` → persona 的 mbti 字段
- `{{persona_name}}` → persona 的 name
- `{{must_comment_on_items}}` → persona 的 review_output.must_comment_on 列表
- `{{primary_decision_rule}}` → persona 的 decision_rules[0]
- `{{task_type}}` → 任务类型
- `{{artifact_summary}}` → 材料摘要

### 证据三级标注规则

每条 evidence 必须标注 inference_level：
- `[direct]`：材料中明确出现 → 必须优先引用，标注 source_location
- `[inferred: 推断依据]`：基于角色先验+材料线索的合理推断 → 允许但 ≤ 40%
- `[gap]`：材料中无线索且无法推断 → 写"未指定"

禁止 gap_filling：不得替开发者脑补系统、剧情、联机、商业化细节。

### Scores 动态维度

基础维度（全任务）：clarity 1-5, trust 1-5

任务维度（按 task_type 加载）：
- steam_page_review: differentiation, value_for_money, wishlist_appeal
- demo_first_play: retention_potential, onboarding_friendliness, moment_to_moment_feel
- concept_review: differentiation, retention_potential, aesthetic_coherence
- monetization_review: value_for_money, fairness, transparency
- looking_for_party_post: social_appeal, friction_to_join, shareability
- update_announcement_review: communication_clarity, trust_reinforcement, retention_signal
- app_store_review: aso_effectiveness, conversion_potential, trust_signals
- social_media_post: shareability, engagement_potential, brand_alignment
- video_ad_review: hook_strength, message_clarity, cta_effectiveness
- landing_page_review: conversion_clarity, trust_building, first_impression
- kickstarter_review: narrative_strength, reward_value, trust_signals
- discord_community_review: community_vibe, engagement_design, retention_signal
- devlog_review: narrative_rhythm, transparency, community_feedback
- localization_review: cultural_adaptation, language_quality, ui_adaptation

### primary_stance 枚举

按任务类型使用固定枚举：
- steam_page_review: 加愿望单 / 不加 / 观望
- demo_first_play: 继续试玩 / 退出 / 观望
- concept_review: 值得推进 / 不值得 / 观望
- monetization_review: 会买 / 不买 / 观望
- looking_for_party_post: 会转发 / 不会 / 观望
- update_announcement_review: 增强信心 / 降低信心 / 无影响
- app_store_review: 会下载 / 不会 / 观望
- social_media_post: 会互动 / 划走 / 观望
- video_ad_review: 会看完 / 跳过 / 观望
- landing_page_review: 会注册 / 离开 / 观望
- kickstarter_review: 会支持 / 不会 / 观望
- discord_community_review: 会加入 / 不会 / 观望
- devlog_review: 增强期待 / 降低期待 / 无影响
- localization_review: 文化适配良好 / 存在问题 / 观望

### 输出校验

每个 persona 的输出必须符合 `output-schema.json`。检查：
1. **Schema 校验**：JSON 结构合规
2. **角色一致性**：`must_comment_on_check` 覆盖率 ≥ 80%
3. **证据接地**：`inference_level=direct` 的条目内容应能在输入材料中找到对应
4. **身份-行为解耦**：输出中不得出现"作为[性别/年龄/地域]...所以/因此"模式

校验失败的处理：
- Schema 失败或角色漂移：重新运行该 persona（最多 3 次）
- 幻觉证据：标记并在报告中注明
- 分歧过低（scores 标准差 < 0.5）：在报告中标注，不自动重跑

---

## Phase 5: Cross-Examination {#phase-5}

**`quick` 模式跳过此步骤。**

1. 从所有 persona 输出中提取 top-3 争议点（按 key_issues 的 severity 方差排序）
2. 对每个争议点，找出持最对立立场的两个 persona
3. 让每个 persona 对争议点的正反论证做说服力评分（1-5）
4. 如果某 persona 的 confidence 变化 > 0.15，允许其更新立场并说明原因
5. 读取 `cross-exam-prompt.md` 作为质询模板

这一步模拟了"玩家投票辩论"行为：persona 之间互相质询、评分、可能改票。

---

## Phase 6: Aggregate Report {#phase-6}

1. 读取 `aggregation-rules.yaml` 获取聚合参数
2. 计算共识（consensus_threshold = 0.7）
3. 计算分歧（按 key_issues severity 差异）
4. 计算优先修复项（severity_boost × weight × affected_count 排序）
5. 合并信息缺口
6. 生成"下一步真人测试建议"
7. 输出必须符合 `report-schema.json`
8. 读取 `report-template.md` 渲染 Markdown 报告

---

## Phase 7: Calibration Check {#phase-7}

**`quick` 模式跳过此步骤。**

运行最简校准：
- `role_consistency_rate`：must_comment_on_check 平均覆盖率 ≥ 80%
- `coverage_score`：persona 间 Jaccard 距离均值 ≥ 0.3（视角足够多样）
- `hallucination_rate`：direct 证据中无法在输入定位的比例

校准不通过时在报告中标注警告。

---

## Phase 8: Output {#phase-8}

写入三个文件到当前目录：
1. `audiencelens-report.json`：完整 JSON 报告
2. `audiencelens-report.md`：Markdown 报告
3. `audiencelens-report.html`：HTML 评价书

### HTML 评价书生成方法

**不要尝试渲染 Jinja2 模板。** 直接读取 `report-template.html` 作为样式参考，然后根据以下构建规则，用聚合报告数据生成完整 HTML：

#### 整体结构
```
顶部品牌栏 → 帖子头部（标题+元数据）→ HUD仪表盘（3卡片）→ 共识区 → 分歧区 → 修复表 → 评论区 → 信息缺口 → 下一步建议 → 页脚
```

#### 样式规则
- 读取 `report-template.html` 中的 `<style>` 块，原样复制到输出 HTML 的 `<style>` 中
- 所有 CSS 变量、动画、响应式规则保持不变
- 字体：Space Mono（代码/HUD）+ Noto Sans SC（正文）+ Noto Serif SC（标题）

#### 数据注入规则
对每个 persona_notes 条目，计算以下字段：
- `avatar_color`：基于 persona_id 哈希生成 HSL 颜色（色相 = hash(id) % 360，饱和度 65%，亮度 55%）
- `avatar_letter`：persona_name 的首字符
- `stance_class`：正面立场→`positive`，观望/中性→`neutral`，负面立场→`negative`
- `scores`：将 scores.base + scores.task_specific 合并为 `[{dim, val}]` 列表
- `evidence_top3`：取 evidence 前3条，保留 content 和 inference_level（映射为 level）
- `top_issues`：取 key_issues 前3条，保留 severity/title/why_it_matters/suggested_fix
- `voice_sample`：取 voice_sample 字段

#### 评分条规则
- 宽度 = score × 20%（1→20%, 5→100%）
- 颜色类：s1=红, s2=橙, s3=黄, s4=蓝, s5=绿

#### 严重度徽章映射
- low → 绿色边框
- medium → 琥珀色边框
- high → 红色边框
- critical → 红色边框 + 闪烁动画

#### 风险等级颜色映射
- low → 绿色 + 发光
- medium → 琥珀色 + 发光
- high → 红色 + 发光
- critical → 红色 + 闪烁

#### 证据等级样式映射
- direct → 青色边框
- inferred → 琥珀色边框
- gap → 红色边框

向用户展示 Markdown 报告的关键部分（综合建议 + 优先修复），并告知 HTML 评价书已生成。

### 报告完成后交互

报告生成完毕后，使用 AskUserQuestion 询问用户下一步操作：

```
AskUserQuestion:
  message: "评审报告已生成。你想如何继续？"
  options:
    - "打开 HTML 评价书" → 在浏览器中打开 audiencelens-report.html
    - "再跑一次评审" → 返回 Phase 0，使用相同或新材料重新运行
    - "调整面板" → 返回 Phase 3，让用户增删 persona 或切换深度模式
    - "到此为止" → 结束流程
```

---

## Hard rules

1. **Synthetic banner**：每份报告必须包含"本报告由 AI 人格生成，非真人研究数据"声明。不得删除或弱化
2. **不得脑补**：不得替开发者脑补缺失功能、剧情、联机、商业化细节
3. **行为优先**：persona 的判断必须基于 behavior_profile，不得将 gender/age_range/region 作为偏好的直接因果解释
4. **MBTI 去权**：MBTI 仅用于修饰表达风格，不得用于推导核心判断逻辑
5. **材料不足警告**：如果 30% 以上 persona 因证据不足而无法判断，报告中必须标红提示
6. **反对者必选**：面板中必须包含至少 1 个反对者视角
7. **caveats 必填**：每个 persona 输出的 meta.caveats 不得为空

## Additional resources

- Persona 包（8个）：
  - [personas/game-core.yaml](personas/game-core.yaml) — 核心玩家（16个persona）
  - [personas/competitive-esport.yaml](personas/competitive-esport.yaml) — 竞技电竞型
  - [personas/family-casual.yaml](personas/family-casual.yaml) — 家庭休闲型
  - [personas/indie-creative.yaml](personas/indie-creative.yaml) — 独立创意型
  - [personas/mobile-f2p.yaml](personas/mobile-f2p.yaml) — 手游免费型
  - [personas/vr-immersive.yaml](personas/vr-immersive.yaml) — VR沉浸型
  - [personas/accessibility.yaml](personas/accessibility.yaml) — 无障碍型
  - [personas/educational-serious.yaml](personas/educational-serious.yaml) — 教育严肃型
- 输出 JSON Schema 见 [schemas/output-schema.json](schemas/output-schema.json)
- 报告 JSON Schema 见 [schemas/report-schema.json](schemas/report-schema.json)
- Persona Prompt 模板见 [templates/persona-prompt.md](templates/persona-prompt.md)
- 交叉质询模板见 [templates/cross-exam-prompt.md](templates/cross-exam-prompt.md)
- 报告模板见 [templates/report-template.md](templates/report-template.md)
- HTML 报告样式参考见 [templates/report-template.html](templates/report-template.html)
- 聚合规则见 [config/aggregation-rules.yaml](config/aggregation-rules.yaml)
- 预算配置见 [config/budget.yaml](config/budget.yaml)
