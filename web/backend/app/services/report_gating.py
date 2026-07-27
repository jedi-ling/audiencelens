"""匿名/登录用户看到的报告详情分级。

"体验机会 + 登录看详情"：匿名能跑评审、能看执行摘要和第一条优先修复项，
其余内容（各角色视角、完整优先级列表、共识与分歧）需要登录解锁。
两条评审链路（旧的同步 /api/reviews、新的异步 /api/v2/reviews）共用这一份裁剪逻辑，
避免两处各写一套、日后改一处漏一处。
"""

from typing import Optional

# 追问回复的匿名体验版长度——留够一段实质内容（不是半句话就截断），
# 但明显短于完整回复，逼真实价值感留在"登录后"。
CHAT_REPLY_PREVIEW_CHARS = 80


def gate_chat_reply_for_anonymous(content: str) -> dict:
    """匿名用户追问的回复只给前 N 字 + 明确的"登录看完整"信号。

    真实完整回复已经在 chat_service.send_message 里原样存进
    ReviewChatMessage 了——这里只裁剪"返回给这次请求的内容"，
    登录后同一条历史记录（GET /chat）会拿到完整内容，不需要重新问一遍。
    """
    if len(content) <= CHAT_REPLY_PREVIEW_CHARS:
        # 本来就短，裁了也没意义，还可能造成"登录后应该更长"的错误预期
        return {"content": content, "is_gated": False, "full_length": len(content)}
    return {
        "content": content[:CHAT_REPLY_PREVIEW_CHARS].rstrip() + "…",
        "is_gated": True,
        "full_length": len(content),
    }


def gate_markdown_for_anonymous(markdown: Optional[str]) -> Optional[str]:
    """匿名一律不给 markdown 全文——返回 None。

    markdown 是整份报告的纯文本镜像：各角色视角、完整优先级列表、共识与分歧
    全在里面。gate_report_for_anonymous 辛苦裁掉的东西，只要 markdown 原样
    发出去就等于没裁——这正是曾经的实际情况：GET /api/reviews/{id}/report
    裁了 report_json，紧接着一行 `report_markdown=review.report_markdown`
    把全文又漏了出去，登录墙形同虚设。

    这里刻意不做"截断前 N 字"：截断点落在哪一节取决于报告长度和结构，
    不是一条能被测试钉死的安全边界。宁可不给，让前端走 report_json
    的体验版渲染（那份是结构化裁剪，边界明确）。
    """
    return None


def gate_persona_outputs_for_anonymous(outputs) -> list:
    """裁掉每位角色的**输出内容**，但保留他们的**存在与状态**。

    要护的是"各角色怎么看"（output_json / validation_result）——那是本产品
    要卖的东西，不能从 persona_outputs 这个侧门免费拿走。

    但**不能整个列表清空**：进度页正是靠这个列表画"6 位角色，3 位已完成"的。
    清空的后果是匿名用户全程看到"0 位角色"，跑完还是 0——这恰恰是本仓库
    反复出现过的那个症状（"评审明明跑了，页面显示 0 条修复项 0 位角色"）。
    付费墙该挡的是内容，不是"你的评审到底在不在跑"这个基本事实。
    """
    if not outputs:
        return []
    gated = []
    for po in outputs:
        # Pydantic v2 模型：model_copy 不改原对象（原对象还挂在 ORM 上，改了会写库）
        if hasattr(po, "model_copy"):
            gated.append(po.model_copy(update={"output_json": None, "validation_result": None}))
        else:
            gated.append(po)
    return gated


def gate_report_for_anonymous(report: Optional[dict]) -> Optional[dict]:
    """裁剪报告为匿名可见的"体验版"。

    **诚实声明一律不裁**——这是这个函数唯一不能让步的地方：
      · simulation_notice —— "这是模拟数据"
      · error            —— 评审失败时的真实原因（失败的评审 report_json 就是 {"error": ...}，
                            当初漏了这个键，匿名用户的失败评审会被裁成一份"什么都没有
                            但看起来正常"的空报告，连为什么失败都看不到）
      · degradation      —— "本次有 N 位人格没跑成，结论只据 M 位得出"
                            （字段名与引擎链路 runner/cli.py 一致，两条链路同一口径）

    把坏消息裁掉、只留好看的部分，那不叫体验版，那叫误导。付费墙可以挡"价值"，
    不能挡"真相"。
    """
    if not report:
        return report
    # 失败报告不是"内容"，没有可裁的价值，原样透出（里面只有 error）
    if "error" in report and not report.get("executive_summary"):
        return report
    priority_fixes = report.get("priority_fixes") or []
    persona_notes = report.get("persona_notes") or []
    return {
        "meta": report.get("meta"),
        "executive_summary": report.get("executive_summary"),
        "simulation_notice": report.get("simulation_notice"),
        "error": report.get("error"),
        "degradation": report.get("degradation"),
        "priority_fixes": priority_fixes[:1],
        "persona_notes": [],
        "consensus": None,
        "major_disagreements": [],
        "cross_examination": None,
        "is_gated": True,
        "gated_counts": {
            "priority_fixes_hidden": max(0, len(priority_fixes) - 1),
            "persona_notes_hidden": len(persona_notes),
        },
    }
