# TLS 部署补全方案（HTTPS 上线）

> 审计对象：`docs/project/release-plan.md` 审计表中「HTTPS/TLS 🔴 缺失」一项。
> 结论先行：**该审计结论已过时** —— Caddy 反代方案（方案 B 的推荐路线）在仓库里已落地大半：
> `web/docker-compose.prod.yml`、`web/deploy/Caddyfile`、`.env.production.example` 的
> `FRONTEND_BIND` / `SITE_DOMAIN` 均已就位。剩余工作主要是**补 3 个硬化缺口（HSTS 头、
> Caddy healthcheck、上线冒烟验证）+ 填真实域名 + 按检查清单验证**，而不是从零搭 TLS。
>
> 本文档假设部署形态为 release-plan 第 34 行确定的**方案 B：单台 VPS + docker compose 全栈上线**。
> 所有域名以 `app.example.com` 占位，上线时替换为真实域名（本文不涉及具体域名决策，
> 该决策在 release-plan「待用户决策」中）。

---

## 1. 现状缺口清单

### 1.1 审计表陈述与仓库现状的出入（先纠正）

| # | release-plan 陈述 | 仓库现状（2026-08 核对） | 结论 |
|---|---|---|---|
| 1 | 「HTTPS/TLS 🔴 缺失：nginx 只监听 80，`server_name localhost`，无证书方案」（`docs/project/release-plan.md:11`） | Caddy 方案已落地：`web/docker-compose.prod.yml`（caddy 服务 + 80/443 + caddy-data/config 卷）、`web/deploy/Caddyfile`（`{$SITE_DOMAIN}` → `reverse_proxy frontend:80`）、`web/.env.production.example:57-67` 已补 `FRONTEND_BIND=127.0.0.1:8080` 与 `SITE_DOMAIN`。内层 nginx 仍监听 80（`web/frontend/nginx.conf:2`、`web/admin/nginx.conf:2`），但这在「Caddy 终结 TLS → 转发内层 80」的架构下是设计使然 | **已过时**，应更新为「🟡 半就绪：配置齐备、未上线验证」 |
| 2 | 「CI/CD 🔴 缺失：`.github/` 只有 issue 模板，无 workflows」（`docs/project/release-plan.md:17`） | `.github/workflows/ci.yml` 已存在，含 5 个作业：skill-consistency / core-engine / backend / backend-postgres / frontend（frontend+admin 矩阵构建，admin 跑 vitest） | **已过时**。CI 测试链齐备，但 release-plan P2 的「构建镜像 → 推 registry → 服务器一键更新 → 冒烟脚本」（第 51-53 行）**未落地** |

### 1.2 真实存在的 HTTPS/TLS 相关缺口（按严重度排序）

