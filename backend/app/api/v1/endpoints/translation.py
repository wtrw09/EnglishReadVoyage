"""翻译API端点 - 百度翻译配置管理"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User, UserSettings, TranslationAPI
from app.schemas.dictionary import (
    TranslationAPIConfig,
    TranslationAPIResponse,
    UserTranslationSettings
)


router = APIRouter()


async def get_effective_translation_api(db: AsyncSession, user_id: int) -> Optional[TranslationAPI]:
    """
    获取用户实际可用的翻译API
    - 如果用户是管理员，使用用户自己的翻译API
    - 如果用户不是管理员，使用admin用户的翻译API
    - 如果admin用户没有配置，返回None
    """
    # 获取用户信息
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        return None

    # 获取用户设置
    settings = await get_or_create_user_settings(db, user_id)

    # 如果是管理员，使用自己的翻译API
    if user.role == "admin":
        if not settings.selected_translation_api_id:
            return None

        result = await db.execute(
            select(TranslationAPI).where(
                TranslationAPI.id == settings.selected_translation_api_id,
                TranslationAPI.user_id == user_id
            )
        )
        return result.scalars().first()

    # 非管理员：查找admin用户
    result = await db.execute(select(User).where(User.username == "admin"))
    admin_user = result.scalars().first()

    if not admin_user:
        return None

    # 获取admin用户的设置
    admin_settings = await get_or_create_user_settings(db, admin_user.id)

    if not admin_settings.selected_translation_api_id:
        return None

    # 获取admin用户的翻译API
    result = await db.execute(
        select(TranslationAPI).where(
            TranslationAPI.id == admin_settings.selected_translation_api_id,
            TranslationAPI.user_id == admin_user.id,
            TranslationAPI.is_active == True
        )
    )
    return result.scalars().first()


async def get_effective_translation_api_id(db: AsyncSession, user_id: int) -> tuple[Optional[int], Optional[str]]:
    """
    获取用户实际可用的翻译API ID和错误信息
    返回: (api_id, error_message)
    """
    api = await get_effective_translation_api(db, user_id)

    if api:
        return api.id, None

    # 获取用户信息，检查是否是管理员
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user and user.role == "admin":
        return None, "请先配置百度翻译API：设置 → 词典设置"
    else:
        return None, "管理员未配置百度翻译API，请联系管理员"


async def get_effective_translation_api_config(db: AsyncSession, user_id: int) -> tuple[Optional[dict], str]:
    """
    获取用户实际可用的翻译API配置
    返回: (config_dict, error_message)
    """
    # 获取用户信息
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        return None, "用户不存在"

    # 获取用户设置
    settings = await get_or_create_user_settings(db, user_id)

    # 如果是管理员，使用自己的翻译API
    if user.role == "admin":
        if not settings.selected_translation_api_id:
            return None, "请先配置百度翻译API"

        result = await db.execute(
            select(TranslationAPI).where(
                TranslationAPI.id == settings.selected_translation_api_id,
                TranslationAPI.user_id == user_id,
                TranslationAPI.is_active == True
            )
        )
        api = result.scalars().first()

        if not api:
            return None, "翻译API未启用或不存在"

        return {
            "app_id": api.app_id,
            "app_key": api.app_key
        }, None

    # 非管理员：使用admin的翻译API
    result = await db.execute(select(User).where(User.username == "admin"))
    admin_user = result.scalars().first()

    if not admin_user:
        return None, "管理员账户不存在"

    admin_settings = await get_or_create_user_settings(db, admin_user.id)

    if not admin_settings.selected_translation_api_id:
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

    return {
        "app_id": api.app_id,
        "app_key": api.app_key
    }, None


async def get_or_create_user_settings(db: AsyncSession, user_id: int) -> UserSettings:
    """获取或创建用户设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalars().first()

    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


@router.get("/settings", response_model=UserTranslationSettings)
async def get_translation_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户的翻译设置
    """
    # 获取用户设置
    settings = await get_or_create_user_settings(db, current_user.id)

    # 获取用户的翻译API列表
    result = await db.execute(
        select(TranslationAPI).where(TranslationAPI.user_id == current_user.id)
    )
    apis = result.scalars().all()

    api_responses = [
        TranslationAPIResponse(
            id=api.id,
            name=api.name,
            app_id=api.app_id,
            is_active=api.is_active,
            created_at=api.created_at
        )
        for api in apis
    ]

    return UserTranslationSettings(
        selected_api_id=settings.selected_translation_api_id,
        apis=api_responses,
        is_admin=current_user.role == "admin"
    )


@router.get("/apis", response_model=List[TranslationAPIResponse])
async def get_translation_apis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户所有翻译API配置
    """
    result = await db.execute(
        select(TranslationAPI).where(TranslationAPI.user_id == current_user.id)
    )
    apis = result.scalars().all()

    return [
        TranslationAPIResponse(
            id=api.id,
            name=api.name,
            app_id=api.app_id,
            is_active=api.is_active,
            created_at=api.created_at
        )
        for api in apis
    ]


