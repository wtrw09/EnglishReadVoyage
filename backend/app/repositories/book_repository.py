from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.repositories.base_repository import BaseRepository
from app.models.database_models import Book, BookCategoryRel


class BookRepository(BaseRepository[Book]):
    """Book-specific repository operations."""

    async def get_by_title(self, db: AsyncSession, title: str) -> List[Book]:
        """Get books by title (partial match)."""
        result = await db.execute(
            select(Book).where(Book.title.contains(title))
        )
        return result.scalars().all()

    async def get_by_category(self, db: AsyncSession, category_id: int, user_id: int) -> List[Book]:
        """Get books by category for a specific user."""
        result = await db.execute(
            select(Book)
            .join(BookCategoryRel, Book.id == BookCategoryRel.book_id)
            .where(
                BookCategoryRel.category_id == category_id,
                BookCategoryRel.user_id == user_id
            )
        )
        return result.scalars().all()

    async def get_uncategorized(self, db: AsyncSession, user_id: int) -> List[Book]:
        """Get books that are not assigned to any category for a user."""
        # First get all book_ids that have category assignments for this user
        result = await db.execute(
            select(BookCategoryRel.book_id).where(BookCategoryRel.user_id == user_id)
        )
        assigned_book_ids = [row[0] for row in result.fetchall()]

        # Then get all books that are not in that list
        if assigned_book_ids:
            result = await db.execute(
                select(Book).where(Book.id.not_in(assigned_book_ids))
            )
        else:
            result = await db.execute(select(Book))
        return result.scalars().all()


book_repository = BookRepository(Book)
