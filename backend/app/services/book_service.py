"""书籍业务逻辑服务层"""
import os
import re
import json
import hashlib
import asyncio
import zipfile
import io
import logging
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

from collections import OrderedDict

logger = logging.getLogger(__name__)

# Edge-TTS 有效英文语音名称前缀
VALID_EDGE_TTS_EN_PREFIXES = ('en-',)
# Edge-TTS 有效中文语音名称前缀
VALID_EDGE_TTS_ZH_PREFIXES = ('zh-', 'yue-', 'wuu-', 'mn-', 'cmn-')


def validate_edge_tts_voice(voice: Optional[str], default_voice: str) -> str:
    """
    验证 Edge-TTS 语音名称是否有效
    - 英文语音必须以 'en-' 开头
    - 中文语音必须以 'zh-', 'yue-', 'wuu-', 'mn-', 'cmn-' 开头
    - 或者包含 'Neural' 后缀
    如果无效，返回默认语音
    """
    if not voice:
        return default_voice
    
    # 检查是否是有效的语音格式
    voice_upper = voice.upper()
    if ('NEURAL' in voice_upper or  # 包含 Neural 后缀
        voice.startswith(VALID_EDGE_TTS_EN_PREFIXES) or
        any(voice.startswith(prefix) for prefix in VALID_EDGE_TTS_ZH_PREFIXES)):
        return voice
    
    # 无效的语音名称，使用默认值并记录警告
    logger.warning(f"Edge-TTS 语音名称无效: '{voice}'，使用默认值: '{default_voice}'")
    return default_voice


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


class TranslationGenerateResult:
    """翻译生成结果类"""
    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message


