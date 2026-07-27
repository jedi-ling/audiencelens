import os
import sys
import tempfile

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 每个测试会话用独立的临时库，绝不碰开发数据
_tmp_db = os.path.join(tempfile.mkdtemp(prefix="al-test-"), "test.db")
os.environ.setdefault("AL_DATABASE_URL", f"sqlite:///{_tmp_db}")
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
    from app.db import init_db

    init_db()


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
