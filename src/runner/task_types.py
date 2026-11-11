"""任务类型单一注册表——全仓库唯一权威源。

此前同一份"合法任务类型"清单散落四处各自维护：
    runner/cli.py 的 VALID_TASK_TYPES（引擎校验）
    web/backend intent_service 的 VALID_TASK_TYPES（意图解析）
    web/backend services 的 TASK_TYPES 元数据字典（/api/task-types 展示）
    src/mcp_tools.py 的 TASK_TYPE_DESCRIPTIONS（MCP 工具）
四处漂移的直接后果：services 元数据里多出 4 个引擎根本不认的类型
（app_store_review / social_media_post / video_ad_review / landing_page_review，
无 panel 预设、无人格亲和度），前端把它们当可选项展示，用户选了创建必 400。

新增任务类型的完整清单（缺一不可）：
    1. 本文件 VALID_TASK_TYPES 加 id
    2. src/presets/panel-presets.yaml 加面板预设
    3. 人格包里补 task_affinity
    4. web/backend services TASK_TYPES 加展示元数据（stance/score 维度）
    5. src/mcp_tools.py TASK_TYPE_DESCRIPTIONS 加一句话描述
"""

VALID_TASK_TYPES = [
    "steam_page_review",
    "demo_first_play",
    "concept_review",
    "monetization_review",
    "looking_for_party_post",
    "update_announcement_review",
    "devlog_review",
    "kickstarter_review",
    "localization_review",
    "discord_community_review",
    # 通用产品向（不限游戏）——见 src/personas/general-consumer.yaml
    "product_feedback_review",
    "pricing_page_review",
    "onboarding_review",
    # 创业项目评审（BP/路演/申报表）——见 src/personas/startup-panel.yaml
    "pitch_review",
]


# ---------------------------------------------------------------------------
# 任务类型 → 默认人格包。全仓库唯一权威源：引擎（run_panel）、CLI、MCP 工具和
# web/backend 的 intent_service 都从这里读。
#
# 为什么放在引擎里而不是后端：没传人格包时 run_panel 以前一律回落到 game-core，
# 于是"评定价页"会被悄悄塞给游戏玩家人格——报告照常生成，看不出任何异常。这个错
# 在生成样例报告时发生过两次（2026-11-04、2026-11-11），两次都是脚本没传 personas_path。
# 后端早就有一份映射，但引擎读不到它。
#
# 新增任务类型时必须在这里登记；没登记的类型 default_pack_for_task_type 直接报错，
# 不回落到任何默认包。
DEFAULT_PACK_BY_TASK_TYPE = {
    "steam_page_review": "game-core",
    "demo_first_play": "game-core",
    "concept_review": "game-core",
    "monetization_review": "game-core",
    "looking_for_party_post": "game-core",
    "update_announcement_review": "game-core",
    "devlog_review": "game-core",
    "kickstarter_review": "game-core",
    "localization_review": "game-core",
    "discord_community_review": "game-core",
    "product_feedback_review": "general-consumer",
    "pricing_page_review": "general-consumer",
    "onboarding_review": "general-consumer",
    "pitch_review": "startup-panel",
}


def default_pack_for_task_type(task_type: str) -> str:
    """这个任务类型在没指定人格包时该用哪个包。没登记就报错，不猜。"""
    try:
        return DEFAULT_PACK_BY_TASK_TYPE[task_type]
    except KeyError:
        raise ValueError(
            f"任务类型 {task_type!r} 没有登记默认人格包（src/runner/task_types.py 的 "
            "DEFAULT_PACK_BY_TASK_TYPE）。请显式传入人格包，或先在那里登记。"
        ) from None


def default_personas_path(task_type: str, personas_dir: str) -> str:
    """default_pack_for_task_type 对应的 yaml 路径。"""
    import os

    return os.path.join(personas_dir, f"{default_pack_for_task_type(task_type)}.yaml")


def pack_mismatch_warning(task_type: str, personas_path: str):
    """显式传入的人格包和任务类型登记的默认包不一致时，返回一句警告；一致或无法判断返回 None。

    不是错误：拿别的包评某类材料是合法用法（比如用 mobile-f2p 评 Steam 页）。
    但它必须看得见——悄悄用错包正是这里要防的事。
    """
    import os

    expected = DEFAULT_PACK_BY_TASK_TYPE.get(task_type)
    given = os.path.splitext(os.path.basename(personas_path or ""))[0]
    if not expected or not given or given == expected:
        return None
    return (
        f"人格包 {given!r} 不是任务类型 {task_type!r} 登记的默认包 {expected!r}。"
        "如果是有意为之可以忽略；否则请检查调用方传入的人格包。"
    )
