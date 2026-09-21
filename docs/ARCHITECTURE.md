# AudienceLens 全链路架构

> 本文描述**前后端框架与所有预埋链路**。运维操作看 [MAINTENANCE.md](MAINTENANCE.md)。
> 核心引擎（人格/交叉质询/聚合）看 [../README.md](../README.md)。

## 一句话

一套**开源单机形态**开箱即用、**改几个环境变量就能切成托管 SaaS** 的评审系统。
所有未来要接的链路（登录、计费、队列、上传、对话入口、判断复利）都已埋好并通电——
不是 TODO 注释，是能跑、有测试覆盖的最小实现 + 明确的扩展缝。

---

## 1. 分层总览

```
                    ┌─────────────────── 前端 (React 19 + Vite) ───────────────────┐
                    │  pages/AskPage        真多轮对话入口（历史拼接 → 意图解析     │
                    │                       → 开庭），不再是单轮表单              │
                    │  pages/LoginPage      登录/注册（渐进式认证，见 §2.6）        │
                    │  pages/RegisterPage                                          │
                    │  pages/LedgerPage     判断复利（预测留档 → 回填 → 命中率）    │
                    │  lib/apiClient.ts     类型化客户端（统一 token / 错误 / 基址）│
                    │  lib/ws.ts            WS 客户端（指数退避重连 + 轮询兜底）    │
                    │  store/session-store  身份 + 后端开关 + BYOK key 状态         │
                    └───────────────┬─────────────────────────────────────────────┘
                                    │ HTTP /api   +   WS /ws/review/{id}
                    ┌───────────────┴─────────────────── 后端 (FastAPI) ───────────┐
   请求守卫链 →     │  deps.py     限流 → 身份 → key 解析 → 配额                    │
                    │  api/platform.py   health/auth/keys/intent/uploads/usage/     │
                    │                    v2 评审/jobs/ledger                        │
                    │  api/__init__.py   既有业务路由（personas/task-types/…）      │
                    ├──────────────────────────────────────────────────────────────┤
                    │  services/                                                   │
                    │    key_service      BYOK vs 服务端 key —— "谁付这次的钱"      │
                    │    quota_service    配额 + 用量流水（计费事实源）             │
                    │    job_service      异步队列（线程池，可换 Celery/RQ）        │
                    │    intent_service   意图解析（LLM 档 + 启发式降级档）         │
                    │    ledger_service   判断复利闭环（护城河）                     │
                    │    review_service   把 runner 引擎接进全链路                   │
                    ├──────────────────────────────────────────────────────────────┤
                    │  core/  errors / logging / security / ratelimit               │
                    │  db.py  models/  config.py（所有开关的唯一来源）              │
                    └───────────────┬──────────────────────────────────────────────┘
                                    │  复用（同一套 src/runner 被 CLI 与 Web 共用）
                    ┌───────────────┴──────────────────────────────────────────────┐
                    │  src/runner/   面板选择 → 证据预检 → 人格并发评审 → 三层校验  │
                    │                → 争议点提取/派生摘要 → 聚合 → 校准            │
                    │  src/harness/  8 维事后打分卡 / 刻板印象检测 / 消融实验        │
                    └──────────────────────────────────────────────────────────────┘
```

**第三个消费者——`web/admin/`**：与用户产品前端并列、完全独立的运营后台
（自己的 `package.json`/端口 5200/构建产物，不共享路由，不共享 JS 包）。
只认 `/api/admin/*`，走 `X-Admin-Token` 而非用户的 Bearer JWT，可以单独部署
到内网/VPN，不随用户产品前端一起发布到公网。详见 [MAINTENANCE.md](MAINTENANCE.md)
「后台管理面板」一节。

