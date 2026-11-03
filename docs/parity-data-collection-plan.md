# AudienceLens 真人对照数据收集方案（Parity Baseline）

> **版本**：v0.1（草案） | **日期**：2026-08-04 | **状态**：待评审
> **关联工具**：`tools/parity_check.py`（AI vs 真人 4 维一致性）
> **配套文档**：`docs/benchmark-protocol.md`、`docs/pilot-playbook.md`、`docs/product-validation.md`

---

## 1. 背景与目标

### 1.1 现状：尚无真人对照数据

AudienceLens 的核心主张是"多代理合成评审能替代部分真人测试"，但当前**没有任何真人对照数据**来验证这一主张：

- 原 `benchmark-report.md`（2026-07-27 口径勘误版，现已移出仓库）§7.1 明确声明：**"本报告中的所有评分基于设计分析而非真实用户对比实验"**；§7.4 又指出"一致性验证需要真人数据作为参照，目前 parity_check.py 的基准线基于 SyntheticUsers 的公开数据"。
- `docs/product-validation.md`「仍需补齐」清单中列出："建立至少 100 组预测与真人测试/上线数据的配对样本"。
- `docs/benchmark-protocol.md` 的 JSON 契约与 `benchmark-init / benchmark-compare / benchmark-suite` 脚手架已就绪，但缺少真人参考数据填充。

**结论：benchmark-report.md 中没有任何实测的 parity 数字。本文档之前，parity 得分尚不存在。**

### 1.2 目标

收集 **≥ 50 份真人评审数据**（3 个固定任务 × 每任务 ≥ 10 人），每份与同一材料的 AI 评审配对，用 `tools/parity_check.py` 的 4 个加权维度验证一致性，回答：

> "AI 合成评审与真人评审在**主题、评分、立场、深度**四个维度上是否足够接近，足以支撑'替代部分真人测试'的主张？"

### 1.3 指标速查（来自 `tools/parity_check.py`）

| 维度 | key | 权重 | 计算方法 |
|------|-----|------|---------|
| 主题重叠 | `topic_overlap` | 0.30 | Jaccard 相似度（全局 + 每 AI 评审最佳匹配的均值，各占 50%） |
| 评分相关性 | `score_correlation` | 0.25 | 各维度 Spearman 秩相关均值，从 [-1,1] 归一化到 [0,1] |
| 立场对齐 | `stance_alignment` | 0.25 | 正/中/负三立场分布的卡方距离相似度 `1/(1+χ²)` |
| 深度对齐 | `depth_alignment` | 0.20 | AI 侧按证据数量/direct 占比/平均长度加权；真人侧按显式 `depth` 或 issue/score 数量启发式 |

- 综合得分 = 加权和；单维度通过阈值 `PASS_THRESHOLD = 0.6`（代码内逐维度判定 `passed`）。
- 等级：A ≥ 0.90 / B ≥ 0.80 / C ≥ 0.70 / D ≥ 0.60 / F < 0.60。
- **SyntheticUsers 基准线**：`SYNTHETICUSERS_BENCHMARK = {"low": 0.85, "high": 0.92}`，用于横向对比（见 §4）。

---

## 2. 方案设计

### 2.1 收集对象

两个互补人群，覆盖游戏向与产品向两类任务：

| 人群 | 任务类型 | 为什么选他们 |
|------|---------|-------------|
| 独立游戏开发者 / 独立游戏核心玩家 | `steam_page_review`（Steam 商店页）、`demo_first_play`（Demo 首玩） | 与 `docs/pilot-playbook.md` 的 Steam 商店页试点人群重合，反馈可直接回用 |
| 产品经理 / 运营 / 产品侧从业者 | `pricing_page_review`（定价页）、`onboarding_review`（引导流程） | 引擎现有合法任务类型（`landing_page_review` 已从 `VALID_TASK_TYPES` 移除，见 benchmark-report §3），产品向评审需要产品从业者视角 |

不要求参与者是"目标用户"的严格抽样——本方案验证的是**评审内容一致性**，不是市场调研代表性问题。但需记录参与者背景（游戏时长/职业年限等），供后续分层分析。

### 2.2 招募渠道（5 个低成本渠道）

