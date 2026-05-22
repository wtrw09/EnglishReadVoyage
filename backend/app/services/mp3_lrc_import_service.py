"""MP3+LRC 书籍导入服务"""
import os
import sys
import re
import json
import io
import hashlib
import asyncio
import subprocess
import zipfile
import shutil
import logging
from typing import List, Optional, Callable, Tuple
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC

from app.repositories.book_repository import book_repository
from app.models.database_models import Book, BookCategoryRel
from app.schemas.book import BookImportResponse

logger = logging.getLogger(__name__)


class Mp3LrcImportService:
    """MP3+LRC 配对书籍导入服务"""

    # 支持的二级标签元数据行前缀
    LRC_METADATA_PREFIXES = ('[al:', '[ar:', '[ti:', '[by:', '[re:', '[ve:', '[la:', '[offset:')

    @staticmethod
    def _get_ffmpeg_path() -> str:
        """获取 ffmpeg 可执行文件路径"""
        # Windows 本地开发：优先使用项目目录下的 ffmpeg.exe
        if sys.platform == "win32":
            local_ffmpeg = Path(__file__).parent.parent.parent / "ffmpeg.exe"
            if local_ffmpeg.exists():
                return str(local_ffmpeg)
        # Linux/Mac/Docker：使用系统 PATH 中的 ffmpeg
        return "ffmpeg"

    @staticmethod
    def check_ffmpeg_available() -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            path = Mp3LrcImportService._get_ffmpeg_path()
            result = subprocess.run([path, "-version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _detect_zip_encoding(zip_bytes: bytes) -> str:
        """
        检测 ZIP 文件名的编码（处理 Windows 中文 ZIP 的 GBK 编码问题）
        返回 'utf-8' 或 'gbk'
        """
        candidates = ['utf-8', 'gbk']
        best_enc = 'utf-8'
        best_score = float('inf')

        for enc in candidates:
            try:
                with zipfile.ZipFile(io.BytesIO(zip_bytes), metadata_encoding=enc) as zf:
                    names = zf.namelist()
            except (UnicodeDecodeError, Exception):
                continue

            # 计分：拉丁补充字符越少越好
            score = 0
            for name in names:
                for ch in name:
                    cp = ord(ch)
                    if 0x0080 <= cp <= 0x00FF:  # Latin-1 Supplement
                        score += 2
                    elif 0x2000 <= cp <= 0x206F:  # 通用排版符号
                        score += 1
                    elif cp > 0x00FF and cp < 0x4E00:  # 其他奇怪字符
                        score += 1
            if score < best_score:
                best_score = score
                best_enc = enc

        if best_enc != 'utf-8':
            logger.info(f"检测到 ZIP 编码为 {best_enc}（非 UTF-8）")
        return best_enc

    @staticmethod
    def parse_lrc_with_translation(lrc_content: str) -> List[dict]:
        """
        解析 LRC 格式歌词，分离中英文。

        LRC 格式参考（新概念英语 NCE1）：
            [mm:ss.xx]英文句子|中文翻译

        返回格式：
            [{
                "start_ms": int,
                "end_ms": int,
                "text": str,         # 纯英文
                "translation": str   # 中文翻译（可能为空）
            }]
        """
        lines = lrc_content.strip().split('\n')
        entries = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过元数据行
            if line.startswith(Mp3LrcImportService.LRC_METADATA_PREFIXES):
                continue

            # 解析时间戳 [mm:ss.xx] 或 [mm:ss.xxx]
            match = re.match(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)', line)
            if not match:
                continue

            minutes = int(match.group(1))
            seconds = float(match.group(2))
            text_content = match.group(3).strip()

            if not text_content:
                continue

            start_ms = int((minutes * 60 + seconds) * 1000)

            # 用 | 分隔中英文
            en_text, zh_text = Mp3LrcImportService._parse_line(text_content)

            # 跳过纯中文行（无英文内容）
            if not en_text:
                continue

            entries.append({
                "start_ms": start_ms,
                "text": en_text,
                "translation": zh_text or ""
            })

        # 计算每条的 end_ms
        for i in range(len(entries)):
            if i + 1 < len(entries):
                entries[i]["end_ms"] = entries[i + 1]["start_ms"]
            else:
                # 最后一条兜底：往后延伸5秒
                entries[i]["end_ms"] = entries[i]["start_ms"] + 5000

        return entries

    @staticmethod
    def _parse_line(text: str) -> Tuple[str, str]:
        """解析 LRC 单行文本，返回 (英文, 中文)"""
        if '|' in text:
            parts = text.split('|', 1)
            en = parts[0].strip()
            zh = parts[1].strip()
            return en, zh
        # 无 | 分隔符：检测是否含中文
        if Mp3LrcImportService._contains_chinese(text):
            return "", text.strip()  # 纯中文行，跳过
        return text.strip(), ""

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        """检测文本中是否包含中文字符"""
        return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))

    @staticmethod
    def extract_cover_from_mp3(mp3_path: Path) -> Optional[bytes]:
        """
        从 MP3 文件中提取封面图片（APIC 帧）
        返回图片二进制数据，或 None
        """
        try:
            audio = MP3(mp3_path)
            if audio.tags is None:
                return None
            for tag in audio.tags.values():
                if tag.FrameID == 'APIC':
                    return tag.data
        except Exception as e:
            logger.warning(f"提取封面失败 {mp3_path}: {e}")
        return None

    @staticmethod
    def cut_mp3_segment(mp3_path: Path, output_path: Path, start_ms: int, end_ms: int) -> Optional[float]:
        """
        使用 ffmpeg 从 MP3 中截取一段音频。

        使用 -c copy（stream copy）模式：
        - 不重新编码，速度快
        - 内存占用小，适合大文件
        - 精度在关键帧边界，对句子级 LRC 足够
        """
        start_sec = start_ms / 1000.0
        duration_sec = (end_ms - start_ms) / 1000.0

        if duration_sec <= 0:
            return None

        try:
            ffmpeg_path = Mp3LrcImportService._get_ffmpeg_path()
            result = subprocess.run([
                ffmpeg_path, "-y",
                "-ss", f"{start_sec:.3f}",
                "-i", str(mp3_path),
                "-t", f"{duration_sec:.3f}",
                "-c", "copy",
                str(output_path)
            ], capture_output=True, timeout=60)

            if result.returncode != 0:
                logger.error(f"ffmpeg 切割失败: {result.stderr.decode()}")
                return None

            # 获取生成的音频时长
            try:
                audio = MP3(str(output_path))
                return audio.info.length
            except Exception as e:
                logger.warning(f"读取切割后音频时长失败: {e}")
                return duration_sec

        except subprocess.TimeoutExpired:
            logger.error(f"ffmpeg 超时: {mp3_path}")
            return None
        except FileNotFoundError:
            logger.error(f"ffmpeg 调用失败: {mp3_path}")
            return None

    async def import_mp3_lrc_book(
        self,
        db: AsyncSession,
        zip_bytes: bytes,
        original_filename: str,
        progress_callback: Optional[Callable] = None,
        category_id: Optional[int] = None,
        user_id: Optional[int] = None,
        skip_duplicates: bool = False,
        overwrite_book_ids: Optional[list] = None,
    ) -> BookImportResponse:
        """
        导入 MP3+LRC 配对的 ZIP 包。

        处理流程：
        1. 解压 ZIP → 扫描 mp3/lrc 配对 → 生成校验报告
        2. 逐个处理有效配对：
           - 创建书目录
           - 提取封面
           - 解析 LRC → 切割音频
           - 生成 sentences.json + markdown
        3. 写入数据库

        重复处理：
        - skip_duplicates=True 时跳过已存在的书籍
        - overwrite_book_ids 指定要覆盖的书籍ID列表，其他重复书籍会被跳过
        """
        async def update_progress(percentage: int, message: str):
            if progress_callback:
                await progress_callback(percentage, message)

        # 0. 检查 ffmpeg 是否可用
        if not self.check_ffmpeg_available():
            logger.error("ffmpeg 未安装，无法切割音频")
            return BookImportResponse(
                success=False,
                message="ffmpeg 未安装，请确保 Docker 环境已安装 ffmpeg",
                book_id="",
                title=""
            )

        # 1. 解压到临时目录
        temp_dir = Path("Books") / ".mp3_lrc_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 清理旧临时文件
        for item in temp_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)

        # 解压 ZIP
        try:
            # 检测 ZIP 文件名编码（Windows 中文 ZIP 常用 GBK）
            zip_encoding = self._detect_zip_encoding(zip_bytes)

            with zipfile.ZipFile(io.BytesIO(zip_bytes), metadata_encoding=zip_encoding) as zf:
                # 先验证所有文件路径，防止路径遍历攻击
                temp_dir_resolved = temp_dir.resolve()
                for name in zf.namelist():
                    # 跳过目录
                    if name.endswith('/'):
                        continue
                    target_path = (temp_dir / name).resolve()
                    if not str(target_path).startswith(str(temp_dir_resolved)):
                        logger.error(f"ZIP 包含非法路径: {name}")
                        return BookImportResponse(
                            success=False,
                            message=f"ZIP 包含非法路径: {name}",
                            book_id="",
                            title=""
                        )
                zf.extractall(temp_dir)
                logger.info(f"使用 {zip_encoding} 编码解压 ZIP 完成")
        except Exception as e:
            logger.error(f"解压ZIP失败: {e}")
            # 清理临时文件
            shutil.rmtree(temp_dir, ignore_errors=True)
            return BookImportResponse(
                success=False,
                message=f"解压ZIP文件失败: {e}",
                book_id="",
                title=""
            )

        try:
            await update_progress(10, "正在扫描 MP3/LRC 配对...")

            # 2. 扫描 mp3/lrc 文件，按文件名（不含扩展名）分组
            pairs = self._scan_mp3_lrc_pairs(temp_dir)

            valid_pairs = pairs["valid"]
            missing_lrc = pairs["missing_lrc"]
            missing_mp3 = pairs["missing_mp3"]

            if not valid_pairs:
                msg = "未找到有效的 MP3+LRC 配对"
                if missing_lrc:
                    msg += f"，{len(missing_lrc)} 个文件缺少 LRC"
                if missing_mp3:
                    msg += f"，{len(missing_mp3)} 个文件缺少 MP3"
                return BookImportResponse(
                    success=False,
                    message=msg,
                    book_id="",
                    title=""
                )

            # 3. 处理配对
            book_ids = []
            success_count = 0
            fail_count = 0
            skipped_count = 0
            total = len(valid_pairs)

            for idx, pair in enumerate(valid_pairs):
                try:
                    mp3_path = pair["mp3"]
                    lrc_path = pair["lrc"]
                    # 使用文件名（不含扩展名）作为书名，空格替换为下划线
                    book_name = mp3_path.stem.replace(" ", "_")
                    book_id = hashlib.md5(book_name.encode()).hexdigest()

                    progress_base = 20 + int((idx / total) * 70)
                    await update_progress(
                        progress_base,
                        f"正在处理 [{idx + 1}/{total}]: {book_name}"
                    )

                    # 重复检查：查看数据库中有无此书籍
                    existing_book = await book_repository.get(db, book_id)
                    if existing_book:
                        if skip_duplicates:
                            logger.info(f"跳过已存在的书籍: {book_name} (skip_duplicates=True)")
                            skipped_count += 1
                            continue
                        if overwrite_book_ids is not None and len(overwrite_book_ids) > 0:
                            if book_id not in overwrite_book_ids:
                                logger.info(f"跳过已存在的书籍: {book_name} (不在overwrite列表中)")
                                skipped_count += 1
                                continue
                            # 在覆盖列表中，继续执行覆盖逻辑
                            logger.info(f"覆盖已存在的书籍: {book_name}")
                            book_dir = Path("Books") / book_name
                            if book_dir.exists():
                                shutil.rmtree(book_dir, ignore_errors=True)
                        else:
                            # 与 book_service 保持一致：默认返回错误，不静默覆盖
                            logger.warning(f"书籍已存在但未设置重复处理参数: {book_name}")
                            fail_count += 1
                            continue
                    else:
                        book_dir = Path("Books") / book_name

                    # 创建书籍目录
                    book_dir.mkdir(parents=True, exist_ok=True)
                    audio_dir = book_dir / "audio"
                    audio_dir.mkdir(parents=True, exist_ok=True)

                    # 提取封面
                    cover_data = self.extract_cover_from_mp3(mp3_path)
                    cover_path = None
                    if cover_data:
                        cover_file = book_dir / "cover.jpg"
                        with open(cover_file, "wb") as f:
                            f.write(cover_data)
                        cover_path = f"/books/{book_name}/cover.jpg"

                    # 解析 LRC
                    lrc_content = lrc_path.read_text(encoding='utf-8', errors='ignore')
                    sentences = self.parse_lrc_with_translation(lrc_content)

                    if not sentences:
                        logger.warning(f"LRC 为空或无有效内容: {lrc_path}")
                        shutil.rmtree(book_dir, ignore_errors=True)
                        fail_count += 1
                        continue

                    # 切割每个句子的音频
                    sentence_items = []
                    total_sentences = len(sentences)

                    for sent_idx, sent in enumerate(sentences):
                        text = sent["text"]
                        text_hash = hashlib.md5(text.encode()).hexdigest()
                        audio_filename = f"{text_hash}.mp3"
                        audio_path = audio_dir / audio_filename

                        # 使用线程池执行 ffmpeg，避免阻塞事件循环
                        duration = await asyncio.to_thread(
                            self.cut_mp3_segment,
                            mp3_path, audio_path, sent["start_ms"], sent["end_ms"]
                        )
                        if duration is None or duration <= 0:
                            logger.warning(f"切割音频失败或时长为0: {text}")
                            continue

                        sentence_items.append({
                            "page": 0,
                            "index": sent_idx,
                            "text": text,
                            "translation": sent["translation"],
                            "audio_file": audio_filename,
                            "duration": round(duration, 2)
                        })

                    if not sentence_items:
                        shutil.rmtree(book_dir, ignore_errors=True)
                        fail_count += 1
                        continue

                    # 生成 sentences.json
                    sentences_json = {"sentences": sentence_items}
                    sentences_path = audio_dir / "sentences.json"
                    with open(sentences_path, 'w', encoding='utf-8') as f:
                        json.dump(sentences_json, f, ensure_ascii=False, indent=2)

                    # 生成 markdown 文件（纯英文，单页）
                    all_texts = [s["text"] for s in sentence_items]
                    md_content = "\n\n".join(all_texts)
                    md_path = book_dir / f"{book_name}.md"
                    with open(md_path, 'w', encoding='utf-8') as f:
                        f.write(md_content)

                    # 写入数据库
                    page_count = 1  # 单页模式
                    book_data = {
                        "id": book_id,
                        "title": book_name,
                        "author": "",
                        "cover_path": cover_path,
                        "file_path": f"Books/{book_name}/{book_name}.md",
                        "page_count": page_count
                    }

                    existing_book = await book_repository.get(db, book_id)
                    if existing_book:
                        await book_repository.update(db, existing_book, book_data)
                    else:
                        await book_repository.create(db, book_data)

                    # 关联分类
                    if category_id and user_id:
                        rel = BookCategoryRel(
                            book_id=book_id,
                            category_id=category_id,
                            user_id=user_id
                        )
                        db.add(rel)

                    book_ids.append(book_id)
                    success_count += 1

                except Exception as e:
                    logger.error(f"处理配对失败 {pair}: {e}")
                    fail_count += 1

            # 清理临时文件（正常路径）
            shutil.rmtree(temp_dir, ignore_errors=True)

            await update_progress(95, f"导入完成: 成功 {success_count} 本, 跳过 {skipped_count} 本, 失败 {fail_count} 本")

            total_pairs = len(valid_pairs)
            if success_count > 0:
                msg = (f"导入完成! 成功 {success_count} 本"
                       f"{f', 跳过 {skipped_count} 本' if skipped_count > 0 else ''}"
                       f"{f', 失败 {fail_count} 本' if fail_count > 0 else ''}"
                       f"{f', {len(missing_lrc)} 个缺LRC' if missing_lrc else ''}"
                       f"{f', {len(missing_mp3)} 个缺MP3' if missing_mp3 else ''}"
                       f"。翻译已从LRC提取，中文语音可通过「补充中文语音」功能生成")
                return BookImportResponse(
                    success=True,
                    message=msg,
                    book_id=book_ids[0] if len(book_ids) == 1 else "",
                    book_ids=book_ids,
                    title=valid_pairs[0]["mp3"].stem if valid_pairs else ""
                )
            elif skipped_count > 0 and success_count == 0:
                return BookImportResponse(
                    success=False,
                    message=f"跳过 {skipped_count} 本已存在的书籍，无新书导入",
                    book_id="",
                    title=""
                )
            else:
                return BookImportResponse(
                    success=False,
                    message=f"导入失败，{fail_count} 本书处理出错",
                    book_id="",
                    title=""
                )
        finally:
            # 确保临时文件始终被清理（即使中间发生异常）
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def check_mp3_lrc_duplicates(
        self,
        db: AsyncSession,
        zip_bytes: bytes,
    ) -> dict:
        """
        检查MP3+LRC ZIP包中的书籍是否已存在。
        与 check_zip_all / check_md_duplicates 返回格式一致。

        返回:
        {
            "has_duplicates": bool,
            "duplicate_books": [{"title": str, "book_id": str}, ...],
            "new_books": [{"title": str, "book_id": str}, ...],
            "total_books": int,
            "message": str
        }
        """
        result = {
            "has_duplicates": False,
            "duplicate_books": [],
            "new_books": [],
            "total_books": 0,
            "message": ""
        }

        temp_dir = Path("Books") / ".mp3_lrc_temp_check"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 清理旧临时文件
            for item in temp_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)

            # 解压ZIP
            zip_encoding = self._detect_zip_encoding(zip_bytes)
            with zipfile.ZipFile(io.BytesIO(zip_bytes), metadata_encoding=zip_encoding) as zf:
                temp_dir_resolved = temp_dir.resolve()
                for name in zf.namelist():
                    if name.endswith('/'):
                        continue
                    target_path = (temp_dir / name).resolve()
                    if not str(target_path).startswith(str(temp_dir_resolved)):
                        return {**result, "message": f"ZIP包含非法路径: {name}"}
                zf.extractall(temp_dir)

            # 扫描MP3/LRC配对
            pairs = self._scan_mp3_lrc_pairs(temp_dir)
            valid_pairs = pairs["valid"]

            if not valid_pairs:
                return {**result, "message": "未找到有效的MP3+LRC配对"}

            result["total_books"] = len(valid_pairs)

            for pair in valid_pairs:
                mp3_path = pair["mp3"]
                book_name = mp3_path.stem.replace(" ", "_")
                book_id = hashlib.md5(book_name.encode()).hexdigest()

                existing_book = await book_repository.get(db, book_id)

                book_info = {"title": book_name}

                if existing_book:
                    book_info["book_id"] = book_id
                    result["duplicate_books"].append(book_info)
                else:
                    book_info["book_id"] = None
                    result["new_books"].append(book_info)

            result["has_duplicates"] = len(result["duplicate_books"]) > 0

            if result["has_duplicates"]:
                result["message"] = f"共 {result['total_books']} 个配对，{len(result['duplicate_books'])} 个已存在"
            else:
                result["message"] = "所有书籍均可导入（无重复）"

        except Exception as e:
            logger.error(f"检查MP3+LRC重复失败: {e}")
            result["message"] = f"检查失败: {str(e)}"
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

        return result

    @staticmethod
    def _scan_mp3_lrc_pairs(directory: Path) -> dict:
        """
        扫描目录下的 MP3 和 LRC 文件，按文件名配对。

        返回:
        {
            "valid": [{"mp3": Path, "lrc": Path}, ...],
            "missing_lrc": [Path, ...],    # 有MP3但无LRC
            "missing_mp3": [Path, ...]     # 有LRC但无MP3
        }
        """
        mp3_files = {}
        lrc_files = {}

        # 递归扫描所有文件
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                if file_path.suffix.lower() == '.mp3':
                    stem = file_path.stem
                    mp3_files[stem] = file_path
                elif file_path.suffix.lower() == '.lrc':
                    stem = file_path.stem
                    lrc_files[stem] = file_path

        valid = []
        missing_lrc = []
        missing_mp3 = []

        # 找有效配对
        all_stems = set(mp3_files.keys()) | set(lrc_files.keys())
        for stem in all_stems:
            has_mp3 = stem in mp3_files
            has_lrc = stem in lrc_files
            if has_mp3 and has_lrc:
                valid.append({"mp3": mp3_files[stem], "lrc": lrc_files[stem]})
            elif has_mp3 and not has_lrc:
                missing_lrc.append(mp3_files[stem])
            else:
                missing_mp3.append(lrc_files[stem])

        return {
            "valid": valid,
            "missing_lrc": missing_lrc,
            "missing_mp3": missing_mp3
        }


mp3_lrc_import_service = Mp3LrcImportService()
