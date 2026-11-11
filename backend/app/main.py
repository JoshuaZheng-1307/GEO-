"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.auth_routes import admin_router, router as auth_router
from app.api.routes import router
from app.database import Base, engine, SessionLocal
from app.models import MonitorReport, MonitorTask, User  # noqa: F401 确保建表
from app.services.auth import SIGNUP_BONUS, hash_password

app = FastAPI(
    title="GEO 监测量化模拟系统",
    description="基于 SHEEP 五维框架（参照 SheepGEO 模板）的生成式引擎优化监测与量化平台",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(admin_router)

DEFAULT_ADMIN = ("admin", "admin123")   # 首次启动自动创建，请登录后尽快改密


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
    # 轻量迁移：给已存在的库补上后加的列（PostgreSQL 支持 IF NOT EXISTS）
    with engine.begin() as conn:
        for ddl in (
            "ALTER TABLE monitor_tasks ADD COLUMN IF NOT EXISTS hint VARCHAR(200)",
            "ALTER TABLE monitor_reports ADD COLUMN IF NOT EXISTS eeat JSON",
            "ALTER TABLE monitor_tasks ADD COLUMN IF NOT EXISTS user_id INTEGER",
        ):
            try:
                conn.execute(text(ddl))
            except Exception:  # 非 PostgreSQL 或列已存在
                pass
    _ensure_default_admin()


def _ensure_default_admin():
    """首次启动创建默认管理员（admin / admin123）。"""
    db = SessionLocal()
    try:
        if not db.query(User).first():
            db.add(User(username=DEFAULT_ADMIN[0],
                        password_hash=hash_password(DEFAULT_ADMIN[1]),
                        role="admin", token_balance=0))
            db.commit()
    finally:
        db.close()


@app.get("/")
def root():
    return {"service": "GEO Monitor", "docs": "/docs"}
