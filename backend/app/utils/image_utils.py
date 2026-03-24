"""图片处理工具函数"""
from PIL import Image
from pathlib import Path
from io import BytesIO
from typing import Optional, Tuple
import os


# 封面尺寸配置
# 封面用于列表(60x80px)和播放器(240x336px)，需要兼顾两者
# 采用2倍尺寸(480x672)确保播放器高清屏清晰
COVER_WIDTH = 480  # 宽480px (240*2)
COVER_HEIGHT = 672  # 高672px (336*2)
COVER_QUALITY = 80  # JPEG质量
WEBP_QUALITY = 80  # WebP质量

# 播放器大封面尺寸（已合并到主封面尺寸，此配置保留备用）
PLAYER_COVER_WIDTH = 480  # 宽480px (240*2)
PLAYER_COVER_HEIGHT = 672  # 高672px (336*2)


def compress_image(
    source: Path | bytes,
    target_path: Path,
    max_width: int = COVER_WIDTH,
    max_height: int = COVER_HEIGHT,
    quality: int = COVER_QUALITY,
    format: str = "JPEG"
) -> Tuple[bool, int]:
    """
    压缩图片并保存
    
    参数:
        source: 源图片路径或字节数据
        target_path: 目标保存路径
        max_width: 最大宽度
        max_height: 最大高度
        quality: 图片质量 (1-100)
        format: 输出格式 (JPEG, WEBP)
    
    返回:
        (是否成功, 压缩后文件大小bytes)
    """
    try:
        # 读取图片
        if isinstance(source, bytes):
            img = Image.open(BytesIO(source))
        else:
            img = Image.open(source)
        
        # 转换RGBA为RGB
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 按比例缩放，保持宽高比
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # 确保目标目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 根据格式保存
        if format.upper() == 'WEBP':
            # WebP格式，文件扩展名改为.webp
            if target_path.suffix.lower() != '.webp':
                target_path = target_path.with_suffix('.webp')
            img.save(target_path, 'WEBP', quality=quality, method=6)
        else:
            # 默认JPEG格式，渐进式编码
            img.save(target_path, 'JPEG', quality=quality, optimize=True, progressive=True)
        
        # 返回压缩后文件大小
        file_size = os.path.getsize(target_path)
        return True, file_size
        
    except Exception as e:
        print(f"压缩图片失败: {e}")
        return False, 0


def compress_cover(
    source: Path | bytes,
    target_path: Path,
    prefer_webp: bool = False
) -> Tuple[bool, int, str]:
    """
    压缩书籍封面图片
    
    参数:
        source: 源图片路径或字节数据
        target_path: 目标保存路径
        prefer_webp: 是否优先使用WebP格式
    
    返回:
        (是否成功, 压缩后文件大小bytes, 最终保存路径)
    """
    # 确定输出格式和路径
    if prefer_webp:
        output_format = 'WEBP'
        final_path = target_path.with_suffix('.webp')
    else:
        output_format = 'JPEG'
        final_path = target_path.with_suffix('.jpg')
    
    success, size = compress_image(
        source=source,
        target_path=final_path,
        max_width=COVER_WIDTH,
        max_height=COVER_HEIGHT,
        quality=COVER_QUALITY if output_format == 'JPEG' else WEBP_QUALITY,
        format=output_format
    )
    
    return success, size, final_path


def compress_player_cover(
    source: Path | bytes,
    target_path: Path,
    prefer_webp: bool = False
) -> Tuple[bool, int, str]:
    """
    压缩播放器大封面图片（2倍分辨率）
    
    参数:
        source: 源图片路径或字节数据
        target_path: 目标保存路径
        prefer_webp: 是否优先使用WebP格式
    
    返回:
        (是否成功, 压缩后文件大小bytes, 最终保存路径)
    """
    if prefer_webp:
        output_format = 'WEBP'
        final_path = target_path.with_suffix('.webp')
    else:
        output_format = 'JPEG'
        final_path = target_path.with_suffix('.jpg')
    
    success, size = compress_image(
        source=source,
        target_path=final_path,
        max_width=PLAYER_COVER_WIDTH,
        max_height=PLAYER_COVER_HEIGHT,
        quality=COVER_QUALITY if output_format == 'JPEG' else WEBP_QUALITY,
        format=output_format
    )
    
    return success, size, final_path


def get_image_size(source: Path | bytes) -> Optional[Tuple[int, int]]:
    """
    获取图片尺寸
    
    返回:
        (宽度, 高度) 或 None
    """
    try:
        if isinstance(source, bytes):
            img = Image.open(BytesIO(source))
        else:
            img = Image.open(source)
        return img.size
    except Exception:
        return None


def delete_existing_covers(book_folder: Path) -> None:
    """删除书籍目录下已存在的封面文件"""
    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
        existing = book_folder / f"cover{ext}"
        if existing.exists():
            existing.unlink()


def compress_to_webp(
    source: Path | bytes,
    target_path: Path,
    quality: int = WEBP_QUALITY
) -> Tuple[bool, int, Path]:
    """
    压缩图片并转换为WebP格式
    
    参数:
        source: 源图片路径或字节数据
        target_path: 目标保存路径（扩展名会自动改为.webp）
        quality: 图片质量 (1-100)
    
    返回:
        (是否成功, 压缩后文件大小bytes, 最终保存路径)
    """
    try:
        # 读取图片
        if isinstance(source, bytes):
            img = Image.open(BytesIO(source))
        else:
            img = Image.open(source)
        
        # 转换RGBA为RGB（WebP支持RGBA，但保持一致处理）
        if img.mode in ('RGBA', 'P'):
            # 对于透明图片，转换为RGB并添加白色背景
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 确保目标目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 设置WebP输出路径
        webp_path = target_path.with_suffix('.webp')
        
        # 保存为WebP格式
        img.save(webp_path, 'WEBP', quality=quality, method=6)
        
        # 返回压缩后文件大小
        file_size = os.path.getsize(webp_path)
        return True, file_size, webp_path
        
    except Exception as e:
        print(f"压缩并转换为WebP失败: {e}")
        return False, 0, target_path
