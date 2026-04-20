"""书籍管理API端点。"""
import asyncio
import io
import zipfile
import os
import json
import logging
from pathlib import Path
import hashlib
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query, Path as FastAPIPath, Body
from fastapi.responses import StreamingResponse
from typing import List, Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.schemas.book import BookInfo, BookDetail, BookImportResponse, BookUpdateRequest, BookUpdateResponse, BookPagesResponse, BookRenameRequest, BookRenameResponse, TranslationStatusResponse, RetryTranslateResponse, UpdateSentenceTranslationRequest, UpdateSentenceTranslationResponse, SentencePreviewResponse, SentenceUpdateRequest, SentenceUpdateResponse, BookSentencesResponse
from app.services.book_service import book_service, get_effective_translation_api_config, get_cancel_event, clear_cancel_event
from app.services.precompile_service import precompile_service
from app.core.database import get_db
from app.utils.sse_utils import format_sse_message
from app.api.dependencies import get_current_user, get_current_admin
from app.models.database_models import User
from app.core.config import get_settings


# ========== SSE 生成器辅助函数 ==========


def create_progress_callback(queue: asyncio.Queue):
    """
    创建进度回调函数

    参数:
        queue: asyncio.Queue 实例，用于存储进度消息

    返回:
        进度回调函数
    """
    async def progress_callback(percentage: int, message: str, book_title: str = None, book_index: int = 0, total_books: int = 0):
        data = {"percentage": percentage, "message": message}
        if book_title:
            data["book_title"] = book_title
        if book_index:
            data["book_index"] = book_index
        if total_books:
            data["total_books"] = total_books
        await queue.put(data)
    return progress_callback


def create_progress_callback_with_extra(queue: asyncio.Queue, extra_fields: dict):
    """
    创建带额外字段的进度回调函数

    参数:
        queue: asyncio.Queue 实例
        extra_fields: 额外的字段字典

    返回:
        进度回调函数
    """
    async def progress_callback(percentage: int, message: str, **extra):
        data = {"percentage": percentage, "message": message}
        data.update(extra_fields)
        data.update(extra)
        await queue.put(data)
    return progress_callback


def create_sse_stream_generator(
    queue: asyncio.Queue,
    task: asyncio.Task,
    final_message: str = "任务完成",
    error_message: str = "任务执行失败"
):
    """
    创建 SSE 流响应生成器

    参数:
        queue: asyncio.Queue 实例
        task: 已创建的任务对象（asyncio.Task）
        final_message: 完成时的消息
        error_message: 错误消息

    返回:
        异步生成器
    """
    async def event_generator():
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=0.5)
                # 构建额外的参数（排除 percentage 和 message）
                extra = {k: v for k, v in data.items() if k not in ("percentage", "message")}
                sse_msg = format_sse_message(data.get("percentage", 0), data.get("message", ""), **extra)
                yield sse_msg
            except asyncio.TimeoutError:
                if task.done():
                    try:
                        result = task.result()
                        if hasattr(result, "success") and hasattr(result, "message"):
                            yield format_sse_message(100, result.message, result.success)
                        elif hasattr(result, "success"):
                            yield format_sse_message(100, final_message, result.success)
                        else:
                            yield format_sse_message(100, final_message, True)
                    except Exception as e:
                        yield format_sse_message(0, f"{error_message}: {str(e)}", False)
                    break

    # 返回调用的结果（async generator对象），不是函数本身
    return event_generator()



router = APIRouter()

# 获取项目根目录（backend目录）
# books.py 在 backend/app/api/v1/endpoints/，往上5层是backend
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
BOOKS_DIR = PROJECT_ROOT / "Books"


