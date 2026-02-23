"""TTS服务用于文本转语音操作"""
import os
import hashlib
import httpx
from typing import Optional

from app.core.config import get_settings
from app.schemas.tts import TTSResponse


class TTSService:
    """TTS相关业务逻辑的服务层"""
    
    def __init__(self):
        """使用配置初始化服务"""
        self.settings = get_settings()
        # 确保缓存目录存在
        os.makedirs(self.settings.CACHE_DIR, exist_ok=True)
    
    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> TTSResponse:
        """
        使用Kokoro TTS API从文本生成语音
        
        参数:
            text: 要转换为语音的文本
            voice: 语音ID（默认为配置的默认语音）
            
        返回:
            包含音频URL的TTSResponse
            
        异常:
            Exception: 如果TTS API调用失败
        """
        if voice is None:
            voice = self.settings.TTS_DEFAULT_VOICE
        
        # 生成缓存文件名
        text_hash = hashlib.md5(f"{text}_{voice}".encode()).hexdigest()
        file_name = f"{text_hash}.mp3"
        file_path = os.path.join(self.settings.CACHE_DIR, file_name)
        
        # 如果存在则返回缓存文件
        if os.path.exists(file_path):
            return TTSResponse(url=f"/audio/{file_name}")
        
        # 调用Kokoro Docker API
        async with httpx.AsyncClient(timeout=self.settings.TTS_TIMEOUT) as client:
            payload = {
                "model": "kokoro",
                "input": text,
                "voice": voice,
                "response_format": "mp3",
                "speed": 1.0
            }
            response = await client.post(self.settings.KOKORO_API_URL, json=payload)
            
            if response.status_code != 200:
                raise Exception(
                    f"TTS API returned {response.status_code}: {response.text}"
                )
            
            # 将mp3内容保存到缓存
            with open(file_path, "wb") as f:
                f.write(response.content)
        
        return TTSResponse(url=f"/audio/{file_name}")


# 单例实例
tts_service = TTSService()
