import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from starlette.middleware.base import BaseHTTPMiddleware

from app.models import Base
from app.api import router as api_router
from app.websocket import router as ws_router, manager as ws_manager

DATABASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATABASE_PATH = os.path.join(DATABASE_DIR, "reviews.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db():
    os.makedirs(DATABASE_DIR, exist_ok=True)
    Base.metadata.create_all(engine)
    _migrate_add_mode_column()


def _migrate_add_mode_column():
    from sqlalchemy import inspect, text
    with engine.connect() as conn:
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("reviews")]
        if "mode" not in columns:
            conn.execute(text("ALTER TABLE reviews ADD COLUMN mode VARCHAR DEFAULT 'standard' NOT NULL"))
            conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.services import PersonaService
    PersonaService.load_all_personas()
    PersonaService.load_agents_from_md()
    PersonaService.load_trae_personas()
    PersonaService.list_packs()
    PersonaService.load_presets()
    from app.services.evaluation_service import EvaluationService
    EvaluationService.load_evaluators()
    EvaluationService.load_rubrics()
    from app.services.ethics_service import EthicsService
    EthicsService._load_stereotype_patterns()
    ws_manager.set_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="AudienceLens Review API", version="0.2.0", lifespan=lifespan)


# 安全措施：添加安全响应头中间件，防止 MIME 类型嗅探、点击劫持等攻击
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://localhost:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
