"""用于身份验证的Pydantic模式"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """登录请求模式"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """登录响应模式"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str


class UserCreateByAdmin(BaseModel):
    """管理员创建新用户的模式"""
    username: str = Field(..., min_length=1, max_length=50)


class UserActivateRequest(BaseModel):
    """用户使用邀请码激活账户的模式"""
    invitation_code: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """用户信息响应模式"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime


class UserDetailResponse(BaseModel):
    """详细的用户信息响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    username: str
    role: str
    is_active: bool
    invitation_code: Optional[str] = None
    invitation_expires: Optional[datetime] = None
    created_at: datetime


class UserCreateResponse(BaseModel):
    """管理员创建用户时的响应"""
    user: UserResponse
    invitation_code: str
    invitation_expires: datetime


class UpdatePasswordRequest(BaseModel):
    """密码重置的模式"""
    new_password: str = Field(..., min_length=1)


class UpdateCurrentUserPasswordRequest(BaseModel):
    """当前用户更新自己密码的模式"""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class UpdateUserRequest(BaseModel):
    """更新用户信息的模式（由管理员操作）"""
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    role: Optional[str] = None
