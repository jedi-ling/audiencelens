# AudienceLens Web — 技术架构文档

## 1. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Browser                           │
│  React + TypeScript + Tailwind + shadcn/ui          │
│  (Vite dev server :5173)                             │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                      │
│  (uvicorn :8000)                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ REST API    │  │ WebSocket    │  │ Background  │ │
│  │ /api/*      │  │ /ws/review/* │  │ Tasks       │ │
│  └─────────────┘  └──────────────┘  └──────┬──────┘ │
│                                             │        │
│  ┌──────────────────────────────────────────▼──────┐ │
│  │          src/runner/ (existing modules)          │ │
│  │  panel_selector → evidence_precheck →            │ │
│  │  persona_agent → validator → cross_exam →        │ │
│  │  aggregator → calibration → cli                  │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  SQLite / PostgreSQL                  │
│  reviews, persona_outputs, reports, users            │
└─────────────────────────────────────────────────────┘
```

## 2. 技术栈

### 前端

| 技术 | 版本 | 用途 |
|---|---|---|
| React | 19 | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Vite | 6.x | 构建工具 |
| Tailwind CSS | 4.x | 样式 |
| shadcn/ui | latest | 组件库 |
| Recharts | 2.x | 图表（雷达图、饼图） |
| React Router | 7.x | 路由 |
| Zustand | 5.x | 状态管理 |
| @tanstack/react-query | 5.x | 数据获取 |

### 后端

| 技术 | 版本 | 用途 |
|---|---|---|
| FastAPI | 0.115+ | Web 框架 |
| uvicorn | 0.34+ | ASGI 服务器 |
| SQLAlchemy | 2.x | ORM |
| Alembic | 1.x | 数据库迁移 |
| python-socketio | 5.x | WebSocket |
| anthropic | 0.40+ | Claude API |
| pyyaml | 6.x | YAML 解析 |
| jsonschema | 4.x | Schema 校验 |

## 3. 数据模型

### Review（评审）

```python
class Review:
    id: str              # UUID
    task_type: str       # 10种任务类型
    target_title: str    # 评审对象名称
    artifact_bundle: dict # 材料包
    persona_pack: str    # 使用的 Pack
    selected_personas: list[str]  # 选中的 persona ID
    status: str          # pending/running/completed/failed
    created_at: datetime
    completed_at: datetime | None
    total_cost_usd: float
    report_json: dict | None
    report_markdown: str | None
    calibration: dict | None
```

### PersonaOutput（单个 Persona 输出）

```python
class PersonaOutput:
    id: str
    review_id: str       # FK → Review
    persona_id: str
    persona_name: str
    status: str          # pending/running/completed/failed
    output_json: dict | None
    validation_result: dict | None
    cost_usd: float
    started_at: datetime | None
    completed_at: datetime | None
```

## 4. API 设计

### REST API

```
POST   /api/reviews                    # 创建评审
GET    /api/reviews                    # 列出评审
GET    /api/reviews/:id                # 获取评审详情
DELETE /api/reviews/:id                # 删除评审
GET    /api/reviews/:id/report         # 获取报告

GET    /api/personas                   # 列出所有 persona
GET    /api/personas/:id               # 获取 persona 详情
GET    /api/personas/packs             # 列出 persona packs

GET    /api/presets                    # 列出面板预设
GET    /api/presets/:task_type         # 获取特定任务预设

POST   /api/validate-artifact          # 校验材料包格式
```

### WebSocket

```
WS /ws/review/:id                      # 评审实时进度
  → 事件: persona_started, persona_completed, persona_failed,
          cross_exam_started, cross_exam_completed,
          aggregation_started, aggregation_completed,
          review_completed, review_failed
```

## 5. 目录结构

```
web/
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── components/          # UI 组件
│   │   │   ├── ui/              # shadcn/ui 组件
│   │   │   ├── persona/         # Persona 相关组件
│   │   │   ├── review/          # 评审相关组件
│   │   │   └── report/          # 报告相关组件
│   │   ├── pages/               # 页面
│   │   ├── hooks/               # 自定义 hooks
│   │   ├── stores/              # Zustand stores
│   │   ├── lib/                 # 工具函数
│   │   └── types/               # TypeScript 类型
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
├── backend/                     # FastAPI 后端
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── api/                 # API 路由
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/            # 业务逻辑
│   │   └── websocket/           # WebSocket 处理
│   ├── alembic/                 # 数据库迁移
│   └── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

## 6. 关键实现细节

### 评审执行流程

1. 用户提交评审请求 → 创建 Review 记录（status=pending）
2. 后台任务启动 → 依次运行 persona_agent
3. 每个 persona 完成后 → WebSocket 推送 persona_completed 事件
4. 全部 persona 完成 → 运行 cross_exam → 推送事件
5. 聚合 → 推送 aggregation_completed 事件
6. 校准 → 更新 Review 记录（status=completed）

### Persona 雷达图

使用 Recharts 的 RadarChart，12个行为轴映射为雷达图的12个顶点：
- 5级轴映射为 1-5 分
- 3级轴映射为 1/2/3 → 1.67/3.33/5 分（归一化到5分制）

### 成本控制

- 后端在启动评审前检查 budget.yaml 的 max_cost_per_run_usd
- 每个 persona 完成后累计成本，超预算时停止后续 persona
- 前端实时显示已消耗成本

## 7. 部署方案

### 开发环境

```bash
# 前端
cd web/frontend && npm run dev

# 后端
cd web/backend && uvicorn app.main:app --reload
```

### 生产部署

```bash
docker-compose up -d
```

Docker Compose 包含：
- frontend: Nginx + React 静态文件
- backend: uvicorn + FastAPI
- db: PostgreSQL（生产）/ SQLite（MVP 可选）
