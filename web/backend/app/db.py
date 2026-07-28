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
    """建表 + 轻量迁移 + 孤儿任务收尸。

    生产环境应改用 Alembic（见 docs/MAINTENANCE.md「数据库迁移」）。
    这里的 create_all 只新增缺失的表，不会改动已有表结构。
    """
    Base.metadata.create_all(engine)
    _legacy_migrations()
    _reap_orphans()


def _reap_orphans() -> None:
    """进程重启后，上一个进程遗留的 queued/running 任务永远不会有人接手
    （队列在内存里）——不收尸的话对应评审就一直"进行中"转圈到天荒地老。
    启动时统一标记 failed，用户端能看到明确的失败提示并重新发起。"""
    from datetime import datetime, timezone

    from sqlalchemy import text

    msg = "服务重启，任务中断——请重新发起评审"
    now = datetime.now(timezone.utc)
    with engine.connect() as conn:
        jobs = conn.execute(
            text(
                "UPDATE jobs SET status='failed', error_message=:msg, finished_at=:now "
                "WHERE status IN ('queued','running')"
            ),
            {"msg": msg, "now": now},
        )
        reviews = conn.execute(
            text(
                "UPDATE reviews SET status='failed', error_message=:msg, completed_at=:now "
                "WHERE status IN ('pending','running')"
            ),
            {"msg": msg, "now": now},
        )
        conn.commit()
    if jobs.rowcount or reviews.rowcount:
        import logging

        logging.getLogger("audiencelens").warning(
            "启动收尸：标记 %d 个孤儿 job、%d 个孤儿 review 为 failed",
            jobs.rowcount,
            reviews.rowcount,
        )


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
    if "skill_type" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN skill_type VARCHAR")
    if "project_key" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN project_key VARCHAR")
    if "enable_evaluation" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN enable_evaluation BOOLEAN DEFAULT 0 NOT NULL")
    if "input_tokens" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN input_tokens INTEGER DEFAULT 0 NOT NULL")
    if "output_tokens" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN output_tokens INTEGER DEFAULT 0 NOT NULL")

    if "persona_outputs" in inspector.get_table_names():
        po_columns = {c["name"] for c in inspector.get_columns("persona_outputs")}
        if "input_tokens" not in po_columns:
            patches.append("ALTER TABLE persona_outputs ADD COLUMN input_tokens INTEGER DEFAULT 0 NOT NULL")
        if "output_tokens" not in po_columns:
            patches.append("ALTER TABLE persona_outputs ADD COLUMN output_tokens INTEGER DEFAULT 0 NOT NULL")

    if "usage_records" in inspector.get_table_names():
        ur_columns = {c["name"] for c in inspector.get_columns("usage_records")}
        if "input_tokens" not in ur_columns:
            patches.append("ALTER TABLE usage_records ADD COLUMN input_tokens INTEGER DEFAULT 0 NOT NULL")
        if "output_tokens" not in ur_columns:
            patches.append("ALTER TABLE usage_records ADD COLUMN output_tokens INTEGER DEFAULT 0 NOT NULL")

    if "user_api_keys" in inspector.get_table_names():
        key_columns = {c["name"] for c in inspector.get_columns("user_api_keys")}
        if "model" not in key_columns:
            patches.append("ALTER TABLE user_api_keys ADD COLUMN model VARCHAR")
        if "api_base" not in key_columns:
            patches.append("ALTER TABLE user_api_keys ADD COLUMN api_base VARCHAR")

    if "users" in inspector.get_table_names():
        user_columns = {c["name"] for c in inspector.get_columns("users")}
        if "is_guest" not in user_columns:
            patches.append("ALTER TABLE users ADD COLUMN is_guest BOOLEAN DEFAULT 0 NOT NULL")
        if "email_verified_at" not in user_columns:
            patches.append("ALTER TABLE users ADD COLUMN email_verified_at DATETIME")

    # ethics_reports 补归属列。老库里这张表没有 review_id，写进去的行
    # 既查不回来也删不掉，而 violations_json 里含用户内容摘录——等于
    # 隐私政策承诺的"删号即物理删除评审内容"有一个永久漏项。
    orphan_purge = False
    if "ethics_reports" in inspector.get_table_names():
        er_columns = {c["name"] for c in inspector.get_columns("ethics_reports")}
        if "review_id" not in er_columns:
            # SQLite 的 ADD COLUMN 不能带 FK，这里只加普通列；
            # 归属与级联删除由 ORM 侧的 relationship(cascade) 保证
            patches.append("ALTER TABLE ethics_reports ADD COLUMN review_id VARCHAR")
            patches.append(
                "CREATE INDEX IF NOT EXISTS ix_ethics_reports_review_id ON ethics_reports (review_id)"
            )
            # 存量孤儿行：review_id 为空 = 无法回指到任何评审、任何用户，
            # 也就无法在删号时被删掉。留着它们就是留着一堆无主的用户内容摘录，
            # 与隐私承诺直接冲突；且它们是"只读接口反复 INSERT"这个 bug 的
            # 产物（同一份内容被重复算了 N 遍），没有任何保留价值 —— 直接清掉。
            orphan_purge = True

    if not patches:
        return
    with engine.connect() as conn:
        for sql in patches:
            conn.execute(text(sql))
        if orphan_purge:
            purged = conn.execute(text("DELETE FROM ethics_reports WHERE review_id IS NULL"))
            if purged.rowcount:
                import logging

                logging.getLogger("audiencelens").warning(
                    "迁移：清理 %d 行无归属的伦理报告（含用户内容摘录，无法归属即无法按承诺删除）",
                    purged.rowcount,
                )
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
