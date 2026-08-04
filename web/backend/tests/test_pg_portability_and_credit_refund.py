""""本机 SQLite 一切正常、切到 Postgres 全线崩"这一类缺陷的回归。

为什么需要单独一个文件：这组 bug 在开发机上 100% 测不出来。
SQLite 默认 `PRAGMA foreign_keys=OFF`——所有外键违约静默通过；
而 DEPLOY.md 指定的生产库是 PostgreSQL，那边外键永远强制。
于是"删账号 / 删评审"在本机怎么点都正常，上了生产对每个注册用户必 500。

这里的做法：用一个**显式打开外键校验**的独立 SQLite 库做夹具，
让本机也能撞上同一堵墙。第一条用例专门验证夹具本身有效——
外键没真的打开的话，下面所有断言都是假绿，那比没有测试更糟。

另一半是计费正确性：credits 模式下评审次数在入口就原子扣 1 次，
评审失败必须退还，且退还本身必须幂等（同一条评审失败两次不能退两次）。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import (
    AuthToken,
    CreditLedger,
    EvaluationScorecard,
    PersonaOutput,
    Review,
    UsageRecord,
    User,
    UserApiKey,
)


# ---------------------------------------------------------------------------
# 外键强制生效的夹具（模拟 PostgreSQL 的约束行为）
# ---------------------------------------------------------------------------


@pytest.fixture
def fk_db(tmp_path):
    """一个开启了 `PRAGMA foreign_keys=ON` 的独立 SQLite 会话。

    独立库而不是复用 conftest 的共享库：pragma 是**连接级**的，改共享
    engine 会波及其它测试文件；而且这里要的是刚建好、带最新 ondelete
    子句的表结构。
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    from app.models import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'fk.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_account(db, uid="u-fk-del"):
    """造一个"什么都有"的账号：评审 + 用量流水 + 认证令牌 + BYOK key + 评分卡。"""
    db.add(User(id=uid, email=f"{uid}@example.com", password_hash="x"))
    review = Review(
        user_id=uid,
        task_type="concept_review",
        artifact_bundle={"title": "我的材料"},
        status="completed",
    )
    db.add(review)
    db.flush()
    db.add(
        UsageRecord(
            user_id=uid, review_id=review.id, kind="review", cost_usd=0.5, key_source="server"
        )
    )
    db.add(
        AuthToken(
            user_id=uid,
            purpose="reset_password",
            token_hash="hash",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db.add(UserApiKey(user_id=uid, key_ciphertext="cipher", key_masked="sk-***x"))
    db.add(EvaluationScorecard(review_id=review.id, overall_score=80, passed=True))
    db.add(PersonaOutput(review_id=review.id, persona_id="P01", status="completed"))
    db.commit()
    return uid, review.id


class TestFixtureItself:
    def test_foreign_keys_are_actually_enforced(self, fk_db):
        """先证明这个夹具是有效的：外键没真开的话，本文件其余断言全是假绿。"""
        fk_db.add(UsageRecord(user_id="whoever", review_id="review-does-not-exist"))
        with pytest.raises(IntegrityError):
            fk_db.commit()
        fk_db.rollback()


class TestDeleteAccountUnderForeignKeys:
    def test_delete_account_does_not_violate_foreign_keys(self, fk_db):
        """删号这条路径以前在 Postgres 上对每个注册用户 100% 报 500。

        两个原因：auth_tokens 没人删（孤儿行挡住 users 的删除），
        usage_records.review_id 指着即将被删的评审。
        """
        from app.services import user_data_service

        uid, review_id = _seed_account(fk_db)

        stats = user_data_service.delete_user_data(fk_db, uid)

        assert stats["auth_tokens_deleted"] == 1
        assert stats["usage_records_detached"] == 1
        assert stats["account_deleted"] == 1
        assert fk_db.get(User, uid) is None
        assert fk_db.query(AuthToken).filter(AuthToken.user_id == uid).count() == 0
        assert fk_db.query(UserApiKey).filter(UserApiKey.user_id == uid).count() == 0
        assert fk_db.get(Review, review_id) is None
        # 评分卡是派生内容，必须随评审删干净（以前没有任何路径清理它）
        assert fk_db.query(EvaluationScorecard).count() == 0
        assert fk_db.query(PersonaOutput).count() == 0

    def test_billing_row_survives_with_a_dead_pointer(self, fk_db):
        """"评审删了账要在"：流水留下，review_id 置空，金额与 token 一字不改。"""
        from app.services import user_data_service

        uid, _ = _seed_account(fk_db)
        user_data_service.delete_user_data(fk_db, uid)

        fk_db.expire_all()
        rows = fk_db.query(UsageRecord).all()
        assert len(rows) == 1
        assert rows[0].review_id is None       # 指向失效
        assert rows[0].cost_usd == 0.5         # 但账还在
        assert rows[0].user_id.startswith("deleted-")  # 且已无法回指到人

    def test_deleting_only_the_review_keeps_the_billing_row(self, fk_db):
        """删单条评审（不删号）走的是库级 ON DELETE SET NULL，不经过删号那段代码。"""
        uid, review_id = _seed_account(fk_db, "u-fk-review-only")

        fk_db.delete(fk_db.get(Review, review_id))
        fk_db.commit()

        fk_db.expire_all()
        rows = fk_db.query(UsageRecord).filter(UsageRecord.user_id == uid).all()
        assert len(rows) == 1, "计费流水被评审删除连累了——它是财务事实源，不能级联删"
        assert rows[0].review_id is None

    def test_bulk_user_delete_does_not_orphan_credentials(self, fk_db):
        """绕过 ORM 的批量删（测试清理、运维脚本）也不能撞外键——靠库级 CASCADE 兜。

        注意范围：这里只覆盖 users 的两张子表（auth_tokens / user_api_keys）。
        reviews 的子表仍只有 ORM 级 cascade，`DELETE FROM reviews` 这种裸删
        在开了外键的库上会报错——当前没有任何生产路径这么删，不在本次改动范围内。
        """
        uid, review_id = _seed_account(fk_db, "u-fk-bulk")
        fk_db.query(UsageRecord).update({"review_id": None}, synchronize_session=False)
        fk_db.delete(fk_db.get(Review, review_id))
        fk_db.commit()

        fk_db.query(User).filter(User.id == uid).delete(synchronize_session=False)
        fk_db.commit()

        assert fk_db.query(AuthToken).count() == 0
        assert fk_db.query(UserApiKey).count() == 0


# ---------------------------------------------------------------------------
# credits 模式：评审失败必须退次数，且退还幂等
# ---------------------------------------------------------------------------


@pytest.fixture
def credits_mode(monkeypatch):
    monkeypatch.setattr(settings, "quota_enabled", True)
    monkeypatch.setattr(settings, "quota_mode", "credits")


@pytest.fixture
def clean_ledger(db):
    """本组用的都是专属 user_id，跑完清掉，免得污染别的测试文件的余额断言。"""
    yield
    db.query(CreditLedger).filter(CreditLedger.user_id.like("refund-%")).delete(
        synchronize_session=False
    )
    db.commit()


class TestRefundPrimitive:
    def test_refund_requires_an_idempotency_key(self, db, clean_ledger):
        """没有 ref_id 就无法保证只退一次——宁可报错，也不能悄悄插一行。"""
        from app.services import cdk_service

        with pytest.raises(ValueError):
            cdk_service.refund_credit(db, "refund-nokey-user", "")

    def test_same_ref_id_refunds_only_once(self, db, clean_ledger):
        from app.services import cdk_service

        uid = "refund-idem-user"
        db.add(CreditLedger(user_id=uid, delta=1, reason="cdk_redeem"))
        db.commit()
        assert cdk_service.try_consume_credit(db, uid) is True
        assert cdk_service.credit_balance(db, uid) == 0

        assert cdk_service.refund_credit(db, uid, "review-1") is True
        assert cdk_service.credit_balance(db, uid) == 1
        # 同一条评审再退一次：什么都不该发生
        assert cdk_service.refund_credit(db, uid, "review-1") is False
        assert cdk_service.refund_credit(db, uid, "review-1") is False
        assert cdk_service.credit_balance(db, uid) == 1

        # 另一条评审是另一笔账，照退
        assert cdk_service.refund_credit(db, uid, "review-2") is True
        assert cdk_service.credit_balance(db, uid) == 2

    def test_refund_is_visible_in_the_ledger(self, db, clean_ledger):
        """退还必须落成一行可核对的流水，不是隐形补偿。"""
        from app.services import cdk_service

        uid = "refund-ledger-user"
        cdk_service.refund_credit(db, uid, "review-x")
        row = (
            db.query(CreditLedger)
            .filter(CreditLedger.user_id == uid, CreditLedger.reason == "review_refund")
            .one()
        )
        assert row.delta == 1
        assert row.ref_id == "review-x"


class TestRefundGating:
    def test_only_credits_mode_refunds(self, db, monkeypatch, clean_ledger):
        """plan 模式下扣减流水没有 review_id，事后无法判断这条评审垫没垫——
        宁可不退也不能猜着退（猜错就是凭空发次数）。"""
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "plan")
        assert quota_service.refund_review_credit(db, "refund-plan-user", "rv-1") is False
        assert (
            db.query(CreditLedger).filter(CreditLedger.user_id == "refund-plan-user").count() == 0
        )

    def test_byok_never_gets_refunded(self, db, credits_mode, clean_ledger):
        """BYOK 从来不扣次数，退了就是凭空发次数。"""
        from app.services import quota_service

        assert (
            quota_service.refund_review_credit(db, "refund-byok-user", "rv-1", key_source="byok")
            is False
        )
        assert db.query(CreditLedger).filter(CreditLedger.user_id == "refund-byok-user").count() == 0

    def test_quota_disabled_never_refunds(self, db, monkeypatch, clean_ledger):
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", False)
        monkeypatch.setattr(settings, "quota_mode", "credits")
        assert quota_service.refund_review_credit(db, "refund-off-user", "rv-1") is False
        assert db.query(CreditLedger).filter(CreditLedger.user_id == "refund-off-user").count() == 0


class TestFailedReviewRefundsEndToEnd:
    """真跑一遍后台执行路径：模型报错 → 评审 failed → 次数回到用户账上。"""

    def _boom(self, **_kwargs):
        raise RuntimeError("上游模型 500 了")

    def test_failed_review_gives_the_credit_back(self, db, credits_mode, clean_ledger, monkeypatch):
        from app.services import cdk_service, quota_service, review_service

        import runner.cli

        uid = "refund-e2e-user"
        db.add(CreditLedger(user_id=uid, delta=1, reason="cdk_redeem"))
        review = Review(
            user_id=uid,
            task_type="concept_review",
            artifact_bundle={"title": "x", "materials": [{"type": "text", "text": "y"}]},
            status="pending",
        )
        db.add(review)
        db.commit()

        # 入口原子扣 1 次（真实链路里由 create_review 依赖跑）
        quota_service.check_quota(db, uid, key_source="server", plan="free")
        assert cdk_service.credit_balance(db, uid) == 0

        monkeypatch.setattr(runner.cli, "run_panel", self._boom)
        with pytest.raises(RuntimeError):
            review_service._execute_review(review.id, "sk-fake", "server", uid, "job-fake")

        db.expire_all()
        assert db.get(Review, review.id).status == "failed"
        assert cdk_service.credit_balance(db, uid) == 1, "评审失败了，用户花钱买的次数却没退回来"

    def test_retrying_the_same_failed_review_does_not_refund_twice(
        self, db, credits_mode, clean_ledger, monkeypatch
    ):
        """收尸/重试可能让同一条评审失败两次——退还必须只发生一次。"""
        from app.services import cdk_service, quota_service, review_service

        import runner.cli

        uid = "refund-twice-user"
        db.add(CreditLedger(user_id=uid, delta=1, reason="cdk_redeem"))
        review = Review(
            user_id=uid,
            task_type="concept_review",
            artifact_bundle={"title": "x", "materials": [{"type": "text", "text": "y"}]},
            status="pending",
        )
        db.add(review)
        db.commit()
        quota_service.check_quota(db, uid, key_source="server", plan="free")

        monkeypatch.setattr(runner.cli, "run_panel", self._boom)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                review_service._execute_review(review.id, "sk-fake", "server", uid, "job-fake")

        db.expire_all()
        assert cdk_service.credit_balance(db, uid) == 1, "同一条评审被退了多次——凭空发次数"


# ---------------------------------------------------------------------------
# 并发扣减：Postgres 分支只验证"确实取了锁"，真并发语义本机验不了
# ---------------------------------------------------------------------------


class _StubSession:
    """只记录 execute 了什么的假 Session——用来检查方言分支，不碰真库。"""

    def __init__(self, dialect_name):
        self._dialect = dialect_name
        self.executed = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self._dialect))

    def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        return SimpleNamespace(rowcount=1)


