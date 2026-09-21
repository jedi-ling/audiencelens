# Harness 评估流水线执行指南

本指南说明如何运行完整的 AudienceLens 评估流水线，对技能输出进行8维度质量评估。

## 前置条件

- AudienceLens synthetic-playtest 技能已配置
- Harness 文件完整（evaluators/ + rubrics/ + expected/ + fixtures/）
- 评估者可以是人类或 AI 代理

## 流水线步骤

### 步骤1：选择夹具并运行技能

选择一个测试夹具，运行 synthetic-playtest 技能生成评审报告。

**夹具选择：**

| 夹具 | 任务类型 | 用途 |
|------|---------|------|
| `fixtures/game-concept-cyber-scavenger.md` | `concept_review` | 测试优质游戏概念的评审质量 |
| `fixtures/weak-game-concept.md` | `concept_review` | 测试劣质概念的识别能力 |
| `fixtures/landing-page-good.md` | `landing_page_review` | 测试非游戏产品的评审质量 |
| `fixtures/landing-page-bad.md` | `landing_page_review` | 测试劣质落地页的识别能力 |

**执行命令示例：**

```
synthetic-playtest concept_review fixtures/game-concept-cyber-scavenger.md --depth standard
```

**预期输出：**
- `audiencelens-report.json` — 完整JSON报告
- `audiencelens-report.md` — Markdown报告
- `audiencelens-report.html` — HTML评价书

### 步骤2：收集输出

读取生成的 JSON 报告，提取以下关键数据：

1. **任务类型**：`task_type`
2. **人格输出列表**：`persona_notes[]`
3. **共识发现**：`consensus_findings`
4. **分段分歧**：`segment_disagreements`
5. **优先行动项**：`priority_actions`
6. **自检结果**：`harness_self_check`

### 步骤3：逐维度评估

对8个维度逐一运行评估器。每个评估器读取报告对应部分，按评分标准打分。

#### 3.1 行动可操作性

**评估器**：[evaluators/actionability.md](evaluators/actionability.md)

**输入**：`priority_actions` + 每个 persona 的 `key_issues[].suggested_fix`

**检查要点**：
- 建议是否包含明确对象+动作+预期效果？
- 是否有P0/P1/P2优先级标注？
- 可操作建议占比是否 ≥ 40%？

#### 3.2 输入接地性

**评估器**：[evaluators/input-grounding.md](evaluators/input-grounding.md)

**输入**：每个 persona 的 `evidence[]` + 原始输入材料

**检查要点**：
- evidence 是否引用了输入材料的具体内容？
- `inference_level=direct` 的条目是否能在输入中定位？
- 幻觉率是否 < 20%？

#### 3.3 人格差异化

**评估器**：[evaluators/persona-differentiation.md](evaluators/persona-differentiation.md)

**输入**：所有 persona 的 `key_issues[]` + `scores` + `primary_stance`

**检查要点**：
- 不同 persona 的 key_issues 标题集合 Jaccard 距离均值是否 ≥ 0.3？
- 不同 persona 的关注点是否有本质差异？
- scores 标准差是否 ≥ 0.5？

#### 3.4 刻板印象检查

**评估器**：[evaluators/stereotype-check.md](evaluators/stereotype-check.md)

**输入**：每个 persona 的 `evidence[]` + `key_issues[]` + `voice_sample`

**检查要点**：
- 是否出现"因为[性别/年龄/地域/MBTI]...所以/因此"模式？
- 判断逻辑是否基于 behavior_profile？
- 可运行 `check_identity_behavior_decoupling()` 辅助检测

#### 3.5 结构完整性

**评估器**：[evaluators/structure-check.md](evaluators/structure-check.md)

**输入**：报告全文 + `expected/synthetic-playtest-required-sections.yaml`

**检查要点**：
- 报告是否包含该任务类型的所有必需章节？
- Disclaimer 是否存在且未被弱化？
- Priority Actions 是否有P0/P1/P2标注？

