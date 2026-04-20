"""发音获取API端点 - 支持本地缓存"""
import os
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Query
import httpx

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.models.database_models import User


router = APIRouter()
settings = get_settings()


def _get_ecdict_path() -> str:
    """获取ECDICT数据库路径"""
    # 优先使用环境变量配置的路径
    env_path = os.getenv("ECDICT_DB_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    
    # 使用 settings.BASE_DIR（与 main.py 和 config.py 保持一致）
    return os.path.join(settings.BASE_DIR, "data", "ecdict.db")


def _get_audio_cache_dir() -> str:
    """获取音频缓存目录（放在 data 目录下）"""
    cache_dir = os.path.join(settings.BASE_DIR, "data", "word_audio")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _get_cached_audio_path(word: str, accent: str) -> str:
    """获取单词的本地缓存音频文件路径"""
    cache_dir = _get_audio_cache_dir()
    first_letter = word[0].lower() if word else 'a'
    word_dir = os.path.join(cache_dir, first_letter)
    os.makedirs(word_dir, exist_ok=True)
    return os.path.join(word_dir, f"{word}_{accent}.mp3")


def _get_base_dir() -> str:
    """获取项目根目录（复用 settings.BASE_DIR）"""
    return settings.BASE_DIR


def _check_local_cache(word: str, accent: str) -> tuple:
    """
    检查本地缓存
    返回: (是否存在, 缓存路径)
    """
    try:
        ecdict_path = _get_ecdict_path()
        if not os.path.exists(ecdict_path):
            return False, None

        conn = sqlite3.connect(ecdict_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT audio FROM stardict WHERE word = ? COLLATE NOCASE",
            (word,)
        )
        row = cursor.fetchone()
        conn.close()

        if row and row['audio']:
            base_dir = _get_base_dir()
            cached_path = os.path.join(base_dir, row['audio'])
            if os.path.exists(cached_path):
                return True, cached_path

        return False, None
    except Exception as e:
        print(f"检查本地缓存失败: {e}")
        return False, None


def _update_ecdict_audio(word: str, audio_path: str):
    """更新ECDICT数据库中的audio字段"""
    try:
        ecdict_path = _get_ecdict_path()
        # 将绝对路径转换为相对路径
        base_dir = _get_base_dir()
        relative_path = os.path.relpath(audio_path, base_dir)
        relative_path = relative_path.replace(os.sep, '/')  # 统一使用正斜杠

        conn = sqlite3.connect(ecdict_path)
        conn.execute(
            "UPDATE stardict SET audio = ? WHERE word = ? COLLATE NOCASE",
            (relative_path, word)
        )
        conn.commit()
        conn.close()
        print(f"已更新 {word} 的缓存路径: {relative_path}")
    except Exception as e:
        print(f"更新数据库缓存路径失败: {e}")


@router.get("/{word}")
async def get_pronunciation(
    word: str,
    accent: str = Query("uk", description="口音类型：'uk' 英式，'us' 美式"),
    force_refresh: bool = Query(False, description="强制刷新缓存"),
    current_user: User = Depends(get_current_user)
):
    """
    获取单词发音。

    策略：
    1. 优先检查本地缓存
    2. 缓存命中直接返回本地文件路径
    3. 未命中从有道API获取并缓存到本地

    Args:
        word: 要获取发音的单词
        accent: 口音类型，'uk' 或 'us'
        force_refresh: 是否强制刷新缓存

    Returns:
        包含发音音频URL的响应
    """
    word = word.lower().strip()

    if not word:
        raise HTTPException(status_code=400, detail="单词不能为空")

    # 1. 检查本地缓存
    if not force_refresh:
        cached_exists, cached_path = _check_local_cache(word, accent)
        print(f"[DEBUG pronunciation] 单词={word}, accent={accent}, cached_exists={cached_exists}, cached_path={cached_path}")
        if cached_exists and cached_path:
            audio_url = f"/audio/data/word_audio/{word[0]}/{word}_{accent}.mp3"
            print(f"[DEBUG pronunciation] 返回缓存音频URL: {audio_url}")
            return {
                "word": word,
                "audio_url": audio_url,
                "accent": accent,
                "cached": True
            }

    # 2. 从有道API获取音频
    type_map = {"uk": 1, "us": 2}
    voice_type = type_map.get(accent, 1)
    audio_url = f"http://dict.youdao.com/dictvoice?type={voice_type}&word={word}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 先检查URL是否可访问
            response = await client.head(audio_url)
            if response.status_code != 200:
                # 尝试备用口音
                fallback_type = 2 if voice_type == 1 else 1
                fallback_accent = "us" if accent == "uk" else "uk"
                fallback_url = f"http://dict.youdao.com/dictvoice?type={fallback_type}&word={word}"
                response = await client.head(fallback_url)
                if response.status_code == 200:
                    audio_url = fallback_url
                    accent = fallback_accent
                    voice_type = fallback_type
                else:
                    return {
                        "word": word,
                        "audio_url": None,
                        "accent": None,
                        "message": "未找到发音"
                    }

            # 3. 下载音频并缓存到本地
            download_response = await client.get(audio_url)
            if download_response.status_code == 200:
                audio_data = download_response.content
                cached_path = _get_cached_audio_path(word, accent)

                # 保存到本地
                with open(cached_path, 'wb') as f:
                    f.write(audio_data)

                # 4. 更新数据库
                _update_ecdict_audio(word, cached_path)

                # 返回本地文件路径
                return {
                    "word": word,
                    "audio_url": f"/audio/data/word_audio/{word[0]}/{word}_{accent}.mp3",
                    "accent": accent,
                    "cached": False
                }

            return {
                "word": word,
                "audio_url": None,
                "accent": None,
                "message": "下载发音失败"
            }

    except Exception as e:
        print(f"获取发音失败: {e}")
        return {
            "word": word,
            "audio_url": None,
            "accent": None,
            "message": f"获取发音失败: {str(e)}"
        }


# ==================== 管理接口 ====================
from fastapi import status


def _get_cache_stats() -> dict:
    """获取缓存统计信息"""
    try:
        cache_dir = _get_audio_cache_dir()
        total_files = 0
        total_size = 0
        accent_counts = {"uk": 0, "us": 0}

        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                if file.endswith('.mp3'):
                    total_files += 1
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    if '_uk.' in file:
                        accent_counts['uk'] += 1
                    elif '_us.' in file:
                        accent_counts['us'] += 1

        ecdict_path = _get_ecdict_path()
        db_cached_count = 0
        if os.path.exists(ecdict_path):
            conn = sqlite3.connect(ecdict_path)
            cursor = conn.execute(
                "SELECT COUNT(*) FROM stardict WHERE audio IS NOT NULL AND audio != ''"
            )
            db_cached_count = cursor.fetchone()[0]
            conn.close()

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "accent_counts": accent_counts,
            "db_recorded_count": db_cached_count,
            "cache_dir": cache_dir
        }
    except Exception as e:
        return {"error": str(e)}