class TestConcurrencySerialization:
    """`INSERT ... SELECT ... WHERE (子查询)` 在 SQLite 上碰巧原子，在
    PostgreSQL 的 READ COMMITTED 下并不原子（子查询读的是语句开始时的快照），
    余额会被并发请求扣成负数。修法是在 Postgres 上先取事务级 advisory lock。

    本机没有 Postgres（psycopg2/testcontainers 都没装），所以这里只能验到
    "走 Postgres 分支时确实发出了 pg_advisory_xact_lock"以及"SQLite 上不多发
    任何语句"。真正的并发语义没有在本机验证过。
    """

    def test_postgres_takes_a_transaction_advisory_lock(self):
        from app.services import cdk_service

        stub = _StubSession("postgresql")
        cdk_service._serialize_credit_writes(stub, "u-1")
        assert len(stub.executed) == 1
        sql, params = stub.executed[0]
        assert "pg_advisory_xact_lock" in sql
        assert isinstance(params["k"], int)
        assert -(2**63) <= params["k"] < 2**63  # 必须落在 bigint range 内

    def test_lock_key_is_stable_and_per_user(self):
        from app.services import cdk_service

        assert cdk_service._credit_lock_key("u-1") == cdk_service._credit_lock_key("u-1")
        assert cdk_service._credit_lock_key("u-1") != cdk_service._credit_lock_key("u-2")

    def test_sqlite_path_is_unchanged(self):
        from app.services import cdk_service

        stub = _StubSession("sqlite")
        cdk_service._serialize_credit_writes(stub, "u-1")
        assert stub.executed == []

    def test_balance_still_cannot_go_negative_on_sqlite(self, db, clean_ledger):
        """加了锁之后，原来的单机行为不能退化。"""
        from app.services import cdk_service

        uid = "refund-negative-user"
        db.add(CreditLedger(user_id=uid, delta=1, reason="cdk_redeem"))
        db.commit()
        assert cdk_service.try_consume_credit(db, uid) is True
        assert cdk_service.try_consume_credit(db, uid) is False
        assert cdk_service.credit_balance(db, uid) == 0