#### 3.6 校准诚实度

**评估器**：[evaluators/calibration-honesty.md](evaluators/calibration-honesty.md)

**输入**：报告全文

**检查要点**：
- 是否存在过度自信语言（"一定会"/"注定"/"绝对"）？
- 发现是否被标注为假设而非事实？
- 是否包含AI生成免责声明？
- 是否推荐了真人验证？

#### 3.7 风险检测力

**评估器**：[evaluators/risk-detection.md](evaluators/risk-detection.md)

**输入**：`key_issues[]` + `top_blockers` + `segment_disagreements`

**检查要点**：
- 是否识别了致命级（showstopper）风险？
- key_issues 中 high/critical 占比是否 ≥ 20%？
- Top Blockers 章节是否存在且内容充实？

#### 3.8 分段冲突度

**评估器**：[evaluators/segment-conflict.md](evaluators/segment-conflict.md)

**输入**：`segment_disagreements` + persona 的 `primary_stance` + `scores`

**检查要点**：
- 不同 persona 的 primary_stance 是否有分歧？
- Segment Disagreements 章节是否识别了有意义的冲突？
- 冲突是否对产品决策有指导意义？

### 步骤4：生成评分卡

将8个维度的评分汇总为评分卡：

```
┌──────────────────────┬───────┬────────┬──────────────────┐
│ 维度                 │ 得分  │ 通过？ │ 备注             │
├──────────────────────┼───────┼────────┼──────────────────┤
│ 行动可操作性         │  /5   │  ≥3?   │                  │
│ 输入接地性           │  /5   │  ≥3?   │                  │
│ 人格差异化           │  /5   │  ≥3?   │                  │
│ 刻板印象检查         │  /5   │  ≥3?   │                  │
│ 结构完整性           │  /5   │  ≥3?   │                  │
│ 校准诚实度           │  /5   │  ≥3?   │                  │
│ 风险检测力           │  /5   │  ≥3?   │                  │
│ 分段冲突度           │  /5   │  ≥3?   │                  │
├──────────────────────┼───────┼────────┼──────────────────┤
│ 总分                 │ /40   │        │                  │
│ 关键失败触发？       │       │        │ 是/否            │
│ 最终判定             │       │        │ PASS / FAIL      │
└──────────────────────┴───────┴────────┴──────────────────┘
```

### 步骤5：判定 PASS / FAIL

**PASS 条件**：
- 所有8个维度 ≥ 3分
- 无关键失败条件触发

**FAIL 条件**（任一触发）：
- 任何维度 < 3分
- 缺少 AI 生成免责声明
- Priority Actions 无 P0/P1/P2 标注
- 使用人口统计属性作为判断因果
- 声称预测真实世界成功/失败
- 报告未接地于输入材料
- 所有 persona 无实质分歧
- 未识别任何关键风险

## FAIL 后的处理

1. 定位弱维度，阅读对应评估器的详细标准
2. 识别具体问题（如"建议过于模糊"/"存在刻板印象"/"缺少Top Blockers"）
3. 修订技能配置（人格定义/提示模板/聚合规则）
4. 使用相同夹具重新运行
5. 重新评估，直到 PASS

## 多夹具交叉验证

建议至少使用2个不同夹具进行评估，确保技能在不同输入质量下都能达标：

| 组合 | 覆盖场景 |
|------|---------|
| cyber-scavenger + weak-game-concept | 游戏概念：优质 vs 劣质 |
| landing-page-good + landing-page-bad | 落地页：优质 vs 劣质 |
| cyber-scavenger + landing-page-good | 跨领域：游戏 vs 非游戏 |

**关键观察**：
- 劣质夹具应触发更多高风险/致命级发现
- 优质夹具不应被过度批评（风险检测力 ≠ 吹毛求疵）
- 不同领域夹具应产生不同的 persona 面板和关注点
