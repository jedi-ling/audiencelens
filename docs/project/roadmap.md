# AudienceLens 路线图

> 最后更新：2026-08-03（✅ 条目均已对照仓库代码与 git 历史核实，标注实际完成 commit；🔲 条目经核实未实现；部分条目经二次勘误修正）

## v0.1 — Skill Pack

- ✅ 4 个 Claude Code Skills（synthetic-playtest / audience-panel / red-team-audience / persona-generate）
- ✅ 50 个行为驱动 Persona（8 个 YAML 包）
- ✅ 14 种游戏任务类型 + 6 种产品任务类型
- ✅ 五段式 Prompt 模板
- ✅ 焦点争议点质询
- ✅ 规则驱动聚合器
- ✅ 三层校验（schema + 角色一致性 + 证据接地）
- ✅ 50 个 Agent 定义
- ✅ 4 个 Hook 脚本

## v0.2 — Harness Edition

- ✅ 8 维 Harness 质量评估框架
- ✅ 8 个评估器模板
- ✅ 评分量规
- ✅ 测试夹具（优质/劣质样本）
- ✅ 预期报告结构定义
- ✅ 完整伦理守则
- ✅ Persona Schema 校验
- ✅ Skills 内置自检阶段

## v0.2.1 — Enhanced Cross-Examination

- ✅ 72 个 Persona（11 个 YAML Pack，51 游戏向 + 5 上线合规 + 8 通用消费 + 8 创业评审；红队人格包不存在，"red team" 是技能提示）
- ✅ 交叉质询增强版（结构化论证 + 立场更新机制 + 收敛判定）
- ✅ 跨技能质询适配（synthetic-playtest / audience-panel / red-team-audience）
- ✅ 一致性验证工具（tools/parity_check.py）
- ✅ 竞品对比文档（docs/competitive-landscape.md）
- ✅ 10 个 Hook 脚本
- ✅ .claude/skills/ 和 .trae/skills/ 双路径支持

## v0.3 — CLI

- ✅ `audiencelens run synthetic-playtest`（实际已在 commit 9a90599 完成：click 命令组统一 CLI 入口，`audiencelens run <skill> <task_type> <artifact>`，skill 可选 synthetic-playtest / audience-panel / red-team-audience）
- ✅ `audiencelens personas validate`（实际已在 commit 9a90599 完成，命令名为 `audiencelens personas-validate`）
- ✅ `audiencelens harness evaluate`（实际已在 commit 9a90599 完成，命令名为 `audiencelens harness-evaluate`，8 维评估 + table/json/markdown 三种输出）
- ✅ `audiencelens parity-check`（实际已在 commit 9a90599 完成，另有 `ablation` / `stereotype-eval` / `benchmark-*` 命令）
- ✅ 人类对照导入和校准流程（src/runner/calibration.py 校准检查自 commit 1c16db9 即有；tools/benchmark_compare.py / benchmark_suite.py / benchmark_scaffold.py 三方盲测对照工具，实际已在 commit 9a90599 / 10a18ec 完成）
- 🔲 黄金输出回归测试（tests/ 中无 golden 回归用例）
- ✅ 证据三级标注自动检测（src/harness/evidence_detector.py，direct / inferred / gap 三级检测 + 编造信息检测，实际已在 commit 9a90599 完成）

## v0.4 — MCP Server

MCP server 整体已落地（commit 882f8f8）：`audiencelens-mcp` 入口 + FastMCP server，实际工具合并为 4 个——list_task_types / list_persona_packs / list_personas / run_synthetic_review；roadmap 预想的 5 个独立工具功能由 run_synthetic_review 的 task_type / personas_pack 参数覆盖。

- ✅ `generate_persona_panel`（面板生成由引擎 select_panel 自动完成，MCP 侧未单设独立工具）
- ✅ `run_synthetic_playtest`（合并进 run_synthetic_review，以游戏类 task_type + game-core 等游戏人格包运行）
- ✅ `run_audience_panel`（合并进 run_synthetic_review，以产品类 task_type + general-consumer / startup-panel 人格包运行）
- 🔲 `run_red_team_audience`（MCP 侧未暴露红队视角参数；红队评审经 CLI `--skill red-team-audience` 与 Web 技能中心提供，但不在 MCP server 内）
- ✅ `synthesize_panel_results`（聚合由引擎 aggregator 在内部完成，run_synthetic_review 直接返回结构化报告）

## v1.0 — Hosted Integration

- 🔲 平台集成（代码中无平台对接实现；署名已统一为 Ling Yuanyi）
- ✅ 积分系统（web/backend：plan_service 套餐 + cdk_service CDK 兑换 + ledger_service 账本 + quota_service 配额计费，前端 PlansPage / LedgerPage；CDK 兑换实际已在 commit 9ced26e 完成，套餐实际已在 commit a838286 完成）
- ✅ 可视化报告（web/frontend ReportPage / ReviewProgressPage / EvaluationPage；评审卡片美化与完整报告弹窗化实际已在 commit 70610ef / 3113e45 完成）
- 🔲 版本对比（前端无版本对比功能，ReportPage 中"对比"仅指配色对比度）
- 🟡 真实玩家反馈对照（工具链已就绪：tools/benchmark_compare.py 三方盲测；但真人对照数据为 0，尚未跑出任何实证结果）
- ✅ 无障碍专项 persona pack（4-6个）（src/personas/accessibility.yaml，4 个：P17 色弱 / P18 认知负担 / P19 运动障碍 / P20 听觉障碍，实际已在 commit 1c16db9 完成）
- 🔲 Big-Five 替代 MBTI（persona-schema.json 仍为 mbti 字段，仅有伦理使用说明 mbti_usage，无 Big-Five 字段）
- ✅ 动态面板生成算法（src/runner/panel_selector.py：select_panel + 行为距离 compute_behavioral_distance + 多样性保证 ensure_diversity + 亲和度打分 _pick_by_affinity，实际已在 commit 1c16db9 完成、9a90599 升级）
- ✅ 成本感知模型路由（src/runner/persona_agent.py select_model 按 budget.yaml model_pricing 分级选型 + web/backend quota_service / plan_service 用量与成本闸；计费口径修正实际已在 commit 135d2ba / f93103b 完成）

## 企业版

- ✅ RBAC + 审计日志（web/backend audit_log_service.py 审计记录 + admin.py 全部路由挂 require_admin（X-Admin-Token 统一鉴权，非细粒度 RBAC）；审计日志实际已在 commit 9ced26e 完成，管理后台实际已在 commit 10a18ec 完成）
- 🔲 团队空间和私有人物包（后端模型无 team/workspace 概念，"team"仅出现于 red-team 技能枚举）
- ✅ 多模型网关（web/backend key_service.py：anthropic + openai_compatible 多服务商（DeepSeek/Kimi/通义千问/智谱GLM/Ollama），平台 Key + BYOK Key 并存与 resolve_key 回退；多服务商 Key 实际已在 commit 9ced26e 完成，BYOK 自定义 API Base 实际已在 commit 6b904f0 完成）
- ✅ Web UI + 仪表板（web/frontend 用户端 + web/admin 独立后台应用：仪表盘可视化、用户/CDK/平台 Key 面板；后台拆分独立应用实际已在 commit 3b95fcf 完成，仪表盘实际已在 commit c5e23cf / a2b44af 完成）