| # | 缺口 | 位置 | 说明 |
|---|---|---|---|
| G1 | **无 HSTS 响应头** | `web/backend/app/main.py:71-80`（SecurityHeadersMiddleware 只设了 X-Content-Type-Options / X-Frame-Options / Referrer-Policy / Permissions-Policy，无 `Strict-Transport-Security`）；`web/deploy/Caddyfile:3-6`（未加 header 指令） | Caddy 默认也不发 HSTS。缺 HSTS = 首次访问后的「强制 HTTPS」只存在于浏览器当前标签页，用户手动敲 `http://` 域名仍会先走明文再被 308 |
| G2 | **Caddy 服务无 healthcheck** | `web/docker-compose.prod.yml:6-19` | backend 有 healthcheck（`docker-compose.yml:63-68`），caddy 只有 `restart: unless-stopped`。Caddy 挂了（如证书/配置损坏）时 `compose ps` 仍显示 up |
| G3 | **无自动化的 HTTPS 上线验证** | `.github/workflows/ci.yml`（无部署作业）；release-plan P2-11（`/api/health` + 首页 200 冒烟）未实现 | 上线后证书是否真的签下来、80→443 是否真的跳转，目前只能靠人肉 curl |
| G4 | **证书签发的外部硬依赖** | `web/.env.production.example:66-67`（「必须已解析到本机公网 IP，否则签发失败」）；`web/docker-compose.prod.yml:8-9`（Caddy 绑定宿主 80/443） | ① `SITE_DOMAIN` 必须已解析到公网 IP（ACME HTTP-01 需要）；② 宿主 80/443 必须空闲可绑定。任一不满足即签不下来。这是**配置易错点**而非代码缺口 |
| G5 | **CORS / 邮件链接必须用 `https://` 前缀** | `web/.env.production.example:8`（`AL_CORS_ORIGINS`）、`:48`（`AL_PUBLIC_WEB_URL`）、`:45`（`AL_MAIL_FROM`） | 若误填 `http://app.example.com`：Caddy 会把 http 308 到 https，浏览器实际请求 Origin 是 `https://...`，不在 CORS 白名单 → 前端跨域失败，且报错不明显。后端 `AL_CORS_ORIGINS` 读取实现见 `web/backend/app/config.py:129-135` |
| G6 | **内层 nginx 无 TLS 能力、`server_name localhost`** | `web/frontend/nginx.conf:2-3`、`web/admin/nginx.conf:2-3` | 架构上由 Caddy 终结 TLS，内层 80 只对容器网络/回环开放，**本身不是必须改的缺口**。但含义要写明：任何人绕过 Caddy 直连 `127.0.0.1:8080`（frontend 绑定）得到的是明文；`server_name localhost` 因是唯一 server 块兜底，不影响 Caddy 转发（Host 透传后仍命中）。可选项：改为 `server_name _;` 更规范，非必需 |
| G7 | **登录态存 localStorage 而非 cookie** | `web/frontend/src/lib/apiClient.ts:46-51`（token 读写 `localStorage`） | 后端无 `set_cookie`（全仓库搜不到），所以「cookie Secure 标志」检查项**不适用**。但 HTTPS 仍是必需前提：明文 HTTP 下 token 会被中间人直接截获。另：localStorage 对 XSS 开放，后端中间件也未设 `Content-Security-Policy` —— 属可选加固项，不在本次 TLS 范围内 |

> 补充事实（非缺口）：后端类生产自检已在 `web/backend/app/config.py:280-308` 实现 ——
> CORS/站点地址指向公网主机即按生产对待，`AL_JWT_SECRET` 为默认值时拒绝启动。
> 这对应 release-plan P0-3 的 fail-fast，已落地。

---

## 2. 两种方案对比

| 维度 | 方案 A：Caddy 最外层反代 | 方案 B：nginx + certbot |
|---|---|---|
| 配置量 | **最小**。一个 Caddyfile 站点块（现有 `web/deploy/Caddyfile` 共 4 行）；无证书路径、无续期 cron、无 443 server 块 | 大。需新增 nginx 443 `server` 块（ssl_certificate、ssl_protocols 等）+ certbot 初次签发 + 续期定时任务（systemd timer / cron）+ 续期后 reload hook |
| 自动续期 | **内置**。Caddy 自动 ACME，约 60 天检查一次；证书存 `caddy-data` 命名卷，重启容器不丢 | 手动。certbot renew 需定时任务 + `nginx -s reload` hook，漏配即到期 500 |
| 多域名支持 | 加一个站点块即可（同一 Caddyfile 堆 `{$SITE_DOMAIN2} { ... }`）；通配符需 DNS 插件，非必需 | 每个域名一套 443 配置 + certbot 按域名签发，重复劳动 |
| 与现有 compose 整合难度 | **低**。已有现成叠加层 `web/docker-compose.prod.yml`（`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`），Caddy 端口映射与数据卷已写好 | 中高。内层 frontend nginx 已占容器 80，certbot 方案要么再叠一层宿主 nginx、要么改 frontend 镜像塞证书与 443 配置 —— 都要动现有镜像/配置 |
| 当前仓库已落地程度 | **~90%**：compose 叠加层、Caddyfile、`.env` 模板三项均已存在 | 0%：仓库内无任何 nginx ssl 配置、无 certbot 引用 |

**结论：方案 A（Caddy）**。与 release-plan 第 46 行「TLS：Caddy 作为最外层反代（自动 Let's Encrypt，配置量最小）」一致，且大部分代码已在仓库中，无需引入新依赖。

---

## 3. 推荐方案的实施步骤（Caddy）

