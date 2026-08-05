# 服务器部署手册 · 非 Docker 版（systemd + nginx）

面向：一台干净的 Linux 服务器（Ubuntu 22.04/24.04 或 Debian 12），已解析好的域名。
不想装 Docker、或者机器上已经有 nginx 的，走这一份。要用 Docker 的看 `DEPLOY.md`。

> 全文命令假设你用一个非 root 账号 `deploy` 操作，代码放在 `/opt/audiencelens`。
> 换路径的话把下面所有 `/opt/audiencelens` 一起换掉，systemd 单元里的路径也要改。

---

## 0. 先读这一条：**后端只能单进程跑**

这是这套系统最容易踩、踩了还很难查的一个坑。

后端的**任务队列**（`ThreadPoolExecutor`，见 `app/services/job_service.py`）、
**WebSocket 连接表**（`app/websocket/__init__.py` 的 `ConnectionManager`）、
**限流计数桶**（`app/core/ratelimit.py`）全都活在**进程内存**里。所以：

```bash
uvicorn app.main:app --workers 4     # ← 绝对不要这么起
```

多进程会造成三种故障，而且都不报错、只是行为变得莫名其妙：

| 现象 | 原因 |
|---|---|
| 评审卡在"进行中"不动，刷新才看到结果 | 任务在 worker A 跑，用户的 WebSocket 连到了 worker B，进度事件永远送不到 |
| 限流形同虚设 | 每个 worker 各有一套计数桶，实际限额 = 配置值 × worker 数 |
| 重启后重复收尸 | 每个 worker 启动时都跑一遍 `_reap_orphans` |

**要提高吞吐就调这两个环境变量，不要加 worker：**

- `AL_QUEUE_WORKERS`（默认 2）—— 同时能跑几场评审
- `AUDIENCELENS_MAX_CONCURRENCY`（默认 6）—— 单场评审内并发调用几个人格

真需要横向扩多机时，得先把队列换成 Redis/RQ 之类的外部队列，那是另一项改造，
不在本文范围。

---

## 1. 装依赖

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx git curl
# Node 用于构建前端静态文件（构建完就不需要它常驻）
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

Python 版本按 `web/backend/Dockerfile` 的基线是 **3.11**。3.10+ 都能跑，
但别用 3.8——本仓库有部分类型写法在 3.8 上会出问题。

```bash
sudo mkdir -p /opt/audiencelens && sudo chown deploy:deploy /opt/audiencelens
git clone <你的仓库地址> /opt/audiencelens
cd /opt/audiencelens

python3.11 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt            # 引擎依赖
.venv/bin/pip install -r web/backend/requirements.txt # 平台依赖（含 psycopg2-binary）
```

> **目录结构不能改。** 后端多处用「从本文件往上数几级」来定位 `src/`（引擎）、
> `src/personas/`、`audiencelens-v0.2-harness/`、`web/.env`。把 `web/backend`
> 单独拷出去部署会让 `from runner...` 直接 ModuleNotFoundError。整个仓库一起放。

---

## 2. 写配置

```bash
cd /opt/audiencelens/web
cp .env.production.example .env
chmod 600 .env          # 里面有密钥，别让同机其它用户读到
```

必须自己生成、且**三个必须互不相同**的密钥：

```bash
openssl rand -hex 32    # 跑三次，分别填给下面三项
```

| 变量 | 说明 |
|---|---|
| `AL_JWT_SECRET` | 签登录态。轮换它 = 踢掉所有已登录用户 |
| `AL_ENCRYPTION_KEY` | 加密落库的用户 API Key。**设了就别再换**——换了所有已存的 key 都解不开 |
| `AL_ADMIN_TOKEN` | 后台面板的唯一凭据。**必须 ≥16 字符**，短了启动直接拒绝 |

其余要改的：

```ini
AL_CORS_ORIGINS=https://你的域名.com     # 同时也是 WebSocket 的 origin 白名单
AL_PUBLIC_WEB_URL=https://你的域名.com   # 邮件里链接的落点，填错=用户点开打不开
AL_MAIL_BACKEND=smtp                     # 邮件那一段见 DEPLOY.md「邮件发送」
AL_SMTP_HOST=...                         # 不配的话用户收不到激活/重置邮件
```

`FRONTEND_BIND` / `SITE_DOMAIN` 这两项是 Docker + Caddy 用的，**本方案不用**，
可以留着不管（nginx 的监听地址在 nginx 配置里写）。

### 数据库：SQLite 还是 PostgreSQL

默认 SQLite，文件落在 `web/backend/data/reviews.db`，单机够用。
要用 PostgreSQL 就设：

```ini
AL_DATABASE_URL=postgresql+psycopg2://用户:密码@127.0.0.1:5432/audiencelens
```

驱动 `psycopg2-binary` 已经在 `web/backend/requirements.txt` 里。
换库之后**务必重跑一遍测试**（`cd web/backend && ../../.venv/bin/python -m pytest -q`）——
SQLite 默认不校验外键、布尔当整数存，好些问题只在 PostgreSQL 上才显形。

---

## 3. 先手动跑一次，让启动自检说话

