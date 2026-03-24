"""管理员管理用户书籍分组API端点"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse, BookWithCategory, BookGroup
from app.services.category_service import category_service
from app.core.database import get_db
from app.api.dependencies import get_current_admin
from app.models.database_models import User, Book


router = APIRouter()


@router.get("/users/{user_id}/categories", response_model=List[CategoryResponse])
async def list_user_categories(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """获取指定用户的所有分组（管理员接口）
    
    返回被管理用户的分组结构
    """
    # 验证用户是否存在
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 返回被管理用户的分组
    return await category_service.list_categories(db, user_id)


@router.post("/users/{user_id}/categories", response_model=CategoryResponse)
async def create_user_category(
    user_id: int,
    category: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """为指定用户创建新分组（管理员接口）
    
    在被管理用户的分组下创建新分组
    """
    # 验证用户是否存在
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 使用被管理用户的ID创建分组
    return await category_service.create_category(db, user_id, category.name)


@router.put("/users/{user_id}/categories/{category_id}", response_model=CategoryResponse)
async def update_user_category(
    user_id: int,
    category_id: int,
    category: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """更新指定用户的分组名称（管理员接口）
    
    更新被管理用户的分组名称
    """
    # 使用被管理用户的ID
    result = await category_service.update_category(db, category_id, user_id, category.name)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分组未找到或无权限修改"
        )
    return result


@router.delete("/users/{user_id}/categories/{category_id}")
async def delete_user_category(
    user_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """删除指定用户的分组（管理员接口）
    
    删除被管理用户的分组
    """
    # 使用被管理用户的ID
    success = await category_service.delete_category(db, category_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分组未找到或无权限删除"
        )
    return {"success": True, "message": "分组已删除"}


@router.get("/users/{user_id}/categories/{category_id}/books", response_model=List[BookWithCategory])
async def get_category_books(
    user_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """获取指定分组内的书籍列表（管理员接口）"""
    # 获取该分组下的书籍
    groups = await category_service.get_books_grouped(db, user_id)

    for group in groups:
        if group.id == category_id:
            return group.books

    return []


@router.get("/users/{user_id}/books", response_model=List[BookWithCategory])
async def get_user_all_books(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """获取指定用户未添加的书籍（管理员接口，用于分配）"""
    # 验证用户是否存在
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 获取该用户已拥有的书籍ID
    from app.models.database_models import BookCategoryRel
    stmt_rels = select(BookCategoryRel.book_id).where(BookCategoryRel.user_id == user_id)
    result = await db.execute(stmt_rels)
    user_book_ids = {row[0] for row in result.fetchall()}

    # 获取用户没有的书籍
    if user_book_ids:
        stmt = select(Book).where(~Book.id.in_(user_book_ids)).order_by(Book.title)
    else:
        stmt = select(Book).order_by(Book.title)
    result = await db.execute(stmt)
    books = result.scalars().all()

    return [
        BookWithCategory(
            id=book.id,
            title=book.title,
            level="Unknown",
            file_path=book.file_path,
            page_count=book.page_count or 0,
            cover_path=book.cover_path,
            is_read=0
        )
        for book in books
    ]


@router.post("/users/{user_id}/categories/books")
async def assign_book_to_category(
    user_id: int,
    request: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """分配书籍到指定分组（管理员接口）

    请求体: {"book_id": "xxx", "category_id": 1}
    """
    book_id = request.get("book_id")
    category_id = request.get("category_id")

    if not book_id or category_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要参数 book_id 或 category_id"
        )

    # 验证用户是否存在
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    success = await category_service.add_book_to_category(db, book_id, category_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍或分组未找到"
        )
    return {"success": True, "message": "书籍已分配到分组"}


@router.delete("/users/{user_id}/categories/{category_id}/books/{book_id}")
async def remove_book_from_user_category(
    user_id: int,
    category_id: int,
    book_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """从指定用户的分组中移除书籍（管理员接口）"""
    success = await category_service.remove_book_from_category(db, book_id, category_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍或分组未找到"
        )
    return {"success": True, "message": "书籍已从分组中移除"}


@router.get("/users/{user_id}/categories/grouped", response_model=List[BookGroup])
async def get_user_books_grouped(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """获取指定用户按分组的所有书籍（管理员接口）"""
    # 验证用户是否存在
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    return await category_service.get_books_grouped(db, user_id)


@router.delete("/users/{user_id}/books/{book_id}")
async def delete_user_book(
    user_id: int,
    book_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """删除用户添加的书籍（完全移除，使其回到未添加书籍列表）"""
    # 验证用户是否存在
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    success = await category_service.delete_user_book(db, book_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户{user_id}没有书籍{book_id}"
        )
    return {"success": True, "message": "书籍已删除"}


@router.get("/users/{user_id}/books/grouped", response_model=List[BookGroup])
async def get_unadded_books_grouped(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """获取用户未添加的书籍（按分组分类，用于管理员分配书籍）
    
    显示管理员的分组结构，书籍按管理员的分类进行分组
    """
    # 验证用户是否存在
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 传递管理员ID，使未添加书籍按管理员的分组结构显示
    return await category_service.get_unadded_books_grouped(db, user_id, admin.id)
