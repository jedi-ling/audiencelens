# 评估器：结构完整性（Structure Check）

验证报告是否包含任务类型所需的全部章节。以 `expected/synthetic-playtest-required-sections.yaml` 为唯一事实来源。

## 评分标准（1-5分）

### 5分 — 完整且规范
报告包含该任务类型的所有必需章节，且每个章节内容充实（非占位符）。

### 4分 — 完整但部分简略
所有必需章节都存在，但1-2个章节内容过于简略（少于3句话或明显敷衍）。

### 3分 — 基本完整
缺少1个非关键章节，或2-3个章节内容简略。达到最低通过线。

### 2分 — 明显缺失
缺少2个及以上章节，或关键章节（Disclaimer / Executive Verdict / Priority Actions）内容为空。

### 1分 — 严重不完整
缺少3个及以上章节，或缺少 Disclaimer。

## 评估方法

### 步骤1：确定任务类型

从报告元数据中读取 `task_type`，映射到 `synthetic-playtest-required-sections.yaml` 中的对应配置。

### 步骤2：逐章节检查

对每个必需章节：

1. **存在性检查**：章节标题是否出现在报告中？
2. **内容检查**：章节内容是否超过占位符级别？（至少3句实质内容）
3. **嵌套检查**：如果章节有子节要求，子节是否都存在？

### 步骤3：计算完整率

```
完整率 = 存在且内容充实的章节数 / 必需章节总数
```

### 综合评分

| 完整率 | 分数 |
|--------|------|
| 100% | 5分 |
| 90-99% | 4分 |
| 75-89% | 3分 |
| 50-74% | 2分 |
| < 50% | 1分 |

## 通用必需章节（所有任务类型）

以下章节在所有任务类型中都是必需的：

1. **Disclaimer** — AI生成声明，不得缺失或弱化
2. **Executive Verdict** — 综合判定
3. **Assumption Summary** — 材料假设摘要
4. **Persona Panel** — 人格面板说明
5. **Persona Reviews** — 逐人格评审
6. **Consensus Findings** — 共识发现
7. **Segment Disagreements** — 分段分歧
8. **Top Blockers** — 主要阻碍
9. **Top Opportunities** — 主要机会
10. **Priority Actions** — 优先行动项（必须含P0/P1/P2）
11. **Real Validation Questions** — 真人验证问题
12. **Harness Self-Check** — 自检章节

## 任务类型特定章节

详见 `expected/synthetic-playtest-required-sections.yaml` 中每个任务类型的 `task_specific_sections` 定义。

## 关键失败条件

- 缺少 Disclaimer → 自动失败
- Priority Actions 中无 P0/P1/P2 标注 → 自动失败
- 缺少 Executive Verdict → 自动失败
- 缺少 Persona Reviews → 自动失败