**根目录下两个 `audiencelens-*-harness/` 与 `src/harness/` 的关系**（三者容易被误认为同一样东西，注意区分）：
- `src/harness/`——本项目内置的质量评估引擎（8 维评分、刻板印象检测、消融实验），是 `src/runner/` 评审流水线的一部分，随主仓库一起维护。
- `audiencelens-v0.2-harness/`——`web/backend` 运行时依赖的评委规则集/评分标准来源（`ethics_service.py`、`evaluation_service.py` 在启动时从这里读取 evaluators/rubrics/刻板印象模式；缺失时优雅降级为内置规则）。**已转正入库**：`.gitignore` 里那条忽略已删除并写明原因，`git ls-files audiencelens-v0.2-harness` 下有 33 个文件，`docker-compose.yml` 也把它挂进后端容器。转正的理由是「缺了它会静默降级」——降级这件事不报错，fresh clone 出来的站点看起来一切正常，只是评分口径悄悄换成了内置的那套。
- `audiencelens-harness/`——完全独立的开源发行仓库，自带 `.git`（指向 `github.com/jedilpf/audiencelens-harness`），是面向 Claude Code / Cursor 的 Skill 包分发版本，与本仓库的 `src/`、`web/` 代码无任何导入/调用关系，只是恰好放在同一层目录下。同样已 `.gitignore`。

---

## 2. 一次评审的完整链路

```
POST /api/v2/reviews
  │
  ├─ 1. rate_limit("review")        默认 20 次/小时（AL_RATELIMIT_*）
  ├─ 2. optional_identity           渐进式认证：带 token 用真实身份，不带永远匿名可用
  ├─ 3. resolve_llm_key             BYOK / managed / hybrid，无 key → 428
  │                                 ↑ 绝不返回模拟数据，这是产品底线
  ├─ 4. check_quota                 BYOK 不限；服务端 key 才受配额约束
  │
  ├─ 4.5 project_memory.attach_to_bundle   同 project_key 下**尚未被证伪**的历史
  │                                 判断作为背景材料进 bundle（被回填 miss 的不带）。
  │                                 匿名身份一律不带——匿名桶所有访客共用，注入即泄漏。
  │                                 v1 与 v2 调同一个函数（收敛测试盯着）。
  ├─ 5. 落库 Review(status=pending) + 入队 Job
  └─ 6. 202 返回 { review_id, job_id, key_source, websocket }

后台 worker（job_service 线程池）
  │
  ├─ WS: review.started
  ├─ runner.run_panel(max_concurrency=6, progress_callback=…, api_key=…)
  │     ← 人格并发（实测约 4×）；key 显式传参，绝不写进程全局环境变量
  │       （多 worker 并发跑不同用户的评审时，环境变量注入会串 key）
  │     ← 每个人格完成即回调 → WS: review.persona_completed {persona_id, done, total}
  │                              WS: review.progress {progress: 5→80}
  │                              job.progress 同步更新
  │     ← wide_screen=true 时走**两层评审**：L1 全包初筛（每位人格一次廉价
  │       短调用，只出立场+严重度+一句话关切，材料截断至 4000 字符并留痕）
  │       → 确定性门禁 rank_for_advance（严重度降序 + 少数派立场加权 +
  │         异见者保底，同分按 persona_id 字典序）→ L2 胜出者走完整评审。
  │       选谁进深评可复现、逐人有理由——不是又一次黑箱模型调用。
  │       显式点名人格时初筛让位（与 adaptive_panel 同一条纪律）。
  │     ← adaptive_panel=true 时先跑小面板，再按任务亲和度 / 行为新颖度 /
  │       证据缺口覆盖率逐个扩面；低于阈值或达到成本上限即停止。
  │       报告中的 method 明示为 marginal_value_proxy_v1（启发式，不冒充信息增益）
  ├─ 安全网：若 result.simulated == true → 直接丢弃并报错（不让假数据入库）
  ├─ 落库 report + persona_outputs
  ├─ ledger.record_judgments()             ← 预测盖时间戳留档（护城河）
  ├─ quota.record_usage()                  ← 记账（即使配额没开也记）
  └─ WS: review.completed
```

> 并发下 `review.progress` 可能乱序到达（done=3 先于 done=2），前端取 max 处理。

**前端**：`POST` 后拿 `review_id` → `connectReviewSocket()` 订阅进度 → 终态跳报告页。
WS 连不上时自动回落轮询 `GET /api/v2/reviews/{id}`。

### 2.6 渐进式认证 + 报告分级（"体验机会 + 登录看详情"）

`AL_AUTH_ENABLED=true` 打开的是**认证能力**（`/auth/register`/`/auth/login` 生效），
不是"强制登录墙"——`app/deps.py` 的 `optional_identity` 在所有评审/Key/意图解析
路由上取代了原来的 `current_identity`：带合法 token 解析出真实用户，不带或 token
无效一律静默回落匿名，两种路径都不 401。这样打开认证开关既不影响现有的匿名单机
体验，又能让登录用户拿到基于真实身份的额度归属。

报告详情按登录态分级，落在 `app/services/report_gating.py`（`gate_report_for_anonymous`），
新旧两条评审链路共用一份逻辑：
- `GET /api/v2/reviews/{id}`（`api/platform.py`，对话式入口用）
- `GET /api/reviews/{id}/report`（`api/__init__.py`，`ReportPage.tsx` 实际调用的旧链路）

匿名只能看 `executive_summary` + 第一条 `priority_fixes`，`persona_notes`/`consensus`/
`major_disagreements`/`cross_examination` 全部裁掉，返回体带 `is_gated: true` 和
`gated_counts`（隐藏了几条）供前端渲染"还有 N 条，登录解锁"提示。登录用户拿到完整
`report_json`。`web/frontend/src/lib/api.ts` 的 `fetchReport` 现在会带上 Bearer token——
早期这里没带，导致登录了也白登录，见测试 `test_auth_and_gating.py`。

---

## 3. 每条预埋线的现状与激活方式

| 链路 | 默认状态 | 已实现的最小闭环 | 激活/升级方式 |
|---|---|---|---|
| **身份认证** | 匿名 | JWT 签发/校验、口令 PBKDF2 哈希、注册/登录接口 | `AL_AUTH_ENABLED=true` |
| **BYOK Key** | 启用 | 密文落库、掩码回显、轮换、解析链 | 默认即用；改 `AL_KEY_MODE` 切托管 |
| **配额计费** | 关闭（但**照常记账**） | UsageRecord 流水、24h 窗口聚合、402 拦截、**free/pro/team 套餐限额**（`plan_service.py`，按 `user.plan` 生效） | `AL_QUOTA_ENABLED=true` |
| **限流** | 启用 | 内存令牌桶、按用户/IP 分桶 | 多副本部署时换 Redis 后端 |
| **任务队列** | 线程池 | Job 落库、进度、失败记录、取消 | 实现 `JobBackend` 换 Celery/RQ |
| **WebSocket** | 启用 | 5 类事件、线程安全推送、origin 白名单 | 生产配 `AL_CORS_ORIGINS` |
| **上传** | 启用 | 类型/大小校验、UTF-8 解码、落盘 | 换 S3：改 `api/platform.py:upload_file` |
| **意图解析** | 启用 | LLM 档 + 启发式降级档（无 key 也能用） | 默认即用 |
| **LLM 服务商** | 启用 | 双路径出口 `runner/llm_client.py`：Anthropic 原生 SDK + 任意 OpenAI 兼容 HTTP（DeepSeek/Kimi/通义千问/智谱GLM/Ollama），不依赖 litellm | BYOK/平台 key 各自存 `provider/model/api_base`；`/api/keys/test`、`/api/admin/server-key/test` 走同一条真实链路，不是摆设 |
| **多模态** | 启用 | 图片走独立上传白名单转 `data:` URI；内部统一用 OpenAI Vision 内容块，按 provider 转换（Anthropic）或原样透传；非视觉模型静默降级为纯文字，不中断评审 | `/api/uploads` 图片扩展名默认 `.png,.jpg,.jpeg,.webp,.gif`；`VISION_CAPABLE_PREFIXES` 控制哪些模型真正"看" |
| **判断复利** | 启用 | 可证伪干预假设留档、回填验证、命中率、Brier/ECE 校准、人格排行 | 默认即用 |
| **CDK 兑换码** | 启用 | 后台批量生成、免登录兑换（匿名兑换时自动签发游客身份）、防枚举限流；两种配额模式：`plan`（日限用完后垫）/ `credits`（纯次数制，每次评审 -1，用完即止） | CDK 发码运营：`AL_AUTH_ENABLED=true` + `AL_QUOTA_ENABLED=true` + `AL_QUOTA_MODE=credits`（次数只对服务端垫付 key 生效） |
| **游客试用** | 启用 | 匿名用户**第一次发起评审**时自动签发一个独立游客身份并附赠几次体验额度，不需要注册也不需要 CDK。签发有每日上限，防止有人循环刷身份把垫付额度当无限用；试用完可以在原地绑定邮箱把身份升级成正式账号，历史评审不丢 | 额度与签发上限都在 `web/backend/app/services/guest_service.py` 顶部的常量里，这里不重复写数字 |
| **QQ 互联登录** | 可选 | `AL_QQ_APP_ID` / `AL_QQ_APP_KEY` / `AL_QQ_REDIRECT_URI` 三项配齐才启用；`/api/health` 的 `qq_login_enabled` 决定前端画不画那个按钮 | 三项少配一项 = 按钮不出现且无报错。Docker 下还要确认 compose 透传了这三个变量（有 `test_compose_env_matches_config` 守着） |
| **分享页 / 项目 / 对话** | 启用 | 评审可生成只读分享页（可撤销）；评审按 `project_key` 归入项目，同项目历史判断进下一次评审（见 §4.4）；发起评审前的澄清对话落库，可重命名/删除 | 见 §5 的 `/v2/reviews/{id}/share`、`/v2/projects`、`/v2/conversations` 三组 |
| **结构化错误** | 启用 | 统一 `{error:{code,message}}`，错误码清单见 §5（唯一事实源是 `web/backend/app/core/errors.py`，这里不再写条数——曾经写 9、实际 10） | 新错误继承 `AppError` |
| **可观测性** | 启用 | 请求 ID、耗时日志、`X-Request-Id` 回传 | 接 Sentry：改 `core/logging.py` |

