"""应用配置管理"""
import os
import secrets
import logging
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """应用设置 - 从 .env 文件加载"""

    # 应用信息
    APP_NAME: str = "EnglishReadVoyage API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 跨域 - 支持从环境变量读取，逗号分隔多个域名
    CORS_ORIGINS: str = "*"  # 默认允许所有（开发环境）

    # 生产环境标志
    IS_PRODUCTION: bool = False

    # 目录
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    BOOKS_DIR: Optional[str] = None
    DATABASE_PATH: Optional[str] = None

    @property
    def DATABASE_URL(self) -> str:
        path = self.DATABASE_PATH or os.path.join(self.BASE_DIR, "data.db")
        return f"sqlite+aiosqlite:///{path}"

    # Kokoro语音合成
    KOKORO_API_URL: str = "http://localhost:8880/v1/audio/speech"
    KOKORO_DEFAULT_VOICE: str = "bf_v0isabella"
    KOKORO_DEFAULT_VOICE_ZH: str = "zf_xiaoxiao"  # 默认中文语音
    KOKORO_DEFAULT_SPEED: float = 1.0
    TTS_TIMEOUT: float = 30.0

    # 默认TTS服务 (kokoro-tts, doubao-tts, siliconflow-tts, edge-tts, minimax-tts)
    DEFAULT_TTS_SERVICE: str = "edge-tts"

    # 豆包语音合成
    DOUBAO_API_URL: str = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    DOUBAO_DEFAULT_VOICE: str = "zh_female_shuangkuaisisi_moon_bigtts"
    DOUBAO_DEFAULT_VOICE_ZH: str = "zh_female_yingyujiaoyu_mars_bigtts"  # 默认中文语音
    DOUBAO_DEFAULT_RESOURCE_ID: str = "seed-tts-1.0"
    DOUBAO_DEFAULT_SPEED: float = 1.0

    # 硅基流动语音合成
    SILICONFLOW_API_URL: str = "https://api.siliconflow.cn/v1/audio/speech"
    SILICONFLOW_DEFAULT_MODEL: str = "fnlp/MOSS-TTSD-v0.5"
    SILICONFLOW_DEFAULT_VOICE: str = "anna"

    # Edge-TTS语音合成 (微软Edge在线TTS)
    EDGE_TTS_DEFAULT_VOICE: str = "en-US-AriaNeural"
    EDGE_TTS_DEFAULT_VOICE_ZH: str = "zh-CN-XiaoxiaoNeural"
    EDGE_TTS_DEFAULT_SPEED: float = 1.0

    # MiniMax语音合成 (speech-2.8-hd)
    MINIMAX_API_URL: str = "https://api.minimaxi.com/v1/t2a_v2"
    MINIMAX_DEFAULT_MODEL: str = "speech-2.8-hd"
    MINIMAX_DEFAULT_VOICE: str = "male-qn-qingse"
    MINIMAX_DEFAULT_SPEED: float = 1.0
    MINIMAX_MIN_INTERVAL: float = 3.0  # 最小请求间隔(秒)，确保 20 RPM

    # JWT 认证
    # 不再提供默认值，生产环境必须通过环境变量设置
    SECRET_KEY: str = ""
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
        # BASE_DIR 是 /app，Books 目录在 /app/Books
        self.BOOKS_DIR = self.BOOKS_DIR or os.path.join(self.BASE_DIR, "Books")
        self.DATABASE_PATH = self.DATABASE_PATH or os.path.join(self.BASE_DIR, "data.db")

        # 处理 CORS_ORIGINS：从逗号分隔字符串转为列表
        if isinstance(self.CORS_ORIGINS, str):
            if self.CORS_ORIGINS.strip() == "*":
                self._cors_origins_list = ["*"]
            else:
                self._cors_origins_list = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        else:
            self._cors_origins_list = self.CORS_ORIGINS

        # 检测是否为生产环境
        if not self.IS_PRODUCTION:
            self.IS_PRODUCTION = self.DEBUG is False and os.getenv("ENVIRONMENT") == "production"

        # JWT Secret Key 安全检查
        self._validate_secret_key()

    def _validate_secret_key(self):
        """验证 SECRET_KEY 的安全性"""
        if not self.SECRET_KEY:
            if self.IS_PRODUCTION:
                raise ValueError(
                    "生产环境必须设置 SECRET_KEY 环境变量！"
                    "请设置: SECRET_KEY=<your-secret-key>"
                )
            else:
                # 开发环境生成临时密钥并警告
                self.SECRET_KEY = secrets.token_urlsafe(32)
                logger.warning(
                    "⚠️  未设置 SECRET_KEY，已生成临时密钥用于开发。"
                    "⚠️  生产环境请设置环境变量: SECRET_KEY=<your-secret-key>"
                )
        elif len(self.SECRET_KEY) < 32:
            logger.warning(
                f"⚠️  SECRET_KEY 长度不足 32 字符，当前: {len(self.SECRET_KEY)} 字符"
                "⚠️  建议使用至少 32 字符的随机字符串。"
            )

    @property
    def cors_origins(self) -> list[str]:
        """获取 CORS origins 列表"""
        return self._cors_origins_list

    def get_cors_origins(self) -> list[str]:
        """
        获取 CORS origins。
        生产环境下，如果未配置具体域名，给出警告。
        """
        if self.IS_PRODUCTION and self._cors_origins_list == ["*"]:
            logger.warning(
                "⚠️  生产环境 CORS_ORIGINS 设为 '*'，建议配置具体域名！"
            )
        return self._cors_origins_list


@lru_cache()
def get_settings() -> Settings:
    """获取缓存的配置实例"""
    return Settings()
