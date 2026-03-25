"""用户设置API端点。"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import json
from app.core.config import get_settings
from app.core.database import get_db
from app.api.dependencies import get_current_user
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
            # Edge-TTS 默认配置
            "edge_tts_voice": settings.EDGE_TTS_DEFAULT_VOICE,
            "edge_tts_speed": settings.EDGE_TTS_DEFAULT_SPEED,
            # MiniMax TTS 默认配置
            "minimax_api_key": None,
            "minimax_model": settings.MINIMAX_DEFAULT_MODEL,
            "minimax_voice": settings.MINIMAX_DEFAULT_VOICE,
            "minimax_speed": settings.MINIMAX_DEFAULT_SPEED
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
            doubao_voice_zh=settings.doubao_voice_zh or default_config.get("doubao_voice_zh"),
            doubao_speed=settings.doubao_speed if settings.doubao_speed is not None else default_config.get("doubao_speed", 1.0),
            doubao_app_id=settings.doubao_app_id or default_config.get("doubao_app_id"),
            doubao_access_key=settings.doubao_access_key or default_config.get("doubao_access_key"),
            doubao_resource_id=settings.doubao_resource_id or default_config.get("doubao_resource_id"),
            # 硅基流动TTS设置
            siliconflow_api_key=settings.siliconflow_api_key or default_config.get("siliconflow_api_key"),
            siliconflow_model=settings.siliconflow_model or default_config.get("siliconflow_model"),
            siliconflow_voice=settings.siliconflow_voice or default_config.get("siliconflow_voice"),
            # Edge-TTS设置
            edge_tts_voice=settings.edge_tts_voice or default_config.get("edge_tts_voice"),
            edge_tts_speed=settings.edge_tts_speed if settings.edge_tts_speed is not None else default_config.get("edge_tts_speed", 1.0),
            # MiniMax TTS设置
            minimax_api_key=settings.minimax_api_key or default_config.get("minimax_api_key"),
            minimax_model=settings.minimax_model or default_config.get("minimax_model"),
            minimax_voice=settings.minimax_voice or default_config.get("minimax_voice"),
            minimax_speed=settings.minimax_speed if settings.minimax_speed is not None else default_config.get("minimax_speed", 1.0)
        ),
        phonetic=UserPhoneticSettings(
            accent=settings.phonetic_accent or "uk"
        ),
        ui=UserUiSettings(
            hide_read_books_map=hide_read_books_map
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
        settings.tts_service_name = request.service_name.strip() or "edge-tts"

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

    # 更新 Edge-TTS 设置
    if request.edge_tts_voice is not None:
        settings.edge_tts_voice = request.edge_tts_voice.strip() if request.edge_tts_voice.strip() else None
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
    if request.minimax_speed is not None:
        if not (0.25 <= request.minimax_speed <= 4.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MiniMax 朗读速度必须在 0.25 到 4.0 之间"
            )
        settings.minimax_speed = request.minimax_speed

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
        doubao_voice_zh=settings.doubao_voice_zh or default_config.get("doubao_voice_zh"),
        doubao_speed=settings.doubao_speed if settings.doubao_speed is not None else default_config.get("doubao_speed", 1.0),
        doubao_app_id=settings.doubao_app_id or default_config.get("doubao_app_id"),
        doubao_access_key=settings.doubao_access_key or default_config.get("doubao_access_key"),
        doubao_resource_id=settings.doubao_resource_id or default_config.get("doubao_resource_id"),
        # 硅基流动TTS设置
        siliconflow_api_key=settings.siliconflow_api_key or default_config.get("siliconflow_api_key"),
        siliconflow_model=settings.siliconflow_model or default_config.get("siliconflow_model"),
        siliconflow_voice=settings.siliconflow_voice or default_config.get("siliconflow_voice"),
        # Edge-TTS设置
        edge_tts_voice=settings.edge_tts_voice or default_config.get("edge_tts_voice"),
        edge_tts_speed=settings.edge_tts_speed if settings.edge_tts_speed is not None else default_config.get("edge_tts_speed", 1.0),
        # MiniMax TTS设置
        minimax_api_key=settings.minimax_api_key or default_config.get("minimax_api_key"),
        minimax_model=settings.minimax_model or default_config.get("minimax_model"),
        minimax_voice=settings.minimax_voice or default_config.get("minimax_voice"),
        minimax_speed=settings.minimax_speed if settings.minimax_speed is not None else default_config.get("minimax_speed", 1.0)
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
