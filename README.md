# AudienceLens

> 基于合成人格（Synthetic Persona）的多代理游戏评审系统。

使用 16 个行为驱动的 AI 人格对独立游戏的 Steam 商店页、Demo、概念稿、商业化方案、社区文案和版本公告进行多视角评审，输出结构化的 JSON 和 Markdown 报告。

**AudienceLens 不是玩家研究，不能替代真人测试。** 它是一个**预筛与压力测试工具**，用于在投入真人测试资源之前发现最明显的问题。

---

## 核心特性

### 16 个行为驱动的人格库

每个 persona 不再是"25岁男性玩家"这样的身份标签，而是通过 12 个行为轴刻画：

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

人格库涵盖：核心探索者、系统推演党、动作手感党、叙事沉浸党、视觉氛围党、轻度碎片玩家、新手上手观察者、治愈社交分享型、Steam 愿望单浏览者、TapTap 口碑型浏览者、创作者视角、发行侦察官、价格敏感买家、毒舌怀疑型、竞品对标老兵。

### 6 种任务类型

| 任务类型 | 中文名 | 适用场景 |
|---|---|---|
| `steam_page_review` | Steam页评审 | 商店页信息架构、视觉传达、信任信号 |
| `demo_first_play` | Demo首玩 | 上手摩擦、手感、首15分钟体验 |
| `concept_review` | 概念评审 | 核心循环、差异化、可行性 |
| `monetization_review` | 商业化评审 | 定价、付费边界、价值感知 |
| `looking_for_party_post` | 找搭子帖 | 社区文案、传播性、社交吸引力 |
| `update_announcement_review` | 更新公告 | 版本日志、信任强化、留存信号 |

### 严格的行为约束

- **证据三级标注**：`[direct]` 直接引用材料 / `[inferred]` 角色合理推断 / `[gap]` 信息缺口写"未指定"
- **禁止脑补**：不得替开发者脑补缺失功能、剧情、联机、商业化细节
- **身份-行为解耦**：persona 的判断必须基于 behavior_profile，不得将性别/年龄/地域作为偏好的直接因果解释
- **MBTI 去权**：MBTI 仅用于修饰表达风格，不得用于推导核心判断逻辑
- **Demographics 正交化**：每个敏感人口属性值（如"非二元"）至少出现在两个不同 archetype 的人格上

### 焦点争议点质询

传统"让分歧最大的两个 persona 互问"容易变成两个极端角色的无意义争吵。AudienceLens 改为：

1. 从所有 persona 输出中提取 top-3 争议点（按 severity 方差排序）
2. 对每个争议点，让持相反立场的 persona 各写一段论证
3. 所有 persona 对每段论证做说服力评分
4. confidence 变化超过 0.15 时允许更新立场

### 校准与监控

| 指标 | 说明 |
|---|---|
| `role_consistency_rate` | must_comment_on_check 覆盖率 ≥ 80% |
| `coverage_score` | persona 间 Jaccard 距离均值 ≥ 0.3（视角足够多样） |
| `hallucination_rate` | direct 证据中无法在输入材料中定位的比例 |
| `variance_ratio` | scores 面板方差充足 |

---

## 安装

### 前置依赖

- Python 3.11+
- Anthropic API Key（用于真实 API 调用，可选）

### 安装步骤

```bash
git clone https://github.com/your-repo/audiencelens.git
cd audiencelens
pip install -r requirements.txt
```

### 安装为 Claude Code Skill（可选）

```bash
# 项目级安装
Expand-Archive synthetic-playtest.skill.zip -DestinationPath .claude/skills/synthetic-playtest/

# 或个人级安装（所有项目可用）
Expand-Archive synthetic-playtest.skill.zip -DestinationPath ~/.claude/skills/synthetic-playtest/
```

---

## 快速开始

### 方式1：Claude Code Skill（推荐）

在 Claude Code 中直接调用：

```bash
# 评审 Steam 商店页
/synthetic-playtest steam_page_review examples/steam-page-sample/artifact.json

# 评审 Demo 体验
/synthetic-playtest demo_first_play examples/demo-sample/artifact.json

# 评审概念文档
/synthetic-playtest concept_review examples/concept-sample/artifact.json
```

Claude 会自动读取 SKILL.md 中的指令，选择合适的 persona 面板，逐一运行隔离评审，然后聚合输出 `audiencelens-report.json` 和 `audiencelens-report.md`。

### 方式2：Python CLI

```bash
# 模拟模式（无需 API Key）
python -m runner.cli steam_page_review examples/steam-page-sample/artifact.json

# 真实 API 模式
export ANTHROPIC_API_KEY=your-api-key
python -m runner.cli steam_page_review examples/steam-page-sample/artifact.json

# 指定输出目录
python -m runner.cli steam_page_review examples/steam-page-sample/artifact.json --output-dir ./reports
```

### 方式3：程序化调用

```python
from runner.cli import run_panel
import json

with open('examples/steam-page-sample/artifact.json') as f:
    artifact = json.load(f)

result = run_panel(
    task_type='steam_page_review',
    artifact_bundle=artifact
)

print(result['markdown'])       # Markdown 报告
print(result['report'])         # JSON 报告
print(result['calibration'])    # 校准结果
```

---

## 准备评审材料

评审材料是一个 JSON 或 YAML 文件，包含 `title`、`description` 和 `materials` 列表：