---

## 4. 三个关键设计决定（以及为什么）

### 4.1 无 key 时**拒绝**，而不是返回模拟数据

模拟输出是预制占位数据，**没有任何评审价值**。若在 Web 端悄悄返回它，
用户会以为"这系统就这水平"。所以：

- 入口 `resolve_llm_key` 直接抛 428 `llm_key_missing`
- 后台再加一道安全网：`result.simulated == true` 就丢弃并报错
- 前端 `ApiError.needsApiKey` 判定后**引导去设置页**，而不是弹个干瘪报错

CLI 里保留模拟模式（带醒目警告）仅供开发者验证流水线。

### 4.2 配额关着也要记账

`quota_service.record_usage()` **无条件写 UsageRecord**。
等你想收费那天，历史用量数据早已存在——不必等"想收费了"才开始埋点，那时就晚了。

`key_source` 字段区分 BYOK / server：**BYOK 花的是用户自己的钱，不计入你的配额**。

### 4.3 判断复利闭环是护城河，不是附加功能

一次性评审工具跑完就断了，经验不沉淀。这一层把优先修复项转换成带
`target_metric / comparison / success_criterion / verification_window` 的
**可证伪干预假设**并盖时间戳留档。它不虚构效果量，置信度明确标为尚未实证校准的
合成面板启发式。真人测试回来回填 Outcome。于是系统能回答"P14 的判断历史上准不准"。

我们的验证来源是**真实用户测试**——干净的 ground truth，不像股价那样掺运气噪音。

**诚实原则写进代码**：样本 < 10 时 `low_confidence=true` 且 `note` 明说"不具统计意义"，
UI 必须显示。绝不用 3 个样本吹准确率。

**闭环现在反哺一处，仍未反哺推理权重（别对外说成"越用越准"）**：

*已接上的那一处*——项目记忆（见 §4.4）。回填结果**直接决定**下一次评审看不看得到
这条判断：判为 miss 的不再进入同 `project_key` 的评审上下文。这是回填第一次有了
真实后果，也是"回填"从记分动作变成产品机制的那一步。

