"""JWT和密码哈希的安全工具"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.core.config import get_settings
import uuid

settings = get_settings()

# JWT配置
ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY


def hash_password(password: str) -> str:
    """使用bcrypt哈希密码"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码与哈希值"""
    try:
        # bcrypt.checkpw期望两个参数都是字节
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)
    except ValueError:
        # 无效的哈希格式
        return False


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建JWT访问令牌
    
    参数:
        data: 包含令牌声明的字典（例如：{"sub": user_id}）
        expires_delta: 令牌过期时间差
        
    返回:
        编码的JWT令牌
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """验证并解码JWT令牌
    
    参数:
        token: 要验证的JWT令牌
        
    返回:
        如果有效则返回令牌负载，否则返回None
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"[Token Verify] Success, payload: {payload}")
        return payload
    except JWTError as e:
        logger.warning(f"[Token Verify] Failed: {e}")
        return None


def generate_invitation_code() -> str:
    """生成随机邀请码"""
    return str(uuid.uuid4())


def get_invitation_expiry() -> datetime:
    """获取邀请码过期日期时间"""
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.INVITATION_CODE_EXPIRE_MINUTES
    )
