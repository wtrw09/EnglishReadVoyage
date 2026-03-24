"""身份认证API端点。"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import get_settings
from app.api.dependencies import get_current_user, get_current_admin
from app.models.database_models import User, UserSettings
from app.services.auth_service import AuthService
from app.schemas.auth import (
    LoginResponse,
    UserCreateByAdmin,
    UserActivateRequest,
    UserResponse,
    UserDetailResponse,
    UserCreateResponse,
    UpdatePasswordRequest,
    UpdateCurrentUserPasswordRequest,
    UpdateUserRequest
)

router = APIRouter()


# ==================== 身份认证端点 ====================

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """用户登录并返回JWT令牌。
    
    符合OAuth2标准的端点,用于Swagger自动授权。
    
    Args:
        form_data: 来自OAuth2表单的用户名和密码
        db: 数据库会话
        
    Returns:
        包含access_token和token_type的OAuth2令牌响应
        
    Raises:
        HTTPException: 如果凭证无效
    """
    token = await AuthService.login(db, form_data.username, form_data.password)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码无效"
        )
    
    # 返回符合OAuth2标准的响应,用于Swagger自动授权
    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.post("/login-detail", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login_detail(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """用户登录并返回JWT令牌和用户详情。

    扩展的登录端点,返回完整的用户信息。

    如果是管理员账户登录，会自动检查并设置微软Edge-TTS作为默认朗读服务。

    Args:
        form_data: 来自OAuth2表单的用户名和密码
        db: 数据库会话

    Returns:
        JWT令牌和用户信息

    Raises:
        HTTPException: 如果凭证无效
    """
    token = await AuthService.login(db, form_data.username, form_data.password)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码无效"
        )

    # 获取用户信息
    user = await AuthService.get_user_by_username(db, form_data.username)

    # 如果是管理员账户，检查并设置默认TTS服务为微软Edge-TTS
    if user.role == "admin":
        # 检查用户设置
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        user_settings = result.scalars().first()

        settings = get_settings()
        need_commit = False

        if not user_settings:
            # 如果没有设置，创建新的用户设置
            user_settings = UserSettings(user_id=user.id)
            db.add(user_settings)
            need_commit = True

        if not user_settings.tts_service_name:
            # 如果没有设置TTS服务，设置为edge-tts
            user_settings.tts_service_name = "edge-tts"
            need_commit = True

        # 如果使用edge-tts但没有设置语音，设置默认英文语音
        if user_settings.tts_service_name == "edge-tts" and not user_settings.edge_tts_voice:
            user_settings.edge_tts_voice = settings.EDGE_TTS_DEFAULT_VOICE
            need_commit = True

        if need_commit:
            await db.commit()

    return LoginResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role
    )


@router.post("/activate", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def activate_user(
    activation: UserActivateRequest,
    db: AsyncSession = Depends(get_db)
):
    """使用邀请码激活用户账户并设置密码。
    
    Args:
        activation: 邀请码和新密码
        db: 数据库会话
        
    Returns:
        激活后的用户信息
        
    Raises:
        HTTPException: 如果激活失败
    """
    try:
        user = await AuthService.activate_user(
            db,
            activation.invitation_code,
            activation.password
        )
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息。
    
    Args:
        current_user: 当前已认证用户
    
    Returns:
        当前用户信息
    """
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    update_data: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新当前用户信息(仅用户名)。
    
    Args:
        update_data: 新的用户数据
        db: 数据库会话
        current_user: 当前已认证用户
        
    Returns:
        更新后的用户信息
        
    Raises:
        HTTPException: 如果用户名已被占用
    """
    try:
        updated_user = await AuthService.update_current_user(
            db, current_user, username=update_data.username
        )
        return UserResponse.model_validate(updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== 管理员用户管理端点 ====================

@router.post("/users", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateByAdmin,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """创建新用户并生成邀请码(仅限管理员)。
    
    Args:
        user_data: 新用户的用户名
        db: 数据库会话
        admin: 当前管理员用户
        
    Returns:
        创建的用户和邀请码
        
    Raises:
        HTTPException: 如果用户名已存在
    """
    try:
        user, invitation_code = await AuthService.create_user_by_admin(db, user_data.username)
        
        return UserCreateResponse(
            user=UserResponse.model_validate(user),
            invitation_code=invitation_code,
            invitation_expires=user.invitation_expires
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/users", response_model=list[UserDetailResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """获取所有用户(仅限管理员)。
    
    Args:
        skip: 跳过的记录数
        limit: 返回的最大记录数
        db: 数据库会话
        admin: 当前管理员用户
        
    Returns:
        用户列表
    """
    users = await AuthService.list_users(db, skip=skip, limit=limit)
    return [UserDetailResponse.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """获取用户详情(仅限管理员)。
    
    Args:
        user_id: 用户ID
        db: 数据库会话
        admin: 当前管理员用户
        
    Returns:
        用户详情
        
    Raises:
        HTTPException: 如果用户未找到
    """
    user = await AuthService.get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户未找到"
        )

    return UserDetailResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: int,
    update_data: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """更新用户信息(仅限管理员)。

    Args:
        user_id: 要更新的用户ID
        update_data: 新的用户数据
        db: 数据库会话
        admin: 当前管理员用户

    Returns:
        更新后的用户信息

    Raises:
        HTTPException: 如果用户未找到或更新失败
    """
    # 检查是否是默认管理员（admin账户是保留账户，禁止修改）
    target_user = await AuthService.get_user_by_id(db, user_id)
    if target_user and target_user.username == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能修改默认管理员账户"
        )

    # 检查是否是管理员自己（可以修改自己的用户名，但不能修改自己的角色）
    if admin.id == user_id:
        if update_data.role is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="不能修改自己的角色，请联系管理员！"
            )

    try:
        user = await AuthService.update_user_by_admin(
            db, user_id,
            username=update_data.username,
            role=update_data.role
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户未找到"
            )
        return UserDetailResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """删除用户(仅限管理员)。

    Args:
        user_id: 要删除的用户ID
        db: 数据库会话
        admin: 当前管理员用户

    Raises:
        HTTPException: 如果用户未找到或不能删除
    """
    try:
        user = await AuthService.delete_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户未找到"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    user_id: int,
    password_data: UpdatePasswordRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """重置用户密码(仅限管理员)。

    Args:
        user_id: 要重置密码的用户ID
        password_data: 新密码
        db: 数据库会话
        admin: 当前管理员用户

    Returns:
        成功消息

    Raises:
        HTTPException: 如果用户未找到或无权重置admin用户密码
    """
    # 获取目标用户信息
    target_user = await AuthService.get_user_by_id(db, user_id)
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户未找到"
        )
    
    # 检查是否是重置admin用户的密码
    if target_user.username == "admin":
        # 只有admin用户本人可以重置自己的密码
        if admin.username != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有admin用户可以重置admin用户的密码"
            )
    
    user = await AuthService.reset_password_by_admin(db, user_id, password_data.new_password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户未找到"
        )

    return {"message": "密码重置成功"}


@router.get("/users/{user_id}/invitation-code", response_model=UserDetailResponse)
async def get_user_invitation_code(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """获取指定未激活用户的邀请码(仅限管理员)。

    Args:
        user_id: 用户ID
        db: 数据库会话
        admin: 当前管理员用户

    Returns:
        未激活用户的邀请码信息

    Raises:
        HTTPException: 如果用户未找到或用户已激活
    """
    user = await AuthService.get_user_invitation_code(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户未找到或用户已激活"
        )

    return UserDetailResponse.model_validate(user)


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
async def change_current_user_password(
    password_data: UpdateCurrentUserPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """当前用户修改自己的密码。
    
    Args:
        password_data: 旧密码和新密码
        db: 数据库会话
        current_user: 当前已认证用户
        
    Returns:
        成功消息
        
    Raises:
        HTTPException: 如果旧密码不正确
    """
    try:
        await AuthService.update_current_user_password(
            db, current_user, 
            password_data.old_password, 
            password_data.new_password
        )
        return {"message": "密码修改成功"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
