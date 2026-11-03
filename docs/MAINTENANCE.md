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
9. [`mcp-admin-server/`](#9-mcp-admin-server本地运维用的-mcp-工具不随产品部署)
10. [已知待办](#10-已知待办记录在案尚未实现)

---

## 1. 本地起服务

> **后端推荐用 supervisor 脚本起**：`bash scripts/backend-supervisor.sh`。
> 崩溃自动重启、日志统一写到 `logs/backend.log`（目录不存在会自动建），排查时直接 grep 即可。
>
> 脚本此前放在 `logs/` 下，而 `/logs/` 整个目录在 `.gitignore` 里——
> 也就是说 fresh clone 里根本没有这个文件，照文档敲那行命令只会得到
> "No such file or directory"。脚本是源码（该入库），日志是产物（该忽略），
> 两者混在一个目录里必然出这种事，所以脚本移到了 `scripts/`。
>
> ⚠️ 这是**开发辅助脚本**，**不是**部署入口——生产部署看 §5（`web/docker-compose.prod.yml`），
> 不要把 supervisor 搬到容器里，更不要拿它代替进程管理器。

```bash
# 后端（推荐：supervisor 脚本，自动重启 + 日志落到 logs/backend.log）
bash scripts/backend-supervisor.sh

# 后端（手动：需要看前台输出或自己接进程管理器时）
cd web/backend
pip install -r requirements.txt
python run.py                      # → http://localhost:8001（与 vite 代理目标一致）
                                   #   接口文档 http://localhost:8001/docs

# 用户产品前端（另开一个终端）
cd web/frontend
npm install
npm run dev -- --port 5199         # → http://localhost:5199

# 后台管理（独立项目，需要才起，不随产品前端一起跑；另开一个终端）
cd web/admin
npm install
npm run dev                        # → http://localhost:5200（需先设 AL_ADMIN_TOKEN）
```

**验证链路通了**：

```bash
curl http://localhost:8001/api/health
# 应返回当前生效的开关；server_key_present 是布尔，绝不会回显密钥明文
```

打开 <http://localhost:5199/ask>（对话式入口）。BYOK 模式下未填 key 会引导你去设置页——
这是**故意的**：评审必须用真实模型，模拟数据没有评审价值。

**跑测试**：

```bash
python -m pytest tests/ -q                      # 核心引擎
cd web/backend && python -m pytest tests/ -q    # 平台链路
cd web/frontend && npm run typecheck            # 用户产品前端类型检查（= tsc -b）
#   注意别写成 npx tsc --noEmit：根 tsconfig 是 "files": [] + project references，
#   --noEmit 检查的是空集，对任何错误都返回成功——看起来像"类型干净"，其实什么都没查。
cd web/admin && npx tsc -b                      # 后台管理前端类型检查
```

**这里不写具体条数，以上面命令的实际输出为准。** 曾经写过「核心引擎 1648 passed」，
而同一天实测是 1649——测试数每加一条就过期一次，而且没有任何东西会提醒。
仓库里同一个数字一度有四个互相矛盾的版本（CI 步骤名、README 徽章、本文件、落地页），
任何人按其中一个去核对都会认为项目在虚报。宁可不写。

---

## 2. 环境变量全表

所有开关的唯一来源是 [`web/backend/app/config.py`](../web/backend/app/config.py)。

> 这张表以前漏掉了整个邮件段与 `AL_ENCRYPTION_KEY`——恰好是两处**配不对就直接拒绝启动**的开关，
> 于是"照着全表配完却起不来"。`tests/test_public_claims.py::test_maintenance_env_table_is_complete`
> 现在会拿 `config.py` 里读到的变量名逐个比对本节，漏一个就测试失败。

### 基础

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_ENV` | `development` | `production` 时自动关 debug |
| `AL_DEBUG` | 非 production 为 true | 错误响应里是否带 detail |
| `AL_CORS_ORIGINS` | `localhost:5173,localhost:3000` | 逗号分隔；**同时用于 WS origin 白名单** |
| `AL_DATABASE_URL` | `sqlite:///data/reviews.db` | 换 Postgres 直接改这里 |
| `AL_SKIP_DOTENV` | 空 | 设任意非空值则不加载 `web/.env`（CI / 容器里想完全靠显式环境变量时用） |

### 身份认证

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_AUTH_ENABLED` | `false` | false = `/auth/register`\`/login` 关闭；true = 开放注册登录 |
| `AL_JWT_SECRET` | `dev-insecure-...` | **生产必须改**；只用于签发登录态，**不参与任何加密** |
| `AL_JWT_TTL_SECONDS` | `604800`（7天） | 令牌有效期 |
| `AL_GUEST_COOKIE_NAME` | `al_guest` | 未登录访客游客身份 cookie 的名字（认证开启时，第一次请求即铸造，见下方「游客身份」） |
| `AL_GUEST_COOKIE_SECURE` | 类生产 → `true`，否则 `false` | cookie 的 Secure 标记；只有纯 http 本机调试才该关 |
| `AL_GUEST_COOKIE_TTL_SECONDS` | `2592000`（30天） | 游客 cookie / 游客令牌有效期；过期后该浏览器会拿到一个新游客 |
| `AL_GUEST_IDENTITY_PER_HOUR` | `30` | 每个来源每小时最多新建的游客身份数；超了 429，不会回落共享 anonymous 桶 |
| `AL_ENCRYPTION_KEY` | 空 → 回落 `DEV_ENCRYPTION_KEY`（一个**独立的**开发默认值） | **落库 API Key 的加密主密钥**；类生产下仍是默认值会**拒绝启动** |

> ⚠️ 这两个密钥**从来不共用**。不设 `AL_ENCRYPTION_KEY` 时回落的是 `config.py` 里
> 那个独立的 `DEV_ENCRYPTION_KEY` 常量（`config.py:162`），**不是** `AL_JWT_SECRET`——
> JWT 密钥不参与加密，所以轮换登录态不会牵连密钥库。
>
> 而且在类生产环境（`AL_ENV=production`，或 CORS / 站点地址指向公网）下，
> 加密密钥仍是开发默认值时 `_validate_startup` 会**直接抛错拒绝启动**
> （`config.py:375`），不会悄悄裸奔着跑起来。
>
> 真正要小心的是：一旦有用户存过 key，就不要再改 `AL_ENCRYPTION_KEY`——
> 改了等于所有已存密文解不开（系统当作"无 key"让用户重填，不会崩，但用户要重配）。

**这不是"全匿名 vs 强制登录"的二选一开关**——打开 `AL_AUTH_ENABLED` 只是让注册/登录
接口可用，评审、Key 管理、意图解析这些路由用的是 `optional_identity`（`app/deps.py`），
不带 token 永远回落匿名，不会 401。这是"体验机会 + 登录看详情"的技术基础：
匿名用户随时能试用评审功能，登录只是解锁个人归属和完整报告详情（见架构文档 §2.6）——
不是把产品从"开源单机"切换成"必须登录"的托管形态。

### LLM Key 策略

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_KEY_MODE` | `byok` | `byok`（用户自带）/ `managed`（你的 key）/ `hybrid`（先用户后你） |
| `ANTHROPIC_API_KEY` | 空 | 服务端 key（Anthropic 原生档）；`managed`/`hybrid` 下必填 |

**多服务商**：BYOK/平台 key 都不再限定 Anthropic——`provider` 可选 `anthropic` 或
`openai_compatible`（DeepSeek/Kimi/通义千问/智谱GLM/Ollama 等任意兼容 `/chat/completions`
协议的服务），后者需额外填 `model` 和 `api_base`。出口统一走 `src/runner/llm_client.py`：
不依赖 litellm（历史上是 3.8 装不上才手搓的；现已统一 3.11，但两条路径各几十行、且 Prompt Caching / 强制工具调用都直接对着官方参数写，没有理由再垫一层，见模块 docstring），Anthropic 走官方 SDK，
其余走裸 `httpx.post`。`/api/keys/test`、`/api/admin/server-key/test` 测的就是这条真实链路。

**多模态**：`/api/uploads` 对图片扩展名（`.png/.jpg/.jpeg/.webp/.gif`）走独立分支，
转成 `data:` URI 而非抽取文字；评审引擎把图片和文字一起塞进 OpenAI Vision 格式的内容块，
只有 `llm_client.VISION_CAPABLE_PREFIXES` 里的视觉模型才会真正"看"，其余模型静默降级为纯文字。

**CDK 兑换码**：后台面板批量生成（数量/每码次数/可兑人数/有效期/备注），用户在设置页
免登录兑换。匿名兑换（认证开启时）自动签发游客身份——真实 User 行 + JWT，次数落到访客
各自头上而不是共享匿名桶；前端把 token 存 localStorage，清缓存即丢（游客形态的固有代价）。
兑换接口限流 10 次/分钟防暴力枚举，且所有不可用状态（不存在/停用/过期/用完）
对外话术统一，不给枚举者可区分信号。次数只对服务端垫付 key 生效（BYOK 本来就不限量）。

**两种配额模式**（`AL_QUOTA_MODE`，后台面板可实时切换）：

| 模式 | 语义 | 适用场景 |
|---|---|---|
| `plan`（默认） | 套餐日限额；CDK 次数在日限用完后垫。成本日上限是硬闸，次数不能绕过 | 有免费额度的 SaaS 形态 |
| `credits` | 纯次数制："一个码 10 次，用完就没了"。每次评审消耗 1 次余额，余额 0 → 402 引导兑换；无每日刷新、无套餐日限 | CDK 发码运营——用户没有免费额度，全靠兑换 |

`credits` 模式下总成本由发码量控制（单次评审有 budget.yaml 的 `max_cost_per_run_usd` 封顶）。
CDK 发码运营的典型部署组合：

```bash
AL_AUTH_ENABLED=true      # 匿名兑换自动签发游客身份的前提
AL_QUOTA_ENABLED=true
AL_QUOTA_MODE=credits
AL_KEY_MODE=managed       # 服务端垫付 key（后台面板填）
```

### 配额与限流

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_QUOTA_ENABLED` | `false` | **注意：关着也照常记账**，随时可开始计费 |
| `AL_QUOTA_MODE` | `plan` | `plan`（套餐日限）/ `credits`（纯 CDK 次数制，用完即止）——见"两种配额模式" |
| `AL_QUOTA_FREE_REVIEWS_PER_DAY` | `5` | 仅约束走服务端 key 的评审 |
| `AL_QUOTA_FREE_COST_USD_PER_DAY` | `1.0` | 同上 |
| `AL_PLAN_PRO_COST_USD_PER_DAY` | `0.63`（≈ $19 / 30） | Pro 档每日平台垫付成本上限的默认值；后台「套餐」可覆盖 |
| `AL_PLAN_TEAM_COST_USD_PER_DAY` | `1.63`（≈ $49 / 30） | Team 档同上 |
| `AL_QUOTA_TOKENS_TOTAL` | `0` | 每账号**累计**能烧掉的平台 token，`0` = 不限。上面两条是 24h 滚动窗口，跨天重置，拦不住"每天用满连用一个月"；这一条不重置。只算平台垫付，BYOK 不受影响 |
| `AL_QUOTA_TOKENS_PER_REVIEW_ESTIMATE` | `150000` | 发起评审时按这个数给终身额度占位，跑完用真实用量顶掉。**它决定并发超额的上界**：没有占位时并发请求会各自读到"没超"而全部放行（实测 8 线程 8/8 全过）。设 `0` = 关闭占位，闸门仍生效但退回逐次检查 |
| `AL_QUOTA_UNVERIFIED_REVIEWS_PER_DAY` | `1` | 未验证邮箱的账号每天能用平台 key 评审几次。软拦：能登录能用，验证邮箱即解锁完整额度。负数 = 关闭本机制 |
| `AL_SKILL_FREE_USES` | `3` | 高级技能的免费体验次数。用完不报错，静默降级成普通评审并如实告知。`0` = 对免费用户完全关闭；负数 = 不限制。BYOK 用户不受限 |
| `AL_PREMIUM_SKILLS` | `red_team_audience` | 哪些技能算"高级"（逗号分隔，取值见 `models.SkillType`）。默认只有红队：它是唯一真正多花钱的那层 |
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

### 邮件（注册验证 / 密码重置）

**开了账号体系就必须配这一段**：`AL_AUTH_ENABLED=true` 且类生产环境下，邮件后端不是 `smtp`
会**直接拒绝启动**（`AL_MAIL_BACKEND=smtp` 但没填 `AL_SMTP_HOST` 同样拒绝启动）。
原因写在 config.py 的自检里：console 档的完整邮件（含令牌）会落到服务器磁盘上的 outbox 文件，
能读该文件的人就能接管任意账号，而用户永远收不到验证/重置链接。

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_MAIL_BACKEND` | `console` | `smtp` 才会真发信；`console` 只写日志与 outbox 文件 |
| `AL_MAIL_FROM` | `AudienceLens <noreply@localhost>` | 保持默认会被服务商拒收（`@localhost`），类生产下告警 |
| `AL_SMTP_HOST` | 空 | `AL_MAIL_BACKEND=smtp` 时必填，否则拒绝启动 |
| `AL_SMTP_PORT` | `587` | 587/25 用 STARTTLS，465 用隐式 SSL；配错组合类生产下告警 |
| `AL_SMTP_USER` | 空 | |
| `AL_SMTP_PASSWORD` | 空 | 别写进任何进版本库的文件（本仓库出过一次） |
| `AL_SMTP_USE_SSL` | `false` | 465 端口必须设 `true`，587/25 必须留 `false` |
| `AL_SMTP_TIMEOUT_SECONDS` | `15.0` | 不设超时 = socket 全局默认（通常永不超时），一台连不上的 SMTP 能把工作线程永久挂住 |
| `AL_MAIL_OUTBOX_DIR` | `web/backend/data/outbox` | `console` 档的本地投递目录（0600 文件，含令牌） |
| `AL_PUBLIC_WEB_URL` | `http://localhost:5199` | 邮件里链接的落点；**同时参与"是否像生产环境"的判定** |
| `AL_EMAIL_TOKEN_TTL_SECONDS` | `86400`（24h） | 邮箱验证令牌有效期 |
| `AL_RESET_TOKEN_TTL_SECONDS` | `3600`（1h） | 密码重置令牌有效期 |

#### QQ 登录（QQ 互联 OAuth2.0）

三项**必须配齐**才会启用；缺任何一项 `qq_login_enabled` 为 false，前端连按钮都不画
（不做"按钮在但点了必然失败"）。

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_QQ_APP_ID` | 空（功能关闭） | QQ 互联后台的 APP ID |
| `AL_QQ_APP_KEY` | 空（功能关闭） | QQ 互联后台的 APP KEY。**密钥，只走环境变量，不要写进任何配置文件或仓库** |
| `AL_QQ_REDIRECT_URI` | 空（功能关闭） | 回调地址，必须与 QQ 互联后台登记的**逐字符一致** |

回调地址填 `https://<你的域名>/api/auth/qq/callback` —— 必须走 `/api/` 前缀（nginx 只把
这个前缀转发给后端），且必须具体到路径。腾讯自 2015 年起不接受只填根域名的回调，
填错的表现是授权时报 `redirect uri is illegal(100010)`；差一个尾斜杠、协议不同都算错。
主域与 www 两个版本都要用的话，在后台用分号隔开填两条。


### 危险默认值的逃生舱

两个都是"明知故犯"开关：类生产环境下不设就**拒绝启动**，设了则放行并持续告警。
留逃生舱是因为单人自建、内网试跑确实可能就是要这么跑，但必须是一次显式动作。

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_ALLOW_SHARED_ANONYMOUS` | `false` | 允许类生产下 `AL_AUTH_ENABLED=false`——所有访客共用 anonymous 身份，彼此可见对方的评审、用量与 API Key |
| `AL_ALLOW_CONSOLE_MAIL` | `false` | 允许类生产 + 开了账号体系时不真发邮件——用户激活不了、找不回密码 |

### 其他

| 变量 | 默认 | 说明 |
|---|---|---|
| `AL_UPLOAD_DIR` | `{backend_dir}/data/uploads` | 上传图片的落盘目录。**Docker 下必须在挂载卷内**，否则容器一重建，用户对话里的图全变 404（数据库记录还在，字节没了）。清理孤儿文件见下方说明 |
| `AL_UPLOAD_MAX_BYTES` | `10485760`（10MB） | 文本类材料上限 |
| `AL_UPLOAD_ALLOWED_EXT` | `.txt,.md,.json,.yaml,.yml` | 这是"抽取成文字材料"的格式白名单 |
| `AL_UPLOAD_ALLOWED_IMAGE_EXT` | `.png,.jpg,.jpeg,.webp,.gif` | 图片走独立分支：原样转 data URI 进多模态请求，不抽文字 |
| `AL_UPLOAD_MAX_IMAGE_BYTES` | `8388608`（8MB） | 图片单独的大小上限 |

> **清理孤儿上传文件**：`web/backend/scripts/cleanup_orphan_uploads.py`，
> 默认只报告，加 `--apply` 才真删。
>
> Docker 下直接在容器里跑（镜像已 `COPY scripts/ ./scripts/`）：
>
> ```bash
> docker compose exec backend python scripts/cleanup_orphan_uploads.py          # 先看报告
> docker compose exec backend python scripts/cleanup_orphan_uploads.py --apply  # 确认后再删
> ```
>
> 裸机部署（DEPLOY-BAREMETAL.md）仓库整棵树都在机器上，直接
> `cd /opt/audiencelens/web/backend && .venv/bin/python scripts/cleanup_orphan_uploads.py`。
| `AL_INTENT_LLM_ENABLED` | `true` | 关掉则意图解析只用启发式（零成本） |
| `AL_INTENT_MODEL` | `claude-haiku-4-5-20251001` | 意图解析用的模型 |
| `AL_LEDGER_ENABLED` | `true` | 关掉则不记录判断（不建议——这是护城河） |
| `AL_ADMIN_TOKEN` | 空（后台面板关闭） | 设置后 `web/admin` 与 `/api/admin/*` 生效，见 §2.5；含非 ASCII 或短于 16 字符会拒绝启动 |

### 后台管理面板（独立应用，不嵌在用户产品里）

后台管理是 **`web/admin/` 下一个完全独立的前端项目**——自己的 `package.json`、
自己的端口（5200）、自己的构建产物，不和用户产品前端（`web/frontend`，5199）
打包在一起、不共享路由。两者只是同一个后端（8000）的两个不同消费者，
可以分开部署到不同域名（比如把 admin 只挂内网/VPN，产品前端挂公网）。

```bash
cd web/admin
npm install
npm run dev          # http://localhost:5200
```

1. 设置 `AL_ADMIN_TOKEN`（任意强随机字符串）并重启后端——未设置时面板显示"未启用"，
   接口整体返回 503，这是安全默认值，绝不无密钥暴露管理接口。
2. 面板输入同一个 token 解锁（`X-Admin-Token` 请求头，独立的 localStorage 键
   `al_admin.token`，与用户产品前端的登录态毫无关系）。
3. 面板提供以下能力：
   - **系统概览**：跨用户聚合的评审/用量/判断留档/任务队列统计（不是某个 user_id 的切片），
     附一张近 N 天评审量/状态分布/成本的趋势图（无第三方图表库，纯 SVG，够用即可）
   - **判断复利（全局）**：`ledger_service.hit_rate`/`persona_leaderboard` 传 `user_id=None`
     跨全体用户聚合的命中率与人格排行——产品的护城河指标第一次能在后台看到全局视角
   - **运行时配置**：`quota_enabled`、`ratelimit_*`、`key_mode`、`review_concurrency`
     等白名单项，改了立即生效、**不需要重启进程**——落在表 `platform_settings`，
     DB 覆盖值优先于环境变量默认值；"重置"按钮清除覆盖、回落 env 默认值
   - **平台级 API Key**：托管/混合模式下服务端垫付的 key，复用 `UserApiKey` 表
     （保留 user_id `__platform__`），此设置优先于环境变量 `ANTHROPIC_API_KEY`
   - **套餐（可编辑）**：pro/team 的月价与每日额度可在面板直接改，同样落
     `platform_settings`（键名前缀 `plan_override:`）、改动立即生效、可逐字段重置；
     free 档的额度沿用 `quota_free_*` 配置项，这里不重复放开，避免两套覆盖机制打架
   - **用户管理**：注册用户列表（带评审数/累计成本聚合）、按邮箱搜索、改套餐、
     停用/启用——停用立即生效（登录被拒、已有 token 失效），全部写入审计日志
   - **统计分析**：任务类型分布（完成/失败分段条形图）、人格包使用量、
     成本构成（BYOK vs 平台垫付占比 + 消耗 Top 用户）
   - **操作审计**：谁在何时改了哪个配置/套餐/平台 Key/用户（`admin_audit_log` 表，只增不改）。
     **具名账号已经可用**，审计行里记的是真实用户名而不再只是"某个拿着令牌的人"：
     - 账号管理走 `/api/admin/auth/users`（列表 / 新建 / 停用），登录后签发一个
       12 小时的会话令牌，前端之后用它代替静态令牌。会话令牌用 `AL_ADMIN_TOKEN`
       **本身**做签名密钥（不是 `AL_JWT_SECRET`）——后台与产品侧用户会话是两个
       完全独立的信任根，令牌互相不能串用；轮换或清空 `AL_ADMIN_TOKEN` 会让所有
       已登录的具名会话一起失效，这是期望行为。
     - `AL_ADMIN_TOKEN` 静态主密钥**仍然有效**，但它现在的定位是
       **bootstrap 与逃生舱**：第一个管理员账号得靠它建出来，账号体系出问题时
       也得靠它进去修。用主密钥操作时审计行的 actor 记成 `static-token`——
       那本身就是一条要记下来的事实（这次操作没有具名账号可追责），不是"未知"。
     - 因此运营上的建议是：上线后立刻用主密钥建具名账号，此后日常操作一律用账号登录，
       主密钥收进密钥管理服务（见 §8 清单）。新建/停用管理员账号本身也写审计日志。
   - **任务 / 评审巡检**：支持按 `status`/`user_id`/时间范围过滤 + 分页的列表，
     点击一行可下钻查看完整详情（含 `payload`/`report_json` 等原始数据）；
     评审可从详情抽屉删除（二次确认 + 审计，计费流水不随评审删除）

只有白名单里的键可被后台面板调整（见 `app/services/admin_settings_service.py`
的 `ADJUSTABLE` 字典，套餐字段见 `plan_service.OVERRIDABLE_PLAN_FIELDS`）——
`jwt_secret`、`database_url`、`cors_origins` 这类需要重启才能安全生效的基础设施
配置，不放进这里，面板也不会显示可编辑项。

**生产部署**：`web/admin` 构建后是纯静态文件（`npm run build` → `dist/`），
和用户产品前端一样丢进任意静态托管；不同的是它不需要暴露在公网——建议只挂
内网、VPN 或加一层反向代理的 IP 白名单。`vite.config.ts` 的开发代理只在
`npm run dev` 时生效，生产环境需要后端的 `AL_CORS_ORIGINS` 里加上 admin
应用实际部署的域名，否则浏览器会因跨域拦截请求。

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

1. `src/runner/task_types.py` → `VALID_TASK_TYPES` 加一项。**这是唯一事实源**：
   `src/runner/cli.py` 和后端的 `intent_service` 都从这里导入，不再各存一份
   （以前各存一份的直接后果是 CLI 认 6 种、README 说 10 种，谁都没错谁都对不上）
2. `src/presets/panel-presets.yaml` → 加对应的人格面板预设
3. `web/backend/app/services/intent_service.py` → 只需要补 `TASK_KEYWORDS`
   （`VALID_TASK_TYPES` 是 `from runner.task_types import ...` 来的，不用动）；
   关键词是人工维护的，不补就是对话入口永远识别不出这个任务类型
4. `web/frontend/src/lib/types.ts` → `TaskType` 联合类型
5. `web/frontend/src/pages/AskPage.tsx` → `TASK_LABELS_ZH_FOR_ENGINE` 加一项
   （这张表是**给引擎看的中文名**，不是 UI 文案；用户看到的标签在 i18n 资源里）

> 这几处不同步会导致：CLI 能跑但 Web 报"未知任务类型"，或对话入口永远识别不出它。

### 4.2 加一个新的人格包

1. 放 `src/personas/<name>.yaml`（照抄现有格式，跑 `audiencelens personas-validate` 校验）
2. `web/backend/app/services/intent_service.py` → `PACK_KEYWORDS` 加关键词
3. `web/frontend/src/lib/types.ts` → `PersonaPack` 联合类型
4. `src/mcp_tools.py` → `PERSONA_PACKS`（让 AI 助手也能用）

### 4.3 落库加密：已是标准 AEAD（✅ 已完成，此处只记迁移口径）

`core/security.py` 的 `encrypt_secret` 现在写的是 **v2 格式：`cryptography.fernet`**
（AES-128-CBC + HMAC-SHA256 认证加密），密钥用 PBKDF2-HMAC-SHA256（10 万轮，
盐 `audiencelens-key-encryption-v2`）从 `AL_ENCRYPTION_KEY` 派生。
密文带 `v2$` 前缀。自研密码学已经不在写入路径上。

**v1 → v2 的迁移是惰性的，不需要停机批处理：**

- v1（HMAC 派生密钥流 XOR 的自实现封装）**只读保留**。`decrypt_secret` 认前缀，
  没有 `v2$` 的按 v1 解——存量用户完全无感，不会因为换算法就要重填 key。
- 升级发生在"用一次"的时候：`key_service.resolve_key` 解开一条 v1 密文后，
  用 `is_legacy_ciphertext` 判断并就地用 v2 重新写回（`key_service.py:166-170`）。
  也就是说每个用户下次真正发起评审时，他那条 key 自动升级一条。
- 所以**不存在**"迁移脚本跑完之前系统不可用"的窗口，也不存在只跑了一半的中间态。

为什么当初非换不可：v1 的问题不是"能被直接解开"，而是自研密码学本身不该出现在
生产路径上——分组模式、填充、侧信道都没有人审过。

> 还想再进一步的话，下一步是把密钥交给 KMS/密钥管理服务而不是 `.env`（见 §8 清单），
> 那是密钥**保管**问题，与这里的加密算法是两件事。

### 4.3.5 服务商预设保鲜（定期做）

`OPENAI_COMPATIBLE_PRESETS` 里每个服务商的默认模型名，三处各存一份手抄副本，改的时候三处都要动：

1. `src/runner/llm_client.py`（Python 核心引擎，唯一真正参与请求的一份）
2. `web/frontend/src/lib/types.ts`（用户 BYOK 设置页下拉预设）
3. `web/admin/src/lib/types.ts`（后台平台 Key 面板下拉预设）

这些默认值只是"填个能用的起点"，不是强制——用户/管理员随时能手改模型名。但服务商换代很快
（2026-07 一次核实就发现 DeepSeek 三天后硬下线旧模型名、Kimi legacy 系列已停新用户注册、
智谱刚发新旗舰），建议每季度用 WebSearch 核实一遍各服务商最新文档，三处同步更新。

> 顺带：`VISION_CAPABLE_PREFIXES`（同文件）决定哪些模型会真正"看"图片素材，新模型系列
> 发布时也要检查是否需要把前缀加进去，否则该模型明明支持视觉能力，评审时却被静默降级成纯文字。

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
cp .env.production.example .env   # 不能省：compose 里两个必填项用了 ${VAR:?}
# 编辑 .env：至少填 AL_CORS_ORIGINS 与 AL_JWT_SECRET
docker compose up -d              # 前端 Nginx + 后端 Uvicorn + 后台面板
```

`docker-compose.yml` 把 `AL_CORS_ORIGINS` 与 `AL_JWT_SECRET` 声明成
`${VAR:?...}`，没有 `.env` 时 compose 在**解析阶段**就报错退出——刻意如此，
免得起一个不限 CORS、会话密钥可猜的栈。代价是 fresh clone 直接 `up` 必然失败，
所以那行 `cp` 是步骤的一部分，不是可选项。
命令一律用 `docker compose`（v2，Docker CLI 插件）；独立二进制 `docker-compose`（v1）
已停止维护，两者对 `${VAR:?}` 与 profiles 的行为并不一致。

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

**数据迁移：隔离 legacy 共享匿名桶**（游客身份 cookie 上线后跑一次）——
`web/backend/scripts/quarantine_anonymous.py`，默认只预览、`--apply` 才执行、可重复跑。
它把 `user_id="anonymous"`（以及内容表里 `user_id IS NULL`）的行改挂到
`quarantine:legacy-anonymous`，不删任何数据。逻辑在 `app/services/guest_service.py`
末尾一节，部署时的命令见 `web/DEPLOY.md`「升级到游客身份 cookie 版本后」。

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
| 用户 key 突然失效 | **`AL_ENCRYPTION_KEY`** 被改过（不是 `AL_JWT_SECRET`——它不参与加密） | 密文解不开会当"无 key"，让用户重填即可。换回原值即可恢复；换不回就只能让用户重填 |
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

- [x] 换标准 AEAD 加密（§4.3）—— 已完成：写入走 Fernet（v2），v1 存量密文只读兼容并在下次使用时自动升级
- [ ] `AL_JWT_SECRET` 用密钥管理服务，别写进 `.env` 提交
- [ ] HTTPS（WS 会自动跟着升级为 wss）
- [ ] 接入 Sentry 或等价物（`core/logging.py` 已留好接入点）
- [ ] `AL_ADMIN_TOKEN` 同样用密钥管理服务；后台面板建议只对内网/VPN 开放

---

## 9. `mcp-admin-server/`（本地运维用的 MCP 工具，不随产品部署）

仓库根目录下有一个 `mcp-admin-server/`，此前任何文档都没提过它——于是它既
没人维护，也没人知道能不能删。写在这里备案：

**它是什么**：一个本地 MCP server（`mcp-admin-server/server.py`），把
`/api/admin/*` 的常用操作包装成 MCP 工具，让 Claude Code / Cursor 这类客户端
能直接查概览、发 CDK、看审计日志，不用手工 curl 拼 `X-Admin-Token`。

**它不是什么**：不是产品的一部分。源码（`server.py` / `README.md` /
`requirements.txt`）已入库，这样换台机器还能拿到；但它**不参与 CI**，
**不进部署包**（`scripts/make_deploy_package.py` 的 INCLUDE 里没有它），
`docker-compose.yml` 也不认识它。`venv/` 仍然忽略，每台机器自己建。

**安全边界**：它拿着 `AL_ADMIN_TOKEN`，等于后台的全部权限。所以：

- 只在本机跑，不要监听外部地址；
- `mcp-admin-server/venv/` 已加进 `.gitignore`；
- 里面的 `admin_request` 是个"任意后台路径"逃生舱，路径前缀校验已收紧为
  只接受 `/admin` 或 `/admin/...`（此前 `startswith("/admin")` 会连
  `/administrator-elsewhere` 一起放行），并且会拒绝含 `..` 的路径。
  即便如此，它仍是权限最大的一个工具——不要把它暴露给不受信的会话。

---

## 10. 已知待办（记录在案，尚未实现）

- **定期清理空的过期游客行。** 游客身份 cookie 上线后（见 `deps.resolve_guest_identity`），
  每个新浏览器会话都会在 `users` 表里留一行 `is_guest=True` 的记录，其中大多数从未产生任何
  数据（爬虫、只看了一眼首页的访客）。需要一个定期任务：删除"游客 cookie 已过期
  （`AL_GUEST_COOKIE_TTL_SECONDS`）且名下没有任何评审 / 对话 / 项目 / 上传 / CDK 流水"的
  游客行。注意不能动有数据的游客——那是别人还没认领的历史。
