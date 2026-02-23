from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.repositories.base_repository import BaseRepository
from app.models.database_models import ReadingProgress

class ReadingProgressRepository(BaseRepository[ReadingProgress]):
    """Reading progress specific repository operations."""

    async def get_progress(self, db: AsyncSession, user_id: int, book_id: str) -> Optional[ReadingProgress]:
        """Get progress for a specific user and book."""
        result = await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == user_id,
                ReadingProgress.book_id == book_id
            )
        )
        return result.scalars().first()

reading_progress_repository = ReadingProgressRepository(ReadingProgress)