```json
{
  "title": "Echoes of the Void",
  "description": "一款融合 roguelite 与 metroidvania 的 2D 动作游戏",
  "materials": [
    {
      "type": "截图",
      "description": "胶囊图：暗色调像素风格，主角背影面对巨大虚空裂缝"
    },
    {
      "type": "实机视频",
      "description": "30秒实机预告片，展示时间回溯、战斗和探索核心循环"
    },
    {
      "type": "核心循环说明",
      "description": "探索→战斗→死亡→时间回溯→解锁新路径→获得永久能力"
    },
    {
      "type": "价格",
      "description": "抢先体验价 $14.99，正式版 $19.99"
    },
    {
      "type": "tags",
      "description": "roguelite, metroidvania, pixel art, time manipulation"
    }
  ]
}
```

**材料越丰富，评审越准确。** 如果材料缺失某类证据，persona 会输出"未指定"并在报告中标注。

---

## 理解报告

AudienceLens 输出两类文件：

### audiencelens-report.json

完整的结构化报告，包含：
- **executive_summary**：主要建议、发布风险、证据质量
- **consensus**：多数 persona 认可的点和质疑的点
- **major_disagreements**：主要分歧及解决方案建议
- **priority_fixes**：按优先级排序的修复项（severity × persona权重 × 影响人数）
- **persona_notes**：每个 persona 的立场、证据、继续/退出触发器
- **information_gaps**：材料中缺失的信息
- **next_human_test**：建议下一步真人测试的方向

### audiencelens-report.md

人类可读的 Markdown 报告，包含 Synthetic Banner、Executive Summary、共识/分歧/优先修复项、Persona 视角摘要、信息缺口和下一步建议。

---

## 项目结构

```
audiencelens/
├── SKILL.md                           # Claude Code Skill 主入口
├── synthetic-playtest.skill.zip       # 可分发的 Skill 包
├── src/
│   ├── personas/
│   │   └── game-core.yaml             # 16个persona定义
│   ├── presets/
│   │   └── panel-presets.yaml         # 6种任务默认面板
│   ├── schemas/
│   │   ├── persona-schema.json        # Persona YAML校验schema
│   │   ├── output-schema.json         # 单persona输出schema
│   │   └── report-schema.json         # 聚合报告schema
│   ├── templates/
│   │   ├── persona-prompt.md          # 五段式Prompt模板
│   │   ├── cross-exam-prompt.md       # 焦点争议点质询模板
│   │   └── report-template.md         # Markdown报告模板
│   ├── config/
│   │   ├── aggregation-rules.yaml     # 聚合规则
│   │   └── budget.yaml                # 成本配置
│   └── runner/
│       ├── panel_selector.py           # 面板选择
│       ├── evidence_precheck.py       # 证据完整性预检
│       ├── validator.py                # 三层校验
│       ├── persona_agent.py           # 单persona代理
│       ├── cross_exam.py              # 焦点争议点质询
│       ├── aggregator.py              # 规则驱动聚合
│       ├── calibration.py             # 校准harness
│       └── cli.py                     # CLI入口
├── tests/                             # 180个TDD测试
├── examples/                          # 示例素材
├── requirements.txt
└── pytest.ini
```

---

## 运行测试

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

当前：**180 个测试全部通过**

---

## 伦理使用声明

> **Synthetic panel. All responses were generated by AI personas, not human respondents.**
> This report must not be represented as "player research findings", "user survey results", or "real player opinion distribution".

AudienceLens 的输出：

- ❌ **不能**写成真实性玩家研究结论
- ❌ **不能**写成用户调查或真实玩家意见分布
- ❌ **不能**替代真人 playtest 或用户访谈
- ✅ **可以**作为预筛工具，发现最明显的问题
- ✅ **可以**作为压力测试工具，检验开发团队是否遗漏了关键视角
- ✅ **可以**作为快速迭代工具，在投入真人测试资源之前做多轮快速评审

详见 [伦理使用指南](./ETHICS.md)。

---

## Roadmap

### v0.1 — MVP（当前）

- [x] 16个persona YAML（含12行为轴）
- [x] 6种任务preset
- [x] 五段式Prompt模板
- [x] 焦点争议点质询
- [x] 规则驱动聚合器
- [x] 三层校验（schema + 角色一致性 + 证据接地）
- [x] 最简校准harness
- [x] Claude Code Skill

### v0.2

- [ ] 人类对照导入和校准流程
- [ ] 黄金输出回归测试
- [ ] 证据三级标注自动检测

### v1.0

- [ ] 无障碍专项persona pack（4-6个）
- [ ] Big-Five替代MBTI
- [ ] 动态面板生成算法
- [ ] 成本感知模型路由

### 企业版

- [ ] RBAC + 审计日志
- [ ] 团队空间和私有人物包
- [ ] 多模型网关
- [ ] Web UI + 仪表板

---

## 致谢

AudienceLens 借鉴了以下开源项目和学术研究：

- **CCGS** — Claude Code Skills 生态的多代理组织方式
- **SynthPanel** — YAML persona/instrument 和合成面板的工程实践
- **Mirror** — think-aloud 和综合报告机制
- **trashmy.tech** — 并行 persona 和确定性评分思路
- **SCOPE 研究** — demographics 仅解释 1.5% 行为方差
- **NN/g persona 方法论** — 行为优先于身份的设计原则

---

## 许可证

MIT License