*仍未接上的*——历史命中率**没有**接回 `panel_selector` 或聚合权重：系统不会因为
某个人格历史上准就自动多选它或给它加权，要不要更信某个人格由用户自己判断。
留档、回填、命中率、Brier Score、ECE、可靠性分箱、`low_confidence` 标注、
leaderboard 都已实现，但"按历史表现自动调权"是路线图不是现状。

**「你 vs 评审团」——留档从"只评工具"变成"两边都记"**

留档层原先只记评审团的预测，所以回填之后系统只能回答一个问题："这个工具准不准"。
而用户真正关心的是另一个："我自己在变准吗"。现在两边都记：

- `POST /api/ledger/reviews/{id}/my-judgment` —— 用户在看完报告后写下**自己的**判断
  （claim / stance / confidence / rationale），可以用 `based_on_judgment_id` 挂在
  评审团的某条预测上表示"我不同意这条"。它和评审团的预测进同一张表、用同一套
  回填与校准算法，日后才可比。
- `GET /api/ledger/scoreboard` —— 同一批回填结果下两个来源各自的命中率。
  **双方都有已定论样本时才给对比结论**：任一方为空就如实说明，不拿 0/0 拼一个
  "你 100% 领先"出来（`comparable=false` + `note`）。这是 §4.3 开头那条诚实原则
  在对比场景下的同一条规则。

为什么这算护城河而不是功能：工具的命中率是工具的资产，用户自己的命中率是
**用户的**资产——后者会让人不舍得换工具。但它成立的前提是回填，所以产品上
一切设计都围绕"让回填这件事足够轻"。

另注：v1 链路目前不记 judgment，两条链路的口径尚未统一。

### 4.4 项目记忆：同项目的历史判断进下一次评审

`project_memory_service.attach_to_bundle()` 在评审入队前跑，把同 `project_key` 下
**尚未被证伪**的历史判断拼成一条材料塞进 bundle。三条红线各有测试钉住并做过
破坏性验证（改坏 → 测试红 → 还原 → 绿）：

1. **被回填 miss 的判断不再带入。** 判定一句 claim 带不带，只看它**最新那条**的
   回填结论——所以去重必须在 miss 过滤**之前**。反过来做会静默绕过这条红线：
   最新那条被证伪的行先被剔除，同一句 claim 的更旧未验证副本顶上来成为去重赢家，
   被证伪的判断照样进提示词，还顶着"尚未验证"的标签。多代理审计实测复现过。
2. **匿名身份一律不带。** 关掉认证时所有访客共用同一个 `anonymous` user_id，
   而 `project_key` 是自由文本——两个互不相识的访客起了同名项目就会读到对方的结论。
3. **注入内容必须可见。** 材料本身进 `Review.artifact_bundle`（天然可审计），
   另在 bundle 上挂 `project_memory` 元数据，报告页如实展示带了几条、没带的原因。

已知取舍：这条材料会进 `artifact_texts`，所以人格把历史结论当 `direct` 证据引用时
幻觉检测不会拦。反过来（排除出 `artifact_texts`）会让**如实引用历史**的人格被判成
幻觉，那个误伤更糟——改用提示词正文明写"这是背景，不是本次材料的直接证据"来约束。

### 4.5 两层评审：让"72 个人格"名副其实

`wide_screen=true`（默认关）时，评审从"选人后截断"变成两层：

```
L1 全包初筛   所选人格包**每一位**一次廉价短调用（fallback_model 档）
              只出 立场 + 严重度 + 一句话关切；材料截断至 4000 字符并留痕
    ↓
门禁          rank_for_advance：确定性排序，不是又一次模型调用
              严重度降序 → 少数派立场加权 → 异见者保底 → 同分按 id 字典序
    ↓
L2 深评       胜出者走完整评审 + 交叉质询（人数上限仍是档位的 3/6/8）
```

为什么门禁是确定性的：**选谁进深评必须可复现、逐人可解释**。用模型选人等于把
"选谁"也变成不可复现的黑箱，而这恰恰是最需要说清楚的一步。排序目标是**分歧信号
最大化**而非"选最悲观的"——分歧是交叉质询机制的燃料，全员和气的面板不值得付深评的钱。

初筛结论**只用于选人，绝不混进正式结论**：它是廉价模型 + 截断材料跑出来的粗筛信号，
质量低于完整评审一个档位。报告里它放在独立的 `report["triage"]` 块并标明口径。

