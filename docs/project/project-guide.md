# AudienceLens 项目指示性文档

> 版本：v0.2.1 | 更新日期：2026-05-30

---

## 一、项目概述

**AudienceLens** 是一个开源的多代理交叉质询合成评审系统，通过 AI Persona 模拟真实用户评审产品/游戏，支持三轮辩论、改票机制、共识演化追踪。

### 核心数据

| 指标 | 数值 |
|------|------|
| Persona 总数 | 75（50 游戏 + 20 产品 + 5 红队） |
| 技能数量 | 4（synthetic-playtest / audience-panel / red-team-audience / persona-generate） |
| 评估维度 | 8（Harness 框架） |
| 评审模式 | 3（quick 3人 / standard 4-6人 / full 6-8人） |
| 任务类型 | 20（14 游戏 + 6 产品） |

---

## 二、项目目录结构

```
AudienceLens-Skills/          ← GitHub 开源版（CCGS 标准）
├── CLAUDE.md                 ← 主配置文件
├── README.md                 ← 项目说明（含竞品对比）
├── .claude/                  ← Claude Code 配置
│   ├── settings.json         ← Hook 注册 + 权限
│   ├── skills/               ← 4 个技能完整目录
│   │   ├── synthetic-playtest/  ← 游戏评审（50 persona）
│   │   ├── audience-panel/      ← 产品评审（20 persona）
│   │   ├── red-team-audience/   ← 红队对抗（5 persona）
│   │   └── persona-generate/    ← 生成器
│   ├── agents/               ← 50 个 Agent 定义
│   ├── hooks/                ← 10 个 Hook 脚本
│   ├── rules/                ← 4 个路径规则
│   └── docs/                 ← 5 个内部文档
├── .trae/skills/             ← Trae 技能目录（与 .claude 同步）
├── tools/
│   └── parity_check.py       ← 一致性验证工具
├── docs/
│   ├── methodology.md        ← 方法论
│   ├── roadmap.md            ← 路线图
│   ├── changelog.md          ← 变更日志
│   ├── competitive-landscape.md  ← 竞品对比
│   ├── benchmark-report.md   ← 基准测试报告
│   ├── arxiv-paper.md        ← arXiv 论文初稿
│   └── landing-page/         ← 产品落地页
├── demo/
│   ├── demo-report.html      ← Demo 评价书
│   └── demo-summary.md       ← Demo 摘要
├── production/               ← 生产环境
└── examples/                 ← 使用示例

AudienceLens-Server/          ← 服务器部署版
├── .trae/skills/             ← 技能文件
├── src/                      ← Python 后端
├── web/                      ← FastAPI + React
├── docker-compose.yml
└── deploy.sh

多人评审系统/                  ← 原始开发目录
├── .trae/skills/             ← 技能文件
├── src/                      ← Python 后端
├── web/                      ← FastAPI + React
└── tests/                    ← 测试文件
```

---

## 三、竞品定位

| 维度 | AudienceLens | SyntheticUsers | Outset | Yabble |
|------|-------------|---------------|--------|--------|
| **模式** | 评审式 | 访谈式 | 真人访谈 | 对话式 |
| **交互** | 三轮质询+改票 | 一问一答 | AI 主持 | 单轮对话 |
| **定价** | 开源免费 | $2-60/次 | 企业级 | $800/月 |
| **开源** | ✅ | ❌ | ❌ | ❌ |
| **游戏评审** | ✅ | ❌ | ❌ | ❌ |
| **红队对抗** | ✅ | ❌ | ❌ | ❌ |
| **学术验证** | 待做 | 85-92% | N/A | N/A |

**核心差异化**：市场上唯一开源的、支持交叉质询+投票改票的合成评审工具。

---

## 四、已完成工作

### 第一轮优化（技术基础）

- [x] 修复 indie-creative.yaml YAML 语法错误
- [x] 优化 4 个 SKILL.md frontmatter（≤200字符英文）
- [x] 增强交叉质询模板（32行→231行，三轮辩论+改票+置信度）
- [x] 补强伦理框架（OCEAN 对标 + EU AI Act + 合规差异）
- [x] 优化 HTML 评价书（验证指标+交叉质询记录+合规横幅）
- [x] 添加一致性验证脚本（parity_check.py）
- [x] 创建 audience-panel 完整文件（20 persona + 全套支撑）
- [x] 创建 red-team 完整文件（5 persona + 全套支撑）
- [x] 优化 Harness 评估器（量化阈值+自动评分）
- [x] 优化 README（竞品对比+交叉质询演示+验证保障）
- [x] 三端同步（Skills / Server / 原始项目）

### 第二轮优化（质量保障）

