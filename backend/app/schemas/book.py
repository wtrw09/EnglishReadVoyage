"""书籍相关的Pydantic模式"""
from pydantic import BaseModel, Field
from typing import List, Optional


class BookPagesResponse(BaseModel):
    """分页加载响应"""
    id: str = Field(..., description="书籍ID")
    title: str = Field(..., description="书籍标题")
    book_path: str = Field(..., description="书籍文件路径")
    page_count: int = Field(..., description="总页数")
    pages: List[str] = Field(..., description="请求的页面内容列表")
    start_page: int = Field(..., description="起始页索引（从0开始）")
    end_page: int = Field(..., description="结束页索引（不包含）")


class BookInfo(BaseModel):
    """图书信息模式"""
    id: str = Field(..., description="唯一书籍标识符（文件路径的MD5哈希）")
    title: str = Field(..., description="书籍标题")
    level: str = Field(..., description="阅读等级（例如 'E', 'F'）")
    file_path: str = Field(..., description="Markdown文件的绝对路径")
    page_count: int = Field(..., ge=0, description="书籍页数")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123def456",
                "title": "All About Coyotes",
                "level": "E",
                "file_path": "/path/to/book.md",
                "page_count": 12
            }
        }


class BookDetail(BaseModel):
    """包含内容的详细书籍信息"""
    id: str = Field(..., description="唯一书籍标识符")
    title: str = Field(..., description="书籍标题")
    level: str = Field(..., description="阅读等级")
    book_path: str = Field(..., description="书籍文件路径")
    pages: List[str] = Field(..., description="HTML页面列表")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123def456",
                "title": "All About Coyotes",
                "level": "E",
                "book_path": "Books/A_Week_with_Grandpa/A_Week_with_Grandpa.md",
                "pages": ["<h1>Page 1</h1><p>Content...</p>", "<h1>Page 2</h1>"]
            }
        }


class BookImportResponse(BaseModel):
    """书籍导入响应"""
    success: bool = Field(..., description="导入成功状态")
    message: str = Field(..., description="导入结果消息")
    book_id: str = Field(None, description="导入的书籍ID（单本导入时）")
    title: str = Field(None, description="导入的书籍标题")
    book_ids: List[str] = Field(default_factory=list, description="导入的书籍ID列表（批量导入时）")


class BookUpdateRequest(BaseModel):
    """书籍更新请求"""
    content: str = Field(..., description="书籍markdown内容")


class BookUpdateResponse(BaseModel):
    """书籍更新响应"""
    success: bool = Field(..., description="更新成功状态")
    message: str = Field(..., description="更新结果消息")
    deleted_files: List[str] = Field(default_factory=list, description="已删除的资源文件列表")


class BookRenameRequest(BaseModel):
    """书籍重命名请求"""
    new_title: str = Field(..., description="新的书籍标题")


class BookRenameResponse(BaseModel):
    """书籍重命名响应"""
    success: bool = Field(..., description="重命名成功状态")
    message: str = Field(..., description="重命名结果消息")
    new_id: Optional[str] = Field(None, description="重命名后的新书籍ID")
    new_title: Optional[str] = Field(None, description="重命名后的新标题")
    new_file_path: Optional[str] = Field(None, description="重命名后的新文件路径")
    new_cover_path: Optional[str] = Field(None, description="重命名后的新封面路径")
