"""管理员操作审计流水——只增不改，记录"谁在何时改了什么"。

"谁"这一栏（actor）此前是缺的：文档里说具名管理员账号的意义就是"能知道是谁
干的"，而 require_admin 解析出来的 admin_user 被塞进 request.state 之后
**全仓库没有任何地方读过它**，审计行里一律没有署名。于是"具名账号"这个功能
在它唯一的目的上是空转的。现在 record() 收 actor：
  · 具名账号会话令牌 → 用户名，如 "alice-admin"
  · 静态 AL_ADMIN_TOKEN（bootstrap / 逃生舱）→ "static-token"
  · 没传（老调用点）→ NULL，如实表示"这条记录不知道是谁做的"，不编造。
"""

import json
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.models import AdminAuditLog

# 用静态主密钥操作时的署名。不写 None，因为"用主密钥做的"本身就是一条信息
# （它意味着这次操作没有具名账号可追责），与"这条老记录没记署名"必须分得开。
ACTOR_STATIC_TOKEN = "static-token"


def record(
    db: Session,
    action: str,
    target: Optional[str] = None,
    detail: Optional[dict] = None,
    actor: Optional[str] = None,
) -> None:
    db.add(
        AdminAuditLog(
            action=action,
            target=target,
            actor=actor,
            detail=json.dumps(detail, ensure_ascii=False, default=str) if detail is not None else None,
        )
    )
    db.commit()


def list_recent(db: Session, limit: int = 100) -> List[dict]:
    rows = (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    out = []
    for r in rows:
        detail: Any = None
        if r.detail:
            try:
                detail = json.loads(r.detail)
            except (TypeError, ValueError):
                detail = r.detail
        out.append(
            {
                "id": r.id,
                "action": r.action,
                "target": r.target,
                "actor": r.actor,
                "detail": detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return out
