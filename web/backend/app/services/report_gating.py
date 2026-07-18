"""匿名/登录用户看到的报告详情分级。

"体验机会 + 登录看详情"：匿名能跑评审、能看执行摘要和第一条优先修复项，
其余内容（各角色视角、完整优先级列表、共识与分歧）需要登录解锁。
两条评审链路（旧的同步 /api/reviews、新的异步 /api/v2/reviews）共用这一份裁剪逻辑，
避免两处各写一套、日后改一处漏一处。
"""

from typing import Optional


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
