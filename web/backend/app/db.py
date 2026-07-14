"""数据库会话与建表。

SQLite → Postgres 迁移：只需改 AL_DATABASE_URL，
connect_args 里的 check_same_thread 仅对 sqlite 生效（见下）。
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    db_path = settings.database_url.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """建表 + 轻量迁移。

    生产环境应改用 Alembic（见 docs/MAINTENANCE.md「数据库迁移」）。
    这里的 create_all 只新增缺失的表，不会改动已有表结构。
    """
    Base.metadata.create_all(engine)
    _legacy_migrations()


def _legacy_migrations() -> None:
    """历史遗留的列补丁；新表不需要写在这里。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "reviews" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("reviews")}
    patches = []
    if "mode" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN mode VARCHAR DEFAULT 'standard' NOT NULL")
    if "user_id" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN user_id VARCHAR")
    if "error_message" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN error_message TEXT")
    if not patches:
        return
    with engine.connect() as conn:
        for sql in patches:
            conn.execute(text(sql))
        conn.commit()


def get_db():
    """FastAPI 依赖：每请求一个会话。"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def session_scope() -> Session:
    """给后台任务用（不在请求上下文里）——调用方负责 close。"""
    return SessionLocal()
