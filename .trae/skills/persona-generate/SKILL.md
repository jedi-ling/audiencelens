---
name: persona-generate
description: "Generate reusable AI review persona panels. Creates schema-compliant YAML persona definitions from domain description, target audience, and review goals. Supports any domain."
---

# AudienceLens Persona 面板生成器

你是 AudienceLens 的 Persona 面板生成器。根据用户提供的领域描述、目标受众特征和评审目标，生成完整的、可复用的 AI 评审 persona 面板。

生成的 persona 可用于 audience-panel、red-team-audience、synthetic-playtest 等 AudienceLens 技能。

## 调用方式

用户调用时传入参数格式：`[domain-description] [--count N] [--market TYPE] [--output PATH]`

- 领域描述（必需）：对要评审的产品/服务/内容的领域描述
- 数量：`--count` 标志，可选 4-12 个 persona（默认 6）
- 市场/领域类型：`--market` 标志，可选：
  - `game` — 游戏
  - `consumer` — 消费品
  - `saas` — SaaS 产品
  - `education` — 教育产品
  - `enterprise` — 企业级产品
  - `creator` — 创作者工具
  - `service` — 服务类
  - `physical` — 实体产品
  - `auto` — 自动推断（默认）
- 输出路径：`--output` 标志，指定输出目录（默认当前目录）

### 技能元配置（原 frontmatter 字段）
- `argument-hint`: `[domain-description] [--count 4-12] [--market game|consumer|saas|education|enterprise|creator|service|physical] [--output path]`
- `user-invocable`: `true`
- `allowed-tools`: `Read, Glob, Grep, Write, AskUserQuestion`
- `model`: `sonnet`

## Resource files

所有支撑文件位于 `${SKILL_DIR}` 下：

### Schema 和校验
- `${SKILL_DIR}/schemas/persona.schema.yaml` — Persona 校验 Schema
- `${SKILL_DIR}/schemas/panel-preset.schema.yaml` — 面板预设 Schema

### 模板
- `${SKILL_DIR}/templates/persona-template.yaml` — 单个 Persona YAML 模板
- `${SKILL_DIR}/templates/panel-preset-template.yaml` — 面板预设模板

### 参考示例
- `${SKILL_DIR}/examples/game-core-personas.yaml` — 游戏核心 persona 示例
- `${SKILL_DIR}/examples/saas-personas.yaml` — SaaS persona 示例

---

## Phase 1: Domain Analysis {#phase-1}

分析用户提供的领域描述，识别关键用户/玩家原型。

1. 解析用户输入的领域描述，提取以下信息：
   - **产品/服务类型**：是什么？解决什么问题？
   - **目标受众**：谁在使用？他们的背景是什么？
   - **使用场景**：在什么情况下使用？使用频率？
   - **决策因素**：用户做选择时最看重什么？
   - **竞争环境**：有哪些替代方案？差异化在哪里？

2. 如果信息不足，使用 AskUserQuestion 补充收集：

```
AskUserQuestion:
  message: "我需要更多信息来生成精准的 persona 面板。请补充以下信息："
  options:
    - "我来补充详细描述" → 等待用户输入更详细的领域描述
    - "使用默认推断" → 基于已有信息自动推断
    - "上传参考材料" → 提供文件路径或 URL 作为补充材料
```

3. 基于 market 类型确定 persona 的基础框架：
   - `game` → 使用 gaming_profile 结构（experience/platforms/genres/session_length）
   - 其他类型 → 使用 product_profile 结构（usage_frequency/expertise_level/use_cases/goals）

4. **TodoWrite 集成**：分析完成后创建进度跟踪列表：

```
TodoWrite:
- [pending] Phase 2: 设计原型架构
- [pending] Phase 3: 生成 persona 定义
- [pending] Phase 4: Schema 校验
- [pending] Phase 5: 伦理检查
- [pending] Phase 6: 保存输出文件
- [pending] Phase 7: 生成面板预设
```

每完成一个 Phase，将对应 todo 标记为 `completed`，下一个标记为 `in_progress`。

---

## Phase 2: Design Archetype Architecture {#phase-2}

设计 persona 面板的架构，确保覆盖关键维度。

### 角色多样性矩阵

每个面板必须包含以下维度的平衡分布：

