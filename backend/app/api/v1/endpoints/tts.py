"""TTS语音合成API端点。"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.tts import TTSResponse
from app.services.tts_service import tts_service
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User, UserSettings
from app.core.config import get_settings
from app.api.v1.endpoints.settings import get_default_tts_config


router = APIRouter()


class TTSRequest(BaseModel):
    """TTS请求体"""
    text: str
    voice: str = "bf_v0isabella"
    speed: float = 1.0
    service_name: Optional[str] = None  # 可选，指定服务名称 'kokoro-tts' 或 'doubao-tts'


@router.get("/", response_model=TTSResponse)
async def text_to_speech(
    text: str = Query(..., min_length=1, description="要转换为语音的文本"),
    voice: str = Query(
        default="bf_v0isabella",
        description="TTS语音ID（例如：'bf_v0isabella'、'bf_alice'）"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    使用Kokoro TTS将文本转换为语音（GET方式）。

    Args:
        text: 要转换的文本
        voice: 要使用的语音ID
        db: 数据库会话
        current_user: 当前已认证用户

    Returns:
        生成的音频文件URL

    Raises:
        HTTPException: 如果TTS服务失败返回500错误
    """
    try:
        result = await tts_service.generate_speech(text, voice)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS生成失败：{str(e)}"
        )


@router.post("/", response_model=TTSResponse)
async def text_to_speech_post(
    request: TTSRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    使用TTS将文本转换为语音（POST方式，支持更长的文本和语速设置）。
    根据用户设置自动选择Kokoro或豆包TTS服务。

    Args:
        request: 包含text、voice、speed的请求体
        db: 数据库会话
        current_user: 当前已认证用户

    Returns:
        生成的音频文件URL

    Raises:
        HTTPException: 如果TTS服务失败返回500错误
    """
    import traceback
    try:
        # 获取用户设置
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == current_user.id))
        user_settings = result.scalars().first()
        default_config = get_default_tts_config()

        # 确定使用哪个服务及其配置
        # 优先使用请求中指定的服务名称，其次是用户设置，最后是默认值
        service_name = request.service_name or (user_settings.tts_service_name if user_settings else None) or "kokoro-tts"
        voice = None
        speed = 1.0
        doubao_app_id = None
        doubao_access_key = None
        doubao_resource_id = None

        if service_name == "kokoro-tts":
            # 使用 Kokoro 独立设置
            voice = user_settings.kokoro_voice if user_settings else None
            speed = user_settings.kokoro_speed if user_settings and user_settings.kokoro_speed is not None else default_config["kokoro_speed"]
        else:
            # 使用豆包独立设置
            voice = user_settings.doubao_voice if user_settings else None
            speed = user_settings.doubao_speed if user_settings and user_settings.doubao_speed is not None else default_config["doubao_speed"]
            doubao_app_id = user_settings.doubao_app_id if user_settings else None
            doubao_access_key = user_settings.doubao_access_key if user_settings else None
            doubao_resource_id = user_settings.doubao_resource_id if user_settings else None

        # 如果请求中指定了voice，使用请求的voice
        if request.voice:
            voice = request.voice
        # 如果请求中指定了speed，使用请求的speed
        if request.speed is not None:
            speed = request.speed

        print(f"TTS POST请求: service={service_name}, text={request.text[:50]}..., voice={voice}, speed={speed}")

        result = await tts_service.generate_speech(
            text=request.text,
            voice=voice,
            service_name=service_name,
            doubao_app_id=doubao_app_id,
            doubao_access_key=doubao_access_key,
            doubao_resource_id=doubao_resource_id,
            speed=speed
        )
        print(f"TTS生成成功: {result}")
        return result
    except Exception as e:
        error_detail = f"TTS生成失败：{str(e)}"
        print(f"TTS错误: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )


@router.get("/health")
async def tts_health_check():
    """
    检查TTS服务是否可用。

    Returns:
        服务状态信息
    """
    from app.core.config import get_settings
    import httpx

    settings = get_settings()
    health_url = settings.KOKORO_API_URL.replace('/v1/audio/speech', '/health')

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)
            if response.status_code == 200:
                return {"status": "ok", "message": "TTS服务正常运行"}
            else:
                return {"status": "error", "message": f"TTS服务返回错误: {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"无法连接到TTS服务: {str(e)}"}
