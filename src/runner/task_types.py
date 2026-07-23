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
