"""报告出来后的真对话——追问结论，或直接找某个虚拟人格聊。

此前"多轮对话"名不副实：AskPage 的多轮只是把用户历史发言拼接后重新过一遍
无状态的 intent_service（决定任务类型/技能），报告生成后就是终点——不能追问，
更不能跟某个具体人格（比如 P15 毒舌差评者）对话。这里补的是报告产出*之后*
的第二段对话，有独立的持久化上下文（ReviewChatMessage），每次追问都真的把
之前聊过的内容带给模型，而不是每次都从零开始。

两种 thread（用 persona_id 是否为空区分，同一 review 下互不干扰）：
    综合评审团：追问报告结论本身（"为什么定价页评分低"），语气是评审团口吻
    单个人格：跟该人格的 identity_summary/behavior_profile/communication_style
              保持人设一致地聊（不是通用助手腔）
"""

import os
import sys
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest
from app.models import Review, ReviewChatMessage

_SRC = os.path.join(settings.repo_root, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

MAX_HISTORY_TURNS = 12  # 单条 thread 最多带这么多轮历史进 prompt，避免越聊越贵


def _find_persona(review: Review, persona_id: str) -> Optional[dict]:
    if not review.persona_pack:
        return None
    from runner.panel_selector import load_personas

    path = os.path.join(settings.repo_root, "src", "personas", f"{review.persona_pack}.yaml")
    if not os.path.isfile(path):
        return None
    for p in load_personas(path):
        if p["id"] == persona_id:
            return p
    return None


def _find_persona_note(review: Review, persona_id: str) -> Optional[dict]:
    for note in (review.report_json or {}).get("persona_notes", []) or []:
        if note.get("persona_id") == persona_id:
            return note
    return None


def _report_summary_text(review: Review) -> str:
    report = review.report_json or {}
    summary = report.get("executive_summary") or {}
    fixes = report.get("priority_fixes") or []
    notes = report.get("persona_notes") or []
    lines = [
        f"标题：{review.target_title or '(未命名)'}",
        f"整体建议：{summary.get('primary_recommendation', '(无)')}",
        f"发布风险：{summary.get('release_risk', '(无)')}",
        f"证据质量：{summary.get('evidence_quality', '(无)')}",
        "优先修复项：",
    ]
    for f in fixes[:8]:
        lines.append(f"  - [{f.get('severity', '?')}] {f.get('title', '')}：{f.get('why_it_matters', '')}")
    lines.append("各人格立场：")
    for n in notes:
        lines.append(f"  - {n.get('persona_name', n.get('persona_id', ''))}：{n.get('primary_stance', '')}")
    return "\n".join(lines)


def _build_prompt(
    review: Review, history: List[ReviewChatMessage], user_message: str, persona: Optional[dict], persona_note: Optional[dict]
) -> str:
    if persona is not None:
        from runner.persona_agent import _minify_persona

        persona_yaml = _minify_persona(persona)
        system = (
            f"你正在扮演一个虚拟评审人格，完全代入这个人设跟用户对话，不要跳出角色说"
            f"「作为AI」之类的话。你已经评审过用户的产品/项目，以下是你的人设与你当时的"
            f"评审意见：\n\n人设：\n{persona_yaml}\n\n你当时的评审意见：\n"
            f"{persona_note or '（未找到你当时的具体意见，凭人设自然回应）'}\n\n"
            f"回答要符合你的 communication_style，简体中文，不要写成正式报告腔。"
        )
    else:
        system = (
            "你是这次多人格评审的召集人，代表评审团整体回答用户对报告的追问。"
            "以下是完整报告摘要：\n\n" + _report_summary_text(review) + "\n\n"
            "如实基于报告内容回答，报告里没有的信息就说没有，不要编造。简体中文作答。"
        )

    turns = []
    for m in history[-MAX_HISTORY_TURNS:]:
        speaker = "用户" if m.role == "user" else "你"
        turns.append(f"{speaker}：{m.content}")
    turns.append(f"用户：{user_message}")
    turns.append("你：")
    return system + "\n\n对话记录：\n" + "\n".join(turns)


def send_message(db: Session, review: Review, message: str, persona_id: Optional[str] = None) -> ReviewChatMessage:
    if review.status != "completed":
        raise BadRequest("评审尚未完成，还不能追问")
    if not message or not message.strip():
        raise BadRequest("消息不能为空")

    from app.services import key_service
    from runner.llm_client import chat_completion

    persona = _find_persona(review, persona_id) if persona_id else None
    if persona_id and persona is None:
        raise BadRequest(f"未找到人格 {persona_id}")
    persona_note = _find_persona_note(review, persona_id) if persona_id else None

    history = (
        db.query(ReviewChatMessage)
        .filter(ReviewChatMessage.review_id == review.id, ReviewChatMessage.persona_id == persona_id)
        .order_by(ReviewChatMessage.created_at)
        .all()
    )

    user_msg = ReviewChatMessage(review_id=review.id, persona_id=persona_id, role="user", content=message)
    db.add(user_msg)
    db.commit()

    resolved = key_service.resolve_key(db, review.user_id or "anonymous")
    prompt = _build_prompt(review, history, message, persona, persona_note)
    reply_text, _in_tok, _out_tok = chat_completion(
        model=resolved.model or settings.intent_model,
        prompt=prompt,
        api_key=resolved.key,
        provider=resolved.provider,
        api_base=resolved.api_base,
        max_tokens=1200,
    )

    assistant_msg = ReviewChatMessage(
        review_id=review.id, persona_id=persona_id, role="assistant", content=reply_text.strip()
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


def list_messages(db: Session, review_id: str, persona_id: Optional[str] = None) -> List[ReviewChatMessage]:
    return (
        db.query(ReviewChatMessage)
        .filter(ReviewChatMessage.review_id == review_id, ReviewChatMessage.persona_id == persona_id)
        .order_by(ReviewChatMessage.created_at)
        .all()
    )