| # | 渠道 | 说明 | 预期转化 |
|---|------|------|---------|
| 1 | Discord 游戏开发者社群（r/gamedev、itch.io、中文游戏开发者社群） | 发帖 + 私信；社群里开发者对"评审我的商店页"天然有强需求 | 高 |
| 2 | V2EX（游戏开发 / 酷工作节点） | 发帖说明"用真人评审意见换免费评审次数" | 中 |
| 3 | 即刻（独立游戏 / 产品经理圈） | 发动态 + 转发；适合招募产品向评审人 | 中 |
| 4 | 独立游戏社区（IndieNova、奶牛关、TapTap 开发者站） | 与 Steam 商店页/Demo 任务直接对口 | 中 |
| 5 | 朋友网络 / 私域（团队已有社群、前用户、合作开发者） | 冷启动最快；注意样本偏向，需在数据里标记来源渠道 | 高（但样本偏） |

每条招募文案固定同一套：任务说明 + 材料链接 + 激励说明 + 预计耗时（15-20 分钟）+ 同意书要点。

### 2.3 激励设计（CDK 兑换码，符合现有机制）

- 每位提交**完整有效评审**（填写全部必填字段且通过基础校验）的参与者，发放 1 个 CDK 兑换码，兑换后获得 **1-3 次免费评审额度（credits）**。
- 复用现有 CDK 机制（`web/backend/app/services/cdk_service.py`）：后台 `CdkPanel` 批量生成 `AL-XXXX-XXXX-XXXX` 格式兑换码，参与者免登录兑换获得评审次数，用于给自己的产品发起 AI 评审——激励与产品价值直接挂钩，零现金成本。
- 操作：`generate_codes(count=N, credits=2, max_uses=1, expires_in_days=90, note="parity-pilot-batch1")`，单批 ≤ 500 个；发放记录保存在 `note`/`batch_id` 便于对账。
- 明确声明激励是"参与感谢"，与评审内容无关，避免利益冲突；不收现金、不买"好评"。
- 建议发放节奏：每批次回收满后统一发放，防止中途流失；对无效提交（字段缺失/明显敷衍）不发放，并在回收记录中标记。

### 2.4 评审任务模板（3 个固定任务）

每个任务 = **一份冻结的评审材料（artifact.json）+ 一份 AI 评审报告 + N 份真人评审**。材料冻结后不可更改，AI 评审与真人评审必须基于**完全相同的材料**（遵循 benchmark-protocol.md 的防泄漏原则：真人参考数据不得进入 AI 评审的上下文，反之亦然）。

| 任务 | 任务类型 | 固定材料 | 评分维度（与 AI 输出对齐） |
|------|---------|---------|---------------------------|
| T1：评审我的 Steam 商店页 | `steam_page_review` | `examples/steam-page-sample/artifact.json`（Echoes of the Void，含截图描述/价格/核心循环/竞品对比） | base：`clarity`、`trust`；task：`differentiation`、`value_for_money`、`wishlist_appeal` |
| T2：Demo 首玩体验 | `demo_first_play` | `examples/demo-sample/artifact.json`（Echoes of the Void Demo，前 15 分钟实机/HUD/控制/教程说明） | base：`clarity`、`trust`；task：`retention_potential`、`onboarding_friendliness`、`moment_to_moment_feel` |
| T3：定价页评审 | `pricing_page_review` | 需新固定一份定价页材料（团队自选或自拟一份含价格档位/FAQ/信任信号的定价页文本；当前 `examples/` 下暂无产品向样例） | base：`clarity`、`trust`；task：`value_for_money`、`pricing_clarity`、`trust_signals` |

> 说明：评分维度名取自 `web/backend/app/services/__init__.py` 的 `TASK_TYPES[*].score_dimensions`，与 `src/runner/persona_agent.py` 的 `TASK_SCORE_DIMENSIONS` 逐字一致——**真人评分必须使用同名维度，否则 `score_correlation` 会因 `common_dimensions` 为空直接得 0 分**。

每个任务的参与者问卷（结构化，控制填写质量）：
1. 整体立场：正面 / 负面 / 中立（三选一，可加"复杂/混合"备注，映射到 neutral）；
2. 列出 2-5 条关键问题（短句，如"教程过长""价格偏高"，供主题重叠用）；
3. 对上述 5 个维度各打 1-5 分；
4. 一句话总体评价（可选，供定性参考）；
5. 背景字段：游戏向（近期玩过的游戏/游戏年资）、产品向（职业年限）；来源渠道。

### 2.5 数据格式（JSON 契约，对齐 `parity_check.py` 的 `parse_human`）

真人数据落盘为每案例一个 JSON 文件，顶层含 `reviewers` 列表（**`parse_human` 只认 `data["reviewers"]`，缺失或为空会直接报错**）：

