"""书籍管理API端点。"""
import asyncio
import io
import zipfile
import os
from pathlib import Path
import hashlib
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.book import BookInfo, BookDetail, BookImportResponse, BookUpdateRequest, BookUpdateResponse, BookPagesResponse, BookRenameRequest, BookRenameResponse
from app.services.book_service import book_service
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User
from app.core.config import get_settings


router = APIRouter()

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """分页获取书籍内容，支持渐进式预加载"""
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
    current_user: User = Depends(get_current_user)
):
    """
    导入书籍文件（支持MD和ZIP）。
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

        async def progress_callback(percentage: int, message: str):
            await queue.put({"percentage": percentage, "message": message})

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
                    yield f"data: {{\"percentage\": {data['percentage']}, \"message\": \"{data['message']}\"}}\n\n"
                except asyncio.TimeoutError:
                    pass

                # 检查任务是否完成
                if import_task.done():
                    try:
                        result = import_task.result()
                    except Exception as e:
                        yield f"data: {{\"percentage\": 0, \"message\": \"导入失败: {str(e)}\", \"success\": false}}\n\n"
                    break
            except Exception as e:
                print(f"SSE error: {e}")
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
                                db, bid, category_id, current_user.id
                            )
                except Exception as e:
                    print(f"添加书籍到分类失败: {e}")

            # 构建返回的book_id字符串（单本用book_id，多本用逗号分隔）
            return_book_id = result.book_id if result.book_id else ",".join(result.book_ids) if result.book_ids else ""
            yield f"data: {{\"percentage\": 100, \"message\": \"{result.message}\", \"success\": true, \"book_id\": \"{return_book_id}\"}}\n\n"
        elif result:
            yield f"data: {{\"percentage\": 0, \"message\": \"{result.message}\", \"success\": false}}\n\n"

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
    current_user: User = Depends(get_current_user)
):
    print(f"Overwrite import called with book_id: {book_id}, category_id: {category_id}")
    """
    覆盖导入书籍（删除旧内容，保存新内容，不生成音频）
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

        async def progress_callback(percentage: int, message: str):
            await queue.put({"percentage": percentage, "message": message})

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
                    yield f"data: {{\"percentage\": {data['percentage']}, \"message\": \"{data['message']}\"}}\n\n"
                except asyncio.TimeoutError:
                    pass

                # 检查任务是否完成
                if import_task.done():
                    try:
                        result = import_task.result()
                    except Exception as e:
                        yield f"data: {{\"percentage\": 0, \"message\": \"导入失败: {str(e)}\", \"success\": false}}\n\n"
                    break
            except Exception as e:
                print(f"SSE error: {e}")
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
                        db, target_book_id, category_id, current_user.id
                    )
                except Exception as e:
                    print(f"添加书籍到分类失败: {e}")

            yield f"data: {{\"percentage\": 100, \"message\": \"{result.message}\", \"success\": true, \"book_id\": \"{result.book_id}\"}}\n\n"
        elif result:
            yield f"data: {{\"percentage\": 0, \"message\": \"{result.message}\", \"success\": false}}\n\n"

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

        async def progress_callback(percentage: int, message: str):
            await queue.put({"percentage": percentage, "message": message})

        # 启动后台任务
        regen_task = asyncio.create_task(
            book_service.regenerate_audio(
                db=db,
                book_id=book_id,
                user_id=current_user.id,
                progress_callback=progress_callback
            )
        )

        result = None
        while True:
            try:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield f"data: {{\"percentage\": {data['percentage']}, \"message\": \"{data['message']}\"}}\n\n"
                except asyncio.TimeoutError:
                    pass

                if regen_task.done():
                    try:
                        result = regen_task.result()
                    except Exception as e:
                        yield f"data: {{\"percentage\": 0, \"message\": \"生成失败: {str(e)}\", \"success\": false}}\n\n"
                    break
            except Exception as e:
                print(f"SSE error: {e}")
                break

        if result and result.success:
            yield f"data: {{\"percentage\": 100, \"message\": \"{result.message}\", \"success\": true}}\n\n"
        elif result:
            yield f"data: {{\"percentage\": 0, \"message\": \"{result.message}\", \"success\": false}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


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
    print(f"Reading content from file: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")

    # 如果文件存在，直接读取
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"Content length: {len(content)}")
        print(f"First 200 chars: {content[:200]}")
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
    
    如果 cover_path 指向 assets 目录下的图片，会将其复制到书籍根目录并重命名为 cover.jpg
    """
    import shutil
    cover_path = request.get('cover_path') if request else None
    print(f"update_book_cover called: book_id={book_id}, cover_path={cover_path}")
    
    # 获取书籍信息
    book = await book_service.repository.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="书籍未找到"
        )
    
    # 如果 cover_path 指向 assets 目录下的图片，复制到根目录作为 cover.jpg
    if cover_path and '/assets/' in cover_path:
        # 解析路径获取书籍文件夹和文件名
        # cover_path 格式: /books/{book_name}/assets/{filename}
        try:
            book_path = Path(book.file_path)
            book_folder = book_path.parent
            
            # 提取 assets 中的文件名
            filename = cover_path.split('/assets/')[-1]
            source_image_path = book_folder / "assets" / filename
            
            if source_image_path.exists():
                # 删除已存在的封面文件
                for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    existing_cover = book_folder / f"cover{ext}"
                    if existing_cover.exists():
                        existing_cover.unlink()
                
                # 复制图片到根目录并重命名为 cover.jpg
                cover_file = book_folder / "cover.jpg"
                shutil.copy2(source_image_path, cover_file)
                
                # 更新 cover_path 为根目录下的 cover.jpg
                cover_path = f"/books/{book_folder.name}/cover.jpg"
                print(f"已将 assets 图片复制为封面: {cover_path}")
        except Exception as e:
            print(f"复制封面图片失败: {e}")
    
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
    """更新书籍内容"""
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
        print(f"删除书籍错误: {e}")
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
    """上传书籍封面，保存为 cover.jpg 在书籍根目录"""
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
    from pathlib import Path
    book_path = Path(book.file_path)
    book_folder = book_path.parent

    # 删除已存在的封面文件（各种扩展名）
    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
        existing_cover = book_folder / f"cover{ext}"
        if existing_cover.exists():
            existing_cover.unlink()

    # 保存文件为 cover.jpg（统一格式）
    cover_path = book_folder / "cover.jpg"
    with open(cover_path, 'wb') as f:
        f.write(content)

    # 返回相对路径
    relative_path = str(cover_path.relative_to(BOOKS_DIR))
    return {"path": f"/books/{relative_path}"}


@router.post("/export")
async def export_books(
    request: dict,
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

            # 如果只有一本书，直接将内容放在ZIP根目录
            if len(books) == 1:
                prefix = ""
            else:
                # 多本书时，每本书放在自己的文件夹中
                prefix = f"{book.title}/"

            # 遍历书籍文件夹中的所有文件
            for root, dirs, files in os.walk(book_folder):
                for file in files:
                    file_path = Path(root) / file
                    # 计算在ZIP中的相对路径
                    arc_name = prefix + str(file_path.relative_to(book_folder))
                    zf.write(file_path, arc_name)

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

    return StreamingResponse(
        zip_buffer,
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
            except:
                pass

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
                print(f"检查图片引用失败: {e}")

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
    返回完整性检查结果，不实际导入
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