**不要跳过这一步直接写 systemd。** 配置不对时后端是**拒绝启动**的，
手动跑能一眼看到原因；写成服务再启，同样的错误只会变成一行 `status=1/FAILURE`。

```bash
cd /opt/audiencelens/web/backend
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

会拒绝启动的几种情况（都是故意的，不是 bug）：

| 报错 | 含义 |
|---|---|
| `AL_ADMIN_TOKEN 太短` | 少于 16 字符。它是静态令牌、无有效期，短了能被爆破 |
| `AL_JWT_SECRET 仍是开发默认值` | 生产环境用默认密钥 = 任何人都能伪造登录态 |
| `AL_AUTH_ENABLED=false` | 关认证时所有访客共用一个匿名身份、互相看得见。确认是单人自用就显式设 `AL_ALLOW_SHARED_ANONYMOUS=true` |
| `AL_MAIL_BACKEND=smtp 但未配 AL_SMTP_HOST` | 会静默退化成 console 档，用户永远收不到邮件 |

看到 `Application startup complete` 就 Ctrl+C，进下一步。

---

## 4. 后端做成 systemd 服务

```bash
sudo tee /etc/systemd/system/audiencelens.service >/dev/null <<'EOF'
[Unit]
Description=AudienceLens backend
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/audiencelens/web/backend

# --workers 保持 1（不写就是 1）。原因见手册第 0 节：队列/WS/限流都在进程内存里。
# --forwarded-allow-ips 只信任本机 nginx 递来的 X-Forwarded-For。
#   不限定的话，uvicorn 默认信任任何来源的该头部——直连的攻击者可以伪造它，
#   绕过按 IP 的限流和后台令牌失败锁定。
ExecStart=/opt/audiencelens/.venv/bin/python -m uvicorn app.main:app \
    --host 127.0.0.1 --port 8000 \
    --forwarded-allow-ips 127.0.0.1

Restart=always
RestartSec=3