```json
{
  "case_id": "parity-t1-batch1",
  "task_type": "steam_page_review",
  "artifact": "examples/steam-page-sample/artifact.json",
  "collected_after_ai_frozen": true,
  "reviewers": [
    {
      "id": "P-001",
      "stance": "negative",
      "key_issues": ["教程过长", "价格偏高", "愿望单吸引力不足"],
      "scores": {
        "clarity": 3, "trust": 2,
        "differentiation": 4, "value_for_money": 2, "wishlist_appeal": 2
      },
      "depth": 0.6,
      "evidence_detail": 0.5,
      "meta": {
        "background": "5年独立游戏开发经验",
        "channel": "v2ex",
        "collected_at": "2026-08-04T12:00:00+08:00",
        "consent": true,
        "incentive_paid": "cdk-batch1"
      }
    }
  ]
}
```

字段约定（仅下列字段被 `parse_human` 读取，其余被忽略，安全）：

| 字段 | 要求 | 说明 |
|------|------|------|
| `id` | 必填 | 匿名编号（P-001…），不落真实身份 |
| `stance` | 必填 | 必须是 `STANCE_MAP` 的 20 个键之一（positive/negative/neutral/mixed/cautiously_optimistic/skeptical/…）；推荐只收集三主立场，`mixed` 等会映射到 neutral |
| `key_issues` | 必填 | 字符串数组或 `{"title": ...}` 数组；**短句**为宜（中文按 2/3-gram 分词，长句会稀释重叠度） |
| `scores` | 必填 | 扁平 dict，键 = base + task 维度名（与 §2.4 表一致），值 1-5 数值 |
| `depth` / `evidence_detail` | 可选 | 0-1 的显式自评深度；**不填则由工具按 issue 数/score 数/stance 自动推导**（建议首版不收集，避免自评偏差，让两条链路用同一套结构逻辑） |
| `meta` | 可选 | 收集渠道/背景/时间戳/同意标记/激励批次，供分层分析与审计，不参与计算 |

**AI 侧（synthetic）数据**：直接用引擎产物——`persona_notes` 聚合报告、`reviews` 数组或单个评审对象均可（`parse_synthetic` 三种格式都支持）。推荐每任务固定一份冻结的 AI 报告跨批次复用（材料未变时避免多次生成的随机性干扰对比；如需测稳定性可每批重跑）。

**文件名规范**：`data/parity/<case_id>/human_reviewers.json` 与 `data/parity/<case_id>/audiencelens.json`，`case_id` 如 `t1-batch1`。

---

## 3. 执行节奏（3 批）

每批覆盖 3 个任务，每任务 5-7 人，合计每批 15-21 份；3 批累计 45-60 份（≥ 50 目标）。**每批结束跑一次 `parity_check` 并记录，形成逐步收敛的证据链。**

| 批次 | 时间窗（建议） | 每任务人数 | 本批动作 | 批后动作 |
|------|--------------|-----------|---------|---------|
| 批 1 | 第 1-2 周 | 5-7 | 冷启动：朋友网络 + 1 个社区渠道；收集 T1/T2/T3 | 跑 3 个 case 的 parity；修收集问卷的问题（字段歧义/维度名错误） |
| 批 2 | 第 3-4 周 | 5-7 | 扩到 3-4 个渠道；按批 1 修正后的问卷继续 | 跑 parity；对比批 1 指标变化；若某维度 < 0.4 触发 §5 排查 |
| 批 3 | 第 5-6 周 | 5-7 | 补足薄弱任务的样本量（每任务累计 ≥ 10，满足 benchmark-protocol 低置信度线） | 汇总 3 批全部 case 的 parity；输出总报告 |

里程碑门槛（对齐 `docs/benchmark-protocol.md`）：

- 每 case 累计真人样本 **≥ 10**（否则结果强制标记低置信度）；
- 每批后必须同时报告 4 个维度，不允许只挑最好看的指标；
- 未达门槛前，对外只能展示原始样本数，不能宣传"准确率/提升百分比"（对齐 pilot-playbook.md 规则）。

---

## 4. 通过标准

**核心主张（"AI 评审能替代部分真人测试"）成立的最低门槛：4 维度综合得分 ≥ 0.6，且每个单维度 ≥ 0.6**（与 `parity_check.py` 的 `PASS_THRESHOLD` 一致，代码里逐维度标 `passed`）。

参考对标：

- **SyntheticUsers 基准 0.85-0.92**：`parity_check.py` 内置的 `synthetic_baseline` 会输出 `comparison_status`（exceeds/within/below benchmark）与差距。这是"另一个合成评审产品与真人数据的一致性"参考区间，**不是我们的承诺目标**——真人评审间的一致性本身也达不到 1.0，合理预期是先达到 0.6 门槛，再向 0.85-0.92 逼近。
- 达成门槛后的汇报口径示例："在 N 份真人对照样本上，AI 评审与真人评审的主题重叠/评分相关/立场对齐/深度对齐综合得分 X（SyntheticUsers 基准区间 0.85-0.92），四个维度均 ≥ 0.6。"
- **未达成时**：如实报告分数与样本量，不对外宣称验证成功（遵循 benchmark-report.md 的诚实口径先例）。

---

## 5. 失败处理（单维度 < 0.4 排查表）

> 0.4-0.6 之间属于"未通过但接近"，优先补样本、改进收集质量后再判断；
> **< 0.4 说明存在系统性偏差**，按下表区分是 **AI 评审问题** 还是 **真人收集方式问题**：

| 维度 < 0.4 | 可能是 AI 评审问题 | 可能是真人收集方式问题 |
|-----------|------------------|----------------------|
| `topic_overlap` 主题重叠 | AI 输出跑题/幻觉，key_issues 与材料无关；AI 用词过于抽象 | 参与者未仔细看材料（敷衍）；问题写得太笼统（如"不好玩"）或太长；**词法切分限制**（同义词不共享 token，benchmark-protocol §7 已注明中文主题匹配受切分限制） |
| `score_correlation` 评分相关 | AI 评分系统性偏高（全部 4-5 分）或与人类评分标准相反 | 维度名拼写/中英文不一致 → `common_dimensions` 为空得 0；参与者不理解 1-5 评分含义（问卷缺少锚点示例） |
| `stance_alignment` 立场对齐 | AI 人格面板立场分布偏斜（如默认保守中立）；人格提示词诱导正面 | 招募样本偏差（对项目感兴趣的人才愿评 → 偏正面）；问卷立场选项设计诱导 |
| `depth_alignment` 深度对齐 | AI 深度计算依赖 evidence 结构（长度/direct 占比），AI 输出超长 → 深度虚高 | 人类填写过于简略（1 个 issue、无 scores → 启发式深度被压低）；未按"2-5 条问题 + 5 个维度分"的模板填写 |

**排查步骤**（按顺序执行，先低成本后高成本）：
1. 打开该 case 的 `parity` 结果 JSON，看 `details`（`shared_themes` / `synthetic_only_themes` / `human_only_themes`、`per_dimension`、分布对比），定位是"漏掉主题"还是"用词不同"；
2. 抽查 2-3 份原始人工问卷，判断是填写质量问题还是真实意见分歧；
3. 若是收集方式问题：修订问卷（加评分锚点、限定 issue 条数与句式）、更换渠道、补充"是否认真看了材料"的自检问题；
4. 若是 AI 评审问题：按 benchmark-protocol 的失败处理逻辑——"缩减人格和质询流程，定位无增益环节"；对某一任务子类型显著弱时收窄适用范围，而不是平均所有场景（对齐 pilot-playbook 失败处理）；
5. 重跑批次收集（注意防泄漏：修正后的问卷不可把 AI 答案透露给参与者）。

---

## 6. 与现有工具衔接

收集完成后，用 `parity_check.py` 逐 case 计算：

```bash
# 方式一：CLI 集成命令（推荐）
python src/cli.py parity-check \
  --synthetic data/parity/t1-batch1/audiencelens.json \
  --human    data/parity/t1-batch1/human_reviewers.json \
  --output   data/parity/t1-batch1/parity.json

# 方式二：独立脚本（无依赖/调试用）
python tools/parity_check.py \
  --synthetic data/parity/t1-batch1/audiencelens.json \
  --human    data/parity/t1-batch1/human_reviewers.json \
  --output   data/parity/t1-batch1/parity.json
```

输出结构（`compute_parity` 返回，附加 meta 后落盘；**下列数值仅为演示输出结构的占位示例，非实测数据**）：

