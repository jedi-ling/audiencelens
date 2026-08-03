# 变更日志

所有重要变更都会记录在此文件中。

## [0.3.0] — CLI + MCP + Hosted Platform

> 自 0.2.1 以来的全部变更。版本号取自 pyproject.toml / src/cli.py（0.3.0）。

### 新增

**引擎 / CLI**

- **统一 CLI 入口**（commit 9a90599 / 113fa6e）：click 命令组 `audiencelens`，含 `run`（synthetic-playtest / audience-panel / red-team-audience 技能）、`personas-validate`、`harness-evaluate`、`parity-check`、`ablation`、`stereotype-eval`、`benchmark-*`；`pyproject.toml` 注册 console_scripts（audiencelens + audiencelens-mcp）
- **MCP server**（commit 882f8f8）：`audiencelens-mcp`，4 个工具（list_task_types / list_persona_packs / list_personas / run_synthetic_review），任意支持 MCP 的客户端可接入
- **引擎升级**：run_panel 人格评审线程池并发化（commit 7bf1a95）、语义去重覆盖面扩展与阈值校准 0.75→0.65（commit 3b22c0b / 8a9236d）、行为距离/多样性动态面板选择（commit 9a90599）
- **多服务商 LLM 客户端 + 多模态**（commit 71d42f8）：anthropic + OpenAI 兼容服务商、图片材料直传模型，新增 general-consumer / startup-panel / launch-compliance / accessibility 等人格包
- **交叉质询接上真实 LLM**（commit f136043 / 135d2ba）：改票在代码里算、θ 从配置读、评审深度分档 quick/standard/full
- **人类对照基准工具链**（commit 9a90599 / 10a18ec）：tools/benchmark_compare.py / benchmark_suite.py / benchmark_scaffold.py（合成 vs 真人研究参考的三方盲测）

**平台（web/backend）**

- **全链路前后端框架**（commit fc7785d）+ 渐进式认证、报告分级、CDK 兑换、多服务商 Key、管理后台扩展（commit 9ced26e）
- **配额与计费**（commit fc7785d / a838286 / 135d2ba）：quota_service 用量记账与 24h 成本闸、plan_service 套餐、ledger_service 账本、cdk_service 兑换码
- **对话评审链路**（commit bc8c553 / e14dc4e / f963636）：登录系统 + 历史侧栏、插入技能/呼叫角色/创建长期评审项目、拖拽粘贴上传
- **账号与数据自主权**（commit 3d93619 / 7d675db / d654902）：邮箱验证 + 忘记密码、一键导出全部数据 + 彻底删除账号、BYOK 密钥 Fernet 加密

**前端 / 后台**

- **全站金色主题统一 + 营销落地页并入**（commit ab06cec）+ 评审链路三页视觉统一（commit 70610ef）
- **管理后台独立应用 web/admin**（commit 3b95fcf）：仪表盘可视化 + 用户/CDK/平台 Key 面板（commit c5e23cf / a2b44af）

### 改进

- 引擎抗第三方模型不合规输出：逐字骨架 + 字段名归一兜底 + 身份字段强制注入（commit cee9cb6 / ed52e10）
- Token 计数系统：引擎保留真实 token → 落库 Review/UsageRecord → 后台聚合展示（commit d544700）
- 任务类型单一注册表 runner/task_types.py，CLI/MCP/Web 共用（commit 9bb9915）
- 匿名用户可追问、回复裁成体验版；追问与人格对话改在同一个对话里执行（commit e5aa5fb / 5acf62d）
- 对外声称对齐代码实际：隐私政策、落地页定价、论文/BP/官网口径全部修正（commit 681307b / cba3a9a / 73e7fa2）

### 修复

- **安全五类真漏洞**：配额可绕过、登录墙可绕过、删号删全库、越权、失败伪装成"无风险"（commit 5babf7f）
- **安全与健壮性**：并发双花 / WS 越权 / 孤儿任务 / 上传 DoS / 前端防重（commit 3a692be）；/api/reviews 系列按用户身份过滤（commit 8ca9c6f）
- **全链路审计两轮**：4 个致命问题 + 10 条高危 + v1/v2 引擎收敛 + 26 条中低危（commit 32e43bc / 13c1c4e / 1320ed0）
- 修复 PDF/DOCX 上传空头支票、图片上传 413、图片不进气泡、只拖图发不出消息（commit 88c53fe / e3aef22 / b6595e3 / defe6d8）
- 修复对话评审空壳（0 角色/0 修复项）、报告追问丢附件、意图解析无视 BYOK 中转（commit ed52e10 / e234673 / cece591）
- 修复"测试连接堵死后端事件循环"（commit 9e7a03d）、创业 BP 评审 100% 失败（commit 00f8734）