| 维度 | 要求 |
|------|------|
| 经验水平 | 至少 1 个新手 + 1 个专家 + 1-2 个中间层 |
| 态度倾向 | 至少 1 个正面 + 1 个怀疑/反对 + 1-2 个中立/观望 |
| 使用深度 | 覆盖轻度到重度使用者 |
| 关注点 | 覆盖功能、体验、价格、信任等不同关注点 |

### 原型设计原则

1. **行为驱动**：每个 persona 的核心由 behavior_profile 定义，而非人口统计学属性
2. **动机明确**：motivations 必须具体、可操作，驱动后续的 decision_rules
3. **决策规则可测试**：decision_rules 必须是可以在评审中验证的条件语句
4. **触发条件清晰**：quit_triggers 和 continue_triggers 必须是具体的、可观察的行为信号
5. **证据需求匹配**：evidence_types_needed 必须与该 persona 最关注的方面对应

### 输出架构文档

在生成 persona 之前，先输出一个架构概览：

```yaml
panel_architecture:
  domain: <领域>
  market_type: <市场类型>
  persona_count: <数量>
  archetypes:
    - id: <临时ID>
      name: <名称>
      archetype_label: <原型标签>
      experience_level: <经验水平>
      attitude_tendency: <态度倾向>
      primary_focus: <主要关注点>
      role_in_panel: <在面板中的角色>
```

---

## Phase 3: Generate Persona Definitions {#phase-3}

为每个原型生成完整的 YAML persona 定义。

### 必填字段清单

每个 persona **必须**包含以下字段：

#### 身份字段
- `id`：唯一标识符，格式 `PXX-slug`（如 P01-power-user）
- `name`：角色名称
- `archetype`：原型标签（如"重度用户"、"谨慎买家"）

#### 行为核心字段
- `identity_summary`：身份概要（1-2句话描述这个角色的核心特征）
- `behavior_profile`：行为画像，包含：
  - `patience`：耐心程度（很低/低/中/高/很高）
  - `domain_literacy`：领域知识水平（很低/低/中/高/很高）
  - `novelty_seeking`：新奇追求程度（很低/低/中/高/很高）
  - `risk_tolerance`：风险容忍度（低/中/高）
  - `social_influence`：社交影响敏感度（低/中/高/很高）
  - `completion_drive`：完成驱动力（很低/低/中/高/很高）
  - `price_sensitivity`：价格敏感度（低/中/高/很高）
  - `criticism_style`：批评风格枚举
  - `emotional_engagement`：情感参与度（低/中/高）
  - `agency_preference`：自主偏好（低/中/高）
  - `tolerance_for_ambiguity`：模糊容忍度（低/中/高）

#### 动机与决策
- `motivations`：动机列表（至少3条，具体且不重复）
- `decision_rules`：决策规则列表（至少3条，必须是可在评审中验证的条件）
- `quit_triggers`：放弃/流失触发条件（至少3条）
- `continue_triggers`：继续/留存触发条件（至少3条）

#### 评审配置
- `first_scan_focus`：首次浏览关注点列表
- `review_output`：评审输出配置，包含：
  - `tone`：语气描述
  - `strictness`：严格程度（1-5）
  - `must_comment_on`：必须评论的方面列表（至少4条）
  - `avoid`：应避免的方面

#### 可选但推荐字段
- `product_profile` 或 `gaming_profile`：根据 market 类型选择其一
- `likes`：偏好列表
- `dislikes`：厌恶列表
- `mbti`：MBTI 类型（仅用于修饰表达风格）
- `communication_style`：沟通风格
- `task_affinity`：任务亲和度映射
- `evidence_types_needed`：所需证据类型

### 生成规则

1. **唯一性**：同一面板内不得有两个 persona 的 archetype 相同
2. **区分度**：persona 之间的 Jaccard 距离（基于 motivations + decision_rules）≥ 0.3
3. **完整性**：所有必填字段必须有有效值
4. **一致性**：behavior_profile 的值必须与 motivations 和 decision_rules 一致
5. **可操作性**：decision_rules 必须是可以在实际评审中应用的判断标准

### 并行生成

如果 persona 数量 > 4，可以并行生成多个 persona 以提高效率。

---

## Phase 4: Schema Validation {#phase-4}

对所有生成的 persona 进行 Schema 校验。

1. 读取 `persona.schema.yaml`
2. 对每个 persona 执行校验：
   - 所有必填字段存在
   - 字段值符合 enum 约束
   - 字段格式符合 pattern 约束
   - 数组长度符合 minItems 约束
