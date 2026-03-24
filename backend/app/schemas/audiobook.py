"""听书播放器相关的Pydantic模式"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class PlaylistItemBase(BaseModel):
    """播放列表项基础模式"""
    book_id: str = Field(..., description="书籍ID")
    sort_order: int = Field(default=0, description="排序顺序")


class PlaylistItemAddRequest(BaseModel):
    """添加书籍到播放列表请求"""
    book_ids: List[str] = Field(..., description="要添加的书籍ID列表")


class PlaylistItemReorderRequest(BaseModel):
    """重新排序播放列表请求"""
    item_orders: List[dict] = Field(..., description="列表项排序信息，格式: [{item_id: int, sort_order: int}]")


class PlaylistItemResponse(BaseModel):
    """播放列表项响应"""
    id: int = Field(..., description="列表项ID")
    book_id: str = Field(..., description="书籍ID")
    book_title: str = Field(..., description="书籍标题")
    book_cover: Optional[str] = Field(None, description="书籍封面URL")
    sort_order: int = Field(..., description="排序顺序")
    added_at: datetime = Field(..., description="添加时间")

    class Config:
        from_attributes = True


class PlaylistSettingsUpdateRequest(BaseModel):
    """更新播放列表设置请求"""
    play_mode: Optional[str] = Field(None, description="播放模式: sequential/random")
    sleep_timer: Optional[int] = Field(None, description="定时关闭时间(分钟)，null表示不设置")
    current_book_index: Optional[int] = Field(None, description="当前播放的书籍索引")


class PlaylistResponse(BaseModel):
    """播放列表响应"""
    id: int = Field(..., description="列表ID")
    name: str = Field(..., description="列表名称")
    play_mode: str = Field(..., description="播放模式")
    sleep_timer: Optional[int] = Field(None, description="定时关闭时间(分钟)")
    current_book_index: int = Field(..., description="当前播放的书籍索引")
    items: List[PlaylistItemResponse] = Field(default_factory=list, description="列表项")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class BookForPlaylistResponse(BaseModel):
    """可用于添加到播放列表的书籍响应"""
    id: str = Field(..., description="书籍ID")
    title: str = Field(..., description="书籍标题")
    cover_path: Optional[str] = Field(None, description="封面路径")
    level: str = Field(default="Unknown", description="阅读等级")

    class Config:
        from_attributes = True


class BooksByGroupResponse(BaseModel):
    """按分组组织的书籍列表响应"""
    group_id: int = Field(..., description="分组ID")
    group_name: str = Field(..., description="分组名称")
    books: List[BookForPlaylistResponse] = Field(default_factory=list, description="书籍列表")


class PlaylistOperationResponse(BaseModel):
    """播放列表操作响应"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")


class NextBookResponse(BaseModel):
    """下一本书籍响应"""
    has_next: bool = Field(..., description="是否有下一本")
    book_id: Optional[str] = Field(None, description="书籍ID")
    book_title: Optional[str] = Field(None, description="书籍标题")
    book_cover: Optional[str] = Field(None, description="书籍封面URL")
    index: int = Field(..., description="在播放列表中的索引")


class BookAudioInfo(BaseModel):
    """书籍音频信息"""
    text_hash: str = Field(..., description="文本哈希值（文件名）")
    text: str = Field(..., description="原文文本")
    translation: Optional[str] = Field(default="", description="中文翻译")
    audio_url: str = Field(..., description="英文音频文件URL")
    audio_url_zh: Optional[str] = Field(default="", description="中文音频文件URL")
    duration: float = Field(default=0.0, description="英文音频时长（秒）")
    duration_zh: float = Field(default=0.0, description="中文音频时长（秒）")


class BookAudioListResponse(BaseModel):
    """书籍音频列表响应"""
    book_id: str = Field(..., description="书籍ID")
    book_title: str = Field(..., description="书籍标题")
    total: int = Field(..., description="音频文件总数")
    total_duration: float = Field(default=0.0, description="总时长（秒）")
    has_chinese: bool = Field(default=False, description="是否有中文翻译")
    audio_list: List[BookAudioInfo] = Field(default_factory=list, description="音频列表")


class BookAudioCheckResult(BaseModel):
    """单本书籍音频检查结果"""
    book_id: str = Field(..., description="书籍ID")
    book_title: str = Field(..., description="书籍标题")
    total_sentences: int = Field(..., description="总句子数")
    en_audio_count: int = Field(..., description="英文音频数量")
    zh_audio_count: int = Field(..., description="中文音频数量")
    missing_en: int = Field(default=0, description="缺失英文音频数量")
    missing_zh: int = Field(default=0, description="缺失中文音频数量")
    is_complete_en: bool = Field(..., description="英文音频是否完整")
    is_complete_zh: bool = Field(..., description="中文音频是否完整")


class PlaylistAudioCheckResponse(BaseModel):
    """播放列表音频完整性检查响应"""
    total_books: int = Field(..., description="播放列表中的书籍总数")
    complete_books_en: int = Field(..., description="英文音频完整的书籍数")
    complete_books_zh: int = Field(..., description="中文音频完整的书籍数")
    results: List[BookAudioCheckResult] = Field(default_factory=list, description="各书籍检查结果")
