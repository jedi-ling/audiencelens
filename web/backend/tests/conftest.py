import os
import sys
import tempfile

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 测试不读开发机的 web/.env（config._load_dotenv_once 认这个开关）。
# 必须在 import app.config 之前设置——那个函数在模块导入时就跑。
# 理由同下面清 AL_ADMIN_TOKEN：本机 .env 里写什么是开发者的自由
# （比如 AL_AUTH_ENABLED=true），但它不该决定测试断言的成败。
# 实测：不加这行时 test_auth_and_gating / test_cdk 共 4 条会因为
# 本机 .env 开了鉴权而失败——测试环境必须是确定的。
os.environ["AL_SKIP_DOTENV"] = "1"

# 每个测试会话用独立的临时库，绝不碰开发数据。
#
# 这里必须是**强制覆盖**，不能用 setdefault ——上面那句"绝不碰开发数据"在
# setdefault 下是一句假话：AL_DATABASE_URL 正是真实部署用的环境变量名，
# 在配了它的机器（或 CI 的部署环境、或刚 source 过 .env 的 shell）上跑测试，
# 整个测试套会对着那个库建用户、删用户、写用量流水。
# 退一万步说，就算指向的是另一个开发库，用户 id 也是确定性的
# （u-{email}，见 test_unverified_quota_cap 等）+ users.email 唯一约束，
# 同一个库跑第二遍必然 IntegrityError —— 表现为"测试昨天还好好的今天全红"。
#
# 代价：无法通过环境变量把测试指向 PostgreSQL 做方言验证。那件事应该由
# 显式的 opt-in 开关来做（AL_TEST_DATABASE_URL），而不是让一个同名于生产配置的
# 变量悄悄接管——后者的失败模式是数据损坏，不是测试失败。
_tmp_db = os.path.join(tempfile.mkdtemp(prefix="al-test-"), "test.db")
os.environ["AL_DATABASE_URL"] = os.environ.get(
    "AL_TEST_DATABASE_URL", f"sqlite:///{_tmp_db}"
)
os.environ.setdefault("AL_JWT_SECRET", "test-secret")
os.environ.setdefault("AL_RATELIMIT_ENABLED", "false")  # 单测里默认关限流

# 测试进程不继承开发机上的后台令牌。
# config._validate_admin_token 会因为长度/字符不合格直接 raise，
# 于是「本机 shell 里恰好导出过一个短 AL_ADMIN_TOKEN」就能让整个测试套在收集期崩掉——
# 这跟被测代码毫无关系。测试要用后台身份时一律 monkeypatch settings.admin_token
# （见 test_admin.py），不依赖环境变量，所以这里直接清空最诚实。
os.environ.pop("AL_ADMIN_TOKEN", None)


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    """建表；复用外部测试库时先清空。

    清空这一步是为了让测试套**可重跑**。很多测试里的用户 id 是确定性的
    （u-{email} 之类）而 users.email 有唯一约束，所以对着同一个库跑第二遍
    必然 IntegrityError——现象是"昨天还全绿，今天一片红"，而代码一行没改。

    默认路径每次都是新建的临时目录，本来就不会撞；这条只对显式
    AL_TEST_DATABASE_URL 生效。清的是"测试库"——变量名已经把这件事说明白了，
    而且绝不会碰到生产库：上面那段强制赋值保证了 AL_DATABASE_URL 只可能是
    临时库或这个显式变量指向的库。
    """
    from app.db import Base, engine, init_db

    init_db()
    if os.environ.get("AL_TEST_DATABASE_URL"):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    from app.db import session_scope

    s = session_scope()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _reset_limiter():
    from app.core.ratelimit import get_limiter

    get_limiter().reset()
    yield


@pytest.fixture(autouse=True)
def _cleanup_anonymous_key():
    """每条测试跑完都清掉 "anonymous" 身份下的 BYOK key。

    为什么必须是全局 autouse，而不是让每个文件自己记得清：
    整个测试会话共用一个 sqlite 文件、不按测试回滚（见上面 _init_db 的说明），
    而 "anonymous" 是**所有测试共享的同一个身份桶**——任何一条测试给它存了
    key 而没清，后面所有断言"匿名且没配 key 时应该 428/不该有 key"的测试
    都会跟着红，且红在一个跟它自己毫无关系的文件里。

    这个坑已经被踩过两次，两次的处理都是"在出事的那个文件里补一个
    autouse fixture"（test_review_chat.py、test_token_counting.py 里都有
    同款局部 fixture，注释还写明了病因）——但那是打补丁不是堵源头：
    test_chat_features.py 有 9 处 save_user_key、一处清理都没有，它现在不炸
    纯粹是因为字母序在它后面的 test_multi_provider_keys.py 有一句
    `db.query(UserApiKey).delete()` 顺手替它擦了屁股。靠文件名字母序维持的
    正确性，下一个新增测试文件就可能打破。

    实测复现（本次修复前）：
        pytest tests/test_chat_features.py \\
               tests/test_auth_and_gating.py::...::test_anonymous_review_creation_not_blocked_by_auth
        → 1 failed（后者拿到了前者漏下的 key，428 变成了别的）

    放在这里之后，新写测试的人不需要知道这件事，也不会再踩。
    只清 "anonymous"：真实用户 id 在各测试里是唯一的（随机邮箱），
    不构成跨测试污染，没必要连它们一起删。
    """
    yield
    from app.db import session_scope
    from app.services import key_service

    s = session_scope()
    try:
        key_service.delete_user_key(s, "anonymous")
    finally:
        s.close()