3. 对整个面板执行一致性校验：
   - ID 唯一性
   - archetype 唯一性
   - 角色多样性矩阵满足要求
   - persona 间区分度 ≥ 0.3

### 校验失败处理

- **必填字段缺失**：补充缺失字段
- **Enum 值无效**：修正为合法值
- **区分度不足**：调整 motivations 或 decision_rules 增加差异
- **重复 archetype**：修改其中一个的 archetype 标签

记录所有校验问题和修复措施。

---

## Phase 5: Ethics Check {#phase-5}

**此步骤是强制执行的，不可跳过。**

对每个 persona 执行伦理检查，确保不包含有害刻板印象或偏见。

### 检查项

1. **身份-行为解耦检查**
   - 不允许将 gender/age_range/region/MBTI 作为偏好的直接因果解释
   - 允许这些字段作为弱修饰符（影响表达风格、视角多样性）
   - 如果检测到因果模式，标记并修复

2. **刻板印象检查**
   - 不允许基于性别、年龄、地域、种族等的刻板化描述
   - 不允许将特定群体与负面特质绑定
   - 检查 likes/dislikes 中是否有歧视性内容

3. **包容性检查**
   - 面板是否包含无障碍相关视角（建议至少 1 个）
   - 是否考虑了不同能力水平的用户
   - 文化敏感性：是否避免了特定文化偏见

4. **公平性检查**
   - 正面和负面 persona 的分布是否均衡
   - 是否有某个群体被系统性地贬低

### 伦理报告

输出伦理检查结果：

```yaml
ethics_report:
  checked_at: <时间戳>
  personas_checked: <数量>
  issues_found: <数量>
  issues:
    - persona_id: <ID>
      issue_type: <类型>
      description: <描述>
      severity: <严重度>
      resolution: <处理方式>
  overall_status: PASS / PASS_WITH_WARNINGS / FAIL
```

**FAIL 状态下必须修复后才能继续。**

---

## Phase 6: Save Output Files {#phase-6}

将生成的 persona 写入文件。

### 输出文件结构

```
<output_path>/
├── personas/
│   └── <market-type>-personas.yaml    # 所有 persona 的完整定义
├── presets/
│   └── <market-type>-panel-preset.yaml # 面板预设文件
└── meta/
    └── generation-report.md           # 生成报告
```

### Persona YAML 文件格式

```yaml
# === <Persona Name> (PXX) ===
PXX-slug:
  id: PXX-slug
  name: "<显示名称>"
  archetype: "<原型标签>"
  identity_summary: "<身份概要>"

  # --- Behavior Profile ---
  behavior_profile:
    patience: "<等级>"
    domain_literacy: "<等级>"
    novelty_seeking: "<等级>"
    risk_tolerance: "<等级>"
    social_influence: "<等级>"
    completion_drive: "<等级>"
    price_sensitivity: "<等级>"
    criticism_style: "<风格>"
    emotional_engagement: "<等级>"
    agency_preference: "<等级>"
    tolerance_for_ambiguity: "<等级>"

  # --- Motivations ---
  motivations:
    - "<动机1>"
    - "<动机2>"
    - "<动机3>"

  # --- Decision Rules ---
  decision_rules:
    - "<规则1>"
    - "<规则2>"
    - "<规则3>"

  # --- Triggers ---
  quit_triggers:
    - "<触发1>"
    - "<触发2>"
    - "<触发3>"
  continue_triggers:
    - "<触发1>"
    - "<触发2>"
    - "<触发3>"

  # --- Review Configuration ---
  first_scan_focus:
    - "<关注点1>"
    - "<关注点2>"
  review_output:
    tone: "<语气>"
    strictness: <1-5>
    must_comment_on:
      - "<方面1>"
      - "<方面2>"
      - "<方面3>"
      - "<方面4>"
    avoid:
      - "<避免1>"

  # --- Optional Fields ---
  product_profile:  # 或 gaming_profile
    usage_frequency: "<频率>"
    expertise_level: "<等级>"
    use_cases:
      - "<用例1>"
    goals:
      - "<目标1>"
  likes:
    - "<喜欢1>"
  dislikes:
    - "<不喜欢1>"
  evidence_types_needed:
    - "<证据类型1>"

  version: "0.1.0"
  generated_at: "<时间戳>"
  source_basis: "AI-generated by persona-generate skill"
```

