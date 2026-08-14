# 一页纸部署手册（v1.0 · 国内服务器 + 已备案域名 + hybrid 形态）

前提：服务器装好 Docker（含 compose 插件），域名 A 记录已指向服务器 IP。

> **不想装 Docker？** 看 [`DEPLOY-BAREMETAL.md`](DEPLOY-BAREMETAL.md)——
> systemd + nginx + certbot 的裸机部署方案，适合机器上已经有 nginx、
> 或者不打算引入容器运行时的情况。两份手册的配置项（`web/.env`）完全通用。

## 首次部署

```bash
git clone <你的仓库地址> audiencelens && cd audiencelens/web

# 1. 生产配置
cp .env.production.example .env
# 编辑 .env：
#   AL_JWT_SECRET / AL_ENCRYPTION_KEY / AL_ADMIN_TOKEN 各生成一个：openssl rand -hex 32
#   AL_CORS_ORIGINS=https://你的域名
#   SITE_DOMAIN=你的域名            ← Caddy 用它申请 HTTPS 证书
#   FRONTEND_BIND=127.0.0.1:8080    ← 让出 80/443 给 Caddy
#   ANTHROPIC_API_KEY=平台垫付 key（也可稍后在后台面板配）
#   邮件那一段（AL_SMTP_*）      ← 不配用户收不到激活/重置邮件，见下方「邮件发送」

# 2. 起全栈（backend + frontend + admin + Caddy 自动 HTTPS）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 3. 冒烟
curl -s https://你的域名/api/health   # 应返回 JSON 且 env=production

# 4. 装自动备份（这一步之前只是文档里提一句"建议挂 cron"，没人真的装——
#    数据库单点无备份。跑一次即可，幂等，改 schedule 重跑会覆盖旧的）
chmod +x deploy/install-backup-cron.sh
./deploy/install-backup-cron.sh   # 默认每天 04:00；改时间：BACKUP_CRON_SCHEDULE="0 */6 * * *" ./deploy/install-backup-cron.sh
```

## 后台管理面板

admin 只绑服务器本机 `127.0.0.1:5200`，公网访问不到。本地用 SSH 隧道：

```bash
ssh -L 5200:127.0.0.1:5200 你的服务器
# 浏览器打开 http://localhost:5200 ，登录令牌填 .env 里的 AL_ADMIN_TOKEN
```

上线后第一件事：在后台「平台 Key」面板配好垫付 key 并点"测试"，然后生成第一批 CDK 码。

## 邮件发送

**不配这一段，用户收不到任何邮件**：注册后激活不了、密码忘了找不回。
而且这个故障是静默的——注册接口照样返回成功，后端不报错，只有用户那边什么都没有。

后端说的是标准 SMTP（隐式 SSL 或 STARTTLS 二选一）。任何提供 SMTP 的邮箱服务商
都能接，但**本仓库没有对接过任何一家具体服务商、没有做过端到端验证**，
所以这里不列服务商名单也不写"已支持 X"，只说明你要去拿哪几个参数。

### 你需要准备的 5 个值

| .env 变量 | 是什么 | 去哪拿 |
|---|---|---|
| `AL_SMTP_HOST` | SMTP 服务器主机名 | 服务商帮助页的「SMTP 设置」。是它给的主机名，不是你的网站域名 |
| `AL_SMTP_PORT` + `AL_SMTP_USE_SSL` | 端口与加密方式，**必须成对** | 465 → `true`（隐式 SSL）；587 或 25 → `false`（STARTTLS） |
| `AL_SMTP_USER` | 登录账号 | 通常就是你的发信邮箱地址 |
| `AL_SMTP_PASSWORD` | 登录凭据 | 多数服务商要的是**授权码 / 应用专用密码**，在邮箱网页端「设置 → 账户 → SMTP 服务」里单独申请，**不是**网页登录密码 |
| `AL_MAIL_FROM` | 发件人 | 地址部分要与 `AL_SMTP_USER` 一致，或属于已在服务商处验证的域名。留默认的 `@localhost` 必被拒 |

外加一个 `AL_PUBLIC_WEB_URL=https://你的域名` —— 邮件里链接的落点。
配错它邮件能发出，但用户点开是打不开的页面。

### 配完怎么自测（必做）

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build backend
ssh -L 5200:127.0.0.1:5200 你的服务器   # 后台只绑本机，走隧道
```

浏览器开 `http://localhost:5200` → 左侧「运行时配置」→「邮件发送」面板：

