"""AudienceLens MCP 工具的纯逻辑层（不依赖 mcp 包，可单测）。

mcp_server.py 用 FastMCP 把这些函数包成 AI 可调用的工具。
分层目的：即使运行环境未安装 mcp，核心逻辑仍可被 pytest 覆盖。
"""

import json
import os
import sys

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SRC_DIR)
for _p in (_SRC_DIR, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from runner import cli as runner_cli  # noqa: E402
from runner.task_types import VALID_TASK_TYPES  # noqa: E402

TASK_TYPE_DESCRIPTIONS = {
    "steam_page_review": "Steam 商店页：信息架构、视觉传达、信任信号",
    "demo_first_play": "Demo 首玩：上手摩擦、手感、前 15 分钟体验",
    "concept_review": "概念评审：核心循环、差异化、可行性",
    "monetization_review": "付费设计：定价、付费边界、价值感知",
    "looking_for_party_post": "组队招募文案：社区文案、传播性、社交吸引力",
    "update_announcement_review": "更新公告：补丁说明、信任强化、留存信号",
    "devlog_review": "开发日志：开发叙事、社区互动",
    "kickstarter_review": "众筹页：活动页、回报档位、支持者信任",
    "localization_review": "本地化：翻译质量、文化适配",
    "discord_community_review": "Discord 社区：社区管理、语气、互动模式",
    "product_feedback_review": "产品反馈评审：通用产品反馈收集与解读，不限游戏",
    "pricing_page_review": "定价页评审：定价分层、价值传达、信任信号，不限游戏",
    "onboarding_review": "新手引导评审：首次使用体验、上手摩擦，不限游戏",
    "pitch_review": "创业项目评审：BP/路演/申报表，投资人与尽调视角，不限行业",
}

# 描述表必须与单一注册表（runner/task_types.py）完全对齐——漂移就在导入时炸，
# 而不是等到用户调用工具才发现"注册表认的类型这里没有描述"或反之。
assert set(TASK_TYPE_DESCRIPTIONS) == set(VALID_TASK_TYPES), (
    "TASK_TYPE_DESCRIPTIONS 与 runner/task_types.py 的 VALID_TASK_TYPES 不一致："
    f"仅描述表有 {set(TASK_TYPE_DESCRIPTIONS) - set(VALID_TASK_TYPES)}；"
    f"仅注册表有 {set(VALID_TASK_TYPES) - set(TASK_TYPE_DESCRIPTIONS)}"
)

def _discover_persona_packs():
    """人格包清单从 src/personas/ 现算，不写死。

    写死过一次的代价：这里曾是一份手写的 10 项列表，而 src/personas/ 下已经有 11 个
    YAML（新增的 launch-compliance 没人补进来）——于是 MCP 客户端**根本选不到**
    那个包，run_synthetic_review 会直接以"未知人格包"拒绝。加包的人不会想到
    还要来改这个列表，所以下次一定还会漏。现算就不会。

    排序固定（sorted）：这个列表会出现在 MCP 工具的参数说明里，顺序抖动会让
    客户端缓存的 schema 无谓失效。
    """
    import glob

    paths = glob.glob(os.path.join(_SRC_DIR, "personas", "*.yaml"))
    packs = sorted(os.path.splitext(os.path.basename(p))[0] for p in paths)
    # 兜底：真出现空目录（打包漏文件之类）时不要静默返回空列表——那会让所有
    # 调用都以"未知人格包"失败，而错误信息指向的方向完全是错的。
    if not packs:
        raise RuntimeError(
            f"{os.path.join(_SRC_DIR, 'personas')} 下一个人格包 YAML 都没有，"
            "MCP 无法提供评审能力——先确认部署是否漏带了 src/personas/。"
        )
    return packs


PERSONA_PACKS = _discover_persona_packs()

VALID_MODES = ("quick", "standard", "full")

API_KEY_REQUIRED_MSG = (
    "未配置 ANTHROPIC_API_KEY。AudienceLens 评审必须使用真实 LLM——"
    "模拟数据没有任何评审价值。请在 MCP server 的环境变量中设置 ANTHROPIC_API_KEY 后重试；"
    "若仅想验证流水线是否可运行，可显式传入 allow_simulation=true（返回的将是带警告的占位数据）。"
)


def list_task_types() -> dict:
    """返回所有支持的评审任务类型及说明。"""
    return {
        "task_types": [
            {"id": tid, "description": desc}
            for tid, desc in TASK_TYPE_DESCRIPTIONS.items()
        ]
    }


def list_persona_packs() -> dict:
    """返回所有可用的人格包名称。"""
    return {"persona_packs": PERSONA_PACKS}


def list_personas(pack: str = "game-core") -> dict:
    """返回指定人格包内的人格 id/name/archetype 列表。"""
    if pack not in PERSONA_PACKS:
        return {"error": f"未知人格包: {pack}。可用: {', '.join(PERSONA_PACKS)}"}
    path = os.path.join(_SRC_DIR, "personas", f"{pack}.yaml")
    from runner.panel_selector import load_personas

    personas = load_personas(path)
    return {
        "pack": pack,
        "count": len(personas),
        "personas": [
            {
                "id": p.get("id", ""),
                "name": p.get("name", ""),
                "archetype": p.get("archetype", ""),
            }
            for p in personas
        ],
    }


def _resolve_artifact_bundle(artifact: str) -> dict:
    """把入参解析成材料包 dict。

    artifact 支持三种形式：
      - 已存在的 .json/.yaml/.yml 文件路径
      - 直接的 JSON 字符串（含 title/materials 等字段）
      - 纯文本材料（自动包成单条 material）
    """
    artifact = (artifact or "").strip()
    if not artifact:
        raise ValueError("artifact 不能为空")

    if os.path.isfile(artifact):
        return runner_cli.load_artifact_bundle(artifact)

    # 尝试当作 JSON 字符串
    if artifact.startswith("{"):
        try:
            data = json.loads(artifact)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 兜底：当作纯文本材料
    return {
        "title": "（内联文本材料）",
        "materials": [{"type": "text", "description": artifact}],
    }


def run_synthetic_review(
    task_type: str,
    artifact: str,
    mode: str = "standard",
    personas_pack: str = "game-core",
    allow_simulation: bool = False,
) -> dict:
    """运行一次合成观众评审，返回结构化报告。

    Args:
        task_type: 评审任务类型，见 list_task_types
        artifact: 材料（文件路径 / JSON 字符串 / 纯文本）
        mode: quick | standard | full
        personas_pack: 人格包名，见 list_persona_packs
        allow_simulation: 无 API key 时是否允许返回带警告的模拟占位数据

    Returns:
        含 report / calibration / cost_summary / simulated 的 dict；
        参数非法或缺 key 时返回 {"error": ...}
    """
    if task_type not in TASK_TYPE_DESCRIPTIONS:
        return {
            "error": f"未知任务类型: {task_type}。可用: {', '.join(TASK_TYPE_DESCRIPTIONS)}"
        }
    if mode not in VALID_MODES:
        return {"error": f"未知模式: {mode}。可用: {', '.join(VALID_MODES)}"}
    if personas_pack not in PERSONA_PACKS:
        return {"error": f"未知人格包: {personas_pack}。可用: {', '.join(PERSONA_PACKS)}"}

    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key and not allow_simulation:
        return {"error": API_KEY_REQUIRED_MSG, "needs_api_key": True}

    try:
        bundle = _resolve_artifact_bundle(artifact)
    except (ValueError, FileNotFoundError) as e:
        return {"error": f"材料解析失败: {e}"}

    personas_path = os.path.join(_SRC_DIR, "personas", f"{personas_pack}.yaml")
    # mode 必须真的传下去。以前上面校验完 mode 合法性就把它丢了，run_panel 收到 None
    # 走全量流程：不截人数、交叉质询和校准全跑。也就是 MCP 客户端选 quick 想省钱，
    # 实际按最贵的档在花，而且没有任何地方看得出来。
    # 同型的 bug 在 src/cli.py 修过一次（那边注释写着"以前只在 _print 里露个脸就被丢掉"），
    # 当时没意识到 MCP 这条通道有一份一模一样的断链——这正是本仓库最常见的
    # "一条链路修了、另一条没修"。
    result = runner_cli.run_panel(
        task_type=task_type,
        artifact_bundle=bundle,
        personas_path=personas_path,
        mode=mode,
    )

    return {
        "report": result["report"],
        "calibration": result.get("calibration"),
        "cost_summary": result.get("cost_summary"),
        "simulated": result.get("simulated", False),
    }
