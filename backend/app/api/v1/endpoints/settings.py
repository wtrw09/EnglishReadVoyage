"""用户设置API端点。"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User, UserSettings
from app.schemas.dictionary import (
    UserSettingsResponse,
    UserDictionarySettings,
    UserTtsSettings,
    UserPhoneticSettings,
    UpdateDictionarySettingsRequest,
    UpdatePhoneticSettingsRequest,
    UpdateTtsSettingsRequest
)

# 全局缓存默认TTS配置（从.env读取）
_default_tts_config = None

def get_default_tts_config():
    """获取默认TTS配置（从.env文件）"""
    global _default_tts_config
    if _default_tts_config is None:
        settings = get_settings()
        _default_tts_config = {
            "service_name": "kokoro-tts",
            # Kokoro TTS 默认配置
            "kokoro_voice": settings.KOKORO_DEFAULT_VOICE,
            "kokoro_speed": settings.KOKORO_DEFAULT_SPEED,
            "kokoro_api_url": settings.KOKORO_API_URL,
            # 豆包 TTS 默认配置
            "doubao_voice": settings.DOUBAO_DEFAULT_VOICE,
            "doubao_speed": settings.DOUBAO_DEFAULT_SPEED,
            "doubao_app_id": None,
            "doubao_access_key": None,
            "doubao_resource_id": settings.DOUBAO_DEFAULT_RESOURCE_ID
        }
    return _default_tts_config

router = APIRouter()


async def get_or_create_user_settings(db: AsyncSession, user_id: int) -> UserSettings:
    """获取或创建用户设置"""
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalars().first()
    if not settings:
        settings = UserSettings(user_id=user_id, dictionary_source="local")
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.get("/", response_model=UserSettingsResponse)
async def get_user_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的设置。

    返回用户的词典设置和朗读设置。
    如果用户没有设置记录，会自动创建一个默认配置（使用.env中的默认值）。
    """
    settings = await get_or_create_user_settings(db, current_user.id)
    default_config = get_default_tts_config()

    return UserSettingsResponse(
        dictionary=UserDictionarySettings(
            dictionary_source=settings.dictionary_source
        ),
        tts=UserTtsSettings(
            service_name=settings.tts_service_name or default_config["service_name"],
            # Kokoro TTS 设置
            kokoro_voice=settings.kokoro_voice or default_config.get("kokoro_voice"),
            kokoro_speed=settings.kokoro_speed if settings.kokoro_speed is not None else default_config.get("kokoro_speed", 1.0),
            kokoro_api_url=settings.kokoro_api_url or default_config.get("kokoro_api_url"),
            # 豆包TTS设置
            doubao_voice=settings.doubao_voice or default_config.get("doubao_voice"),
            doubao_speed=settings.doubao_speed if settings.doubao_speed is not None else default_config.get("doubao_speed", 1.0),
            doubao_app_id=settings.doubao_app_id or default_config.get("doubao_app_id"),
            doubao_access_key=settings.doubao_access_key or default_config.get("doubao_access_key"),
            doubao_resource_id=settings.doubao_resource_id or default_config.get("doubao_resource_id")
        ),
        phonetic=UserPhoneticSettings(
            accent=settings.phonetic_accent or "uk"
        )
    )


