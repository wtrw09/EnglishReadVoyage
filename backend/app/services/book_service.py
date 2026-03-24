"""书籍业务逻辑服务层"""
import os
import re
import json
import hashlib
import asyncio
import zipfile
import io
from typing import List, Optional, Dict, Set
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.repositories.book_repository import book_repository
from app.schemas.book import BookInfo, BookDetail, BookImportResponse, BookUpdateResponse, BookPagesResponse, BookRenameResponse
from app.utils.parser import MarkdownParser
from app.services.tts_service import tts_service
from app.services.translation_service import translation_service
from app.core.config import get_settings
from app.models.database_models import UserSettings, TranslationAPI, User
from mutagen.mp3 import MP3


# 任务取消事件管理
# key: book_id, value: asyncio.Event 用于取消任务
active_tasks: Dict[str, asyncio.Event] = {}


def get_cancel_event(book_id: str) -> asyncio.Event:
    """获取或创建书籍的取消事件"""
    if book_id not in active_tasks:
        active_tasks[book_id] = asyncio.Event()
    return active_tasks[book_id]


def clear_cancel_event(book_id: str):
    """清除书籍的取消事件"""
    if book_id in active_tasks:
        del active_tasks[book_id]


def is_cancelled(book_id: str) -> bool:
    """检查书籍任务是否被取消"""
    if book_id in active_tasks:
        return active_tasks[book_id].is_set()
    return False


async def get_effective_translation_api_config(db: AsyncSession, user_id: int) -> tuple[Optional[TranslationAPI], str]:
    """
    获取用户实际可用的翻译API配置
    - 如果用户是管理员，使用用户自己的翻译API
    - 如果用户不是管理员，使用admin用户的翻译API
    返回: (translation_api, error_message)
    """
    # 获取用户信息
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        return None, "用户不存在"

    # 获取用户设置
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    user_settings = result.scalars().first()

    # 如果是管理员，使用自己的翻译API
    if user.role == "admin":
        if not user_settings or not user_settings.selected_translation_api_id:
            return None, "请先配置百度翻译API：设置 → 词典设置"

        result = await db.execute(
            select(TranslationAPI).where(
                TranslationAPI.id == user_settings.selected_translation_api_id,
                TranslationAPI.user_id == user_id,
                TranslationAPI.is_active == True
            )
        )
        api = result.scalars().first()

        if not api:
            return None, "翻译API未启用或不存在"

        return api, None

    # 非管理员：使用admin的翻译API
    result = await db.execute(select(User).where(User.username == "admin"))
    admin_user = result.scalars().first()

    if not admin_user:
        return None, "管理员账户不存在"

    result = await db.execute(select(UserSettings).where(UserSettings.user_id == admin_user.id))
    admin_settings = result.scalars().first()

    if not admin_settings or not admin_settings.selected_translation_api_id:
        return None, "管理员未配置翻译API"

    result = await db.execute(
        select(TranslationAPI).where(
            TranslationAPI.id == admin_settings.selected_translation_api_id,
            TranslationAPI.user_id == admin_user.id,
            TranslationAPI.is_active == True
        )
    )
    api = result.scalars().first()

    if not api:
        return None, "管理员的翻译API未启用"

    return api, None