### 3.0 前置条件（必须先满足，否则证书签不下来）

1. 域名已注册，A 记录解析到 VPS 公网 IP，**待部署前提前解析**（TTL 生效后再跑 Caddy）。
2. VPS 安全组/云防火墙放行 **TCP 80 和 443**（国内云还要注意：**443 公网入方向**经常默认不放行，需显式开）。
3. 宿主 80/443 空闲（`ss -ltnp | grep -E ':(80|443)'` 无输出；VPS 上若有 nginx/apache 先停掉）。
4. 国内 VPS 需先完成 ICP 备案（release-plan「待用户决策」未决，本文不展开；备案未完成前 HTTPS 部署无法面向公众）。

### 3.1 `.env` 接线清单（`cp web/.env.production.example web/.env` 后逐项填）

```dotenv
# ---- 域名与端口（TLS 叠加层必改）----
SITE_DOMAIN=app.example.com              # 替换为真实域名；必须已解析到公网 IP
FRONTEND_BIND=127.0.0.1:8080             # 让出公网 80/443 给 Caddy，前端只监听回环

# ---- 生产身份（全部 https:// 前缀）----
AL_ENV=production
AL_CORS_ORIGINS=https://app.example.com  # 与浏览器实际访问的域名完全一致，勿用 http://
AL_PUBLIC_WEB_URL=https://app.example.com
AL_MAIL_FROM=AudienceLens <noreply@app.example.com>

# ---- 密钥（openssl rand -hex 32，两个必须不同）----
AL_JWT_SECRET=
AL_ENCRYPTION_KEY=
AL_ADMIN_TOKEN=
```

> 环境变量接线说明：backend 全部 `AL_*` 已由 `web/docker-compose.yml:28-62` 从 `.env` 注入
> （`docker compose` 自动读取同目录 `.env`），无需再改 compose。`SITE_DOMAIN` 由
> `web/docker-compose.prod.yml:16` 注入 Caddy，`FRONTEND_BIND` 由 `docker-compose.yml:78` 控制
> frontend 宿主端口。`AL_PUBLIC_WEB_URL` 决定邮件里验证/重置链接的落点（`web/backend/app/config.py:214-216`），
> 配错用户点开邮件链接是打不开的页面。

### 3.2 Caddyfile 内容示例

现有 `web/deploy/Caddyfile`（4 行，已可用）：

```caddyfile
# 域名从 web/.env 的 SITE_DOMAIN 注入；Caddy 自动申请并续期证书。
# WebSocket（/ws/）Caddy 原生透传，无需额外配置。
{$SITE_DOMAIN} {
    reverse_proxy frontend:80
    encode gzip zstd
}
```

建议的**最小硬化增强**（新增一行 HSTS 头，其余不动）：

```caddyfile
{$SITE_DOMAIN} {
    reverse_proxy frontend:80
    encode gzip zstd
    # 强制 HTTPS 的记忆期。首次上线建议先用小值观察（如 max-age=300），
    # 确认跳转/证书稳定后再调大到 31536000（一年）。设大后浏览器不再回退 http。
    header Strict-Transport-Security "max-age=31536000"
}
```

说明：
- `http://` → `https://` 的 308 跳转是 **Caddy 默认行为**，不需要写配置。
- `/api/`、`/ws/` 不需要在 Caddyfile 显式列 route —— 全部流量反代给 frontend nginx，
  nginx 内部按 `location` 分发（`web/frontend/nginx.conf:12-29`）。
- `server_name` 用 `{$SITE_DOMAIN}` 占位注入，**不要**在 Caddyfile 里写死域名。

### 3.3 compose 启动命令与可选 healthcheck 补丁

```bash
cd web
cp .env.production.example .env   # 逐项填写（见 3.1）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps   # 三服务 + caddy 均应 healthy
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f caddy   # 观察 ACME 签发日志
```

**可选硬化**：给 caddy 服务补 healthcheck（当前 `web/docker-compose.prod.yml:6-19` 没有）。
示例（文档仅供参考，实施时改 `docker-compose.prod.yml`）：

