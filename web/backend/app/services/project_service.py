"""对话分组：CC Desktop 风格侧栏里的"项目"。

与 Review.project_key（自由文本标签）是两套并存的系统，见 models.Project
的类文档。这里只管 Project 实体本身和它与 Conversation 的挂靠关系。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Conversation, Project

ANON = "anonymous"

# 单用户项目数上限。没有上限的话，脚本化滥用可以无限建空项目撑爆列表接口——
# 项目本身几乎零成本（一行记录），但列表页要为每个项目算一次对话计数，
# 数量不受控就是一个廉价的放大攻击面。
MAX_PROJECTS_PER_USER = 200
NAME_MAX_CHARS = 80


def _owner(user_id: Optional[str]) -> str:
    return user_id or ANON


def create_project(db: Session, user_id: Optional[str], name: str) -> Project:
    name = (name or "").strip()[:NAME_MAX_CHARS]
    if not name:
        raise ValueError("项目名不能为空")
    owner = _owner(user_id)
    count = db.query(func.count(Project.id)).filter(Project.user_id == owner).scalar() or 0
    if count >= MAX_PROJECTS_PER_USER:
        raise ValueError(f"最多创建 {MAX_PROJECTS_PER_USER} 个项目")
    project = Project(user_id=owner, name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_owned(db: Session, project_id: str, user_id: Optional[str]) -> Optional[Project]:
    """取一个属于该用户的项目。不属于则 None——调用方回 404 不回 403，
    403 等于确认该 id 存在，可用来枚举他人项目 id（与 conversation_service 同一口径）。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        return None
    if _owner(project.user_id) != _owner(user_id):
        return None
    return project


def list_projects(db: Session, user_id: Optional[str]) -> List[Project]:
    return (
        db.query(Project)
        .filter(Project.user_id == _owner(user_id))
        .order_by(Project.updated_at.desc())
        .all()
    )


def conversation_counts(db: Session, project_ids: List[str]) -> Dict[str, int]:
    """批量取每个项目下的对话数，避免侧栏每个项目卡片各发一次查询（N+1）。"""
    if not project_ids:
        return {}
    rows = (
        db.query(Conversation.project_id, func.count(Conversation.id))
        .filter(Conversation.project_id.in_(project_ids))
        .group_by(Conversation.project_id)
        .all()
    )
    return {pid: n for pid, n in rows}


def rename_project(db: Session, project: Project, name: str) -> Project:
    name = (name or "").strip()[:NAME_MAX_CHARS]
    if not name:
        raise ValueError("项目名不能为空")
    project.name = name
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> int:
    """删除项目。归属的对话**不删除**，只是解除挂靠（回到"未分组"）。

    显式 UPDATE 而不是指望数据库的 ON DELETE SET NULL：SQLite 默认不校验
    外键约束，那条子句在 SQLite 下是摆设；这里在应用层把话说清楚，
    两种数据库后端行为一致。返回解绑的对话数，供调用方回给前端确认。
    """
    unlinked = (
        db.query(Conversation)
        .filter(Conversation.project_id == project.id)
        .update({"project_id": None}, synchronize_session=False)
    )
    db.delete(project)
    db.commit()
    return unlinked


def to_dict(project: Project, conversation_count: int = 0) -> Dict[str, object]:
    return {
        "id": project.id,
        "name": project.name,
        "conversation_count": conversation_count,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }
