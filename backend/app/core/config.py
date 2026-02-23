"""应用配置管理"""
import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用设置 - 从 .env 文件加载"""

    # 应用信息
    APP_NAME: str = "EnglishReadVoyage API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 跨域
    CORS_ORIGINS: list[str] = ["*"]

    # 目录
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    BOOKS_DIR: Optional[str] = None
    CACHE_DIR: Optional[str] = None
    DATABASE_PATH: Optional[str] = None

    @property
    def DATABASE_URL(self) -> str:
        path = self.DATABASE_PATH or os.path.join(self.BASE_DIR, "data.db")
        return f"sqlite+aiosqlite:///{path}"

    # Kokoro语音合成
    KOKORO_API_URL: str = "http://localhost:8880/v1/audio/speech"
    TTS_TIMEOUT: float = 30.0
    TTS_DEFAULT_VOICE: str = "bf_v0isabella"

    # JWT 认证
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    INVITATION_CODE_EXPIRE_MINUTES: int = 10080
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 设置默认路径
        self.BOOKS_DIR = self.BOOKS_DIR or os.path.join(os.path.dirname(self.BASE_DIR), "Books")
        self.CACHE_DIR = self.CACHE_DIR or os.path.join(self.BASE_DIR, "cache", "audio")
        self.DATABASE_PATH = self.DATABASE_PATH or os.path.join(self.BASE_DIR, "data.db")


@lru_cache()
def get_settings() -> Settings:
    """获取缓存的配置实例"""
    return Settings()
