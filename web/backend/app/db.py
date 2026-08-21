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
    启动时统一标记 failed，用户端能看到明确的失败提示并重新发起。

    标 failed 只是**用户看得见**的那一半。另一半是钱：这些评审在发起时就已经
    扣了 CDK 次数 / 占了日配额名额（见 quota_service.check_quota），而退还逻辑
    此前只存在于 review_service 的进程内异常分支——进程被重启的那一刻，
    那段代码根本没有机会跑。后果是用户花钱买的次数凭空消失，且账面上完全
    看不出来。所以收尸必须连计费一起收，见 _settle_reaped_reviews。
    """
    from datetime import datetime, timezone

    from sqlalchemy import text

    msg = "服务重启，任务中断——请重新发起评审"
    now = datetime.now(timezone.utc)
    with engine.connect() as conn:
        # 先把待收尸的评审捞出来：UPDATE 之后就分不清"这条是刚被我收尸的"
        # 还是"上一次启动就已经是 failed 的"了，而退款必须只针对前者。
        orphans = [
            (row[0], row[1])
            for row in conn.execute(
                text("SELECT id, user_id FROM reviews WHERE status IN ('pending','running')")
            ).fetchall()
        ]
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
    _settle_reaped_reviews(orphans)


def _settle_reaped_reviews(orphans) -> None:
    """被收尸的评审在计费侧也要收干净：退次数、还名额、清过期占位。

    为什么用 ORM 会话而不是上面那条裸连接：判定"这条评审当时花的是谁的钱"
    要读 jobs.payload（JSON 列），跨 SQLite/PostgreSQL 的裸 SQL 写法不一样；
    而退还本身要复用 quota_service 那两个幂等原语（它们以 review_id 为幂等键
    写 credit_ledger，可核对），不能在这里另写一份——同一件事两套实现正是
    本仓库反复出现"v2 修了 v1 没修"的根因。

    延迟导入 app.services：本模块被 app.services 间接依赖，模块级 import 会
    形成环；而 _reap_orphans 只在 init_db()（进程启动、模块早已加载完）里跑，
    这时导入是安全的。

    失败绝不静默：每条评审单独兜异常并打 ERROR 级堆栈，说清"谁的额度可能被吞"，
    然后继续处理下一条——不能让一条坏数据把整批退款连坐掉，也不能让它拦住启动。
    """
    import logging

    log = logging.getLogger("audiencelens")

    # 注意：即使这次一条孤儿都没有，下面的过期占位清理也照跑——上一个进程
    # 可能是被 kill -9 掉的，那时评审已经结束、占位却没人释放。
    from app.models import Job
    from app.services import quota_service

    db: Session = SessionLocal()
    refunded = released = stale = 0
    try:
        for review_id, user_id in orphans:
            uid = user_id or "anonymous"
            try:
                job = (
                    db.query(Job)
                    .filter(Job.kind == "review", Job.ref_id == review_id)
                    .order_by(Job.created_at.desc())
                    .first()
                )
                # 谁付的钱在入队时就记在 job.payload 里了（review_service.enqueue_review）。
                # 读不到就当 BYOK：BYOK 从来不扣次数也不占名额，退了才是凭空发额度。
                key_source = ((job.payload or {}).get("key_source") if job else None) or "byok"
                if key_source != "server":
                    continue
                if quota_service.refund_review_credit(db, uid, review_id, key_source="server"):
                    refunded += 1
                if quota_service.release_review_slot(db, uid, key_source="server"):
                    released += 1
            except Exception:
                db.rollback()
                log.exception(
                    "启动收尸：评审 %s 的计费回收失败——用户 %s 的次数/配额可能被吞，需人工核对",
                    review_id,
                    uid,
                )
        try:
            stale = quota_service.sweep_stale_reservations(db)
        except Exception:
            db.rollback()
            log.exception("启动收尸：清理过期配额占位失败")
        if refunded or released or stale:
            log.warning(
                "启动收尸：退还 %d 次 CDK、释放 %d 个日配额占位、清理 %d 条过期占位",
                refunded,
                released,
                stale,
            )
    finally:
        db.close()


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
        # DEFAULT false 而不是 DEFAULT 0 —— 与下面 users.is_guest 同一个坑：
        # PostgreSQL 的 boolean 不接受整数字面量，这条迁移在 PG 上会直接报
        # "column is of type boolean but default expression is of type integer"。
        # 这里原本写的就是 DEFAULT 0，而那个坑在同一个文件里已经被记录过一次——
        # 新建库走 create_all 不经过这条路，所以本机 SQLite 永远测不出来。
        patches.append(
            "ALTER TABLE reviews ADD COLUMN enable_evaluation BOOLEAN DEFAULT false NOT NULL"
        )
    if "enable_red_team" not in columns:
        patches.append(
            "ALTER TABLE reviews ADD COLUMN enable_red_team BOOLEAN DEFAULT false NOT NULL"
        )
    if "adaptive_panel" not in columns:
        patches.append(
            "ALTER TABLE reviews ADD COLUMN adaptive_panel BOOLEAN DEFAULT false NOT NULL"
        )
    if "key_source" not in columns:
        # 可空、无默认：老数据确实不知道当时花的是谁的钱，写成 'byok' 会是编造，
        # 写成 'server' 会凭空给老用户扣掉免费次数。NULL 如实表达"不知道"，
        # 而计次那侧只统计 key_source == 'server'，NULL 自然不计入。
        patches.append("ALTER TABLE reviews ADD COLUMN key_source VARCHAR")
    if "input_tokens" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN input_tokens INTEGER DEFAULT 0 NOT NULL")
    if "output_tokens" not in columns:
        patches.append("ALTER TABLE reviews ADD COLUMN output_tokens INTEGER DEFAULT 0 NOT NULL")
    if "share_token" not in columns:
        # 不带 UNIQUE：SQLite 的 ALTER TABLE ADD COLUMN 不支持加唯一约束，
        # 写了整条迁移会失败。唯一性在新库由 create_all 保证；老库这里补一个
        # 普通索引保证按 token 查是走索引的，防重复则靠 token 本身的熵
        # （32 字节随机，碰撞概率远低于硬盘位翻转）。
        patches.append("ALTER TABLE reviews ADD COLUMN share_token VARCHAR")
        patches.append("CREATE INDEX IF NOT EXISTS ix_reviews_share_token ON reviews (share_token)")
    if "shared_at" not in columns:
        # TIMESTAMP 而不是 DATETIME：PostgreSQL 不认 DATETIME，
        # 而 SQLite 对类型名是宽容的（亲和性规则），两边都能过的写法只有 TIMESTAMP。
        patches.append("ALTER TABLE reviews ADD COLUMN shared_at TIMESTAMP")

    # 项目记忆按 (user_id, project_key) 查历史判断（评审创建的同步路径）。
    # 新库由模型的 __table_args__ 建；这一条给存量库补。IF NOT EXISTS 幂等，
    # 每次启动都跑也无害。
    if "wide_screen" not in columns:
        # DEFAULT false 而不是 0：PostgreSQL 的 boolean 不与整数隐式互转（见 is_guest 的教训）
        patches.append("ALTER TABLE reviews ADD COLUMN wide_screen BOOLEAN DEFAULT false NOT NULL")

    patches.append(
        "CREATE INDEX IF NOT EXISTS ix_reviews_user_project ON reviews (user_id, project_key)"
    )

    if "judgments" in inspector.get_table_names():
        j_columns = {c["name"] for c in inspector.get_columns("judgments")}
        if "source" not in j_columns:
            # 存量行全部是评审团产出的预测，回填成 'panel' 是事实而不是猜测
            patches.append(
                "ALTER TABLE judgments ADD COLUMN source VARCHAR DEFAULT 'panel' NOT NULL"
            )
            patches.append(
                "CREATE INDEX IF NOT EXISTS ix_judgments_source ON judgments (source)"
            )
        if "stance" not in j_columns:
            patches.append("ALTER TABLE judgments ADD COLUMN stance VARCHAR")

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

    if "conversations" in inspector.get_table_names():
        conv_columns = {c["name"] for c in inspector.get_columns("conversations")}
        if "project_id" not in conv_columns:
            # 新建库 create_all 会带上这一列（Project 表也在同一批新建），
            # 老库（本次上线前就已产生对话数据的实例）不会自动补，得靠这里。
            patches.append("ALTER TABLE conversations ADD COLUMN project_id VARCHAR")

    if "users" in inspector.get_table_names():
        user_columns = {c["name"] for c in inspector.get_columns("users")}
        if "is_guest" not in user_columns:
            # DEFAULT false，不是 DEFAULT 0：PostgreSQL 的 boolean 与整数不可隐式互转，
            #   ERROR: column "is_guest" is of type boolean but default expression is of type integer
            # 也就是说老库升级到带 is_guest 的版本时，这条迁移在 Postgres 上必挂。
            # 新建库不会走到这里（create_all 建表时列就齐了），所以本机 SQLite 永远测不出来。
            # `false` 关键字 SQLite 3.23+（2018）起支持，两边都成立。
            patches.append("ALTER TABLE users ADD COLUMN is_guest BOOLEAN DEFAULT false NOT NULL")
        if "email_verified_at" not in user_columns:
            patches.append("ALTER TABLE users ADD COLUMN email_verified_at DATETIME")
        if "token_quota_total" not in user_columns:
            # 可空 INTEGER，不带 DEFAULT：SQLite 与 PostgreSQL 都接受这条 DDL。
            # （对比上面 is_guest 那条踩过的坑：DEFAULT 0 在 PG 的 boolean 上会挂。）
            patches.append("ALTER TABLE users ADD COLUMN token_quota_total INTEGER")

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
