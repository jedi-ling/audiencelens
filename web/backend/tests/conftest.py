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
