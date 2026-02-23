"""User repository for database operations."""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.database_models import User


class UserRepository:
    """Repository for user data access."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()
    
    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Get user by username."""
        result = await db.execute(select(User).where(User.username == username))
        return result.scalars().first()
    
    @staticmethod
    async def get_by_invitation_code(db: AsyncSession, code: str) -> Optional[User]:
        """Get user by invitation code."""
        result = await db.execute(
            select(User).where(User.invitation_code == code)
        )
        return result.scalars().first()
    
    @staticmethod
    async def get_all(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination."""
        result = await db.execute(
            select(User).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def create(
        db: AsyncSession,
        username: str,
        password_hash: str,
        role: str = "user",
        invitation_code: Optional[str] = None,
        invitation_expires: Optional[object] = None
    ) -> User:
        """Create a new user."""
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=False,
            invitation_code=invitation_code,
            invitation_expires=invitation_expires
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def update(db: AsyncSession, user: User, **kwargs) -> User:
        """Update user fields."""
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await db.flush()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def delete(db: AsyncSession, user: User) -> bool:
        """Delete user."""
        await db.delete(user)
        return True
    
    @staticmethod
    async def is_admin(user: User) -> bool:
        """Check if user is admin."""
        return user.role == "admin"
    