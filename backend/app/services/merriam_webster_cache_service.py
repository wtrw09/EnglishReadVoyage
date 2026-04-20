"""韦氏词典缓存服务 - 离线缓存机制"""
import json
import os
import asyncio
import httpx
from typing import Optional, Dict, Any
from datetime import datetime

# 缓存数据库路径 - 使用相对于 backend 目录的路径
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DB_PATH = os.path.join(_BACKEND_DIR, "data", "merriam_webster_cache.db")
# 音频文件存储目录
AUDIO_DIR = os.path.join(_BACKEND_DIR, "data", "word_audio")


class MerriamWebsterCacheService:
    """韦氏词典缓存服务类"""

    def __init__(self):
        """初始化缓存服务"""
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保必要的目录存在"""
        os.makedirs(os.path.dirname(CACHE_DB_PATH), exist_ok=True)
        os.makedirs(AUDIO_DIR, exist_ok=True)

    def _get_connection(self):
        """获取SQLite连接"""
        import sqlite3
        conn = sqlite3.connect(CACHE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS merriam_webster_cache (
                    word TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    audio_filename TEXT,
                    cached_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get_from_cache(self, word: str) -> Optional[Dict[str, Any]]:
        """
        从缓存中查询单词

        Args:
            word: 要查询的单词（小写）

        Returns:
            缓存的词典数据，如果未命中返回 None
        """
        word = word.lower().strip()

        # 确保表存在
        self._init_db()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data_json, audio_filename FROM merriam_webster_cache WHERE word = ?",
                (word,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            data = json.loads(row["data_json"])

            # 如果有本地音频文件，替换音频URL
            if row["audio_filename"]:
                local_audio_path = f"/data/word_audio/{row['audio_filename']}"
                # 替换 phonetics 中的音频URL
                if "phonetics" in data:
                    for p in data["phonetics"]:
                        if p.get("audio"):
                            p["audio"] = local_audio_path
                # 替换主音频
                if data.get("phonetics") and len(data["phonetics"]) > 0:
                    for p in data["phonetics"]:
                        if p.get("audio"):
                            p["audio"] = local_audio_path
                            break

            return data
        except Exception as e:
            print(f"[MWCache] 查询缓存失败: {e}")
            return None
        finally:
            conn.close()

    async def save_to_cache(self, word: str, data: Dict[str, Any], audio_url: Optional[str] = None):
        """
        保存查询结果到缓存

        Args:
            word: 单词（小写）
            data: 词典数据（包含 phonetic, phonetics, meanings 等）
            audio_url: 音频URL（可选），会自动下载到本地
        """
        word = word.lower().strip()

        # 确保表存在
        self._init_db()

        # 下载音频（异步）
        audio_filename = None
        if audio_url:
            audio_filename = await self._download_audio(audio_url, word)

        # 构建要存储的数据
        cache_data = {
            "word": data.get("word", word),
            "phonetic": data.get("phonetic"),
            "phonetics": data.get("phonetics", []),
            "meanings": data.get("meanings", []),
            "source": data.get("source", "merriam-webster"),
            "thesaurus_synonyms": data.get("thesaurus_synonyms", []),
            "thesaurus_antonyms": data.get("thesaurus_antonyms", []),
            "idioms": data.get("idioms"),
        }

        now = datetime.now().isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO merriam_webster_cache (word, data_json, audio_filename, cached_at, updated_at)
                VALUES (?, ?, ?, COALESCE((SELECT cached_at FROM merriam_webster_cache WHERE word = ?), ?), ?)
            """, (word, json.dumps(cache_data, ensure_ascii=False), audio_filename, word, now, now))
            conn.commit()
            print(f"[MWCache] 已缓存单词: {word}, 音频: {audio_filename}")
        except Exception as e:
            print(f"[MWCache] 保存缓存失败: {e}")
        finally:
            conn.close()

    async def _download_audio(self, audio_url: str, word: str) -> Optional[str]:
        """
        下载音频文件到本地

        Args:
            audio_url: 音频URL
            word: 单词（用于命名文件）

        Returns:
            保存后的文件名，如果失败返回 None
        """
        # 生成文件名
        filename = f"{word}_us.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        # 如果文件已存在，直接返回
        if os.path.exists(filepath):
            return filename

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(audio_url)
                response.raise_for_status()

                with open(filepath, "wb") as f:
                    f.write(response.content)

                print(f"[MWCache] 已下载音频: {filename}")
                return filename
        except Exception as e:
            print(f"[MWCache] 下载音频失败: {audio_url}, 错误: {e}")
            return None

    def is_cached(self, word: str) -> bool:
        """检查单词是否已缓存"""
        word = word.lower().strip()
        self._init_db()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM merriam_webster_cache WHERE word = ?", (word,))
            return cursor.fetchone() is not None
        finally:
            conn.close()


# 全局单例
_cache_service: Optional[MerriamWebsterCacheService] = None


def get_cache_service() -> MerriamWebsterCacheService:
    """获取缓存服务单例"""
    global _cache_service
    if _cache_service is None:
        _cache_service = MerriamWebsterCacheService()
    return _cache_service
