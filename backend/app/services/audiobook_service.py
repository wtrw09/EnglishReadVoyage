"""听书播放器业务逻辑服务层"""
import json
import random
import hashlib
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path

from app.repositories.audiobook_repository import audiobook_repository
from app.models.database_models import AudiobookPlaylist, AudiobookPlaylistItem, Book, Category, BookCategoryRel
from app.schemas.audiobook import (
    PlaylistResponse,
    PlaylistItemResponse,
    PlaylistOperationResponse,
    NextBookResponse,
    BooksByGroupResponse,
    BookForPlaylistResponse,
    BookAudioListResponse,
    BookAudioInfo
)
from app.core.config import get_settings


class AudiobookService:
    """听书播放器业务逻辑服务"""

    def __init__(self):
        self.repository = audiobook_repository

    async def get_user_playlist(self, db: AsyncSession, user_id: int) -> PlaylistResponse:
        """获取用户播放列表详情"""
        playlist = await self.repository.get_or_create_playlist(db, user_id)

        # 获取列表项及书籍信息
        items = await self.repository.get_playlist_items(db, playlist.id)

        item_responses = []
        for item in items:
            # 使用数据库中存储的 cover_path
            book_cover = item.book.cover_path if item.book else None

            item_responses.append(PlaylistItemResponse(
                id=item.id,
                book_id=item.book_id,
                book_title=item.book.title if item.book else "未知书籍",
                book_cover=book_cover,
                sort_order=item.sort_order,
                added_at=item.added_at
            ))

        return PlaylistResponse(
            id=playlist.id,
            name=playlist.name,
            play_mode=playlist.play_mode,
            sleep_timer=playlist.sleep_timer,
            current_book_index=playlist.current_book_index,
            items=item_responses,
            created_at=playlist.created_at,
            updated_at=playlist.updated_at
        )

    async def add_books_to_playlist(
        self,
        db: AsyncSession,
        user_id: int,
        book_ids: List[str]
    ) -> PlaylistOperationResponse:
        """批量添加书籍到播放列表"""
        playlist = await self.repository.get_or_create_playlist(db, user_id)

        # 获取当前最大排序值
        items = await self.repository.get_playlist_items(db, playlist.id)
        max_order = max([item.sort_order for item in items], default=-1)

        added_count = 0
        for book_id in book_ids:
            # 检查是否已存在
            existing = any(item.book_id == book_id for item in items)
            if not existing:
                max_order += 1
                await self.repository.add_book_to_playlist(
                    db, playlist.id, book_id, max_order
                )
                added_count += 1

        await db.commit()

        return PlaylistOperationResponse(
            success=True,
            message=f"成功添加 {added_count} 本书籍到播放列表"
        )

    async def remove_book_from_playlist(
        self,
        db: AsyncSession,
        user_id: int,
        item_id: int
    ) -> PlaylistOperationResponse:
        """从播放列表中移除书籍"""
        # 验证权限
        playlist = await self.repository.get_user_playlist(db, user_id)
        if not playlist:
            return PlaylistOperationResponse(success=False, message="播放列表不存在")

        # 验证该项是否属于该用户的播放列表
        items = await self.repository.get_playlist_items(db, playlist.id)
        item = next((i for i in items if i.id == item_id), None)
        if not item:
            return PlaylistOperationResponse(success=False, message="列表项不存在")

        await self.repository.remove_book_from_playlist(db, item_id)

        # 如果删除的是当前播放索引之前或当前的书籍，需要调整索引
        item_index = next((i for i, it in enumerate(items) if it.id == item_id), -1)
        if item_index != -1 and item_index <= playlist.current_book_index and playlist.current_book_index > 0:
            playlist.current_book_index -= 1

        await db.commit()

        return PlaylistOperationResponse(success=True, message="已从播放列表移除")

    async def reorder_playlist(
        self,
        db: AsyncSession,
        user_id: int,
        item_orders: List[dict]
    ) -> PlaylistOperationResponse:
        """重新排序播放列表"""
        playlist = await self.repository.get_user_playlist(db, user_id)
        if not playlist:
            return PlaylistOperationResponse(success=False, message="播放列表不存在")

        await self.repository.reorder_items(db, playlist.id, item_orders)
        await db.commit()

        return PlaylistOperationResponse(success=True, message="排序已更新")

    async def update_play_settings(
        self,
        db: AsyncSession,
        user_id: int,
        play_mode: Optional[str] = None,
        sleep_timer: Optional[int] = None,
        current_book_index: Optional[int] = None
    ) -> PlaylistOperationResponse:
        """更新播放设置"""
        playlist = await self.repository.get_user_playlist(db, user_id)
        if not playlist:
            return PlaylistOperationResponse(success=False, message="播放列表不存在")

        await self.repository.update_settings(
            db, playlist.id, play_mode, sleep_timer, current_book_index
        )
        await db.commit()

        return PlaylistOperationResponse(success=True, message="设置已更新")

    async def get_next_book(
        self,
        db: AsyncSession,
        user_id: int,
        direction: str = "next"
    ) -> NextBookResponse:
        """获取下一本/上一本书籍

        Args:
            direction: "next" 或 "prev"
        """
        playlist = await self.repository.get_user_playlist(db, user_id)
        if not playlist:
            return NextBookResponse(has_next=False, index=-1)

        items = await self.repository.get_playlist_items(db, playlist.id)
        if not items:
            return NextBookResponse(has_next=False, index=-1)

        current_index = playlist.current_book_index

        if playlist.play_mode == "single":
            # 单曲循环模式：保持在当前书籍
            return NextBookResponse(has_next=False, index=current_index)
        elif playlist.play_mode == "random":
            # 随机模式：随机选择一个索引（不包括当前）
            available_indices = [i for i in range(len(items)) if i != current_index]
            if not available_indices:
                return NextBookResponse(has_next=False, index=current_index)
            next_index = random.choice(available_indices)
        else:  # sequential 顺序模式
            if direction == "next":
                next_index = current_index + 1
                if next_index >= len(items):
                    next_index = 0  # 循环到第一首
            else:  # prev
                next_index = current_index - 1
                if next_index < 0:
                    next_index = len(items) - 1  # 循环到最后一首

        if 0 <= next_index < len(items):
            item = items[next_index]
            book_cover = None
            if item.book and item.book.cover_path:
                book_cover = f"/books/cover/{item.book.id}"

            # 更新当前索引
            playlist.current_book_index = next_index
            await db.commit()

            return NextBookResponse(
                has_next=True,
                book_id=item.book_id,
                book_title=item.book.title if item.book else "未知书籍",
                book_cover=book_cover,
                index=next_index
            )

        return NextBookResponse(has_next=False, index=current_index)

    async def get_available_books_by_group(
        self,
        db: AsyncSession,
        user_id: int
    ) -> List[BooksByGroupResponse]:
        """获取可按分组添加的书籍列表"""
        # 获取所有分组
        result = await db.execute(
            select(Category).where(Category.user_id == user_id)
        )
        categories = result.scalars().all()

        groups = []

        # 处理每个分组
        for category in categories:
            # 获取该分组下的书籍
            result = await db.execute(
                select(Book)
                .join(BookCategoryRel, Book.id == BookCategoryRel.book_id)
                .where(
                    BookCategoryRel.category_id == category.id,
                    BookCategoryRel.user_id == user_id
                )
            )
            books = result.scalars().all()

            book_responses = []
            for book in books:
                book_responses.append(BookForPlaylistResponse(
                    id=book.id,
                    title=book.title,
                    cover_path=book.cover_path,  # 直接使用数据库中的 cover_path
                    level="Unknown"  # 可以从标签解析
                ))

            groups.append(BooksByGroupResponse(
                group_id=category.id,
                group_name=category.name,
                books=book_responses
            ))

        # 添加"未分组"类别
        result = await db.execute(
            select(Book)
            .outerjoin(
                BookCategoryRel,
                (Book.id == BookCategoryRel.book_id) & (BookCategoryRel.user_id == user_id)
            )
            .where(BookCategoryRel.book_id == None)
        )
        uncategorized_books = result.scalars().all()

        if uncategorized_books:
            book_responses = []
            for book in uncategorized_books:
                book_responses.append(BookForPlaylistResponse(
                    id=book.id,
                    title=book.title,
                    cover_path=book.cover_path,  # 直接使用数据库中的 cover_path
                    level="Unknown"
                ))

            groups.append(BooksByGroupResponse(
                group_id=0,
                group_name="未分组",
                books=book_responses
            ))

        return groups

    async def clear_playlist(
        self,
        db: AsyncSession,
        user_id: int
    ) -> PlaylistOperationResponse:
        """清空播放列表"""
        playlist = await self.repository.get_user_playlist(db, user_id)
        if not playlist:
            return PlaylistOperationResponse(success=False, message="播放列表不存在")

        await self.repository.clear_playlist(db, playlist.id)
        playlist.current_book_index = 0
        await db.commit()

        return PlaylistOperationResponse(success=True, message="播放列表已清空")

    async def get_book_audio_list(
        self,
        db: AsyncSession,
        book_id: str
    ) -> BookAudioListResponse:
        """获取书籍的音频列表"""
        # 获取书籍信息
        from app.repositories.book_repository import book_repository
        book = await book_repository.get(db, book_id)
        if not book:
            return BookAudioListResponse(
                book_id=book_id,
                book_title="未知书籍",
                total=0,
                total_duration=0.0,
                audio_list=[]
            )

        # 获取音频文件夹路径
        book_folder = Path(book.file_path).parent
        audio_folder = book_folder / "audio"
        mapping_file = audio_folder / "sentences.json"

        # 检查映射文件是否存在
        if not mapping_file.exists():
            return BookAudioListResponse(
                book_id=book_id,
                book_title=book.title,
                total=0,
                total_duration=0.0,
                audio_list=[]
            )

        # 读取映射文件
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
        except Exception as e:
            print(f"读取音频映射文件失败: {e}")
            return BookAudioListResponse(
                book_id=book_id,
                book_title=book.title,
                total=0,
                total_duration=0.0,
                audio_list=[]
            )

        # 兼容旧格式：如果是列表，则转换为新格式
        if isinstance(mapping_data, list):
            sentences = mapping_data
            total_duration = 0.0
        else:
            # 新格式：包含 total_duration 和 sentences
            sentences = mapping_data.get('sentences', [])
            total_duration = mapping_data.get('total_duration', 0.0)

        # 获取音频文件夹中所有mp3文件
        existing_audio_files = set()
        if audio_folder.exists():
            existing_audio_files = {f.name for f in audio_folder.glob('*.mp3')}

        # 构建音频列表
        audio_list = []
        for item in sentences:
            text = item.get('text', '')
            if text:
                # 根据文本计算MD5哈希
                text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
                audio_file = f"{text_hash}.mp3"

                # 检查音频文件是否存在
                if audio_file in existing_audio_files:
                    audio_url = f"/books/{book_folder.name}/audio/{audio_file}"
                    audio_list.append(BookAudioInfo(
                        text_hash=text_hash,
                        text=text,
                        audio_url=audio_url,
                        duration=item.get('duration', 0.0)
                    ))

        return BookAudioListResponse(
            book_id=book_id,
            book_title=book.title,
            total=len(audio_list),
            total_duration=total_duration,
            audio_list=audio_list
        )


audiobook_service = AudiobookService()
