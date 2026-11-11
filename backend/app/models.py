"""ORM 模型：用户/Token 流水 + 监测任务 + 监测报告。"""
import datetime as dt

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """账号：token 余额制。admin 角色额度无限（扣费跳过）。"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), default="user", nullable=False)   # admin / user
    token_balance = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    transactions = relationship(
        "TokenTx", back_populates="user", cascade="all, delete-orphan",
        order_by="TokenTx.created_at.desc()",
    )


class TokenTx(Base):
    """token 流水：充值 / 消费 / 赠送 / 退款，每笔带变动后余额，可审计。"""
    __tablename__ = "token_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)            # 正=入账 负=扣减
    balance_after = Column(Integer, nullable=False)     # 变动后余额
    reason = Column(String(32), nullable=False)         # recharge/consume/refund/signup_bonus/adjust
    note = Column(String(200), default="")
    task_id = Column(Integer, nullable=True)            # 消费/退款关联的任务
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="transactions")


class MonitorTask(Base):
    """一次 GEO 监测任务的配置（目标站点 + 关键词组）。"""
    __tablename__ = "monitor_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    url = Column(String(1000), nullable=False)
    keywords = Column(JSON, default=list, nullable=False)  # ["品牌词", "行业词", ...]
    hint = Column(String(200), default="")                 # 行业大方向（选填，用于校准自动关键词）
    engines = Column(JSON, default=list, nullable=False)   # 模拟的生成式引擎列表
    status = Column(String(20), default="pending", nullable=False)  # pending/running/done/failed
    last_message = Column(String(500), default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    reports = relationship(
        "MonitorReport", back_populates="task", cascade="all, delete-orphan",
        order_by="MonitorReport.created_at.desc()",
    )


class MonitorReport(Base):
    """一次监测产出的量化报告（结构对齐 SheepGEO 模板）。"""
    __tablename__ = "monitor_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("monitor_tasks.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(1000), nullable=False)
    overall_score = Column(Float, nullable=False)
    grade = Column(String(4), nullable=False)  # S/A/B/C/D
    dimensions = Column(JSON, nullable=False)      # 五维得分 + 等级 + 说明
    core_metrics = Column(JSON, nullable=False)    # 核心指标汇总
    eeat = Column(JSON, nullable=True)             # EEAT 四维（经验/专业性/权威性/可信度）
    findings = Column(JSON, nullable=False)        # 关键发现 + 改进优先级
    performance = Column(JSON, nullable=False)     # Core Web Vitals + 资源统计
    keyword_matrix = Column(JSON, nullable=False) # 多引擎 x 多关键词识别矩阵
    suggestions = Column(JSON, nullable=False)    # 分维度优化建议
    snapshot = Column(JSON, nullable=True)        # 原始页面特征快照
    signature = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    task = relationship("MonitorTask", back_populates="reports")


Base.metadata.create_all  # 占位，实际建表在 init_db()