@router.get("", response_model=List[BookInfo])
@router.get("/", response_model=List[BookInfo])
async def list_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有可用书籍列表。"""
    return await book_service.list_books(db)


@router.get("/check/{filename}")
async def check_book_exists(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查书籍是否已存在"""
    # 从文件名提取book_title
    safe_name = Path(filename).stem.replace(" ", "_")

    # 直接从数据库查询是否存在该标题的书籍
    from sqlalchemy import select
    from app.models.database_models import Book
    stmt = select(Book).where(Book.title == safe_name)
    result = await db.execute(stmt)
    existing_book = result.scalar_one_or_none()

    if existing_book:
        return {"exists": True, "book_id": existing_book.id, "title": existing_book.title}

    return {"exists": False}


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取书籍详细信息，包括所有页面。"""
    book = await book_service.get_book_detail(db, book_id)

    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    return book


@router.get("/{book_id}/pages", response_model=BookPagesResponse)
async def get_book_pages(
    book_id: str,
    start_page: int = Query(0, ge=0, description="起始页索引"),
    end_page: Optional[int] = Query(None, ge=0, description="结束页索引（不包含）"),
    chunk_size: int = Query(10, ge=1, le=20, description="单次请求最大页数（1-20）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """分页获取书籍内容，支持渐进式预加载和智能分片传输"""
    # 限制单次请求大小，防止响应过大
    if end_page and (end_page - start_page) > chunk_size:
        end_page = start_page + chunk_size
    
    result = await book_service.get_book_pages(db, book_id, start_page, end_page)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    return result


@router.post("/import")
async def import_book(
    file: UploadFile = File(...),
    category_id: Optional[int] = Query(None),
    skip_duplicates: Optional[bool] = Query(False, description="跳过已存在的书籍"),
    overwrite_book_ids: Optional[str] = Query(None, description="指定要覆盖的书籍ID列表，逗号分隔"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    导入书籍文件（仅管理员可用）。
    支持MD和ZIP格式。
    使用SSE推送导入进度。
    可选传入category_id将书籍添加到指定分类。
    skip_duplicates为True时跳过已存在的书籍。
    overwrite_book_ids指定要覆盖的书籍ID，其他重复书籍会被跳过。
    """
    # 检查文件扩展名
    if not file.filename.endswith('.md') and not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 .md 或 .zip 格式的文件"
        )

    # 读取文件内容
    content = await file.read()

    # 解析要覆盖的书籍ID列表
    overwrite_ids = None
    if overwrite_book_ids:
        overwrite_ids = [id.strip() for id in overwrite_book_ids.split(',') if id.strip()]

    # 使用生成器推送SSE进度
    async def event_generator():
        # 存储进度消息用于异步回调
        queue = asyncio.Queue()
        progress_callback = create_progress_callback(queue)

        # 启动后台任务运行导入（不生成音频，让用户选择是否生成）
        import_task = asyncio.create_task(
            book_service.import_book_with_progress(
                db=db,
                file_content=content,
                original_filename=file.filename,
                progress_callback=progress_callback,
                generate_audio=False,
                skip_duplicates=skip_duplicates,
                overwrite_book_ids=overwrite_ids
            )
        )

        # 持续发送进度直到完成
        result = None
        while True:
            try:
                # 等待进度消息，带超时以检查任务是否完成
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield format_sse_message(data['percentage'], data['message'])
                except asyncio.TimeoutError:
                    pass

                # 检查任务是否完成
                if import_task.done():
                    try:
                        result = import_task.result()
                    except Exception as e:
                        yield format_sse_message(0, f"导入失败: {str(e)}", False)
                    break
            except Exception as e:
                logger.error(f"SSE error: {e}")
                break

        # 发送最终结果
        if result and result.success:
            # 如果传入了category_id，添加书籍到分类
            if category_id:
                try:
                    from app.services.category_service import category_service
                    # 处理批量导入的多个书籍ID
                    book_ids_to_add = result.book_ids if result.book_ids else [result.book_id] if result.book_id else []
                    for bid in book_ids_to_add:
                        if bid:  # 确保book_id不为空
                            await category_service.add_book_to_category(
                                db, bid, category_id, admin.id
                            )
                except Exception as e:
                    logger.error(f"添加书籍到分类失败: {e}")

            # 如果没有指定分类，自动创建"未分组"分类关联
            if not category_id:
                try:
                    from app.services.category_service import category_service
                    from app.models.database_models import Category, BookCategoryRel
                    from sqlalchemy import select

                    # 查找或创建"未分组"分类
                    stmt = select(Category).where(
                        Category.name == "未分组",
                        Category.type == "user",
                        Category.user_id == admin.id
                    )
                    result_cat = await db.execute(stmt)
                    ungrouped_cat = result_cat.scalar_one_or_none()

                    if not ungrouped_cat:
                        # 创建"未分组"分类
                        ungrouped_cat = Category(
                            name="未分组",
                            type="user",
                            user_id=admin.id
                        )
                        db.add(ungrouped_cat)
                        await db.commit()
                        await db.refresh(ungrouped_cat)

                    # 为书籍创建关联
                    book_ids_to_link = result.book_ids if result.book_ids else [result.book_id] if result.book_id else []
                    for bid in book_ids_to_link:
                        if bid:
                            # 检查是否已有关联
                            existing_stmt = select(BookCategoryRel).where(
                                BookCategoryRel.book_id == bid,
                                BookCategoryRel.user_id == admin.id
                            )
                            existing_result = await db.execute(existing_stmt)
                            existing_rel = existing_result.scalar_one_or_none()

                            if not existing_rel:
                                await category_service.add_book_to_category(
                                    db, bid, ungrouped_cat.id, admin.id
                                )
                except Exception as e:
                    logger.error(f"创建未分组关联失败: {e}")

            # 构建返回的book_id字符串（单本用book_id，多本用逗号分隔）
            return_book_id = result.book_id if result.book_id else ",".join(result.book_ids) if result.book_ids else ""
            yield format_sse_message(100, result.message, True, return_book_id)
        elif result:
            yield format_sse_message(0, result.message, False)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/import/overwrite")
async def import_book_overwrite(
    file: UploadFile = File(...),
    book_id: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    logger.info(f"Overwrite import called with book_id: {book_id}, category_id: {category_id}")
    """
    覆盖导入书籍（仅管理员可用）。
    删除旧内容，保存新内容，不生成音频。
    使用SSE推送导入进度。
    可选传入category_id将书籍添加到指定分类。
    """
    # 检查文件扩展名
    if not file.filename.endswith('.md') and not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 .md 或 .zip 格式的文件"
        )

    # 读取文件内容
    content = await file.read()

    # 使用生成器推送SSE进度
    async def event_generator():
        # 存储进度消息用于异步回调
        queue = asyncio.Queue()
        progress_callback = create_progress_callback(queue)

        # 启动后台任务运行导入
        import_task = asyncio.create_task(
            book_service.import_book_with_progress(
                db=db,
                file_content=content,
                original_filename=file.filename,
                progress_callback=progress_callback,
                generate_audio=False,  # 覆盖导入不生成音频
                overwrite=True,  # 标记为覆盖导入
                existing_book_id=book_id  # 传入已有书籍的book_id
            )
        )

        # 持续发送进度直到完成
        result = None
        while True:
            try:
                # 等待进度消息，带超时以检查任务是否完成
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield format_sse_message(data['percentage'], data['message'])
                except asyncio.TimeoutError:
                    pass

                # 检查任务是否完成
                if import_task.done():
                    try:
                        result = import_task.result()
                    except Exception as e:
                        yield format_sse_message(0, f"导入失败: {str(e)}", False)
                    break
            except Exception as e:
                logger.error(f"SSE error: {e}")
                break

        # 发送最终结果
        if result and result.success:
            # 如果传入了category_id，添加书籍到分类
            if category_id:
                try:
                    from app.services.category_service import category_service
                    # 使用book_id参数传入的ID，或者使用result中的book_id
                    target_book_id = book_id if book_id else result.book_id
                    await category_service.add_book_to_category(
                        db, target_book_id, category_id, admin.id
                    )
                except Exception as e:
                    logger.error(f"添加书籍到分类失败: {e}")

            # 如果没有指定分类，自动创建"未分组"分类关联
            if not category_id:
                try:
                    from app.services.category_service import category_service
                    from app.models.database_models import Category, BookCategoryRel
                    from sqlalchemy import select

                    # 查找或创建"未分组"分类
                    stmt = select(Category).where(
                        Category.name == "未分组",
                        Category.type == "user",
                        Category.user_id == admin.id
                    )
                    result_cat = await db.execute(stmt)
                    ungrouped_cat = result_cat.scalar_one_or_none()

                    if not ungrouped_cat:
                        # 创建"未分组"分类
                        ungrouped_cat = Category(
                            name="未分组",
                            type="user",
                            user_id=admin.id
                        )
                        db.add(ungrouped_cat)
                        await db.commit()
                        await db.refresh(ungrouped_cat)

                    # 使用book_id参数传入的ID，或者使用result中的book_id
                    target_book_id = book_id if book_id else result.book_id
                    if target_book_id:
                        # 检查是否已有关联
                        existing_stmt = select(BookCategoryRel).where(
                            BookCategoryRel.book_id == target_book_id,
                            BookCategoryRel.user_id == admin.id
                        )
                        existing_result = await db.execute(existing_stmt)
                        existing_rel = existing_result.scalar_one_or_none()

                        if not existing_rel:
                            await category_service.add_book_to_category(
                                db, target_book_id, ungrouped_cat.id, admin.id
                            )
                except Exception as e:
                    logger.error(f"创建未分组关联失败: {e}")

            # 使用book_id参数传入的ID，或者使用result中的book_id
            target_book_id = book_id if book_id else result.book_id
            yield format_sse_message(100, result.message, True, target_book_id)
        elif result:
            yield format_sse_message(0, result.message, False)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{book_id}/regenerate-audio")
