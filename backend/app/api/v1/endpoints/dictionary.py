"""词典查询API端点。"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User, UserSettings
from app.schemas.dictionary import DictionaryResponse
from app.services.dictionary_service import dictionary_service


router = APIRouter()


async def get_user_dictionary_source(
    db: AsyncSession,
    user_id: int
) -> str:
    """获取用户的词典来源设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalars().first()
    if settings:
        return settings.dictionary_source
    return "local"  # 默认使用本地词典


async def get_user_phonetic_accent(
    db: AsyncSession,
    user_id: int
) -> str:
    """获取用户的音标口音偏好设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalars().first()
    if settings:
        return settings.phonetic_accent or "uk"
    return "uk"  # 默认使用英式音标


@router.get("/lookup", response_model=DictionaryResponse)
async def lookup_word(
    word: str = Query(..., min_length=1, description="要查询的英文单词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询英文单词的释义、音标等信息。

    根据用户的词典设置选择查询方式：
    - 本地ECDICT：使用本地词典数据库
    - FreeDictionaryAPI：使用在线API

    包括：
    - 音标（phonetic）
    - 词性分类的释义
    - 例句和同义词

    Args:
        word: 要查询的英文单词

    Returns:
        单词的详细信息

    Raises:
        HTTPException: 如果单词未找到返回404，服务错误返回500
    """
    # 获取用户的词典设置和音标偏好
    source = await get_user_dictionary_source(db, current_user.id)
    accent = await get_user_phonetic_accent(db, current_user.id)
    
    # 使用词典服务查询
    result = await dictionary_service.lookup(word, source)
    
    # 根据用户偏好选择主音标
    if result and result.phonetics:
        preferred_phonetic = None
        for p in result.phonetics:
            if p.accent == accent and p.text:
                preferred_phonetic = p.text
                break
        # 如果没有找到对应口音的音标，使用第一个有文本的音标
        if not preferred_phonetic:
            for p in result.phonetics:
                if p.text:
                    preferred_phonetic = p.text
                    break
        if preferred_phonetic:
            result.phonetic = preferred_phonetic
    
    return result


@router.get("/status")
async def get_dictionary_status(
    current_user: User = Depends(get_current_user)
):
    """
    获取词典服务状态。
    
    返回本地ECDICT是否可用。
    """
    return {
        "ecdict_available": dictionary_service.ecdict_available,
        "ecdict_path": dictionary_service.ecdict_db_path
    }