@router.post("/apis", response_model=TranslationAPIResponse, status_code=status.HTTP_201_CREATED)
async def create_translation_api(
    api_config: TranslationAPIConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    添加新的翻译API配置（仅管理员可操作）
    """
    # 检查是否是管理员
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员才能配置翻译API"
        )

    # 检查是否已存在同名API
    result = await db.execute(
        select(TranslationAPI).where(
            TranslationAPI.user_id == current_user.id,
            TranslationAPI.name == api_config.name
        )
    )
    existing = result.scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已存在同名翻译API配置"
        )

    # 创建新API
    api = TranslationAPI(
        user_id=current_user.id,
        name=api_config.name,
        app_id=api_config.app_id,
        app_key=api_config.app_key,
        is_active=api_config.is_active
    )
    db.add(api)
    await db.commit()
    await db.refresh(api)

    return TranslationAPIResponse(
        id=api.id,
        name=api.name,
        app_id=api.app_id,
        is_active=api.is_active,
        created_at=api.created_at
    )


@router.put("/apis/{api_id}", response_model=TranslationAPIResponse)
async def update_translation_api(
    api_id: int,
    api_config: TranslationAPIConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新翻译API配置（仅管理员可操作）
    """
    # 检查是否是管理员
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员才能修改翻译API"
        )

    result = await db.execute(
        select(TranslationAPI).where(
            TranslationAPI.id == api_id,
            TranslationAPI.user_id == current_user.id
        )
    )
    api = result.scalars().first()

    if not api:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="翻译API配置不存在"
        )

    # 更新字段
    api.name = api_config.name
    api.app_id = api_config.app_id
    if api_config.app_key:  # 只在提供新密码时更新
        api.app_key = api_config.app_key
    api.is_active = api_config.is_active

    await db.commit()
    await db.refresh(api)

    return TranslationAPIResponse(
        id=api.id,
        name=api.name,
        app_id=api.app_id,
        is_active=api.is_active,
        created_at=api.created_at
    )


@router.delete("/apis/{api_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_translation_api(
    api_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除翻译API配置（仅管理员可操作）
    """
    # 检查是否是管理员
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员才能删除翻译API"
        )

    result = await db.execute(
        select(TranslationAPI).where(
            TranslationAPI.id == api_id,
            TranslationAPI.user_id == current_user.id
        )
    )
    api = result.scalars().first()

    if not api:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="翻译API配置不存在"
        )

    # 如果删除的是当前选中的API，清除选择
    settings = await get_or_create_user_settings(db, current_user.id)
    if settings.selected_translation_api_id == api_id:
        settings.selected_translation_api_id = None

    await db.delete(api)
    await db.commit()


@router.put("/select")
async def select_translation_api(
    api_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    选择当前使用的翻译API（仅管理员可操作）
    """
    # 检查是否是管理员
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员才能选择翻译API"
        )

    # 验证API存在且属于当前用户
    if api_id:
        result = await db.execute(
            select(TranslationAPI).where(
                TranslationAPI.id == api_id,
                TranslationAPI.user_id == current_user.id
            )
        )
        api = result.scalars().first()
        if not api:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="翻译API配置不存在"
            )

    # 更新用户设置
    settings = await get_or_create_user_settings(db, current_user.id)
    settings.selected_translation_api_id = api_id if api_id else None

    await db.commit()

    return {"message": "翻译API选择已更新", "selected_api_id": settings.selected_translation_api_id}


@router.get("/status")
async def get_translation_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    检查用户是否可以使用百度翻译API
    - 管理员：检查自己的配置
    - 普通用户：使用admin的配置
    返回: { "configured": true/false, "message": "..." }
    """
    api = await get_effective_translation_api(db, current_user.id)

    if not api:
        # 检查用户是否是管理员
        if current_user.role == "admin":
            return {
                "configured": False,
                "message": "请先配置百度翻译API：设置 → 词典设置"
            }
        else:
            return {
                "configured": False,
                "message": "管理员未配置百度翻译API，请联系管理员"
            }

    # 判断使用的是谁的API
    is_using_admin = current_user.role != "admin"

    return {
        "configured": True,
        "message": "翻译API已配置",
        "api_name": api.name,
        "is_using_admin_api": is_using_admin
    }