初筛 token 在 `cost_summary` 里单列（`triage_input_tokens` / `triage_output_tokens`）——
它用的是便宜档模型，混进人格深评的用量会让单价估算失真。

显式点名人格时初筛整层让位：用户指定的角色一个都不能被门禁筛掉。

### 4.6 证据构成：给报告自己记账，不给产品打分

`aggregator` 产出两块**纯规则**的数字（零 LLM 调用）：

- `evidence_profile` —— 全体人格证据的 direct / inferred / gap 构成、推断占比、
  以及**随报告落库的阈值**（历史报告要按当时的规则解读，规则改了不能追溯改写）。
  口径与 `validator` 逐字一致：未标注等级的条目计入分母但不算 inferred。
  `MAX_INFERRED_RATIO` 是单一常量，validator 拦人格、aggregator 记账、前端展示三处同源。
- `dimension_scores` —— 逐维度**简单均分** + min/max + 人数。

**刻意没有加权综合分。** 权重没有任何校准依据，编一套就是假精确；min/max 一起给是
因为"均分 3.0"可能是全员 3 也可能是 1 和 5 对半，只报均值会把最有信息量的分歧抹掉。
测试里有红线断言：报告里不存在 `overall_score`，维度条目不带 `weight`。

度量对象是**报告自身的可信度**，不是产品得分——合成面板给产品打一个综合分是假精确，
给自己的证据构成记账是诚实的。

---

## 5. API 契约速查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 探活 + 当前生效开关（绝不泄露密钥） |
| GET | `/api/auth/me` | 当前身份（匿名形态返回 `is_anonymous:true`） |
| POST | `/api/auth/register` `/login` | 认证关闭时返回 400 |
| GET/POST/DELETE | `/api/keys` | BYOK key（`provider/model/api_base`，仅掩码回显，明文只进不出） |
| POST | `/api/keys/test` | 真实测一次 key 连通性——走 `runner.llm_client`，评审真正会用的那条链路 |
| POST | `/api/intent/parse` | 大白话 → 评审参数（`method` 字段声明用了哪档） |
| POST | `/api/uploads` | 上传材料，返回文本 |
| GET | `/api/usage` | 24h 用量与配额（含当前套餐限额与 CDK 加量余额 `bonus_credits`） |
| POST | `/api/cdk/redeem` | 兑换 CDK 获得评审次数——免登录，匿名兑换自动签发游客身份（限流 10 次/分钟防枚举） |
| GET | `/api/plans` | 套餐矩阵 free/pro/team（公开，纯静态定价数据） |
| **POST** | **`/api/v2/reviews`** | **发起评审（202，异步）** |
| GET | `/api/v2/reviews/{id}` | 评审详情/报告 |
| GET | `/api/jobs/{id}` | 任务状态与进度 |
| GET | `/api/ledger/judgments` | 历史预测（`only_unverified=true` 即待回填工作台） |
| POST | `/api/ledger/judgments/{id}/verify` | 回填真实结果 |
| GET | `/api/ledger/hit-rate` | 命中率（带 `low_confidence` 诚实标注） |
| GET | `/api/ledger/calibration` | 置信度可靠性（Brier Score、ECE、五档分箱；小样本警告） |
| GET | `/api/ledger/leaderboard` | 人格命中率排行 |
| POST | `/api/ledger/reviews/{id}/my-judgment` | 记下**用户自己的**判断，与评审团预测并列留档（见 §4.3） |
| GET | `/api/ledger/scoreboard` | 你 vs 评审团：同一批回填下两边各自的命中率；双方都有已定论样本才给结论 |
| POST/GET/DELETE | `/api/v2/reviews/{id}/share` | 生成 / 读取 / 撤销只读分享页 |
| GET/PATCH/DELETE | `/api/v2/projects[/{id}]` | 项目列表与改名/删除（`project_key` 是项目记忆的分组键，见 §4.4） |
| GET/PATCH/DELETE | `/api/v2/conversations[/{id}]` | 发起评审前的澄清对话：列表、详情、改名、删除（删号时一并删除，见隐私政策） |
| GET | `/api/auth/qq/authorize` · POST `/api/auth/qq/exchange` | QQ 互联登录：取授权地址 / 用 code 换本站会话（三项配置齐备时才可用） |
| WS | `/ws/review/{id}` | 进度推送 |
| GET | `/api/admin/overview` | 跨用户系统概览（需 `X-Admin-Token`，见 §8） |
| GET | `/api/admin/timeseries` | 近 N 天评审量/成本趋势（可视化图表用） |
| GET | `/api/admin/ledger` | 判断复利全局聚合（跨全体用户的命中率/人格排行） |
| GET/PUT/DELETE | `/api/admin/settings[/{key}]` | 运行时配置覆盖，改动无需重启 |
| GET/PUT/DELETE | `/api/admin/server-key` | 平台级 API Key（`provider/model/api_base`，托管/混合模式垫付用） |
| POST | `/api/admin/server-key/test` | 真实测一次已保存的平台 key（同一条 `runner.llm_client` 链路） |
| GET/PUT/DELETE | `/api/admin/plans[/{id}][/{field}]` | 套餐可编辑覆盖（价格/额度，改动无需重启） |
| GET/PUT | `/api/admin/users[/{id}]` | 用户管理：列表（带评审数/累计成本）、改套餐、停用/启用 |
| GET | `/api/admin/stats/task-types` `/persona-packs` `/costs` | 统计分析：任务类型分布、人格包使用量、成本构成（BYOK vs 垫付 + Top 用户） |
| POST/GET/PUT | `/api/admin/cdk[/generate][/{id}/disable]` | CDK 兑换码：批量生成 / 列表（按状态过滤）/ 停用 |
| GET | `/api/admin/audit-log` | 管理员操作审计流水 |
| GET | `/api/admin/jobs` `/reviews` | 任务/评审巡检（支持 status/user_id/时间范围过滤 + 分页） |
| GET | `/api/admin/jobs/{id}` `/reviews/{id}` | 任务/评审详情下钻（含完整 payload/report_json） |
| DELETE | `/api/admin/reviews/{id}` | 删除评审（级联判断留档；UsageRecord 计费事实源不删） |

