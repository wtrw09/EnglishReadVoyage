"""用户设置API端点。"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import json
from app.core.config import get_settings
from app.core.database import get_db
from app.api.dependencies import get_current_user, get_current_admin
from app.models.database_models import User, UserSettings
from app.schemas.dictionary import (
    UserSettingsResponse,
    UserDictionarySettings,
    UserTtsSettings,
    UserPhoneticSettings,
    UserUiSettings,
    UpdateDictionarySettingsRequest,
    UpdatePhoneticSettingsRequest,
    UpdateTtsSettingsRequest,
    UpdateUiSettingsRequest
)

# 全局缓存默认TTS配置（从.env读取）
_default_tts_config = None

def get_default_tts_config():
    """获取默认TTS配置（从.env文件）"""
    global _default_tts_config
    if _default_tts_config is None:
        settings = get_settings()
        _default_tts_config = {
            "service_name": "edge-tts",
            # Kokoro TTS 默认配置
            "kokoro_voice": settings.KOKORO_DEFAULT_VOICE,
            "kokoro_voice_zh": settings.KOKORO_DEFAULT_VOICE_ZH,
            "kokoro_speed": settings.KOKORO_DEFAULT_SPEED,
            "kokoro_api_url": settings.KOKORO_API_URL,
            # 豆包 TTS 默认配置
            "doubao_voice": settings.DOUBAO_DEFAULT_VOICE,
            "doubao_voice_zh": settings.DOUBAO_DEFAULT_VOICE_ZH,
            "doubao_speed": settings.DOUBAO_DEFAULT_SPEED,
            "doubao_app_id": None,
            "doubao_access_key": None,
            "doubao_resource_id": settings.DOUBAO_DEFAULT_RESOURCE_ID,
            # 硅基流动 TTS 默认配置
            "siliconflow_api_key": None,
            "siliconflow_model": settings.SILICONFLOW_DEFAULT_MODEL,
            "siliconflow_voice": settings.SILICONFLOW_DEFAULT_VOICE,
            "siliconflow_voice_zh": settings.SILICONFLOW_DEFAULT_VOICE,  # 硅基流动音色不区分中英文
            # Edge-TTS 默认配置
            "edge_tts_voice": settings.EDGE_TTS_DEFAULT_VOICE,
            "edge_tts_voice_zh": settings.EDGE_TTS_DEFAULT_VOICE_ZH,
            "edge_tts_speed": settings.EDGE_TTS_DEFAULT_SPEED,
            # MiniMax TTS 默认配置
            "minimax_api_key": None,
            "minimax_model": settings.MINIMAX_DEFAULT_MODEL,
            "minimax_voice": settings.MINIMAX_DEFAULT_VOICE,
            "minimax_voice_zh": settings.MINIMAX_DEFAULT_VOICE_ZH,
            "minimax_speed": settings.MINIMAX_DEFAULT_SPEED,
            # Azure TTS 默认配置
            "azure_subscription_key": None,
            "azure_region": settings.AZURE_TTS_REGION or None,
            "azure_voice": settings.AZURE_TTS_DEFAULT_VOICE,
            "azure_voice_zh": settings.AZURE_TTS_DEFAULT_VOICE_ZH,
            "azure_speed": settings.AZURE_TTS_DEFAULT_SPEED
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

    # 解析隐藏已读书籍状态
    hide_read_books_map = {}
    if settings.hide_read_books_map:
        try:
            hide_read_books_map = json.loads(settings.hide_read_books_map)
            # 将字符串键转换为整数键
            hide_read_books_map = {int(k): v for k, v in hide_read_books_map.items()}
        except (json.JSONDecodeError, ValueError):
            hide_read_books_map = {}

    # 构建 TTS 响应（普通用户返回空）
    tts_response = None
    if current_user.role == "admin":
        tts_response = UserTtsSettings(
            service_name=settings.tts_service_name or default_config["service_name"],
            # Kokoro TTS 设置
            kokoro_voice=settings.kokoro_voice or default_config.get("kokoro_voice"),
            kokoro_voice_zh=settings.kokoro_voice_zh or default_config.get("kokoro_voice_zh"),
            kokoro_speed=settings.kokoro_speed if settings.kokoro_speed is not None else default_config.get("kokoro_speed", 1.0),
            kokoro_api_url=settings.kokoro_api_url or default_config.get("kokoro_api_url"),
            # 豆包TTS设置
            doubao_voice=settings.doubao_voice or default_config.get("doubao_voice"),
            doubao_voice_zh=settings.doubao_voice_zh or default_config.get("doubao_voice_zh"),
            doubao_speed=settings.doubao_speed if settings.doubao_speed is not None else default_config.get("doubao_speed", 1.0),
            doubao_app_id=settings.doubao_app_id or default_config.get("doubao_app_id"),
            doubao_access_key=settings.doubao_access_key or default_config.get("doubao_access_key"),
            doubao_resource_id=settings.doubao_resource_id or default_config.get("doubao_resource_id"),
            # 硅基流动TTS设置
            siliconflow_api_key=settings.siliconflow_api_key or default_config.get("siliconflow_api_key"),
            siliconflow_model=settings.siliconflow_model or default_config.get("siliconflow_model"),
            siliconflow_voice=settings.siliconflow_voice or default_config.get("siliconflow_voice"),
            siliconflow_voice_zh=settings.siliconflow_voice_zh or default_config.get("siliconflow_voice_zh"),
            # Edge-TTS设置
            edge_tts_voice=settings.edge_tts_voice or default_config.get("edge_tts_voice"),
            edge_tts_voice_zh=settings.edge_tts_voice_zh or default_config.get("edge_tts_voice_zh"),
            edge_tts_speed=settings.edge_tts_speed if settings.edge_tts_speed is not None else default_config.get("edge_tts_speed", 1.0),
            # MiniMax TTS设置
            minimax_api_key=settings.minimax_api_key or default_config.get("minimax_api_key"),
            minimax_model=settings.minimax_model or default_config.get("minimax_model"),
            minimax_voice=settings.minimax_voice or default_config.get("minimax_voice"),
            minimax_voice_zh=settings.minimax_voice_zh or default_config.get("minimax_voice_zh"),
            minimax_speed=settings.minimax_speed if settings.minimax_speed is not None else default_config.get("minimax_speed", 1.0),
            # Azure TTS设置
            azure_subscription_key=settings.azure_subscription_key or default_config.get("azure_subscription_key"),
            azure_region=settings.azure_region or default_config.get("azure_region"),
            azure_voice=settings.azure_voice or default_config.get("azure_voice"),
            azure_voice_zh=settings.azure_voice_zh or default_config.get("azure_voice_zh"),
            azure_speed=settings.azure_speed if settings.azure_speed is not None else default_config.get("azure_speed", 1.0)
        )

    return UserSettingsResponse(
        dictionary=UserDictionarySettings(
            dictionary_source=settings.dictionary_source
        ),
        tts=tts_response,
        phonetic=UserPhoneticSettings(
            accent=settings.phonetic_accent or "uk"
        ),
        ui=UserUiSettings(
            hide_read_books_map=hide_read_books_map
        )
    )


@router.get("/dictionary", response_model=UserDictionarySettings)
async def get_dictionary_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户的词典设置（轻量级API）。

    Returns:
        用户的词典设置
    """
    settings = await get_or_create_user_settings(db, current_user.id)
    return UserDictionarySettings(
        dictionary_source=settings.dictionary_source
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
    current_user: User = Depends(get_current_admin)  # 只有管理员可以修改朗读设置
):
    """
    更新用户的朗读设置（仅限管理员）。

    Args:
        request: 包含 service_name, voice, speed, api_url 的请求体

    Returns:
        更新后的朗读设置

    Raises:
        HTTPException: 403 如果不是管理员
    """
    settings = await get_or_create_user_settings(db, current_user.id)

    # 更新服务名称
    if request.service_name is not None:
        settings.tts_service_name = request.service_name.strip() or "edge-tts"

    # 更新 Kokoro TTS 设置
    if request.kokoro_voice is not None:
        settings.kokoro_voice = request.kokoro_voice.strip() if request.kokoro_voice.strip() else None

    if request.kokoro_voice_zh is not None:
        settings.kokoro_voice_zh = request.kokoro_voice_zh.strip() if request.kokoro_voice_zh.strip() else None

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

    if request.doubao_voice_zh is not None:
        settings.doubao_voice_zh = request.doubao_voice_zh.strip() if request.doubao_voice_zh.strip() else None

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

    # 更新硅基流动 TTS 设置
    if request.siliconflow_api_key is not None:
        settings.siliconflow_api_key = request.siliconflow_api_key.strip() if request.siliconflow_api_key.strip() else None
    if request.siliconflow_model is not None:
        settings.siliconflow_model = request.siliconflow_model.strip() if request.siliconflow_model.strip() else None
    if request.siliconflow_voice is not None:
        settings.siliconflow_voice = request.siliconflow_voice.strip() if request.siliconflow_voice.strip() else None
    if request.siliconflow_voice_zh is not None:
        settings.siliconflow_voice_zh = request.siliconflow_voice_zh.strip() if request.siliconflow_voice_zh.strip() else None

    # 更新 Edge-TTS 设置
    if request.edge_tts_voice is not None:
        settings.edge_tts_voice = request.edge_tts_voice.strip() if request.edge_tts_voice.strip() else None
    if request.edge_tts_voice_zh is not None:
        settings.edge_tts_voice_zh = request.edge_tts_voice_zh.strip() if request.edge_tts_voice_zh.strip() else None
    if request.edge_tts_speed is not None:
        if not (0.5 <= request.edge_tts_speed <= 2.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Edge-TTS 朗读速度必须在 0.5 到 2.0 之间"
            )
        settings.edge_tts_speed = request.edge_tts_speed

    # 更新 MiniMax TTS 设置
    if request.minimax_api_key is not None:
        settings.minimax_api_key = request.minimax_api_key.strip() if request.minimax_api_key.strip() else None
    if request.minimax_model is not None:
        settings.minimax_model = request.minimax_model.strip() if request.minimax_model.strip() else None
    if request.minimax_voice is not None:
        settings.minimax_voice = request.minimax_voice.strip() if request.minimax_voice.strip() else None
    if request.minimax_voice_zh is not None:
        settings.minimax_voice_zh = request.minimax_voice_zh.strip() if request.minimax_voice_zh.strip() else None
    if request.minimax_speed is not None:
        if not (0.25 <= request.minimax_speed <= 4.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MiniMax 朗读速度必须在 0.25 到 4.0 之间"
            )
        settings.minimax_speed = request.minimax_speed

    # 更新 Azure TTS 设置
    if request.azure_subscription_key is not None:
        settings.azure_subscription_key = request.azure_subscription_key.strip() if request.azure_subscription_key.strip() else None
    if request.azure_region is not None:
        settings.azure_region = request.azure_region.strip() if request.azure_region.strip() else None
    if request.azure_voice is not None:
        settings.azure_voice = request.azure_voice.strip() if request.azure_voice.strip() else None
    if request.azure_voice_zh is not None:
        settings.azure_voice_zh = request.azure_voice_zh.strip() if request.azure_voice_zh.strip() else None
    if request.azure_speed is not None:
        if not (0.5 <= request.azure_speed <= 2.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Azure 朗读速度必须在 0.5 到 2.0 之间"
            )
        settings.azure_speed = request.azure_speed

    await db.commit()
    await db.refresh(settings)

    default_config = get_default_tts_config()
    return UserTtsSettings(
        service_name=settings.tts_service_name or default_config["service_name"],
        # Kokoro TTS 设置
        kokoro_voice=settings.kokoro_voice or default_config.get("kokoro_voice"),
        kokoro_voice_zh=settings.kokoro_voice_zh or default_config.get("kokoro_voice_zh"),
        kokoro_speed=settings.kokoro_speed if settings.kokoro_speed is not None else default_config.get("kokoro_speed", 1.0),
        kokoro_api_url=settings.kokoro_api_url or default_config.get("kokoro_api_url"),
        # 豆包TTS设置
        doubao_voice=settings.doubao_voice or default_config.get("doubao_voice"),
        doubao_voice_zh=settings.doubao_voice_zh or default_config.get("doubao_voice_zh"),
        doubao_speed=settings.doubao_speed if settings.doubao_speed is not None else default_config.get("doubao_speed", 1.0),
        doubao_app_id=settings.doubao_app_id or default_config.get("doubao_app_id"),
        doubao_access_key=settings.doubao_access_key or default_config.get("doubao_access_key"),
        doubao_resource_id=settings.doubao_resource_id or default_config.get("doubao_resource_id"),
        # 硅基流动TTS设置
        siliconflow_api_key=settings.siliconflow_api_key or default_config.get("siliconflow_api_key"),
        siliconflow_model=settings.siliconflow_model or default_config.get("siliconflow_model"),
        siliconflow_voice=settings.siliconflow_voice or default_config.get("siliconflow_voice"),
        siliconflow_voice_zh=settings.siliconflow_voice_zh or default_config.get("siliconflow_voice_zh"),
        # Edge-TTS设置
        edge_tts_voice=settings.edge_tts_voice or default_config.get("edge_tts_voice"),
        edge_tts_voice_zh=settings.edge_tts_voice_zh or default_config.get("edge_tts_voice_zh"),
        edge_tts_speed=settings.edge_tts_speed if settings.edge_tts_speed is not None else default_config.get("edge_tts_speed", 1.0),
        # MiniMax TTS设置
        minimax_api_key=settings.minimax_api_key or default_config.get("minimax_api_key"),
        minimax_model=settings.minimax_model or default_config.get("minimax_model"),
        minimax_voice=settings.minimax_voice or default_config.get("minimax_voice"),
        minimax_voice_zh=settings.minimax_voice_zh or default_config.get("minimax_voice_zh"),
        minimax_speed=settings.minimax_speed if settings.minimax_speed is not None else default_config.get("minimax_speed", 1.0),
        # Azure TTS设置
        azure_subscription_key=settings.azure_subscription_key or default_config.get("azure_subscription_key"),
        azure_region=settings.azure_region or default_config.get("azure_region"),
        azure_voice=settings.azure_voice or default_config.get("azure_voice"),
        azure_voice_zh=settings.azure_voice_zh or default_config.get("azure_voice_zh"),
        azure_speed=settings.azure_speed if settings.azure_speed is not None else default_config.get("azure_speed", 1.0)
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


@router.get("/tts/kokoro/voices/zh")
async def get_kokoro_voices_zh(
    current_user: User = Depends(get_current_user)
):
    """
    获取Kokoro TTS可用的中文语音列表。

    从Kokoro TTS服务获取支持的语音列表，筛选出中文语音。

    Returns:
        中文语音列表
    """
    settings = get_settings()
    tts_api_url = settings.KOKORO_API_URL.replace('/v1/audio/speech', '/v1/audio/voices')

    # 中文语音ID到显示名称的映射
    voice_name_map_zh = {
        # 中文女声
        "zf_xiaobei": "中文 女声 - 小贝",
        "zf_xiaoni": "中文 女声 - 小妮",
        "zf_xiaoxiao": "中文 女声 - 晓晓",
        "zf_xiaoyi": "中文 女声 - 小艺",
        # 中文男声
        "zm_yunjian": "中文 男声 - 云健",
        "zm_yunxi": "中文 男声 - 云希",
        "zm_yunxia": "中文 男声 - 云夏",
        "zm_yunyang": "中文 男声 - 云扬",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(tts_api_url)
            if response.status_code == 200:
                data = response.json()
                # Kokoro 可能返回字符串数组或对象数组
                if isinstance(data, list):
                    all_voices = data
                elif isinstance(data, dict) and "voices" in data:
                    all_voices = data["voices"]
                else:
                    all_voices = []

                # 筛选中文音色 (zf_, zm_ 开头)
                voices = []
                for voice_id, voice_name in voice_name_map_zh.items():
                    if voice_id in all_voices:
                        voices.append({"id": voice_id, "name": voice_name})

                # 如果映射中的音色不在返回中，直接筛选 zf_, zm_ 开头的
                if not voices:
                    for voice_id in all_voices:
                        if isinstance(voice_id, str) and (voice_id.startswith('zf_') or voice_id.startswith('zm_')):
                            # 确定性别
                            gender = "女声" if voice_id.startswith('zf_') else "男声"
                            # 提取名称
                            name = voice_id.split('_')[-1] if '_' in voice_id else voice_id
                            voices.append({"id": voice_id, "name": f"中文 {gender} - {name}"})

                return {"voices": voices}
            else:
                return {"voices": []}
    except Exception as e:
        # 如果无法连接到TTS服务，返回默认中文语音列表
        default_voices = [
            {"id": k, "name": v}
            for k, v in voice_name_map_zh.items()
        ]
        return {"voices": default_voices}


@router.put("/ui", response_model=UserUiSettings)
async def update_ui_settings(
    request: UpdateUiSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新用户的界面设置。

    Args:
        request: 包含 hide_read_books_map 的请求体

    Returns:
        更新后的界面设置
    """
    settings = await get_or_create_user_settings(db, current_user.id)

    if request.hide_read_books_map is not None:
        settings.hide_read_books_map = json.dumps(request.hide_read_books_map)

    await db.commit()
    await db.refresh(settings)

    # 解析返回
    hide_read_books_map = {}
    if settings.hide_read_books_map:
        try:
            hide_read_books_map = json.loads(settings.hide_read_books_map)
            hide_read_books_map = {int(k): v for k, v in hide_read_books_map.items()}
        except (json.JSONDecodeError, ValueError):
            hide_read_books_map = {}

    return UserUiSettings(
        hide_read_books_map=hide_read_books_map
    )


@router.get("/tts/siliconflow/voices")
async def get_siliconflow_voices(
    current_user: User = Depends(get_current_user)
):
    """
    获取硅基流动可用的模型和语音列表。

    返回固定的模型和语音类型列表。

    Returns:
        模型列表和语音列表
    """
    # 硅基流动支持的模型列表
    models = [
        {"id": "fnlp/MOSS-TTSD-v0.5", "name": "MOSS TTSD v0.5"},
        {"id": "FunAudioLLM/CosyVoice2-0.5B", "name": "CosyVoice2 0.5B"},
        {"id": "IndexTeam/IndexTTS-2", "name": "IndexTTS 2"}
    ]
    
    # 硅基流动支持的语音类型列表
    voices = [
        {"id": "anna", "name": "Anna"},
        {"id": "alex", "name": "Alex"},
        {"id": "bella", "name": "Bella"},
        {"id": "benjiamin", "name": "Benjamin"},
        {"id": "charles", "name": "Charles"},
        {"id": "claire", "name": "Claire"},
        {"id": "david", "name": "David"},
        {"id": "diana", "name": "Diana"}
    ]
    
    return {"models": models, "voices": voices}


@router.get("/tts/edge/voices")
async def get_edge_tts_voices(
    current_user: User = Depends(get_current_user)
):
    """
    获取Edge-TTS可用的语音列表。

    动态调用 edge-tts --list-voices 命令获取语音列表，
    过滤出英语语音返回给前端。

    Returns:
        语音列表
    """
    import subprocess
    import json
    
    # 地区名称映射
    region_names = {
        "en-US": "美式英语",
        "en-GB": "英式英语",
    }
    
    # 性别名称映射
    gender_names = {
        "Female": "女声",
        "Male": "男声",
    }
    
    try:
        # 调用 edge-tts --list-voices 获取语音列表
        result = subprocess.run(
            ["edge-tts", "--list-voices"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"edge-tts --list-voices 失败: {result.stderr}")
            return {"voices": []}
        
        # 解析输出
        voices = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            # 跳过表头行
            if not line.strip() or 'Name' in line or '---' in line:
                continue
            
            # 提取语音ID（第一列）
            parts = line.split()
            if not parts:
                continue
            
            voice_id = parts[0]
            
            # 只保留美式英语和英式英语 (en-US 和 en-GB)
            if not (voice_id.startswith('en-US') or voice_id.startswith('en-GB')):
                continue
            
            # 解析地区和性别
            region_code = '-'.join(voice_id.split('-')[:2])  # 如 en-US
            
            # 从行中提取性别
            gender = "Unknown"
            if "Female" in line:
                gender = "Female"
            elif "Male" in line:
                gender = "Male"
            
            # 提取语音名称（去掉 Neural 后缀）
            voice_name = voice_id.split('-')[-1].replace('Neural', '').replace('Multilingual', '')
            
            # 构建显示名称
            region_name = region_names.get(region_code, region_code)
            gender_name = gender_names.get(gender, "")
            
            display_name = f"{region_name} - {voice_name} ({gender_name})" if gender_name else f"{region_name} - {voice_name}"
            
            voices.append({
                "id": voice_id,
                "name": display_name
            })
        
        # 按地区排序（英式英语在前，美式英语在后）
        voices.sort(key=lambda v: 0 if v["id"].startswith("en-GB") else 1)
        
        return {"voices": voices}
        
    except FileNotFoundError:
        # edge-tts 未安装
        return {"voices": []}
    except subprocess.TimeoutExpired:
        return {"voices": []}
    except Exception as e:
        print(f"获取Edge-TTS语音列表失败: {e}")
        return {"voices": []}


@router.get("/tts/edge/voices/zh")
async def get_edge_tts_voices_zh(
    current_user: User = Depends(get_current_user)
):
    """
    获取Edge-TTS可用的中文语音列表。

    动态调用 edge-tts --list-voices 命令获取语音列表，
    过滤出中文语音返回给前端。

    Returns:
        中文语音列表
    """
    import subprocess
    
    # 地区名称映射
    region_names = {
        "zh-CN": "中国大陆",
        "zh-HK": "香港粤语",
        "zh-TW": "台湾国语",
    }
    
    # 性别名称映射
    gender_names = {
        "Female": "女声",
        "Male": "男声",
    }
    
    try:
        # 调用 edge-tts --list-voices 获取语音列表
        result = subprocess.run(
            ["edge-tts", "--list-voices"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"edge-tts --list-voices 失败: {result.stderr}")
            return {"voices": []}
        
        # 解析输出
        voices = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            # 跳过表头行
            if not line.strip() or 'Name' in line or '---' in line:
                continue
            
            # 提取语音ID（第一列）
            parts = line.split()
            if not parts:
                continue
            
            voice_id = parts[0]
            
            # 只保留中文语音 (zh-CN, zh-HK, zh-TW)
            if not (voice_id.startswith('zh-CN') or voice_id.startswith('zh-HK') or voice_id.startswith('zh-TW')):
                continue
            
            # 解析地区和性别
            region_code = '-'.join(voice_id.split('-')[:2])  # 如 zh-CN
            
            # 从行中提取性别
            gender = "Unknown"
            if "Female" in line:
                gender = "Female"
            elif "Male" in line:
                gender = "Male"
            
            # 提取语音名称（去掉 Neural 后缀）
            voice_name = voice_id.split('-')[-1].replace('Neural', '').replace('Multilingual', '')
            
            # 构建显示名称
            region_name = region_names.get(region_code, region_code)
            gender_name = gender_names.get(gender, "")
            
            display_name = f"{region_name} - {voice_name} ({gender_name})" if gender_name else f"{region_name} - {voice_name}"
            
            voices.append({
                "id": voice_id,
                "name": display_name
            })
        
        # 按地区排序（中国大陆在前）
        voices.sort(key=lambda v: 0 if v["id"].startswith("zh-CN") else 1)
        
        return {"voices": voices}
        
    except FileNotFoundError:
        # edge-tts 未安装
        return {"voices": []}
    except subprocess.TimeoutExpired:
        return {"voices": []}
    except Exception as e:
        print(f"获取Edge-TTS中文语音列表失败: {e}")
        return {"voices": []}


@router.get("/tts/minimax/voices")
async def get_minimax_voices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取 MiniMax 可用的语音列表。

    从 MiniMax API 获取 system_voice 列表。

    Returns:
        语音列表
    """
    import os

    # 获取用户设置
    settings = await get_or_create_user_settings(db, current_user.id)
    
    # 优先从用户数据库设置获取 API Key，其次使用全局环境变量
    api_key = settings.minimax_api_key if settings.minimax_api_key else os.getenv("MINIMAX_API_KEY")

    if not api_key:
        return {"voices": [], "error": "未配置 MiniMax API Key"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.minimaxi.com/v1/get_voice",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={"voice_type": "all"}
            )

            if response.status_code == 200:
                data = response.json()
                voices = []

                # 提取系统音色（仅英文 - 以 English_ 开头）
                system_voices = data.get("system_voice", [])
                for voice in system_voices:
                    voice_id = voice.get("voice_id", "")
                    voice_name = voice.get("voice_name", "")
                    description = voice.get("description", [])
                    desc_text = description[0] if description else ""

                    # 只保留 English_ 开头的明确英文音色
                    if not voice_id.startswith("English_"):
                        continue

                    # 判断口音类型（美式/英式）
                    accent = "美式英语"
                    if any(keyword in desc_text for keyword in ["英式", "英口", "British"]):
                        accent = "英式英语"
                    elif any(keyword in desc_text for keyword in ["澳大利亚", "澳式", "Aussie", "australia"]):
                        accent = "澳大利亚英语"
                    elif any(keyword in desc_text for keyword in ["印度", "India"]):
                        accent = "印度英语"
                    elif any(keyword in desc_text for keyword in ["苏格兰", "Scotland"]):
                        accent = "苏格兰英语"

                    # 构建显示名称：口音 + 姓名
                    display_name = f"{accent} {voice_name}"

                    voices.append({
                        "id": voice_id,
                        "name": display_name,
                        "description": desc_text[:50] if desc_text else ""
                    })

                return {"voices": voices}
            else:
                return {"voices": [], "error": f"获取音色失败: {response.status_code}"}

    except Exception as e:
        return {"voices": [], "error": str(e)}


@router.get("/tts/minimax/voices/zh")
async def get_minimax_voices_zh(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取 MiniMax 可用的中文语音列表。

    从 MiniMax API 获取 system_voice 列表，筛选出中文语音。

    Returns:
        中文语音列表
    """
    import os

    # 获取用户设置
    settings = await get_or_create_user_settings(db, current_user.id)
    
    # 优先从用户数据库设置获取 API Key，其次使用全局环境变量
    api_key = settings.minimax_api_key if settings.minimax_api_key else os.getenv("MINIMAX_API_KEY")

    if not api_key:
        return {"voices": [], "error": "未配置 MiniMax API Key"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.minimaxi.com/v1/get_voice",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={"voice_type": "all"}
            )

            if response.status_code == 200:
                data = response.json()
                voices = []

                # 提取系统音色
                system_voices = data.get("system_voice") or []
                for voice in system_voices:
                    if not voice:
                        continue
                    voice_id = voice.get("voice_id", "")
                    voice_name = voice.get("voice_name", "")
                    description = voice.get("description", [])
                    desc_text = description[0] if description else ""

                    # 筛选中文音色
                    # 1. Chinese (Mandarin)_ 前缀 - 标准普通话
                    # 2. Cantonese_ 前缀 - 粤语
                    # 3. male-qn-*, female-* 等中文风格名称
                    # 4. 其他中文风格前缀
                    is_chinese = (
                        voice_id.startswith("Chinese (Mandarin)") or
                        voice_id.startswith("Cantonese_") or
                        voice_id.startswith("male-qn-") or
                        voice_id.startswith("female-") or
                        voice_id.startswith("clever_") or
                        voice_id.startswith("cute_") or
                        voice_id.startswith("lovely_") or
                        voice_id.startswith("cartoon_") or
                        voice_id.startswith("bingjiao_") or
                        voice_id.startswith("junlang_") or
                        voice_id.startswith("chunzhen_") or
                        voice_id.startswith("lengdan_") or
                        voice_id.startswith("badao_") or
                        voice_id.startswith("tianxin_") or
                        voice_id.startswith("qiaopi_") or
                        voice_id.startswith("wumei_") or
                        voice_id.startswith("diadia_") or
                        voice_id.startswith("danya_")
                    )
                    
                    if not is_chinese:
                        continue

                    # 判断语音类型
                    voice_type = "中文音色"
                    if voice_id.startswith("Chinese (Mandarin)"):
                        voice_type = "普通话"
                    elif voice_id.startswith("Cantonese_"):
                        voice_type = "粤语"
                    elif voice_id.startswith("male-qn-"):
                        voice_type = "男声"
                    elif voice_id.startswith("female-"):
                        voice_type = "女声"

                    # 构建显示名称
                    display_name = f"{voice_type} - {voice_name}"

                    voices.append({
                        "id": voice_id,
                        "name": display_name,
                        "description": desc_text[:50] if desc_text else ""
                    })

                return {"voices": voices}
            else:
                return {"voices": [], "error": f"获取音色失败: {response.status_code}"}

    except Exception as e:
        return {"voices": [], "error": str(e)}


@router.get("/tts/minimax/usage")
async def get_minimax_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    查询 MiniMax Token Plan 剩余配额。

    返回 TTS HD 每日配额使用情况。

    Returns:
        配额信息
    """
    import os

    # 获取用户设置
    settings = await get_or_create_user_settings(db, current_user.id)
    
    # 优先从用户数据库设置获取 API Key，其次使用全局环境变量
    api_key = settings.minimax_api_key if settings.minimax_api_key else os.getenv("MINIMAX_API_KEY")

    if not api_key:
        return {"error": "未配置 MiniMax API Key"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # MiniMax 用量查询 API（使用 www.minimaxi.com）
            response = await client.get(
                "https://www.minimaxi.com/v1/api/openplatform/coding_plan/remains",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            print(f"MiniMax用量查询响应: {response.status_code}, {response.text[:500]}")
            if response.status_code == 200:
                data = response.json()
                # 返回 model_remains 数组
                return {"model_remains": data.get("model_remains", [])}
            else:
                return {"error": f"查询失败: {response.status_code}, {response.text[:200]}"}
    except Exception as e:
        print(f"MiniMax用量查询异常: {e}")
        return {"error": str(e)}


# ==================== Azure TTS 端点 ====================
# Azure 语音列表缓存（内存缓存，减少 API 调用）
# 缓存有效期 1 小时
azure_voices_cache = {}

def _get_cached_full_data(subscription_key: str, region: str) -> tuple:
    """获取缓存的完整语音列表"""
    key = f"{subscription_key}:{region}:full"
    if key in azure_voices_cache:
        import time
        cached_data, cached_time = azure_voices_cache[key]
        if time.time() - cached_time < 3600:  # 1小时有效期
            return cached_data, True
    return None, False

def _set_cached_full_data(subscription_key: str, region: str, data: list):
    """设置完整数据缓存"""
    import time
    key = f"{subscription_key}:{region}:full"
    azure_voices_cache[key] = (data, time.time())

async def _get_azure_voices_from_api(subscription_key: str, region: str) -> list:
    """从 Azure API 获取语音列表（异步版本）"""
    import httpx
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}
    # 增加超时时间到 60 秒，因为从国内访问 Azure 全球云较慢
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    raise Exception(f"HTTP {response.status_code}")

async def _get_filtered_voices(subscription_key: str, region: str, locale_prefix: str) -> list:
    """获取筛选后的语音列表（带缓存，异步版本）"""
    # 先检查缓存
    cached, found = _get_cached_full_data(subscription_key, region)
    if not found:
        cached = await _get_azure_voices_from_api(subscription_key, region)
        _set_cached_full_data(subscription_key, region, cached)
    
    # 筛选对应语言
    voices = []
    for voice in cached:
        short_name = voice.get('ShortName', '')
        locale = voice.get('Locale', '')
        
        if locale_prefix == "en" and (short_name.startswith("en-US") or short_name.startswith("en-GB")):
            display_name = short_name.replace("Neural", "").replace("en-US-", "美式-").replace("en-GB-", "英式-")
            voices.append({"id": short_name, "name": display_name, "locale": locale, "gender": voice.get('Gender', '')})
        elif locale_prefix == "zh" and locale.startswith("zh-"):
            display_name = short_name.replace("Neural", "").replace("zh-CN-", "中/").replace("zh-HK-", "粤/").replace("zh-TW-", "台/")
            voices.append({"id": short_name, "name": display_name, "locale": locale, "gender": voice.get('Gender', '')})
    
    return voices


@router.get("/tts/azure/voices")
async def get_azure_voices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取 Azure TTS 可用的英文语音列表。

    从 Azure Speech SDK 获取支持的神经网络语音列表。

    Returns:
        英文语音列表
    """
    import os

    # 获取用户设置
    settings = await get_or_create_user_settings(db, current_user.id)

    # 优先从用户数据库设置获取配置
    subscription_key = settings.azure_subscription_key if settings.azure_subscription_key else os.getenv("AZURE_TTS_SUBSCRIPTION_KEY")
    region = settings.azure_region if settings.azure_region else os.getenv("AZURE_TTS_REGION")

    if not subscription_key or not region:
        return {"voices": [], "error": "未配置 Azure TTS Subscription Key 或 Region"}

    try:
        # 使用带缓存的筛选函数
        voices = await _get_filtered_voices(subscription_key, region, "en")
        return {"voices": voices}

    except Exception as e:
        print(f"Azure TTS 英文语音列表获取异常: {e}")
        return {"voices": [], "error": str(e)}


@router.get("/tts/azure/voices/zh")
async def get_azure_voices_zh(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取 Azure TTS 可用的中文语音列表。

    从 Azure Speech SDK 获取支持的中文神经网络语音列表。

    Returns:
        中文语音列表
    """
    import os

    # 获取用户设置
    settings = await get_or_create_user_settings(db, current_user.id)

    # 优先从用户数据库设置获取配置
    subscription_key = settings.azure_subscription_key if settings.azure_subscription_key else os.getenv("AZURE_TTS_SUBSCRIPTION_KEY")
    region = settings.azure_region if settings.azure_region else os.getenv("AZURE_TTS_REGION")

    if not subscription_key or not region:
        return {"voices": [], "error": "未配置 Azure TTS Subscription Key 或 Region"}

    try:
        # 使用带缓存的筛选函数
        voices = await _get_filtered_voices(subscription_key, region, "zh")
        return {"voices": voices}

    except Exception as e:
        print(f"Azure TTS 中文语音列表获取异常: {e}")
        return {"voices": [], "error": str(e)}


@router.get("/tts/azure/usage")
async def get_azure_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, description="查询天数，默认30天")
):
    """
    查询 Azure TTS 使用量。

    通过 Azure Monitor API 获取指定时间范围内的 TTS 使用统计。

    Args:
        days: 查询天数，默认30天

    Returns:
        使用量统计
    """
    import os
    from datetime import datetime, timedelta

    # 获取用户设置
    settings = await get_or_create_user_settings(db, current_user.id)

    # 优先从用户数据库设置获取配置
    subscription_key = settings.azure_subscription_key if settings.azure_subscription_key else os.getenv("AZURE_TTS_SUBSCRIPTION_KEY")
    region = settings.azure_region if settings.azure_region else os.getenv("AZURE_TTS_REGION")

    if not subscription_key or not region:
        return {"error": "未配置 Azure TTS Subscription Key 或 Region"}

    try:
        # 计算时间范围
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        # Azure Monitor Metrics API
        url = f"https://management.azure.com/subscriptions/{{subscription_id}}/resourceGroups/{{resource_group}}/providers/Microsoft.CognitiveServices/accounts/{{account_name}}/metrics?api-version=2023-05-01"

        # 由于 Azure Monitor API 需要复杂的认证和订阅信息，这里使用简化的方式
        # 实际使用中可以通过 Azure Portal 或 Azure CLI 查询

        # 尝试使用 Azure REST API 查询用量
        # 注意：实际部署时需要替换为正确的订阅和资源信息
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 构造 Azure Resource Manager 请求
            # 这里需要用户的 Azure 订阅信息，实际使用中可能需要额外配置
            return {
                "message": f"Azure TTS 使用量查询需要配置 Azure 订阅信息",
                "subscription_key_configured": bool(subscription_key),
                "region_configured": bool(region),
                "days": days,
                "note": "请通过 Azure Portal (https://portal.azure.com) -> 您的语音服务资源 -> 指标 查看详细使用量"
            }

    except Exception as e:
        print(f"Azure TTS 用量查询异常: {e}")
        return {"error": str(e)}