async def regenerate_book_audio(
    book_id: str,
    force: bool = Query(False, description="是否强制重新生成（覆盖已有音频）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重新生成书籍音频
    1. 获取书籍信息
    2. 删除现有音频文件夹内容
    3. 重新提取句子并生成音频
    """
    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 使用生成器推送SSE进度
    async def event_generator():
        queue = asyncio.Queue()
        progress_callback = create_progress_callback(queue)

        # 启动后台任务
        regen_task = asyncio.create_task(
            book_service.regenerate_audio(
                db=db,
                book_id=book_id,
                user_id=current_user.id,
                progress_callback=progress_callback,
                force=force
            )
        )

        # 使用统一的 SSE 生成器（异步迭代）
        async for sse_msg in create_sse_stream_generator(
            queue, regen_task, final_message="音频生成完成", error_message="生成失败"
        ):
            yield sse_msg

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{book_id}/regenerate-audio-bilingual")
async def regenerate_book_audio_bilingual(
    book_id: str,
    force: bool = Query(False, description="是否强制重新生成（覆盖已有内容）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重新生成书籍中英文音频
    1. 获取用户翻译API配置
    2. 翻译每个句子为中文
    3. 生成英文和中文语音
    """
    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )
    
    # 使用生成器推送SSE进度
    async def event_generator():
        queue = asyncio.Queue()
        progress_callback = create_progress_callback(queue)
        
        try:
            # 启动后台任务
            regen_task = asyncio.create_task(
                book_service.regenerate_audio_bilingual(
                    db=db,
                    book_id=book_id,
                    user_id=current_user.id,
                    progress_callback=progress_callback,
                    force=force
                )
            )

            # 使用统一的 SSE 生成器（异步迭代）
            async for sse_msg in create_sse_stream_generator(
                queue, regen_task, final_message="双语音频生成完成", error_message="生成失败"
            ):
                yield sse_msg
                
        except Exception as e:
            yield format_sse_message(0, f"发生错误: {type(e).__name__}: {str(e)}", False)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{book_id}/generate-translation")
async def generate_book_translation(
    book_id: str,
    force: bool = Query(False, description="是否强制重新生成（覆盖已有翻译）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    生成句子翻译
    1. 获取用户翻译API配置
    2. 翻译每个句子为中文
    3. 保存到 sentences.json（不生成音频）
    """
    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )
    
    # 使用生成器推送SSE进度
    async def event_generator():
        queue = asyncio.Queue()
        progress_callback = create_progress_callback(queue)
        try:
            # 启动后台任务
            task = asyncio.create_task(
                book_service.generate_translation(
                    db=db,
                    book_id=book_id,
                    user_id=current_user.id,
                    progress_callback=progress_callback,
                    force=force
                )
            )

            # 使用统一的 SSE 生成器（异步迭代）
            async for sse_msg in create_sse_stream_generator(
                queue, task, final_message="翻译生成完成", error_message="生成失败"
            ):
                yield sse_msg
                
        except Exception as e:
            yield format_sse_message(0, f"发生错误: {type(e).__name__}: {str(e)}", False)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/{book_id}/check-chinese-audio")
async def check_chinese_audio(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    检查书籍是否已有中文音频
    返回: { "has_chinese_audio": true/false }
    """
    import json
    from pathlib import Path

    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 检查 sentences.json
    book_path = Path(book.file_path)
    book_folder = book_path.parent
    audio_folder = book_folder / "audio"
    mapping_path = audio_folder / "sentences.json"

    chinese_audio_count = 0
    english_audio_count = 0
    translation_count = 0
    total_sentences = 0

    if mapping_path.exists():
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sentences = data.get('sentences', [])
                total_sentences = len(sentences)
                # 统计中文音频数量（需要文件真实存在）
                chinese_audio_count = sum(
                    1 for s in sentences
                    if s.get('audio_file_zh') and (audio_folder / s['audio_file_zh']).exists()
                )
                # 统计英文音频数量（需要文件真实存在）
                english_audio_count = sum(
                    1 for s in sentences
                    if s.get('audio_file') and (audio_folder / s['audio_file']).exists()
                )
                # 统计翻译数量
                translation_count = sum(1 for s in sentences if s.get('translation'))
        except Exception as e:
            logger.error(f"读取sentences.json失败: {e}")

    return {
        "has_chinese_audio": chinese_audio_count > 0,
        "has_english_audio": english_audio_count > 0,
        "has_translation": translation_count > 0,
        "chinese_audio_count": chinese_audio_count,
        "english_audio_count": english_audio_count,
        "translation_count": translation_count,
        "total_sentences": total_sentences,
        "chinese_audio_complete": total_sentences > 0 and chinese_audio_count >= total_sentences,
        "english_audio_complete": total_sentences > 0 and english_audio_count >= total_sentences,
        "translation_complete": total_sentences > 0 and translation_count >= total_sentences
    }


@router.post("/{book_id}/generate-chinese-audio")
async def generate_book_chinese_audio(
    book_id: str,
    force: bool = Query(False, description="是否强制重新生成（覆盖已有音频）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    生成中文音频
    1. 检查现有 sentences.json 是否有翻译
    2. 若无翻译，先翻译所有句子
    3. 生成中文音频
    4. 更新 sentences.json
    force参数：True时强制重新生成所有音频，False时跳过已有音频
    """
    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 使用生成器推送SSE进度
    async def event_generator():
        queue = asyncio.Queue()
        progress_callback = create_progress_callback(queue)

        # 启动后台任务
        task = asyncio.create_task(
            book_service.generate_chinese_audio(
                db=db,
                book_id=book_id,
                user_id=current_user.id,
                progress_callback=progress_callback,
                force=force
            )
        )

        # 使用统一的 SSE 生成器（异步迭代）
        async for sse_msg in create_sse_stream_generator(
            queue, task, final_message="中文音频生成完成", error_message="生成失败"
        ):
            yield sse_msg

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{book_id}/cancel-audio-task")
async def cancel_audio_task(
    book_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    取消书籍的音频生成任务
    """
    try:
        # 获取取消事件并设置取消标志
        cancel_event = get_cancel_event(book_id)
        cancel_event.set()
        logger.info(f"[取消] 用户 {current_user.username} 请求取消书籍 {book_id} 的音频生成任务")
        return {"success": True, "message": "任务取消请求已发送"}
    except Exception as e:
        logger.error(f"[取消] 取消任务失败: {str(e)}")
        return {"success": False, "message": f"取消失败: {str(e)}"}


@router.get("/{book_id}/content")
async def get_book_content(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取书籍原始markdown内容"""
    content = await book_service.get_book_content(db, book_id)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )
    return {"content": content}


@router.get("/{book_id}/content-file")
async def get_book_content_from_file(
    book_id: str,
    db: AsyncSession = Depends(get_db)
):
    """直接从文件读取书籍内容（用于封面图片选择）"""
    from sqlalchemy import select
    from app.models.database_models import Book

    # 从数据库获取书籍信息
    stmt = select(Book).where(Book.id == book_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 直接读取文件内容
    import os
    file_path = book.file_path

    # 如果文件存在，直接读取
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"content": content}

    # 如果文件不存在，返回空
    return {"content": ""}


@router.put("/{book_id}/rename", response_model=BookRenameResponse)
async def rename_book(
    book_id: str,
    request: BookRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重命名书籍
    1. 更新数据库中的书籍标题和文件路径
    2. 重命名文件夹
    3. 重命名MD文件
    """
    result = await book_service.rename_book(db, book_id, request.new_title)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if "已存在" in result.message else status.HTTP_404_NOT_FOUND,
            detail=result.message
        )
    return result


@router.put("/{book_id}/cover")
async def update_book_cover(
    book_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新书籍封面
    
    如果 cover_path 指向 assets 目录下的图片，会将其压缩后复制到书籍根目录并重命名为 cover.jpg
    """
    from app.utils.image_utils import compress_cover, delete_existing_covers
    
    cover_path = request.get('cover_path') if request else None
    logger.info(f"update_book_cover called: book_id={book_id}, cover_path={cover_path}")
    
    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )
    
    book_path = Path(book.file_path)
    book_folder = book_path.parent
    
    # 如果 cover_path 指向 assets 目录下的图片，压缩后复制到根目录作为 cover.jpg
    if cover_path and '/assets/' in cover_path:
        # 解析路径获取书籍文件夹和文件名
        # cover_path 格式: /books/{book_name}/assets/{filename}
        try:
            # 提取 assets 中的文件名
            filename = cover_path.split('/assets/')[-1]
            source_image_path = book_folder / "assets" / filename
            
            if source_image_path.exists():
                # 删除已存在的封面文件
                delete_existing_covers(book_folder)
                
                # 压缩图片并保存为封面
                cover_target = book_folder / "cover.jpg"
                success, file_size, final_path = compress_cover(
                    source=source_image_path,
                    target_path=cover_target,
                    prefer_webp=False
                )
                
                if not success:
                    # 压缩失败，直接复制原文件
                    import shutil
                    final_path = book_folder / "cover.jpg"
                    shutil.copy2(source_image_path, final_path)
                    logger.warning(f"警告: 封面压缩失败，使用原始文件")
                else:
                    logger.info(f"封面压缩成功: {final_path}, 大小: {file_size / 1024:.1f}KB")
                
                # 更新 cover_path 为根目录下的封面
                cover_path = f"/books/{book_folder.name}/{final_path.name}"
                logger.info(f"已将 assets 图片压缩为封面: {cover_path}")
        except Exception as e:
            logger.error(f"处理封面图片失败: {e}")
    elif cover_path == '' or cover_path is None:
        # 清空封面，删除封面文件
        delete_existing_covers(book_folder)
    
    result = await book_service.update_book_cover(db, book_id, cover_path)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )
    return {"success": True, "message": "封面更新成功", "cover_path": cover_path}


@router.put("/{book_id}", response_model=BookUpdateResponse)
async def update_book(
    book_id: str,
    request: BookUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新书籍内容（仅管理员可用）"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以编辑书籍"
        )
    return await book_service.update_book(db, book_id, request.content)


@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除书籍及其所有资源"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以删除书籍"
        )

    try:
        result = await book_service.delete_book(db, book_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="书籍未找到"
            )
        return {"success": True, "message": "书籍删除成功"}
    except Exception as e:
        logger.error(f"删除书籍错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )


@router.post("/upload-cover")
async def upload_cover(
    file: UploadFile = File(...),
    book_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传书籍封面，自动压缩后保存为 cover.webp 在书籍根目录"""
    from app.utils.image_utils import compress_cover, delete_existing_covers
    
    # 读取文件内容
    content = await file.read()

    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 保存到书籍根目录
    book_path = Path(book.file_path)
    book_folder = book_path.parent

    # 删除已存在的封面文件（各种扩展名）
    delete_existing_covers(book_folder)

    # 压缩并保存封面（支持WebP格式）
    cover_target = book_folder / "cover.webp"
    success, file_size, final_path = compress_cover(
        source=content,
        target_path=cover_target,
        prefer_webp=True  # 使用WebP格式减小体积
    )
    
    if not success:
        # 压缩失败，尝试直接保存原文件
        cover_path = book_folder / "cover.webp"
        with open(cover_path, 'wb') as f:
            f.write(content)
        final_path = cover_path
        file_size = len(content)
        logger.warning(f"警告: 封面压缩失败，使用原始文件: {final_path}")
    else:
        logger.info(f"封面压缩成功: {final_path}, 大小: {file_size / 1024:.1f}KB")

    # 返回相对路径
    # 处理路径计算，确保返回正确的相对路径
    if final_path.is_absolute():
        try:
            relative_path = str(final_path.relative_to(BOOKS_DIR))
        except ValueError:
            # 如果相对路径计算失败，尝试其他方式
            relative_path = str(final_path.relative_to(PROJECT_ROOT / "Books"))
    else:
        # 相对路径，需要移除可能的前导 "Books\" 或 "Books/"
        relative_path = str(final_path)
        # 规范化为小写并替换各种格式
        relative_path = relative_path.replace("\\", "/")
        if relative_path.lower().startswith("books/"):
            relative_path = relative_path[6:]
    
    # 确保路径使用正斜杠
    relative_path = relative_path.replace("\\", "/")
    result_path = f"/books/{relative_path}"
    return {"path": result_path, "size": file_size}


@router.post("/{book_id}/upload-image")
async def upload_book_image(
    file: UploadFile = File(...),
    book_id: str = FastAPIPath(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传图片到书籍的assets目录
    支持 jpg, jpeg, png, gif, webp 等常见图片格式
    返回相对于书籍文件夹的路径，格式为 ./assets/filename
    """
    # 检查文件类型
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式，仅支持: {', '.join(allowed_extensions)}"
        )

    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 获取书籍文件夹路径
    # file_path 是相对路径，需要拼接 PROJECT_ROOT
    book_path = PROJECT_ROOT / book.file_path
    book_folder = book_path.parent
    assets_folder = book_folder / "assets"

    
    # 确保 assets 目录存在
    assets_folder.mkdir(exist_ok=True)
 
    # 生成简单的 image_X.ext 文件名（避免清理时被删除）
    existing_images = list(assets_folder.glob(f'image_*'))
    max_num = 0
    for img in existing_images:
        try:
            num = int(img.stem.split('_')[1])
            max_num = max(max_num, num)
        except (IndexError, ValueError):
            pass
    safe_filename = f"image_{max_num + 1}{file_ext}"
    target_path = assets_folder / safe_filename
  
    # 读取并保存文件
    content = await file.read()
    
    # 压缩并转换为WebP格式
    from app.utils.image_utils import compress_to_webp
    
    # 生成临时文件路径（用于压缩）
    temp_path = assets_folder / safe_filename
    
    try:
        success, file_size, final_path = compress_to_webp(
            source=content,
            target_path=temp_path
        )
        
        if success:
            logger.info(f"[UPLOAD] 图片压缩并转换为WebP成功: {final_path.name}, 大小: {file_size / 1024:.1f}KB")
            # 返回相对于 md 文件的路径（用于 Markdown）
            relative_path = f"./assets/{final_path.name}"
            return {
                "path": relative_path,
                "full_path": f"/books/{book_folder.name}/assets/{final_path.name}",
                "size": file_size,
                "filename": final_path.name
            }
        else:
            # 压缩失败，直接保存原文件
            raise Exception("WebP转换失败")
    except Exception as e:
        logger.warning(f"[UPLOAD] 图片压缩失败: {e}, 使用原始文件保存")
        with open(temp_path, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        
        file_size = len(content)
        relative_path = f"./assets/{safe_filename}"
        return {
            "path": relative_path,
            "full_path": f"/books/{book_folder.name}/assets/{safe_filename}",
            "size": file_size,
            "filename": safe_filename
        }


@router.post("/export")
async def export_books(
    request: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导出书籍为ZIP压缩包
    支持单本或多本导出
    请求体: {"book_ids": ["id1", "id2", ...]}
    """
    book_ids = request.get("book_ids", [])
    if not book_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少选择一本书籍"
        )

    # 获取所有要导出的书籍信息
    from sqlalchemy import select
    from app.models.database_models import Book

    books = []
    for book_id in book_ids:
        stmt = select(Book).where(Book.id == book_id)
        result = await db.execute(stmt)
        book = result.scalar_one_or_none()
        if book:
            books.append(book)

    if not books:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要导出的书籍"
        )

    # 创建内存中的ZIP文件
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for book in books:
            # 获取书籍文件夹路径
            book_path = Path(book.file_path)
            book_folder = book_path.parent

            if not book_folder.exists():
                continue

            # 每本书都放在自己的文件夹中，与批量导出格式保持一致
            prefix = f"{book.title}/"

            # 遍历书籍文件夹中的所有文件
            for root, dirs, files in os.walk(book_folder):
                for file in files:
                    file_path = Path(root) / file
                    # 计算在ZIP中的相对路径
                    arc_name = prefix + str(file_path.relative_to(book_folder))
                    try:
                        zf.write(file_path, arc_name)
                    except Exception as e:
                        logger.error(f"[Export Error] file_path={file_path}, arc_name={arc_name}, error={e}")
                        raise

    # 准备响应
    zip_buffer.seek(0)

    # 生成下载文件名
    if len(books) == 1:
        filename = f"{books[0].title}.zip"
    else:
        filename = f"books_export_{len(books)}_items.zip"

    # 对文件名进行URL编码
    from urllib.parse import quote
    encoded_filename = quote(filename)

    async def iter_bytes():
        """分块迭代zip数据，提高大文件下载速度"""
        chunk_size = 1024 * 1024  # 1MB chunks
        while True:
            chunk = zip_buffer.read(chunk_size)
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        iter_bytes(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Length": str(zip_buffer.getbuffer().nbytes)
        }
    )


@router.post("/check-integrity")
async def check_book_integrity(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    检查书籍资源完整性
    请求体: {"book_id": "xxx"} 或 {"book_ids": ["id1", "id2", ...]}
    返回: 每本书的完整性检查结果
    """
    book_ids = request.get("book_ids", [])
    single_book_id = request.get("book_id")

    if single_book_id:
        book_ids = [single_book_id]

    if not book_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供书籍ID"
        )

    from sqlalchemy import select
    from app.models.database_models import Book
    import json

    results = []

    for book_id in book_ids:
        stmt = select(Book).where(Book.id == book_id)
        result = await db.execute(stmt)
        book = result.scalar_one_or_none()

        if not book:
            results.append({
                "book_id": book_id,
                "exists": False,
                "message": "书籍不存在"
            })
            continue

        # 检查书籍文件夹
        book_path = Path(book.file_path)
        book_folder = book_path.parent

        if not book_folder.exists():
            results.append({
                "book_id": book_id,
                "title": book.title,
                "exists": True,
                "folder_exists": False,
                "message": "书籍文件夹不存在"
            })
            continue

        # 检查各个资源文件夹
        assets_folder = book_folder / "assets"
        audio_folder = book_folder / "audio"

        has_assets = assets_folder.exists() and any(assets_folder.iterdir())
        has_audio = audio_folder.exists() and any(audio_folder.iterdir())

        # 检查语音映射文件
        has_mapping = False
        mapping_file = audio_folder / "sentences.json"
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mapping = json.load(f)
                    has_mapping = len(mapping) > 0
            except Exception:
                pass  # 忽略JSON解析错误

        # 读取markdown内容检查图片引用
        missing_images = []
        if book_path.exists():
            try:
                with open(book_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    import re
                    # 查找所有本地图片引用
                    img_matches = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', content)
                    for img_path in img_matches:
                        # 只检查本地相对路径
                        if not img_path.startswith(('http://', 'https://', 'data:')):
                            # 解析相对路径
                            if img_path.startswith('./'):
                                full_path = book_folder / img_path[2:]
                            elif img_path.startswith('../'):
                                full_path = (book_folder / img_path).resolve()
                            else:
                                full_path = book_folder / img_path

                            if not full_path.exists():
                                missing_images.append(img_path)
            except Exception as e:
                logger.error(f"检查图片引用失败: {e}")

        # 判断完整性
        is_complete = has_assets and has_audio and has_mapping and len(missing_images) == 0

        results.append({
            "book_id": book_id,
            "title": book.title,
            "exists": True,
            "folder_exists": True,
            "has_assets": has_assets,
            "has_audio": has_audio,
            "has_mapping": has_mapping,
            "missing_images": missing_images,
            "is_complete": is_complete,
            "message": "资源完整" if is_complete else "资源不完整"
        })

    return {
        "results": results,
        "all_complete": all(r.get("is_complete", False) for r in results if r.get("exists"))
    }


@router.post("/check-zip-integrity")
async def check_zip_integrity(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    检查上传的ZIP文件资源完整性
    返回每本书的详细检查结果，不实际导入
    """
    # 检查文件扩展名
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 .zip 格式的文件"
        )

    # 读取文件内容
    content = await file.read()

    # 检查完整性
    result = await book_service.check_zip_integrity(content)

    return result


@router.post("/cleanup-failed-import")
async def cleanup_failed_import(
    book_titles: List[str] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    清理导入失败的书籍文件夹
    """
    import shutil
    
    deleted = []
    for title in book_titles:
        safe_name = title.replace(" ", "_")
        book_folder = Path("Books") / safe_name
        if book_folder.exists():
            try:
                shutil.rmtree(book_folder)
                deleted.append(title)
                logger.info(f"已删除不完整的书籍文件夹: {safe_name}")
            except Exception as e:
                logger.error(f"删除书籍文件夹失败: {safe_name}, 错误: {e}")
    
    return {"deleted": deleted}


@router.post("/check-zip-all")
async def check_zip_all(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    同时检查ZIP文件的完整性和重复情况
    返回合并的检查结果
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 .zip 格式的文件"
        )

    content = await file.read()
    result = await book_service.check_zip_all(db, content)
    return result


@router.post("/check-zip-duplicates")
async def check_zip_duplicates(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    检查ZIP文件中包含的书籍是否已存在
    返回重复书籍清单，不实际导入
    """
    # 检查文件扩展名
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 .zip 格式的文件"
        )

    # 读取文件内容
    content = await file.read()

    # 检查重复
    result = await book_service.check_zip_duplicates(db, content)

    return result


@router.post("/check-md-duplicates")
async def check_md_duplicates(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    检查多个MD文件是否已存在
    返回重复书籍清单，不实际导入
    """
    # 读取所有文件内容
    file_list = []
    for file in files:
        if not file.filename.endswith('.md'):
            continue
        content = await file.read()
        file_list.append((file.filename, content))

    if not file_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有有效的 .md 文件"
        )

    # 检查重复
    result = await book_service.check_md_duplicates(db, file_list)

    return result


@router.post("/sync")
async def sync_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    同步 Books 目录与数据库
    
    扫描 Books 目录，检查并修复数据库记录：
    - 修复路径不匹配的书籍记录
    - 添加新发现的书籍到数据库
    - 标记数据库中有但文件夹不存在的书籍
    
    返回:
        dict: 包含修复统计信息
        {
            "fixed": [...],    # 修复的记录
            "added": [...],    # 新增的记录
            "removed": [...],  # 文件夹不存在的记录
            "errors": [...]    # 处理出错的记录
        }
    """
    try:
        result = await book_service.sync_books_from_directory(db)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步失败: {str(e)}"
        )


@router.post("/compress-images")
async def compress_all_book_images(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    压缩所有书籍中未压缩的图片为WebP格式（仅管理员可用）
    
    扫描所有书籍的assets目录，查找jpg/jpeg/png/bmp格式图片，
    压缩并转换为WebP，同时更新MD文件中的引用链接
    
    返回:
        dict: 包含处理结果统计
    """
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以使用此功能"
        )
    try:
        from app.services.book_service import compress_all_images
        result = await compress_all_images(db)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"压缩失败: {str(e)}"
        )


@router.post("/{book_id}/check-audio")
async def check_book_audio(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    检查并修复单本书籍的音频配置（仅管理员可用）

    检查内容：
    - sentences.json 文件格式
    - 缺失的字段自动修复
    - 音频文件完整性检查

    返回:
        dict: 包含检查和修复结果
    """
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以检查音频"
        )
    try:
        result = await book_service.check_and_fix_book_audio(db, book_id)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查失败: {str(e)}"
        )


@router.get("/{book_id}/translation-status", response_model=TranslationStatusResponse)
async def get_translation_status(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取书籍翻译状态
    返回: 总句子数、成功数、失败数以及失败的句子列表
    """
    import json
    from pathlib import Path

    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 读取 sentences.json
    book_path = Path(book.file_path)
    book_folder = book_path.parent
    audio_folder = book_folder / "audio"
    mapping_path = audio_folder / "sentences.json"

    if not mapping_path.exists():
        return TranslationStatusResponse(
            success=True,
            total_count=0,
            success_count=0,
            failed_count=0,
            failed_sentences=[]
        )

    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            sentences = data.get('sentences', [])
            failed_sentences = data.get('failed_sentences', [])

            # 计算成功数（翻译不为空且不在失败列表中）
            failed_texts = {f['text'] for f in failed_sentences}
            success_count = sum(1 for s in sentences if s.get('translation') and s.get('text') not in failed_texts)

            # 构建失败列表
            failed_list = []
            for f in failed_sentences:
                failed_list.append({
                    'text': f.get('text', ''),
                    'translation': f.get('translation'),
                    'error': f.get('error', '未知错误'),
                    'page': f.get('page', 0),
                    'index': f.get('index', 0)
                })

            return TranslationStatusResponse(
                success=True,
                total_count=len(sentences),
                success_count=success_count,
                failed_count=len(failed_sentences),
                failed_sentences=failed_list
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取翻译状态失败: {str(e)}"
        )


@router.post("/{book_id}/retry-translate", response_model=RetryTranslateResponse)
async def retry_translate_sentence(
    book_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重试翻译指定句子
    请求体: {"text": "要翻译的句子", "page": 0, "index": 0}
    返回: 翻译结果
    """
    import json
    import hashlib
    from pathlib import Path

    text = request.get('text')
    page = request.get('page', 0)
    index = request.get('index', 0)

    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供要翻译的句子"
        )

    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 获取用户翻译API配置
    translation_api, error_msg = await get_effective_translation_api_config(db, current_user.id)
    if not translation_api:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # 读取 sentences.json
    book_path = Path(book.file_path)
    book_folder = book_path.parent
    audio_folder = book_folder / "audio"
    mapping_path = audio_folder / "sentences.json"

    if not mapping_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍翻译文件不存在"
        )

    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            sentences = data.get('sentences', [])
            failed_sentences = data.get('failed_sentences', [])

        # 翻译句子
        result = await translation_service.translate_with_result(
            text=text,
            app_id=translation_api.app_id,
            app_key=translation_api.app_key
        )

        if not result.success:
            return RetryTranslateResponse(
                success=False,
                message=f"翻译失败: {result.error}",
                translation=None
            )

        # 更新 sentences.json
        text_hash = hashlib.md5(text.encode()).hexdigest()
        audio_file = f"{text_hash}.mp3"

        # 查找并更新句子
        found = False
        for s in sentences:
            if s.get('text') == text:
                s['translation'] = result.translation
                s['audio_file'] = audio_file
                found = True
                break

        if not found:
            sentences.append({
                'text': text,
                'translation': result.translation,
                'audio_file': audio_file,
                'page': page,
                'index': index
            })

        # 从失败列表中移除
        failed_sentences = [f for f in failed_sentences if f.get('text') != text]

        # 保存更新后的数据
        data['sentences'] = sentences
        data['failed_sentences'] = failed_sentences
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return RetryTranslateResponse(
            success=True,
            message="翻译成功",
            translation=result.translation
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重试翻译失败: {str(e)}"
        )


@router.put("/{book_id}/translate-sentence", response_model=UpdateSentenceTranslationResponse)
async def update_sentence_translation(
    book_id: str,
    request: UpdateSentenceTranslationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    手动更新句子翻译
    请求体: {"text": "要翻译的句子", "translation": "用户输入的翻译"}
    返回: 更新结果
    """
    import json
    import hashlib
    from pathlib import Path

    text = request.text
    translation = request.translation

    if not text or not translation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供句子原文和翻译"
        )

    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 读取 sentences.json
    book_path = Path(book.file_path)
    book_folder = book_path.parent
    audio_folder = book_folder / "audio"
    mapping_path = audio_folder / "sentences.json"

    if not mapping_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍翻译文件不存在"
        )

    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            sentences = data.get('sentences', [])
            failed_sentences = data.get('failed_sentences', [])

        # 更新句子翻译
        text_hash = hashlib.md5(text.encode()).hexdigest()
        audio_file = f"{text_hash}.mp3"

        found = False
        for s in sentences:
            if s.get('text') == text:
                s['translation'] = translation
                s['audio_file'] = audio_file
                found = True
                break

        if not found:
            sentences.append({
                'text': text,
                'translation': translation,
                'audio_file': audio_file,
                'page': 0,
                'index': len(sentences)
            })

        # 从失败列表中移除
        failed_sentences = [f for f in failed_sentences if f.get('text') != text]

        # 保存更新后的数据
        data['sentences'] = sentences
        data['failed_sentences'] = failed_sentences
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return UpdateSentenceTranslationResponse(
            success=True,
            message="翻译更新成功"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新翻译失败: {str(e)}"
        )


@router.get("/{book_id}/sentence-preview", response_model=SentencePreviewResponse)
async def get_sentence_preview(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取书籍断句预览
    返回书籍的所有句子列表，供用户预览和编辑
    """
    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    try:
        # 读取书籍内容进行断句
        book_path = Path(book.file_path)
        
        with open(book_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 解析句子
        sentences = book_service.get_sentence_preview(content)
        return SentencePreviewResponse(
            total_count=len(sentences),
            sentences=sentences
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取断句预览失败: {str(e)}"
        )


@router.get("/{book_id}/sentences", response_model=BookSentencesResponse)
async def get_book_sentences(
    book_id: str,
    page: int = Query(0, ge=0, description="页码（从0开始）"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user)
):
    """
    获取书籍指定页的句子列表
    用于前端点击查词时定位句子，确保前后端断句一致
    """
    import re

    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    try:
        # 读取书籍内容
        book_path = Path(book.file_path)
        with open(book_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 按页分割
        pages = re.split(r'\n---\n', content)

        if page < 0 or page >= len(pages):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"页码 {page} 超出范围"
            )

        # 获取指定页的内容
        page_content = pages[page]

        # 使用与后端相同的断句逻辑
        sentences_data = book_service.get_sentence_preview(content)

        # 过滤出指定页的句子
        page_sentences = [
            {"index": s['index'], "text": s['text']}
            for s in sentences_data
            if s['page'] == page
        ]

        return BookSentencesResponse(sentences=page_sentences)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取句子列表失败: {str(e)}"
        )


@router.get("/{book_id}/preview-image")
async def preview_book_image(
    book_id: str,
    filename: str = Query(..., description="图片文件名，如 assets/image_01.jpg"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    预览书籍中的图片
    根据文件名返回对应的图片文件，用于编辑器中点击图片链接时预览
    """
    from sqlalchemy import select
    from app.models.database_models import Book
    import mimetypes

    # 获取书籍信息
    stmt = select(Book).where(Book.id == book_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    # 获取书籍文件夹路径
    # file_path 是相对路径，需要拼接 PROJECT_ROOT
    book_path = PROJECT_ROOT / book.file_path
    book_folder = book_path.parent

    # 处理图片路径
    # 清理路径中的 ./ 前缀
    clean_filename = filename.lstrip('./')
    # filename 可能是 "assets/image_01.jpg" 或 "./assets/image_01.jpg"
    image_path = book_folder / clean_filename

    # 如果相对路径找不到，尝试在 assets 文件夹中查找
    if not image_path.exists():
        assets_path = book_folder / "assets" / clean_filename
        if assets_path.exists():
            image_path = assets_path

    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"图片未找到: {filename}"
        )

    # 读取图片文件
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()

        # 根据文件扩展名确定 Content-Type
        content_type, _ = mimetypes.guess_type(str(image_path))
        if not content_type:
            content_type = 'application/octet-stream'

        return StreamingResponse(
            io.BytesIO(image_data),
            media_type=content_type,
            headers={
                'Content-Disposition': f'inline; filename="{image_path.name}"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取图片失败: {str(e)}"
        )


@router.put("/{book_id}/sentence", response_model=SentenceUpdateResponse)
async def update_sentence(
    book_id: str,
    request: SentenceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新书籍中的句子
    用户编辑句子后保存到书籍内容中
    """
    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )

    try:
        # 读取当前书籍内容
        book_path = Path(book.file_path)
        with open(book_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 更新句子
        success, message, updated_content = book_service.update_sentence_in_content(
            content=content,
            page=request.page,
            index=request.index,
            new_text=request.text
        )

        if not success:
            return SentenceUpdateResponse(
                success=False,
                message=message
            )

        # 保存更新后的内容
        with open(book_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        return SentenceUpdateResponse(
            success=True,
            message="句子更新成功"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新句子失败: {str(e)}"
        )


# 全局取消标志（用于补充翻译+中文语音批量任务）
supplement_all_cancelled = [False]

@router.post("/admin/books/supplement-all")
async def supplement_all_books(
    force: bool = Query(False, description="是否强制重新生成（覆盖已有内容）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    批量补充所有书籍的翻译和中文语音（仅管理员可用）
    遍历所有书籍，对缺少翻译或中文音频的句子进行补充
    使用SSE流式返回进度信息
    """
    # 重置取消标志
    supplement_all_cancelled[0] = False

    # 使用生成器推送SSE进度
    async def event_generator():
        queue = asyncio.Queue()
        progress_callback = create_progress_callback(queue)

        # 启动后台任务
        supplement_task = asyncio.create_task(
            book_service.supplement_all_books(
                db=db,
                user_id=current_user.id,
                progress_callback=progress_callback,
                force=force,
                cancelled=supplement_all_cancelled
            )
        )

        # 发送进度消息
        while True:
            try:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=0.5)
                    # 添加 book_title, book_index, total_books 到消息
                    message = data['message']
                    if data.get('book_title'):
                        message = f"[{data.get('book_index', 0)}/{data.get('total_books', 0)}] {data.get('book_title', '')}: {data['message']}"
                    yield format_sse_message(data['percentage'], message)
                except asyncio.TimeoutError:
                    pass

                if supplement_task.done():
                    try:
                        result = supplement_task.result()
                    except Exception as e:
                        yield format_sse_message(0, f"处理失败: {str(e)}", False)
                    break
            except Exception as e:
                logger.error(f"SSE error: {e}")
                break

        # 发送最终结果
        if supplement_task.done():
            try:
                result = supplement_task.result()
                if result and result.get("cancelled"):
                    yield format_sse_message(100, result.get("message", "已取消"), False)
                elif result and result.get("success"):
                    yield format_sse_message(100, result.get("message", "处理完成"), True)
                elif result:
                    yield format_sse_message(0, result.get("message", "处理失败"), False)
            except Exception as e:
                logger.error(f"获取结果失败: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/admin/books/supplement-all/cancel")
async def cancel_supplement_all_books(
    current_user: User = Depends(get_current_admin)
):
    """
    取消批量补充翻译和中文语音任务（仅管理员可用）
    """
    global supplement_all_cancelled
    supplement_all_cancelled[0] = True
    return {"success": True, "message": "已发送取消信号"}


# ========== 预编译缓存 API ==========


@router.get("/precompile/status")
async def get_precompile_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    获取预编译缓存状态（仅管理员可用）
    
    返回：
        - total_books: 总书籍数
        - cached_books: 已缓存书籍数
        - uncached_books: 未缓存书籍数
        - cache_size_mb: 缓存总大小(MB)
    """
    # 获取所有书籍
    from app.repositories.book_repository import book_repository
    books = await book_repository.get_multi(db)
    book_ids = [b.id for b in books]
    
    # 获取缓存状态
    cache_status = precompile_service.get_cache_status(book_ids)
    
    return {
        "total_books": cache_status.total_books,
        "cached_books": cache_status.cached_books,
        "uncached_books": cache_status.uncached_books,
        "cache_size_mb": cache_status.cache_size_mb,
        "cache_percentage": round(cache_status.cached_books / cache_status.total_books * 100, 1) if cache_status.total_books > 0 else 0
    }


@router.post("/precompile")
async def precompile_all_books(
    force: bool = Query(False, description="是否强制重新编译（忽略现有缓存）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    批量预编译所有书籍（仅管理员可用）
    使用SSE流式返回进度信息
    """
    async def event_generator():
        from app.repositories.book_repository import book_repository
        books = await book_repository.get_multi(db)
        total = len(books)
        
        if total == 0:
            yield format_sse_message(100, "没有书籍需要预编译", True)
            return
        
        success_count = 0
        skip_count = 0
        fail_count = 0
        
        for idx, book in enumerate(books):
            progress = int((idx + 1) / total * 100)
            
            result = precompile_service.precompile_book(
                book_id=book.id,
                md_file_path=book.file_path,
                force=force
            )
            
            if result.success:
                if "已存在" in result.message:
                    skip_count += 1
                    message = f"[{idx+1}/{total}] {book.title}: 跳过（已缓存）"
                else:
                    success_count += 1
                    message = f"[{idx+1}/{total}] {book.title}: 编译成功 ({result.page_count}页)"
            else:
                fail_count += 1
                message = f"[{idx+1}/{total}] {book.title}: 失败 - {result.message}"
            
            yield format_sse_message(progress, message)
        
        # 发送最终统计
        final_message = f"预编译完成: 成功 {success_count}, 跳过 {skip_count}, 失败 {fail_count}"
        yield format_sse_message(100, final_message, fail_count == 0)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{book_id}/precompile")
async def precompile_single_book(
    book_id: str = FastAPIPath(..., description="书籍ID"),
    force: bool = Query(False, description="是否强制重新编译"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    预编译单本书籍（仅管理员可用）
    """
    from app.repositories.book_repository import book_repository
    book = await book_repository.get(db, book_id)
    
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍不存在"
        )
    
    result = precompile_service.precompile_book(
        book_id=book.id,
        md_file_path=book.file_path,
        force=force
    )
    
    return {
        "success": result.success,
        "message": result.message,
        "book_id": result.book_id,
        "page_count": result.page_count
    }


@router.delete("/precompile/cache")
async def clear_precompile_cache(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    清除所有预编译缓存（仅管理员可用）
    """
    count = precompile_service.clear_all_cache()
    return {
        "success": True,
        "message": f"已清除 {count} 个书籍的预编译缓存",
        "cleared_count": count
    }