# 崩溃重启后会自动把上一轮遗留的"进行中"评审收尸并退还已扣的次数/配额，
# 见 app/db.py::_reap_orphans。所以 Restart=always 是安全的。

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now audiencelens
sudo systemctl status audiencelens --no-pager
curl -s http://127.0.0.1:8000/api/health
```

> 后端只监听 `127.0.0.1`，公网流量一律走 nginx。别把它绑到 `0.0.0.0`——
> 那样 `/api/admin/*` 就直接暴露在公网上，只剩一个静态令牌挡着。

---

## 5. 构建前端 + 后台面板

两个都是 Vite 静态站，构建完只剩一堆静态文件，不需要 Node 常驻。

```bash
cd /opt/audiencelens/web/frontend
npm ci && npm run build          # 产物在 dist/

cd /opt/audiencelens/web/admin
npm ci && npm run build          # 产物在 dist/
```

前端请求走同源相对路径 `/api`，所以**不需要**配 `VITE_API_BASE`，
交给 nginx 反代即可。

---

## 6. nginx

```bash
sudo tee /etc/nginx/sites-available/audiencelens >/dev/null <<'EOF'
server {
    listen 80;
    server_name 你的域名.com;

    root /opt/audiencelens/web/frontend/dist;
    index index.html;

    location /api/ {
        # nginx 默认 client_max_body_size 只有 1m，而后端图片上传上限是 8MB。
        # 不放宽的话，任何正常大小的截图都会在到达后端之前被 413 拦掉，
        # 而且前端拿到的是连接重置，不是后端那句"图片超过上限"的清晰报错——
        # 用户只会看到"发不出去"，完全不知道为什么。
        client_max_body_size 10m;

        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # 注意是 $remote_addr 而不是 $proxy_add_x_forwarded_for：
        # 后者会把客户端**自己发来的** XFF 原样接在前面，于是攻击者可以
        # 伪造一串假 IP，绕过按 IP 的限流和后台失败锁定。这里直接覆盖。
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 评审是长任务，别让 nginx 在默认 60s 就掐断
        proxy_read_timeout 300s;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;   # WebSocket 要长连接，不能按普通请求超时
    }

    location / {
        try_files $uri $uri/ /index.html;   # SPA 路由回落
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/audiencelens /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### HTTPS（Let's Encrypt）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名.com
```

certbot 会自动改上面那个 server 块并装好续期定时器。装完加一条 HSTS：

```nginx
# 加在 443 的 server 块里
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

> HSTS 一旦生效，浏览器在 max-age 内会拒绝走 HTTP 访问该域名。
> 先确认 HTTPS 真的通了再加，否则证书出问题时你连回退的机会都没有。

验证：

```bash
curl -sI https://你的域名.com | head -3
curl -s https://你的域名.com/api/health
```

---

## 7. 后台管理面板（不要暴露到公网）

面板只有一个静态令牌，没有账号体系、没有失败锁定之外的防护。
**不要**给它配公网域名。用 nginx 只监听本机 + SSH 隧道访问：

```bash
sudo tee /etc/nginx/sites-available/audiencelens-admin >/dev/null <<'EOF'
server {
    listen 127.0.0.1:5200;        # 只监听本机，公网访问不到
    server_name localhost;

    root /opt/audiencelens/web/admin/dist;
    index index.html;

    location /api/ {
        client_max_body_size 10m;
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
    location / { try_files $uri $uri/ /index.html; }
}
EOF

sudo ln -sf /etc/nginx/sites-available/audiencelens-admin /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

在**你自己的电脑**上开隧道：

```bash
ssh -L 5200:127.0.0.1:5200 deploy@你的服务器
# 然后浏览器打开 http://localhost:5200 ，令牌填 .env 里的 AL_ADMIN_TOKEN
```

---

## 8. 备份（必做）

数据库单点，不备份就是在等一次误删。仓库里的 `web/deploy/backup.sh` 会按
`AL_DATABASE_URL` 自动分辨 SQLite / PostgreSQL，未知方言会明确报错退出
（而不是假装备份成功产出一个空文件）。

脚本会先用本机 venv（默认 `<仓库>/.venv/bin/python`）去问后端的真实数据库地址，
问不到再回落 Docker。venv 装在别处就用 `VENV_PY=/你的/python` 覆盖。

```bash
sudo mkdir -p /var/backups/audiencelens && sudo chown deploy:deploy /var/backups/audiencelens

crontab -e
# 加一行：每天 03:30 备份
30 3 * * * cd /opt/audiencelens && BACKUP_DIR=/var/backups/audiencelens bash web/deploy/backup.sh >> /var/log/audiencelens-backup.log 2>&1
```

**装完当场手跑一次**，别等到明天才发现路径写错：

```bash
cd /opt/audiencelens && BACKUP_DIR=/var/backups/audiencelens bash web/deploy/backup.sh
ls -lh /var/backups/audiencelens
```

> ⚠️ 用 SQLite 时，`data/reviews.db` 里存的用户 API Key 是**用 `AL_ENCRYPTION_KEY` 加密的**。
> 只备份 db、不备份 `.env`，恢复出来的库里所有 key 都解不开。两个要一起备，
> 而且 `.env` 里有明文密钥，备份目标的权限要收紧。

---

## 9. 日常运维

```bash
# 看日志（后端所有输出都进 journal）
sudo journalctl -u audiencelens -f
sudo journalctl -u audiencelens --since "1 hour ago" | grep -i error

# 重启
sudo systemctl restart audiencelens

# 更新发布
cd /opt/audiencelens
git pull
.venv/bin/pip install -r requirements.txt -r web/backend/requirements.txt
(cd web/frontend && npm ci && npm run build)
(cd web/admin && npm ci && npm run build)
sudo systemctl restart audiencelens
curl -s https://你的域名.com/api/health
```

发布前建议先跑一遍测试（几十秒）：

```bash
cd /opt/audiencelens && .venv/bin/python -m pytest tests/ -q
cd web/backend && ../../.venv/bin/python -m pytest -q
```

---

## 10. 排障：先看这几条

| 现象 | 多半是 |
|---|---|
| `systemctl start` 立刻失败，`status=1` | 启动自检拒启。`journalctl -u audiencelens -n 30` 看具体哪一项（见第 3 节表格） |
| 上传截图报错 / 发不出去 | nginx 的 `client_max_body_size` 没放宽（默认 1m），后端 8MB 的图到不了 |
| 评审进度条不动、要刷新才更新 | WebSocket 没通。查 nginx 的 `/ws/` 块有没有 `Upgrade` 头，以及 `AL_CORS_ORIGINS` 是否包含你的域名（它同时是 WS 的 origin 白名单） |
| 评审跑到一半断、日志里是超时 | nginx 的 `proxy_read_timeout` 太短（本文给的是 300s） |
| 发起评审返回 428 | 没有可用的模型 Key。BYOK 形态下要用户自己在设置页填；平台垫付形态要配 `ANTHROPIC_API_KEY` 或在后台面板配 |
| 用户收不到激活/重置邮件 | `AL_MAIL_*` 没配全，或落点 `AL_PUBLIC_WEB_URL` 填的不是真实站点。到后台面板「运行时配置 → 邮件发送」点一次测试邮件当场验 |
| 限流好像不起作用 | 检查是不是起了多个 worker（见第 0 节），以及 nginx 是否用 `$remote_addr` 覆盖了 XFF |
| 换 PostgreSQL 后删账号/删评审报 500 | 先把两套测试在 PostgreSQL 上跑一遍——SQLite 默认不校验外键，好些问题只在 PG 上暴露 |

---

## 关键事实速查

- 后端监听 **127.0.0.1:8000**（本地开发用 `run.py` 是 **8001**，对齐 vite 代理，两者故意不同）
- 前端产物 `web/frontend/dist`，后台产物 `web/admin/dist`，都是纯静态
- 数据库默认 `web/backend/data/reviews.db`
- 配置文件 `web/.env`，**不在版本库里**，权限应为 600
- 后端进程**必须单实例**，扩容靠 `AL_QUEUE_WORKERS` / `AUDIENCELENS_MAX_CONCURRENCY`
- 重启会自动收尸 + 退还已扣的评审次数（`app/db.py::_reap_orphans`）
