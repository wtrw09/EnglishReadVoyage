"""导入临时文件管理器"""
import os
import asyncio
import logging
import secrets
import shutil
import time
from pathlib import Path
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 内存注册表：token -> 元数据
_import_registry: dict[str, dict] = {}


def _get_temp_dir() -> Path:
    settings = get_settings()
    return Path(settings.IMPORT_TEMP_DIR)


async def ensure_temp_dir():
    _get_temp_dir().mkdir(parents=True, exist_ok=True)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


async def save_file(token: str, content: bytes, filename: str) -> Path:
    """保存单个文件到临时目录"""
    token_dir = _get_temp_dir() / token
    token_dir.mkdir(parents=True, exist_ok=True)
    file_path = token_dir / filename
    with open(file_path, 'wb') as f:
        f.write(content)
    _import_registry[token] = {
        "path": str(token_dir),
        "filenames": [filename],
        "created_at": time.time(),
        "file_type": "zip" if filename.endswith('.zip') else "md"
    }
    return file_path


async def save_files(token: str, files: list[tuple[bytes, str]]) -> list[Path]:
    """保存多个文件（批量MD用）"""
    token_dir = _get_temp_dir() / token
    token_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for content, filename in files:
        file_path = token_dir / filename
        with open(file_path, 'wb') as f:
            f.write(content)
        paths.append(file_path)
    _import_registry[token] = {
        "path": str(token_dir),
        "filenames": [fn for _, fn in files],
        "created_at": time.time(),
        "file_type": "batch_md"
    }
    return paths


async def read_file(token: str) -> tuple[bytes, str]:
    """读取单个文件，返回 (content, filename)"""
    meta = _import_registry.get(token)
    if not meta:
        raise FileNotFoundError(f"Token {token} 不存在或已过期")
    file_path = Path(meta["path"]) / meta["filenames"][0]
    with open(file_path, 'rb') as f:
        return (f.read(), meta["filenames"][0])


async def read_files(token: str) -> list[tuple[bytes, str]]:
    """读取所有文件（批量MD用），返回 [(content, filename), ...]"""
    meta = _import_registry.get(token)
    if not meta:
        raise FileNotFoundError(f"Token {token} 不存在或已过期")
    if meta["file_type"] == "zip":
        c, fn = await read_file(token)
        return [(c, fn)]
    result = []
    token_dir = Path(meta["path"])
    for filename in meta.get("filenames", []):
        file_path = token_dir / filename
        if file_path.exists():
            with open(file_path, 'rb') as f:
                result.append((f.read(), filename))
    return result


async def cleanup(token: str):
    """清理临时文件"""
    meta = _import_registry.pop(token, None)
    if meta:
        token_dir = Path(meta["path"])
        if token_dir.exists():
            shutil.rmtree(token_dir)
            logger.info(f"已清理临时文件: {token_dir}")


def get_meta(token: str) -> dict | None:
    return _import_registry.get(token)


async def cleanup_expired():
    """清理过期（>30分钟）的 token"""
    cutoff = time.time() - get_settings().IMPORT_TEMP_TTL_MINUTES * 60
    expired = [t for t, m in list(_import_registry.items()) if m["created_at"] < cutoff]
    for token in expired:
        await cleanup(token)
    if expired:
        logger.info(f"已清理 {len(expired)} 个过期的导入临时文件")
