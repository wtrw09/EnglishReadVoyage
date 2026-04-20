"""词典查询API端点。"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User, UserSettings, TranslationAPI, DictionaryHistory
from app.schemas.dictionary import DictionaryResponse, DictionaryHistoryResponse, DictionaryHistoryListResponse
from app.services.dictionary_service import dictionary_service
from app.services.translation_service import translation_service
from app.services.merriam_webster_service import MerriamWebsterService


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


async def get_user_translation(
    db: AsyncSession,
    user_id: int,
    text: str
) -> str:
    """获取用户的百度翻译结果
    - 管理员使用自己的翻译API
    - 普通用户直接使用admin的翻译API（无需同步数据库）
    """
    # 获取用户信息
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        return ""

    if user.role == "admin":
        # 管理员：使用自己的翻译API
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalars().first()
        if not settings or not settings.selected_translation_api_id:
            return ""

        result = await db.execute(
            select(TranslationAPI).where(
                TranslationAPI.id == settings.selected_translation_api_id,
                TranslationAPI.user_id == user_id,
                TranslationAPI.is_active == True
            )
        )
        api = result.scalars().first()
    else:
        # 普通用户：直接使用admin的翻译API
        result = await db.execute(select(User).where(User.username == "admin"))
        admin_user = result.scalars().first()
        if not admin_user:
            return ""

        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == admin_user.id)
        )
        admin_settings = result.scalars().first()
        if not admin_settings or not admin_settings.selected_translation_api_id:
            return ""

        result = await db.execute(
            select(TranslationAPI).where(
                TranslationAPI.id == admin_settings.selected_translation_api_id,
                TranslationAPI.user_id == admin_user.id,
                TranslationAPI.is_active == True
            )
        )
        api = result.scalars().first()

    if not api:
        return ""

    # 调用百度翻译API
    translation = await translation_service.translate_with_baidu(
        text=text,
        from_lang="en",
        to_lang="zh",
        app_id=api.app_id,
        app_key=api.app_key
    )

    return translation or ""


@router.get("/lookup", response_model=DictionaryResponse)
async def lookup_word(
    word: str = Query(..., min_length=1, description="要查询的英文单词"),
    sentence: str = Query("", description="单词所在的句子"),
    source: str = Query("", description="词典来源：'local' ECDICT，'api' FreeDictionaryAPI，'merriam-webster' 韦氏词典，为空则使用用户设置"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询英文单词的释义、音标等信息。

    根据用户的词典设置选择查询方式：
    - 本地ECDICT：使用本地词典数据库
    - FreeDictionaryAPI：使用在线API
    - 韦氏词典：使用Merriam-Webster Learner's Dictionary + Thesaurus

    可选提供sentence参数获取句子翻译（需要配置百度翻译API）：
    - 翻译单词所在的句子为中文

    包括：
    - 音标（phonetic）
    - 词性分类的释义
    - 例句和同义词
    - 句子翻译（如果提供了sentence参数）
    - 韦氏词典：额外提供同义词/反义词/习语

    Args:
        word: 要查询的英文单词
        sentence: 单词所在的句子（可选）
        source: 词典来源（可选，优先级高于用户设置）

    Returns:
        单词的详细信息

    Raises:
        HTTPException: 如果单词未找到返回404，服务错误返回500
    """
    if source:
        dict_source = source
    else:
        dict_source = await get_user_dictionary_source(db, current_user.id)
      
    # 获取用户的音标偏好
    accent = await get_user_phonetic_accent(db, current_user.id)

    # 韦氏词典需要获取API keys
    merriam_webster_keys = None
    if dict_source == "merriam-webster":
        merriam_webster_keys = await MerriamWebsterService.get_api_keys(db, current_user.id)
    result = await dictionary_service.lookup(word, dict_source, merriam_webster_keys)
    
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


@router.get("/translate-sentence")
async def translate_sentence(
    sentence: str = Query(..., min_length=1, description="要翻译的英文句子"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    翻译英文句子为中文。

    使用百度翻译API进行翻译。
    需要用户配置百度翻译API。

    Returns:
        句子翻译结果
    """
    translation = await get_user_translation(db, current_user.id, sentence)
    return {"sentence": sentence, "translation": translation}


@router.get("/status")
async def get_dictionary_status():
    """
    获取词典服务状态（无需认证）。

    返回本地ECDICT是否可用。
    """
    return {
        "ecdict_available": dictionary_service.ecdict_available,
        "ecdict_path": dictionary_service.ecdict_db_path
    }


@router.get("/history", response_model=DictionaryHistoryListResponse)
async def get_dictionary_history(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户的词典查询历史。

    返回最近的查询记录，最多100条。
    """
    result = await db.execute(
        select(DictionaryHistory)
        .where(DictionaryHistory.user_id == current_user.id)
        .order_by(DictionaryHistory.created_at.desc())
        .limit(limit)
    )
    history_list = result.scalars().all()

    return DictionaryHistoryListResponse(
        items=[DictionaryHistoryResponse.model_validate(h) for h in history_list],
        total=len(history_list)
    )


@router.post("/history", response_model=DictionaryHistoryResponse)
async def add_dictionary_history(
    word: str = Query(..., min_length=1, description="查询的单词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    添加词典查询历史记录。

    如果单词已存在于历史中，则更新时间戳（删除旧记录，创建新记录）。
    """
    # 删除同一用户相同单词的旧记录
    await db.execute(
        delete(DictionaryHistory).where(
            DictionaryHistory.user_id == current_user.id,
            DictionaryHistory.word == word
        )
    )

    # 创建新记录
    history = DictionaryHistory(
        user_id=current_user.id,
        word=word
    )
    db.add(history)
    await db.commit()
    await db.refresh(history)

    return history


@router.delete("/history")
async def clear_dictionary_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    清空用户的词典查询历史。
    """
    await db.execute(
        delete(DictionaryHistory).where(DictionaryHistory.user_id == current_user.id)
    )
    await db.commit()

    return {"success": True, "message": "历史记录已清空"}
