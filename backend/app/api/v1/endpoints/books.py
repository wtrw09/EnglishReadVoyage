"""书籍管理API端点。"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.book import BookInfo, BookDetail
from app.services.book_service import book_service
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User


router = APIRouter()


@router.get("", response_model=List[BookInfo])
@router.get("/", response_model=List[BookInfo])
async def list_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有可用书籍列表。"""
    return await book_service.list_books(db)


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取书籍详细信息，包括所有页面。"""
    book = await book_service.get_book_detail(db, book_id)
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )
    
    return book
