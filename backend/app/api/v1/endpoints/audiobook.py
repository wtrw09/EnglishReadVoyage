"""听书播放器API端点"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.audiobook import (
    PlaylistResponse,
    PlaylistItemAddRequest,
    PlaylistItemReorderRequest,
    PlaylistSettingsUpdateRequest,
    PlaylistOperationResponse,
    NextBookResponse,
    BooksByGroupResponse,
    BookAudioListResponse,
    PlaylistAudioCheckResponse
)
from app.services.audiobook_service import audiobook_service
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User


router = APIRouter()


@router.get("/playlist", response_model=PlaylistResponse)
async def get_playlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的播放列表"""
    return await audiobook_service.get_user_playlist(db, current_user.id)


@router.post("/playlist/books", response_model=PlaylistOperationResponse)
async def add_books_to_playlist(
    request: PlaylistItemAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量添加书籍到播放列表"""
    result = await audiobook_service.add_books_to_playlist(
        db, current_user.id, request.book_ids
    )
    return result


@router.delete("/playlist/items/{item_id}", response_model=PlaylistOperationResponse)
async def remove_book_from_playlist(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从播放列表中移除书籍"""
    result = await audiobook_service.remove_book_from_playlist(
        db, current_user.id, item_id
    )
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.message
        )
    return result


@router.put("/playlist/reorder", response_model=PlaylistOperationResponse)
async def reorder_playlist(
    request: PlaylistItemReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重新排序播放列表"""
    result = await audiobook_service.reorder_playlist(
        db, current_user.id, request.item_orders
    )
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message
        )
    return result


@router.put("/playlist/settings", response_model=PlaylistOperationResponse)
async def update_playlist_settings(
    request: PlaylistSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新播放列表设置（播放模式、定时关闭等）"""
    result = await audiobook_service.update_play_settings(
        db,
        current_user.id,
        play_mode=request.play_mode,
        sleep_timer=request.sleep_timer,
        current_book_index=request.current_book_index
    )
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message
        )
    return result


@router.get("/playlist/books", response_model=List[BooksByGroupResponse])
async def get_available_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取可按分组添加的书籍列表"""
    return await audiobook_service.get_available_books_by_group(db, current_user.id)


@router.get("/playlist/next", response_model=NextBookResponse)
async def get_next_book(
    direction: str = "next",
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取下一本/上一本书籍

    Args:
        direction: 方向，"next" 表示下一本，"prev" 表示上一本
        force: 是否强制切换，忽略单曲循环模式限制（手动点击时使用）
    """
    if direction not in ["next", "prev"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="direction 参数必须是 'next' 或 'prev'"
        )
    return await audiobook_service.get_next_book(db, current_user.id, direction, force)


@router.delete("/playlist/clear", response_model=PlaylistOperationResponse)
async def clear_playlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清空播放列表"""
    result = await audiobook_service.clear_playlist(db, current_user.id)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message
        )
    return result


@router.get("/books/{book_id}/audio", response_model=BookAudioListResponse)
async def get_book_audio_list(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取书籍的音频列表"""
    return await audiobook_service.get_book_audio_list(db, book_id)


@router.get("/playlist/audio-check", response_model=PlaylistAudioCheckResponse)
async def check_playlist_audio_completeness(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查播放列表中所有书籍的音频完整性（英文和中文）"""
    return await audiobook_service.check_playlist_audio_completeness(db, current_user.id)