# ---------------------------------------------------------------------------
# 进程重启收尸（spec 3.2）：_reap_orphans 标 failed 之外必须连计费一起收
# ---------------------------------------------------------------------------


class TestReapOrphansRefunds:
    """重启时 queued/running 的评审被标 failed，但退款逻辑此前只存在于
    review_service 的进程内异常分支——进程被重启的那一刻它根本没机会跑。
    于是用户花钱买的次数凭空消失。这里验证收尸真的退款，且幂等、不误退。"""

    def _seed_orphan(self, db, uid, key_source):
        """建一条"扣过钱的孤儿"：pending review + queued job（payload 记录谁付的钱）。"""
        from app.models import Job

        review = Review(
            user_id=uid,
            task_type="concept_review",
            artifact_bundle={"title": "x"},
            status="pending",
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        db.add(
            Job(
                kind="review",
                ref_id=review.id,
                user_id=uid,
                status="queued",
                payload={"key_source": key_source},
            )
        )
        db.commit()
        return review.id

    def test_server_key_orphan_is_refunded(self, db, credits_mode, clean_ledger):
        """credits 模式 + server key：入口扣了 1 次，进程重启后必须退回来。"""
        from app import db as app_db
        from app.models import Job
        from app.services import cdk_service, quota_service

        uid = "refund-orphan-srv"
        db.add(CreditLedger(user_id=uid, delta=1, reason="cdk_redeem"))
        db.commit()
        review_id = self._seed_orphan(db, uid, "server")

        # 模拟发起时的入口扣减（真实链路里由 create_review 的 check_quota 做）
        quota_service.check_quota(db, uid, key_source="server", plan="free")
        assert cdk_service.credit_balance(db, uid) == 0

        app_db._reap_orphans()

        db.expire_all()
        assert db.get(Review, review_id).status == "failed"
        job = db.query(Job).filter(Job.ref_id == review_id).one()
        assert job.status == "failed"
        assert cdk_service.credit_balance(db, uid) == 1, "扣了次数但任务孤儿——重启后次数没退回来"

    def test_reap_is_idempotent(self, db, credits_mode, clean_ledger):
        """同一批孤儿只会被收尸一次；重复启动不能再退一遍（凭空发次数）。"""
        from app import db as app_db
        from app.services import cdk_service, quota_service

        uid = "refund-orphan-idem"
        db.add(CreditLedger(user_id=uid, delta=1, reason="cdk_redeem"))
        db.commit()
        review_id = self._seed_orphan(db, uid, "server")
        quota_service.check_quota(db, uid, key_source="server", plan="free")

        app_db._reap_orphans()
        assert cdk_service.credit_balance(db, uid) == 1
        # 第二次启动：评审已经是 failed，不在收尸范围，退款也不该再发生
        app_db._reap_orphans()
        assert cdk_service.credit_balance(db, uid) == 1

    def test_byok_orphan_is_not_refunded(self, db, credits_mode, clean_ledger):
        """BYOK 从来不扣次数，退了就是凭空发次数。"""
        from app import db as app_db
        from app.services import cdk_service

        uid = "refund-orphan-byok"
        db.add(CreditLedger(user_id=uid, delta=2, reason="cdk_redeem"))
        db.commit()
        self._seed_orphan(db, uid, "byok")

        app_db._reap_orphans()

        assert cdk_service.credit_balance(db, uid) == 2

    def test_plan_mode_orphan_releases_the_reserved_slot(self, db, monkeypatch, clean_ledger):
        """plan 模式的日名额是入口占位（review_pending）。评审没跑成，占位
        必须在收尸时还回去，否则用户被自己失败的评审挡到 TTL 过期。"""
        from app import db as app_db
        from app.models import UsageRecord
        from app.services import quota_service

        monkeypatch.setattr(settings, "quota_enabled", True)
        monkeypatch.setattr(settings, "quota_mode", "plan")
        monkeypatch.setattr(settings, "quota_free_reviews_per_day", 1)
        uid = "refund-orphan-plan"
        review_id = self._seed_orphan(db, uid, "server")
        quota_service.check_quota(db, uid, key_source="server", plan="free")
        assert (
            db.query(UsageRecord)
            .filter(UsageRecord.user_id == uid, UsageRecord.kind == "review_pending")
            .count()
            == 1
        )

        app_db._reap_orphans()

        db.expire_all()
        assert (
            db.query(UsageRecord)
            .filter(UsageRecord.user_id == uid, UsageRecord.kind == "review_pending")
            .count()
            == 0
        ), "收尸没有释放日配额占位——用户被自己失败的评审挡在门外"
        # 占位释放后名额恢复，还能再发起一次
        quota_service.check_quota(db, uid, key_source="server", plan="free")
