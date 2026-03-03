"""分类管理API端点"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse, BookCategoryRequest, BookWithCategory, BookGroup
from app.services.category_service import category_service
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User


router = APIRouter()


@router.get("", response_model=List[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有分类"""
    return await category_service.list_categories(db, current_user.id)


@router.post("", response_model=CategoryResponse)
async def create_category(
    category: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新分类"""
    return await category_service.create_category(db, current_user.id, category.name)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新分类名称"""
    result = await category_service.update_category(db, category_id, current_user.id, category.name)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分类未找到或无权限修改"
        )
    return result


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除分类"""
    success = await category_service.delete_category(db, category_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分类未找到或无权限删除"
        )
    return {"success": True, "message": "分类已删除"}


@router.post("/books")
async def add_book_to_category(
    request: BookCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将书籍添加到分类"""
    success = await category_service.add_book_to_category(
        db, request.book_id, request.category_id, current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍或分类未找到"
        )
    return {"success": True, "message": "书籍已添加到分类"}


@router.delete("/{category_id}/books/{book_id}")
async def remove_book_from_category(
    category_id: int,
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从分类中移除书籍"""
    success = await category_service.remove_book_from_category(
        db, book_id, category_id, current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍或分类未找到"
        )
    return {"success": True, "message": "书籍已从分类中移除"}


@router.get("/books/grouped", response_model=List[BookGroup])
async def get_books_grouped(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取按分类分组的书籍列表"""
    return await category_service.get_books_grouped(db, current_user.id)


@router.post("/books/{book_id}/read-status")
async def update_book_read_status(
    book_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新书籍的已读状态
    
    请求体: {"is_read": 1} 或 {"is_read": 0}
    """
    is_read = request.get("is_read", 0)
    success = await category_service.update_book_read_status(
        db, book_id, current_user.id, is_read
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )
    status_text = "已读" if is_read else "未读"
    return {"success": True, "message": f"书籍已标记为{status_text}"}


@router.get("/books/{book_id}/read-status")
async def get_book_read_status(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取书籍的已读状态"""
    is_read = await category_service.get_book_read_status(db, book_id, current_user.id)
    return {"book_id": book_id, "is_read": is_read}
