"""身份认证服务层。"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_invitation_code,
    get_invitation_expiry
)
from app.repositories.user_repository import UserRepository
from app.models.database_models import User


class AuthService:
    """身份认证操作服务。"""
    
    @staticmethod
    async def login(
        db: AsyncSession,
        username: str,
        password: str
    ) -> Optional[str]:
        """验证用户身份并返回JWT令牌。
        
        Args:
            db: 数据库会话
            username: 用户名
            password: 用户密码
            
        Returns:
            如果凭证有效则返回JWT访问令牌,否则返回None
        """
        user = await UserRepository.get_by_username(db, username)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.password_hash):
            return None
        
        # 创建包含user_id和role的JWT令牌(根据JWT规范sub必须是字符串)
        token = create_access_token(data={"sub": str(user.id), "role": user.role})
        return token
    
    @staticmethod
    async def create_user_by_admin(
        db: AsyncSession,
        username: str
    ) -> Tuple[User, str]:
        """创建新用户并生成邀请码。
        
        Args:
            db: 数据库会话
            username: 新用户的用户名
            
        Returns:
            元组:(创建的用户, 邀请码)
            
        Raises:
            ValueError: 如果用户名已存在
        """
        # 检查用户名是否存在
        existing_user = await UserRepository.get_by_username(db, username)
        if existing_user:
            raise ValueError(f"用户名 '{username}' 已存在")
        
        # 生成邀请码和过期时间
        invitation_code = generate_invitation_code()
        invitation_expires = get_invitation_expiry()
        
        # 创建临时密码(将在激活时被替换)
        temp_password = hash_password(invitation_code)
        
        # 创建用户
        user = await UserRepository.create(
            db=db,
            username=username,
            password_hash=temp_password,
            role="user",
            invitation_code=invitation_code,
            invitation_expires=invitation_expires
        )
        
        await db.commit()
        
        return user, invitation_code
    
    @staticmethod
    async def activate_user(
        db: AsyncSession,
        invitation_code: str,
        password: str
    ) -> Optional[User]:
        """使用邀请码激活用户并设置密码。
        
        Args:
            db: 数据库会话
            invitation_code: 用户的邀请码
            password: 要设置的新密码
            
        Returns:
            如果成功则返回激活的用户,否则返回None
            
        Raises:
            ValueError: 如果邀请码无效或已过期
        """
        # 通过邀请码查找用户
        user = await UserRepository.get_by_invitation_code(db, invitation_code)
        
        if not user:
            raise ValueError("Invalid invitation code")
        
        # 检查邀请码是否过期（处理无时区的datetime）
        if user.invitation_expires is None:
            raise ValueError("Invitation code has expired")
        now = datetime.now(timezone.utc)
        expires = user.invitation_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise ValueError("Invitation code has expired")
        
        # 更新用户: 设置密码、激活、清除邀请码
        hashed_password = hash_password(password)
        user = await UserRepository.update(
            db=db,
            user=user,
            password_hash=hashed_password,
            is_active=True,
            invitation_code=None,
            invitation_expires=None
        )
        
        await db.commit()
        
        return user
    
    @staticmethod
    async def reset_password_by_admin(
        db: AsyncSession,
        user_id: int,
        new_password: str
    ) -> Optional[User]:
        """重置用户密码(仅限管理员)。

        Args:
            db: 数据库会话
            user_id: 要重置密码的用户ID
            new_password: 新密码

        Returns:
            如果成功则返回更新后的用户,如果用户未找到则返回None
        """
        user = await UserRepository.get_by_id(db, user_id)

        if not user:
            return None

        hashed_password = hash_password(new_password)
        user = await UserRepository.update(
            db=db,
            user=user,
            password_hash=hashed_password
        )

        await db.commit()

        return user

    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: int
    ) -> Optional[User]:
        """根据ID获取用户。

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            用户对象,未找到则返回None
        """
        return await UserRepository.get_by_id(db, user_id)

    @staticmethod
    async def get_user_by_username(
        db: AsyncSession,
        username: str
    ) -> Optional[User]:
        """根据用户名获取用户。

        Args:
            db: 数据库会话
            username: 用户名

        Returns:
            用户对象,未找到则返回None
        """
        return await UserRepository.get_by_username(db, username)

    @staticmethod
    async def list_users(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> list[User]:
        """获取用户列表。

        Args:
            db: 数据库会话
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            用户列表
        """
        return await UserRepository.get_all(db, skip=skip, limit=limit)

    @staticmethod
    async def update_current_user(
        db: AsyncSession,
        current_user: User,
        username: Optional[str] = None
    ) -> User:
        """更新当前用户信息。

        Args:
            db: 数据库会话
            current_user: 当前用户
            username: 新用户名(可选)

        Returns:
            更新后的用户

        Raises:
            ValueError: 如果用户名已被占用
        """
        if username:
            existing = await UserRepository.get_by_username(db, username)
            if existing and existing.id != current_user.id:
                raise ValueError("用户名已被占用")
            current_user = await UserRepository.update(
                db, current_user, username=username
            )
            await db.commit()

        return current_user

    @staticmethod
    async def update_user_by_admin(
        db: AsyncSession,
        user_id: int,
        username: Optional[str] = None,
        role: Optional[str] = None
    ) -> Optional[User]:
        """管理员更新用户信息。

        Args:
            db: 数据库会话
            user_id: 要更新的用户ID
            username: 新用户名(可选)
            role: 新角色(可选)

        Returns:
            更新后的用户,未找到则返回None

        Raises:
            ValueError: 如果用户名已被占用
        """
        user = await UserRepository.get_by_id(db, user_id)
        if not user:
            return None

        update_kwargs = {}

        if username:
            existing = await UserRepository.get_by_username(db, username)
            if existing and existing.id != user_id:
                raise ValueError("用户名已被占用")
            update_kwargs["username"] = username

        if role:
            update_kwargs["role"] = role

        if update_kwargs:
            user = await UserRepository.update(db, user, **update_kwargs)
            await db.commit()

        return user

    @staticmethod
    async def delete_user(
        db: AsyncSession,
        user_id: int
    ) -> Optional[User]:
        """删除用户(不能删除默认管理员)。

        Args:
            db: 数据库会话
            user_id: 要删除的用户ID

        Returns:
            被删除的用户,未找到则返回None

        Raises:
            ValueError: 如果用户是默认管理员
        """
        user = await UserRepository.get_by_id(db, user_id)

        if not user:
            return None

        if user.username == "admin":
            raise ValueError("不能删除默认管理员用户")

        await UserRepository.delete(db, user)
        await db.commit()

        return user

    @staticmethod
    async def get_user_invitation_code(
        db: AsyncSession,
        user_id: int
    ) -> Optional[User]:
        """获取未激活用户的邀请码。

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            用户对象(如果用户未激活),如果用户不存在或已激活则返回None
        """
        user = await UserRepository.get_by_id(db, user_id)

        if not user:
            return None

        # 只返回未激活用户的邀请码
        if user.is_active:
            return None

        return user

    @staticmethod
    async def update_current_user_password(
        db: AsyncSession,
        current_user: User,
        old_password: str,
        new_password: str
    ) -> User:
        """当前用户修改自己的密码。

        Args:
            db: 数据库会话
            current_user: 当前用户
            old_password: 旧密码
            new_password: 新密码

        Returns:
            更新后的用户

        Raises:
            ValueError: 如果旧密码不正确或新旧密码相同
        """
        # 验证旧密码
        if not verify_password(old_password, current_user.password_hash):
            raise ValueError("旧密码不正确")

        # 检查新旧密码是否相同
        if old_password == new_password:
            raise ValueError("新密码不能与旧密码相同")

        # 更新密码
        hashed_password = hash_password(new_password)
        user = await UserRepository.update(
            db, current_user, password_hash=hashed_password
        )
        await db.commit()

        return user