```yaml
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    environment:
      - SITE_DOMAIN=${SITE_DOMAIN:-localhost}
    healthcheck:
      # Caddy 管理 API 默认监听容器内 localhost:2019，返回 200 即健康。
      # 不要用 wget 打 http://localhost/ —— 会被 308 到 https，busybox wget 对自签会报错。
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:2019/config/"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

> backend 与 frontend 的 healthcheck 已具备（`web/docker-compose.yml:63-68`；frontend 为 nginx 镜像默认），
> caddy 是唯一缺口。

### 3.4 上线验证命令（G3 的人工版，先于自动化冒烟落地）

```bash
# 1) 证书真实签发（非自签 fallback）
echo | openssl s_client -connect app.example.com:443 -servername app.example.com 2>/dev/null \
  | openssl x509 -noout -issuer -dates
#    issuer 应为 Let's Encrypt / ZeroSSL（而非 Caddy 内部 CA），enddate 为 90 天内到期日

# 2) HTTP → HTTPS 跳转
curl -sI http://app.example.com | head -1     # 期望: HTTP/1.1 308 Permanent Redirect 且 Location: https://...

# 3) HSTS 头（若按 3.2 加了 header 指令）
curl -sI https://app.example.com | grep -i strict-transport

# 4) 健康与同源 API
curl -s https://app.example.com/api/health | head -c 200

# 5) CORS 白名单回显
curl -s -D - -o /dev/null -H "Origin: https://app.example.com" https://app.example.com/api/health \
  | grep -i access-control-allow-origin
```

---

## 4. 上线前检查清单

| # | 检查项 | 判定标准 | 若失败 |
|---|---|---|---|
| C1 | DNS 解析 | `dig +short app.example.com` = VPS 公网 IP（提前 TTL 生效） | 等 TTL；临时改 hosts 只对本机有效，ACME 仍会失败 |
| C2 | 端口占用 | `ss -ltnp` 中 80/443 无其他进程监听 | 停掉占用服务再 `compose up` |
| C3 | 证书签发 | 见 3.4 第 1 条：issuer 非内部 CA | 看 `docker compose logs caddy`；见 §5 风险 |
| C4 | CORS 白名单 | `AL_CORS_ORIGINS` 只含 `https://app.example.com`（`web/.env.production.example:8`），且 curl Origin 回显正确（3.4 第 5 条） | 改 `.env` 后 `compose up -d` 重建 backend |
| C5 | 登录态传输安全 | 确认登录态走 localStorage（`web/frontend/src/lib/apiClient.ts:46-51`）而非 cookie —— 因此**无 cookie Secure/SameSite 检查项**；HTTPS 全链路是 token 不被中间人截获的前提 | 若未来引入 cookie 会话，须补 Secure + SameSite=Lax |
| C6 | HSTS | `curl -sI https://...` 返回 `Strict-Transport-Security` 头；首次上线建议 max-age=300，稳定后调 31536000（3.2） | 补 Caddyfile header 行 |
| C7 | HTTP→HTTPS 跳转 | `curl -sI http://...` 返回 308（Caddy 默认） | 检查 Caddy 站点块是否绑定正确（`{$SITE_DOMAIN}` 环境变量注入） |
| C8 | 证书续期机制 | 证书在 `caddy-data` 命名卷（`docker-compose.prod.yml:12-13`），**不要**用 bind mount 存证书但也不要在重启时删卷；`docker compose down` 不影响 caddy-data | 若曾 `docker volume rm`，证书丢失后 Caddy 会自动重新签发，属正常恢复流程 |
| C9 | 邮件链接落点 | `AL_PUBLIC_WEB_URL=https://app.example.com`（非 localhost） | 改 `.env` 重建；后端启动自检会在类生产下告警（`web/backend/app/config.py:360-364`） |
| C10 | admin 面板隔离 | admin 仍只绑 `127.0.0.1:5200`（`web/docker-compose.yml:90`），不暴露公网 443；远程走 SSH 隧道 | 若曾改成公网端口立即回退 |

---

## 5. 风险与回滚

### 5.1 证书签发失败

- **症状**：`docker compose logs caddy` 出现 `ACME ... error` / `no route to host` 等。
- **行为说明**：Caddy **不会**因 ACME 失败而拒绝启动 —— 它会退回内部自签证书继续提供 HTTPS
  并在后台重试。所以故障表现是「浏览器证书告警」而非「网站打不开」，容易掩盖问题；**必须**看日志确认签发成功（3.4 第 1 条）。
