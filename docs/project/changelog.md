# 变更日志

所有重要变更都会记录在此文件中。

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
