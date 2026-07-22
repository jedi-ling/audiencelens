# AGENTS.md

AudienceLens — 全栈合成观众评审系统（CLI + FastAPI + React 19）。
多代理行为驱动人格模拟 + 结构化交叉质询，用于在投入真人测试前发现最明显的问题。

## 权威源码

- **`src/runner/`** — 评审流水线引擎：面板选择 → 证据预检 → 人格并发 → 三层校验 → 交叉质询 → 聚合 → 校准
- **`src/harness/`** — 质量评估引擎：8 维评分、刻板印象检测、消融实验

> **注意区分三个 "harness" 目录**：`src/harness/`（本项目内置引擎）、
> `audiencelens-v0.2-harness/`（`web/backend` 运行时依赖的评委规则集）、
> `audiencelens-harness/`（独立的开源 Skill 分发仓库）。
> 三者关系详见 [`docs/ARCHITECTURE.md` §1](docs/ARCHITECTURE.md#1-分层总览)。

## 变更校验

```bash
# 核心引擎测试（272 项）
python -m pytest tests/ -q

# 平台链路测试（221 项）
(cd web/backend && python -m pytest tests/ -q)

# 前端构建（TypeScript 编译 + Vite 打包）
(cd web/frontend && npm run build)

# 后台面板单测（10 项，Vitest）
(cd web/admin && npm run test)
```

## 伦理

本项目受 [`ETHICS.md`](ETHICS.md) 约束——合成人格评审**不是**真实用户研究。
输出禁止以 "玩家认为…" 等真实用户口吻呈现，必须标注为合成评审。

## 模拟模式警告

以下警告来自 `src/runner/cli.py`，**任何代码变更不得弱化或绕过**：

> ⚠️ 模拟模式（未检测到 ANTHROPIC_API_KEY）：所有人格输出均为预制占位数据，
> 不包含任何真实评审意见，仅用于验证流水线是否可运行。
> 请勿将本次结果用于任何决策。设置 ANTHROPIC_API_KEY 后重新运行以获得真实评审。

无 API Key 时 CLI 退回模拟模式；Web 端无 Key 时返回 428 `llm_key_missing` 而非模拟数据
（见 [`docs/ARCHITECTURE.md` §4.1](docs/ARCHITECTURE.md#41-无-key-时拒绝而不是返回模拟数据)）。
