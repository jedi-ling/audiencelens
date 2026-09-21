"""AudienceLens 后台管理 MCP 服务器。

给本机的智能体（Hermes 等）一条能调用远程 AudienceLens 后台管理 API 的通道，
不需要把 curl 命令或裸密钥直接摊在对话里。

认证优先级（先判断有没有配用户名密码，没有才退回静态主密钥）：
  1. AL_ADMIN_USERNAME + AL_ADMIN_PASSWORD —— 推荐。给 Hermes 建一个专属的具名
     管理员账号（不要用你自己日常登录的那个），这样：
       - 出问题能在审计维度上区分是人还是 agent 操作的；
       - 需要收回权限时只停用这一个账号，不用轮换全局主密钥影响其他人。
     会话令牌有效期 12 小时，本进程内自动续登，不落盘。
  2. AL_ADMIN_TOKEN —— 静态主密钥，逃生舱用，等效于给了最高权限，尽量不用在
     长期挂机的 agent 上。

必填：AL_ADMIN_BASE_URL，指向远程后端的 /api 前缀，例如
  https://your-domain.com/api
本机联调可以指到 http://localhost:8001/api。

工具分两类：
  - 一批具名工具（admin_overview / admin_list_settings / ...），覆盖最常用的
    查看与配置操作，参数和返回值有明确 schema；
  - 一个逃生舱 admin_request，直接透传到 /admin/* 下任意路径，覆盖具名工具
    没包到的接口——但刻意限制在 /admin 前缀内，不能拿这个通道去打其他路由。
"""

import os
from typing import Any, Optional

import httpx
from mcp.server.mcpserver import MCPServer

BASE_URL = os.environ.get("AL_ADMIN_BASE_URL", "").rstrip("/")
USERNAME = os.environ.get("AL_ADMIN_USERNAME", "")
PASSWORD = os.environ.get("AL_ADMIN_PASSWORD", "")
STATIC_TOKEN = os.environ.get("AL_ADMIN_TOKEN", "")

if not BASE_URL:
    raise RuntimeError("必须设置 AL_ADMIN_BASE_URL，指向远程后端的 /api 前缀")
if not STATIC_TOKEN and not (USERNAME and PASSWORD):
    raise RuntimeError(
        "必须设置 AL_ADMIN_USERNAME+AL_ADMIN_PASSWORD（推荐）或 AL_ADMIN_TOKEN 之一"
    )

mcp = MCPServer("audiencelens-admin")

_session_token: Optional[str] = None


async def _login(client: httpx.AsyncClient) -> str:
    """具名账号登录换会话令牌。401 时调用方会清空缓存重新调这个函数。"""
    resp = await client.post(
        f"{BASE_URL}/admin/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["token"]


async def _call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    json: Any = None,
    params: Any = None,
    retry: bool = True,
) -> Any:
    global _session_token

    if STATIC_TOKEN:
        token = STATIC_TOKEN
    else:
        if _session_token is None:
            _session_token = await _login(client)
        token = _session_token

    resp = await client.request(
        method,
        f"{BASE_URL}{path}",
        json=json,
        params=params,
        headers={"X-Admin-Token": token},
        timeout=30,
    )

    if resp.status_code == 401 and not STATIC_TOKEN and retry:
        # 会话令牌过期（12 小时 TTL）——清掉缓存重登一次，仅重试一次防止死循环。
        _session_token = None
        return await _call(client, method, path, json=json, params=params, retry=False)

    resp.raise_for_status()
    return resp.json() if resp.content else None


async def _admin(method: str, path: str, *, json: Any = None, params: Any = None) -> Any:
    async with httpx.AsyncClient() as client:
        return await _call(client, method, path, json=json, params=params)


# ============================== 系统概览 ==============================

@mcp.tool()
async def admin_overview() -> dict:
    """跨用户聚合总览：评审总数、24h 成本、任务队列、注册用户数等核心指标。"""
    return await _admin("GET", "/admin/overview")


@mcp.tool()
async def admin_timeseries(days: int = 14) -> dict:
    """评审量/成本趋势时间序列。days 建议取 7/14/30/90。"""
    return await _admin("GET", "/admin/timeseries", params={"days": days})


# ============================== 运行时配置 ==============================

@mcp.tool()
async def admin_list_settings() -> dict:
    """列出所有运行时配置开关覆盖值（配额、限流、并发度等）。"""
    return await _admin("GET", "/admin/settings")


@mcp.tool()
async def admin_set_setting(key: str, value: Any) -> dict:
    """覆盖一个运行时配置项，立即生效，不需要重启后端。"""
    return await _admin("PUT", "/admin/settings", json={"key": key, "value": value})


@mcp.tool()
async def admin_reset_setting(key: str) -> dict:
    """清除一个配置覆盖值，回落到环境变量/默认值。"""
    return await _admin("DELETE", f"/admin/settings/{key}")


# ============================== 平台级 API Key ==============================

@mcp.tool()
async def admin_server_key_status(provider: str = "anthropic") -> dict:
    """查看平台级（托管模式垫付用）API Key 的配置状态，key 本身脱敏返回。"""
    return await _admin("GET", "/admin/server-key", params={"provider": provider})


