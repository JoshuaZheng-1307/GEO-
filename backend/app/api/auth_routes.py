"""账号与计费路由：注册/登录/流水 + 管理员用户管理。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MonitorReport, MonitorTask, TokenTx, User
from app.schemas import (LoginIn, RegisterIn, RechargeIn, ResetPasswordIn,
                         SetActiveIn, SetRoleIn, TokenInfoOut, TxOut, UserOut)
from app.services.auth import (SIGNUP_BONUS, TASK_COST, charge_tokens,
                               create_access_token, get_current_user,
                               hash_password, require_admin, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"],
                         dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------
@router.get("/pricing", response_model=TokenInfoOut)
def pricing():
    """计费规则（公开）：每次监测消耗多少、注册送多少。"""
    return TokenInfoOut(task_cost=TASK_COST, signup_bonus=SIGNUP_BONUS)


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if len(username) < 2:
        raise HTTPException(400, "用户名至少 2 个字符")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "用户名已存在")
    user = User(username=username, password_hash=hash_password(payload.password),
                role="user", token_balance=SIGNUP_BONUS)
    db.add(user)
    db.flush()
    db.add(TokenTx(user_id=user.id, amount=SIGNUP_BONUS,
                   balance_after=SIGNUP_BONUS, reason="signup_bonus",
                   note="注册赠送"))
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username.strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")
    return {"access_token": create_access_token(user), "token_type": "bearer",
            "user": UserOut.model_validate(user)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """当前登录用户信息 + token 余额。"""
    return user


@router.get("/transactions", response_model=list[TxOut])
def my_transactions(limit: int = Query(50, ge=1, le=200),
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """我的 token 流水。"""
    return db.query(TokenTx).filter(TokenTx.user_id == user.id)\
        .order_by(TokenTx.created_at.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# 管理员
# ---------------------------------------------------------------------------
@admin_router.get("/users", response_model=list[UserOut])
def list_users(q: str = Query("", description="按用户名模糊搜索"),
               db: Session = Depends(get_db)):
    query = db.query(User)
    if q.strip():
        query = query.filter(User.username.ilike(f"%{q.strip()}%"))
    return query.order_by(User.created_at.desc()).all()


@admin_router.get("/users/{user_id}/transactions", response_model=list[TxOut])
def user_transactions(user_id: int, limit: int = Query(100, ge=1, le=500),
                      db: Session = Depends(get_db)):
    if not db.get(User, user_id):
        raise HTTPException(404, "用户不存在")
    return db.query(TokenTx).filter(TokenTx.user_id == user_id)\
        .order_by(TokenTx.created_at.desc()).limit(limit).all()


@admin_router.post("/users/{user_id}/recharge", response_model=UserOut)
def recharge(user_id: int, payload: RechargeIn,
             admin: User = Depends(require_admin),
             db: Session = Depends(get_db)):
    """充值/扣减 token。amount 可正可负，但不能把余额扣成负数。"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if payload.amount == 0:
        raise HTTPException(400, "变动数量不能为 0")
    if payload.amount < 0 and user.role != "admin" and user.token_balance + payload.amount < 0:
        raise HTTPException(400, f"余额不足（当前 {user.token_balance}，尝试扣减 {abs(payload.amount)}）")
    if user.role == "admin" and payload.amount < 0:
        raise HTTPException(400, "管理员额度无限，无需扣减")
    charge_tokens(db, user, payload.amount, "recharge" if payload.amount > 0 else "adjust",
                  note=payload.note or f"管理员 {admin.username} 操作")
    db.commit()
    db.refresh(user)
    return user


@admin_router.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: RegisterIn, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "用户名已存在")
    user = User(username=username, password_hash=hash_password(payload.password),
                role="user", token_balance=SIGNUP_BONUS)
    db.add(user)
    db.flush()
    db.add(TokenTx(user_id=user.id, amount=SIGNUP_BONUS, balance_after=SIGNUP_BONUS,
                   reason="signup_bonus", note="管理员创建赠送"))
    db.commit()
    db.refresh(user)
    return user


@admin_router.post("/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: int, payload: SetRoleIn,
             admin: User = Depends(require_admin),
             db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id and payload.role != "admin":
        raise HTTPException(400, "不能降级自己的管理员角色")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@admin_router.post("/users/{user_id}/active", response_model=UserOut)
def set_active(user_id: int, payload: SetActiveIn,
               admin: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id and not payload.is_active:
        raise HTTPException(400, "不能禁用自己")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@admin_router.post("/users/{user_id}/password", response_model=UserOut)
def reset_password(user_id: int, payload: ResetPasswordIn,
                   db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user


@admin_router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(400, "不能删除自己")
    db.delete(user)
    db.commit()


@admin_router.get("/reports")
def all_reports(limit: int = Query(100, ge=1, le=500),
                q: str = Query("", description="按用户/任务名/URL 模糊搜索"),
                db: Session = Depends(get_db)):
    """全部用户的报告总览：报告 + 归属用户 + 任务名。"""
    query = db.query(MonitorReport, MonitorTask, User)\
        .outerjoin(MonitorTask, MonitorReport.task_id == MonitorTask.id)\
        .outerjoin(User, MonitorTask.user_id == User.id)
    if q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter(or_(User.username.ilike(kw),
                                 MonitorTask.name.ilike(kw),
                                 MonitorTask.url.ilike(kw)))
    rows = query.order_by(MonitorReport.created_at.desc()).limit(limit).all()
    out = []
    for rep, task, owner in rows:
        out.append({
            "id": rep.id,
            "task_id": rep.task_id,
            "task_name": getattr(task, "name", "") or "",
            "url": getattr(task, "url", "") or "",
            "username": getattr(owner, "username", "") or "",
            "user_id": getattr(owner, "id", None),
            "overall_score": rep.overall_score,
            "grade": getattr(rep, "grade", "") or "",
            "grade_label": getattr(rep, "grade_label", "") or "",
            "eeat_score": ((rep.eeat or {}).get("overall") if isinstance(rep.eeat, dict) else None),
            "created_at": rep.created_at,
        })
    return out


@admin_router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """管理台总览：用户数 / token 发放量 / 消耗量。"""
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_balance = db.query(func.coalesce(func.sum(User.token_balance), 0)).scalar()
    consumed = db.query(func.coalesce(func.sum(TokenTx.amount), 0))\
        .filter(TokenTx.reason == "consume").scalar()
    recharged = db.query(func.coalesce(func.sum(TokenTx.amount), 0))\
        .filter(TokenTx.reason.in_(["recharge", "signup_bonus"])).scalar()
    return {
        "total_users": total_users,
        "total_balance": total_balance,
        "total_recharged": recharged,
        "total_consumed": consumed,
        "task_cost": TASK_COST,
    }