def _cleanup_cache(max_age_days: int = 30) -> dict:
    """清理过期缓存文件"""
    try:
        import time
        cache_dir = _get_audio_cache_dir()
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600

        deleted_files = 0
        deleted_size = 0
        cleaned_db_records = 0

        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                if file.endswith('.mp3'):
                    file_path = os.path.join(root, file)
                    file_age = current_time - os.path.getmtime(file_path)

                    if file_age > max_age_seconds:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_files += 1
                        deleted_size += file_size

                        base_name = file[:-4]
                        if '_uk.' in base_name:
                            word = base_name.replace('_uk', '')
                        elif '_us.' in base_name:
                            word = base_name.replace('_us', '')
                        else:
                            continue

                        try:
                            ecdict_path = _get_ecdict_path()
                            if os.path.exists(ecdict_path):
                                conn = sqlite3.connect(ecdict_path)
                                relative_path = os.path.relpath(file_path, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                                relative_path = relative_path.replace(os.sep, '/')
                                conn.execute(
                                    "UPDATE stardict SET audio = NULL WHERE audio = ?",
                                    (relative_path,)
                                )
                                cleaned_db_records += conn.total_changes
                                conn.commit()
                                conn.close()
                        except Exception:
                            pass

        return {
            "deleted_files": deleted_files,
            "deleted_size_bytes": deleted_size,
            "deleted_size_mb": round(deleted_size / (1024 * 1024), 2),
            "cleaned_db_records": cleaned_db_records,
            "max_age_days": max_age_days
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/admin/cache/stats", tags=["admin"])
async def get_pronunciation_cache_stats(
    current_user: User = Depends(get_current_user)
):
    """获取单词发音缓存统计"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return _get_cache_stats()


@router.post("/admin/cache/cleanup", tags=["admin"])
async def cleanup_pronunciation_cache(
    max_age_days: int = Query(30, description="删除多少天前的缓存"),
    current_user: User = Depends(get_current_user)
):
    """清理过期的单词发音缓存"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return _cleanup_cache(max_age_days)


@router.delete("/admin/cache/all", tags=["admin"])
async def clear_all_pronunciation_cache(
    current_user: User = Depends(get_current_user)
):
    """清空所有单词发音缓存"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    try:
        cache_dir = _get_audio_cache_dir()
        deleted_files = 0
        deleted_size = 0

        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                if file.endswith('.mp3'):
                    file_path = os.path.join(root, file)
                    deleted_size += os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_files += 1

        ecdict_path = _get_ecdict_path()
        cleaned_db_records = 0
        if os.path.exists(ecdict_path):
            conn = sqlite3.connect(ecdict_path)
            cursor = conn.execute(
                "UPDATE stardict SET audio = NULL WHERE audio LIKE 'word_audio/%'"
            )
            cleaned_db_records = cursor.rowcount
            conn.commit()
            conn.close()

        return {
            "deleted_files": deleted_files,
            "deleted_size_bytes": deleted_size,
            "deleted_size_mb": round(deleted_size / (1024 * 1024), 2),
            "cleaned_db_records": cleaned_db_records,
            "message": "已清空所有单词发音缓存"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空缓存失败: {str(e)}"
        )
