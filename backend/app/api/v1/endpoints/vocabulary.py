"""生词本API端点。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from typing import List

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User, Vocabulary
from app.schemas.vocabulary import VocabularyCreate, VocabularyResponse, VocabularyListResponse


router = APIRouter()


@router.post("/", response_model=VocabularyResponse)
async def add_vocabulary(
    request: VocabularyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    添加生词到生词本。

    如果相同的单词和句子组合已存在，则返回已存在的记录。
    """
    # 检查是否已存在相同的生词（同一用户、同一单词、同一句子）
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.user_id == current_user.id,
            Vocabulary.word == request.word,
            Vocabulary.sentence == request.sentence
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # 已存在则返回已存在的记录
        return existing

    # 创建新的生词记录
    vocab = Vocabulary(
        user_id=current_user.id,
        word=request.word,
        phonetic=request.phonetic,
        translation=request.translation,
        sentence=request.sentence,
        book_name=request.book_name
    )
    db.add(vocab)
    await db.commit()
    await db.refresh(vocab)

    return vocab


@router.get("/", response_model=VocabularyListResponse)
async def get_vocabulary_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的生词列表。

    按添加时间倒序排列。
    """
    stmt = select(Vocabulary).where(
        Vocabulary.user_id == current_user.id
    ).order_by(desc(Vocabulary.created_at))

    result = await db.execute(stmt)
    vocab_list = result.scalars().all()

    return VocabularyListResponse(
        items=[VocabularyResponse.model_validate(v) for v in vocab_list],
        total=len(vocab_list)
    )


@router.delete("/{vocab_id}")
async def delete_vocabulary(
    vocab_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除生词本中的生词。

    只能删除自己添加的生词。
    """
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.id == vocab_id,
            Vocabulary.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    vocab = result.scalar_one_or_none()

    if not vocab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="生词不存在"
        )

    await db.delete(vocab)
    await db.commit()

    return {"success": True, "message": "生词已删除"}


@router.get("/check", response_model=dict)
async def check_vocabulary_exists(
    word: str,
    sentence: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    检查生词是否已存在于生词本中。
    """
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.user_id == current_user.id,
            Vocabulary.word == word,
            Vocabulary.sentence == sentence
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    return {
        "exists": existing is not None,
        "id": existing.id if existing else None
    }
