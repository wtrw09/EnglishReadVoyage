"""词典查询相关的Pydantic模式"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class TranslationAPIConfig(BaseModel):
    """翻译API配置"""
    id: Optional[int] = None
    name: str
    app_id: str
    app_key: str
    is_active: bool = True


class TranslationAPIResponse(BaseModel):
    """翻译API响应（不返回app_key）"""
    id: int
    name: str
    app_id: str
    is_active: bool
    created_at: datetime


class UserTranslationSettings(BaseModel):
    """用户翻译设置"""
    selected_api_id: Optional[int] = None
    apis: List[TranslationAPIResponse] = []
    is_admin: bool = False  # 是否是管理员


class UserDictionarySettings(BaseModel):
    """用户词典设置"""
    dictionary_source: str = Field("local", description="词典来源：'local' 本地ECDICT，'api' FreeDictionaryAPI")


class UserTtsSettings(BaseModel):
    """用户朗读设置"""
    service_name: str = Field("kokoro-tts", description="朗读服务名称: kokoro-tts, doubao-tts, siliconflow-tts 或 edge-tts")
    # Kokoro TTS 设置
    kokoro_voice: Optional[str] = Field(None, description="Kokoro语音类型")
    kokoro_speed: float = Field(1.0, description="Kokoro朗读速度 (0.5-2.0)")
    kokoro_api_url: Optional[str] = Field(None, description="Kokoro服务地址，为空则使用系统默认")
    # 豆包TTS设置
    doubao_voice: Optional[str] = Field(None, description="豆包语音类型(英文)")
    doubao_voice_zh: Optional[str] = Field(None, description="豆包语音类型(中文)")
    doubao_speed: float = Field(1.0, description="豆包朗读速度 (0.5-2.0)")
    doubao_app_id: Optional[str] = Field(None, description="豆包APP ID")
    doubao_access_key: Optional[str] = Field(None, description="豆包Access Key")
    doubao_resource_id: Optional[str] = Field(None, description="豆包Resource ID")
    # 硅基流动TTS设置
    siliconflow_api_key: Optional[str] = Field(None, description="硅基流动API Key")
    siliconflow_model: Optional[str] = Field(None, description="硅基流动模型名称")
    siliconflow_voice: Optional[str] = Field(None, description="硅基流动语音类型")
    # Edge-TTS设置
    edge_tts_voice: Optional[str] = Field(None, description="Edge-TTS语音类型")
    edge_tts_speed: float = Field(1.0, description="Edge-TTS朗读速度 (0.5-2.0)")


class UserPhoneticSettings(BaseModel):
    """用户音标设置"""
    accent: str = Field("uk", description="音标口音偏好：'uk' 英式，'us' 美式")


class UserUiSettings(BaseModel):
    """用户界面设置"""
    hide_read_books_map: Dict[int, bool] = Field(default_factory=dict, description="分组隐藏已读书籍状态")


class UpdateUiSettingsRequest(BaseModel):
    """更新界面设置请求"""
    hide_read_books_map: Optional[Dict[int, bool]] = Field(None, description="分组隐藏已读书籍状态")


class UserSettingsResponse(BaseModel):
    """用户设置响应"""
    dictionary: UserDictionarySettings
    tts: UserTtsSettings
    phonetic: UserPhoneticSettings
    ui: UserUiSettings


class UpdateDictionarySettingsRequest(BaseModel):
    """更新词典设置请求"""
    dictionary_source: str = Field(..., description="词典来源：'local' 或 'api'")


class UpdatePhoneticSettingsRequest(BaseModel):
    """更新音标设置请求"""
    accent: str = Field(..., description="音标口音偏好：'uk' 英式，'us' 美式")


class UpdateTtsSettingsRequest(BaseModel):
    """更新朗读设置请求"""
    service_name: Optional[str] = Field(None, description="朗读服务名称: kokoro-tts, doubao-tts, siliconflow-tts 或 edge-tts")
    # Kokoro TTS 设置
    kokoro_voice: Optional[str] = Field(None, description="Kokoro语音类型")
    kokoro_speed: Optional[float] = Field(None, description="Kokoro朗读速度 (0.5-2.0)")
    kokoro_api_url: Optional[str] = Field(None, description="Kokoro服务地址，为空则使用系统默认")
    # 豆包TTS设置
    doubao_voice: Optional[str] = Field(None, description="豆包语音类型(英文)")
    doubao_voice_zh: Optional[str] = Field(None, description="豆包语音类型(中文)")
    doubao_speed: Optional[float] = Field(None, description="豆包朗读速度 (0.5-2.0)")
    doubao_app_id: Optional[str] = Field(None, description="豆包APP ID")
    doubao_access_key: Optional[str] = Field(None, description="豆包Access Key")
    doubao_resource_id: Optional[str] = Field(None, description="豆包Resource ID")
    # 硅基流动TTS设置
    siliconflow_api_key: Optional[str] = Field(None, description="硅基流动API Key")
    siliconflow_model: Optional[str] = Field(None, description="硅基流动模型名称")
    siliconflow_voice: Optional[str] = Field(None, description="硅基流动语音类型")
    # Edge-TTS设置
    edge_tts_voice: Optional[str] = Field(None, description="Edge-TTS语音类型")
    edge_tts_speed: Optional[float] = Field(None, description="Edge-TTS朗读速度 (0.5-2.0)")


class WordDefinition(BaseModel):
    """单词定义模式"""
    definition: str = Field(..., description="英文定义")
    example: Optional[str] = Field(None, description="例句")
    synonyms: List[str] = Field(default_factory=list, description="同义词")


class WordMeaning(BaseModel):
    """单词释义模式（按词性分组）"""
    partOfSpeech: str = Field(..., description="词性（如 noun, verb）")
    definitions: List[WordDefinition] = Field(..., description="定义列表")


class WordPhonetic(BaseModel):
    """音标模式"""
    text: Optional[str] = Field(None, description="音标文本")
    audio: Optional[str] = Field(None, description="发音音频URL")
    accent: Optional[str] = Field(None, description="口音类型：'uk' 英式，'us' 美式，'unknown' 未知")


class DictionaryResponse(BaseModel):
    """词典查询响应"""
    word: str = Field(..., description="查询的单词")
    phonetic: Optional[str] = Field(None, description="主要音标")
    phonetics: List[WordPhonetic] = Field(default_factory=list, description="音标列表")
    meanings: List[WordMeaning] = Field(..., description="释义列表")
    source: str = Field("dictionaryapi.dev", description="数据来源")
    # ECDICT 特有字段
    tag: Optional[str] = Field(None, description="标签（如：zk gk cet4）")
    translation: Optional[str] = Field(None, description="中文翻译（原始）")
    definition: Optional[str] = Field(None, description="英文释义（原始）")
    exchange: Optional[str] = Field(None, description="时态/复数等变换（如：p:went/d:gone/s:goes）")
    # 百度翻译结果（单词翻译 - 保留用于兼容）
    baidu_translation: Optional[str] = Field(None, description="百度翻译中文结果")
    # 句子翻译结果
    sentence_translation: Optional[str] = Field(None, description="单词所在句子的中文翻译")
    # 相关词组
    related_phrases: Optional[List[Dict[str, str]]] = Field(None, description="相关词组 [{phrase, translation}]")
    
    class Config:
        json_schema_extra = {
            "example": {
                "word": "hello",
                "phonetic": "/həˈloʊ/",
                "phonetics": [{"text": "/həˈloʊ/", "audio": "https://..."}],
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [
                            {
                                "definition": "an expression of greeting",
                                "example": "Hello, how are you?",
                                "synonyms": ["greeting", "salutation"]
                            }
                        ]
                    }
                ],
                "source": "dictionaryapi.dev"
            }
        }