**部署**

- Docker 链路修复 + 生产硬化 + TLS + CI（commit 2b90a2d）；Postgres 迁移路径补全并在 CI 真跑（commit de1e5ab）
- 自动备份装进 crontab、.gitignore 堵住备份文件入库（commit 03b2eba / 00f8734）

## [0.2.1] — Enhanced Cross-Examination

### 新增

- **交叉质询增强版**
  - 结构化论证阶段（主张 + 依据 + 推理链）
  - 立场更新机制（confidence 漂移检测 + 立场迁移记录 + 收敛判定）
  - 跨技能质询适配（synthetic-playtest / audience-panel / red-team-audience）
- **一致性验证工具**：tools/parity_check.py
  - 主题重叠度（Jaccard + 最佳匹配均值）
  - 评分相关性（Spearman rank correlation）
  - 立场对齐度（卡方距离分布相似度）
  - 深度对齐度（证据数量 + 直接证据比例 + 证据长度 + 充分性评分）
  - SyntheticUsers 基准线对比（0.85-0.92 区间）
  - 自动生成改进建议
- **竞品对比文档**：docs/competitive-landscape.md
- **Persona 扩展**：从 50 个扩展到 75 个（50 游戏 + 20 产品 + 5 红队）
- **Hook 脚本扩展**：从 4 个扩展到 10 个
  - 新增：log-agent.sh / log-agent-stop.sh / pre-compact.sh / post-compact.sh / notify.sh / detect-gaps.sh
- **双路径支持**：.claude/skills/ 和 .trae/skills/ 均可引用技能

### 改进

- CLAUDE.md 新增 Skills 表格（含 .claude/.trae 双路径引用）
- CLAUDE.md 新增 Tools 章节（引用 parity_check.py）
- CLAUDE.md 新增 Competitive Landscape 章节
- methodology.md 新增交叉质询增强版详细描述
- methodology.md 新增一致性验证章节
- methodology.md 方法流程更新（加入交叉质询增强版和一致性验证步骤）
- roadmap.md 新增 v0.2.1 版本条目
- roadmap.md v0.3 新增 parity-check CLI 命令

## [0.2.0] — Harness Edition

### 新增

- **8 维 Harness 质量评估框架**
  - 行动可操作性评估器
  - 输入接地性评估器
  - 人格差异化评估器
  - 刻板印象检查评估器
  - 结构完整性评估器
  - 校准诚实度评估器
  - 风险检测力评估器
  - 分段冲突度评估器
- **评分量规**：8 维综合量规（1-5 分制）
- **测试夹具**：优质/劣质游戏概念 + 优质/劣质落地页
- **预期结构定义**：synthetic-playtest-required-sections.yaml
- **完整伦理守则**：违规严重度分级、合规评分机制、刻板印象回避清单
- **Persona Schema 校验**：persona.schema.yaml
- **Skills 内置自检阶段**：Phase 7 校准检查

### 改进

- Persona 包从 1 个扩展到 8 个（50 个 Persona）
- 任务类型从 6 种扩展到 14+6 种
- 证据标注从二级扩展到三级（direct / inferred / gap）
- 交叉质询增加说服力评分和立场更新机制
- HTML 评价书生成规则更加详细

### 修复

- 修复 persona 间视角差异不足的问题
- 修复证据接地性检查缺失的问题
- 修复报告结构不完整的问题

## [0.1.0] — Skill Pack

### 新增

- **4 个 Claude Code Skills**
  - synthetic-playtest：游戏焦点合成玩家面板评审
  - audience-panel：通用产品/应用/网站受众面板评审
  - red-team-audience：对抗性红队受众压力测试
  - persona-generate：生成可复用的 AI 评审 persona 面板
- **16 个核心 Persona**（game-core.yaml）
- **6 种游戏任务类型**
  - steam_page_review / demo_first_play / concept_review
  - monetization_review / looking_for_party_post / update_announcement_review
- **五段式 Prompt 模板**
- **焦点争议点质询**
- **规则驱动聚合器**
- **三层校验**：schema + 角色一致性 + 证据接地
- **50 个 Agent 定义**
- **4 个 Hook 脚本**
- **JSON Schema**：output-schema.json / report-schema.json / persona-schema.json
