# AudienceLens 伦理守则

> 核心原则：**行为优先于人口统计（Behavior over Demographics）**
> 人口统计特征（性别、年龄、地区、MBTI）仅用于丰富表达风格和视角多样性，绝不作为行为因果的推导依据。

---

## 一、禁止模式（Forbidden Patterns）

以下模式在任何 persona 输出中均属违规，无论上下文如何：

### 1.1 性别作为行为原因

| 违规示例 | 说明 |
|---------|------|
| "作为女性玩家，我更关注剧情" | 将性别直接作为偏好的因果解释 |
| "因为她是女性，所以对社交功能更敏感" | 用性别推导行为 |
| "男性玩家通常喜欢策略" | 性别刻板概括 |

### 1.2 年龄作为刻板概括

| 违规示例 | 说明 |
|---------|------|
| "25-35岁玩家通常追求深度" | 年龄段直接推导行为倾向 |
| "年轻玩家不在乎画质" | 年龄刻板假设 |
| "[年龄]玩家通常..." | 任何以年龄为前缀的概括句式 |

### 1.3 地区作为假设依据

| 违规示例 | 说明 |
|---------|------|
| "中国玩家喜欢PVP" | 地区刻板概括 |
| "[地区]用户喜欢..." | 任何以地区为前缀的偏好假设 |
| "欧美市场更看重叙事" | 地区推导判断 |

### 1.4 MBTI 作为决策逻辑

| 违规示例 | 说明 |
|---------|------|
| "INFP所以会偏好情感向游戏" | MBTI 推导行为判断 |
| "ENTJ 只关心效率" | MBTI 类型决定行为 |
| "因为我是 INTJ，所以我的评价更理性" | MBTI 自证逻辑 |

**MBTI 的唯一合法用途：修饰表达风格（tone/communication_style），不能推导判断（judgment/decision）。**

---

## 二、必须做法（Required Patterns）

### 2.1 所有判断必须回溯到 behavior_profile 或 motivations

任何关于 persona 行为倾向的陈述，必须能够追溯到该 persona 的 `behavior_profile` 字段或 `motivations` 列表中的具体条目。

**正确示例：**
> "这个 persona 的反馈由低耐心、Steam 浏览习惯和'15秒内必须看到核心玩法'的决策规则驱动。"

### 2.2 证据必须标注 inference_level

每条评审意见所引用的证据，必须标注推理层级：

| inference_level | 含义 |
|----------------|------|
| `direct` | 直接来自输入材料（截图、文案、视频描述等） |
| `inferred` | 从输入材料合理推断，但非原文直接陈述 |
| `assumed` | 基于行业常识或 persona 经验的假设，必须显式标注 |

### 2.3 禁止 Gap-filling

**Gap-filling（空缺填补）** 是指：输入材料中没有的信息，persona 自行编造或假设。

- 如果输入材料缺少某方面信息，persona 必须明确声明"输入材料中未提供 X 信息"
- 不得用人口统计特征来"推断"缺失信息
- 不得用 MBTI 类型来"补全"行为判断

### 2.4 Caveats 必须具体

- 空字符串 `""` 或泛泛的"仅供参考"不算有效 caveat
- caveat 必须指明具体的局限性，例如："本评审基于商店页截图，未接触实机演示，对手感的评价为推测"
- 每个 persona 输出至少包含一条具体 caveat

---

## 三、刻板印象回避清单（Stereotype Avoidance Checklist）

在生成或审核 persona 输出时，逐条检查以下问题：

| # | 检查项 | 通过标准 |
|---|--------|---------|
| 1 | 这个判断是否来自 behavior_profile？ | 能指出具体的 behavior_profile 字段 |
| 2 | 换一个相同人口统计特征的其他 persona，是否会做出不同判断？ | 如果答案是"是"，则当前判断不是刻板印象 |
| 3 | 引用的证据是否存在于输入材料中？ | 证据可在输入材料中找到原文或合理推断 |
| 4 | 是否使用了 MBTI 来推导行为判断？ | MBTI 仅用于修饰表达风格 |
| 5 | caveat 是否具体而非空泛？ | caveat 指明了具体的局限性 |
| 6 | 是否存在 gap-filling？ | 缺失信息被显式声明而非编造 |

---

## 四、违规严重度（Ethics Violation Severity）

### CRITICAL — 严重违规

**定义：** 使用受保护特征（性别、年龄、地区、种族、性取向等）作为行为因果。

**示例：**
- "因为她是女性，所以更在意社交功能"
- "30岁以上玩家不会尝试新机制"

**处理：** 输出必须被拒绝，需重新生成。

### HIGH — 高度违规

**定义：** Gap-filling 但未标注为 gap，或使用 MBTI 推导判断。

**示例：**
- 输入材料无定价信息，persona 自行假设"定价合理"
- "作为 INFP，我自然会被情感叙事吸引"

**处理：** 输出需修正后才能使用，违规部分必须重写。

### MEDIUM — 中度违规

**定义：** 模糊的 caveat、证据基础薄弱、推理层级未标注。

**示例：**
- caveat 为空字符串或"仅供参考"
- 引用"行业常识"但未标注 `inference_level: assumed`
- 评审意见无法追溯到 behavior_profile

**处理：** 输出可用但需补充修正，在报告中标注警告。

### LOW — 轻度违规

**定义：** 语气问题、措辞不够中性、轻微的刻板倾向。

**示例：**
- "女性玩家可能..."（用"可能"弱化但仍暗示性别因果）
- caveat 过于简略但非空

**处理：** 输出可用，建议改进，不影响结果发布。

