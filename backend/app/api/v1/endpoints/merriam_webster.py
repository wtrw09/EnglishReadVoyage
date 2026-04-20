"""韦氏词典API配置管理端点"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.dependencies import get_current_user, get_current_admin
from app.models.database_models import User, MerriamWebsterAPI
from app.schemas.dictionary import MerriamWebsterSettings, UpdateMerriamWebsterSettingsRequest


router = APIRouter()


@router.get("/settings", response_model=MerriamWebsterSettings)
async def get_merriam_webster_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取韦氏词典API配置状态。

    返回是否已配置API Key，不返回实际的Key值。
    """
    # 查找用户的配置
    result = await db.execute(
        select(MerriamWebsterAPI).where(
            MerriamWebsterAPI.user_id == current_user.id,
            MerriamWebsterAPI.is_active == True
        )
    )
    api_config = result.scalars().first()

    if not api_config:
        # 尝试查找admin的配置
        admin_result = await db.execute(
            select(User).where(User.username == "admin")
        )
        admin_user = admin_result.scalars().first()
        if admin_user and admin_user.id != current_user.id:
            result = await db.execute(
                select(MerriamWebsterAPI).where(
                    MerriamWebsterAPI.user_id == admin_user.id,
                    MerriamWebsterAPI.is_active == True
                )
            )
            api_config = result.scalars().first()

    if not api_config:
        return MerriamWebsterSettings(
            configured=False,
            has_learners_key=False,
            has_thesaurus_key=False
        )

    return MerriamWebsterSettings(
        configured=True,
        has_learners_key=bool(api_config.learners_key),
        has_thesaurus_key=bool(api_config.thesaurus_key)
    )


@router.put("/settings", response_model=MerriamWebsterSettings)
async def update_merriam_webster_settings(
    request: UpdateMerriamWebsterSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)  # 仅管理员可配置
):
    """
    更新韦氏词典API配置（仅限管理员）。

    Args:
        request: 包含 learners_key 和可选的 thesaurus_key

    Returns:
        更新后的配置状态
    """
    # 查找现有配置
    result = await db.execute(
        select(MerriamWebsterAPI).where(
            MerriamWebsterAPI.user_id == current_user.id,
            MerriamWebsterAPI.is_active == True
        )
    )
    api_config = result.scalars().first()

    if api_config:
        # 更新现有配置
        api_config.learners_key = request.learners_key
        api_config.thesaurus_key = request.thesaurus_key
    else:
        # 创建新配置
        api_config = MerriamWebsterAPI(
            user_id=current_user.id,
            learners_key=request.learners_key,
            thesaurus_key=request.thesaurus_key,
            is_active=True
        )
        db.add(api_config)

    await db.commit()
    await db.refresh(api_config)

    return MerriamWebsterSettings(
        configured=True,
        has_learners_key=bool(api_config.learners_key),
        has_thesaurus_key=bool(api_config.thesaurus_key)
    )


@router.delete("/settings")
async def delete_merriam_webster_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)  # 仅管理员可删除
):
    """
    删除韦氏词典API配置（仅限管理员）。
    """
    result = await db.execute(
        select(MerriamWebsterAPI).where(
            MerriamWebsterAPI.user_id == current_user.id
        )
    )
    api_configs = result.scalars().all()

    for api_config in api_configs:
        await db.delete(api_config)

    await db.commit()

    return {"success": True, "message": "韦氏词典API配置已删除"}
