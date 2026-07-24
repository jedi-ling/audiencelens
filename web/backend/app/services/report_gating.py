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


def gate_report_for_anonymous(report: Optional[dict]) -> Optional[dict]:
    """裁剪报告为匿名可见的"体验版"。绝不裁剪 simulation_notice 这类诚实声明。"""
    if not report:
        return report
    priority_fixes = report.get("priority_fixes") or []
    persona_notes = report.get("persona_notes") or []
    return {
        "meta": report.get("meta"),
        "executive_summary": report.get("executive_summary"),
        "simulation_notice": report.get("simulation_notice"),
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