@router.put("/dictionary", response_model=UserDictionarySettings)
async def update_dictionary_settings(
    request: UpdateDictionarySettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新用户的词典设置。
    
    Args:
        request: 包含 dictionary_source 的请求体，值为 'local' 或 'api'
        
    Returns:
        更新后的词典设置
        
    Raises:
        HTTPException: 如果 dictionary_source 值无效
    """
    if request.dictionary_source not in ["local", "api"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="词典来源必须是 'local' 或 'api'"
        )
    
    settings = await get_or_create_user_settings(db, current_user.id)
    settings.dictionary_source = request.dictionary_source
    await db.commit()
    await db.refresh(settings)
    
    return UserDictionarySettings(
        dictionary_source=settings.dictionary_source
    )


@router.put("/phonetic", response_model=UserPhoneticSettings)
async def update_phonetic_settings(
    request: UpdatePhoneticSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新用户的音标设置。
    
    Args:
        request: 包含 accent 的请求体，值为 'uk' 或 'us'
        
    Returns:
        更新后的音标设置
        
    Raises:
        HTTPException: 如果 accent 值无效
    """
    if request.accent not in ["uk", "us"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="音标口音必须是 'uk'（英式）或 'us'（美式）"
        )
    
    settings = await get_or_create_user_settings(db, current_user.id)
    settings.phonetic_accent = request.accent
    await db.commit()
    await db.refresh(settings)
    
    return UserPhoneticSettings(
        accent=settings.phonetic_accent
    )


@router.put("/tts", response_model=UserTtsSettings)
async def update_tts_settings(
    request: UpdateTtsSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新用户的朗读设置。

    Args:
        request: 包含 service_name, voice, speed, api_url 的请求体

    Returns:
        更新后的朗读设置
    """
    settings = await get_or_create_user_settings(db, current_user.id)

    # 更新服务名称
    if request.service_name is not None:
        settings.tts_service_name = request.service_name.strip() or "kokoro-tts"

    # 更新 Kokoro TTS 设置
    if request.kokoro_voice is not None:
        settings.kokoro_voice = request.kokoro_voice.strip() if request.kokoro_voice.strip() else None

    if request.kokoro_speed is not None:
        if not (0.5 <= request.kokoro_speed <= 2.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kokoro 朗读速度必须在 0.5 到 2.0 之间"
            )
        settings.kokoro_speed = request.kokoro_speed

    if request.kokoro_api_url is not None:
        request.kokoro_api_url = request.kokoro_api_url.strip()
        if request.kokoro_api_url and not (request.kokoro_api_url.startswith('http://') or request.kokoro_api_url.startswith('https://')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kokoro 服务地址必须以 http:// 或 https:// 开头"
            )
        settings.kokoro_api_url = request.kokoro_api_url if request.kokoro_api_url else None

    # 更新豆包 TTS 设置
    if request.doubao_voice is not None:
        settings.doubao_voice = request.doubao_voice.strip() if request.doubao_voice.strip() else None

    if request.doubao_speed is not None:
        if not (0.5 <= request.doubao_speed <= 2.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="豆包朗读速度必须在 0.5 到 2.0 之间"
            )
        settings.doubao_speed = request.doubao_speed

    if request.doubao_app_id is not None:
        settings.doubao_app_id = request.doubao_app_id.strip() if request.doubao_app_id.strip() else None
    if request.doubao_access_key is not None:
        settings.doubao_access_key = request.doubao_access_key.strip() if request.doubao_access_key.strip() else None
    if request.doubao_resource_id is not None:
        settings.doubao_resource_id = request.doubao_resource_id.strip() if request.doubao_resource_id.strip() else None

    await db.commit()
    await db.refresh(settings)

    default_config = get_default_tts_config()
    return UserTtsSettings(
        service_name=settings.tts_service_name or default_config["service_name"],
        # Kokoro TTS 设置
        kokoro_voice=settings.kokoro_voice or default_config.get("kokoro_voice"),
        kokoro_speed=settings.kokoro_speed if settings.kokoro_speed is not None else default_config.get("kokoro_speed", 1.0),
        kokoro_api_url=settings.kokoro_api_url or default_config.get("kokoro_api_url"),
        # 豆包TTS设置
        doubao_voice=settings.doubao_voice or default_config.get("doubao_voice"),
        doubao_speed=settings.doubao_speed if settings.doubao_speed is not None else default_config.get("doubao_speed", 1.0),
        doubao_app_id=settings.doubao_app_id or default_config.get("doubao_app_id"),
        doubao_access_key=settings.doubao_access_key or default_config.get("doubao_access_key"),
        doubao_resource_id=settings.doubao_resource_id or default_config.get("doubao_resource_id")
    )


@router.get("/tts/voices")
async def get_tts_voices(
    current_user: User = Depends(get_current_user)
):
    """
    获取可用的TTS语音列表。

    从Kokoro TTS服务获取支持的语音列表。

    Returns:
        语音列表，包含语音ID和名称
    """
    settings = get_settings()
    tts_api_url = settings.KOKORO_API_URL.replace('/v1/audio/speech', '/v1/audio/voices')

    # 语音ID到显示名称的映射（仅美式英语和英式英语）- 英式在前
    voice_name_map = {
        # 英式英语 - 女声
        "bf_alice": "英式 女声 - Alice",
        "bf_emma": "英式 女声 - Emma",
        "bf_lily": "英式 女声 - Lily",
        "bf_v0emma": "英式 女声 - V0Emma",
        "bf_v0isabella": "英式 女声 - V0Isabella",
        # 英式英语 - 男声
        "bm_daniel": "英式 男声 - Daniel",
        "bm_fable": "英式 男声 - Fable",
        "bm_george": "英式 男声 - George",
        "bm_lewis": "英式 男声 - Lewis",
        "bm_v0george": "英式 男声 - V0George",
        "bm_v0lewis": "英式 男声 - V0Lewis",
        # 美式英语 - 女声
        "af_alloy": "美式 女声 - Alloy",
        "af_aoede": "美式 女声 - Aoede",
        "af_bella": "美式 女声 - Bella",
        "af_heart": "美式 女声 - Heart",
        "af_jadzia": "美式 女声 - Jadzia",
        "af_jessica": "美式 女声 - Jessica",
        "af_kore": "美式 女声 - Kore",
        "af_nicole": "美式 女声 - Nicole",
        "af_nova": "美式 女声 - Nova",
        "af_river": "美式 女声 - River",
        "af_sarah": "美式 女声 - Sarah",
        "af_sky": "美式 女声 - Sky",
        "af_v0": "美式 女声 - V0",
        "af_v0bella": "美式 女声 - V0Bella",
        "af_v0irulan": "美式 女声 - V0Irulan",
        "af_v0nicole": "美式 女声 - V0Nicole",
        "af_v0sarah": "美式 女声 - V0Sarah",
        "af_v0sky": "美式 女声 - V0Sky",
        # 美式英语 - 男声
        "am_adam": "美式 男声 - Adam",
        "am_echo": "美式 男声 - Echo",
        "am_eric": "美式 男声 - Eric",
        "am_fenrir": "美式 男声 - Fenrir",
        "am_liam": "美式 男声 - Liam",
        "am_michael": "美式 男声 - Michael",
        "am_onyx": "美式 男声 - Onyx",
        "am_puck": "美式 男声 - Puck",
        "am_santa": "美式 男声 - Santa",
        "am_v0adam": "美式 男声 - V0Adam",
        "am_v0gurney": "美式 男声 - V0Gurney",
        "am_v0michael": "美式 男声 - V0Michael",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(tts_api_url)
            print(f"TTS voices API响应: status={response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"TTS voices数据类型: {type(data)}, 数据: {data[:5] if isinstance(data, list) else data}")
                # Kokoro 可能返回字符串数组或对象数组
                if isinstance(data, list):
                    # 字符串数组格式: ['af_alloy', 'af_aoede', ...]
                    # 按照voice_name_map的顺序（英式在前）构建结果
                    voices = []
                    for voice_id, voice_name in voice_name_map.items():
                        if voice_id in data:
                            voices.append({"id": voice_id, "name": voice_name})
                    print(f"转换后的voices: {voices[:3]}")
                    return {"voices": voices}
                elif isinstance(data, dict) and "voices" in data:
                    # 检查voices是否是字符串数组
                    voices_data = data["voices"]
                    if voices_data and isinstance(voices_data[0], str):
                        # 字符串数组格式，需要转换
                        # 按照voice_name_map的顺序（英式在前）构建结果
                        voices = []
                        for voice_id, voice_name in voice_name_map.items():
                            if voice_id in voices_data:
                                voices.append({"id": voice_id, "name": voice_name})
                        print(f"从dict转换后的voices: {voices[:3]}")
                        return {"voices": voices}
                    else:
                        # 已经是对象数组格式
                        return data
                else:
                    return {"voices": []}
            else:
                print(f"TTS voices API错误: {response.text}")
                return {"voices": []}
    except Exception as e:
        # 如果无法连接到TTS服务，返回默认语音列表
        default_voices = [
            {"id": k, "name": v}
            for k, v in voice_name_map.items()
        ]
        return {"voices": default_voices}
