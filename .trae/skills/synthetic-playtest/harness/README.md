# AudienceLens Harness 质量评估框架

Harness 是 AudienceLens 技能输出的质量门控层。它提供测试夹具、评分量规、评估器和预期报告结构，供人类或 AI 代理检验技能输出是否达标。

## 评估维度（8维）

| # | 维度 | 评估器 | 核心问题 |
|---|------|--------|---------|
| 1 | 行动可操作性 | [actionability](evaluators/actionability.md) | 建议是否具体可执行，还是空泛无物？ |
| 2 | 输入接地性 | [input-grounding](evaluators/input-grounding.md) | 反馈是否引用了输入材料的具体细节？ |
| 3 | 人格差异化 | [persona-differentiation](evaluators/persona-differentiation.md) | 不同人格是否产出了真正不同的视角？ |
| 4 | 刻板印象检查 | [stereotype-check](evaluators/stereotype-check.md) | 人格判断是否基于行为画像而非人口统计属性？ |
| 5 | 结构完整性 | [structure-check](evaluators/structure-check.md) | 报告是否包含任务类型所需的全部章节？ |
| 6 | 校准诚实度 | [calibration-honesty](evaluators/calibration-honesty.md) | 发现是否被正确标注为假设而非事实？ |
| 7 | 风险检测力 | [risk-detection](evaluators/risk-detection.md) | 评审是否识别了关键风险而非仅关注次要问题？ |
| 8 | 分段冲突度 | [segment-conflict](evaluators/segment-conflict.md) | 人格分段之间是否存在有意义的分歧？ |

## 目录结构

```
harness/
├── README.md                          # 本文件
├── run-evaluation.md                  # 评估流水线执行指南
├── evaluators/                        # 8个评估器模板
│   ├── actionability.md
│   ├── input-grounding.md
│   ├── persona-differentiation.md
│   ├── stereotype-check.md
│   ├── structure-check.md
│   ├── calibration-honesty.md
│   ├── risk-detection.md
│   └── segment-conflict.md
├── rubrics/                           # 评分量规
│   └── audience-review-rubric.md      # 8维综合量规（1-5分制）
├── expected/                          # 预期结构定义
│   └── synthetic-playtest-required-sections.yaml
└── fixtures/                          # 测试夹具
    ├── game-concept-cyber-scavenger.md  # 优质游戏概念
    ├── weak-game-concept.md             # 劣质游戏概念
    ├── landing-page-good.md             # 优质落地页
    └── landing-page-bad.md              # 劣质落地页
```

## 工作流

```text
在夹具上运行技能
  → 生成报告
  → 用量规逐维评估
  → 识别弱维度
  → 修订技能/人格/模板
  → 重新运行
```

## 快速开始

1. 选择一个夹具（如 `fixtures/game-concept-cyber-scavenger.md`）
2. 按 [run-evaluation.md](run-evaluation.md) 执行评估流水线
3. 查看评分卡，定位弱维度
4. 修订后重新运行，直到所有维度通过

## 评分体系

- 每个维度 1-5 分（5 = 优秀，1 = 严重不足）
- 通过阈值：所有维度 ≥ 3 分
- 关键失败条件：见 [rubrics/audience-review-rubric.md](rubrics/audience-review-rubric.md) 的"关键失败"章节
