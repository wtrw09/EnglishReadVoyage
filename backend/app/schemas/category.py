"""分类相关的Pydantic模式"""
from pydantic import BaseModel, Field
from typing import Optional


class CategoryBase(BaseModel):
    """分类基础模式"""
    name: str = Field(..., description="分类名称")


class CategoryCreate(CategoryBase):
    """创建分类请求"""
    pass


class CategoryUpdate(BaseModel):
    """更新分类请求"""
    name: str = Field(..., description="分类新名称")


class CategoryResponse(CategoryBase):
    """分类响应"""
    id: int = Field(..., description="分类ID")
    type: str = Field(..., description="分类类型：system 或 user")
    user_id: Optional[int] = Field(None, description="所属用户ID")

    class Config:
        from_attributes = True


class BookCategoryRequest(BaseModel):
    """书籍分类关联请求"""
    book_id: str = Field(..., description="书籍ID")
    category_id: int = Field(..., description="分类ID")


class BookWithCategory(BaseModel):
    """带分类信息的书籍"""
    id: str = Field(..., description="书籍ID")
    title: str = Field(..., description="书籍标题")
    level: str = Field(..., description="阅读等级")
    file_path: str = Field(..., description="书籍文件路径")
    page_count: int = Field(..., ge=0, description="书籍页数")
    cover_path: Optional[str] = Field(None, description="封面图片路径")
    is_read: int = Field(0, description="是否已读：0=未读, 1=已读")

    class Config:
        from_attributes = True


class BookGroup(BaseModel):
    """书籍分组（包含分组信息和该分组下的书籍）"""
    id: int = Field(..., description="分组ID")
    name: str = Field(..., description="分组名称")
    type: str = Field(..., description="分组类型")
    books: list[BookWithCategory] = Field(default_factory=list, description="该分组下的书籍列表")
