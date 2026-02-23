"""文件到数据库元数据同步服务"""
import os
import json
import hashlib
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.constants import MARKDOWN_EXTENSION
from app.repositories.book_repository import book_repository
from app.utils.parser import MarkdownParser

settings = get_settings()

class SyncService:
    """用于同步Books目录与SQLite数据库的服务"""

    def __init__(self):
        self.parser = MarkdownParser()

    async def sync_all(self, db: AsyncSession):
        """扫描Books目录并与数据库同步"""
        books_dir = settings.BOOKS_DIR
        if not os.path.exists(books_dir):
            print(f"Books directory not found: {books_dir}")
            return

        # 扫描书籍文件夹（ID_标题格式）
        for folder_name in os.listdir(books_dir):
            folder_path = os.path.join(books_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue

            # 查找index.md和meta.json
            index_path = os.path.join(folder_path, "index.md")
            meta_path = os.path.join(folder_path, "meta.json")

            if os.path.exists(index_path) and os.path.exists(meta_path):
                await self._sync_book(db, folder_path, index_path, meta_path)

    async def _sync_book(self, db: AsyncSession, folder_path: str, index_path: str, meta_path: str):
        """同步单本书籍的元数据"""
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            book_id = meta.get("id")
            if not book_id:
                print(f"Skipping {folder_path}: No ID in meta.json")
                return

            # 计算index.md的sync_hash
            with open(index_path, 'rb') as f:
                content = f.read()
                sync_hash = hashlib.md5(content).hexdigest()

            # 检查数据库中是否存在书籍
            existing_book = await book_repository.get(db, book_id)
            
            # 计算页面数
            pages = self.parser.parse_file(index_path)
            page_count = len(pages)

            book_data = {
                "id": book_id,
                "title": meta.get("title", "Unknown"),
                "author": meta.get("author"),
                "cover_path": os.path.join(folder_path, meta.get("cover_image", "cover.jpg")),
                "file_path": index_path,
                "page_count": page_count,
                "sync_hash": sync_hash
            }

            if not existing_book:
                await book_repository.create(db, book_data)
                print(f"Added new book: {book_data['title']}")
            elif existing_book.sync_hash != sync_hash or existing_book.file_path != index_path:
                await book_repository.update(db, existing_book, book_data)
                print(f"Updated book: {book_data['title']}")
            
        except Exception as e:
            print(f"Error syncing book in {folder_path}: {e}")

sync_service = SyncService()
