"""生词本相关的Pydantic模式"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class VocabularyCreate(BaseModel):
    """添加生词请求"""
    word: str = Field(..., description="生词")
    phonetic: Optional[str] = Field(None, description="音标")
    translation: Optional[str] = Field(None, description="中文翻译")
    sentence: Optional[str] = Field(None, description="生词所在的句子")
    book_name: Optional[str] = Field(None, description="书籍名称")


class VocabularyResponse(BaseModel):
    """生词响应"""
    id: int = Field(..., description="生词记录ID")
    word: str = Field(..., description="生词")
    phonetic: Optional[str] = Field(None, description="音标")
    translation: Optional[str] = Field(None, description="中文翻译")
    sentence: Optional[str] = Field(None, description="生词所在的句子")
    book_name: Optional[str] = Field(None, description="书籍名称")
    created_at: datetime = Field(..., description="添加时间")

    class Config:
        from_attributes = True


class VocabularyListResponse(BaseModel):
    """生词列表响应"""
    items: list[VocabularyResponse] = Field(default_factory=list, description="生词列表")
    total: int = Field(0, description="总数")


class VocabularyBatchDelete(BaseModel):
    """批量删除生词请求"""
    ids: list[int] = Field(..., description="要删除的生词ID列表")


class VocabularyExport(BaseModel):
    """导出生词本请求"""
    ids: list[int] = Field(..., description="要导出的生词ID列表")
    hidden_fields: list[str] = Field(default_factory=list, description="要隐藏的字段：word(英文), phonetic(音标), translation(翻译)")