1. 状态区确认 **后端 = smtp → 实际 smtp**。若显示"实际 console"，说明 `AL_SMTP_HOST` 是空的。
2. 填一个你能立刻打开的邮箱，点「发送测试邮件」。**这个按钮会真的发信。**
3. 收到 = 通了。没收到先翻垃圾箱；面板报错的话按提示改（错误信息里已经写明改哪个变量）。

常见失败与对应动作：

- `SMTP 认证失败` → `AL_SMTP_PASSWORD` 填成了网页登录密码，改用授权码
- `发件人地址被拒` → `AL_MAIL_FROM` 与 `AL_SMTP_USER` 不是同一个地址 / 域名未验证
- `TLS 握手失败` 或 `连接被服务器中断` → 端口与 `AL_SMTP_USE_SSL` 配反了（465↔true，587↔false）
- `连接超时` → 多半是 25 端口被云厂商封了，或安全组没放行出网，换 465/587

### 暂时不接邮件服务商

开了账号体系（`AL_AUTH_ENABLED=true`，本模板的默认形态）时必须显式声明，
否则后端**拒绝启动**（这是故意的）：

```
AL_ALLOW_CONSOLE_MAIL=true
```

代价：邮箱验证与密码重置完全不可用；含令牌的完整邮件会写进容器内
`/app/data/outbox/`（0600 文件，`backend-data` 卷）。能读该目录 = 能接管任意账号，
请按等同于账号权限的级别保护它，并定期清理。

## 日常运维

```bash
# 更新发布（拉代码重建）
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 看日志
docker compose logs -f backend

# 手动备份（自动备份由 install-backup-cron.sh 装的 crontab 定时跑）
./deploy/backup.sh

# 恢复演练：把最新备份恢复到临时库校验后删掉，**不碰生产库**。
# install-backup-cron.sh 已经把它装成每周一次；这条是手动跑一次确认能通过。
./deploy/restore.sh --drill

# 真恢复（会先备份当前库、先演练一遍、再要求手输 RESTORE 确认）
./deploy/restore.sh --to-production backups/reviews-YYYYmmdd-HHMMSS.db.gz

# 查看/确认自动备份与演练都已装
crontab -l | grep -E 'audiencelens-backup|audiencelens-restore-drill'
```

## 健康检查（接外部监控用哪个）

两条端点分工不同，接错了监控会一直显示绿色：

| 端点 | 查什么 | 用在哪 |
|---|---|---|
| `GET /api/health` | 只回写死的 `ok` + 配置快照，**不碰数据库** | 容器 healthcheck（"进程还在不在"） |
| `GET /api/health/ready` | 真打一次 `SELECT 1`，库不可用时返 **503** | 外部监控（UptimeRobot 等） |

拿 `/api/health` 接 UptimeRobot 是个常见错误：数据库挂了它照样 200，
监控一片绿而用户那边每个页面都在报错。**外部监控一律指向 `/api/health/ready`。**

`/health/ready` 刻意不探上游模型服务商——上游按调用计费，每分钟探一次会产生
真实账单；而且上游抖动不该让站点被判定为宕机（评审会失败，但站点是能用的）。
上游可用性看后台「系统健康度」的失败率趋势。

## 关键事实（排障先看这里）

- 后端容器内绑 **8000**（nginx 代理目标）；本地开发 `run.py` 绑 **8001**（vite proxy 目标）。两者故意不同。
- `AL_ENV=production` 且 JWT 密钥没改时，后端**拒绝启动**——这是故意的，看容器日志即知。
- 同理：开了账号体系（`AL_AUTH_ENABLED=true`）但邮件后端不是 smtp 时也**拒绝启动**，
  除非显式设 `AL_ALLOW_CONSOLE_MAIL=true`。邮件配得不对但没到拒启程度的情况（发件人是
  `@localhost`、端口与 SSL 配反、链接指向 localhost）走**启动告警**，在容器日志里搜 `[启动自检]`。
- `AL_ENCRYPTION_KEY` 一旦有用户存了 key 就**不要再换**（换了 = 所有已存 key 解密失败，用户需重填）。
- 评委规则集 `../audiencelens-v0.2-harness` 以只读卷挂进容器；缺失不崩溃，但 ethics/evaluation 会降级为内置规则。
- SQLite 单实例形态：**不要**起多个 backend 副本；要横向扩展先切 `AL_DATABASE_URL` 到 Postgres。
