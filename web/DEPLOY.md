# 一页纸部署手册（v1.0 · 国内服务器 + 已备案域名 + hybrid 形态）

前提：服务器装好 Docker（含 compose 插件），域名 A 记录已指向服务器 IP。

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

## 日常运维

```bash
# 更新发布（拉代码重建）
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 看日志
docker compose logs -f backend

# 手动备份（自动备份由 install-backup-cron.sh 装的 crontab 定时跑）
./deploy/backup.sh

# 查看/确认自动备份已装
crontab -l | grep audiencelens-backup
```

## 关键事实（排障先看这里）

- 后端容器内绑 **8000**（nginx 代理目标）；本地开发 `run.py` 绑 **8001**（vite proxy 目标）。两者故意不同。
- `AL_ENV=production` 且 JWT 密钥没改时，后端**拒绝启动**——这是故意的，看容器日志即知。
- `AL_ENCRYPTION_KEY` 一旦有用户存了 key 就**不要再换**（换了 = 所有已存 key 解密失败，用户需重填）。
- 评委规则集 `../audiencelens-v0.2-harness` 以只读卷挂进容器；缺失不崩溃，但 ethics/evaluation 会降级为内置规则。
- SQLite 单实例形态：**不要**起多个 backend 副本；要横向扩展先切 `AL_DATABASE_URL` 到 Postgres。
