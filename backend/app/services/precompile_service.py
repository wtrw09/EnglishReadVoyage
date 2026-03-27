"""书籍预编译缓存服务

将MD文件解析结果持久化到磁盘，实现三级缓存策略：
1. 内存LRU缓存（最快）
2. 磁盘预编译缓存（快）
3. 实时解析（兜底）
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from app.utils.parser import MarkdownParser
from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PrecompileResult:
    """预编译结果"""
    success: bool
    book_id: str
    message: str
    page_count: int = 0


@dataclass
class PrecompileStatus:
    """预编译状态统计"""
    total_books: int
    cached_books: int
    uncached_books: int
    cache_size_mb: float


class PrecompileService:
    """预编译缓存服务"""

    def __init__(self):
        self.settings = get_settings()
        self.parser = MarkdownParser()
        # 缓存目录: backend/.cache/compiled/
        self.cache_dir = Path(self.settings.BASE_DIR) / ".cache" / "compiled"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, book_id: str) -> Path:
        """获取书籍缓存目录路径"""
        return self.cache_dir / book_id

    def _get_pages_path(self, book_id: str) -> Path:
        """获取pages.json路径"""
        return self._get_cache_path(book_id) / "pages.json"

    def _get_meta_path(self, book_id: str) -> Path:
        """获取meta.json路径"""
        return self._get_cache_path(book_id) / "meta.json"

    def is_cache_valid(self, book_id: str, md_file_path: str) -> bool:
        """
        检查预编译缓存是否有效
        
        Args:
            book_id: 书籍ID
            md_file_path: MD文件路径
            
        Returns:
            缓存是否有效
        """
        meta_path = self._get_meta_path(book_id)
        pages_path = self._get_pages_path(book_id)

        # 检查文件是否存在
        if not meta_path.exists() or not pages_path.exists():
            return False

        try:
            # 读取元数据
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            # 检查MD文件的mtime是否匹配
            current_mtime = os.path.getmtime(md_file_path)
            cached_mtime = meta.get('file_mtime', 0)

            return abs(current_mtime - cached_mtime) < 1  # 允许1秒误差

        except Exception as e:
            logger.warning(f"检查缓存有效性失败 [{book_id}]: {e}")
            return False

    def load_from_cache(self, book_id: str) -> Optional[List[str]]:
        """
        从磁盘缓存加载预编译页面
        
        Args:
            book_id: 书籍ID
            
        Returns:
            解析后的HTML页面列表，如果缓存不存在则返回None
        """
        pages_path = self._get_pages_path(book_id)

        if not pages_path.exists():
            return None

        try:
            with open(pages_path, 'r', encoding='utf-8') as f:
                pages = json.load(f)
            logger.debug(f"从磁盘缓存加载书籍 [{book_id}]，共 {len(pages)} 页")
            return pages
        except Exception as e:
            logger.warning(f"加载磁盘缓存失败 [{book_id}]: {e}")
            return None

    def save_to_cache(self, book_id: str, md_file_path: str, pages: List[str]) -> bool:
        """
        保存预编译结果到磁盘缓存
        
        Args:
            book_id: 书籍ID
            md_file_path: MD文件路径
            pages: 解析后的HTML页面列表
            
        Returns:
            是否保存成功
        """
        cache_path = self._get_cache_path(book_id)
        cache_path.mkdir(parents=True, exist_ok=True)

        try:
            # 保存pages.json
            pages_path = self._get_pages_path(book_id)
            with open(pages_path, 'w', encoding='utf-8') as f:
                json.dump(pages, f, ensure_ascii=False)

            # 保存meta.json
            meta = {
                'book_id': book_id,
                'total_pages': len(pages),
                'file_mtime': os.path.getmtime(md_file_path),
                'compiled_at': datetime.now().isoformat()
            }
            meta_path = self._get_meta_path(book_id)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            logger.info(f"预编译缓存已保存 [{book_id}]，共 {len(pages)} 页")
            return True

        except Exception as e:
            logger.error(f"保存预编译缓存失败 [{book_id}]: {e}")
            return False

    def precompile_book(self, book_id: str, md_file_path: str, force: bool = False) -> PrecompileResult:
        """
        预编译单本书籍
        
        Args:
            book_id: 书籍ID
            md_file_path: MD文件路径
            force: 是否强制重新编译（忽略现有缓存）
            
        Returns:
            预编译结果
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(md_file_path):
                return PrecompileResult(
                    success=False,
                    book_id=book_id,
                    message=f"MD文件不存在: {md_file_path}"
                )

            # 检查缓存是否有效（非强制模式）
            if not force and self.is_cache_valid(book_id, md_file_path):
                meta_path = self._get_meta_path(book_id)
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                return PrecompileResult(
                    success=True,
                    book_id=book_id,
                    message="缓存已存在且有效",
                    page_count=meta.get('total_pages', 0)
                )

            # 执行解析
            logger.info(f"开始预编译书籍 [{book_id}]: {md_file_path}")
            pages = self.parser.parse_file(md_file_path)

            # 保存到缓存
            if self.save_to_cache(book_id, md_file_path, pages):
                return PrecompileResult(
                    success=True,
                    book_id=book_id,
                    message="预编译成功",
                    page_count=len(pages)
                )
            else:
                return PrecompileResult(
                    success=False,
                    book_id=book_id,
                    message="保存缓存失败",
                    page_count=len(pages)
                )

        except Exception as e:
            logger.error(f"预编译书籍失败 [{book_id}]: {e}")
            return PrecompileResult(
                success=False,
                book_id=book_id,
                message=f"预编译失败: {str(e)}"
            )

    def invalidate_cache(self, book_id: str) -> bool:
        """
        删除指定书籍的预编译缓存
        
        Args:
            book_id: 书籍ID
            
        Returns:
            是否删除成功
        """
        cache_path = self._get_cache_path(book_id)

        if not cache_path.exists():
            return True

        try:
            import shutil
            shutil.rmtree(cache_path)
            logger.info(f"已删除预编译缓存 [{book_id}]")
            return True
        except Exception as e:
            logger.error(f"删除预编译缓存失败 [{book_id}]: {e}")
            return False

    def get_cache_status(self, book_ids: List[str]) -> PrecompileStatus:
        """
        获取预编译缓存状态统计
        
        Args:
            book_ids: 书籍ID列表
            
        Returns:
            缓存状态统计
        """
        total = len(book_ids)
        cached = 0
        total_size = 0

        for book_id in book_ids:
            pages_path = self._get_pages_path(book_id)
            if pages_path.exists():
                cached += 1
                total_size += pages_path.stat().st_size

        return PrecompileStatus(
            total_books=total,
            cached_books=cached,
            uncached_books=total - cached,
            cache_size_mb=round(total_size / (1024 * 1024), 2)
        )

    def clear_all_cache(self) -> int:
        """
        清除所有预编译缓存
        
        Returns:
            清除的缓存数量
        """
        count = 0
        try:
            for item in self.cache_dir.iterdir():
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item)
                    count += 1
            logger.info(f"已清除所有预编译缓存，共 {count} 个")
        except Exception as e:
            logger.error(f"清除预编译缓存失败: {e}")
        return count


# 全局单例
precompile_service = PrecompileService()