class BookService:
    """书籍相关业务逻辑服务层"""

    def __init__(self):
        self.repository = book_repository
        self.parser = MarkdownParser()

    async def list_books(self, db: AsyncSession) -> List[BookInfo]:
        """获取所有书籍列表"""
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

    async def delete_book(self, db: AsyncSession, book_id: str) -> bool:
        """删除书籍及其所有资源"""
        book = await self.repository.get(db, book_id)
        if not book:
            return False

        # 删除书籍文件目录（转换为绝对路径）
        abs_file_path = Path(book.file_path)
        book_folder = abs_file_path.parent

        # 删除文件夹及其内容
        if book_folder.exists():
            import shutil
            try:
                shutil.rmtree(book_folder)
            except Exception as e:
                print(f"删除书籍文件夹失败: {e}")

        # 先删除关联数据
        from sqlalchemy import delete
        from app.models.database_models import BookCategoryRel, ReadingProgress

        try:
            # 删除书籍-分类关联
            await db.execute(delete(BookCategoryRel).where(BookCategoryRel.book_id == book_id))
            # 删除阅读进度
            await db.execute(delete(ReadingProgress).where(ReadingProgress.book_id == book_id))
            # 删除书籍
            await db.delete(book)
            await db.commit()
        except Exception as e:
            print(f"删除书籍记录失败: {e}")
            await db.rollback()
            raise e

        return True

    async def update_book_cover(self, db: AsyncSession, book_id: str, cover_path: Optional[str]) -> bool:
        """更新书籍封面"""
        book = await self.repository.get(db, book_id)
        if not book:
            return False

        book.cover_path = cover_path
        await self.repository.update(db, book, {"cover_path": cover_path})
        await db.commit()

        return True

    def _get_book_folder_name(self, file_path: str) -> str:
        """从文件路径中提取书籍文件夹名称
        
        处理不同格式的路径：
        - /app/Books/Animal_Dads/Animal_Dads.md -> Animal_Dads
        - /Books/Animal_Dads/Animal_Dads.md -> Animal_Dads
        - Books/Animal_Dads/Animal_Dads.md -> Animal_Dads
        """
        path = Path(file_path)
        # 从路径中提取书籍文件夹名（假设结构为 .../Books/{book_folder}/{md_file}）
        parts = path.parts
        for i, part in enumerate(parts):
            if part.lower() == "books" and i + 1 < len(parts):
                return parts[i + 1]
        # 如果找不到 Books 目录，返回父目录名
        return path.parent.name

    async def get_book_detail(self, db: AsyncSession, book_id: str) -> Optional[BookDetail]:
        """获取书籍详细信息，包括HTML页面"""
        book = await self.repository.get(db, book_id)
        if not book:
            return None

        # 转换为绝对路径后解析文件
        abs_file_path = Path(book.file_path)
        pages = self.parser.parse_file(str(abs_file_path))

        # 计算书籍相对于Books目录的路径
        book_folder = self._get_book_folder_name(book.file_path)

        return BookDetail(
            id=book.id,
            title=book.title,
            level="Unknown",
            book_path=book_folder,
            pages=pages
        )
    
    async def get_book_pages(
        self,
        db: AsyncSession,
        book_id: str,
        start_page: int = 0,
        end_page: Optional[int] = None
    ) -> Optional[BookPagesResponse]:
        """获取指定范围的页面内容，支持渐进式预加载"""
        book = await self.repository.get(db, book_id)
        if not book:
            return None
    
        # 转换为绝对路径后解析文件
        abs_file_path = Path(book.file_path)
        all_pages = self.parser.parse_file(str(abs_file_path))
        total_pages = len(all_pages)
    
        # 计算实际范围
        start = max(0, start_page)
        end = min(total_pages, end_page if end_page is not None else total_pages)
    
        # 计算书籍相对于Books目录的路径
        book_folder = self._get_book_folder_name(book.file_path)
    
        return BookPagesResponse(
            id=book.id,
            title=book.title,
            book_path=book_folder,
            page_count=total_pages,
            pages=all_pages[start:end],
            start_page=start,
            end_page=end
        )
    
    async def get_book_content(self, db: AsyncSession, book_id: str) -> Optional[str]:
        """获取书籍原始markdown内容"""
        book = await self.repository.get(db, book_id)
        if not book:
            return None

        # 转换为绝对路径后读取文件
        abs_file_path = Path(book.file_path)
        with open(abs_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return content

    async def rename_book(self, db: AsyncSession, book_id: str, new_title: str) -> BookRenameResponse:
        """
        重命名书籍
        步骤：
        1. 检查新名称是否已存在
        2. 生成新的安全文件夹名称
        3. 重命名文件夹（优先使用实际存在的文件夹，而非数据库记录的路径）
        4. 重命名MD文件（如果文件名与文件夹名一致）
        5. 更新数据库中的记录（ID、title、file_path、cover_path）
        """
        import shutil

        book = await self.repository.get(db, book_id)
        if not book:
            return BookRenameResponse(
                success=False,
                message="书籍未找到"
            )

        # 安全化新标题
        safe_new_name = new_title.replace(" ", "_")

        # 检查新名称是否已存在
        from sqlalchemy import select
        from app.models.database_models import Book
        stmt = select(Book).where(Book.title == safe_new_name)
        result = await db.execute(stmt)
        existing_book = result.scalar_one_or_none()

        if existing_book and existing_book.id != book_id:
            return BookRenameResponse(
                success=False,
                message=f"书籍名称 '{new_title}' 已存在"
            )

        # 获取当前书籍路径信息（从数据库，转换为绝对路径）
        abs_file_path = Path(book.file_path)
        db_file_path = abs_file_path
        db_folder = db_file_path.parent
        db_folder_name = db_folder.name
        old_md_filename = db_file_path.name

        # 关键修复：优先查找实际存在的文件夹，而非完全依赖数据库记录
        # 这可以处理数据库路径与实际文件夹不一致的情况
        actual_folder = None
        
        # 首先尝试数据库记录的路径
        if db_folder.exists():
            actual_folder = db_folder
            print(f"使用数据库记录的路径: {db_folder}")
        else:
            # 数据库路径不存在，尝试在 Books 目录下查找匹配的文件夹
            settings = get_settings()
            books_dir = Path(settings.BOOKS_DIR)
            # 策略1：查找与数据库记录同名的文件夹
            candidate = books_dir / db_folder_name
            if candidate.exists():
                actual_folder = candidate
                print(f"数据库路径不存在，找到同名文件夹: {candidate}")
            else:
                # 策略2：查找包含相同MD文件的文件夹
                for folder in books_dir.iterdir():
                    if folder.is_dir():
                        md_file = folder / old_md_filename
                        if md_file.exists():
                            actual_folder = folder
                            print(f"通过MD文件找到实际文件夹: {folder}")
                            break
        
        if not actual_folder:
            return BookRenameResponse(
                success=False,
                message=f"找不到书籍文件夹，数据库记录路径: {db_folder}"
            )

        # 获取实际的文件夹名称
        actual_folder_name = actual_folder.name

        # 构建新路径
        settings = get_settings()
        books_dir = Path(settings.BOOKS_DIR)
        new_folder = books_dir / safe_new_name
        new_file_path = new_folder / f"{safe_new_name}.md"

        # 检查目标文件夹是否已存在（但不同于当前书籍）
        if new_folder.exists() and new_folder != actual_folder:
            return BookRenameResponse(
                success=False,
                message=f"目标文件夹 '{safe_new_name}' 已存在"
            )

        try:
            # 1. 如果文件夹名称改变，重命名文件夹
            if actual_folder != new_folder:
                # 如果目标文件夹已存在（不应该发生，因为上面检查过）
                if new_folder.exists():
                    return BookRenameResponse(
                        success=False,
                        message=f"目标文件夹 '{safe_new_name}' 已存在"
                    )
                # 重命名文件夹
                shutil.move(str(actual_folder), str(new_folder))
                print(f"文件夹已重命名: {actual_folder} -> {new_folder}")

            # 2. 重命名MD文件（如果文件名与旧文件夹名一致）
            # 找到新的MD文件路径
            actual_new_file_path = new_folder / old_md_filename
            if actual_new_file_path.exists() and actual_new_file_path.name != f"{safe_new_name}.md":
                # 如果MD文件名与实际（或数据库记录）的旧文件夹名一致，重命名为新名称
                md_base_name = old_md_filename.replace('.md', '')
                if md_base_name == actual_folder_name or md_base_name == db_folder_name:
                    actual_new_file_path.rename(new_file_path)
                    actual_new_file_path = new_file_path
                    print(f"MD文件已重命名: {old_md_filename} -> {safe_new_name}.md")

            # 3. 计算新的书籍ID（基于新文件路径的MD5）
            new_book_id = hashlib.md5(str(actual_new_file_path).encode()).hexdigest()

            # 检查新ID是否已存在（且不是当前书籍）
            if new_book_id != book_id:
                stmt_check_id = select(Book).where(Book.id == new_book_id)
                result_check = await db.execute(stmt_check_id)
                if result_check.scalar_one_or_none():
                    return BookRenameResponse(
                        success=False,
                        message=f"无法重命名：目标路径对应的书籍已存在"
                    )

            # 4. 更新封面路径（如果存在）
            new_cover_path = None
            if book.cover_path:
                old_cover_path = Path(book.cover_path)
                # 封面路径是相对路径，需要更新其中的文件夹名
                try:
                    # 获取原封面路径中书籍文件夹之后的部分
                    # 例如: /books/Old_Name/assets/cover.jpg -> assets/cover.jpg
                    # 或: /books/Old_Name/cover.jpg -> cover.jpg
                    parts = old_cover_path.parts
                    if 'books' in parts:
                        books_idx = parts.index('books')
                        # 保留书籍文件夹之后的所有路径部分
                        cover_relative_parts = parts[books_idx + 2:]  # 跳过 'books' 和旧文件夹名
                        cover_relative = '/'.join(cover_relative_parts) if cover_relative_parts else old_cover_path.name
                    else:
                        cover_relative = old_cover_path.name
                    new_cover_path = f"/books/{safe_new_name}/{cover_relative}"
                    print(f"封面路径已更新: {book.cover_path} -> {new_cover_path}")
                except Exception as e:
                    print(f"更新封面路径时出错: {e}")
                    new_cover_path = book.cover_path

            # 5. 更新数据库记录
            # 由于ID是主键，需要先删除旧记录，再插入新记录
            # 或者使用UPDATE语句直接更新

            # 先删除旧记录（保留关联数据需要特殊处理）
            from app.models.database_models import BookCategoryRel, ReadingProgress

            # 获取所有关联的分类关系
            stmt_rel = select(BookCategoryRel).where(BookCategoryRel.book_id == book_id)
            result = await db.execute(stmt_rel)
            old_relations = result.scalars().all()

            # 获取所有阅读进度
            stmt_prog = select(ReadingProgress).where(ReadingProgress.book_id == book_id)
            result = await db.execute(stmt_prog)
            old_progresses = result.scalars().all()

            # 删除旧记录
            await db.delete(book)
            await db.flush()  # 确保删除操作执行

            # 创建新记录
            new_book_data = {
                "id": new_book_id,
                "title": safe_new_name,
                "author": book.author,
                "cover_path": new_cover_path,
                "file_path": str(actual_new_file_path),
                "page_count": book.page_count,
                "sync_hash": book.sync_hash
            }
            new_book = Book(**new_book_data)
            db.add(new_book)
            await db.flush()  # 确保新记录创建

            # 恢复分类关联（检查重复避免唯一约束冲突）
            # 先查询新ID已存在的关系
            stmt_existing = select(BookCategoryRel).where(BookCategoryRel.book_id == new_book_id)
            result_existing = await db.execute(stmt_existing)
            existing_rel_keys = {(new_book_id, r.category_id, r.user_id) for r in result_existing.scalars()}
            
            for rel in old_relations:
                rel_key = (new_book_id, rel.category_id, rel.user_id)
                if rel_key not in existing_rel_keys:
                    new_rel = BookCategoryRel(
                        book_id=new_book_id,
                        category_id=rel.category_id,
                        user_id=rel.user_id
                    )
                    db.add(new_rel)
                    existing_rel_keys.add(rel_key)

            # 恢复阅读进度（检查是否已存在）
            stmt_prog_existing = select(ReadingProgress).where(ReadingProgress.book_id == new_book_id)
            result_prog_existing = await db.execute(stmt_prog_existing)
            existing_prog_keys = {(p.user_id, new_book_id) for p in result_prog_existing.scalars()}
            
            for prog in old_progresses:
                prog_key = (prog.user_id, new_book_id)
                if prog_key not in existing_prog_keys:
                    new_prog = ReadingProgress(
                        user_id=prog.user_id,
                        book_id=new_book_id,
                        current_page=prog.current_page,
                        last_read_at=prog.last_read_at,
                        is_completed=prog.is_completed
                    )
                    db.add(new_prog)
                    existing_prog_keys.add(prog_key)

            await db.commit()

            return BookRenameResponse(
                success=True,
                message=f"书籍重命名成功: {book.title} -> {safe_new_name}",
                new_id=new_book_id,
                new_title=safe_new_name,
                new_file_path=str(actual_new_file_path),
                new_cover_path=new_cover_path
            )

        except Exception as e:
            await db.rollback()
            print(f"重命名书籍失败: {e}")
            import traceback
            traceback.print_exc()
            return BookRenameResponse(
                success=False,
                message=f"重命名失败: {str(e)}"
            )

    async def update_book(self, db: AsyncSession, book_id: str, new_content: str) -> BookUpdateResponse:
        """
        更新书籍内容并清理无用的资源文件

        步骤：
        1. 保存新内容到md文件
        2. 提取新内容中引用的图片文件
        3. 删除未被引用的图片文件
        4. 清理不再需要的音频文件
        5. 更新数据库中的页数
        """
        book = await self.repository.get(db, book_id)
        if not book:
            return BookUpdateResponse(
                success=False,
                message="书籍未找到"
            )

        # 转换为绝对路径
        abs_file_path = Path(book.file_path)
        book_path = abs_file_path
        book_folder = book_path.parent

        # 1. 保存新内容
        with open(book_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        # 2. 提取新内容中引用的图片文件
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        matches = re.findall(image_pattern, new_content)
        referenced_files = set()

        for alt_text, url in matches:
            # 只处理本地资源（./assets/开头）
            if url.startswith('./assets/'):
                filename = url.replace('./assets/', '')
                referenced_files.add(filename)
            elif url.startswith('/books/'):
                # 处理绝对路径
                parts = url.split('/assets/')
                if len(parts) > 1:
                    referenced_files.add(parts[1])

        # 3. 获取assets目录下的所有文件，删除无用文件
        assets_folder = book_folder / "assets"
        deleted_files = []

        if assets_folder.exists():
            all_files = set(f.name for f in assets_folder.iterdir() if f.is_file())
            files_to_delete = all_files - referenced_files
            for filename in files_to_delete:
                file_path = assets_folder / filename
                try:
                    file_path.unlink()
                    deleted_files.append(filename)
                except Exception as e:
                    print(f"删除文件失败 {filename}: {e}")

        # 4. 清理不再需要的音频文件
        audio_folder = book_folder / "audio"
        deleted_audio_files = []
        deleted_translation_files = []

        if audio_folder.exists():
            # 提取新内容中的所有句子
            pages = re.split(r'\n---\n', new_content)
            needed_audio_files = set()  # 英文音频
            needed_translation_files = set()  # 中文音频

            for page in pages:
                sentences = self._extract_text_for_tts(page)
                for sentence in sentences:
                    if sentence.strip():
                        text_hash = hashlib.md5(sentence.encode()).hexdigest()
                        needed_audio_files.add(f"{text_hash}.mp3")
                        needed_translation_files.add(f"{text_hash}_zh.mp3")

            # 扫描audio目录，删除不再需要的音频文件
            for audio_file in audio_folder.iterdir():
                if audio_file.is_file() and audio_file.suffix == '.mp3':
                    filename = audio_file.name
                    # 跳过非句子音频文件（如背景音乐等）
                    if filename.startswith('bg_') or filename.startswith('ambient_'):
                        continue
                    # 检查是否需要保留
                    if filename not in needed_audio_files and filename not in needed_translation_files:
                        try:
                            audio_file.unlink()
                            if filename.endswith('_zh.mp3'):
                                deleted_translation_files.append(filename)
                            else:
                                deleted_audio_files.append(filename)
                        except Exception as e:
                            print(f"删除音频文件失败 {filename}: {e}")

            # 更新 sentences.json - 只保留新内容中存在的句子
            mapping_path = audio_folder / 'sentences.json'
            if mapping_path.exists():
                try:
                    with open(mapping_path, 'r', encoding='utf-8') as f:
                        mapping_data = json.load(f)

                    if isinstance(mapping_data, dict):
                        sentences_list = mapping_data.get('sentences', [])
                    else:
                        sentences_list = mapping_data

                    # 过滤出在新内容中存在的句子
                    needed_texts = set()
                    for page in pages:
                        sentences = self._extract_text_for_tts(page)
                        for sentence in sentences:
                            if sentence.strip():
                                needed_texts.add(sentence)

                    filtered_sentences = [
                        s for s in sentences_list
                        if s.get('text') in needed_texts
                    ]

                    # 保存更新后的 sentences.json
                    if isinstance(mapping_data, dict):
                        mapping_data['sentences'] = filtered_sentences
                        with open(mapping_path, 'w', encoding='utf-8') as f:
                            json.dump(mapping_data, f, ensure_ascii=False, indent=2)
                    else:
                        with open(mapping_path, 'w', encoding='utf-8') as f:
                            json.dump(filtered_sentences, f, ensure_ascii=False, indent=2)

                except Exception as e:
                    print(f"更新 sentences.json 失败: {e}")

        # 5. 更新数据库中的页数
        page_count = len(re.split(r'\n---\n', new_content))
        await self.repository.update(db, book, {"page_count": page_count})
        await db.commit()

        # 构建删除文件统计信息
        deleted_count = len(deleted_files)
        deleted_audio_count = len(deleted_audio_files) + len(deleted_translation_files)

        if deleted_count > 0 or deleted_audio_count > 0:
            message_parts = []
            if deleted_count > 0:
                message_parts.append(f"删除了 {deleted_count} 个无用图片")
            if deleted_audio_count > 0:
                message_parts.append(f"清理了 {deleted_audio_count} 个无用音频")
            message = "书籍更新成功，" + "，".join(message_parts)
        else:
            message = "书籍更新成功"

        return BookUpdateResponse(
            success=True,
            message=message,
            deleted_files=deleted_files
        )

    async def import_book(self, db: AsyncSession, file_content: bytes, original_filename: str) -> BookImportResponse:
        """
        导入Markdown书籍文件

        步骤：
        1. 将文件名中的空格替换为下划线
        2. 保存到 Books/[book_name]/[filename].md
        3. 下载网络资源并替换为本地路径
        4. 保存书籍信息到数据库
        """
        # 1. 处理文件名：将空格替换为下划线
        # 获取不带扩展名的文件名
        name_without_ext = Path(original_filename).stem
        # 将空格替换为下划线
        safe_name = name_without_ext.replace(" ", "_")
        # 获取扩展名
        ext = Path(original_filename).suffix

        # 创建书籍文件夹名称
        book_folder_name = safe_name
        book_folder_path = Path("Books") / book_folder_name

        # 创建Books目录（如果不存在）
        Path("Books").mkdir(parents=True, exist_ok=True)

        # 创建书籍文件夹
        book_folder_path.mkdir(parents=True, exist_ok=True)

        # 创建assets文件夹
        assets_folder = book_folder_path / "assets"
        assets_folder.mkdir(parents=True, exist_ok=True)

        # 保存原始md文件内容用于处理
        content = file_content.decode('utf-8')

        # 2. 查找并下载网络资源（图片）
        content, downloaded_files = await self._download_network_resources(content, assets_folder)

        # 3. 保存处理后的md文件
        md_file_path = book_folder_path / f"{book_folder_name}{ext}"
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 4. 计算页数
        page_count = len(re.split(r'\n---\n', content))

        # 5. 生成书籍ID（文件路径的MD5哈希）
        book_id = hashlib.md5(str(md_file_path).encode()).hexdigest()

        # 6. 提取第一张图片作为封面
        cover_path = None
        first_image_match = re.search(r'!\[([^\]]*)\]\((\.\/assets\/[^)]+)\)', content)
        if first_image_match:
            # 使用第一张图片作为封面
            image_relative_path = first_image_match.group(2)  # ./assets/xxx.jpg
            # 提取文件名（包含扩展名）
            filename = image_relative_path.replace('./assets/', '')
            cover_path = f"/books/{book_folder_name}/assets/{filename}"

        # 7. 检查书籍是否已存在
        existing_book = await self.repository.get(db, book_id)
        if existing_book:
            return BookImportResponse(
                success=False,
                message="书籍已存在",
                book_id=book_id,
                title=safe_name
            )

        # 7. 保存到数据库
        book_data = {
            "id": book_id,
            "title": safe_name,
            "file_path": str(md_file_path),
            "page_count": page_count,
            "cover_path": cover_path
        }
        await self.repository.create(db, book_data)
        await db.commit()

        return BookImportResponse(
            success=True,
            message=f"书籍导入成功: {safe_name}",
            book_id=book_id,
            title=safe_name
        )

    async def _download_network_resources(self, content: str, assets_folder: Path) -> tuple[str, Dict[str, str]]:
        """
        下载网络图片并替换链接为本地路径
        返回: (更新后的内容, 下载文件的映射)
        """
        # 查找markdown中所有的图片URL
        # 匹配 ![alt](url) 和 ![alt](url "title")
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        matches = re.findall(image_pattern, content)

        downloaded_files: Dict[str, str] = {}

        # 使用信号量限制并发下载数量
        semaphore = asyncio.Semaphore(5)

        async def download_image(url: str, alt_text: str) -> tuple[str, str]:
            async with semaphore:
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(url)
                        if response.status_code == 200:
                            # 根据URL或content-type确定文件扩展名
                            ext = self._get_extension(url, response.headers.get('content-type', ''))

                            # 使用固定位数数字序号命名（如 image_01.jpg）
                            filename = self._get_sequential_filename(assets_folder, ext)

                            # 保存文件
                            file_path = assets_folder / filename
                            with open(file_path, 'wb') as f:
                                f.write(response.content)

                            # 返回markdown用的相对路径
                            relative_path = f"./assets/{file_path.name}"
                            return url, relative_path
                except Exception as e:
                    print(f"下载失败 {url}: {e}")
                return url, url

        # 并发下载所有图片
        tasks = []
        for alt_text, url in matches:
            # 只下载http/https开头的URL
            if url.startswith('http://') or url.startswith('https://'):
                tasks.append(download_image(url, alt_text))

        if tasks:
            results = await asyncio.gather(*tasks)
            for original_url, local_path in results:
                downloaded_files[original_url] = local_path

        # 替换内容中的URL
        for original_url, local_path in downloaded_files.items():
            # 替换markdown图片语法中的链接
            content = content.replace(f"]({original_url})", f"]({local_path})")

        return content, downloaded_files

    def _get_extension(self, url: str, content_type: str) -> str:
        """根据URL或content-type获取文件扩展名"""
        # 尝试从URL获取
        path = Path(url)
        if path.suffix in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
            return path.suffix

        # 尝试从content-type获取
        content_type_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/svg+xml': '.svg'
        }
        return content_type_map.get(content_type, '.jpg')

    def _sanitize_filename(self, name: str) -> str:
        """通过移除无效字符来清理文件名"""
        # 移除无效字符
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # 将空格替换为下划线
        name = name.replace(' ', '_')
        # 限制长度
        if len(name) > 50:
            name = name[:50]
        return name

    def _get_sequential_filename(self, assets_folder: Path, ext: str, prefix: str = "image") -> str:
        """
        生成固定位数数字序号的文件名（如 image_01.jpg）

        参数:
            assets_folder: 资源文件夹路径
            ext: 文件扩展名
            prefix: 文件名前缀

        返回:
            生成的文件名（如 image_01.jpg）
        """
        # 获取当前已有的文件数量
        existing_files = list(assets_folder.glob(f"{prefix}_*"))
        # 提取已有的序号
        existing_numbers = []
        for f in existing_files:
            stem = f.stem
            if stem.startswith(f"{prefix}_"):
                try:
                    num = int(stem[len(prefix)+1:])
                    existing_numbers.append(num)
                except ValueError:
                    pass

        # 确定下一个序号
        next_number = 1
        if existing_numbers:
            next_number = max(existing_numbers) + 1

        # 生成固定位数（2位）的文件名
        return f"{prefix}_{next_number:02d}{ext}"

    async def import_book_with_progress(
        self,
        db: AsyncSession,
        file_content: bytes,
        original_filename: str,
        progress_callback: Optional[callable] = None,
        generate_audio: bool = True,
        overwrite: bool = False,
        existing_book_id: Optional[str] = None,
        skip_duplicates: bool = False,
        overwrite_book_ids: Optional[list] = None
    ) -> BookImportResponse:
        """
        导入书籍并自动生成语音

        参数:
            db: 数据库会话
            file_content: 文件内容
            original_filename: 原始文件名
            progress_callback: 进度回调函数 (percentage: int, message: str)
            skip_duplicates: 是否跳过已存在的书籍
            overwrite_book_ids: 指定要覆盖的书籍ID列表

        返回:
            BookImportResponse
        """
        async def update_progress(percentage: int, message: str):
            if progress_callback:
                await progress_callback(percentage, message)

        # 根据文件类型处理
        if original_filename.endswith('.zip'):
            return await self._import_zip(db, file_content, original_filename, update_progress, generate_audio, overwrite, existing_book_id, skip_duplicates, overwrite_book_ids)
        elif original_filename.endswith('.md'):
            return await self._import_md(db, file_content, original_filename, update_progress, generate_audio, overwrite, existing_book_id)
        else:
            return BookImportResponse(
                success=False,
                message="不支持的文件格式，请上传 .md 或 .zip 文件",
                book_id="",
                title=""
            )

    async def _import_md(
        self,
        db: AsyncSession,
        file_content: bytes,
        original_filename: str,
        progress_callback: Optional[callable] = None,
        generate_audio: bool = True,
        overwrite: bool = False,
        existing_book_id: Optional[str] = None
    ) -> BookImportResponse:
        """导入单个MD文件并生成语音"""
        await progress_callback(10, "正在保存文件...")

        # 1. 处理文件名
        name_without_ext = Path(original_filename).stem
        safe_name = name_without_ext.replace(" ", "_")
        ext = Path(original_filename).suffix

        book_folder_name = safe_name
        book_folder_path = Path("Books") / book_folder_name

        # 创建目录
        Path("Books").mkdir(parents=True, exist_ok=True)
        book_folder_path.mkdir(parents=True, exist_ok=True)
        assets_folder = book_folder_path / "assets"
        assets_folder.mkdir(parents=True, exist_ok=True)
        audio_folder = book_folder_path / "audio"
        audio_folder.mkdir(parents=True, exist_ok=True)

        await progress_callback(20, "正在解析内容...")

        # 2. 处理内容
        content = file_content.decode('utf-8')
        content, downloaded_files = await self._download_network_resources(content, assets_folder)

        # 3. 保存md文件
        md_file_path = book_folder_path / f"{book_folder_name}{ext}"
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 4. 计算页数并提取语音内容
        pages = re.split(r'\n---\n', content)
        page_count = len(pages)

        # 确定封面路径
        cover_path = None

        # 提取第一张图片作为封面
        first_image_match = re.search(r'!\[([^\]]*)\]\((\.\/assets\/[^)]+)\)', content)
        if first_image_match:
            image_relative_path = first_image_match.group(2)
            filename = image_relative_path.replace('./assets/', '')
            source_image_path = assets_folder / filename

            # 将图片复制到根目录并重命名为 cover.jpg
            if source_image_path.exists():
                import shutil
                cover_file = book_folder_path / "cover.jpg"
                try:
                    shutil.copy2(source_image_path, cover_file)
                    cover_path = f"/books/{book_folder_name}/cover.jpg"
                except Exception as e:
                    print(f"复制封面图片失败: {e}")
                    # 如果复制失败，使用原路径
                    cover_path = f"/books/{book_folder_name}/assets/{filename}"
            else:
                # 源文件不存在，使用原路径
                cover_path = f"/books/{book_folder_name}/assets/{filename}"

        # 提取需要语音的句子（从每个页面提取，返回句子列表）
        sentences_mapping = []  # 保存映射关系
        all_sentences = []  # 所有句子用于批量生成

        for page_idx, page in enumerate(pages):
            page_sentences = self._extract_text_for_tts(page)
            for sent_idx, text in enumerate(page_sentences):
                if text.strip():
                    sentences_mapping.append({
                        'page': page_idx,
                        'index': sent_idx,
                        'text': text
                    })
                    all_sentences.append(text)

        # 5. 根据generate_audio参数决定是否生成语音
        if generate_audio:
            await progress_callback(30, f"共 {len(all_sentences)} 个句子，准备生成语音...")

            # 生成每个句子的语音（使用hash命名）
            # 使用信号量限制并发
            semaphore = asyncio.Semaphore(3)

            # 进度跟踪计数器
            generated_count = [0]
            total_count = len(sentences_mapping)

            async def generate_sentence_audio(sent_info: dict) -> dict:
                """为单个句子生成音频"""
                async with semaphore:
                    text = sent_info['text']
                    # 使用hash作为文件名
                    text_hash = hashlib.md5(text.encode()).hexdigest()
                    audio_filename = f"{text_hash}.mp3"
                    audio_path = audio_folder / audio_filename

                    # 如果已存在，跳过
                    if audio_path.exists():
                        # 已存在的文件也计入进度
                        generated_count[0] += 1
                        current = generated_count[0]
                        progress = 30 + int(current / total_count * 65)
                        await progress_callback(progress, f"正在生成语音 ({current}/{total_count})...")
                        return {**sent_info, 'audio_file': audio_filename}

                    try:
                        # 调用TTS API
                        import httpx
                        settings = get_settings()
                        async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT) as client:
                            payload = {
                                "model": "kokoro",
                                "input": text,
                                "voice": settings.KOKORO_DEFAULT_VOICE,
                                "response_format": "mp3",
                                "speed": 1.0
                            }
                            response = await client.post(settings.KOKORO_API_URL, json=payload)
                            if response.status_code == 200:
                                with open(audio_path, 'wb') as f:
                                    f.write(response.content)
                    except Exception as e:
                        print(f"生成语音失败: {e}")

                    # 更新进度
                    generated_count[0] += 1
                    current = generated_count[0]
                    progress = 30 + int(current / total_count * 65)
                    await progress_callback(progress, f"正在生成语音 ({current}/{total_count})...")

                    return {**sent_info, 'audio_file': audio_filename}

            # 并发生成所有语音
            tasks = [generate_sentence_audio(sent) for sent in sentences_mapping]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 过滤成功的生成结果
            successful_results = [r for r in results if isinstance(r, dict) and r.get('audio_file')]

            # 保存映射文件
            mapping_path = audio_folder / 'sentences.json'
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(successful_results, f, ensure_ascii=False, indent=2)

            await progress_callback(95, f"已生成 {len(successful_results)} 个语音文件")
        else:
            # 不生成音频时，只保存句子映射文件
            await progress_callback(30, "正在保存句子映射...")

            # 保存映射文件（不含audio_file）
            mapping_path = audio_folder / 'sentences.json'
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(sentences_mapping, f, ensure_ascii=False, indent=2)

            await progress_callback(50, "句子映射已保存")

        # 6. 保存到数据库
        # 如果是覆盖导入且提供了existing_book_id，使用它作为book_id
        print(f"DEBUG: overwrite={overwrite}, existing_book_id={existing_book_id}")
        if overwrite and existing_book_id:
            book_id = existing_book_id
            print(f"DEBUG: Using existing_book_id: {book_id}")
        else:
            book_id = hashlib.md5(str(md_file_path).encode()).hexdigest()

        existing_book = await self.repository.get(db, book_id)

        if existing_book and not overwrite:
            return BookImportResponse(
                success=False,
                message="书籍已存在",
                book_id=book_id,
                title=safe_name
            )

        if existing_book and overwrite:
            # 更新现有书籍（使用相对路径存储）
            rel_md_path = str(md_file_path)
            existing_book.page_count = page_count
            existing_book.file_path = rel_md_path
            existing_book.cover_path = cover_path
            await self.repository.update(db, existing_book, {"page_count": page_count, "file_path": rel_md_path, "cover_path": cover_path})

            # 删除旧音频文件夹（确保重新导入时音频与文字匹配）
            abs_old_path = Path(existing_book.file_path)
            old_audio_folder = abs_old_path.parent / "audio"
            if old_audio_folder.exists():
                import shutil
                try:
                    shutil.rmtree(old_audio_folder)
                except Exception as e:
                    print(f"删除旧音频文件夹失败: {e}")
        else:
            book_data = {
                "id": book_id,
                "title": safe_name,
                "file_path": str(md_file_path),
                "page_count": page_count,
                "cover_path": cover_path
            }
            await self.repository.create(db, book_data)

        await db.commit()

        await progress_callback(100, "导入完成")
        print(f"DEBUG: Returning book_id: {book_id}")
        return BookImportResponse(
            success=True,
            message=f"书籍导入成功: {safe_name}",
            book_id=book_id,
            title=safe_name
        )

    async def check_zip_integrity(self, file_content: bytes) -> dict:
        """
        检查ZIP文件的资源完整性
        返回完整性检查结果
        """
        result = {
            "is_valid": True,
            "has_md_file": False,
            "has_assets": False,
            "has_audio": False,
            "has_mapping": False,
            "missing_images": [],
            "message": ""
        }

        try:
            with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                file_list = zf.namelist()

                # 检查是否有MD文件
                md_files = [f for f in file_list if f.endswith('.md')]
                if not md_files:
                    result["is_valid"] = False
                    result["message"] = "ZIP文件中未找到MD文件"
                    return result

                result["has_md_file"] = True

                # 首先尝试查找根目录下的MD文件（单本书导出格式）
                root_md_files = [f for f in md_files if '/' not in f]
                is_multi_book_format = False

                if not root_md_files:
                    # 可能是多书籍打包格式（子文件夹中包含MD文件）
                    # 查找子文件夹中的MD文件，如 BookName/BookName.md
                    for f in md_files:
                        parts = f.split('/')
                        if len(parts) == 2:  # 只有一层子文件夹
                            folder_name = parts[0]
                            file_name = parts[1]
                            if file_name.lower() == f"{folder_name.lower()}.md":
                                root_md_files.append(f)
                                is_multi_book_format = True

                if not root_md_files:
                    # 如果还是没找到，使用所有MD文件
                    root_md_files = md_files

                main_md = root_md_files[0]

                # 检查是否有assets文件夹（支持单本和多本格式）
                if is_multi_book_format:
                    # 多本格式：BookName/assets/xxx
                    book_folder = main_md.split('/')[0]
                    assets_files = [f for f in file_list if f.startswith(f"{book_folder}/assets/")]
                    audio_files = [f for f in file_list if f.startswith(f"{book_folder}/audio/")]
                    mapping_files = [f for f in file_list if f.startswith(f"{book_folder}/audio/") and 'sentences.json' in f]
                else:
                    # 单本格式：assets/xxx
                    assets_files = [f for f in file_list if '/assets/' in f or f.startswith('assets/')]
                    audio_files = [f for f in file_list if '/audio/' in f or f.startswith('audio/')]
                    mapping_files = [f for f in file_list if 'sentences.json' in f]

                result["has_assets"] = len(assets_files) > 0
                result["has_audio"] = len(audio_files) > 0
                result["has_mapping"] = len(mapping_files) > 0

                # 读取MD内容检查图片引用
                try:
                    with zf.open(main_md) as f:
                        content = f.read().decode('utf-8')

                        # 查找所有图片引用
                        img_matches = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', content)

                        for img_path in img_matches:
                            # 只检查本地相对路径
                            if not img_path.startswith(('http://', 'https://', 'data:')):
                                # 在ZIP中查找对应的文件
                                if is_multi_book_format:
                                    book_folder = main_md.split('/')[0]
                                    possible_paths = [
                                        f"{book_folder}/{img_path}",
                                        f"{book_folder}/{img_path.lstrip('./')}",
                                        f"{book_folder}/assets/{img_path.split('/')[-1]}"
                                    ]
                                else:
                                    possible_paths = [
                                        img_path,
                                        img_path.lstrip('./'),
                                        img_path.lstrip('.'),
                                        f"assets/{img_path.split('/')[-1]}"
                                    ]

                                found = False
                                for path in possible_paths:
                                    if path in file_list:
                                        found = True
                                        break
                                    # 检查是否以该路径开头
                                    for zip_path in file_list:
                                        if zip_path.endswith(path) or zip_path.endswith(img_path.split('/')[-1]):
                                            found = True
                                            break
                                    if found:
                                        break

                                if not found:
                                    result["missing_images"].append(img_path)
                except Exception as e:
                    print(f"检查MD内容失败: {e}")

                # 判断完整性
                if result["missing_images"]:
                    result["is_valid"] = False
                    result["message"] = f"缺少 {len(result['missing_images'])} 个图片资源"
                elif not result["has_audio"]:
                    result["is_valid"] = False
                    result["message"] = "缺少音频文件"
                elif not result["has_mapping"]:
                    result["is_valid"] = False
                    result["message"] = "缺少语音映射文件"
                else:
                    result["message"] = "资源完整"

        except zipfile.BadZipFile:
            result["is_valid"] = False
            result["message"] = "无效的ZIP文件"
        except Exception as e:
            result["is_valid"] = False
            result["message"] = f"检查失败: {str(e)}"

        return result

    async def check_zip_duplicates(self, db: AsyncSession, file_content: bytes) -> dict:
        """
        检查ZIP文件中包含的书籍是否已存在
        返回重复书籍清单
        """
        result = {
            "has_duplicates": False,
            "duplicate_books": [],
            "new_books": [],
            "total_books": 0
        }

        try:
            with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                file_list = zf.namelist()

                # 查找所有MD文件
                all_md_files = [f for f in file_list if f.endswith('.md')]

                # 筛选出有效的书籍MD文件
                book_md_files = []
                for f in all_md_files:
                    parts = f.split('/')
                    if len(parts) == 1:  # 根目录下的MD文件（单本格式）
                        book_md_files.append(f)
                    elif len(parts) == 2:  # 子文件夹中的MD文件（多本格式）
                        folder_name = parts[0]
                        file_name = parts[1]
                        if file_name.lower() == f"{folder_name.lower()}.md":
                            book_md_files.append(f)

                result["total_books"] = len(book_md_files)

                # 检查每本书是否已存在
                from sqlalchemy import select
                from app.models.database_models import Book

                for md_file in book_md_files:
                    # 提取书名
                    if '/' in md_file:
                        book_title = Path(md_file).stem
                    else:
                        book_title = Path(md_file).stem

                    safe_name = book_title.replace(" ", "_")

                    # 计算book_id（与导入时相同的逻辑）
                    if '/' in md_file:
                        # 多本格式，需要构建完整路径来计算ID
                        book_folder_name = safe_name
                        md_file_name = f"{book_folder_name}.md"
                        book_folder_path = Path("Books") / book_folder_name
                        md_file_path = book_folder_path / md_file_name
                    else:
                        # 单本格式
                        book_folder_name = safe_name
                        book_folder_path = Path("Books") / book_folder_name
                        md_file_path = book_folder_path / f"{book_folder_name}.md"

                    book_id = hashlib.md5(str(md_file_path).encode()).hexdigest()

                    # 查询数据库
                    stmt = select(Book).where(Book.id == book_id)
                    query_result = await db.execute(stmt)
                    existing_book = query_result.scalar_one_or_none()

                    book_info = {
                        "title": book_title,
                        "safe_name": safe_name,
                        "book_id": book_id,
                        "md_file": md_file
                    }

                    if existing_book:
                        book_info["existing_title"] = existing_book.title
                        result["duplicate_books"].append(book_info)
                    else:
                        result["new_books"].append(book_info)

                result["has_duplicates"] = len(result["duplicate_books"]) > 0

        except zipfile.BadZipFile:
            result["error"] = "无效的ZIP文件"
        except Exception as e:
            result["error"] = f"检查失败: {str(e)}"

        return result

    async def _import_zip(
        self,
        db: AsyncSession,
        file_content: bytes,
        original_filename: str,
        progress_callback: Optional[callable] = None,
        generate_audio: bool = True,
        overwrite: bool = False,
        existing_book_id: Optional[str] = None,
        skip_duplicates: bool = False,
        overwrite_book_ids: Optional[list] = None
    ) -> BookImportResponse:
        """
        导入ZIP压缩包
        支持单本和多本导入
        skip_duplicates: 为True时跳过已存在的书籍
        overwrite_book_ids: 指定要覆盖的书籍ID列表，不在列表中的重复书籍会被跳过
        
        返回:
            BookImportResponse: 导入结果（如果是多本书，message会包含所有书的导入情况）
        """
        await progress_callback(10, "正在解压文件...")

        try:
            with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                # 获取ZIP内的文件列表
                file_list = zf.namelist()

                # 首先尝试查找根目录下的md文件（单本书导出格式）
                root_files = [f for f in file_list if not f.startswith('/') and '/' not in f]
                md_files = [f for f in root_files if f.endswith('.md')]

                # 如果没有找到根目录MD文件，尝试查找子文件夹中的MD文件（多本书导出格式）
                subfolder_md_files = []
                if not md_files:
                    # 查找所有MD文件
                    all_md_files = [f for f in file_list if f.endswith('.md')]
                    # 筛选出直接在子文件夹下的MD文件（如 BookName/BookName.md）
                    for f in all_md_files:
                        parts = f.split('/')
                        if len(parts) == 2:  # 只有一层子文件夹
                            folder_name = parts[0]
                            file_name = parts[1]
                            # 检查文件名是否与文件夹名匹配（不区分大小写）
                            if file_name.lower() == f"{folder_name.lower()}.md":
                                subfolder_md_files.append(f)

                # 如果找到子文件夹格式的MD文件，使用所有检测到的书籍
                if subfolder_md_files:
                    md_files = subfolder_md_files
                    is_subfolder_format = True
                else:
                    is_subfolder_format = False

                if not md_files:
                    return BookImportResponse(
                        success=False,
                        message="ZIP文件中未找到MD文件",
                        book_id="",
                        title=""
                    )

                # 多本书批量导入
                if is_subfolder_format and len(md_files) > 1:
                    return await self._import_multiple_books(
                        db, zf, md_files, file_content, progress_callback, 
                        generate_audio, overwrite, skip_duplicates, overwrite_book_ids
                    )

                # 单本书导入（子文件夹格式但只有一本，或根目录格式）
                # 获取文件夹名称
                if is_subfolder_format:
                    # 从路径中提取，如 "BookName/BookName.md" -> "BookName"
                    main_md = md_files[0]
                    folder_name = main_md.split('/')[0]
                    file_name = main_md.split('/')[1]
                    expected_md = file_name
                    # 子文件夹格式下，MD文件的完整相对路径
                    md_relative_path = main_md
                else:
                    # 根目录格式
                    folder_name = Path(md_files[0]).stem
                    expected_md = md_files[0]
                    md_relative_path = expected_md

                safe_name = folder_name.replace(" ", "_")
                book_folder_name = safe_name

                await progress_callback(30, "正在解析内容...")

                # 创建Books根目录
                Path("Books").mkdir(parents=True, exist_ok=True)

                # 确定解压目标路径
                if is_subfolder_format:
                    # 子文件夹格式：直接解压到Books目录，保持原有结构
                    # 这样 ZIP 中的 BookName/BookName.md 会变成 Books/BookName/BookName.md
                    zf.extractall(Path("Books"))
                    # 构建书籍文件夹路径（解压后）
                    book_folder_path = Path("Books") / safe_name
                else:
                    # 单本格式：创建书籍文件夹并解压到其中
                    book_folder_path = Path("Books") / safe_name
                    book_folder_path.mkdir(parents=True, exist_ok=True)
                    zf.extractall(book_folder_path)

                # 确保assets和audio目录存在
                assets_folder = book_folder_path / "assets"
                assets_folder.mkdir(parents=True, exist_ok=True)
                audio_folder = book_folder_path / "audio"
                audio_folder.mkdir(parents=True, exist_ok=True)

                # 读取md内容
                # 构建MD文件路径
                if is_subfolder_format:
                    # 子文件夹格式：md_relative_path 是 "BookName/BookName.md"
                    # 但文件已经解压到 book_folder_path (Books/BookName/) 下
                    # 所以只需要取文件名部分
                    md_file_path = book_folder_path / expected_md
                else:
                    # 根目录格式：md_relative_path 就是文件名
                    md_file_path = book_folder_path / md_relative_path
                
                # 如果文件不存在，尝试在book_folder_path下查找任何.md文件
                if not md_file_path.exists():
                    md_files_in_folder = list(book_folder_path.glob('*.md'))
                    if md_files_in_folder:
                        md_file_path = md_files_in_folder[0]
                
                with open(md_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 处理网络资源
                content, downloaded_files = await self._download_network_resources(content, assets_folder)

                # 保存处理后的内容
                with open(md_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                # 确定封面路径
                cover_path = None

                # 优先检查是否存在 cover.jpg/cover.png/cover.jpeg
                cover_extensions = ['.jpg', '.jpeg', '.png', '.webp']
                for ext in cover_extensions:
                    cover_file = book_folder_path / f"cover{ext}"
                    if cover_file.exists():
                        cover_path = f"/books/{book_folder_name}/cover{ext}"
                        break

                # 如果没有找到 cover 文件，从MD内容中提取第一张图片
                if not cover_path:
                    first_image_match = re.search(r'!\[([^\]]*)\]\((\.\/assets\/[^)]+)\)', content)
                    if first_image_match:
                        image_relative_path = first_image_match.group(2)
                        filename = image_relative_path.replace('./assets/', '')
                        source_image_path = assets_folder / filename

                        # 将图片复制到根目录并重命名为 cover.jpg
                        if source_image_path.exists():
                            import shutil
                            cover_file = book_folder_path / "cover.jpg"
                            try:
                                shutil.copy2(source_image_path, cover_file)
                                cover_path = f"/books/{book_folder_name}/cover.jpg"
                            except Exception as e:
                                print(f"复制封面图片失败: {e}")
                                # 如果复制失败，使用原路径
                                cover_path = f"/books/{book_folder_name}/assets/{filename}"
                        else:
                            # 源文件不存在，使用原路径
                            cover_path = f"/books/{book_folder_name}/assets/{filename}"

                await progress_callback(50, "正在解析句子...")

                # 解析页面并提取句子
                pages = re.split(r'\n---\n', content)
                page_count = len(pages)

                # 提取需要语音的句子（返回句子列表）
                sentences_mapping = []
                for page_idx, page in enumerate(pages):
                    page_sentences = self._extract_text_for_tts(page)
                    for sent_idx, text in enumerate(page_sentences):
                        if text.strip():
                            sentences_mapping.append({
                                'page': page_idx,
                                'index': sent_idx,
                                'text': text
                            })

                # 根据generate_audio参数决定是否生成语音
                if generate_audio:
                    await progress_callback(60, f"共 {len(sentences_mapping)} 个句子，准备生成语音...")

                    # 生成每个句子的语音（使用hash命名）
                    # 使用信号量限制并发
                    semaphore = asyncio.Semaphore(3)

                    # 进度跟踪计数器
                    generated_count = [0]
                    total_count = len(sentences_mapping)

                    async def generate_sentence_audio(sent_info: dict) -> dict:
                        """为单个句子生成音频"""
                        async with semaphore:
                            text = sent_info['text']
                            # 使用hash作为文件名
                            text_hash = hashlib.md5(text.encode()).hexdigest()
                            audio_filename = f"{text_hash}.mp3"
                            audio_path = audio_folder / audio_filename

                            # 如果已存在，跳过
                            if audio_path.exists():
                                # 已存在的文件也计入进度
                                generated_count[0] += 1
                                current = generated_count[0]
                                progress = 60 + int(current / total_count * 35)
                                await progress_callback(progress, f"正在生成语音 ({current}/{total_count})...")
                                return {**sent_info, 'audio_file': audio_filename}

                            try:
                                # 调用TTS API
                                import httpx
                                settings = get_settings()
                                async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT) as client:
                                    payload = {
                                        "model": "kokoro",
                                        "input": text,
                                        "voice": settings.KOKORO_DEFAULT_VOICE,
                                        "response_format": "mp3",
                                        "speed": 1.0
                                    }
                                    response = await client.post(settings.KOKORO_API_URL, json=payload)
                                    if response.status_code == 200:
                                        with open(audio_path, 'wb') as f:
                                            f.write(response.content)
                            except Exception as e:
                                print(f"生成语音失败: {e}")

                            # 更新进度
                            generated_count[0] += 1
                            current = generated_count[0]
                            progress = 60 + int(current / total_count * 35)
                            await progress_callback(progress, f"正在生成语音 ({current}/{total_count})...")

                            return {**sent_info, 'audio_file': audio_filename}

                    # 并发生成所有语音
                    tasks = [generate_sentence_audio(sent) for sent in sentences_mapping]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 过滤成功的生成结果
                    successful_results = [r for r in results if isinstance(r, dict) and r.get('audio_file')]

                    # 保存映射文件
                    mapping_path = audio_folder / 'sentences.json'
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump(successful_results, f, ensure_ascii=False, indent=2)

                    await progress_callback(95, f"已生成 {len(successful_results)} 个语音文件")
                else:
                    # 不生成音频时，只保存句子映射文件
                    await progress_callback(70, "正在保存句子映射...")

                    # 保存映射文件（不含audio_file）
                    mapping_path = audio_folder / 'sentences.json'
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump(sentences_mapping, f, ensure_ascii=False, indent=2)

                    await progress_callback(80, "句子映射已保存")

                # 保存到数据库
                # 如果是覆盖导入且提供了existing_book_id，使用它作为book_id
                if overwrite and existing_book_id:
                    book_id = existing_book_id
                else:
                    book_id = hashlib.md5(str(md_file_path).encode()).hexdigest()

                # 检查是否已存在
                existing_book = await self.repository.get(db, book_id)
                if existing_book and not overwrite:
                    # 如果指定了overwrite_book_ids，检查当前书籍是否在列表中
                    if overwrite_book_ids is not None:
                        if book_id not in overwrite_book_ids:
                            # 不在覆盖列表中，跳过
                            await progress_callback(100, f"跳过已存在书籍: {safe_name}")
                            return BookImportResponse(
                                success=True,
                                message=f"跳过已存在书籍: {safe_name}",
                                book_id=book_id,
                                title=safe_name
                            )
                        # 在覆盖列表中，继续执行覆盖逻辑
                        overwrite = True
                    elif skip_duplicates:
                        # 如果设置了跳过重复，则跳过此书籍
                        await progress_callback(100, f"跳过已存在书籍: {safe_name}")
                        return BookImportResponse(
                            success=True,
                            message=f"跳过已存在书籍: {safe_name}",
                            book_id=book_id,
                            title=safe_name
                        )
                    else:
                        return BookImportResponse(
                            success=False,
                            message="书籍已存在",
                            book_id=book_id,
                            title=safe_name
                        )

                if existing_book and overwrite:
                    # 更新现有书籍
                    # 先删除整个旧书籍文件夹
                    abs_old_path = Path(existing_book.file_path)
                    old_book_folder = abs_old_path.parent
                    if old_book_folder.exists():
                        import shutil
                        try:
                            shutil.rmtree(old_book_folder)
                            print(f"已删除旧书籍文件夹: {old_book_folder}")
                        except Exception as e:
                            print(f"删除旧书籍文件夹失败: {e}")

                    # 重新创建书籍目录
                    book_folder_path.mkdir(parents=True, exist_ok=True)

                    # 重新解压ZIP文件
                    with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                        if is_subfolder_format:
                            # 子文件夹格式：解压到Books根目录
                            zf.extractall(Path("Books"))
                        else:
                            # 单本格式：解压到书籍目录
                            zf.extractall(book_folder_path)

                    # 重新确定MD文件路径（解压后）
                    if is_subfolder_format:
                        md_file_path = book_folder_path / expected_md
                    else:
                        md_file_path = book_folder_path / md_relative_path

                    # 重新读取和处理MD内容
                    try:
                        # 如果文件不存在，尝试查找任何.md文件
                        if not md_file_path.exists():
                            md_files_in_folder = list(book_folder_path.glob('*.md'))
                            if md_files_in_folder:
                                md_file_path = md_files_in_folder[0]
                        with open(md_file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except FileNotFoundError:
                        # 如果文件不存在，可能是解压后的路径结构不同
                        # 尝试查找解压后的实际MD文件
                        md_files_in_folder = list(book_folder_path.rglob('*.md'))
                        if md_files_in_folder:
                            md_file_path = md_files_in_folder[0]
                            with open(md_file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        else:
                            raise FileNotFoundError(f"找不到MD文件: {md_file_path}")

                    # 更新数据库记录（使用相对路径存储）
                    rel_md_path = str(md_file_path)
                    existing_book.page_count = page_count
                    existing_book.file_path = rel_md_path
                    existing_book.cover_path = cover_path
                    await self.repository.update(db, existing_book, {
                        "page_count": page_count,
                        "file_path": rel_md_path,
                        "cover_path": cover_path
                    })
                else:
                    book_data = {
                        "id": book_id,
                        "title": safe_name,
                        "file_path": str(md_file_path),
                        "page_count": page_count,
                        "cover_path": cover_path
                    }
                    await self.repository.create(db, book_data)

                await db.commit()

                await progress_callback(100, "导入完成")
                return BookImportResponse(
                    success=True,
                    message=f"书籍导入成功: {safe_name}",
                    book_id=book_id,
                    title=safe_name
                )

        except zipfile.BadZipFile:
            return BookImportResponse(
                success=False,
                message="无效的ZIP文件",
                book_id="",
                title=""
            )
        except Exception as e:
            print(f"导入ZIP失败: {e}")
            return BookImportResponse(
                success=False,
                message=f"导入失败: {str(e)}",
                book_id="",
                title=""
            )

    async def _import_multiple_books(
        self,
        db: AsyncSession,
        zf: zipfile.ZipFile,
        md_files: List[str],
        file_content: bytes,
        progress_callback: Optional[callable] = None,
        generate_audio: bool = True,
        overwrite: bool = False,
        skip_duplicates: bool = False,
        overwrite_book_ids: Optional[list] = None
    ) -> BookImportResponse:
        """
        批量导入多本书籍
        
        参数:
            db: 数据库会话
            zf: ZIP文件对象
            md_files: 检测到的所有MD文件列表（格式：BookName/BookName.md）
            file_content: ZIP文件内容（用于重新解压）
            progress_callback: 进度回调
            generate_audio: 是否生成音频
            overwrite: 是否覆盖已存在
            skip_duplicates: 是否跳过重复
            overwrite_book_ids: 指定要覆盖的书籍ID列表
            
        返回:
            BookImportResponse: 汇总导入结果
        """
        total_books = len(md_files)
        success_books = []
        failed_books = []
        skipped_books = []
        success_book_ids = []  # 存储成功导入的书籍ID
        
        await progress_callback(15, f"检测到 {total_books} 本书，开始批量导入...")
        
        # 首先解压所有文件到Books目录
        zf.extractall(Path("Books"))
        
        for idx, md_file in enumerate(md_files):
            # 解析文件夹名和文件名
            folder_name = md_file.split('/')[0]
            file_name = md_file.split('/')[1]
            safe_name = folder_name.replace(" ", "_")
            book_folder_path = Path("Books") / safe_name
            
            progress_base = 20 + int((idx / total_books) * 70)
            await progress_callback(progress_base, f"正在导入 ({idx + 1}/{total_books}): {safe_name}...")
            
            try:
                # 确保assets和audio目录存在
                assets_folder = book_folder_path / "assets"
                assets_folder.mkdir(parents=True, exist_ok=True)
                audio_folder = book_folder_path / "audio"
                audio_folder.mkdir(parents=True, exist_ok=True)
                
                # 读取MD文件
                md_file_path = book_folder_path / file_name
                if not md_file_path.exists():
                    # 尝试查找任何.md文件
                    md_files_in_folder = list(book_folder_path.glob('*.md'))
                    if md_files_in_folder:
                        md_file_path = md_files_in_folder[0]
                    else:
                        failed_books.append((safe_name, "找不到MD文件"))
                        continue
                
                with open(md_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 处理网络资源
                content, downloaded_files = await self._download_network_resources(content, assets_folder)
                
                # 保存处理后的内容
                with open(md_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # 确定封面路径
                cover_path = None
                cover_extensions = ['.jpg', '.jpeg', '.png', '.webp']
                for ext in cover_extensions:
                    cover_file = book_folder_path / f"cover{ext}"
                    if cover_file.exists():
                        cover_path = f"/books/{safe_name}/cover{ext}"
                        break
                
                if not cover_path:
                    first_image_match = re.search(r'!\[([^\]]*)\]\((\.\/assets\/[^)]+)\)', content)
                    if first_image_match:
                        image_relative_path = first_image_match.group(2)
                        filename = image_relative_path.replace('./assets/', '')
                        source_image_path = assets_folder / filename
                        if source_image_path.exists():
                            import shutil
                            cover_file = book_folder_path / "cover.jpg"
                            try:
                                shutil.copy2(source_image_path, cover_file)
                                cover_path = f"/books/{safe_name}/cover.jpg"
                            except Exception:
                                cover_path = f"/books/{safe_name}/assets/{filename}"
                        else:
                            cover_path = f"/books/{safe_name}/assets/{filename}"
                
                # 解析页面
                pages = re.split(r'\n---\n', content)
                page_count = len(pages)
                
                # 提取句子并生成音频
                sentences_mapping = []
                for page_idx, page in enumerate(pages):
                    page_sentences = self._extract_text_for_tts(page)
                    for sent_idx, text in enumerate(page_sentences):
                        if text.strip():
                            sentences_mapping.append({
                                'page': page_idx,
                                'index': sent_idx,
                                'text': text
                            })
                
                if generate_audio:
                    semaphore = asyncio.Semaphore(3)
                    generated_count = [0]
                    total_count = len(sentences_mapping)
                    
                    async def generate_sentence_audio(sent_info: dict) -> dict:
                        async with semaphore:
                            text = sent_info['text']
                            text_hash = hashlib.md5(text.encode()).hexdigest()
                            audio_filename = f"{text_hash}.mp3"
                            audio_path = audio_folder / audio_filename
                            
                            if audio_path.exists():
                                generated_count[0] += 1
                                return {**sent_info, 'audio_file': audio_filename}
                            
                            try:
                                import httpx
                                settings = get_settings()
                                async with httpx.AsyncClient(timeout=settings.TTS_TIMEOUT) as client:
                                    payload = {
                                        "model": "kokoro",
                                        "input": text,
                                        "voice": settings.KOKORO_DEFAULT_VOICE,
                                        "response_format": "mp3",
                                        "speed": 1.0
                                    }
                                    response = await client.post(settings.KOKORO_API_URL, json=payload)
                                    if response.status_code == 200:
                                        with open(audio_path, 'wb') as f:
                                            f.write(response.content)
                            except Exception as e:
                                print(f"生成语音失败: {e}")
                            
                            generated_count[0] += 1
                            return {**sent_info, 'audio_file': audio_filename}
                    
                    tasks = [generate_sentence_audio(sent) for sent in sentences_mapping]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    successful_results = [r for r in results if isinstance(r, dict) and r.get('audio_file')]
                    
                    mapping_path = audio_folder / 'sentences.json'
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump(successful_results, f, ensure_ascii=False, indent=2)
                else:
                    mapping_path = audio_folder / 'sentences.json'
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump(sentences_mapping, f, ensure_ascii=False, indent=2)
                
                # 计算book_id
                book_id = hashlib.md5(str(md_file_path).encode()).hexdigest()
                
                # 检查是否已存在
                existing_book = await self.repository.get(db, book_id)
                
                # 确定是否应该覆盖：
                # - overwrite=True: 覆盖所有已存在的书籍
                # - overwrite_book_ids 不为 None 且包含当前 book_id: 覆盖选中的书籍
                # - overwrite_book_ids 为 None 且 overwrite=False: 不覆盖（根据 skip_duplicates 决定跳过或失败）
                # - overwrite_book_ids 为空列表: 不覆盖任何书籍（根据 skip_duplicates 决定跳过或失败）
                if overwrite_book_ids is not None:
                    # 明确指定了要覆盖的书籍ID列表
                    should_overwrite = book_id in overwrite_book_ids
                else:
                    # 没有指定列表，根据 overwrite 标志决定
                    should_overwrite = overwrite
                
                if existing_book and not should_overwrite:
                    if skip_duplicates:
                        skipped_books.append(safe_name)
                        continue
                    else:
                        failed_books.append((safe_name, "书籍已存在"))
                        continue
                
                if existing_book and should_overwrite:
                    # 更新现有书籍（使用相对路径存储）
                    rel_md_path = str(md_file_path)
                    existing_book.page_count = page_count
                    existing_book.file_path = rel_md_path
                    existing_book.cover_path = cover_path
                    await self.repository.update(db, existing_book, {
                        "page_count": page_count,
                        "file_path": rel_md_path,
                        "cover_path": cover_path
                    })
                else:
                    # 创建新书籍（使用相对路径存储）
                    rel_md_path = str(md_file_path)
                    book_data = {
                        "id": book_id,
                        "title": safe_name,
                        "file_path": rel_md_path,
                        "page_count": page_count,
                        "cover_path": cover_path
                    }
                    await self.repository.create(db, book_data)
                
                await db.commit()
                success_books.append(safe_name)
                success_book_ids.append(book_id)  # 记录成功导入的书籍ID
                
            except Exception as e:
                print(f"导入书籍 {safe_name} 失败: {e}")
                failed_books.append((safe_name, str(e)))
                await db.rollback()
        
        await progress_callback(95, "正在完成导入...")
        
        # 构建汇总消息
        total_processed = len(success_books) + len(failed_books) + len(skipped_books)
        message_parts = []
        if success_books:
            message_parts.append(f"成功导入 {len(success_books)} 本: {', '.join(success_books[:3])}")
            if len(success_books) > 3:
                message_parts[-1] += f" 等"
        if skipped_books:
            message_parts.append(f"跳过 {len(skipped_books)} 本已存在")
        if failed_books:
            message_parts.append(f"失败 {len(failed_books)} 本: {', '.join([f[0] for f in failed_books[:2]])}")
            if len(failed_books) > 2:
                message_parts[-1] += " 等"
        
        await progress_callback(100, "导入完成")
        
        # 只要有成功导入的书籍，就返回success=true，让前端刷新列表
        has_success = len(success_books) > 0
        
        return BookImportResponse(
            success=has_success,
            message="; ".join(message_parts) if message_parts else "无书籍导入",
            book_id="",
            title=f"共 {total_books} 本书",
            book_ids=success_book_ids  # 返回成功导入的书籍ID列表
        )

    def _clean_text_for_tts(self, text: str) -> str:
        """清理文本用于TTS：移除引号和特殊字符"""
        # 移除双引号和单引号
        text = text.replace('"', '').replace("'", "")
        # 移除非英文、非数字、非基本标点的字符（保留字母、数字、空格和基本标点）
        text = re.sub(r'[^\w\s.,!?;:\-]', '', text)
        # 清理多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_text_for_tts(self, content: str) -> List[str]:
        """从页面内容中提取用于TTS的句子列表"""
        # 移除忽略标记
        ignore_pattern = r'<!--\s*ignore\s*-->.*?<!--\s*/ignore\s*-->'
        content = re.sub(ignore_pattern, '', content, flags=re.DOTALL | re.IGNORECASE)

        # 移除图片
        content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', content)

        # 移除HTML标签
        content = re.sub(r'<[^>]+>', '', content)

        # 移除markdown链接
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

        # 移除MD格式字符
        # 移除标题标记 (# ## ### 等)
        content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
        # 移除加粗、斜体等标记
        content = re.sub(r'[*_]+', '', content)

        # 只替换空格和制表符，保留换行符
        content = re.sub(r'[ \t]+', ' ', content).strip()

        # 分句逻辑：先按换行分割（每行是一个独立句子），再按句号分割
        lines = content.split('\n')
        sentences = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 跳过太短的行
            if len(line) < 3:
                continue
            # 按句号分割
            parts = re.split(r'(?<=[.])\s*', line)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                # 清理文本（移除引号和特殊字符）
                cleaned = self._clean_text_for_tts(part)
                # 再次检查长度
                if len(cleaned) < 2:
                    continue
                sentences.append(cleaned)

        return sentences

    async def _check_tts_service(self, service_name: str = "kokoro-tts") -> tuple[bool, str]:
        """检查TTS服务是否可用"""
        # 豆包TTS是在线服务，不需要本地检查
        if service_name == "doubao-tts":
            return True, "豆包TTS服务可用"

        # 检查Kokoro本地TTS服务
        try:
            import httpx
            settings = get_settings()
            async with httpx.AsyncClient(timeout=5.0) as client:
                # 尝试访问TTS服务的健康检查端点或发送一个简单的请求
                response = await client.get(settings.KOKORO_API_URL.replace('/v1/audio/speech', '/health'))
                if response.status_code == 200:
                    return True, "TTS服务正常"
        except Exception as e:
            return False, f"TTS服务不可用: {str(e)}"
        return True, "TTS服务正常"

    async def regenerate_audio(
        self,
        db: AsyncSession,
        book_id: str,
        user_id: int,
        progress_callback: Optional[callable] = None
    ) -> BookImportResponse:
        """
        重新生成书籍音频
        1. 获取书籍信息
        2. 删除现有音频文件夹内容
        3. 重新提取句子并生成音频
        """
        async def update_progress(percentage: int, message: str):
            if progress_callback:
                await progress_callback(percentage, message)

        await update_progress(5, "正在获取用户TTS设置...")

        # 获取用户TTS设置
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        user_settings = result.scalars().first()
        settings = get_settings()

        # 确定使用哪个TTS服务
        service_name = user_settings.tts_service_name if user_settings else "kokoro-tts"
        voice = None
        speed = 1.0
        doubao_app_id = None
        doubao_access_key = None
        doubao_resource_id = None

        if service_name == "kokoro-tts":
            voice = user_settings.kokoro_voice if user_settings else settings.KOKORO_DEFAULT_VOICE
            speed = user_settings.kokoro_speed if user_settings and user_settings.kokoro_speed is not None else 1.0
        else:
            # 豆包TTS
            voice = user_settings.doubao_voice if user_settings else settings.DOUBAO_DEFAULT_VOICE
            speed = user_settings.doubao_speed if user_settings and user_settings.doubao_speed is not None else 1.0
            doubao_app_id = user_settings.doubao_app_id if user_settings else None
            doubao_access_key = user_settings.doubao_access_key if user_settings else None
            doubao_resource_id = user_settings.doubao_resource_id if user_settings else settings.DOUBAO_DEFAULT_RESOURCE_ID

        print(f"书籍音频生成使用TTS服务: {service_name}, voice={voice}, speed={speed}")

        await update_progress(5, "正在检查TTS服务...")

        # 检查TTS服务是否可用
        tts_available, tts_message = await self._check_tts_service(service_name)
        if not tts_available:
            return BookImportResponse(
                success=False,
                message=f"音频生成失败: {tts_message}",
                book_id=book_id,
                title=""
            )

        await update_progress(5, "正在获取书籍信息...")

        # 1. 获取书籍信息
        book = await self.repository.get(db, book_id)
        if not book:
            return BookImportResponse(
                success=False,
                message="书籍未找到",
                book_id=book_id,
                title=""
            )

        # 转换为绝对路径
        abs_file_path = Path(book.file_path)
        book_path = abs_file_path
        book_folder = book_path.parent
        audio_folder = book_folder / "audio"

        await update_progress(10, "正在读取书籍内容...")

        # 2. 读取书籍内容
        with open(book_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 3. 删除现有音频文件夹内容
        if audio_folder.exists():
            for file in audio_folder.iterdir():
                if file.is_file():
                    file.unlink()
        else:
            audio_folder.mkdir(parents=True, exist_ok=True)

        await update_progress(20, "正在解析句子...")

        # 4. 提取需要语音的句子
        pages = re.split(r'\n---\n', content)
        sentences_mapping = []
        all_sentences = []

        for page_idx, page in enumerate(pages):
            page_sentences = self._extract_text_for_tts(page)
            for sent_idx, text in enumerate(page_sentences):
                if text.strip():
                    sentences_mapping.append({
                        'page': page_idx,
                        'index': sent_idx,
                        'text': text
                    })
                    all_sentences.append(text)

        await update_progress(30, f"共 {len(all_sentences)} 个句子，使用 {service_name} 生成语音...")

        # 5. 生成每个句子的语音
        if all_sentences:
            semaphore = asyncio.Semaphore(3)
            generated_count = [0]
            total_count = len(sentences_mapping)

            async def generate_sentence_audio(sent_info: dict) -> dict:
                async with semaphore:
                    text = sent_info['text']
                    # 使用tts_service生成语音
                    try:
                        tts_result = await tts_service.generate_speech(
                            text=text,
                            voice=voice,
                            service_name=service_name,
                            doubao_app_id=doubao_app_id,
                            doubao_access_key=doubao_access_key,
                            doubao_resource_id=doubao_resource_id,
                            speed=speed
                        )

                        # 获取生成的音频数据并保存到书籍音频文件夹
                        text_hash = hashlib.md5(text.encode()).hexdigest()
                        target_filename = f"{text_hash}.mp3"
                        target_path = audio_folder / target_filename

                        if tts_result.audio_data:
                            # 解码base64音频数据并保存
                            import base64
                            audio_bytes = base64.b64decode(tts_result.audio_data)
                            with open(target_path, "wb") as f:
                                f.write(audio_bytes)
                            generated_count[0] += 1
                            current = generated_count[0]
                            progress = 30 + int(current / total_count * 65)
                            await update_progress(progress, f"正在生成语音 ({current}/{total_count})...")
                            return {**sent_info, 'audio_file': target_filename}
                        else:
                            error_msg = "音频数据为空"
                            print(f"生成语音失败: {error_msg}")
                            generated_count[0] += 1
                            current = generated_count[0]
                            progress = 30 + int(current / total_count * 65)
                            await update_progress(progress, f"生成失败 ({current}/{total_count}): {error_msg}")
                            return {**sent_info, 'audio_file': None, 'error': error_msg}
                    except Exception as e:
                        error_msg = str(e)
                        print(f"生成语音失败: {e}")
                        generated_count[0] += 1
                        current = generated_count[0]
                        progress = 30 + int(current / total_count * 65)
                        await update_progress(progress, f"生成失败 ({current}/{total_count}): {error_msg}")
                        return {**sent_info, 'audio_file': None, 'error': error_msg}

            tasks = [generate_sentence_audio(sent) for sent in sentences_mapping]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_results = [r for r in results if isinstance(r, dict) and r.get('audio_file')]

            # 保存映射文件
            mapping_path = audio_folder / 'sentences.json'
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(successful_results, f, ensure_ascii=False, indent=2)

            await update_progress(95, f"已生成 {len(successful_results)} 个语音文件")

        await update_progress(100, "音频生成完成")
        return BookImportResponse(
            success=True,
            message=f"音频重新生成成功",
            book_id=book_id,
            title=book.title
        )

    async def sync_books_from_directory(self, db: AsyncSession) -> dict:
        """
        扫描 Books 目录，同步数据库记录与实际文件夹
        
        功能：
        1. 检查数据库中记录的文件路径是否存在
        2. 扫描 Books 目录下的所有书籍文件夹
        3. 修复路径不匹配的记录
        4. 添加新发现的书籍到数据库
        
        返回:
            dict: 包含修复统计信息
        """
        from app.models.database_models import Book, BookCategoryRel, ReadingProgress
        import shutil
        
        result = {
            "fixed": [],
            "added": [],
            "removed": [],
            "errors": []
        }
        
        # 1. 获取数据库中所有书籍
        stmt = select(Book)
        query_result = await db.execute(stmt)
        db_books = query_result.scalars().all()
        
        # 2. 扫描 Books 目录
        books_dir = Path("Books")
        if not books_dir.exists():
            return {"error": "Books 目录不存在"}
        
        # 获取实际存在的书籍文件夹
        actual_folders = {}
        for folder_name in os.listdir(books_dir):
            folder_path = books_dir / folder_name
            if not folder_path.is_dir():
                continue
            
            # 查找 .md 文件
            md_files = list(folder_path.glob('*.md'))
            if md_files:
                md_file = md_files[0]  # 使用第一个找到的 md 文件
                actual_folders[folder_name] = {
                    "folder_path": folder_path,
                    "md_file": md_file,
                    "md_filename": md_file.name,
                    "md_stem": md_file.stem  # MD文件名（无扩展名）
                }
        
        # 3. 检查并修复数据库记录
        for book in db_books:
            book_path = Path(book.file_path)
            expected_folder_name = book_path.parent.name
            
            # 检查文件夹是否存在
            if expected_folder_name in actual_folders:
                actual_info = actual_folders[expected_folder_name]
                expected_md_path = actual_info["md_file"]
                
                # 检查文件路径是否需要更新
                if str(book.file_path) != str(expected_md_path):
                    # 路径需要更新
                    old_id = book.id
                    new_id = hashlib.md5(str(expected_md_path).encode()).hexdigest()
                    
                    # 保存关联数据
                    stmt_rel = select(BookCategoryRel).where(BookCategoryRel.book_id == old_id)
                    rel_result = await db.execute(stmt_rel)
                    old_relations = rel_result.scalars().all()
                    
                    stmt_prog = select(ReadingProgress).where(ReadingProgress.book_id == old_id)
                    prog_result = await db.execute(stmt_prog)
                    old_progresses = prog_result.scalars().all()
                    
                    # 删除旧记录
                    await db.delete(book)
                    await db.flush()
                    
                    # 创建新记录（使用相对路径存储）
                    rel_md_path = str(expected_md_path)
                    new_book = Book(
                        id=new_id,
                        title=expected_folder_name,
                        author=book.author,
                        cover_path=f"/books/{expected_folder_name}/cover.jpg" if (actual_info["folder_path"] / "cover.jpg").exists() else book.cover_path,
                        file_path=rel_md_path,
                        page_count=book.page_count,
                        sync_hash=book.sync_hash
                    )
                    db.add(new_book)
                    await db.flush()
                    
                    # 恢复关联
                    for rel in old_relations:
                        new_rel = BookCategoryRel(
                            book_id=new_id,
                            category_id=rel.category_id,
                            user_id=rel.user_id
                        )
                        db.add(new_rel)
                    
                    # 恢复阅读进度
                    for prog in old_progresses:
                        new_prog = ReadingProgress(
                            user_id=prog.user_id,
                            book_id=new_id,
                            current_page=prog.current_page,
                            last_read_at=prog.last_read_at,
                            is_completed=prog.is_completed,
                            is_read=prog.is_read
                        )
                        db.add(new_prog)
                    
                    result["fixed"].append({
                        "old_title": book.title,
                        "new_title": expected_folder_name,
                        "old_id": old_id,
                        "new_id": new_id
                    })
                    
                    # 从 actual_folders 中移除，剩下的就是新书籍
                    del actual_folders[expected_folder_name]
                else:
                    # 路径正确，从 actual_folders 中移除
                    del actual_folders[expected_folder_name]
            else:
                # 文件夹名不匹配，尝试通过MD文件名匹配
                db_md_stem = book_path.stem  # 数据库中记录的MD文件名（无扩展名）
                matched_folder = None
                
                for actual_folder_name, info in actual_folders.items():
                    if info["md_stem"] == db_md_stem:
                        # 找到匹配：MD文件名一致，但文件夹名不同
                        matched_folder = actual_folder_name
                        break
                
                if matched_folder:
                    # MD文件名匹配但文件夹名不同，删除数据库记录以便重新导入
                    await db.delete(book)
                    result["removed"].append({
                        "title": book.title,
                        "id": book.id,
                        "reason": f"文件夹名不匹配（数据库：{expected_folder_name}，实际：{matched_folder}），将重新导入"
                    })
                    # 重要：从 actual_folders 中移除，以便后续重新添加
                    del actual_folders[matched_folder]
                else:
                    # 完全找不到匹配，删除记录
                    await db.delete(book)
                    result["removed"].append({
                        "title": book.title,
                        "id": book.id,
                        "reason": "文件夹不存在，已删除数据库记录"
                    })
        
        # 4. 添加新发现的书籍
        for folder_name, info in actual_folders.items():
            try:
                md_file = info["md_file"]
                folder_path = info["folder_path"]
                md_stem = info["md_stem"]  # MD文件名（无扩展名）
                
                # 检查：如果MD文件名与文件夹名不一致，重命名文件夹
                if md_stem != folder_name:
                    new_folder_path = folder_path.parent / md_stem
                    # 检查目标文件夹是否已存在
                    if new_folder_path.exists():
                        result["errors"].append({
                            "title": folder_name,
                            "error": f"无法重命名文件夹：目标文件夹 '{md_stem}' 已存在"
                        })
                        continue
                    
                    # 重命名文件夹
                    folder_path.rename(new_folder_path)
                    print(f"文件夹已重命名: {folder_name} -> {md_stem}")
                    
                    # 更新路径引用
                    folder_path = new_folder_path
                    folder_name = md_stem
                    md_file = new_folder_path / info["md_filename"]
                
                # 计算书籍ID（基于新的文件路径）
                book_id = hashlib.md5(str(md_file).encode()).hexdigest()
                
                # 解析内容获取页数
                pages = self.parser.parse_file(str(md_file))
                page_count = len(pages)
                
                # 检查封面
                cover_path = None
                cover_file = folder_path / "cover.jpg"
                if cover_file.exists():
                    cover_path = f"/books/{folder_name}/cover.jpg"
                
                # 创建新书籍记录（使用相对路径存储）
                rel_md_path = str(md_file)
                new_book = Book(
                    id=book_id,
                    title=folder_name,
                    file_path=rel_md_path,
                    page_count=page_count,
                    cover_path=cover_path
                )
                db.add(new_book)
                
                result["added"].append({
                    "title": folder_name,
                    "id": book_id,
                    "page_count": page_count
                })
            except Exception as e:
                result["errors"].append({
                    "title": folder_name,
                    "error": str(e)
                })
        
        await db.commit()
        return result

    async def supplement_all_books(
        self,
        db: AsyncSession,
        user_id: int,
        progress_callback: Optional[callable] = None,
        force: bool = False
    ) -> dict:
        """
        补充所有书籍的翻译和中文语音
        遍历所有书籍，对缺少翻译或中文音频的句子进行补充
        force=True: 强制重新生成所有内容
        force=False: 只补充缺失部分
        """
        async def update_progress(percentage: int, message: str, book_title: str = None, book_index: int = 0, total_books: int = 0):
            if progress_callback:
                await progress_callback(percentage, message, book_title, book_index, total_books)

        await update_progress(0, "正在获取书籍列表...")

        # 获取所有书籍
        all_books = await self.repository.get_multi(db)

        if not all_books:
            return {
                "success": True,
                "message": "没有找到任何书籍",
                "total_books": 0,
                "processed_books": 0,
                "failed_books": 0,
                "details": []
            }

        total_books = len(all_books)
        result = {
            "success": True,
            "total_books": total_books,
            "processed_books": 0,
            "failed_books": 0,
            "details": []
        }

        await update_progress(5, f"共找到 {total_books} 本书籍，开始处理...")

        # 获取用户设置
        settings = get_settings()
        user_settings = None
        result_settings = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        user_settings = result_settings.scalars().first()

        # 获取翻译API配置
        translation_api = None
        result_api = await db.execute(
            select(TranslationAPI).where(
                TranslationAPI.user_id == user_id,
                TranslationAPI.is_active == True
            ).order_by(TranslationAPI.id.desc())
        )
        translation_api = result_api.scalars().first()

        if not translation_api:
            # 尝试使用admin的配置
            admin_result = await db.execute(select(User).where(User.username == "admin"))
            admin_user = admin_result.scalars().first()
            if admin_user:
                result_api = await db.execute(
                    select(TranslationAPI).where(
                        TranslationAPI.user_id == admin_user.id,
                        TranslationAPI.is_active == True
                    ).order_by(TranslationAPI.id.desc())
                )
                translation_api = result_api.scalars().first()

        if not translation_api:
            await update_progress(100, "错误: 未配置翻译API，请先在设置中配置百度翻译API")
            return {
                "success": False,
                "message": "未配置翻译API，请先在设置中配置百度翻译API",
                "total_books": total_books,
                "processed_books": 0,
                "failed_books": total_books,
                "details": []
            }

        # 获取TTS配置
        service_name = user_settings.tts_service_name if user_settings and user_settings.tts_service_name else "kokoro-tts"
        voice_zh = None
        speed = 1.0
        doubao_app_id = None
        doubao_access_key = None
        doubao_resource_id = None

        if service_name == "kokoro-tts":
            voice_zh = user_settings.kokoro_voice_zh if user_settings and user_settings.kokoro_voice_zh else settings.KOKORO_DEFAULT_VOICE_ZH
            speed = user_settings.kokoro_speed if user_settings and user_settings.kokoro_speed is not None else 1.0
        elif service_name == "doubao-tts":
            voice_zh = user_settings.doubao_voice_zh if user_settings and user_settings.doubao_voice_zh else settings.DOUBAO_DEFAULT_VOICE_ZH
            speed = user_settings.doubao_speed if user_settings and user_settings.doubao_speed is not None else 1.0
            doubao_app_id = user_settings.doubao_app_id if user_settings else None
            doubao_access_key = user_settings.doubao_access_key if user_settings else None
            doubao_resource_id = user_settings.doubao_resource_id if user_settings else settings.DOUBAO_DEFAULT_RESOURCE_ID
        elif service_name == "edge-tts":
            voice_zh = settings.EDGE_TTS_DEFAULT_VOICE_ZH
            speed = user_settings.edge_tts_speed if user_settings and user_settings.edge_tts_speed is not None else 1.0
        else:
            voice_zh = user_settings.siliconflow_voice if user_settings and user_settings.siliconflow_voice else settings.SILICONFLOW_DEFAULT_VOICE

        for idx, book in enumerate(all_books):
            book_index = idx + 1
            book_title = book.title

            # 计算当前书籍在总进度中的占比
            base_percentage = 5
            progress_range = 90
            per_book_progress = progress_range / total_books if total_books > 0 else 0

            await update_progress(
                int(base_percentage + (book_index - 1) * per_book_progress),
                f"[{book_index}/{total_books}] 正在处理: {book_title}",
                book_title,
                book_index,
                total_books
            )

            try:
                # 定义单个书籍的进度回调
                async def book_progress_callback(percentage: int, message: str):
                    book_progress = base_percentage + (book_index - 1) * per_book_progress + (percentage / 100) * per_book_progress
                    await update_progress(
                        int(book_progress),
                        f"[{book_index}/{total_books}] {book_title}: {message}",
                        book_title,
                        book_index,
                        total_books
                    )

                # 处理单本书籍
                book_result = await self._supplement_single_book(
                    db=db,
                    book=book,
                    translation_api=translation_api,
                    service_name=service_name,
                    voice_zh=voice_zh,
                    speed=speed,
                    doubao_app_id=doubao_app_id,
                    doubao_access_key=doubao_access_key,
                    doubao_resource_id=doubao_resource_id,
                    progress_callback=book_progress_callback,
                    force=force
                )

                result["processed_books"] += 1
                result["details"].append({
                    "book_id": book.id,
                    "title": book_title,
                    "status": "success" if book_result["success"] else "failed",
                    "message": book_result["message"]
                })
                print(f"处理完成 [{book_index}/{total_books}]: {book_title} - {book_result['message']}")

            except Exception as e:
                error_msg = str(e)
                result["failed_books"] += 1
                result["details"].append({
                    "book_id": book.id,
                    "title": book_title,
                    "status": "failed",
                    "message": error_msg
                })
                print(f"处理异常 [{book_index}/{total_books}]: {book_title} - {error_msg}")

        # 最终进度
        await update_progress(100, f"处理完成！成功 {result['processed_books']} 本，失败 {result['failed_books']} 本")

        if result["failed_books"] > 0:
            result["success"] = False
            result["message"] = f"处理完成，成功 {result['processed_books']} 本，失败 {result['failed_books']} 本"
        else:
            result["message"] = f"全部 {result['processed_books']} 本书籍处理完成"

        return result

    async def _supplement_single_book(
        self,
        db: AsyncSession,
        book,
        translation_api,
        service_name: str,
        voice_zh: str,
        speed: float,
        doubao_app_id: str,
        doubao_access_key: str,
        doubao_resource_id: str,
        progress_callback: Optional[callable] = None,
        force: bool = False
    ) -> dict:
        """补充单本书籍的翻译和中文音频"""
        async def update_progress_local(percentage: int, message: str):
            if progress_callback:
                await progress_callback(percentage, message)

        await update_progress_local(0, "正在检查现有数据...")

        # 获取书籍路径
        book_path = Path(book.file_path)
        book_folder = book_path.parent
        audio_folder = book_folder / "audio"
        mapping_path = audio_folder / "sentences.json"

        # 确保音频目录存在
        audio_folder.mkdir(parents=True, exist_ok=True)

        # 读取书籍内容
        with open(book_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取句子
        pages = re.split(r'\n---\n', content)
        sentences_mapping = []
        for page_idx, page in enumerate(pages):
            page_sentences = self._extract_text_for_tts(page)
            for sent_idx, text in enumerate(page_sentences):
                if text.strip():
                    sentences_mapping.append({
                        'page': page_idx,
                        'index': sent_idx,
                        'text': text
                    })

        # 读取现有的 sentences.json
        existing_sentences = []
        if mapping_path.exists():
            try:
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        existing_sentences = data.get('sentences', [])
                    else:
                        existing_sentences = data
            except:
                existing_sentences = []

        # 构建现有数据的映射
        existing_map = {}
        for s in existing_sentences:
            existing_map[s.get('text', '')] = s

        await update_progress_local(10, f"共 {len(sentences_mapping)} 个句子，开始补充...")

        # 处理每个句子
        semaphore = asyncio.Semaphore(3)
        updated_count = [0]
        total_count = len(sentences_mapping)

        async def process_sentence(sent_info: dict) -> dict:
            async with semaphore:
                text = sent_info['text']
                text_hash = hashlib.md5(text.encode()).hexdigest()

                # 检查是否需要补充
                existing = existing_map.get(text, {})

                # 确定音频文件名
                audio_file_zh = existing.get('audio_file_zh', f"{text_hash}_zh.mp3")
                translation = existing.get('translation', '')
                audio_file = existing.get('audio_file', f"{text_hash}.mp3")

                # 检查是否需要翻译
                need_translate = force or not translation
                # 检查是否需要生成中文音频
                need_chinese_audio = force or not existing.get('audio_file_zh')

                # 如果都不需要，跳过
                if not need_translate and not need_chinese_audio:
                    updated_count[0] += 1
                    current = updated_count[0]
                    progress = 10 + int((current / total_count) * 85)
                    await update_progress_local(progress, f"跳过已有 ({current}/{total_count})")
                    return {**sent_info, 'translation': translation, 'audio_file_zh': audio_file_zh, 'audio_file': audio_file}

                # 需要翻译
                if need_translate and not translation:
                    try:
                        trans_result = await translation_service.translate_with_baidu(
                            text=text,
                            app_id=translation_api.app_id,
                            app_key=translation_api.app_key
                        )
                        if trans_result:
                            translation = trans_result
                    except Exception as e:
                        print(f"翻译失败: {text[:30]}... - {e}")

                # 需要生成中文音频
                if need_chinese_audio and translation:
                    try:
                        tts_result = await tts_service.generate_speech(
                            text=translation,
                            voice=voice_zh,
                            service_name=service_name,
                            doubao_app_id=doubao_app_id,
                            doubao_access_key=doubao_access_key,
                            doubao_resource_id=doubao_resource_id,
                            speed=speed
                        )

                        if tts_result and tts_result.audio_data:
                            import base64
                            audio_path = audio_folder / audio_file_zh
                            audio_bytes = base64.b64decode(tts_result.audio_data)
                            with open(audio_path, "wb") as f:
                                f.write(audio_bytes)
                            # 获取时长
                            try:
                                audio = MP3(str(audio_path))
                                duration_zh = audio.info.length
                            except:
                                duration_zh = 0.0
                        else:
                            duration_zh = 0.0
                    except Exception as e:
                        print(f"生成中文音频失败: {text[:30]}... - {e}")
                        duration_zh = 0.0

                updated_count[0] += 1
                current = updated_count[0]
                progress = 10 + int((current / total_count) * 85)
                await update_progress_local(progress, f"处理中 ({current}/{total_count})")

                return {
                    **sent_info,
                    'text': text,
                    'translation': translation,
                    'audio_file': audio_file,
                    'audio_file_zh': audio_file_zh,
                    'duration': existing.get('duration', 0.0),
                    'duration_zh': existing.get('duration_zh', 0.0)
                }

        # 并发处理所有句子
        tasks = [process_sentence(sent) for sent in sentences_mapping]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤成功的结果
        successful_results = [r for r in results if isinstance(r, dict)]

        # 保存更新的 sentences.json
        mapping_data = {
            'sentences': successful_results
        }
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, ensure_ascii=False, indent=2)

        await update_progress_local(100, "完成")
        return {
            "success": True,
            "message": f"补充完成，{len(successful_results)} 个句子"
        }


book_service = BookService()
