"""分类业务逻辑服务层"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_

from app.models.database_models import Category, BookCategoryRel, Book, ReadingProgress
from app.schemas.category import CategoryResponse, BookWithCategory, BookGroup


class CategoryService:
    """分类相关业务逻辑服务层"""

    async def list_categories(self, db: AsyncSession, user_id: int) -> List[CategoryResponse]:
        """获取当前用户的所有分类"""
        stmt = select(Category).where(
            (Category.user_id == user_id) | (Category.type == 'system')
        ).order_by(Category.id)
        result = await db.execute(stmt)
        categories = result.scalars().all()

        return [
            CategoryResponse(
                id=c.id,
                name=c.name,
                type=c.type,
                user_id=c.user_id
            ) for c in categories
        ]

    async def create_category(self, db: AsyncSession, user_id: int, name: str) -> CategoryResponse:
        """创建新分类"""
        # 检查是否已存在同名分类
        stmt = select(Category).where(
            and_(Category.name == name, Category.user_id == user_id)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(f"分类 '{name}' 已存在")

        # 创建新分类
        category = Category(
            name=name,
            type='user',
            user_id=user_id
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)

        return CategoryResponse(
            id=category.id,
            name=category.name,
            type=category.type,
            user_id=category.user_id
        )

    async def update_category(
        self, db: AsyncSession, category_id: int, user_id: int, new_name: str
    ) -> Optional[CategoryResponse]:
        """更新分类名称"""
        stmt = select(Category).where(
            and_(Category.id == category_id, Category.user_id == user_id, Category.type == 'user')
        )
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            return None

        category.name = new_name
        await db.commit()
        await db.refresh(category)

        return CategoryResponse(
            id=category.id,
            name=category.name,
            type=category.type,
            user_id=category.user_id
        )

    async def delete_category(
        self, db: AsyncSession, category_id: int, user_id: int
    ) -> bool:
        """删除分类"""
        stmt = select(Category).where(
            and_(Category.id == category_id, Category.user_id == user_id, Category.type == 'user')
        )
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            return False

        # 删除该分类下的所有书籍关联
        stmt_rel = delete(BookCategoryRel).where(
            and_(BookCategoryRel.category_id == category_id, BookCategoryRel.user_id == user_id)
        )
        await db.execute(stmt_rel)

        # 删除分类
        await db.delete(category)
        await db.commit()

        return True

    async def add_book_to_category(
        self, db: AsyncSession, book_id: str, category_id: int, user_id: int
    ) -> bool:
        """将书籍添加到分类"""
        # 检查书籍是否存在
        stmt_book = select(Book).where(Book.id == book_id)
        result = await db.execute(stmt_book)
        book = result.scalar_one_or_none()

        if not book:
            return False

        # 如果 category_id 为 0，表示移动到"未分组"，删除所有分类关联
        if category_id == 0:
            stmt_del = delete(BookCategoryRel).where(
                and_(BookCategoryRel.book_id == book_id, BookCategoryRel.user_id == user_id)
            )
            await db.execute(stmt_del)
            await db.commit()
            return True

        # 检查分类是否存在
        stmt_cat = select(Category).where(
            (Category.id == category_id) | (Category.type == 'system')
        )
        result = await db.execute(stmt_cat)
        category = result.scalar_one_or_none()

        if not category:
            return False

        # 检查是否已有该书籍在该用户下的分类关联
        stmt_rel = select(BookCategoryRel).where(
            and_(BookCategoryRel.book_id == book_id, BookCategoryRel.user_id == user_id)
        )
        result = await db.execute(stmt_rel)
        existing_rel = result.scalar_one_or_none()

        if existing_rel:
            # 更新已有关联
            existing_rel.category_id = category_id
        else:
            # 创建新关联
            rel = BookCategoryRel(
                book_id=book_id,
                category_id=category_id,
                user_id=user_id
            )
            db.add(rel)

        await db.commit()
        return True

    async def remove_book_from_category(
        self, db: AsyncSession, book_id: str, category_id: int, user_id: int
    ) -> bool:
        """从分类中移除书籍"""
        stmt = delete(BookCategoryRel).where(
            and_(
                BookCategoryRel.book_id == book_id,
                BookCategoryRel.category_id == category_id,
                BookCategoryRel.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        await db.commit()

        return result.rowcount > 0

    async def get_books_grouped(
        self, db: AsyncSession, user_id: int
    ) -> List[BookGroup]:
        """获取按分类分组的书籍列表"""
        # 获取当前用户的所有分类
        stmt = select(Category).where(
            (Category.user_id == user_id) | (Category.type == 'system')
        ).order_by(Category.id)
        result = await db.execute(stmt)
        categories = result.scalars().all()

        # 获取该用户关联的书籍ID列表
        stmt_rels = select(BookCategoryRel).where(BookCategoryRel.user_id == user_id)
        result = await db.execute(stmt_rels)
        book_cats = result.scalars().all()

        # 构建 book_id -> category_id 映射
        book_to_cat = {rel.book_id: rel.category_id for rel in book_cats}

        # 获取所有书籍
        stmt_books = select(Book)
        result = await db.execute(stmt_books)
        all_books = result.scalars().all()

        # 获取用户的阅读进度（包含已读状态）
        stmt_progress = select(ReadingProgress).where(ReadingProgress.user_id == user_id)
        result = await db.execute(stmt_progress)
        progresses = result.scalars().all()
        # 构建 book_id -> is_read 映射
        book_read_status = {p.book_id: p.is_read for p in progresses}

        # 创建分类ID到分类信息的映射
        cat_map = {c.id: c for c in categories}

        # 收集所有有分类的书籍
        categorized_book_ids = set(book_to_cat.keys())

        # 按分类分组书籍
        groups: dict[int, list[BookWithCategory]] = {}
        for cat in categories:
            groups[cat.id] = []

        for book in all_books:
            if book.id in book_to_cat:
                cat_id = book_to_cat[book.id]
                if cat_id in groups:
                    groups[cat_id].append(BookWithCategory(
                        id=book.id,
                        title=book.title,
                        level="Unknown",
                        file_path=book.file_path,
                        page_count=book.page_count or 0,
                        cover_path=book.cover_path,
                        is_read=book_read_status.get(book.id, 0)
                    ))

        # 构建返回结果
        result_groups: list[BookGroup] = []

        for cat in categories:
            # 返回所有分类（包括空分组），但排除"未分组"类型
            result_groups.append(BookGroup(
                id=cat.id,
                name=cat.name,
                type=cat.type,
                books=groups[cat.id]
            ))

        # 添加未分组的书籍
        uncategorized_books = [
            BookWithCategory(
                id=book.id,
                title=book.title,
                level="Unknown",
                file_path=book.file_path,
                page_count=book.page_count or 0,
                cover_path=book.cover_path,
                is_read=book_read_status.get(book.id, 0)
            )
            for book in all_books
            if book.id not in categorized_book_ids
        ]

        if uncategorized_books:
            result_groups.insert(0, BookGroup(
                id=0,
                name="未分组",
                type="system",
                books=uncategorized_books
            ))

        return result_groups


    async def update_book_read_status(
        self, db: AsyncSession, book_id: str, user_id: int, is_read: int
    ) -> bool:
        """更新书籍的已读状态"""
        # 检查书籍是否存在
        stmt_book = select(Book).where(Book.id == book_id)
        result = await db.execute(stmt_book)
        book = result.scalar_one_or_none()

        if not book:
            return False

        # 查询是否已有阅读进度记录
        stmt = select(ReadingProgress).where(
            and_(ReadingProgress.book_id == book_id, ReadingProgress.user_id == user_id)
        )
        result = await db.execute(stmt)
        progress = result.scalar_one_or_none()

        if progress:
            # 更新已有记录
            progress.is_read = is_read
        else:
            # 创建新记录
            progress = ReadingProgress(
                user_id=user_id,
                book_id=book_id,
                current_page=1,
                is_read=is_read
            )
            db.add(progress)

        await db.commit()
        return True

    async def get_book_read_status(
        self, db: AsyncSession, book_id: str, user_id: int
    ) -> int:
        """获取书籍的已读状态"""
        stmt = select(ReadingProgress).where(
            and_(ReadingProgress.book_id == book_id, ReadingProgress.user_id == user_id)
        )
        result = await db.execute(stmt)
        progress = result.scalar_one_or_none()

        return progress.is_read if progress else 0


category_service = CategoryService()