- **常见原因与处置**：
  - DNS 未解析 / 解析未生效 → 等 TTL 或修正 A 记录后，Caddy 重试会自动成功；
  - 80 端口被占（ACME HTTP-01 需要 80）→ 释放 80 后重启 caddy（`docker compose restart caddy`）；
  - 云安全组未放行 80 出/入方向 → 在云控制台放行；
  - 域名已备案/审核问题（国内 VPS）→ 属 release-plan「待用户决策」，不在 TLS 层可解。

### 5.2 80/443 端口被占

- 排查：`ss -ltnp | grep -E ':(80|443)'`，找到占用进程（VPS 上常见的 nginx/apache/宝塔面板）。
- 处置：停用/改绑占用服务；**不要**给 Caddy 换端口凑合 —— HTTP-01 challenge 只认 80，
  换端口 = 证书永远签不下来。

### 5.3 DNS 未就绪时的 fallback（三种，按安全程度排序）

| 场景 | 做法 | 说明 |
|---|---|---|
| DNS 已解析、想先验证 compose 全链路 | `SITE_DOMAIN=app.example.com` 照常配置，接受浏览器自签告警临时访问 | 最接近生产；注意这期间是**自签证书**，不要对外宣传 |
| 完全不想暴露公网（纯本机/内网联调） | `SITE_DOMAIN=localhost`（compose.prod.yml 默认值） | Caddy 对 localhost 走内部 CA 自签，不触发 ACME，服务可跑，浏览器会告警 |
| 域名/备案未就绪但必须公网演示 | **临时裸跑**：`.env` 设 `FRONTEND_BIND=80`（回到 `docker-compose.yml:78` 默认），只 `docker compose up -d` 不加 prod 叠加层 | 纯 HTTP 明文，**必须**：① 后端密钥/白名单照常配齐（类生产自检仍生效）；② 防火墙只对白名单来源 IP 放行；③ 演示完立即切回 Caddy 或关停。这只能作为过渡，不能作为上线形态 |

### 5.4 回滚步骤（任一环节失败）

```bash
cd web
# 回到无 TLS 的裸跑形态：撤掉 prod 叠加层，frontend 重新直接占 80
# 1) 改 .env：FRONTEND_BIND=80（或删掉该行）
# 2) 移除叠加层重建
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose -f docker-compose.yml up -d --build
```

> 回滚代价说明：Caddy 数据卷（证书）保留，将来重新 `compose -f ... -f docker-compose.prod.yml up`
> 时 Caddy 检测到证书仍有效则**不会重新触发 ACME 限额**。因此回滚是安全的、可反复的。

### 5.5 其他注意

- **Let's Encrypt 速率限制**：每域名每周 5 张重复证书。反复「签发失败 → 改配置 → 重签」一般不会撞限，
  但不要在未解析的域名上反复尝试。
- **WS 安全性**：`/ws/` 经 Caddy 透传后同样走 WSS（`wss://`），前端同源调用不受影响；
  后端 WS origin 校验复用 `AL_CORS_ORIGINS`（`.env.production.example:7` 注释），白名单写对即可。
- **国内访问**：海外 VPS 免备案但国内访问偏慢；国内 VPS 需备案 —— 该决策见 release-plan「待用户决策」，
  决定后只需改 `SITE_DOMAIN` 一处。

---

## 附：本文档未覆盖（属其他工作项，不在此展开）

- release-plan P2 的 CI/CD 发布流水线（构建镜像 → 推 registry → 一键更新）与自动化冒烟脚本 ——
  建议在 TLS 验证通过后按 `ci.yml` 现有结构追加部署作业。
- `AL_ENCRYPTION_KEY` 与 `AL_JWT_SECRET` 分离（release-plan P0-4）—— compose 已透传
  `AL_ENCRYPTION_KEY`（`docker-compose.yml:34`），只需在 `.env` 填独立值。
- admin 面板的 basic-auth 加固（release-plan P1-5）—— 与 TLS 无直接关系。