**错误契约**：一律 `{"error": {"code", "message", "detail?"}}`。
错误码（10 个，唯一事实源是 `web/backend/app/core/errors.py` 里各 `AppError` 子类的
`code`）：`bad_request` `unauthorized` `forbidden` `not_found` `rate_limited`
`quota_exceeded` `llm_key_missing` `upstream_error` `internal_error` `admin_disabled`。

**WS 事件**（唯一事实源是 `web/backend/app/websocket/__init__.py::WS_EVENTS`）：
`review.started` `review.progress` `review.persona_completed`
`review.evaluation_completed` `review.completed` `review.failed` `review.cancelled`。
后三个是终态（`WS_TERMINAL_EVENTS`），前端收到任意一个就停止等待。

---

## 6. 数据模型

**既有**：`Review` `PersonaOutput` `EvaluationResult` `EvaluationScorecard` `EthicsReport`

**新增（预埋线）**：

| 表 | 作用 |
|---|---|
| `users` | 身份（匿名形态下不写入） |
| `user_api_keys` | BYOK key（密文 + 掩码，支持轮换与审计） |
| `usage_records` | 用量流水 —— **计费的唯一事实源** |
| `jobs` | 异步任务（换外部队列时前端契约不变） |
| `judgments` | 可证伪的预测 + `predicted_at` 时间戳 |
| `outcomes` | 对预测的事后验证（hit/miss/partial/unknown） |
| `platform_settings` | 后台面板的运行时配置覆盖（键值对，DB 优先于 env 默认值；套餐字段覆盖也复用这张表，键名前缀 `plan_override:`） |
| `cdk_codes` | 兑换码（credits/max_uses/expires_at/批次号；停用是标记不删除） |
| `cdk_redemptions` | 兑换记录（(code_id, user_id) 唯一——同人同码只能兑一次） |
| `credit_ledger` | 评审次数流水（+发放/-消耗，余额=求和；与 UsageRecord 同哲学：事实源是只增流水） |
| `admin_audit_log` | 管理员操作审计流水（谁在何时改了哪个配置/套餐/平台 Key，只增不改） |

