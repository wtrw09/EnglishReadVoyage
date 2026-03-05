"""听书播放列表仓库层"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.repositories.base_repository import BaseRepository
from app.models.database_models import AudiobookPlaylist, AudiobookPlaylistItem


class AudiobookRepository(BaseRepository[AudiobookPlaylist]):
    """听书播放列表仓库操作"""

    async def get_user_playlist(self, db: AsyncSession, user_id: int) -> Optional[AudiobookPlaylist]:
        """获取用户的播放列表，如果不存在返回None"""
        result = await db.execute(
            select(AudiobookPlaylist)
            .where(AudiobookPlaylist.user_id == user_id)
            .options(selectinload(AudiobookPlaylist.items).selectinload(AudiobookPlaylistItem.book))
        )
        return result.scalars().first()

    async def create_default_playlist(self, db: AsyncSession, user_id: int) -> AudiobookPlaylist:
        """创建用户默认播放列表"""
        playlist_data = {
            "user_id": user_id,
            "name": "默认播放列表",
            "play_mode": "sequential",
            "sleep_timer": None,
            "current_book_index": 0
        }
        return await self.create(db, playlist_data)

    async def get_or_create_playlist(self, db: AsyncSession, user_id: int) -> AudiobookPlaylist:
        """获取或创建用户播放列表"""
        playlist = await self.get_user_playlist(db, user_id)
        if not playlist:
            playlist = await self.create_default_playlist(db, user_id)
            await db.commit()
        return playlist

    async def get_playlist_items(self, db: AsyncSession, playlist_id: int) -> List[AudiobookPlaylistItem]:
        """获取播放列表的所有项，按sort_order排序"""
        result = await db.execute(
            select(AudiobookPlaylistItem)
            .where(AudiobookPlaylistItem.playlist_id == playlist_id)
            .order_by(AudiobookPlaylistItem.sort_order)
            .options(selectinload(AudiobookPlaylistItem.book))
        )
        return result.scalars().all()

    async def add_book_to_playlist(
        self,
        db: AsyncSession,
        playlist_id: int,
        book_id: str,
        sort_order: int = 0
    ) -> AudiobookPlaylistItem:
        """添加书籍到播放列表"""
        item_data = {
            "playlist_id": playlist_id,
            "book_id": book_id,
            "sort_order": sort_order
        }
        item = AudiobookPlaylistItem(**item_data)
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item

    async def remove_book_from_playlist(self, db: AsyncSession, item_id: int) -> bool:
        """从播放列表中移除书籍"""
        result = await db.execute(
            delete(AudiobookPlaylistItem).where(AudiobookPlaylistItem.id == item_id)
        )
        return result.rowcount > 0

    async def reorder_items(self, db: AsyncSession, playlist_id: int, item_orders: List[dict]) -> bool:
        """重新排序播放列表项

        Args:
            item_orders: 格式为 [{"item_id": int, "sort_order": int}, ...]
        """
        for order_info in item_orders:
            await db.execute(
                select(AudiobookPlaylistItem)
                .where(
                    AudiobookPlaylistItem.id == order_info["item_id"],
                    AudiobookPlaylistItem.playlist_id == playlist_id
                )
            )
            result = await db.execute(
                select(AudiobookPlaylistItem).where(AudiobookPlaylistItem.id == order_info["item_id"])
            )
            item = result.scalar_one_or_none()
            if item:
                item.sort_order = order_info["sort_order"]
        return True

    async def update_current_index(self, db: AsyncSession, playlist_id: int, index: int) -> bool:
        """更新当前播放的书籍索引"""
        result = await db.execute(
            select(AudiobookPlaylist).where(AudiobookPlaylist.id == playlist_id)
        )
        playlist = result.scalar_one_or_none()
        if playlist:
            playlist.current_book_index = index
            return True
        return False

    async def update_settings(
        self,
        db: AsyncSession,
        playlist_id: int,
        play_mode: Optional[str] = None,
        sleep_timer: Optional[int] = None,
        current_book_index: Optional[int] = None
    ) -> bool:
        """更新播放列表设置"""
        result = await db.execute(
            select(AudiobookPlaylist).where(AudiobookPlaylist.id == playlist_id)
        )
        playlist = result.scalar_one_or_none()
        if not playlist:
            return False

        if play_mode is not None:
            playlist.play_mode = play_mode
        if sleep_timer is not None:
            playlist.sleep_timer = sleep_timer
        if current_book_index is not None:
            playlist.current_book_index = current_book_index
        return True

    async def clear_playlist(self, db: AsyncSession, playlist_id: int) -> bool:
        """清空播放列表"""
        result = await db.execute(
            delete(AudiobookPlaylistItem).where(AudiobookPlaylistItem.playlist_id == playlist_id)
        )
        return result.rowcount >= 0


audiobook_repository = AudiobookRepository(AudiobookPlaylist)
