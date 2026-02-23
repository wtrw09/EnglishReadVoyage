from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    """Base repository for CRUD operations using SQLAlchemy Async."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        """Get by ID."""
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalars().first()

    async def get_multi(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records."""
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(
        self,
        db: AsyncSession,
        obj_in_data: dict
    ) -> ModelType:
        """Create new record."""
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        db_obj: ModelType,
        obj_in_data: dict
    ) -> ModelType:
        """Update record."""
        for field, value in obj_in_data.items():
            setattr(db_obj, field, value)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, id: Any) -> bool:
        """Delete record."""
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            return True
        return False
