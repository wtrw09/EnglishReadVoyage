"""TTS语音合成API端点。"""
from fastapi import APIRouter, HTTPException, status, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tts import TTSResponse
from app.services.tts_service import tts_service
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User


router = APIRouter()


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
    使用Kokoro TTS将文本转换为语音。
    
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
