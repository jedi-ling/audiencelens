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
                    │  pages/AskPage        对话式入口（大白话 → 意图解析 → 开庭）  │
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
                                    │  复用（已过 232 项测试的引擎）
                    ┌───────────────┴──────────────────────────────────────────────┐
                    │  src/runner/   面板选择 → 证据预检 → 人格并发评审 → 三层校验  │
                    │                → 交叉质询 → 聚合 → 校准                       │
                    │  src/harness/  8 维质量评估 / 刻板印象检测 / 消融实验          │
                    └──────────────────────────────────────────────────────────────┘
```

---

## 2. 一次评审的完整链路

```
POST /api/v2/reviews
  │
  ├─ 1. rate_limit("review")        默认 20 次/小时（AL_RATELIMIT_*）
  ├─ 2. current_identity            默认匿名；AL_AUTH_ENABLED=true 后要 Bearer token
  ├─ 3. resolve_llm_key             BYOK / managed / hybrid，无 key → 428
  │                                 ↑ 绝不返回模拟数据，这是产品底线
  ├─ 4. check_quota                 BYOK 不限；服务端 key 才受配额约束
  │
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
  ├─ 安全网：若 result.simulated == true → 直接丢弃并报错（不让假数据入库）
  ├─ 落库 report + persona_outputs
  ├─ ledger.record_judgments()             ← 预测盖时间戳留档（护城河）
  ├─ quota.record_usage()                  ← 记账（即使配额没开也记）
  └─ WS: review.completed
```

> 并发下 `review.progress` 可能乱序到达（done=3 先于 done=2），前端取 max 处理。

**前端**：`POST` 后拿 `review_id` → `connectReviewSocket()` 订阅进度 → 终态跳报告页。
WS 连不上时自动回落轮询 `GET /api/v2/reviews/{id}`。

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
| **判断复利** | 启用 | 预测留档、回填验证、命中率、人格排行 | 默认即用 |
| **结构化错误** | 启用 | 9 种错误码、统一 `{error:{code,message}}` | 新错误继承 `AppError` |
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

一次性评审工具跑完就断了，经验不沉淀。这一层把每条**可证伪的预测**盖时间戳留档，
真人测试回来回填 Outcome。于是系统能回答"P14 的判断历史上准不准"。

我们的验证来源是**真实用户测试**——干净的 ground truth，不像股价那样掺运气噪音。

**诚实原则写进代码**：样本 < 10 时 `low_confidence=true` 且 `note` 明说"不具统计意义"，
UI 必须显示。绝不用 3 个样本吹准确率。

---

## 5. API 契约速查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 探活 + 当前生效开关（绝不泄露密钥） |
| GET | `/api/auth/me` | 当前身份（匿名形态返回 `is_anonymous:true`） |
| POST | `/api/auth/register` `/login` | 认证关闭时返回 400 |
| GET/POST/DELETE | `/api/keys` | BYOK key（仅掩码回显，明文只进不出） |
| POST | `/api/intent/parse` | 大白话 → 评审参数（`method` 字段声明用了哪档） |
| POST | `/api/uploads` | 上传材料，返回文本 |
| GET | `/api/usage` | 24h 用量与配额（含当前套餐限额） |
| GET | `/api/plans` | 套餐矩阵 free/pro/team（公开，纯静态定价数据） |
| **POST** | **`/api/v2/reviews`** | **发起评审（202，异步）** |
| GET | `/api/v2/reviews/{id}` | 评审详情/报告 |
| GET | `/api/jobs/{id}` | 任务状态与进度 |
| GET | `/api/ledger/judgments` | 历史预测（`only_unverified=true` 即待回填工作台） |
| POST | `/api/ledger/judgments/{id}/verify` | 回填真实结果 |
| GET | `/api/ledger/hit-rate` | 命中率（带 `low_confidence` 诚实标注） |
| GET | `/api/ledger/leaderboard` | 人格命中率排行 |
| WS | `/ws/review/{id}` | 进度推送 |
| GET | `/api/admin/overview` | 跨用户系统概览（需 `X-Admin-Token`，见 §8） |
| GET/PUT/DELETE | `/api/admin/settings[/{key}]` | 运行时配置覆盖，改动无需重启 |
| GET/PUT/DELETE | `/api/admin/server-key` | 平台级 API Key（托管/混合模式垫付用） |
| GET | `/api/admin/jobs` `/reviews` | 任务/评审巡检（只读，按状态筛选） |

**错误契约**：一律 `{"error": {"code", "message", "detail?"}}`。
错误码：`bad_request` `unauthorized` `forbidden` `not_found` `rate_limited`
`quota_exceeded` `llm_key_missing` `upstream_error` `internal_error` `admin_disabled`。

**WS 事件**：`review.started` `review.progress` `review.persona_completed`
`review.completed` `review.failed`。

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
| `platform_settings` | 后台面板的运行时配置覆盖（键值对，DB 优先于 env 默认值） |

`Review` 新增 `user_id`（归属）与 `error_message`（失败原因）。
`user_api_keys` 复用保留 user_id `__platform__` 存放后台设置的平台级 server key。

---

## 7. 测试

| 范围 | 位置 | 数量 |
|---|---|---|
| 核心引擎 | `tests/` | 251 |
| 平台链路 | `web/backend/tests/` | 74 |

平台链路里包含一组 **E2E 冒烟测试**（`test_e2e_chain.py`）：用假引擎替换 LLM，
证明"发起 → 队列 → 报告落库 → 判断留档 → 记账"整条链真的闭环，
以及 simulated 结果永远进不了正式数据（负向测试）。

平台测试逐条验证：健康开关不泄密、匿名身份、JWT/口令/密钥加解密、
BYOK 四种解析路径、**无 key 必须 428 且不返回模拟数据**、意图解析四档、
上传校验、**BYOK 不计配额 / 服务端 key 计配额 / 配额关着也记账**、
限流令牌桶、任务生命周期与失败记录、判断复利全流程（留档→回填→命中率→越权拦截）、
错误契约与请求 ID。
