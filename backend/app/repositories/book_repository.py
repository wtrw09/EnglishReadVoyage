from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.repositories.base_repository import BaseRepository
from app.models.database_models import Book

class BookRepository(BaseRepository[Book]):
    """Book-specific repository operations."""
    
    async def get_by_title(self, db: AsyncSession, title: str) -> List[Book]:
        """Get books by title (partial match)."""
        result = await db.execute(
            select(Book).where(Book.title.contains(title))
        )
        return result.scalars().all()

book_repository = BookRepository(Book)
