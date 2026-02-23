"""TTS-related Pydantic schemas."""
from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """文本转语音请求模式"""
    text: str = Field(..., min_length=1, description="Text to convert to speech")
    voice: str = Field(
        default="bf_v0isabella",
        description="Voice ID for TTS (e.g., 'bf_v0isabella', 'bf_alice')"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, this is a test.",
                "voice": "bf_v0isabella"
            }
        }


class TTSResponse(BaseModel):
    """文本转语音响应模式"""
    url: str = Field(..., description="URL to the generated audio file")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "/audio/abc123def456.mp3"
            }
        }
