"""API 路由：任务 CRUD、触发监测、进度查询、报告查询。

计费规则：创建任务配置免费，每次点「运行」消耗 TASK_COST 个 token；
任务失败自动退款。admin 角色额度无限。
"""
import json

import redis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import MonitorReport, MonitorTask, User
from app.schemas import ProfileIn, ProgressOut, ReportOut, TaskCreate, TaskOut
from app.services.auth import TASK_COST, charge_tokens, ensure_can_run, get_current_user
from app.services.keyword_suggester import suggest_keywords
from app.services.site_profiler import profile_site
from app.tasks.geo_tasks import run_monitor

router = APIRouter(prefix="/api")

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _check_task_access(db: Session, task_id: int, user: User) -> None:
    """任务归属校验：admin 全量可见，普通用户仅限自己的任务。"""
    task = db.get(MonitorTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if user.role != "admin" and task.user_id != user.id:
        raise HTTPException(403, "无权访问该任务的报告")


@router.post("/site-profile")
def site_profile(payload: ProfileIn):
    """分析官网：识别企业是做什么的，并自动生成分类关键词。"""
    try:
        return profile_site(str(payload.url), hint=payload.hint or "")
    except HTTPException:
        raise
    except Exception as exc:  # 网络/解析异常统一为 502
        raise HTTPException(502, f"分析官网失败：{exc}")


@router.get("/keyword-suggestions")
def keyword_suggestions(
    url: str = Query(..., description="目标页面 URL"),
    top: int = Query(12, ge=1, le=30),
):
    """从单个页面抽取候选关键词（轻量版，页面级）。"""
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "URL 必须以 http:// 或 https:// 开头")
    try:
        return suggest_keywords(url, top=top)
    except HTTPException:
        raise
    except Exception as exc:  # 网络/解析异常统一为 502
        raise HTTPException(502, f"抓取目标页面失败：{exc}")


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    task = MonitorTask(
        user_id=user.id,
        name=payload.name,
        url=str(payload.url),
        keywords=payload.keywords or [],   # 允许留空，运行时自动从官网提取
        hint=payload.hint or "",
        engines=payload.engines or settings.SIMULATED_ENGINES,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """普通用户只看自己的任务；admin 可见全部。"""
    query = db.query(MonitorTask)
    if user.role != "admin":
        query = query.filter(MonitorTask.user_id == user.id)
    return query.order_by(MonitorTask.created_at.desc()).all()


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    task = db.get(MonitorTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if user.role != "admin" and task.user_id != user.id:
        raise HTTPException(403, "无权查看该任务")
    return task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    task = db.get(MonitorTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if user.role != "admin" and task.user_id != user.id:
        raise HTTPException(403, "无权删除该任务")
    db.delete(task)
    db.commit()


@router.post("/tasks/{task_id}/run")
def run_task(task_id: int, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    """触发一次监测：预扣 TASK_COST token，任务失败由 Worker 自动退款。"""
    task = db.get(MonitorTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if user.role != "admin" and task.user_id != user.id:
        raise HTTPException(403, "无权运行该任务")
    if task.status == "running":
        raise HTTPException(409, "任务正在运行中")
    ensure_can_run(user)
    if user.role != "admin":
        charge_tokens(db, user, -TASK_COST, "consume",
                      note=f"监测任务「{task.name[:60]}」", task_id=task.id)
    task.status = "pending"
    task.last_message = "已提交到队列"
    db.commit()
    async_result = run_monitor.delay(task_id)
    return {"celery_task_id": async_result.id, "task_id": task_id,
            "token_balance": user.token_balance}


@router.get("/tasks/{task_id}/progress", response_model=ProgressOut)
def get_progress(task_id: int, db: Session = Depends(get_db)):
    """读取 Redis 中的实时进度。"""
    raw = redis_client.get(f"geo:progress:{task_id}")
    if raw:
        return json.loads(raw)
    task = db.get(MonitorTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return ProgressOut(task_id=task_id, status=task.status,
                       stage=task.status, percent=100 if task.status == "done" else 0,
                       message=task.last_message)


@router.get("/tasks/{task_id}/reports", response_model=list[ReportOut])
def list_reports(task_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    _check_task_access(db, task_id, user)
    return db.query(MonitorReport).filter(MonitorReport.task_id == task_id)\
        .order_by(MonitorReport.created_at.desc()).all()


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    report = db.get(MonitorReport, report_id)
    if not report:
        raise HTTPException(404, "报告不存在")
    _check_task_access(db, report.task_id, user)
    return report


@router.get("/reports/{report_id}/history")
def score_history(report_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """同任务历史得分趋势（pandas 在分析层使用，这里直接返回时序数据）。"""
    report = db.get(MonitorReport, report_id)
    if not report:
        raise HTTPException(404, "报告不存在")
    _check_task_access(db, report.task_id, user)
    rows = db.query(MonitorReport).filter(MonitorReport.task_id == report.task_id)\
        .order_by(MonitorReport.created_at.asc()).all()
    return {
        "dates": [r.created_at.isoformat() for r in rows],
        "overall": [r.overall_score for r in rows],
        "dimensions": [
            {dim: r.dimensions.get(dim, {}).get("score", 0) for dim in ("S", "H", "E1", "E2", "P")}
            for r in rows
        ],
    }
