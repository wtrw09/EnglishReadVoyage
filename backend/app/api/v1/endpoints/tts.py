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
    service_name: Optional[str] = None  # 可选，指定服务名称 'kokoro-tts', 'doubao-tts', 'siliconflow-tts', 'edge-tts', 'minimax-tts'
    # 硅基流动额外参数
    siliconflow_api_key: Optional[str] = None
    siliconflow_model: Optional[str] = None
    # MiniMax额外参数
    minimax_api_key: Optional[str] = None
    minimax_model: Optional[str] = None


@router.get("/", response_model=TTSResponse)
async def text_to_speech(
    text: str = Query(..., min_length=1, description="要转换为语音的文本"),
    voice: str = Query(
        default="bf_v0isabella",
        description="TTS语音ID（例如：'bf_v0isabella'、'bf_alice'）"
    ),
    service_name: str = Query(
        default=None,
        description="TTS服务名称：kokoro-tts, doubao-tts, siliconflow-tts, edge-tts"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    使用TTS将文本转换为语音（GET方式）。

    根据用户设置自动选择TTS服务，或使用service_name参数指定服务。

    Args:
        text: 要转换的文本
        voice: 要使用的语音ID
        service_name: 可选，指定TTS服务名称
        db: 数据库会话
        current_user: 当前已认证用户

    Returns:
        生成的音频文件URL

    Raises:
        HTTPException: 如果TTS服务失败返回500错误
    """
    try:
        # 获取用户设置
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == current_user.id))
        user_settings = result.scalars().first()
        default_config = get_default_tts_config()

        # 确定使用哪个服务
        actual_service_name = service_name or (user_settings.tts_service_name if user_settings else None) or default_config.get("service_name", "kokoro-tts")

        # 确定语音ID（如果用户使用的是edge-tts，使用edge_tts_voice）
        actual_voice = voice
        if actual_service_name == "edge-tts" and user_settings and user_settings.edge_tts_voice:
            actual_voice = user_settings.edge_tts_voice

        result = await tts_service.generate_speech(
            text,
            voice=actual_voice,
            service_name=actual_service_name
        )
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
        service_name = request.service_name or (user_settings.tts_service_name if user_settings else None) or settings.DEFAULT_TTS_SERVICE
        voice = None
        speed = 1.0
        doubao_app_id = None
        doubao_access_key = None
        doubao_resource_id = None
        siliconflow_api_key = None
        siliconflow_model = None
        minimax_api_key = None
        minimax_model = None

        if service_name == "kokoro-tts":
            # 使用 Kokoro 独立设置
            voice = user_settings.kokoro_voice if user_settings else None
            speed = user_settings.kokoro_speed if user_settings and user_settings.kokoro_speed is not None else default_config["kokoro_speed"]
        elif service_name == "siliconflow-tts":
            # 使用硅基流动独立设置（不支持语速调节）
            voice = user_settings.siliconflow_voice if user_settings else None
            speed = None  # 硅基流动不支持语速
            siliconflow_api_key = user_settings.siliconflow_api_key if user_settings else None
            siliconflow_model = user_settings.siliconflow_model if user_settings else None
        elif service_name == "edge-tts":
            # 使用 Edge-TTS 独立设置
            voice = user_settings.edge_tts_voice if user_settings else None
            speed = user_settings.edge_tts_speed if user_settings and user_settings.edge_tts_speed is not None else default_config.get("edge_tts_speed", 1.0)
        elif service_name == "minimax-tts":
            # 使用 MiniMax 独立设置
            voice = user_settings.minimax_voice if user_settings else None
            speed = user_settings.minimax_speed if user_settings and user_settings.minimax_speed is not None else default_config.get("minimax_speed", 1.0)
            minimax_api_key = user_settings.minimax_api_key if user_settings else None
            minimax_model = user_settings.minimax_model if user_settings else None
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
        # 如果请求中指定了speed，使用请求的speed（硅基流动不支持）
        if request.speed is not None and service_name not in ("siliconflow-tts",):
            speed = request.speed
        # 如果请求中指定了硅基流动参数，使用请求中的
        if request.siliconflow_api_key:
            siliconflow_api_key = request.siliconflow_api_key
        if request.siliconflow_model:
            siliconflow_model = request.siliconflow_model
        # 如果请求中指定了MiniMax参数，使用请求中的
        if request.minimax_api_key:
            minimax_api_key = request.minimax_api_key
        if request.minimax_model:
            minimax_model = request.minimax_model

        print(f"TTS POST请求: service={service_name}, text={request.text[:50]}..., voice={voice}, speed={speed}")

        result = await tts_service.generate_speech(
            text=request.text,
            voice=voice,
            service_name=service_name,
            doubao_app_id=doubao_app_id,
            doubao_access_key=doubao_access_key,
            doubao_resource_id=doubao_resource_id,
            siliconflow_api_key=siliconflow_api_key,
            siliconflow_model=siliconflow_model,
            minimax_api_key=minimax_api_key,
            minimax_model=minimax_model,
            speed=speed if service_name != "siliconflow-tts" else None
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
