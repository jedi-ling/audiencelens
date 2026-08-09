"""对话持续化：把评审**之前**那段来回澄清存下来。

为什么需要这一层（而不是复用 ReviewChatMessage）：
ReviewChatMessage 的主键关系是挂在 review 上的，没有 review 就没有落点。
但用户投入描述最多的时刻恰恰在评审被创建之前——他在跟系统说清"我想评审
什么、给谁看、在意哪些点"。那段内容此前活在前端的 useState/useRef 里，
刷新即永久丢失，而且丢的是最不愿意重打一遍的部分。

归属口径与 Review 保持一字不差（匿名为 "anonymous"）：两套历史列表若
对同一个访客给出不同的可见范围，用户会看到"我的评审在、对话没了"。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Conversation, ConversationMessage

# 单段对话的消息上限。没有上限时，一个长期开着的页面可以把单条对话喂到
# 无限大，之后每次打开它都要全量拉回——先撑爆前端，再撑爆导出接口。
MAX_MESSAGES_PER_CONVERSATION = 500
# 标题取首条用户消息的前 N 字。存下来而不是每次现算：现算要为了列表里的
# 一行标题去 JOIN 消息表。
TITLE_MAX_CHARS = 40

ANON = "anonymous"


def _owner(user_id: Optional[str]) -> str:
    """归属口径的唯一出处。Review 用的是 (user_id or "anonymous")，
    这里必须一致，否则匿名用户的对话与评审会落进两个不同的桶。"""
    return user_id or ANON


def create_conversation(
    db: Session, user_id: Optional[str], title: Optional[str] = None
) -> Conversation:
    conv = Conversation(user_id=_owner(user_id), title=(title or None))
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_owned(db: Session, conversation_id: str, user_id: Optional[str]) -> Optional[Conversation]:
    """取一条属于该用户的对话，不属于则返回 None。

    调用方一律回 404 而不是 403：403 等于确认"这个 id 存在但不是你的"，
    可以被用来枚举他人对话 id。这与 platform.py 里 review 的处理一致。
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv is None:
        return None
    if _owner(conv.user_id) != _owner(user_id):
        return None
    return conv


def list_conversations(
    db: Session, user_id: Optional[str], limit: int = 50, offset: int = 0
) -> List[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == _owner(user_id))
        # 按 updated_at 而不是 created_at：否则你刚在一段老对话里发了消息，
        # 它还沉在列表底部。
        .order_by(Conversation.updated_at.desc())
        .limit(max(1, min(limit, 200)))
        .offset(max(0, offset))
        .all()
    )


def append_message(
    db: Session,
    conv: Conversation,
    role: str,
    content: str,
    meta: Optional[Dict[str, Any]] = None,
) -> ConversationMessage:
    """追加一条消息。seq 由服务端分配，前端不参与编号。

    前端算 seq 会在两种常见情形下出错：两条消息并发提交（各自读到同样的
    当前长度），以及重放历史后接着发（本地数组下标与库里的 seq 不同源）。
    """
    if role not in ("user", "assistant", "system"):
        raise ValueError(f"未知的 role: {role}")

    count = (
        db.query(func.count(ConversationMessage.id))
        .filter(ConversationMessage.conversation_id == conv.id)
        .scalar()
        or 0
    )
    if count >= MAX_MESSAGES_PER_CONVERSATION:
        raise ValueError(
            f"单段对话最多 {MAX_MESSAGES_PER_CONVERSATION} 条消息，请新建对话继续"
        )

    # seq 取"当前最大值 + 1"而不是 count + 1：将来若支持删除单条消息，
    # count 会回退并复用已用过的 seq，把两条消息排到同一个位置。
    max_seq = (
        db.query(func.max(ConversationMessage.seq))
        .filter(ConversationMessage.conversation_id == conv.id)
        .scalar()
    )
    msg = ConversationMessage(
        conversation_id=conv.id,
        seq=(max_seq or 0) + 1,
        role=role,
        content=content,
        meta_json=meta,
    )
    db.add(msg)

    # 首条用户消息顺手当标题，省得列表里全是"未命名对话"
    if not conv.title and role == "user" and content.strip():
        conv.title = content.strip()[:TITLE_MAX_CHARS]

    # onupdate 只在该行**本身**有列被改动时才触发；仅插入子表不会更新它，
    # 于是新消息不断进来而对话永远排在列表末尾。显式碰一下。
    conv.updated_at = func.now()
    db.add(conv)

    db.commit()
    db.refresh(msg)
    return msg


def list_messages(db: Session, conv: Conversation) -> List[ConversationMessage]:
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.seq.asc())
        .all()
    )


def link_review(db: Session, conv: Conversation, review_id: str) -> None:
    """把对话与它产出的评审关联起来（弱引用，见 models.Conversation）。"""
    conv.review_id = review_id
    db.add(conv)
    db.commit()


def set_project(db: Session, conv: Conversation, project_id: Optional[str]) -> None:
    """把对话挂到某个项目下，或传 None 移回"未分组"。

    项目归属校验（project_id 是否存在、是否属于同一用户）由调用方
    （API 层）负责——这里只管赋值，不重复查一次 Project 表。
    """
    conv.project_id = project_id
    db.add(conv)
    db.commit()


def list_by_project(db: Session, user_id: Optional[str], project_id: Optional[str]) -> List[Conversation]:
    """列出某个项目下（或 project_id=None 时"未分组"）的对话。"""
    q = db.query(Conversation).filter(Conversation.user_id == _owner(user_id))
    q = q.filter(Conversation.project_id.is_(None)) if project_id is None else q.filter(
        Conversation.project_id == project_id
    )
    return q.order_by(Conversation.updated_at.desc()).all()


def delete_conversation(db: Session, conv: Conversation) -> None:
    """删对话。走 ORM 的 delete 以触发 messages 的级联，
    批量 delete() 会绕过级联留下孤儿消息行。"""
    db.delete(conv)
    db.commit()


def to_dict(conv: Conversation, with_messages: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": conv.id,
        "title": conv.title,
        "review_id": conv.review_id,
        "project_id": conv.project_id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }
    if with_messages:
        out["messages"] = [
            {
                "id": m.id,
                "seq": m.seq,
                "role": m.role,
                "content": m.content,
                "meta": m.meta_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in sorted(conv.messages, key=lambda x: x.seq)
        ]
    return out
