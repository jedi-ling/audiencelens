# AudienceLens Web 前端

评审平台的用户端界面：发起评审（向导 / 对话澄清）、实时进度（WebSocket）、
报告与图表、分享页、判断留档与「你 vs 评审团」记分板、账号与设置。

技术栈：**React 19 + TypeScript + Vite + Tailwind CSS 4 + shadcn/ui + Recharts + Zustand + react-router**。

## 开发

```bash
npm install
npm run dev
```

开发服务器只绑 `127.0.0.1`，`/api` 与 `/ws` 代理到 `127.0.0.1:8001`——
即 `web/backend` 下 `python run.py` 起的开发后端（容器内后端是 8000，别混）。

## 构建与检查

```bash
npm run build       # i18n:check → tsc -b → vite build，产物在 dist/
npm run typecheck   # 只检查不打包
npm run lint
npm run preview     # 本地预览构建产物
```

## 国际化（i18n）

文案集中在 `src/i18n/`，中英文 locale 按页面分文件。
`keys.gen.ts` 与各 locale 的 `index.gen.ts` 是**生成文件，不要手改**：

```bash
npm run i18n:gen           # 改完文案后重新生成
npm run i18n:check         # 只校验（build / typecheck 会自动跑这步）
npm run i18n:scan          # 扫描硬编码文案
npm run i18n:sync-catalog  # 同步目录
```

## 目录

```
src/
├── pages/       # 路由页面（含落地页、报告页、分享页、记分板等）
├── components/  # 共享组件
├── store/       # Zustand 状态（会话、评审等）
├── i18n/        # 文案与 locale（见上）
└── lib/         # API 客户端、类型、工具
```

## 部署

构建产物是纯静态文件，服务器不需要 Node。
生产由 nginx 伺服 `dist/`，`/api` 与 `/ws` 同源反代到后端，
因此**不需要**配置 `VITE_API_BASE`。
完整部署见 [`../DEPLOY.md`](../DEPLOY.md)（Docker）或
[`../DEPLOY-BAREMETAL.md`](../DEPLOY-BAREMETAL.md)（裸机）。