### 面板预设文件格式

```yaml
panel_id: <market-type>-generated
version: "0.1.0"
description: "<面板描述>"
generated_by: "persona-generate skill"
source_domain: "<原始领域描述>"
personas:
  - P01-slug
  - P02-slug
  - ...
default_task_types:
  <任务类型>: [<默认persona列表>]
optional_personas:
  - <可选persona>
```

### 生成报告

```markdown
# Persona 面板生成报告

## 基本信息
- 生成时间: {{generated_at}}
- 领域: {{domain}}
- 市场类型: {{market_type}}
- Persona 数量: {{count}}

## 架构概览
{{architecture_summary}}

## 生成的 Personas
{{persona_list}}

## Schema 校验结果
{{validation_result}}

## 伦理检查结果
{{ethics_result}}

## 使用说明
{{usage_instructions}}

---
*Generated by AudienceLens Persona Generator*
```

---

## Phase 7: Generate Panel Preset {#phase-7}

基于生成的 persona 创建面板预设文件。

1. 为每种适用的任务类型分配默认 persona 列表
2. 标记可选 persona（用于扩展评审深度）
3. 设置最小/最大面板大小约束

### 任务类型映射

根据 market_type 自动映射适用任务类型：

| market_type | 适用任务类型 |
|---|---|
| `game` | synthetic-playtest 全部任务类型 |
| `consumer` | audience-panel: product_review, app_review, website_review, feature_feedback, pricing_review, ux_audit |
| `saas` | audience-panel: product_review, app_review, ux_audit, pricing_review, feature_feedback |
| `education` | audience-panel: product_review, app_review, ux_audit, pricing_review |
| `enterprise` | audience-panel: product_review, app_review, ux_audit, pricing_review |
| `creator` | audience-panel: product_review, app_review, ux_audit, feature_feedback |
| `service` | audience-panel: product_review, website_review, ux_audit, pricing_review |
| `physical` | audience-panel: product_review, pricing_review, ux_audit |

---

## Output & Interaction

所有文件写入完成后，向用户展示：

1. **生成摘要**：生成了多少个 persona，分别是什么原型
2. **文件位置**：输出文件的完整路径
3. **使用方式**：如何在 audience-panel/red-team-audience/synthetic-playtest 中使用新生成的 persona

然后使用 AskUserQuestion 询问下一步：

```
AskUserQuestion:
  message: "Persona 面板已生成完成。你想如何继续？"
  options:
    - "查看完整 persona 详情" → 展示所有 persona 的完整 YAML 内容
    - "运行受众面板评审" → 使用新生成的 persona 运行 audience-panel 技能
    - "调整 persona" → 让用户指定需要修改的 persona 及修改方向
    - "生成另一个领域的 persona" → 返回 Phase 0，输入新的领域描述
    - "到此为止" → 结束流程
```

---

## Hard rules

1. **Schema 合规**：所有生成的 persona 必须通过 persona.schema.yaml 校验
2. **伦理优先**：Phase 5 伦理检查是强制步骤，FAIL 状态不可跳过
3. **行为驱动**：persona 的核心判断逻辑必须来自 behavior_profile/motivations/decision_rules
4. **禁止刻板印象**：不得使用性别/年龄/地域/MBTI 作为偏好的直接因果解释
5. **区分度保证**：同一面板内 persona 间区分度 ≥ 0.3
6. **完整性保证**：所有必填字段必须有有效值，不得留空或占位
7. **可复用性**：生成的 persona 文件可直接被其他 AudienceLens 技能加载使用
8. **版本管理**：每次生成的 persona 都带有版本号和时间戳

## Additional resources

- Persona Schema 见 [schemas/persona.schema.yaml](schemas/persona.schema.yaml)
- 面板预设 Schema 见 [schemas/panel-preset.schema.yaml](schemas/panel-preset.schema.yaml)
- Persona 模板见 [templates/persona-template.yaml](templates/persona-template.yaml)
- 面板预设模板见 [templates/panel-preset-template.yaml](templates/panel-preset-template.yaml)
- 游戏示例见 [examples/game-core-personas.yaml](examples/game-core-personas.yaml)
- SaaS 示例见 [examples/saas-personas.yaml](examples/saas-personas.yaml)
