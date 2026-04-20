"""FastAPI端点依赖注入。"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.core.config import get_settings
from app.models.database_models import User
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

settings = get_settings()
# OAuth2PasswordBearer，tokenUrl参数使Swagger在登录后自动授权
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _mask_token(token: str) -> str:
    """脱敏token，只显示前5字符"""
    if not token:
        return "None"
    return f"{token[:5]}...***"


def _mask_headers(headers: dict, max_len: int = 200) -> str:
    """脱敏请求头，只显示部分信息"""
    if not headers:
        return "{}"
    # 只记录关键header名称，不记录值
    header_names = list(headers.keys())
    masked = f"[{', '.join(header_names)}]"
    # 限制长度
    if len(masked) > max_len:
        masked = masked[:max_len] + "..."
    return masked


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    request: Request = None
) -> User:
    """从JWT令牌获取当前已认证用户。
    
    Args:
        db: 数据库会话
        token: 来自Authorization头的JWT令牌
        
    Returns:
        当前用户对象
        
    Raises:
        HTTPException: 如果令牌无效或用户未找到
    """
    import logging
    logger = logging.getLogger(__name__)
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
   
    # 调试：打印所有请求头（脱敏）
    if request:
        auth_header = request.headers.get('authorization')
        masked_auth = f"{auth_header[:10]}...***" if auth_header and len(auth_header) > 10 else (auth_header or "None")
    
    if token is None:
        raise credentials_exception
    
    payload = verify_token(token)
    if payload is None:
        
        raise credentials_exception
    
    user_id: int = payload.get("sub")

    
    if user_id is None:
        raise credentials_exception
    
    # 从数据库获取用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if user is None: 
        raise credentials_exception
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前用户并验证管理员角色。
    
    Args:
        current_user: 当前已认证用户
        
    Returns:
        如果是管理员则返回当前用户
        
    Raises:
        HTTPException: 如果用户不是管理员
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="未授权。需要管理员角色。"
        )
    
    return current_user


def get_required_scopes_for_route(route_path: str) -> list[str]:
    """获取特定路由所需的作用域。
    
    Args:
        route_path: 路由路径（例如："/books/list"）
        
    Returns:
        所需作用域/角色列表
    """
    # 路由到所需角色的映射
    route_scopes = {
        # 书籍端点 - 所有已认证用户可访问
        "/books": ["user", "admin"],
        "/books/list": ["user", "admin"],
        
        # TTS端点 - 所有已认证用户可访问
        "/tts": ["user", "admin"],
        
        # 认证端点 - 用户信息可由自己访问，其他由管理员访问
        "/auth/me": ["user", "admin"],
        "/auth/users": ["admin"],
        "/auth/users/": ["admin"],
        "/auth/activate": ["user", "admin"],
        "/config/auth-strategy": ["admin"],
    }
    
    # 检查路由是否匹配任何模式
    for route, scopes in route_scopes.items():
        if route_path.startswith(route):
            return scopes
    
    # 默认：需要认证
    return ["user", "admin"]


async def verify_route_access(
    current_user: User = Depends(get_current_user),
    required_role: str = "user"
) -> User:
    """验证用户是否拥有该路由所需的角色。
    
    Args:
        current_user: 当前已认证用户
        required_role: 所需角色（"user"或"admin"）
        
    Returns:
        如果已授权则返回当前用户
        
    Raises:
        HTTPException: 如果用户没有所需角色
    """
    if required_role == "admin" and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="未授权。需要管理员角色。"
        )
    
    return current_user
