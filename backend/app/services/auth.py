"""认证与计费：pbkdf2 密码哈希 + 手写 HS256 JWT + token 扣费流水。

不引入第三方依赖（无 passlib / python-jose），全部标准库实现：
  - 密码：PBKDF2-HMAC-SHA256，10 万轮 + 随机盐
  - 会话：JWT(HS256)，payload 为 {uid, role, exp}
  - 计费：任务创建即预扣，失败自动退款；admin 角色额度无限
"""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import TokenTx, User

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
TASK_COST = 10          # 每次监测消耗 token
SIGNUP_BONUS = 50       # 注册赠送 token
_PBKDF2_ROUNDS = 100_000
_TOKEN_TTL_SECONDS = 7 * 24 * 3600   # 7 天


def _secret() -> bytes:
    """JWT 签名密钥：优先环境变量，否则用数据库 URL 派生（单机部署够用）。"""
    env = os.environ.get("GEO_JWT_SECRET")
    if env:
        return env.encode()
    return hashlib.sha256(("jwt|" + settings.DATABASE_URL).encode()).digest()


# ---------------------------------------------------------------------------
# 密码
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return salt.hex() + "$" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex),
                                 _PBKDF2_ROUNDS)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# JWT（HS256，标准库实现）
# ---------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_access_token(user: User) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "uid": user.id,
        "role": user.role,
        "exp": int(time.time()) + _TOKEN_TTL_SECONDS,
    }
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url(hmac.new(_secret(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"


def decode_access_token(token: str) -> dict:
    try:
        h, p, sig = token.split(".")
    except ValueError:
        raise HTTPException(401, "令牌格式错误")
    expect = _b64url(hmac.new(_secret(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expect):
        raise HTTPException(401, "令牌签名无效")
    payload = json.loads(_b64url_decode(p))
    if payload.get("exp", 0) < time.time():
        raise HTTPException(401, "登录已过期，请重新登录")
    return payload


# ---------------------------------------------------------------------------
# FastAPI 依赖
# ---------------------------------------------------------------------------
def get_current_user(authorization: str = Header(default=""),
                     db: Session = Depends(get_db)) -> User:
    """解析 Authorization: Bearer <jwt>，返回当前用户。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    payload = decode_access_token(authorization[7:])
    user = db.get(User, payload.get("uid"))
    if not user or not user.is_active:
        raise HTTPException(401, "账号不存在或已被禁用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user


# ---------------------------------------------------------------------------
# 计费
# ---------------------------------------------------------------------------
def charge_tokens(db: Session, user: User, amount: int, reason: str,
                  note: str = "", task_id: int | None = None) -> int:
    """变动 token 余额并写流水，返回变动后的余额。

    admin 角色额度无限：不扣余额、不写消费流水（充值/调整流水照常记录）。
    调用方自行保证 amount 与 reason 匹配（消费为负、充值/退款为正）。
    """
    if reason == "consume" and user.role == "admin":
        return user.token_balance
    user.token_balance += amount
    db.add(TokenTx(user_id=user.id, amount=amount, balance_after=user.token_balance,
                   reason=reason, note=note[:200], task_id=task_id))
    return user.token_balance


def ensure_can_run(user: User) -> None:
    """任务可运行性检查：余额足够或为 admin。"""
    if user.role == "admin":
        return
    if user.token_balance < TASK_COST:
        raise HTTPException(402, f"token 余额不足（需 {TASK_COST}，余 {user.token_balance}），请联系管理员充值")
