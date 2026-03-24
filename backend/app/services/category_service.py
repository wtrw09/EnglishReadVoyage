"""分类业务逻辑服务层"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_

from app.models.database_models import Category, BookCategoryRel, Book, ReadingProgress
from app.schemas.category import CategoryResponse, BookWithCategory, BookGroup


class CategoryService:
    """分类相关业务逻辑服务层"""

    async def list_categories(self, db: AsyncSession, user_id: int) -> List[CategoryResponse]:
        """获取当前用户的所有分类（排除重复的"未分组"，将"未分组"放在最后）"""
        stmt = select(Category).where(
            (Category.user_id == user_id) | (Category.type == 'system')
        ).order_by(Category.id)
        result = await db.execute(stmt)
        categories = result.scalars().all()

        # 过滤掉重复的"未分组"（只保留用户自己的"未分组"分类）
        seen_uncategorized = False
        filtered = []
        uncategorized_category = None
        
        for c in categories:
            if c.name == "未分组":
                if seen_uncategorized:
                    continue  # 跳过重复的"未分组"
                seen_uncategorized = True
                uncategorized_category = c  # 保存"未分组"分类
            else:
                filtered.append(c)
        
        # 将"未分组"分类添加到列表最后
        if uncategorized_category:
            filtered.append(uncategorized_category)

        return [
            CategoryResponse(
                id=c.id,
                name=c.name,
                type=c.type,
                user_id=c.user_id
            ) for c in filtered
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
        """更新分类名称（不支持"未分组"）"""
        stmt = select(Category).where(
            and_(Category.id == category_id, Category.user_id == user_id, Category.type == 'user')
        )
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            return None

        # 不允许修改"未分组"分类
        if category.name == '未分组':
            raise ValueError('不能修改"未分组"分类')

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
        """删除分类，同时删除关联的书籍记录（使书籍回到未添加状态）
        
        注意：不允许删除"未分组"分类
        """
        stmt = select(Category).where(
            and_(Category.id == category_id, Category.user_id == user_id, Category.type == 'user')
        )
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            return False

        # 不允许删除"未分组"分类
        if category.name == '未分组':
            raise ValueError('不能删除"未分组"分类')

        # 删除该分类下的所有书籍关联记录（使书籍回到"未添加"状态）
        # 注意：这只是删除用户的书籍关联，不是删除书籍本身
        stmt_del = delete(BookCategoryRel).where(
            and_(BookCategoryRel.category_id == category_id, BookCategoryRel.user_id == user_id)
        )
        await db.execute(stmt_del)

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

        # 如果 category_id 为 0，表示移动到"未分组"，设置 category_id 为 NULL
        if category_id == 0:
            # 检查是否已有该书籍在该用户下的分类关联
            stmt_rel = select(BookCategoryRel).where(
                and_(BookCategoryRel.book_id == book_id, BookCategoryRel.user_id == user_id)
            )
            result = await db.execute(stmt_rel)
            existing_rel = result.scalar_one_or_none()

            if existing_rel:
                # 更新已有关联，将 category_id 设为 NULL 表示未分组
                existing_rel.category_id = None
            else:
                # 创建新关联，category_id 为 NULL 表示未分组
                rel = BookCategoryRel(
                    book_id=book_id,
                    category_id=None,
                    user_id=user_id
                )
                db.add(rel)

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
        """从分类中移除书籍（设为未分组）"""
        # 将书籍的 category_id 设为 NULL，表示未分组
        from sqlalchemy import update
        stmt = update(BookCategoryRel).where(
            and_(
                BookCategoryRel.book_id == book_id,
                BookCategoryRel.category_id == category_id,
                BookCategoryRel.user_id == user_id
            )
        ).values(category_id=None)
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

        # 构建用户拥有的所有书籍ID集合
        user_book_ids = set(book_to_cat.keys())

        # 如果用户没有任何书籍，返回空
        if not user_book_ids:
            return []

        # 获取用户拥有的书籍详情（只查询用户拥有的书）
        stmt_books = select(Book).where(Book.id.in_(user_book_ids))
        result = await db.execute(stmt_books)
        user_books = result.scalars().all()

        # 创建书籍ID到书籍对象的映射
        book_map = {book.id: book for book in user_books}

        # 获取用户的阅读进度（包含已读状态）
        stmt_progress = select(ReadingProgress).where(ReadingProgress.user_id == user_id)
        result = await db.execute(stmt_progress)
        progresses = result.scalars().all()
        # 构建 book_id -> is_read 映射
        book_read_status = {p.book_id: p.is_read for p in progresses}

        # 按分类分组书籍
        groups: dict[int, list[BookWithCategory]] = {}
        for cat in categories:
            groups[cat.id] = []

        # 收集未分组的书籍ID
        uncategorized_book_ids = []
        uncategorized_books = []

        for book_id in user_book_ids:
            if book_id not in book_map:
                continue
            book = book_map[book_id]
            cat_id = book_to_cat.get(book_id)
            # 如果分类存在
            if cat_id and cat_id in groups:
                groups[cat_id].append(BookWithCategory(
                    id=book.id,
                    title=book.title,
                    level="Unknown",
                    file_path=book.file_path,
                    page_count=book.page_count or 0,
                    cover_path=book.cover_path,
                    is_read=book_read_status.get(book.id, 0)
                ))
            else:
                uncategorized_book_ids.append(book_id)
                uncategorized_books.append(BookWithCategory(
                    id=book.id,
                    title=book.title,
                    level="Unknown",
                    file_path=book.file_path,
                    page_count=book.page_count or 0,
                    cover_path=book.cover_path,
                    is_read=book_read_status.get(book.id, 0)
                ))

        # 对每个分组内的书籍按名称升序排序
        for cat_id in groups:
            groups[cat_id].sort(key=lambda x: x.title.lower())

        # 对未分组书籍按名称升序排序
        uncategorized_books.sort(key=lambda x: x.title.lower())

        # 构建返回结果
        result_groups: list[BookGroup] = []

        # 查找数据库中的"未分组"分类
        db_uncategorized = None
        for cat in categories:
            if cat.name == "未分组":
                db_uncategorized = cat
                break

        # 先添加其他分类（排除"未分组"）
        for cat in categories:
            if cat.name == "未分组":
                continue
            result_groups.append(BookGroup(
                id=cat.id,
                name=cat.name,
                type=cat.type,
                books=groups[cat.id]
            ))

        # 最后添加数据库中的"未分组"分类（放在最后面）
        if db_uncategorized:
            # 合并数据库"未分组"的书籍和未分类的书籍
            db_uncat_books = groups.get(db_uncategorized.id, [])
            merged_books = db_uncat_books + uncategorized_books
            # 去重
            seen = set()
            merged = []
            for b in merged_books:
                if b.id not in seen:
                    seen.add(b.id)
                    merged.append(b)
            merged.sort(key=lambda x: x.title.lower())
            result_groups.append(BookGroup(
                id=db_uncategorized.id,
                name=db_uncategorized.name,
                type=db_uncategorized.type,
                books=merged
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

    async def delete_user_book(self, db: AsyncSession, book_id: str, user_id: int) -> bool:
        """完全删除用户添加的书籍（删除所有分类关联和阅读进度）"""
        deleted = False

        # 删除分类关联
        stmt = delete(BookCategoryRel).where(
            and_(
                BookCategoryRel.book_id == book_id,
                BookCategoryRel.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        if result.rowcount > 0:
            deleted = True

        # 删除阅读进度
        stmt_progress = delete(ReadingProgress).where(
            and_(
                ReadingProgress.book_id == book_id,
                ReadingProgress.user_id == user_id
            )
        )
        result_progress = await db.execute(stmt_progress)
        if result_progress.rowcount > 0:
            deleted = True

        await db.commit()
        return deleted

    async def get_unadded_books_grouped(
        self, db: AsyncSession, user_id: int, admin_id: int = None
    ) -> List[BookGroup]:
        """获取用户未添加书籍的分组列表（按系统分类分组）
        
        Args:
            db: 数据库会话
            user_id: 被管理的用户ID
            admin_id: 管理员ID，用于显示管理员的分组结构（如果提供）
        """
        # 确定使用哪个用户的分组：如果提供了admin_id，使用管理员的分组；否则使用目标用户的分组
        category_user_id = admin_id if admin_id else user_id
        
        # 获取分类用户的分类（用户自己的和系统的）
        stmt = select(Category).where(
            (Category.user_id == category_user_id) | (Category.type == 'system')
        ).order_by(Category.id)
        result = await db.execute(stmt)
        categories = result.scalars().all()

        # 获取被管理用户已拥有的书籍ID
        stmt_rels = select(BookCategoryRel.book_id).where(BookCategoryRel.user_id == user_id)
        result = await db.execute(stmt_rels)
        user_book_ids = {row[0] for row in result.fetchall()}

        # 获取用户没有的书籍
        if user_book_ids:
            stmt = select(Book).where(~Book.id.in_(user_book_ids)).order_by(Book.title)
        else:
            stmt = select(Book).order_by(Book.title)
        result = await db.execute(stmt)
        all_books = result.scalars().all()

        # 创建书籍ID到书籍对象的映射
        book_map = {book.id: book for book in all_books}

        # 获取该管理员的书籍-分类关联（如果有admin_id）
        admin_book_to_cat = {}
        if admin_id:
            stmt_admin_rels = select(BookCategoryRel).where(BookCategoryRel.user_id == admin_id)
            result = await db.execute(stmt_admin_rels)
            admin_rels = result.scalars().all()
            for rel in admin_rels:
                if rel.book_id not in user_book_ids:
                    admin_book_to_cat[rel.book_id] = rel.category_id

        # 获取所有书籍的分类关联（用于没有admin_id时的默认行为）
        stmt_all_rels = select(BookCategoryRel)
        result = await db.execute(stmt_all_rels)
        all_rels = result.scalars().all()

        # 构建 book_id -> category_id 映射
        # 如果有admin_id，优先使用管理员的关联
        book_to_cat = {}
        for rel in all_rels:
            if rel.book_id not in user_book_ids:
                if rel.book_id not in book_to_cat:
                    # 优先使用管理员的关联
                    if admin_id and rel.user_id == admin_id:
                        book_to_cat[rel.book_id] = rel.category_id
                    elif not admin_id:
                        book_to_cat[rel.book_id] = rel.category_id

        # 按分类分组书籍
        groups: dict[int, list[BookWithCategory]] = {}
        for cat in categories:
            groups[cat.id] = []

        # 收集未分类的书籍
        uncategorized_books: list[BookWithCategory] = []

        for book_id in book_map.keys():
            book = book_map[book_id]
            # 如果有admin_id，优先使用管理员的分类映射
            cat_id = admin_book_to_cat.get(book_id) if admin_id else book_to_cat.get(book_id)
            if cat_id and cat_id in groups:
                groups[cat_id].append(BookWithCategory(
                    id=book.id,
                    title=book.title,
                    level="Unknown",
                    file_path=book.file_path,
                    page_count=book.page_count or 0,
                    cover_path=book.cover_path,
                    is_read=0
                ))
            else:
                uncategorized_books.append(BookWithCategory(
                    id=book.id,
                    title=book.title,
                    level="Unknown",
                    file_path=book.file_path,
                    page_count=book.page_count or 0,
                    cover_path=book.cover_path,
                    is_read=0
                ))

        # 对每个分组内的书籍按名称升序排序
        for cat_id in groups:
            groups[cat_id].sort(key=lambda x: x.title.lower())

        # 对未分类书籍按名称升序排序
        uncategorized_books.sort(key=lambda x: x.title.lower())

        # 构建返回结果
        result_groups: list[BookGroup] = []

        # 查找"未分组"分类
        uncategorized_category = None
        other_categories = []
        for cat in categories:
            if cat.name == "未分组":
                uncategorized_category = cat
            else:
                other_categories.append(cat)

        # 先添加其他分类（排除"未分组"）
        for cat in other_categories:
            result_groups.append(BookGroup(
                id=cat.id,
                name=cat.name,
                type=cat.type,
                books=groups[cat.id]
            ))

        # 再添加"未分组"分类（如果有）
        if uncategorized_category:
            result_groups.append(BookGroup(
                id=uncategorized_category.id,
                name=uncategorized_category.name,
                type=uncategorized_category.type,
                books=groups[uncategorized_category.id]
            ))

        # 最后添加"未分类"分组（如果有未分类的书籍）
        if uncategorized_books:
            result_groups.append(BookGroup(
                id=-1,
                name="未分类",
                type="uncategorized",
                books=uncategorized_books
            ))

        return result_groups


category_service = CategoryService()
