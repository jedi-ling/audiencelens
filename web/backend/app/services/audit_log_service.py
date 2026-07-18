"""管理员操作审计流水——只增不改，记录"谁在何时改了什么"。

不记录"谁"（当前只有单一共享的 X-Admin-Token，没有多管理员身份），
只记录动作、目标和变更详情——比完全没有审计强，多管理员场景需要先接入
独立的管理员身份体系（见 docs/MAINTENANCE.md）。
"""

import json
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.models import AdminAuditLog


def record(db: Session, action: str, target: Optional[str] = None, detail: Optional[dict] = None) -> None:
    db.add(
        AdminAuditLog(
            action=action,
            target=target,
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
                "detail": detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return out
