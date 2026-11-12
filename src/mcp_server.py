"""AudienceLens MCP Server

把合成观众评审系统暴露为 AI 助手可调用的 MCP 工具，
任何支持 MCP 的客户端（Claude Desktop、Claude Code、Cursor、Cherry Studio 等）均可接入。

运行：
    pip install -e ".[mcp]"
    audiencelens-mcp            # 或 python -m src.mcp_server

Claude Desktop 配置示例见 README「MCP 接入」一节。
评审需真实 LLM：请在本 server 的环境变量中配置 ANTHROPIC_API_KEY。
"""

from mcp.server.fastmcp import FastMCP

try:
    from . import mcp_tools
except ImportError:
    import mcp_tools

mcp = FastMCP("audiencelens")


@mcp.tool()
def list_task_types() -> dict:
    """列出所有支持的评审任务类型（Steam 页面 / Demo 首玩 / 概念 / 付费 / 通用产品 / 创业评审等 14 种）及说明。"""
    return mcp_tools.list_task_types()


@mcp.tool()
def list_persona_packs() -> dict:
    """列出所有可用的人格包（游戏核心 / 竞技 / 家庭休闲 / 手游 F2P / VR / 无障碍 / 上线合规 等 11 个）。"""
    return mcp_tools.list_persona_packs()


@mcp.tool()
def list_personas(pack: str = "game-core") -> dict:
    """列出指定人格包内的人格 id / 姓名 / 原型。用于在评审前了解面板构成。"""
    return mcp_tools.list_personas(pack)


@mcp.tool()
def run_synthetic_review(
    task_type: str,
    artifact: str,
    mode: str = "standard",
    personas_pack: str = "",
    allow_simulation: bool = False,
) -> dict:
    """运行一次多人格合成观众评审，返回结构化报告（共识 / 分歧 / 优先级修复 / 风险 / 校准）。

    personas_pack 留空时按任务类型取登记的默认人格包（定价页 → general-consumer，
    创业项目 → startup-panel，游戏类 → game-core）。

    artifact 可以是：材料文件路径、JSON 字符串、或直接粘贴的纯文本材料。
    评审使用真实 LLM；若 server 未配置 ANTHROPIC_API_KEY 且未显式允许模拟，将返回提示而非占位数据。
    """
    return mcp_tools.run_synthetic_review(
        task_type=task_type,
        artifact=artifact,
        mode=mode,
        personas_pack=personas_pack or None,
        allow_simulation=allow_simulation,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