```json
{
  "meta": { "tool": "AudienceLens Parity Check", "version": "2.0.0", "generated_at": "..." },
  "dimensions": [
    { "name": "主题重叠", "key": "topic_overlap", "weight": 0.30, "score": 0.71, "passed": true },
    { "name": "评分相关性", "key": "score_correlation", "weight": 0.25, "score": 0.62, "passed": true },
    { "name": "立场对齐", "key": "stance_alignment", "weight": 0.25, "score": 0.88, "passed": true },
    { "name": "深度对齐", "key": "depth_alignment", "weight": 0.20, "score": 0.55, "passed": false }
  ],
  "overall_score": 0.7002,
  "grade": "C",
  "synthetic_baseline": {
    "syntheticusers_range": "85%-92%",
    "audience_lens_score": 0.7002,
    "comparison_status": "below_benchmark",
    "gap_from_low": 0.1498
  }
}
```

衔接点：

- **同一份真人数据可复用于 `benchmark-compare` 三候选盲测**：`docs/benchmark-protocol.md` 的 `--reference` 就接受本方案的 `reviewers` JSON；先跑 `benchmark-init` 建案例目录（不覆盖已有数据），填好三个候选（AudienceLens / single-prompt / 人工快评）后跑 `benchmark-suite`。真人数据按本方案收集即可一举两用。
- 真人数据**不得**进入 AI 评审的上下文；反之 AI 输出在真人收集完成前封存（`collected_after_ai_frozen: true`），遵循 benchmark-protocol 的防泄漏规则。
- 记录每份评审的成本与耗时（对齐 benchmark-protocol 解释规则：质量增益不能脱离单位经济性）。

---

## 7. 伦理注意

本方案涉及真实人类参与者，受 [`ETHICS.md`](ETHICS.md) 与相关法规（GDPR / 个人信息保护法）约束：

1. **知情同意**：每位参与者提交前须勾选同意书，至少包含——用途（AI 一致性验证研究）、数据如何被使用（仅聚合对比，不对外展示原始内容）、可随时撤回与删除、无"购买好评"意图。
2. **最小化收集与匿名化**：只收集任务所需字段（评审内容 + 可选背景），**不收集姓名、联系方式等 PII**；`id` 使用匿名编号 P-001…；如需发放 CDK 需要联系方式，则分开存证，评审数据与身份脱钩（可参考 `web/backend` 已有的 shared anonymous isolation 机制）。
3. **数据脱敏与存储**：评审内容中如出现个人可识别信息（真实姓名/组织名），落盘前脱敏；数据存放在受限访问目录，不进入公共示例。
4. **与 AI 数据隔离**：真人数据仅作参照，**不得用于构建 persona**（ETHICS.md 明确"禁止使用可识别个人身份的信息构建 persona"，且 persona 不得基于任何真实个人）；AI 输出与真人数据分开归档，防止污染。
5. **诚实标注**：后续任何报告必须区分"合成评审"与"真人对照数据"，禁止把 AI 输出冒充真人数据，也禁止把尚未达标的一致性分数宣传为已验证结论（对齐 benchmark-report.md 的勘误先例）。
6. **激励合规**：CDK 激励明确为"参与感谢"，避免暗示"付费买结论"；对无效/敷衍提交不发激励并告知原因。

---

## 附录 A：参与者问卷（简版，随任务材料发放）

1. 这份材料是（Steam 商店页 / Demo 首玩 / 定价页），请先完整阅读材料再作答。
2. 你的整体立场是：□ 正面 　□ 中立 　□ 负面
3. 请列出 2-5 条关键问题（每条一句话，如"教程过长"）：
   - 1) ______
   - 2) ______
   - 3) ______
   - 4) ______（可选）
   - 5) ______（可选）
4. 请对以下维度打 1-5 分（1=很差，5=很好；[任务对应维度名]）：`clarity` __、`trust` __、[task 维度 1] __、[task 维度 2] __、[task 维度 3] __
5. 一句话总体评价（可选）：______
6. 背景（可选）：游戏/产品相关年资 ______ ；你是从哪里看到本次招募的 ______
7. 我已知悉并同意上述数据使用说明：□ 同意

> 各任务的评分维度名由 §2.4 表格按任务类型替换；问卷版本号随批次记录，便于追溯。

---

## 附录 B：与其他文档的关系

| 文档 | 与本方案的关系 |
|------|--------------|
| `docs/benchmark-protocol.md` | 本方案是它的"真人参考数据"来源；JSON 契约与其 §「JSON 契约」一致 |
| `docs/pilot-playbook.md` | Steam 商店页试点的真人盲测数据可直接并入本方案的 T1/T2 样本 |
| `docs/product-validation.md` | 本方案推进其"仍需补齐"中的"100 组配对样本"第一步（≥ 50 份起步） |
