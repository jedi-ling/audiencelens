# AudienceLens 后台管理 MCP 服务器

让本机的智能体（Hermes 等任何支持 MCP 的客户端）通过 MCP 协议管理远程
AudienceLens 后台——查总览、改运行时配置、配平台 Key、管理员账号、看审计日志/
任务队列，不需要在对话里裸敲 curl 或摊密钥。

这是一个 **stdio MCP 服务器**：客户端（Hermes）把它当子进程启动，通过标准输入
输出说 MCP 协议；这个进程再把工具调用转换成对远程后端 `/api/admin/*` 的 HTTP
请求。进程本身不需要单独部署、不需要公网端口。

## 安装

需要 Python 3.10+（`mcp` 库的最低要求；本机 `C:\Users\...\Python311\python.exe`
或 Hermes 自带的 venv 都满足）。

```bash
cd mcp-admin-server
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## 建一个专属账号，不要用你自己的

先照上一步做好的「后台账号」功能，给这个 MCP 服务器单独建一个管理员账号
（后台面板「运行时配置」→「管理员账号」，或用现有的账号登录后台面板去建）：

- 用户名建议就叫 `hermes` 之类，一眼能看出是 agent 用的
- 这样出问题时审计日志能分清是人操作的还是 agent 操作的；
  要收权限时只停用这一个账号，不影响你自己和其他人登录

## 配置

三个环境变量（推荐用户名密码，见上一节；`AL_ADMIN_TOKEN` 是静态主密钥，
逃生舱用，长期挂机的 agent 不建议用它——它是最高权限且没有独立开关）：

```bash
AL_ADMIN_BASE_URL=https://your-domain.com/api   # 或本机联调用 http://localhost:8001/api
AL_ADMIN_USERNAME=hermes
AL_ADMIN_PASSWORD=<刚建的那个密码>
```

## 接入 Hermes

在 Hermes 的配置文件（`cli-config.yaml` 一类）里加一个 stdio MCP server：

```yaml
mcp_servers:
  audiencelens-admin:
    command: C:\path\to\mcp-admin-server\venv\Scripts\python.exe
    args: ["C:\\path\\to\\mcp-admin-server\\server.py"]
    env:
      AL_ADMIN_BASE_URL: "https://your-domain.com/api"
      AL_ADMIN_USERNAME: "hermes"
      AL_ADMIN_PASSWORD: "<刚建的那个密码>"
```

保存后 Hermes 会自动发现并注册下面这些工具。

## 工具一览

| 工具 | 作用 |
|---|---|
| `admin_overview` | 核心指标总览 |
| `admin_timeseries` | 评审量/成本趋势 |
| `admin_list_settings` / `admin_set_setting` / `admin_reset_setting` | 运行时配置开关 |
| `admin_server_key_status` / `admin_set_server_key` / `admin_test_server_key` | 平台级 API Key（含 MiniMax 等 Anthropic 兼容中转） |
| `admin_list_admin_accounts` / `admin_create_admin_account` / `admin_deactivate_admin_account` | 后台登录账号管理 |
| `admin_audit_log` | 操作审计日志 |
| `admin_list_jobs` / `admin_list_reviews` | 任务队列 / 评审记录巡检 |
| `admin_request` | 逃生舱——直接调 `/admin/*` 下任意没被上面包到的接口 |

## 安全边界

- 会话令牌只在这个进程的内存里，不落盘，进程重启就要重新登录
- 会话令牌 12 小时过期，服务器内部自动重登，不需要你干预
- `admin_request` 强制要求 path 以 `/admin` 开头，不能拿它去打后台管理以外的路由
- 停用 `hermes` 这个账号（后台面板一键操作）就能立即收回这个 MCP 服务器的所有权限，
  不影响其他登录中的人
