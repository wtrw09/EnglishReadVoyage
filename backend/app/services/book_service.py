"""Book service for business logic."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.book_repository import book_repository
from app.schemas.book import BookInfo, BookDetail
from app.utils.parser import MarkdownParser

class BookService:
    """Service layer for book-related business logic."""
    
    def __init__(self):
        self.repository = book_repository
        self.parser = MarkdownParser()
    
    async def list_books(self, db: AsyncSession) -> List[BookInfo]:
        """Get all books from DB."""
        books = await self.repository.get_multi(db)
        return [
            BookInfo(
                id=b.id,
                title=b.title,
                level="Unknown",  # 待从数据库获取或从标签解析
                file_path=b.file_path,
                page_count=b.page_count or 0
            ) for b in books
        ]
    
    async def get_book_detail(self, db: AsyncSession, book_id: str) -> Optional[BookDetail]:
        """Get detailed book info including HTML pages."""
        book = await self.repository.get(db, book_id)
        if not book:
            return None
        
        pages = self.parser.parse_file(book.file_path)
        
        return BookDetail(
            id=book.id,
            title=book.title,
            level="Unknown",
            pages=pages
        )

book_service = BookService()