- [x] YAML/JSON 语法验证（38文件全部通过）
- [x] 同步 .trae/skills/ 目录（73文件）
- [x] 创建 persona-generate 缺失文件（5个）
- [x] 清理冗余文件（20个临时文件）
- [x] 修复 Python 代码（aggregator + cross_exam + cli）
- [x] 更新文档（CLAUDE.md / methodology / roadmap / changelog）
- [x] 新增 competitive-landscape.md

### 第三轮（产品化）

- [x] Demo 评审报告（HTML + Markdown）
- [x] arXiv 论文初稿（~5000字，19篇引用）
- [x] 竞品基准测试报告（8维度对比）
- [x] Landing Page（赛博朋克 HUD 风格）

---

## 五、待完成工作（按优先级）

### 🔴 P0 — 必须做（1-2周内）

| # | 任务 | 说明 | 预期产出 |
|---|------|------|---------|
| 1 | **真实用户对比验证** | 找 5-10 个真人评审同一产品，用 parity_check.py 计算一致性 | 一致性数据（目标 ≥80%） |
| 2 | **第一个公开案例** | 找一个独立游戏开发者或产品团队做免费评审 | 案例文章 + 评价书截图 |
| 3 | **arXiv 投稿** | 完善论文（加入真实验证数据），提交 arXiv | 学术背书 |

### 🟡 P1 — 应该做（2-4周内）

| # | 任务 | 说明 | 预期产出 |
|---|------|------|---------|
| 4 | **社区推广** | 发到 r/gamedev / itch.io / 独立游戏 Discord | 第一批用户 |
| 5 | **Landing Page 上线** | 部署到 Vercel/Netlify | 产品入口 |
| 6 | **GitHub 开源发布** | 清理仓库，写好 README，发布 v0.3 | 开源社区曝光 |
| 7 | **CI/CD 流水线** | GitHub Actions 自动测试 + YAML/JSON 校验 | 代码质量保障 |

### 🟢 P2 — 可以做（1-3月内）

| # | 任务 | 说明 | 预期产出 |
|---|------|------|---------|
| 8 | **Server 版部署上线** | Docker 部署 + 域名 + HTTPS | 付费版基础 |
| 9 | **付费层设计** | Free / Pro / Team / Enterprise 定价 | 变现路径 |
| 10 | **视频/语音模态** | 参考 Outset 的多模态评审 | 功能对齐竞品 |
| 11 | **SOC 2 认证准备** | 企业客户必需 | 企业市场准入 |
| 12 | **社区 Persona 贡献机制** | 让社区贡献新 Persona | 飞轮效应 |

---

## 六、关键文件索引

| 用途 | 文件路径 |
|------|---------|
| **Demo 评价书** | `AudienceLens-Skills/demo/demo-report.html` |
| **Demo 摘要** | `AudienceLens-Skills/demo/demo-summary.md` |
| **Landing Page** | `AudienceLens-Skills/docs/landing-page/index.html` |
| **arXiv 论文** | `AudienceLens-Skills/docs/arxiv-paper.md` |
| **基准测试** | `AudienceLens-Skills/docs/benchmark-report.md` |
| **竞品对比** | `AudienceLens-Skills/docs/competitive-landscape.md` |
| **一致性验证** | `AudienceLens-Skills/tools/parity_check.py` |
| **伦理守则** | `AudienceLens-Skills/.claude/skills/synthetic-playtest/ethics.md` |
| **交叉质询模板** | `AudienceLens-Skills/.claude/skills/synthetic-playtest/templates/cross-exam-prompt.md` |
| **路线图** | `AudienceLens-Skills/docs/roadmap.md` |

---

## 七、技术栈

| 层 | 技术 |
|----|------|
| Skill 框架 | Claude Code Skill / Trae Skill |
| 仓库标准 | CCGS（CLAUDE.md + settings.json + agents/ + hooks/ + rules/） |
| 后端 | Python 3.11+ / FastAPI |
| 前端 | React 18 + TypeScript + Tailwind CSS |
| 部署 | Docker + docker-compose |
| 验证 | parity_check.py（纯 Python 标准库） |
| 评估 | Harness 8 维度框架 |

---

## 八、核心差异化话术

1. **"三轮辩论，不是一问一答"** — 交叉质询让 Persona 之间互相反驳、可能改票，比访谈式研究更有深度
2. **"75 个 AI 玩家，零成本"** — 对比 SyntheticUsers $60/次，AudienceLens 完全免费
3. **"唯一开源"** — 所有竞品都是闭源 SaaS，AudienceLens 是唯一可自部署的
4. **"游戏评审蓝海"** — 没有任何竞品做游戏概念评审
5. **"伦理内置"** — 行为优先于人口统计、刻板印象检测、EU AI Act 合规自检
