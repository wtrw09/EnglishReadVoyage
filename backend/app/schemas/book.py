"""Book-related Pydantic schemas."""
from pydantic import BaseModel, Field
from typing import List


class BookInfo(BaseModel):
    """图书信息模式"""
    id: str = Field(..., description="Unique book identifier (MD5 hash of file path)")
    title: str = Field(..., description="Book title")
    level: str = Field(..., description="Reading level (e.g., 'E', 'F')")
    file_path: str = Field(..., description="Absolute path to the markdown file")
    page_count: int = Field(..., ge=0, description="Number of pages in the book")
    
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
    id: str = Field(..., description="Unique book identifier")
    title: str = Field(..., description="Book title")
    level: str = Field(..., description="Reading level")
    pages: List[str] = Field(..., description="List of HTML pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123def456",
                "title": "All About Coyotes",
                "level": "E",
                "pages": ["<h1>Page 1</h1><p>Content...</p>", "<h1>Page 2</h1>"]
            }
        }