@mcp.tool()
async def admin_set_server_key(
    api_key: str,
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_base: Optional[str] = None,
) -> dict:
    """设置平台级 API Key。provider 为 anthropic 或 openai_compatible；
    走 Anthropic 兼容中转（如 MiniMax）时 provider 填 anthropic，
    model/api_base 填对应值。"""
    body: dict = {"api_key": api_key, "provider": provider}
    if model:
        body["model"] = model
    if api_base:
        body["api_base"] = api_base
    return await _admin("PUT", "/admin/server-key", json=body)


@mcp.tool()
async def admin_test_server_key(provider: str = "anthropic") -> dict:
    """测试已配置的平台级 API Key 是否能真正连通。"""
    return await _admin("POST", "/admin/server-key/test", json={"provider": provider})


# ============================== 管理员账号 ==============================

@mcp.tool()
async def admin_list_admin_accounts() -> list:
    """列出后台管理面板的具名登录账号（不是产品用户）。"""
    return await _admin("GET", "/admin/auth/users")


@mcp.tool()
async def admin_create_admin_account(username: str, password: str) -> dict:
    """新建一个后台管理员账号。密码至少 8 位。"""
    return await _admin(
        "POST", "/admin/auth/users", json={"username": username, "password": password}
    )


@mcp.tool()
async def admin_deactivate_admin_account(user_id: str) -> dict:
    """停用一个后台管理员账号——其已签发的会话令牌立即失效。"""
    return await _admin("DELETE", f"/admin/auth/users/{user_id}")


# ============================== 审计与巡检 ==============================

@mcp.tool()
async def admin_audit_log(limit: int = 50) -> dict:
    """最近的后台管理操作审计日志。"""
    return await _admin("GET", "/admin/audit-log", params={"limit": limit})


@mcp.tool()
async def admin_list_jobs(status: Optional[str] = None, limit: int = 50) -> dict:
    """任务队列巡检。status 可选 pending/running/done/failed 等。"""
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    return await _admin("GET", "/admin/jobs", params=params)


@mcp.tool()
async def admin_list_reviews(status: Optional[str] = None, limit: int = 50) -> dict:
    """评审记录巡检。"""
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    return await _admin("GET", "/admin/reviews", params=params)


# ============================== 逃生舱 ==============================

# 允许的方法白名单。放开任意字符串意味着可以发 TRACE / 自定义方法，
# 而这个通道带着后台的全部权限，没有理由比具名工具更宽松。
_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _validate_admin_path(path: str) -> str:
    """把「必须在 /admin 下」这句话真的做实。

    原来的写法是 `path.startswith("/admin")`，它有两个洞：

      1. **前缀不等于路径段**。`/administrator-elsewhere`、`/adminx` 都能通过——
         只要后端哪天挂了一个这样的路由（或者反代把 /admin 之外的东西转出去），
         这个"限制在后台前缀内"的承诺就是空的。
      2. **不处理 `..`**。`/admin/../auth/register` 起手就是 `/admin`，
         但服务器（或中间的反代）做过路径规范化之后打到的是 `/auth/register`。
         逃生舱本来就带着管理员令牌，能拿它去打产品侧路由是最不该有的能力。

    所以改成：先拒 `..` 与反斜杠与控制字符，再要求路径**恰好**是 `/admin`
    或以 `/admin/` 开头。校验在拼 URL 之前做，不依赖服务端的规范化行为。
    """
    if not isinstance(path, str) or not path:
        raise ValueError("path 必须是非空字符串")
    if "\\" in path or any(ord(c) < 0x20 for c in path):
        raise ValueError("path 含非法字符（反斜杠或控制字符）")
    # 只看路径部分：带上 ?query 时交给 params 参数，不要混在 path 里
    if "?" in path or "#" in path:
        raise ValueError("path 不能带 query 或 fragment，请用 query 参数")
    if any(seg == ".." for seg in path.split("/")):
        raise ValueError("path 不能包含 `..` 段")
    if path != "/admin" and not path.startswith("/admin/"):
        raise ValueError("path 必须是 /admin 或以 /admin/ 开头")
    return path


@mcp.tool()
async def admin_request(
    method: str, path: str, json_body: Optional[dict] = None, query: Optional[dict] = None
) -> Any:
    """直接调用任意 /admin/* 接口——覆盖上面具名工具没包到的操作。

    path 必须是 `/admin` 本身或 `/admin/...`（如 /admin/plans、/admin/cdk/generate），
    不接受其他前缀，防止这个通道被用来打后台管理之外的路由。
    method 是 GET/POST/PUT/DELETE 之一。
    """
    verb = method.upper().strip()
    if verb not in _ALLOWED_METHODS:
        raise ValueError(f"method 必须是 {'/'.join(sorted(_ALLOWED_METHODS))} 之一")
    return await _admin(verb, _validate_admin_path(path), json=json_body, params=query)


if __name__ == "__main__":
    mcp.run()
