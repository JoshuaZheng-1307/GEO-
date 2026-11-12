"""FastAPI 应用入口。"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.auth_routes import admin_router, router as auth_router
from app.api.onboarding_routes import router as onboarding_router
from app.api.routes import router
from app.database import Base, engine, SessionLocal
from app.models import MonitorReport, MonitorTask, User  # noqa: F401 确保建表
from app.services.auth import SIGNUP_BONUS, hash_password, verify_password

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
app.include_router(onboarding_router)

# 默认管理员：admin / 123456（可用 GEO_ADMIN_PASSWORD 覆盖）
ADMIN_USERNAME = os.environ.get("GEO_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("GEO_ADMIN_PASSWORD", "123456")
LEGACY_ADMIN_PASSWORD = "admin123"


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
    # 轻量迁移：给已存在的库补上后加的列（PostgreSQL 支持 IF NOT EXISTS）
    with engine.begin() as conn:
        for ddl in (
            "ALTER TABLE monitor_tasks ADD COLUMN IF NOT EXISTS hint VARCHAR(200)",
            "ALTER TABLE monitor_reports ADD COLUMN IF NOT EXISTS eeat JSON",
            "ALTER TABLE monitor_tasks ADD COLUMN IF NOT EXISTS user_id INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(200)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS business VARCHAR(500)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarded BOOLEAN DEFAULT FALSE",
        ):
            try:
                conn.execute(text(ddl))
            except Exception:  # 非 PostgreSQL 或列已存在
                pass
    _ensure_default_admin()


def _ensure_default_admin():
    """保证存在 admin 管理员账号（admin / 123456），额度无限。"""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
        if not admin:
            db.add(User(username=ADMIN_USERNAME,
                        password_hash=hash_password(ADMIN_PASSWORD),
                        role="admin", token_balance=0, onboarded=True))
            db.commit()
            return
        # 历史版本的默认密码 admin123 自动迁移到新默认密码
        if verify_password(LEGACY_ADMIN_PASSWORD, admin.password_hash):
            admin.password_hash = hash_password(ADMIN_PASSWORD)
        admin.role = "admin"
        admin.is_active = True
        admin.onboarded = True
        db.commit()
    finally:
        db.close()


@app.get("/")
def root():
    return {"service": "GEO Monitor", "docs": "/docs"}
