"""发音获取API端点 - 使用有道词典免费API"""
from fastapi import APIRouter, Depends, HTTPException
import httpx

from app.api.dependencies import get_current_user
from app.models.database_models import User


router = APIRouter()


@router.get("/{word}")
async def get_pronunciation(
    word: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取单词发音。

    使用有道词典免费API获取英式发音。

    Args:
        word: 要获取发音的单词

    Returns:
        包含发音音频URL的响应
    """
    word = word.lower().strip()

    if not word:
        raise HTTPException(status_code=400, detail="单词不能为空")

    # 有道词典免费API
    # type=1: 英式发音, type=2: 美式发音
    audio_url = f"http://dict.youdao.com/dictvoice?type=1&word={word}"

    # 验证URL是否可访问
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.head(audio_url)
            if response.status_code == 200:
                return {
                    "word": word,
                    "audio_url": audio_url,
                    "accent": "uk"
                }
            else:
                # 如果英式发音不可用，尝试美式发音
                audio_url_us = f"http://dict.youdao.com/dictvoice?type=2&word={word}"
                response_us = await client.head(audio_url_us)
                if response_us.status_code == 200:
                    return {
                        "word": word,
                        "audio_url": audio_url_us,
                        "accent": "us"
                    }
                return {
                    "word": word,
                    "audio_url": None,
                    "accent": None,
                    "message": "未找到发音"
                }
    except Exception as e:
        print(f"获取发音失败: {e}")
        return {
            "word": word,
            "audio_url": None,
            "accent": None,
            "message": "获取发音失败"
        }