class BookService:
    """书籍相关业务逻辑服务层"""

    # LRU缓存配置（类级别共享）
    _parser_cache: OrderedDict[str, List[str]] = OrderedDict()
    _max_cache_size = 50

    def __init__(self):
        self.repository = book_repository
        self.parser = MarkdownParser()

    def _get_parsed_pages(self, book_id: str, file_path: str) -> List[str]:
        """获取解析后的页面，使用LRU缓存"""
        # 检查缓存
        if book_id in self._parser_cache:
            # 移动到末尾（最近使用）
            self._parser_cache.move_to_end(book_id)
            return self._parser_cache[book_id]
        
        # 解析文件
        pages = self.parser.parse_file(file_path)
        
        # 添加到缓存
        self._parser_cache[book_id] = pages
        
        # 如果缓存满了，淘汰最久未使用的
        if len(self._parser_cache) > self._max_cache_size:
            self._parser_cache.popitem(last=False)
        
        return pages

    def _invalidate_cache(self, book_id: str):
        """删除指定书籍的缓存"""
        if book_id in self._parser_cache:
            del self._parser_cache[book_id]

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

        # 删除缓存
        self._invalidate_cache(book_id)

        # 删除书籍文件目录（转换为绝对路径）
        abs_file_path = Path(book.file_path)
        book_folder = abs_file_path.parent

        # 删除文件夹及其内容
        if book_folder.exists():
            import shutil
            try:
                shutil.rmtree(book_folder)
            except Exception as e:
                logger.error(f"删除书籍文件夹失败: {e}")

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
            logger.error(f"删除书籍记录失败: {e}")
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

        # 转换为绝对路径后使用缓存解析文件
        abs_file_path = Path(book.file_path)
        pages = self._get_parsed_pages(book.id, str(abs_file_path))

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
    
        # 转换为绝对路径后使用缓存解析文件
        abs_file_path = Path(book.file_path)
        all_pages = self._get_parsed_pages(book.id, str(abs_file_path))
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

        # 清除缓存（重命名后路径会变，缓存失效）
        self._invalidate_cache(book_id)

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
            logger.debug(f"使用数据库记录的路径: {db_folder}")
        else:
            # 数据库路径不存在，尝试在 Books 目录下查找匹配的文件夹
            settings = get_settings()
            books_dir = Path(settings.BOOKS_DIR)
            # 策略1：查找与数据库记录同名的文件夹
            candidate = books_dir / db_folder_name
            if candidate.exists():
                actual_folder = candidate
                logger.debug(f"数据库路径不存在，找到同名文件夹: {candidate}")
            else:
                # 策略2：查找包含相同MD文件的文件夹
                for folder in books_dir.iterdir():
                    if folder.is_dir():
                        md_file = folder / old_md_filename
                        if md_file.exists():
                            actual_folder = folder
                            logger.debug(f"通过MD文件找到实际文件夹: {folder}")
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
                logger.info(f"文件夹已重命名: {actual_folder} -> {new_folder}")

            # 2. 重命名MD文件（如果文件名与旧文件夹名一致）
            # 找到新的MD文件路径
            actual_new_file_path = new_folder / old_md_filename
            if actual_new_file_path.exists() and actual_new_file_path.name != f"{safe_new_name}.md":
                # 如果MD文件名与实际（或数据库记录）的旧文件夹名一致，重命名为新名称
                md_base_name = old_md_filename.replace('.md', '')
                if md_base_name == actual_folder_name or md_base_name == db_folder_name:
                    actual_new_file_path.rename(new_file_path)
                    actual_new_file_path = new_file_path
                    logger.info(f"MD文件已重命名: {old_md_filename} -> {safe_new_name}.md")

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
                    logger.info(f"封面路径已更新: {book.cover_path} -> {new_cover_path}")
                except Exception as e:
                    logger.error(f"更新封面路径时出错: {e}")
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
            logger.error(f"重命名书籍失败: {e}")
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
                    logger.error(f"删除文件失败 {filename}: {e}")

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
                            logger.error(f"删除音频文件失败 {filename}: {e}")

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
                    logger.error(f"更新 sentences.json 失败: {e}")

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
                    logger.error(f"下载失败 {url}: {e}")
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
                    logger.error(f"复制封面图片失败: {e}")
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
            cancelled = [False]  # 使用列表以便在闭包中修改

            async def generate_sentence_audio(sent_info: dict) -> dict:
                """为单个句子生成音频"""
                async with semaphore:
                    # 检查是否已取消
                    if cancelled[0] or is_cancelled(book_id):
                        cancelled[0] = True
                        return None

                    text = sent_info['text']
                    # 使用hash作为文件名
                    text_hash = hashlib.md5(text.encode()).hexdigest()
                    audio_filename = f"{text_hash}.mp3"
                    audio_path = audio_folder / audio_filename

                    # 如果已存在，跳过
                    if audio_path.exists():
                        # 检查是否已取消
                        if cancelled[0] or is_cancelled(book_id):
                            cancelled[0] = True
                            return None
                        # 获取已有音频的时长
                        try:
                            audio = MP3(str(audio_path))
                            existing_duration = audio.info.length
                        except:
                            existing_duration = 0.0
                        # 已存在的文件也计入进度
                        generated_count[0] += 1
                        current = generated_count[0]
                        progress = 30 + int(current / total_count * 65)
                        await progress_callback(progress, f"正在生成语音 ({current}/{total_count})...")
                        return {**sent_info, 'audio_file': audio_filename, 'duration': existing_duration}

                    try:
                        # 检查是否已取消
                        if cancelled[0] or is_cancelled(book_id):
                            cancelled[0] = True
                            return None
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
                                # 获取音频时长
                                try:
                                    audio = MP3(str(audio_path))
                                    audio_duration = audio.info.length
                                except:
                                    audio_duration = 0.0
                    except Exception as e:
                        logger.error(f"生成语音失败: {e}")

                    # 检查是否已取消
                    if cancelled[0] or is_cancelled(book_id):
                        cancelled[0] = True
                        return None

                    # 获取音频时长（如果前面已生成则已有，否则读取文件）
                    if 'audio_duration' not in dir() or audio_duration == 0.0:
                        try:
                            audio = MP3(str(audio_path))
                            audio_duration = audio.info.length
                        except:
                            audio_duration = 0.0

                    # 更新进度
                    generated_count[0] += 1
                    current = generated_count[0]
                    progress = 30 + int(current / total_count * 65)
                    await progress_callback(progress, f"正在生成语音 ({current}/{total_count})...")

                    return {**sent_info, 'audio_file': audio_filename, 'duration': audio_duration}

            # 并发生成所有语音
            tasks = [generate_sentence_audio(sent) for sent in sentences_mapping]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 检查是否被取消
            if cancelled[0] or is_cancelled(book_id):
                await progress_callback(100, f"生成已取消 (已生成 {generated_count[0]}/{total_count})")
                # 清理取消事件
                clear_cancel_event(book_id)
                return BookImportResponse(
                    success=False,
                    message=f"生成已取消 (已生成 {generated_count[0]}/{total_count})",
                    book_id=book_id,
                    title=safe_name
                )

            # 过滤成功的生成结果
            successful_results = [r for r in results if isinstance(r, dict) and r.get('audio_file')]

            # 保存映射文件
            mapping_path = audio_folder / 'sentences.json'
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump({'sentences': successful_results}, f, ensure_ascii=False, indent=2)

            await progress_callback(95, f"已生成 {len(successful_results)} 个语音文件")
        else:
            # 不生成音频时，只保存句子映射文件
            await progress_callback(30, "正在保存句子映射...")

            # 保存映射文件（不含audio_file）
            mapping_path = audio_folder / 'sentences.json'
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump({'sentences': sentences_mapping}, f, ensure_ascii=False, indent=2)

            await progress_callback(50, "句子映射已保存")

        # 6. 保存到数据库
        # 如果是覆盖导入且提供了existing_book_id，使用它作为book_id
        logger.debug(f"overwrite={overwrite}, existing_book_id={existing_book_id}")
        if overwrite and existing_book_id:
            book_id = existing_book_id
            logger.debug(f"Using existing_book_id: {book_id}")
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
                    logger.error(f"删除旧音频文件夹失败: {e}")
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
        logger.debug(f"Returning book_id: {book_id}")
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
                    logger.error(f"检查MD内容失败: {e}")

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
                                logger.error(f"复制封面图片失败: {e}")
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
                    cancelled = [False]

                    async def generate_sentence_audio(sent_info: dict) -> dict:
                        """为单个句子生成音频"""
                        async with semaphore:
                            # 检查是否已取消
                            if cancelled[0] or is_cancelled(book_id):
                                cancelled[0] = True
                                return None

                            text = sent_info['text']
                            # 使用hash作为文件名
                            text_hash = hashlib.md5(text.encode()).hexdigest()
                            audio_filename = f"{text_hash}.mp3"
                            audio_path = audio_folder / audio_filename

                            # 如果已存在，跳过
                            if audio_path.exists():
                                # 检查是否已取消
                                if cancelled[0] or is_cancelled(book_id):
                                    cancelled[0] = True
                                    return None
                                # 获取已有音频的时长
                                try:
                                    audio = MP3(str(audio_path))
                                    existing_duration = audio.info.length
                                except:
                                    existing_duration = 0.0
                                # 已存在的文件也计入进度
                                generated_count[0] += 1
                                current = generated_count[0]
                                progress = 60 + int(current / total_count * 35)
                                await progress_callback(progress, f"正在生成语音 ({current}/{total_count})...")
                                return {**sent_info, 'audio_file': audio_filename, 'duration': existing_duration}

                            try:
                                # 检查是否已取消
                                if cancelled[0] or is_cancelled(book_id):
                                    cancelled[0] = True
                                    return None
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
                                        # 获取音频时长
                                        try:
                                            audio = MP3(str(audio_path))
                                            audio_duration = audio.info.length
                                        except:
                                            audio_duration = 0.0
                            except Exception as e:
                                logger.error(f"生成语音失败: {e}")

                            # 检查是否已取消
                            if cancelled[0] or is_cancelled(book_id):
                                cancelled[0] = True
                                return None

                            # 获取音频时长（如果前面已生成则已有，否则读取文件）
                            if 'audio_duration' not in dir() or audio_duration == 0.0:
                                try:
                                    audio = MP3(str(audio_path))
                                    audio_duration = audio.info.length
                                except:
                                    audio_duration = 0.0

                            # 更新进度
                            generated_count[0] += 1
                            current = generated_count[0]
                            progress = 60 + int(current / total_count * 35)
                            await progress_callback(progress, f"正在生成语音 ({current}/{total_count})...")

                            return {**sent_info, 'audio_file': audio_filename, 'duration': audio_duration}

                    # 并发生成所有语音
                    tasks = [generate_sentence_audio(sent) for sent in sentences_mapping]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 检查是否被取消
                    if cancelled[0] or is_cancelled(book_id):
                        await progress_callback(100, f"生成已取消 (已生成 {generated_count[0]}/{total_count})")
                        clear_cancel_event(book_id)
                        return BookImportResponse(
                            success=False,
                            message=f"生成已取消 (已生成 {generated_count[0]}/{total_count})",
                            book_id=book_id,
                            title=safe_name
                        )

                    # 过滤成功的生成结果
                    successful_results = [r for r in results if isinstance(r, dict) and r.get('audio_file')]

                    # 保存映射文件
                    mapping_path = audio_folder / 'sentences.json'
                    
                    # 检查 ZIP 中是否已有 sentences.json，如果有则保留并合并
                    existing_mapping = None
                    for zf_file in zf.namelist():
                        if zf_file.endswith('sentences.json'):
                            try:
                                with zf.open(zf_file) as existing_file:
                                    existing_mapping = json.load(existing_file)
                            except:
                                pass
                            break
                    
                    if existing_mapping and existing_mapping.get('sentences'):
                        # 保留原有的 sentences.json（包含翻译和中文音频信息）
                        # 合并新生成的音频信息
                        new_sentences = successful_results
                        existing_sentences = existing_mapping.get('sentences', [])
                        
                        # 构建 text -> existing_sentence 的映射
                        existing_map = {s.get('text'): s for s in existing_sentences}
                        
                        # 合并：使用新生成的音频信息，但保留原有的翻译和中文音频记录
                        merged_sentences = []
                        for new_s in new_sentences:
                            text = new_s.get('text', '')
                            existing_s = existing_map.get(text, {})
                            merged = {
                                'page': new_s.get('page'),
                                'index': new_s.get('index'),
                                'text': text,
                                'audio_file': new_s.get('audio_file'),
                                'duration': new_s.get('duration'),
                            }
                            # 保留原有的翻译和中文音频信息
                            if existing_s.get('translation'):
                                merged['translation'] = existing_s['translation']
                            if existing_s.get('audio_file_zh'):
                                merged['audio_file_zh'] = existing_s['audio_file_zh']
                            if existing_s.get('duration_zh'):
                                merged['duration_zh'] = existing_s['duration_zh']
                            merged_sentences.append(merged)
                        
                        with open(mapping_path, 'w', encoding='utf-8') as f:
                            json.dump({'sentences': merged_sentences}, f, ensure_ascii=False, indent=2)
                    else:
                        # 没有原有的 sentences.json，保存新生成的
                        with open(mapping_path, 'w', encoding='utf-8') as f:
                            json.dump({'sentences': successful_results}, f, ensure_ascii=False, indent=2)

                    await progress_callback(95, f"已生成 {len(successful_results)} 个语音文件")
                else:
                    # 不生成音频时，只保存句子映射文件
                    await progress_callback(70, "正在保存句子映射...")

                    # 保存映射文件（不含audio_file）
                    mapping_path = audio_folder / 'sentences.json'
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump({'sentences': sentences_mapping}, f, ensure_ascii=False, indent=2)

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
                            logger.info(f"已删除旧书籍文件夹: {old_book_folder}")
                        except Exception as e:
                            logger.error(f"删除旧书籍文件夹失败: {e}")

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
            logger.error(f"导入ZIP失败: {e}")
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
                    cancelled = [False]
                    
                    async def generate_sentence_audio(sent_info: dict) -> dict:
                        async with semaphore:
                            # 检查是否已取消
                            if cancelled[0] or is_cancelled(book_id):
                                cancelled[0] = True
                                return None

                            text = sent_info['text']
                            text_hash = hashlib.md5(text.encode()).hexdigest()
                            audio_filename = f"{text_hash}.mp3"
                            audio_path = audio_folder / audio_filename
                            
                            if audio_path.exists():
                                # 检查是否已取消
                                if cancelled[0] or is_cancelled(book_id):
                                    cancelled[0] = True
                                    return None
                                # 获取已有音频的时长
                                try:
                                    audio = MP3(str(audio_path))
                                    existing_duration = audio.info.length
                                except:
                                    existing_duration = 0.0
                                generated_count[0] += 1
                                return {**sent_info, 'audio_file': audio_filename, 'duration': existing_duration}
                            
                            try:
                                # 检查是否已取消
                                if cancelled[0] or is_cancelled(book_id):
                                    cancelled[0] = True
                                    return None
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
                                        # 获取音频时长
                                        try:
                                            audio = MP3(str(audio_path))
                                            audio_duration = audio.info.length
                                        except:
                                            audio_duration = 0.0
                            except Exception as e:
                                logger.error(f"生成语音失败: {e}")
                            
                            # 检查是否已取消
                            if cancelled[0] or is_cancelled(book_id):
                                cancelled[0] = True
                                return None
                            
                            # 获取音频时长（如果前面已生成则已有，否则读取文件）
                            if 'audio_duration' not in dir() or audio_duration == 0.0:
                                try:
                                    audio = MP3(str(audio_path))
                                    audio_duration = audio.info.length
                                except:
                                    audio_duration = 0.0
                            
                            generated_count[0] += 1
                            return {**sent_info, 'audio_file': audio_filename, 'duration': audio_duration}
                    
                    tasks = [generate_sentence_audio(sent) for sent in sentences_mapping]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 检查是否被取消
                    if cancelled[0] or is_cancelled(book_id):
                        await progress_callback(100, f"生成已取消 (已生成 {generated_count[0]}/{total_count})")
                        clear_cancel_event(book_id)
                        return BookImportResponse(
                            success=False,
                            message=f"生成已取消 (已生成 {generated_count[0]}/{total_count})",
                            book_id=book_id,
                            title=safe_name
                        )

                    successful_results = [r for r in results if isinstance(r, dict) and r.get('audio_file')]
                    
                    mapping_path = audio_folder / 'sentences.json'
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump({'sentences': successful_results}, f, ensure_ascii=False, indent=2)
                else:
                    mapping_path = audio_folder / 'sentences.json'
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump({'sentences': sentences_mapping}, f, ensure_ascii=False, indent=2)
                
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
                logger.error(f"导入书籍 {safe_name} 失败: {e}")
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

    def get_sentence_preview(self, content: str) -> List[dict]:
        """
        获取书籍断句预览
        返回包含page、index、text字段的句子列表
        """
        # 按页分割
        pages = re.split(r'\n---\n', content)
        sentences = []

        for page_idx, page in enumerate(pages):
            page_sentences = self._extract_text_for_tts(page)
            for sent_idx, text in enumerate(page_sentences):
                if text.strip():
                    sentences.append({
                        'page': page_idx,
                        'index': sent_idx,
                        'text': text
                    })

        return sentences

    def _extract_text_for_tts(self, content: str) -> List[str]:
        """从页面内容中提取用于TTS的句子列表
            
        注意：此方法必须与 parser.py 的 _wrap_text_content 方法保持一致的断句逻辑，
        以确保 data-tts 属性和 sentences.json 中的文本哈希一致。
        """
        from app.utils.sentence_splitter import split_sentences
            
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
    
        # 分句逻辑：与 parser.py 的 _wrap_text_content 保持一致
        # 先按空行分割段落
        raw_paragraphs = re.split(r'\n\s*\n', content)
            
        # 进一步分割段落，将标题（# 开头）单独分割出来
        paragraphs = []
        for raw_para in raw_paragraphs:
            # 按标题行分割（# 开头的内容）
            title_parts = re.split(r'(?=^#\s)', raw_para, flags=re.MULTILINE)
            for part in title_parts:
                part = part.strip()
                if part:
                    paragraphs.append(part)
    
        sentences = []
        for para_idx, paragraph in enumerate(paragraphs):
            # 清理段落内容
            paragraph = paragraph.strip()
            if not paragraph:
                continue
    
            # 如果段落是纯小写字母的单词短语（如 "cotton shirts"），作为完整句子处理
            if re.match(r'^[a-z]+(?:\s+[a-z]+)*$', paragraph):
                if paragraph.strip():
                    sentences.append(paragraph.strip())
                continue
    
            # 移除段落中的换行，替换为空格（与 parser.py 一致）
            paragraph = re.sub(r'\n+', ' ', paragraph)
    
            # 去除句首的序号（如 "1.", "2.", "①" 等）
            paragraph = re.sub(r'^\d+[\.)]\s*', '', paragraph)
            paragraph = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]+\s*', '', paragraph)
    
            # 使用智能断句（与 parser.py 一致）
            parts = split_sentences(paragraph)
            for part in parts:
                part = part.strip()
                if part and len(part) >= 1:
                    sentences.append(part)
    
        return sentences

    async def _check_tts_service(self, service_name: str = "kokoro-tts") -> tuple[bool, str]:
        """检查TTS服务是否可用"""
        # 豆包TTS是在线服务，不需要本地检查
        if service_name == "doubao-tts":
            return True, "豆包TTS服务可用"

        # MiniMax TTS 是在线服务，不需要本地检查
        if service_name == "minimax-tts":
            return True, "MiniMax TTS服务可用"

        # Siliconflow TTS 是在线服务，不需要本地检查
        if service_name == "siliconflow-tts":
            return True, "Siliconflow TTS服务可用"

        # Edge-TTS 是在线服务，不需要本地检查
        if service_name == "edge-tts":
            return True, "Edge TTS服务可用"

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
        progress_callback: Optional[callable] = None,
        force: bool = False
    ) -> BookImportResponse:
        """
        重新生成书籍音频
        1. 获取书籍信息
        2. 删除现有音频文件夹内容
        3. 重新提取句子并生成音频
        """
        logger.info(f"[DEBUG] regenerate_audio 开始: book_id={book_id}, user_id={user_id}, force={force}")
        
        async def update_progress(percentage: int, message: str):
            if progress_callback:
                await progress_callback(percentage, message)

        await update_progress(5, "正在获取用户TTS设置...")

        # 获取用户TTS设置
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        user_settings = result.scalars().first()
        settings = get_settings()

        # 调试日志
        logger.debug(f"user_settings = {user_settings}")
        if user_settings:
            logger.debug(f"tts_service_name = {user_settings.tts_service_name}")
            logger.debug(f"minimax_api_key = {'已设置' if user_settings.minimax_api_key else '未设置'}")
            logger.debug(f"minimax_model = {user_settings.minimax_model}")
            logger.debug(f"minimax_voice = {user_settings.minimax_voice}")

        # 确定使用哪个TTS服务
        service_name = user_settings.tts_service_name if user_settings else "kokoro-tts"
        voice = None
        speed = 1.0
        doubao_app_id = None
        doubao_access_key = None
        doubao_resource_id = None
        minimax_api_key = None
        minimax_model = None
        siliconflow_api_key = None
        siliconflow_model = None

        if service_name == "kokoro-tts":
            voice = user_settings.kokoro_voice if user_settings else settings.KOKORO_DEFAULT_VOICE
            speed = user_settings.kokoro_speed if user_settings and user_settings.kokoro_speed is not None else 1.0
        elif service_name == "minimax-tts":
            voice = user_settings.minimax_voice if user_settings else settings.MINIMAX_DEFAULT_VOICE
            speed = user_settings.minimax_speed if user_settings and user_settings.minimax_speed is not None else 1.0
            minimax_api_key = user_settings.minimax_api_key if user_settings else None
            minimax_model = user_settings.minimax_model if user_settings else settings.MINIMAX_DEFAULT_MODEL
        elif service_name == "edge-tts":
            # 验证英文语音名称是否有效
            raw_voice = user_settings.edge_tts_voice if user_settings and user_settings.edge_tts_voice else settings.EDGE_TTS_DEFAULT_VOICE
            voice = validate_edge_tts_voice(raw_voice, settings.EDGE_TTS_DEFAULT_VOICE)
            speed = user_settings.edge_tts_speed if user_settings and user_settings.edge_tts_speed is not None else 1.0
        elif service_name == "siliconflow-tts":
            voice = user_settings.siliconflow_voice if user_settings else settings.SILICONFLOW_DEFAULT_VOICE
            siliconflow_api_key = user_settings.siliconflow_api_key if user_settings else None
            siliconflow_model = user_settings.siliconflow_model if user_settings else settings.SILICONFLOW_DEFAULT_MODEL
        else:
            # 豆包TTS
            voice = user_settings.doubao_voice if user_settings else settings.DOUBAO_DEFAULT_VOICE
            speed = user_settings.doubao_speed if user_settings and user_settings.doubao_speed is not None else 1.0
            doubao_app_id = user_settings.doubao_app_id if user_settings else None
            doubao_access_key = user_settings.doubao_access_key if user_settings else None
            doubao_resource_id = user_settings.doubao_resource_id if user_settings else settings.DOUBAO_DEFAULT_RESOURCE_ID

        logger.info(f"书籍音频生成使用TTS服务: {service_name}, voice={voice}, speed={speed}")

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

        # 3. 删除现有音频文件夹内容（仅 force=True 时才删除英文音频，保留中文语音文件）
        deleted_count = 0
        if audio_folder.exists():
            if force:
                # force=True: 删除英文音频文件（保留中文音频和 sentences.json）
                for file in audio_folder.iterdir():
                    if file.is_file():
                        # 跳过中文语音文件
                        if file.suffix == '.mp3' and file.stem.endswith('_zh'):
                            continue
                        # 跳过 sentences.json（稍后会更新）
                        if file.name == 'sentences.json':
                            continue
                        file.unlink()
                        deleted_count += 1
            else:
                # force=False: 统计已有音频，不删除
                for file in audio_folder.iterdir():
                    if file.is_file() and file.suffix == '.mp3' and not file.stem.endswith('_zh'):
                        if file.name != 'sentences.json':
                            deleted_count += 1
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
            cancelled = [False]

            async def generate_sentence_audio(sent_info: dict) -> dict:
                async with semaphore:
                    # 检查是否已取消
                    if cancelled[0] or is_cancelled(book_id):
                        cancelled[0] = True
                        return None

                    text = sent_info['text']
                    text_hash = hashlib.md5(text.encode()).hexdigest()
                    target_filename = f"{text_hash}.mp3"
                    target_path = audio_folder / target_filename

                    # 如果 force=False 且音频文件已存在，跳过
                    if not force and target_path.exists():
                        # 获取已有音频的时长
                        try:
                            audio = MP3(str(target_path))
                            existing_duration = audio.info.length
                        except:
                            existing_duration = 0.0
                        generated_count[0] += 1
                        current = generated_count[0]
                        progress = 30 + int(current / total_count * 65)
                        await update_progress(progress, f"跳过已有音频 ({current}/{total_count})...")
                        return {**sent_info, 'audio_file': target_filename, 'duration': existing_duration}

                    logger.debug(f"generate_sentence_audio: service_name={service_name}, voice={voice}, minimax_api_key={'已设置' if minimax_api_key else '未设置'}, siliconflow_api_key={'已设置' if siliconflow_api_key else '未设置'}")
                    # 使用tts_service生成语音
                    try:
                        # 检查是否已取消
                        if cancelled[0] or is_cancelled(book_id):
                            cancelled[0] = True
                            return None

                            logger.debug(f"调用 tts_service.generate_speech")
                        tts_result = await tts_service.generate_speech(
                            text=text,
                            voice=voice,
                            service_name=service_name,
                            doubao_app_id=doubao_app_id,
                            doubao_access_key=doubao_access_key,
                            doubao_resource_id=doubao_resource_id,
                            minimax_api_key=minimax_api_key,
                            minimax_model=minimax_model,
                            siliconflow_api_key=siliconflow_api_key,
                            siliconflow_model=siliconflow_model,
                            speed=speed
                        )

                        # 检查是否已取消
                        if cancelled[0] or is_cancelled(book_id):
                            cancelled[0] = True
                            return None

                        # 获取生成的音频数据并保存到书籍音频文件夹
                        if tts_result.audio_data:
                            # 解码base64音频数据并保存
                            import base64
                            audio_bytes = base64.b64decode(tts_result.audio_data)
                            with open(target_path, "wb") as f:
                                f.write(audio_bytes)
                            # 获取音频时长
                            try:
                                audio = MP3(str(target_path))
                                audio_duration = audio.info.length
                            except:
                                audio_duration = 0.0
                            generated_count[0] += 1
                            current = generated_count[0]
                            progress = 30 + int(current / total_count * 65)
                            await update_progress(progress, f"正在生成语音 ({current}/{total_count})...")
                            return {**sent_info, 'audio_file': target_filename, 'duration': audio_duration}
                        else:
                            error_msg = "音频数据为空"
                            logger.error(f"生成语音失败: {error_msg}")
                            generated_count[0] += 1
                            current = generated_count[0]
                            progress = 30 + int(current / total_count * 65)
                            await update_progress(progress, f"生成失败 ({current}/{total_count}): {error_msg}")
                            return {**sent_info, 'audio_file': None, 'error': error_msg}
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"生成语音失败: {e}")
                        generated_count[0] += 1
                        current = generated_count[0]
                        progress = 30 + int(current / total_count * 65)
                        await update_progress(progress, f"生成失败 ({current}/{total_count}): {error_msg}")
                        return {**sent_info, 'audio_file': None, 'error': error_msg}

            tasks = [generate_sentence_audio(sent) for sent in sentences_mapping]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 检查是否被取消
            if cancelled[0] or is_cancelled(book_id):
                await update_progress(100, f"生成已取消 (已生成 {generated_count[0]}/{total_count})")
                clear_cancel_event(book_id)
                return BookImportResponse(
                    success=False,
                    message=f"生成已取消 (已生成 {generated_count[0]}/{total_count})",
                    book_id=book_id,
                    title=""
                )

            successful_results = [r for r in results if isinstance(r, dict) and r.get('audio_file')]

            # 读取已有的 sentences.json，保留翻译和中文语音字段
            existing_sentences = {}
            mapping_path = audio_folder / 'sentences.json'
            if mapping_path.exists():
                try:
                    with open(mapping_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if isinstance(existing_data, dict) and 'sentences' in existing_data:
                            # 新格式：{"sentences": [...]}
                            for item in existing_data.get('sentences', []):
                                if item.get('text'):
                                    existing_sentences[item['text']] = item
                        elif isinstance(existing_data, list):
                            # 旧格式：[...]
                            for item in existing_data:
                                if item.get('text'):
                                    existing_sentences[item['text']] = item
                except (json.JSONDecodeError, IOError) as e:
                                logger.warning(f"读取已有的 sentences.json 失败: {e}")

            # 合并：保留已有的 translation、audio_file_zh、duration_zh，同时包含新的 duration
            merged_results = []
            for result in successful_results:
                text = result.get('text', '')
                merged_item = {
                    'page': result.get('page'),
                    'index': result.get('index'),
                    'text': text,
                    'audio_file': result.get('audio_file'),
                    'duration': result.get('duration', 0.0)
                }
                # 保留已有的中文语音和翻译字段
                if text in existing_sentences:
                    existing = existing_sentences[text]
                    if existing.get('translation'):
                        merged_item['translation'] = existing['translation']
                    if existing.get('audio_file_zh'):
                        merged_item['audio_file_zh'] = existing['audio_file_zh']
                    if existing.get('duration_zh'):
                        merged_item['duration_zh'] = existing['duration_zh']
                merged_results.append(merged_item)

            # 保存映射文件（使用新格式：{"sentences": [...]}）
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump({'sentences': merged_results}, f, ensure_ascii=False, indent=2)

            await update_progress(95, f"已生成 {len(successful_results)} 个语音文件")

        await update_progress(100, "音频生成完成")
        logger.info(f"[DEBUG] regenerate_audio 成功完成: book_id={book_id}, title={book.title}")
        return BookImportResponse(
            success=True,
            message=f"音频重新生成成功",
            book_id=book_id,
            title=book.title
        )

    async def regenerate_audio_bilingual(
        self,
        db: AsyncSession,
        book_id: str,
        user_id: int,
        progress_callback: Optional[callable] = None,
        force: bool = False
    ) -> TranslationGenerateResult:
        """
        重新生成书籍中英文音频
        顺序调用:
        1. regenerate_audio - 生成英文语音 (进度 0-50%)
        2. generate_chinese_audio - 生成中文语音 (进度 50-100%)
        """
        logger.info(f"[DEBUG] regenerate_audio_bilingual 开始: book_id={book_id}, user_id={user_id}, force={force}")
        
        # 包装进度回调，分段处理英文和中文
        async def english_progress(percentage: int, message: str):
            if progress_callback:
                # 英文进度映射到 0-50%
                await progress_callback(percentage * 0.5, f"[英文] {message}")

        async def chinese_progress(percentage: int, message: str):
            if progress_callback:
                # 中文进度映射到 50-100%
                await progress_callback(50 + percentage * 0.5, f"[中文] {message}")

        try:
            # 1. 先生成英文语音
            logger.info(f"[DEBUG] 开始生成英文语音")
            if progress_callback:
                await progress_callback(0, "正在生成英文语音...")
            en_result = await self.regenerate_audio(
                db=db,
                book_id=book_id,
                user_id=user_id,
                progress_callback=english_progress,
                force=force
            )
            logger.info(f"[DEBUG] 英文语音生成完成: success={en_result.success}, message={en_result.message}")

            # 如果英文失败，返回失败
            if not en_result.success:
                logger.warning(f"[DEBUG] 英文语音生成失败: {en_result.message}")
                return TranslationGenerateResult(success=False, message=f"英文语音生成失败: {en_result.message}")

            # 2. 再生成中文语音
            logger.info(f"[DEBUG] 开始生成中文语音")
            if progress_callback:
                await progress_callback(50, "正在生成中文语音...")
            zh_result = await self.generate_chinese_audio(
                db=db,
                book_id=book_id,
                user_id=user_id,
                progress_callback=chinese_progress,
                force=force
            )
            logger.info(f"[DEBUG] 中文语音生成完成: success={zh_result.success}, message={zh_result.message}")

            # 返回最终结果
            if zh_result.success:
                # 3. 修复音频时长字段
                if progress_callback:
                    await progress_callback(100, "正在修复音频时长...")
                try:
                    await self.check_and_fix_book_audio(db, book_id)
                except Exception as e:
                    logger.error(f"修复音频时长失败: {e}")
                return TranslationGenerateResult(success=True, message="中英文语音生成完成")
            else:
                return TranslationGenerateResult(success=False, message=f"中文语音生成失败: {zh_result.message}")
                
        except Exception as e:
            logger.error(f"[DEBUG] regenerate_audio_bilingual 异常: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"[DEBUG] regenerate_audio_bilingual 堆栈: {traceback.format_exc()}")
            return TranslationGenerateResult(success=False, message=f"发生错误: {type(e).__name__}: {str(e)}")

    async def sync_books_from_directory(self, db: AsyncSession) -> dict:
        """
        扫描 Books 目录，同步数据库记录与实际文件夹
        
        功能：
        1. 检查数据库中记录的文件路径是否存在
        2. 扫描 Books 目录下的所有书籍文件夹
        3. 修复路径不匹配的记录
        4. 添加新发现的书籍到数据库
        5. 检查并修复所有书籍的音频配置
        
        返回:
            dict: 包含修复统计信息
        """
        from app.models.database_models import Book, BookCategoryRel, ReadingProgress
        import shutil
        
        settings = get_settings()
        
        result = {
            "fixed": [],
            "added": [],
            "removed": [],
            "errors": [],
            "audio_fixed": [],
            "audio_errors": []
        }
        
        # 1. 获取数据库中所有书籍
        stmt = select(Book)
        query_result = await db.execute(stmt)
        db_books = query_result.scalars().all()
        
        # 2. 扫描 Books 目录
        books_dir = Path(settings.BOOKS_DIR)
        if not books_dir.exists():
            return {"error": f"Books 目录不存在: {books_dir}"}
        
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
                    logger.info(f"文件夹已重命名: {folder_name} -> {md_stem}")
                    
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
        
        # 5. 检查并修复所有书籍的音频配置
        # 重新获取所有书籍（因为可能有新增或修改）
        stmt = select(Book)
        query_result = await db.execute(stmt)
        all_books = query_result.scalars().all()
        
        for book in all_books:
            try:
                audio_result = await self._check_and_fix_book_audio_internal(db, book)
                # 合并结果
                if audio_result.get("audio_fixed"):
                    result["audio_fixed"].extend(audio_result["audio_fixed"])
                if audio_result.get("audio_errors"):
                    result["audio_errors"].extend(audio_result["audio_errors"])
            except Exception as e:
                logger.error(f"检查书籍音频失败 {book.title}: {e}")
                result["audio_errors"].append({
                    "book_id": book.id,
                    "title": book.title,
                    "issues": [f"音频检查失败: {str(e)}"]
                })
        
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
        minimax_api_key = None
        minimax_model = None
        siliconflow_api_key = None
        siliconflow_model = None

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
        elif service_name == "minimax-tts":
            # MiniMax 中英文共用一个音色
            voice_zh = user_settings.minimax_voice if user_settings else settings.MINIMAX_DEFAULT_VOICE
            speed = user_settings.minimax_speed if user_settings and user_settings.minimax_speed is not None else 1.0
            minimax_api_key = user_settings.minimax_api_key if user_settings else None
            minimax_model = user_settings.minimax_model if user_settings else settings.MINIMAX_DEFAULT_MODEL
        elif service_name == "siliconflow-tts":
            voice_zh = user_settings.siliconflow_voice if user_settings and user_settings.siliconflow_voice else settings.SILICONFLOW_DEFAULT_VOICE
            siliconflow_api_key = user_settings.siliconflow_api_key if user_settings else None
            siliconflow_model = user_settings.siliconflow_model if user_settings else settings.SILICONFLOW_DEFAULT_MODEL
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
                    minimax_api_key=minimax_api_key,
                    minimax_model=minimax_model,
                    siliconflow_api_key=siliconflow_api_key,
                    siliconflow_model=siliconflow_model,
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
                logger.info(f"处理完成 [{book_index}/{total_books}]: {book_title} - {book_result['message']}")

            except Exception as e:
                error_msg = str(e)
                result["failed_books"] += 1
                result["details"].append({
                    "book_id": book.id,
                    "title": book_title,
                    "status": "failed",
                    "message": error_msg
                })
                logger.warning(f"处理异常 [{book_index}/{total_books}]: {book_title} - {error_msg}")

        # 最终进度
        await update_progress(100, f"处理完成！成功 {result['processed_books']} 本，失败 {result['failed_books']} 本")

        if result["failed_books"] > 0:
            result["success"] = False
            result["message"] = f"处理完成，成功 {result['processed_books']} 本，失败 {result['failed_books']} 本"
        else:
            result["message"] = f"全部 {result['processed_books']} 本书籍处理完成"

        return result

    def _has_valid_zh_audio(self, existing: dict, audio_folder: Path) -> bool:
        """检查中文音频是否有效（既在 sentences.json 中有记录，文件也实际存在）"""
        audio_file_zh = existing.get('audio_file_zh', '')
        if not audio_file_zh:
            return False
        # 同时检查字段存在和文件实际存在
        return (audio_folder / audio_file_zh).exists()

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
        minimax_api_key: str = None,
        minimax_model: str = None,
        siliconflow_api_key: str = None,
        siliconflow_model: str = None,
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
        # edge-tts 需要串行（QPS<=1限制），其他TTS可以并发
        max_concurrent = 1 if service_name == "edge-tts" else 3
        semaphore = asyncio.Semaphore(max_concurrent)
        updated_count = [0]
        total_count = len(sentences_mapping)
        # 统计需要处理的句子数量（用于进度显示）
        # 修复：同时检查 audio_file_zh 字段存在且文件实际存在
        need_process_count = sum(
            1 for s in sentences_mapping
            if force or not self._has_valid_zh_audio(existing_map.get(s['text'], {}), audio_folder)
        )
        generated_count = [0]  # 记录成功生成的数量

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
                # 检查是否需要生成中文音频（同时检查字段和文件是否存在）
                need_chinese_audio = force or not self._has_valid_zh_audio(existing, audio_folder)

                # 如果都不需要，跳过
                if not need_translate and not need_chinese_audio:
                    updated_count[0] += 1
                    current = updated_count[0]
                    progress = 10 + int((current / total_count) * 85)
                    await update_progress_local(progress, f"跳过已有 ({current}/{total_count})")
                    return {**sent_info, 'translation': translation, 'audio_file_zh': audio_file_zh, 'audio_file': audio_file}

                # 更新处理进度（统一使用 total_count 作为分母，避免进度超过100%）
                updated_count[0] += 1
                current = updated_count[0]
                progress = 10 + int((current / total_count) * 85)
                await update_progress_local(progress, f"处理中 ({current}/{total_count})")

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
                                    logger.error(f"翻译失败: {text[:30]}... - {e}")

                # 需要生成中文音频
                audio_generated = False  # 标记是否成功生成音频
                duration_zh = 0.0
                if need_chinese_audio and translation:
                    try:
                        tts_result = await tts_service.generate_speech(
                            text=translation,
                            voice=voice_zh,
                            service_name=service_name,
                            doubao_app_id=doubao_app_id,
                            doubao_access_key=doubao_access_key,
                            doubao_resource_id=doubao_resource_id,
                            minimax_api_key=minimax_api_key,
                            minimax_model=minimax_model,
                            siliconflow_api_key=siliconflow_api_key,
                            siliconflow_model=siliconflow_model,
                            speed=speed
                        )

                        if tts_result and tts_result.audio_data:
                            import base64
                            audio_path = audio_folder / audio_file_zh
                            audio_bytes = base64.b64decode(tts_result.audio_data)
                            with open(audio_path, "wb") as f:
                                f.write(audio_bytes)
                            audio_generated = True  # 标记成功生成
                            generated_count[0] += 1
                            # TTS调用成功后立即发送进度更新，让前端看到进度数字变化
                            # 修复：使用 total_count 作为分母，避免进度超过100%（与第3403行注释一致）
                            current = updated_count[0]
                            progress = 10 + int((current / total_count) * 85)
                            await update_progress_local(progress, f"生成中 ({current}/{total_count})")
                            # 获取时长
                            try:
                                audio = MP3(str(audio_path))
                                duration_zh = audio.info.length
                            except:
                                duration_zh = 0.0
                    except Exception as e:
                                    logger.error(f"生成中文音频失败: {text[:30]}... - {e}")

                # 构建返回结果，只有成功生成时才包含 audio_file_zh
                result = {
                    **sent_info,
                    'text': text,
                    'translation': translation,
                    'audio_file': audio_file,
                    'duration': existing.get('duration', 0.0),
                }
                # 只有成功生成中文音频或已有音频文件时才包含 audio_file_zh
                if audio_generated or (existing.get('audio_file_zh') and (audio_folder / existing['audio_file_zh']).exists()):
                    result['audio_file_zh'] = audio_file_zh if audio_generated else existing['audio_file_zh']
                    result['duration_zh'] = duration_zh if audio_generated else existing.get('duration_zh', 0.0)
                return result

        # 并发处理所有句子
        tasks = [process_sentence(sent) for sent in sentences_mapping]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤成功的结果
        successful_results = [r for r in results if isinstance(r, dict)]

        # 检查有多少句子有中文音频
        sentences_with_zh_audio = sum(1 for r in successful_results if r.get('audio_file_zh'))
        sentences_without_zh_audio = len(successful_results) - sentences_with_zh_audio

        # 保存更新的 sentences.json
        mapping_data = {
            'sentences': successful_results
        }
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, ensure_ascii=False, indent=2)

        await update_progress_local(100, "完成")
        
        # 如果所有句子都有中文音频才返回成功
        if sentences_without_zh_audio == 0:
            return {
                "success": True,
                "message": f"补充完成，{len(successful_results)} 个句子全部生成中文音频"
            }
        else:
            return {
                "success": False,
                "message": f"补充完成，{sentences_with_zh_audio}/{len(successful_results)} 个句子有中文音频，{sentences_without_zh_audio} 个失败"
            }

    async def _check_and_fix_book_audio_internal(self, db: AsyncSession, book) -> dict:
        """
        检查并修复单本书籍的音频配置（内部方法，接收 Book 对象）

        检查内容：
        - sentences.json 文件格式
        - 缺失的字段自动修复（duration、duration_zh）
        - 音频文件完整性检查

        返回:
            dict: 包含检查和修复结果，格式兼容前端 AudioFixDialog
        """
        # 转换为绝对路径
        abs_file_path = Path(book.file_path)
        book_path = abs_file_path
        book_folder = book_path.parent
        audio_folder = book_folder / "audio"
        mapping_path = audio_folder / "sentences.json"

        # 兼容前端 AudioFixDialog 的返回格式
        audio_fixed = []
        audio_errors = []

        # 检查 sentences.json 是否存在
        if not mapping_path.exists():
            # sentences.json 不存在不算错误，可能是新书籍还没生成音频
            return {"audio_fixed": audio_fixed, "audio_errors": audio_errors}

        # 读取并检查 sentences.json
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                sentences_data = json.load(f)
        except json.JSONDecodeError as e:
            audio_errors.append({
                "book_id": book.id,
                "title": book.title,
                "issues": [f"sentences.json 格式错误: {e}"]
            })
            return {"audio_fixed": audio_fixed, "audio_errors": audio_errors}

        # 兼容旧格式：如果直接是数组
        if isinstance(sentences_data, list):
            sentences_data = {'sentences': sentences_data}

        sentences = sentences_data.get('sentences', [])
        if not isinstance(sentences, list):
            audio_errors.append({
                "book_id": book.id,
                "title": book.title,
                "issues": [f"sentences.json 格式错误: 期望数组，实际为 {type(sentences).__name__}"]
            })
            return {"audio_fixed": audio_fixed, "audio_errors": audio_errors}

        total_sentences = len(sentences)

        # 统计修复信息
        fixed_fields = []
        warnings = []
        issues = []

        # 扫描 audio 目录，获取所有 mp3 文件名集合（用于 MD5 哈希匹配）
        existing_mp3_files = set()
        # 同时扫描中文音频文件（以 _zh.mp3 结尾）
        existing_zh_mp3_files = set()
        if audio_folder.exists():
            for f_path in audio_folder.iterdir():
                if f_path.suffix.lower() == ".mp3":
                    existing_mp3_files.add(f_path.name)
                    if f_path.stem.endswith('_zh'):
                        existing_zh_mp3_files.add(f_path.name)
        logger.info(f"📖 扫描 audio 目录: {audio_folder}, 找到 {len(existing_mp3_files)} 个mp3文件, {len(existing_zh_mp3_files)} 个中文音频文件")
        
        # 检查每个句子的音频
        duration_fixed_count = 0
        duration_zh_fixed_count = 0
        audio_file_fixed_count = 0
        audio_zh_fixed_count = 0
        missing_audio_count = 0
        missing_zh_audio_count = 0
        missing_translation_count = 0

        for i, item in enumerate(sentences):
            # 确保每个item是字典
            if not isinstance(item, dict):
                issues.append(f"第 {i+1} 条数据格式错误（非字典）")
                continue

            sentence = item.get("text", "")
            audio_file = item.get("audio_file")

            # 检查必要字段
            if not sentence:
                issues.append(f"第 {i+1} 条缺少 text 字段")
                continue

            # 如果缺少 audio_file 字段，尝试通过 MD5 哈希匹配已有音频文件
            if not audio_file:
                expected_filename = hashlib.md5(sentence.encode('utf-8')).hexdigest() + ".mp3"
                # 调试：打印前3个匹配结果
                if i < 3:
                    logger.info(f"🔍 句子[{i}] MD5匹配: text[:30]={sentence[:30]}..., expected={expected_filename}, found={expected_filename in existing_mp3_files}")
                if expected_filename in existing_mp3_files:
                    item["audio_file"] = expected_filename
                    audio_file = expected_filename
                    audio_file_fixed_count += 1
                else:
                    missing_audio_count += 1
                    continue

            # 检查音频文件是否存在
            audio_path = audio_folder / audio_file
            if not audio_path.exists():
                missing_audio_count += 1
                continue

            # 检查并补充英文音频时长
            duration_fixed_for_item = False
            if "duration" not in item or item["duration"] is None or item["duration"] == 0.0:
                try:
                    audio = MP3(str(audio_path))
                    item["duration"] = round(audio.info.length, 3)
                    duration_fixed_for_item = True
                    duration_fixed_count += 1
                except:
                    item["duration"] = 0.0

            # 检查中文音频文件：如果缺少 audio_file_zh 但文件存在，则补充
            audio_file_zh = item.get("audio_file_zh")
            text_hash = hashlib.md5(sentence.encode('utf-8')).hexdigest()
            expected_zh_filename = f"{text_hash}_zh.mp3"
            if not audio_file_zh and expected_zh_filename in existing_zh_mp3_files:
                # 文件存在但没有记录，补充记录
                item["audio_file_zh"] = expected_zh_filename
                audio_file_zh = expected_zh_filename
                audio_zh_fixed_count += 1
                logger.info(f"✅ 补充中文音频记录: {sentence[:30]}... -> {expected_zh_filename}")

            # 检查并补充中文音频时长
            duration_zh_fixed_for_item = False
            if audio_file_zh:
                audio_zh_path = audio_folder / audio_file_zh
                if not audio_zh_path.exists():
                    # 文件不存在，尝试重新匹配
                    if expected_zh_filename in existing_zh_mp3_files:
                        item["audio_file_zh"] = expected_zh_filename
                        audio_file_zh = expected_zh_filename
                        audio_zh_path = audio_folder / audio_file_zh
                        audio_zh_fixed_count += 1
                        logger.info(f"✅ 修正中文音频路径: {sentence[:30]}... -> {expected_zh_filename}")

                if audio_zh_path.exists():
                    if "duration_zh" not in item or item["duration_zh"] is None or item["duration_zh"] == 0.0:
                        try:
                            audio_zh = MP3(str(audio_zh_path))
                            item["duration_zh"] = round(audio_zh.info.length, 3)
                            duration_zh_fixed_for_item = True
                            duration_zh_fixed_count += 1
                        except Exception as e:
                            item["duration_zh"] = 0.0
                            logger.warning(f"⚠️ 读取中文音频时长失败: {audio_zh_path} - {e}")
                else:
                    # 记录了但文件不存在
                    missing_zh_audio_count += 1

            # 检查翻译是否缺失
            if not item.get("translation"):
                missing_translation_count += 1

            # 补充 page 和 index 字段
            if "page" not in item:
                item["page"] = 0
            if "index" not in item:
                item["index"] = i

        # 构建修复信息
        logger.info(f"📊 修复统计: audio_file补全={audio_file_fixed_count}, audio_zh补全={audio_zh_fixed_count}, duration补全={duration_fixed_count}, duration_zh补全={duration_zh_fixed_count}, missing英文={missing_audio_count}, missing中文={missing_zh_audio_count}, missing翻译={missing_translation_count}")
        if audio_file_fixed_count > 0:
            fixed_fields.append(f"已通过MD5哈希匹配补全 {audio_file_fixed_count} 个英文音频文件(audio_file)")
        if audio_zh_fixed_count > 0:
            fixed_fields.append(f"已补全 {audio_zh_fixed_count} 个中文音频记录(audio_file_zh)")
        if duration_fixed_count > 0:
            fixed_fields.append(f"已补全 {duration_fixed_count} 个英文音频时长(duration)")
        if duration_zh_fixed_count > 0:
            fixed_fields.append(f"已补全 {duration_zh_fixed_count} 个中文音频时长(duration_zh)")

        if missing_audio_count > 0:
            warnings.append(f"⚠️ 警告: {missing_audio_count} 个句子缺少英文音频文件")
        if missing_zh_audio_count > 0:
            warnings.append(f"⚠️ 警告: {missing_zh_audio_count} 个句子有中文音频记录但文件不存在")
        if missing_translation_count > 0:
            warnings.append(f"⚠️ 提示: {missing_translation_count} 个句子缺少翻译(可使用「补充翻译」功能)")

        # 计算中文语音覆盖率
        total_with_zh = sum(1 for s in sentences if s.get("audio_file_zh") and (audio_folder / s["audio_file_zh"]).exists())
        zh_coverage = f"{total_with_zh}/{total_sentences}" if total_sentences > 0 else "0/0"
        if total_with_zh == 0 and total_sentences > 0:
            warnings.append(f"⚠️ 提示: 该书籍暂无中文语音，可使用「补充翻译+中文语音」功能生成")
        elif total_with_zh < total_sentences:
            warnings.append(f"📊 中文语音覆盖率: {zh_coverage} ({total_with_zh * 100 // total_sentences}%)")

        # 保存修复后的数据
        if audio_file_fixed_count > 0 or audio_zh_fixed_count > 0 or duration_fixed_count > 0 or duration_zh_fixed_count > 0 or warnings:
            try:
                with open(mapping_path, 'w', encoding='utf-8') as f:
                    json.dump({'sentences': sentences}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                issues.append(f"保存修复失败: {e}")

        # 构建返回结果
        if fixed_fields or warnings:
            audio_fixed.append({
                "book_id": book.id,
                "title": book.title,
                "fixed_fields": fixed_fields,
                "warnings": warnings
            })

        if issues:
            audio_errors.append({
                "book_id": book.id,
                "title": book.title,
                "issues": issues
            })

        return {"audio_fixed": audio_fixed, "audio_errors": audio_errors}

    async def check_and_fix_book_audio(self, db: AsyncSession, book_id: str) -> dict:
        """
        检查并修复单本书籍的音频配置

        检查内容：
        - sentences.json 文件格式
        - 缺失的字段自动修复（duration、duration_zh）
        - 音频文件完整性检查

        返回:
            dict: 包含检查和修复结果，格式兼容前端 AudioFixDialog
        """
        # 获取书籍信息
        book = await self.repository.get(db, book_id)
        if not book:
            raise ValueError("书籍未找到")

        return await self._check_and_fix_book_audio_internal(db, book)

    async def generate_translation(
        self,
        db: AsyncSession,
        book_id: str,
        user_id: int,
        progress_callback,
        force: bool = False
    ) -> TranslationGenerateResult:
        """
        生成书籍句子翻译
        1. 获取用户翻译API配置
        2. 读取 sentences.json
        3. 翻译每个英文句子为中文
        4. 保存翻译结果到 sentences.json
        """
        # 获取书籍信息
        book = await self.repository.get(db, book_id)
        if not book:
            return TranslationGenerateResult(success=False, message="书籍未找到")

        # 获取翻译API配置
        api, error_msg = await get_effective_translation_api_config(db, user_id)
        if error_msg:
            await progress_callback(0, f"获取翻译API失败: {error_msg}")
            return TranslationGenerateResult(success=False, message=error_msg)

        # 获取书籍音频文件夹路径
        book_path = Path(book.file_path)
        book_folder = book_path.parent
        audio_folder = book_folder / "audio"
        mapping_path = audio_folder / "sentences.json"

        if not mapping_path.exists():
            return TranslationGenerateResult(success=False, message="未找到 sentences.json 文件")

        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                sentences_data = json.load(f)
        except Exception as e:
            return TranslationGenerateResult(success=False, message=f"读取 sentences.json 失败: {str(e)}")

        sentences = sentences_data.get("sentences", [])
        if not sentences:
            return TranslationGenerateResult(success=True, message="没有需要翻译的句子")

        # 统计需要翻译的句子
        need_translate_count = 0
        for sentence in sentences:
            # 判断是否需要翻译：force=True 时全部翻译，否则只翻译没有翻译的
            if force or "translation" not in sentence or not sentence["translation"]:
                need_translate_count += 1

        if need_translate_count == 0:
            return TranslationGenerateResult(success=True, message="所有句子已有翻译")

        await progress_callback(0, f"开始翻译 {need_translate_count} 个句子...")

        translated_count = 0
        error_count = 0
        total = len(sentences)

        # 中间保存计数器（每翻译20个句子保存一次）
        save_interval = 20
        last_save_index = 0

        for i, sentence in enumerate(sentences):
            # 判断是否需要翻译
            if not force and sentence.get("translation"):
                continue

            text = sentence.get("text", "")
            if not text:
                continue

            # 调用翻译API
            result = await translation_service.translate_with_result(
                text=text,
                from_lang="en",
                to_lang="zh",
                app_id=api.app_id,
                app_key=api.app_key
            )

            if result.success:
                sentence["translation"] = result.translation
                translated_count += 1
            else:
                error_count += 1
                logger.warning(f"翻译失败 [{i}]: {text[:30]}... - {result.error}")

            # 更新进度
            progress = int((i / total) * 100)
            if translated_count % 10 == 0 or i == total - 1:
                await progress_callback(
                    progress,
                    f"翻译中... {translated_count}/{need_translate_count}"
                )

            # 检查是否需要保存中间进度
            if i - last_save_index >= save_interval:
                last_save_index = i
                # 检查是否已取消
                if is_cancelled(book_id):
                    await progress_callback(
                        int((i / total) * 100),
                        f"翻译已取消 (已翻译 {translated_count}/{need_translate_count})"
                    )
                    clear_cancel_event(book_id)
                    # 保存已翻译的内容
                    try:
                        with open(mapping_path, 'w', encoding='utf-8') as f:
                            json.dump(sentences_data, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    return TranslationGenerateResult(
                        success=False,
                        message=f"翻译已取消 (已翻译 {translated_count}/{need_translate_count})"
                    )

        # 循环结束后再次检查取消状态
        if is_cancelled(book_id):
            await progress_callback(100, f"翻译已取消 (已翻译 {translated_count}/{need_translate_count})")
            clear_cancel_event(book_id)
            try:
                with open(mapping_path, 'w', encoding='utf-8') as f:
                    json.dump(sentences_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return TranslationGenerateResult(
                success=False,
                message=f"翻译已取消 (已翻译 {translated_count}/{need_translate_count})"
            )

        # 保存翻译结果
        try:
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(sentences_data, f, ensure_ascii=False, indent=2)

            message = f"翻译完成！成功 {translated_count} 个"
            if error_count > 0:
                message += f"，失败 {error_count} 个"

            await progress_callback(100, message)
            return TranslationGenerateResult(success=True, message=message)

        except Exception as e:
            return TranslationGenerateResult(success=False, message=f"保存翻译结果失败: {str(e)}")

    async def generate_chinese_audio(
        self,
        db: AsyncSession,
        book_id: str,
        user_id: int,
        progress_callback,
        force: bool = False
    ) -> TranslationGenerateResult:
        """
        生成中文音频
        1. 获取用户设置（翻译API、TTS配置）
        2. 检查 sentences.json 是否有翻译
        3. 若无翻译，先翻译所有句子
        4. 生成中文音频
        5. 更新 sentences.json
        """
        async def update_progress_local(percentage: int, message: str):
            if progress_callback:
                await progress_callback(percentage, message)

        # 获取用户设置
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        user_settings = result.scalars().first()
        app_settings = get_settings()

        # 获取翻译API配置
        translation_api, error_msg = await get_effective_translation_api_config(db, user_id)
        if error_msg:
            await update_progress_local(0, f"获取翻译API失败: {error_msg}")
            return TranslationGenerateResult(success=False, message=error_msg)

        # 获取书籍信息
        book = await self.repository.get(db, book_id)
        if not book:
            return TranslationGenerateResult(success=False, message="书籍未找到")

        # 确定TTS服务配置
        service_name = user_settings.tts_service_name if user_settings else "kokoro-tts"
        voice_zh = None
        speed = 1.0
        doubao_app_id = None
        doubao_access_key = None
        doubao_resource_id = app_settings.DOUBAO_DEFAULT_RESOURCE_ID
        minimax_api_key = None
        minimax_model = None
        siliconflow_api_key = None
        siliconflow_model = None

        if service_name == "kokoro-tts":
            voice_zh = user_settings.kokoro_voice_zh if user_settings and user_settings.kokoro_voice_zh else app_settings.KOKORO_DEFAULT_VOICE_ZH
            speed = user_settings.kokoro_speed if user_settings and user_settings.kokoro_speed is not None else 1.0
        elif service_name == "minimax-tts":
            voice_zh = user_settings.minimax_voice_zh if user_settings and user_settings.minimax_voice_zh else app_settings.MINIMAX_DEFAULT_VOICE
            speed = user_settings.minimax_speed if user_settings and user_settings.minimax_speed is not None else 1.0
            minimax_api_key = user_settings.minimax_api_key if user_settings else None
            minimax_model = user_settings.minimax_model if user_settings else app_settings.MINIMAX_DEFAULT_MODEL
        elif service_name == "edge-tts":
            # 验证中文语音名称是否有效
            raw_voice_zh = user_settings.edge_tts_voice_zh if user_settings and user_settings.edge_tts_voice_zh else app_settings.EDGE_TTS_DEFAULT_VOICE_ZH
            voice_zh = validate_edge_tts_voice(raw_voice_zh, app_settings.EDGE_TTS_DEFAULT_VOICE_ZH)
            speed = user_settings.edge_tts_speed if user_settings and user_settings.edge_tts_speed is not None else 1.0
        elif service_name == "siliconflow-tts":
            voice_zh = user_settings.siliconflow_voice_zh if user_settings and user_settings.siliconflow_voice_zh else app_settings.SILICONFLOW_DEFAULT_VOICE
            siliconflow_api_key = user_settings.siliconflow_api_key if user_settings else None
            siliconflow_model = user_settings.siliconflow_model if user_settings else app_settings.SILICONFLOW_DEFAULT_MODEL
        else:
            # 豆包TTS
            voice_zh = user_settings.doubao_voice_zh if user_settings and user_settings.doubao_voice_zh else app_settings.DOUBAO_DEFAULT_VOICE_ZH
            speed = user_settings.doubao_speed if user_settings and user_settings.doubao_speed is not None else 1.0
            doubao_app_id = user_settings.doubao_app_id if user_settings else None
            doubao_access_key = user_settings.doubao_access_key if user_settings else None
            doubao_resource_id = user_settings.doubao_resource_id if user_settings else app_settings.DOUBAO_DEFAULT_RESOURCE_ID

        # 调用内部方法补充中文音频
        result = await self._supplement_single_book(
            db=db,
            book=book,
            translation_api=translation_api,
            service_name=service_name,
            voice_zh=voice_zh,
            speed=speed,
            doubao_app_id=doubao_app_id,
            doubao_access_key=doubao_access_key,
            doubao_resource_id=doubao_resource_id,
            minimax_api_key=minimax_api_key,
            minimax_model=minimax_model,
            siliconflow_api_key=siliconflow_api_key,
            siliconflow_model=siliconflow_model,
            progress_callback=progress_callback,
            force=force
        )

        return TranslationGenerateResult(success=result["success"], message=result["message"])


async def compress_all_images(db: AsyncSession) -> dict:
    """
    压缩所有书籍的图片，转换为WebP格式（管理员功能）
    
    扫描所有书籍的assets目录，将jpg/jpeg/png/bmp格式图片转换为WebP
    并自动更新MD文件中的图片引用链接
    
    返回:
        dict: 包含转换、跳过、错误数量及详细信息
    """
    from app.utils.image_utils import compress_to_webp
    
    settings = get_settings()
    books_dir = Path(settings.BOOKS_DIR)
    
    # 支持转换的图片格式
    convertible_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
    
    total_converted = 0
    total_skipped = 0
    total_errors = 0
    error_details = []
    
    # 遍历所有书籍目录
    for book_dir in books_dir.iterdir():
        if not book_dir.is_dir():
            continue
            
        assets_dir = book_dir / "assets"
        if not assets_dir.exists():
            continue
        
        # 查找可转换的图片
        for img_file in assets_dir.iterdir():
            if not img_file.is_file():
                continue
                
            if img_file.suffix.lower() not in convertible_extensions:
                continue
            
            # 检查是否已有对应的WebP文件
            webp_file = img_file.with_suffix('.webp')
            if webp_file.exists():
                total_skipped += 1
                logger.info(f"跳过 {img_file.name}，WebP版本已存在")
                continue
            
            try:
                # 转换为WebP
                success, file_size, saved_path = compress_to_webp(
                    source=img_file,
                    target_path=webp_file,
                    quality=80
                )
                
                if success:
                    # 删除原图
                    img_file.unlink()
                    total_converted += 1
                    logger.info(f"转换成功: {img_file.name} -> {saved_path.name}")
                    
                    # 更新MD文件中的引用
                    md_file = book_dir / f"{book_dir.name}.md"
                    if md_file.exists():
                        md_content = md_file.read_text(encoding='utf-8')
                        # 更新图片引用（支持 ./assets/xxx.jpg 和 assets/xxx.jpg 两种格式）
                        old_ref_patterns = [
                            f"./assets/{img_file.name}",
                            f"assets/{img_file.name}"
                        ]
                        for old_ref in old_ref_patterns:
                            if old_ref in md_content:
                                new_ref = old_ref.replace(img_file.name, webp_file.name)
                                md_content = md_content.replace(old_ref, new_ref)
                        md_file.write_text(md_content, encoding='utf-8')
                else:
                    total_errors += 1
                    error_msg = f"{book_dir.name}/{img_file.name}: 转换失败"
                    error_details.append(error_msg)
                    logger.error(error_msg)
                    
            except Exception as e:
                total_errors += 1
                error_msg = f"{book_dir.name}/{img_file.name}: {str(e)}"
                error_details.append(error_msg)
                logger.error(f"转换图片失败: {error_msg}")
    
    result = {
        "success": True,
        "message": f"图片压缩完成: 转换{total_converted}个, 跳过{total_skipped}个, 错误{total_errors}个",
        "converted": total_converted,
        "skipped": total_skipped,
        "errors": total_errors,
        "error_details": error_details[:10]  # 只返回前10个错误详情
    }
    
    logger.info(result["message"])
    return result


book_service = BookService()
