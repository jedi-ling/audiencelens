# 落地版本发布计划（v1.0 上线工程）

> 目标：把现在"本地全功能可跑"的系统变成"外人打开网址就能用"的正式产品。
> 基于 2026-07-19 的部署就绪度审计。代码功能层已基本齐备，主要缺口在部署工程与安全配置。

## 现状盘点（审计结论）

| 领域 | 状态 | 说明 |
|---|---|---|
| Docker 化 | 🟡 部分 | backend + frontend 都有 Dockerfile 和 compose；**admin 面板没有**，也没进 compose |
| HTTPS/TLS | 🔴 缺失 | nginx 只监听 80，`server_name localhost`，无证书方案 |
| 生产配置 | 🟡 部分 | 所有 `AL_*` 开关都从 env 读（多实例友好），但 compose 没接线；`AL_JWT_SECRET` 默认值不安全且**兼作 BYOK key 的加密密钥** |
| 数据库 | 🟡 部分 | 默认 SQLite + 启动时 create_all + 手写 legacy 迁移；支持换 Postgres（`AL_DATABASE_URL`），但无 Alembic |
| 评委规则集 | 🟢 就绪 | `audiencelens-v0.2-harness/` 缺失时优雅降级为内置规则，不阻塞部署（但托管版应带上以保证评分质量） |
| 前端 API 基址 | 🟢 就绪 | 构建版走同源 `/api`（nginx 代理），`VITE_API_BASE` 可选拆分域名 |
| 计费 | 🔴 缺失（有意） | 无支付网关；变现 = CDK 兑换码 + 配额套餐，`plan_service.py` 留了 Stripe 接缝 |
| CI/CD | 🔴 缺失 | `.github/` 只有 issue 模板，无 workflows |

## 上线形态决策（三选一）

**A. 静态落地页先行（最快，0 后端）**
只把 `REMOVED/landing-page/index.html` 发布到静态托管（GitHub Pages / Cloudflare Pages / Vercel）。收集意向，产品仍走本地/开源。1 小时内可完成。

**B. BYOK 开放版（推荐的第一个真发布）**
单台 VPS + docker compose 全栈上线：用户自带 API key 评审，服务端不垫钱、无配额压力、无支付需求。
- 风险最小：没有 key 泄露赔付面（BYOK 明文只进不出）、没有成本失控面
- CDK 码可作为增值钩子提前发（`AL_QUOTA_MODE=credits`）
- 这是 BP 里"开源获客 → 付费 pilot"路径的线上支点

**C. 托管 SaaS 版（需要垫付 key + 配额 + 客服）**
`AL_KEY_MODE=hybrid` + `AL_AUTH_ENABLED=true` + `AL_QUOTA_ENABLED=true` + 平台 key 垫付。
成本敞口和滥用风险都需要运营投入，建议在 B 版跑出真实用户后再切。

> 默认推进 **A + B 并行**：落地页立即上线开始积累流量，B 版作为 v1.0 主体。

## v1.0（B 版）工作清单

### P0 — 安全与配置硬化（半天）
1. `.env.production.example`：列全所有必改项——`AL_ENV=production`、`AL_JWT_SECRET`（32+ 随机字节）、`AL_ADMIN_TOKEN`、`AL_CORS_ORIGINS=正式域名`、`AL_AUTH_ENABLED=true`
2. compose 接线：把全套 `AL_*` 从 env_file 注入 backend（现在只传了 `ANTHROPIC_API_KEY`）
3. 启动自检：`AL_ENV=production` 时若 `AL_JWT_SECRET` 仍是默认值则拒绝启动（fail fast，防止裸奔）
4. **JWT 密钥与 BYOK 加密密钥分离**（`AL_ENCRYPTION_KEY` 独立配置，兼容旧数据的迁移路径）——换 JWT secret 不该让所有用户存的 key 变成乱码

### P1 — 部署工程补全（1 天）
5. `web/admin/Dockerfile` + 进 compose（绑内网端口或独立 basic-auth，不暴露公网）
6. TLS：Caddy 作为最外层反代（自动 Let's Encrypt，配置量最小），或 nginx + certbot
7. compose 加 healthcheck + restart policy；SQLite 卷备份脚本（每日 cron + 保留 7 份）
8. 评委规则集打包：Dockerfile COPY `audiencelens-v0.2-harness/harness`（或转正提交进主仓库——它只有 118KB 规则文本，gitignore 掉反而是隐患）

### P2 — 发布流水线（1 天）
9. GitHub Actions：PR 跑 `pytest tests/`（267）+ `web/backend pytest`（173）+ 双前端 `npm run build`
10. main 分支打 tag → 构建镜像 → push registry → 服务器 `compose pull && up -d` 一键更新
11. 冒烟脚本：部署后自动打 `/api/health` + 首页 200 检查

### P3 — 上线后一周内
12. Alembic 引入（趁数据少把 create_all 换掉，为将来 Postgres 铺路）
13. 错误监控（Sentry 免费档，`core/logging.py` 已留接缝）
14. 落地页 → 产品域名打通（`app.域名` 或同域路由）
15. CDK 首批发码 + 判断复利数据开始积累

## 明确不做（v1.0 范围外）
- 支付网关（Stripe/支付宝）——等付费 pilot 有真实需求再接，CDK 码足够过渡
- Postgres 迁移——单实例 SQLite 完全够第一批流量，先上线再演进
- 多实例/队列外置（Celery/RQ）——`job_service` 已留缝，流量到了再说

## 待用户决策
- [ ] 部署目标：国内 VPS（需 ICP 备案，落地页含中文产品）vs 海外 VPS（免备案，国内访问稍慢）
- [ ] 域名是否已注册；落地页与产品是否同域
- [ ] v1.0 是否默认开 `AL_AUTH_ENABLED=true`（推荐开：匿名仍可用，登录解锁完整报告，符合"体验机会+登录看详情"设计）