`Review` 新增 `user_id`（归属）与 `error_message`（失败原因）。
`Review.wide_screen`（两层评审开关，见 §4.5）与复合索引
`ix_reviews_user_project (user_id, project_key)` —— 项目记忆的查询走这两列，
且发生在评审创建的同步路径上，单列索引各查一次再回表不够。
`user_api_keys` 复用保留 user_id `__platform__` 存放后台设置的平台级 server key。
`ledger_service.hit_rate` / `persona_leaderboard` 的 `user_id` 参数可传 `None`
跳过按用户过滤，供后台面板做跨用户聚合视角（产品侧调用永远传具体 user_id，行为不变）。

### 6.1 `report_json` 里这批工作新增的键

| 键 | 产出方 | 说明 |
|---|---|---|
| `evidence_profile` | aggregator（纯规则） | 证据构成记账，阈值随报告落库（§4.6） |
| `dimension_scores` | aggregator（纯规则） | 逐维度均分 + min/max，**无加权综合分** |
| `abstentions` | cli（证据预检） | 弃权人格 + 原因 + 缺哪些证据类型。弃权 ≠ 失败：
  失败是跑了没跑成（`degradation`），弃权是"材料里没有我需要的证据类型，按规矩不硬评" |
| `triage` | cli（两层评审 L1） | 全包初筛记录：谁晋级/为什么、谁落选说了什么、失败几个（§4.5） |

`artifact_bundle.project_memory` 不是报告键而是**入参**记录（评审开始前就决定了带哪些
历史），所以它挂在 bundle 上而不是 report 里——报告页取它也是从 `review` 而非 `report`。

> **四种报告形态必须说同样的话**：网页版 / Markdown 导出 / 引擎 HTML / 分享页
> （`/s/:token`）。绝大多数人是把 `.md` 发给同事的——账目只在网页版出现等于账目
> 只对本人公开。分享页尤其重要：收链接的人没有任何上下文，最需要知道"这是哪一档、
> 结论建立在什么证据之上"。分享页**复用** ReportPage 导出的组件而非复制一份，
> 不再产生新的漂移面。

---

## 7. 测试

| 范围 | 位置 | 覆盖什么 |
|---|---|---|
| 核心引擎 | `tests/` | 流水线各阶段、争议提取、聚合、校准、伦理、消融、benchmark，以及 `test_llm_client.py` 的多服务商/多模态出口 |
| 平台链路 | `web/backend/tests/` | 认证与会话、配额与计费、CDK 与两种配额模式、后台管理、报告分级、多服务商 BYOK、图片上传、判断留档、E2E 冒烟 |

**这里刻意不写条数。** 本文件一度在三处各写一个互相矛盾的数字（分层总览里 394、
本节两行里 267 与 173），任何人按其中一个去核对都会以为项目在虚报。
判据只有一条：`python -m pytest tests/ -q` 与
`(cd web/backend && python -m pytest tests/ -q)` 各自退出码为 0。

平台链路里包含一组 **E2E 冒烟测试**（`test_e2e_chain.py`）：用假引擎替换 LLM，
证明"发起 → 队列 → 报告落库 → 判断留档 → 记账"整条链真的闭环，
以及 simulated 结果永远进不了正式数据（负向测试）。

平台测试逐条验证：健康开关不泄密、匿名身份、JWT/口令/密钥加解密、
BYOK 四种解析路径、**无 key 必须 428 且不返回模拟数据**、意图解析四档、
上传校验、**BYOK 不计配额 / 服务端 key 计配额 / 配额关着也记账**、
限流令牌桶、任务生命周期与失败记录、判断复利全流程（留档→回填→命中率→越权拦截）、
错误契约与请求 ID、**打开认证不影响匿名可用性**、**报告按登录态分级裁剪**、
**通用任务类型不会被误判进游戏向人格包**（`test_general_consumer_pack.py` 专门覆盖了
一次真实踩过的关键词歧义回归）。
