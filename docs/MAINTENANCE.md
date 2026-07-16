# AudienceLens 运维手册

> 架构与链路设计看 [ARCHITECTURE.md](ARCHITECTURE.md)。本文只讲**怎么跑、怎么改、出事怎么办**。

## 目录

1. [本地起服务](#1-本地起服务)
2. [环境变量全表](#2-环境变量全表)
3. [两种形态的切换](#3-两种形态的切换)
4. [常见维护任务](#4-常见维护任务)
5. [部署](#5-部署)
6. [数据库迁移](#6-数据库迁移)
7. [故障排查](#7-故障排查)
8. [安全清单](#8-安全清单)

---

## 1. 本地起服务

```bash
# 后端
cd web/backend
pip install -r requirements.txt
python run.py                      # → http://localhost:8000
                                   #   接口文档 http://localhost:8000/docs

# 前端（另开一个终端）
cd web/frontend
npm install
npm run dev                        # → http://localhost:5173
```

**验证链路通了**：

```bash
curl http://localhost:8000/api/health
# 应返回当前生效的开关；server_key_present 是布尔，绝不会回显密钥明文
```

打开 <http://localhost:5173/ask>（对话式入口）。BYOK 模式下未填 key 会引导你去设置页——
这是**故意的**：评审必须用真实模型，模拟数据没有评审价值。

**跑测试**：

```bash
python -m pytest tests/ -q                      # 核心引擎 232 项
cd web/backend && python -m pytest tests/ -q    # 平台链路 37 项
cd web/frontend && npx tsc --noEmit             # 前端类型检查
```

---

## 2. 环境变量全表

所有开关的唯一来源是 [`web/backend/app/config.py`](../web/backend/app/config.py)。

### 基础

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_ENV` | `development` | `production` 时自动关 debug |
| `AL_DEBUG` | 非 production 为 true | 错误响应里是否带 detail |
| `AL_CORS_ORIGINS` | `localhost:5173,localhost:3000` | 逗号分隔；**同时用于 WS origin 白名单** |
| `AL_DATABASE_URL` | `sqlite:///data/reviews.db` | 换 Postgres 直接改这里 |

### 身份认证

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_AUTH_ENABLED` | `false` | false = 全匿名（开源单机形态） |
| `AL_JWT_SECRET` | `dev-insecure-...` | **生产必须改**；同时用于加密用户 key |
| `AL_JWT_TTL_SECONDS` | `604800`（7天） | 令牌有效期 |

> ⚠️ `AL_JWT_SECRET` 同时是**用户 API Key 的加密主密钥**。改它会导致已存的
> 用户 key 解密失败（系统会当作"无 key"让用户重填，不会崩）。轮换前请通知用户。

### LLM Key 策略

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_KEY_MODE` | `byok` | `byok`（用户自带）/ `managed`（你的 key）/ `hybrid`（先用户后你） |
| `ANTHROPIC_API_KEY` | 空 | 服务端 key；`managed`/`hybrid` 下必填 |

### 配额与限流

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_QUOTA_ENABLED` | `false` | **注意：关着也照常记账**，随时可开始计费 |
| `AL_QUOTA_FREE_REVIEWS_PER_DAY` | `5` | 仅约束走服务端 key 的评审 |
| `AL_QUOTA_FREE_COST_USD_PER_DAY` | `1.0` | 同上 |
| `AL_RATELIMIT_ENABLED` | `true` | |
| `AL_RATELIMIT_PER_MINUTE` | `60` | 通用接口 |
| `AL_RATELIMIT_REVIEW_PER_HOUR` | `20` | 评审接口 |

### 队列与并发

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_QUEUE_BACKEND` | `inprocess` | `external` 需自行接入（见 §4.4） |
| `AL_QUEUE_WORKERS` | `2` | 同时跑几个评审任务 |
| `AUDIENCELENS_MAX_CONCURRENCY` | `6` | **单次评审内部的人格并发度**（CLI 也读这个） |

> 总并发 ≈ `AL_QUEUE_WORKERS × AUDIENCELENS_MAX_CONCURRENCY`。
> 默认 2×6=12 个并发 LLM 调用。调高前请确认你的 API 速率限制扛得住。

### 其他

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_UPLOAD_MAX_BYTES` | `10485760`（10MB） | |
| `AL_UPLOAD_ALLOWED_EXT` | `.txt,.md,.json,.yaml,.yml` | |
| `AL_INTENT_LLM_ENABLED` | `true` | 关掉则意图解析只用启发式（零成本） |
| `AL_LEDGER_ENABLED` | `true` | 关掉则不记录判断（不建议——这是护城河） |
| `AL_ADMIN_TOKEN` | 空（后台面板关闭） | 设置后 `/admin` 与 `/api/admin/*` 生效，见 §2.5 |

### 后台管理面板

访问 `http://localhost:5173/admin`（页脚"管理后台"链接，故意不放进顶部导航）。

1. 设置 `AL_ADMIN_TOKEN`（任意强随机字符串）并重启后端——未设置时面板显示"未启用"，
   接口整体返回 503，这是安全默认值，绝不无密钥暴露管理接口。
2. 面板输入同一个 token 解锁（`X-Admin-Token` 请求头，与普通用户的 Bearer JWT
   完全独立，存在单独的 localStorage 键 `al.admin_token`）。
3. 面板提供四块能力：
   - **系统概览**：跨用户聚合的评审/用量/判断留档/任务队列统计（不是某个 user_id 的切片）
   - **运行时配置**：`quota_enabled`、`ratelimit_*`、`key_mode`、`review_concurrency`
     等白名单项，改了立即生效、**不需要重启进程**——落在新表 `platform_settings`，
     DB 覆盖值优先于环境变量默认值；"重置"按钮清除覆盖、回落 env 默认值
   - **平台级 API Key**：托管/混合模式下服务端垫付的 key，复用 `UserApiKey` 表
     （保留 user_id `__platform__`），此设置优先于环境变量 `ANTHROPIC_API_KEY`
   - **任务 / 评审巡检**：最近任务与评审的只读列表，按状态筛选

只有白名单里的键可被后台面板调整（见 `app/services/admin_settings_service.py`
的 `ADJUSTABLE` 字典）——`jwt_secret`、`database_url`、`cors_origins` 这类需要
重启才能安全生效的基础设施配置，不放进这里，面板也不会显示可编辑项。

---

## 3. 两种形态的切换

### 形态 A：开源单机（默认，零成本）

用户自己跑、自己填 key。**你不部署、不垫钱、不用做计费。**

```bash
# 什么都不用配，默认就是这个形态
python run.py
```

### 形态 B：托管 SaaS

用户打开网址就能用。**你要部署、要垫算力钱、必须开配额。**

```bash
export AL_ENV=production
export AL_DEBUG=false
export AL_JWT_SECRET="$(openssl rand -hex 32)"     # 必须改！
export AL_CORS_ORIGINS="https://your-domain.com"

export AL_AUTH_ENABLED=true                        # 开登录
export AL_KEY_MODE=hybrid                          # 用户有 key 用他的，否则用你的
export ANTHROPIC_API_KEY="sk-ant-..."              # 你垫钱的那个 key

export AL_QUOTA_ENABLED=true                       # 必须开！否则用户越多你亏越多
export AL_QUOTA_FREE_REVIEWS_PER_DAY=3

export AL_DATABASE_URL="postgresql://user:pass@host/db"
export AL_QUEUE_WORKERS=4
```

> **强烈建议先用 `AL_KEY_MODE=byok` 上线**：用户填自己的 key，你不垫算力钱、
> 不用做计费系统。等用户量证明值得，再切 `hybrid` + 开配额。

### 成本参考（一次 Standard 评审，4–6 人格 + 交叉质询）

| 模型 | 单次成本 |
|---|---|
| Haiku | ~$0.05 – 0.30 |
| Sonnet | ~$0.30 – 1.50 |

**这是"算力成本"的全部——不需要 GPU。** 系统本身只调 API；
唯一的本地模型是语义去重用的 bge-small（CPU，毫秒级，可忽略）。

---

## 4. 常见维护任务

### 4.1 加一个新的评审任务类型

1. `src/runner/cli.py` → `VALID_TASK_TYPES` 加一项
2. `src/presets/panel-presets.yaml` → 加对应的人格面板预设
3. `web/backend/app/services/intent_service.py` → `VALID_TASK_TYPES` + `TASK_KEYWORDS`（让对话入口认得它）
4. `web/frontend/src/lib/types.ts` → `TaskType` 联合类型
5. `web/frontend/src/pages/AskPage.tsx` → `TASK_LABELS` 加中文名

> 这 5 处不同步会导致：CLI 能跑但 Web 报"未知任务类型"，或对话入口永远识别不出它。

### 4.2 加一个新的人格包

1. 放 `src/personas/<name>.yaml`（照抄现有格式，跑 `audiencelens personas-validate` 校验）
2. `web/backend/app/services/intent_service.py` → `PACK_KEYWORDS` 加关键词
3. `web/frontend/src/lib/types.ts` → `PersonaPack` 联合类型
4. `src/mcp_tools.py` → `PERSONA_PACKS`（让 AI 助手也能用）

### 4.3 换加密实现（生产建议）

`core/security.py` 的 `encrypt_secret`/`decrypt_secret` 是 HMAC 派生 + XOR 的简化实现，
足以避免"数据库被看一眼就泄露明文"，但**不是标准 AEAD**。生产环境请换：

```python
pip install cryptography

from cryptography.fernet import Fernet
def encrypt_secret(plaintext: str, secret: str) -> str:
    return Fernet(derive_fernet_key(secret)).encrypt(plaintext.encode()).decode()
```

只需替换这两个函数，**调用方（key_service）无感**。
换之前存量密文需要迁移（读旧格式 → 写新格式的一次性脚本）。

### 4.4 换外部队列（多副本部署时必须）

内存线程池只在单进程内有效。多副本部署时任务会丢。

1. 实现 `services/job_service.py` 里的 `JobBackend` 协议（`submit` / `cancel`）
2. 在 `get_backend()` 里返回你的实现
3. `AL_QUEUE_BACKEND=external`

`Job` 表已落库、WS 事件契约不变，**前端不用改一行**。

### 4.5 换 Redis 限流（多副本部署时必须）

内存令牌桶同样只在单进程内有效。实现 `core/ratelimit.py` 的同名接口
（`allow(key, limit, window) -> bool`），在 `get_limiter()` 返回即可，
调用方（`deps.rate_limit`）无感。

### 4.6 接入真实计费

1. ~~`quota_service.check_quota` → 按 `user.plan` 查套餐额度~~ **已完成**：
   `check_quota(db, user_id, key_source, plan=identity.plan)` 按 `plan_service` 的套餐限额校验
2. `quota_service.record_usage` 末尾 → 推送计量事件到 Stripe/自建计费
   （代码里已标好接入点注释）

历史用量在 `usage_records` 表里**早就攒着了**——这就是"配额关着也记账"的价值。

### 4.7 调整套餐

套餐矩阵在 [`web/backend/app/services/plan_service.py`](../web/backend/app/services/plan_service.py)
的 `PLANS` 字典里，当前三档：free / pro($19) / team($49)。

- **加档位**：往 `PLANS` 加一个条目即可，`GET /api/plans` 与配额校验自动生效
- **free 档的限额仍从环境变量读**（`AL_QUOTA_FREE_REVIEWS_PER_DAY` / `AL_QUOTA_FREE_COST_USD_PER_DAY`），
  这是有意的——单机形态下不用改代码就能调；pro/team 是代码里的固定值
- **未知 plan 一律回落 free**（防御：数据库里出现脏 plan 值时不至于放开限额）
- 用户的档位在 `users.plan` 字段；改档 = 更新该字段（未来接 Stripe webhook 时在此落点）
- BYOK 用户**始终不受套餐限额约束**——他们花自己的钱

---

## 5. 部署

```bash
cd web
docker-compose up -d          # 前端 Nginx + 后端 Uvicorn
```

**生产检查清单**：

- [ ] `AL_JWT_SECRET` 已改成随机值（`openssl rand -hex 32`）
- [ ] `AL_DEBUG=false`（否则错误响应会带内部细节）
- [ ] `AL_CORS_ORIGINS` 只列真实域名（它同时是 WS origin 白名单）
- [ ] 若 `AL_KEY_MODE` 不是 `byok` → **必须** `AL_QUOTA_ENABLED=true`
- [ ] 数据库不是 SQLite（多副本会锁死）
- [ ] 多副本 → 已换外部队列 + Redis 限流（见 §4.4 / §4.5）
- [ ] `data/` 目录（SQLite + 上传文件）已挂载持久卷

---

## 6. 数据库迁移

当前用 `Base.metadata.create_all()`（只新增缺失的表，不改已有表结构）
+ `db.py::_legacy_migrations()` 里的手写 ALTER。

**加新表**：定义 ORM 模型即可，重启自动建。

**改已有表的列**：`create_all` **不会**帮你改。要么在 `_legacy_migrations()` 里加一条
幂等的 ALTER，要么上 Alembic：

```bash
pip install alembic
alembic init migrations
# 在 migrations/env.py 里 target_metadata = app.models.Base.metadata
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

生产环境**建议直接上 Alembic**，手写 ALTER 只适合早期。

---

## 7. 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| 前端报 428 / 要求填 Key | BYOK 模式下没 key | **这是预期行为**。去设置页填 key，或切 `AL_KEY_MODE=managed` |
| 评审卡在 pending | 队列 worker 没起来 | 看日志 `job ... failed`；确认 `AL_QUEUE_WORKERS>0` |
| 评审 failed，报"模拟模式" | key 无效或没传进去 | 这是**安全网**：宁可失败也不返回无价值的假数据。检查 key 是否有效 |
| WS 连不上，进度不动 | origin 不在白名单 | 配 `AL_CORS_ORIGINS`。前端会自动回落轮询，不影响拿结果 |
| 429 太频繁 | 限流 | 调 `AL_RATELIMIT_*`；多副本部署请换 Redis |
| 402 配额超限 | 走服务端 key 且超额 | 让用户填自己的 key（BYOK 不受配额约束） |
| 用户 key 突然失效 | `AL_JWT_SECRET` 被改过 | 密文解不开会当"无 key"，让用户重填即可 |
| 评审很慢 | 并发度太低 | 调 `AUDIENCELENS_MAX_CONCURRENCY`（默认 6） |
| 进度条不动但评审能完成 | WS 被拦（origin 不在白名单） | 检查 `AL_CORS_ORIGINS`；前端会自动回落 2s 轮询，功能不受影响 |
| 402 提示"XX 套餐限 N 次" | 套餐限额（走服务端 key） | 升级 `users.plan` 或让用户填 BYOK key（不受限）；档位定义见 §4.7 |

**排查任何线上问题的第一步**：拿到用户报障时的 `X-Request-Id`（响应头里），
在日志里 grep 它——一次请求的全链路都串在这个 ID 上。

---

## 8. 安全清单

已经做了的：

- 用户 API Key **密文落库**，接口只回显掩码（`sk-ant-...4f2a`），明文只进不出
- 口令 PBKDF2-HMAC-SHA256（20 万轮）
- JWT 签名校验 + 过期检查
- WS origin 白名单（防跨站 WebSocket 劫持）
- 安全响应头（`X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy`）
- 上传白名单（扩展名 + 大小 + 强制 UTF-8）
- 越权防护：查别人的评审/判断一律返回 404（**不泄露资源是否存在**）
- `/api/health` 只暴露 `server_key_present` 布尔，**绝不回显密钥**
- 后台管理面板默认关闭（未设 `AL_ADMIN_TOKEN` 时 503），令牌比较用
  `hmac.compare_digest` 恒定时间比较，平台级 key 同样密文落库、只回显掩码

上生产前还要做的：

- [ ] 换标准 AEAD 加密（§4.3）
- [ ] `AL_JWT_SECRET` 用密钥管理服务，别写进 `.env` 提交
- [ ] HTTPS（WS 会自动跟着升级为 wss）
- [ ] 接入 Sentry 或等价物（`core/logging.py` 已留好接入点）
- [ ] `AL_ADMIN_TOKEN` 同样用密钥管理服务；后台面板建议只对内网/VPN 开放
