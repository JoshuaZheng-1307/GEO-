"""Pydantic 请求/响应模型。"""
import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class TaskCreate(BaseModel):
    name: str = Field(..., max_length=200, description="任务名称")
    url: HttpUrl = Field(..., description="目标站点 URL")
    keywords: list[str] = Field(default_factory=list,
                                description="监测关键词（选填：留空则由系统分析官网自动生成）")
    hint: Optional[str] = Field(None, max_length=200,
                                description="行业大方向（选填：如『建材』『智能卫浴』，用于校准自动关键词）")
    engines: Optional[list[str]] = None  # 不传则使用配置中的默认引擎


class ProfileIn(BaseModel):
    url: HttpUrl = Field(..., description="目标站点 URL")
    hint: Optional[str] = Field(None, max_length=200, description="行业大方向（选填）")


class TaskOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    url: str
    keywords: list[str]
    hint: Optional[str] = ""
    engines: list[str]
    status: str
    last_message: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


class ReportOut(BaseModel):
    id: int
    task_id: int
    url: str
    overall_score: float
    grade: str
    dimensions: dict[str, Any]
    core_metrics: dict[str, Any]
    eeat: Optional[dict[str, Any]] = None   # EEAT 四维（旧报告可能为 None）
    findings: dict[str, Any]
    performance: dict[str, Any]
    keyword_matrix: dict[str, Any]
    suggestions: dict[str, Any]
    signature: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


class ProgressOut(BaseModel):
    task_id: int
    status: str
    stage: str
    percent: int
    message: str


# ---------------------------------------------------------------------------
# 账号 / token
# ---------------------------------------------------------------------------
class RegisterIn(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    token_balance: int
    is_active: bool
    company_name: Optional[str] = ""
    business: Optional[str] = ""
    onboarded: bool = False
    created_at: dt.datetime

    class Config:
        from_attributes = True


class TxOut(BaseModel):
    id: int
    user_id: int
    amount: int
    balance_after: int
    reason: str
    note: str
    task_id: Optional[int] = None
    created_at: dt.datetime

    class Config:
        from_attributes = True


class RechargeIn(BaseModel):
    amount: int = Field(..., description="正数充值，负数扣减")
    note: Optional[str] = Field(None, max_length=200)


class SetRoleIn(BaseModel):
    role: str = Field(..., pattern="^(admin|user)$")


class SetActiveIn(BaseModel):
    is_active: bool


class ResetPasswordIn(BaseModel):
    password: str = Field(..., min_length=6, max_length=128)


class TokenInfoOut(BaseModel):
    task_cost: int
    signup_bonus: int


class OnboardingIn(BaseModel):
    """注册后的首次免费分析：公司名称 + 业务项目 + 官网链接。"""
    company_name: str = Field(..., min_length=1, max_length=200)
    business: str = Field("", max_length=500)
    url: str

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("官网链接必须以 http:// 或 https:// 开头")
        return v


class AdminReportOut(BaseModel):
    """管理端报告总览：报告 + 归属用户 + 任务信息。"""
    id: int
    task_id: int
    task_name: Optional[str] = ""
    url: Optional[str] = ""
    username: Optional[str] = ""
    user_id: Optional[int] = None
    overall_score: Optional[float] = None
    grade: Optional[str] = ""
    grade_label: Optional[str] = ""
    eeat_score: Optional[float] = None
    created_at: dt.datetime
