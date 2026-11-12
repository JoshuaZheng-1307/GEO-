"""注册引导：新用户首次输入公司信息，免费生成一份官网分析报告（不扣 token）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import MonitorTask, User
from app.schemas import OnboardingIn, TaskOut
from app.services.auth import get_current_user
from app.tasks.geo_tasks import run_monitor

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/status")
def status(user: User = Depends(get_current_user)):
    """是否还需要走引导（管理员视为已完成，可随时免费分析）。"""
    return {
        "onboarded": bool(user.onboarded) or user.role == "admin",
        "company_name": user.company_name or "",
        "business": user.business or "",
        "is_admin": user.role == "admin",
    }


@router.post("/start", response_model=TaskOut, status_code=201)
def start(payload: OnboardingIn, db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    """提交公司信息 → 创建首个监测任务并免费执行（不扣 token，仅一次）。

    管理员不受次数限制（额度无限），可用于快速分析任意公司官网。
    """
    if user.role != "admin" and user.onboarded:
        raise HTTPException(409, "首次免费分析已使用，后续监测请消耗 token 或在任务页运行")

    company = payload.company_name.strip()[:200]
    business = (payload.business or "").strip()[:500]

    # 仅首次引导写入用户资料；管理员临时分析不覆盖自己的公司信息
    if user.role != "admin":
        user.company_name = company
        user.business = business
        user.onboarded = True

    task = MonitorTask(
        user_id=user.id,
        name=company or payload.url,
        url=payload.url,
        keywords=[],                          # 运行时会自动从官网抽取关键词
        hint=business[:200],
        engines=settings.SIMULATED_ENGINES,
    )
    db.add(task)
    db.flush()
    db.commit()
    db.refresh(task)

    try:
        run_monitor.delay(task.id)            # 免费：不写 consume 流水
    except Exception as exc:  # 队列不可用时给明确提示，避免前端 500
        raise HTTPException(503, f"分析队列不可用，请确认 Redis 与 Celery 已启动：{exc}")
    return task