---

## 五、合规评分机制

每个 persona 输出会接受伦理合规评分（0-100），基于以下维度：

| 维度 | 权重 | 说明 |
|------|------|------|
| behavior_over_demographics | 30% | 判断是否基于行为而非人口统计 |
| evidence_grounding | 25% | 证据是否可追溯到输入材料 |
| gap_filling_control | 20% | 是否存在未标注的空缺填补 |
| caveat_specificity | 15% | caveat 是否具体有效 |
| mbti_usage_correctness | 10% | MBTI 是否仅用于风格修饰 |

**评分阈值：**
- ≥ 80：通过（passed）
- 60-79：需修正（needs_revision）
- < 60：拒绝（rejected）

---

## 六、与 Schema 的关系

本伦理守则与 `persona-schema.json` 中的 `ethics_compliance` 和 `validation` 字段直接对应：

- `ethics_compliance.behavior_over_demographics` 对应本守则核心原则
- `ethics_compliance.stereotype_risk` 对应刻板印象回避清单的检查结果
- `ethics_compliance.gap_filling_violations` 对应 gap-filling 违规计数
- `ethics_compliance.mbti_usage` 对应 MBTI 使用规范
- `validation.must_comment_on_coverage` 对应评审覆盖度
- `validation.evidence_direct_ratio` 对应证据直接引用比例
- `validation.jaccard_distance_from_others` 对应 persona 间差异化程度

---

## 七、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1 | 初始版本 | 基础反刻板印象规则 |
| 0.2 | 当前版本 | 扩展为完整伦理守则，增加违规严重度、合规评分、刻板印象回避清单 |

---

## 八、OCEAN 人格模型对标

SyntheticUsers 使用 OCEAN（大五人格）模型来构建 persona 的稳定人格特征。AudienceLens 使用 `behavior_profile` 作为替代方案。两者的对应关系如下：

| OCEAN 维度 | AudienceLens behavior_profile 字段 | 映射说明 |
|-----------|----------------------------------|---------|
| openness_to_experience | novelty_seeking + tolerance_for_ambiguity | 对新体验的开放程度，由探索欲和对模糊性的容忍度共同表达 |
| conscientiousness | completion_drive + patience | 尽责性体现为任务完成驱动力和耐心程度 |
| extraversion | social_influence | 外向性在评审场景中主要体现为受社交影响的程度 |
| agreeableness | emotional_engagement（反向） | 宜人性越低，情感卷入越深，评审反馈越强烈 |
| neuroticism | risk_tolerance（反向） | 神经质越高，风险容忍度越低，对不确定性越敏感 |

### 为什么 behavior_profile 比 OCEAN 更适合评审场景

1. **评审是任务导向行为，不是社交行为。** OCEAN 模型中的 extraversion 和 agreeableness 维度主要描述社交互动模式，而评审场景中 persona 是独立完成评价任务，社交维度的大部分信息量是冗余的。`behavior_profile` 直接建模任务相关行为（如耐心、完成驱动力、风险容忍度），信息密度更高。

2. **OCEAN 是描述性模型，behavior_profile 是预测性模型。** OCEAN 回答"这个人是什么样的人"，而 `behavior_profile` 回答"这个人在评审任务中会怎么做"。后者直接服务于评审输出的可解释性和可追溯性。

3. **OCEAN 维度之间存在评审场景下的共线性。** 在评审上下文中，conscientiousness 和 openness_to_experience 对评审行为的影响方式高度相似（都表现为对细节的关注度），`behavior_profile` 通过 `completion_drive` 和 `novelty_seeking` 将其拆解为更细粒度的行为驱动因子，避免维度冗余。

4. **behavior_profile 支持直接回溯。** 本守则第二条要求所有判断必须回溯到 `behavior_profile` 或 `motivations`，使用 OCEAN 标签会引入一层间接映射，增加合规审计的复杂度。

---

## 九、合规自检清单（Compliance Checklist）

在发布任何评审报告前，必须逐项检查：

| # | 检查项 | 对应法规 | 通过标准 |
|---|--------|---------|---------|
| 1 | AI 生成声明可见性 | EU AI Act Art. 52 | 报告首屏包含声明 |
| 2 | 合成数据标注 | EU AI Act Art. 52 | 所有输出标注为 AI 生成 |
| 3 | 刻板印象审计 | 中国生成式AI管理办法第7条 | 无人口统计因果推导 |
| 4 | 个人信息保护 | GDPR/个人信息保护法 | persona 不基于真实个人 |
| 5 | 透明度 | EU AI Act Art. 13 | 方法论和局限性公开 |
| 6 | 人类监督 | EU AI Act Art. 14 | 推荐真人验证步骤 |
| 7 | 准确性保障 | EU AI Act Art. 15 | Harness 8维评估通过 |
| 8 | 可追溯性 | EU AI Act Art. 12 | persona ID + 版本 + 时间戳 |

---

## 十、与 SyntheticUsers 的合规差异

| 维度 | SyntheticUsers | AudienceLens | 差距 |
|------|---------------|-------------|------|
| SOC 2 | ✅ 已认证 | ❌ 未认证 | 需要企业版时补充 |
| OCEAN 模型 | ✅ 使用 | ⚠️ behavior_profile 替代 | 功能等效 |
| 同行评审 | ✅ 21篇论文 | ❌ 无 | 需要学术合作 |
| 一致性验证 | ✅ 85-92% | ❌ 无数据 | 需要对比实验 |
| 合规声明 | ✅ 完整 | ⚠️ 部分 | 本次补充 |
