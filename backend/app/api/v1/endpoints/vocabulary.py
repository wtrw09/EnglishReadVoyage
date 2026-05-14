"""生词本API端点。"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, delete
from typing import List, Optional
import io
import os

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.database_models import User, Vocabulary, TranslationAPI
from app.schemas.vocabulary import VocabularyCreate, VocabularyResponse, VocabularyListResponse, VocabularyBatchDelete, VocabularyExport
from app.services.dictionary_service import dictionary_service
from app.services.translation_service import translation_service
from docx import Document
import genanki
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from urllib.parse import quote

# 获取字体文件路径
FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'fonts', 'simsun.ttc')
TITLE_FONT_NAME = '方正小标宋简体'  # 标题字体
TABLE_FONT_NAME = '黑体'  # 表格字体


def set_run_font(run, font_name, font_size=None):
    """设置run的字体"""
    r = run._element
    rPr = r.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), font_name)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rPr.append(rFonts)
    if font_size:
        run.font.size = font_size


def set_cell_vertical_center(cell):
    """设置表格单元格垂直居中"""
    # 使用python-docx的内置方法，需要使用枚举值
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


router = APIRouter()


@router.post("/", response_model=VocabularyResponse)
async def add_vocabulary(
    request: VocabularyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    添加生词到生词本。

    如果相同的单词和句子组合已存在，则返回已存在的记录。
    如果有句子但没有句子翻译，自动调用百度翻译获取。
    """
    # 检查是否已存在相同的生词（同一用户、同一单词、同一句子）
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.user_id == current_user.id,
            Vocabulary.word == request.word,
            Vocabulary.sentence == request.sentence
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # 已存在则返回已存在的记录
        return existing

    # 确定句子翻译
    sentence_translation = request.sentence_translation
    if not sentence_translation and request.sentence:
        # 需要翻译句子
        sentence_translation = await _get_sentence_translation(db, current_user.id, request.sentence)
        if sentence_translation is None:
            sentence_translation = "请配置百度翻译api"

    # 创建新的生词记录
    vocab = Vocabulary(
        user_id=current_user.id,
        word=request.word,
        phonetic=request.phonetic,
        translation=request.translation,
        sentence=request.sentence,
        sentence_translation=sentence_translation,
        book_name=request.book_name
    )
    db.add(vocab)
    await db.commit()
    await db.refresh(vocab)

    return vocab


async def _get_sentence_translation(db: AsyncSession, user_id: int, sentence: str) -> Optional[str]:
    """获取用户的翻译API配置并翻译句子"""
    try:
        # 获取用户的翻译API配置
        stmt = select(TranslationAPI).where(
            TranslationAPI.user_id == user_id,
            TranslationAPI.is_active == True
        ).order_by(TranslationAPI.id)
        result = await db.execute(stmt)
        api = result.scalars().first()

        if not api or not api.app_id or not api.app_key:
            return None

        # 调用百度翻译
        translated = await translation_service.translate_with_baidu(
            text=sentence,
            from_lang="en",
            to_lang="zh",
            app_id=api.app_id,
            app_key=api.app_key
        )
        return translated
    except Exception as e:
        logging.warning(f"翻译句子失败: {e}")
        return None


@router.get("/", response_model=VocabularyListResponse)
async def get_vocabulary_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的生词列表。

    按添加时间倒序排列。
    """
    stmt = select(Vocabulary).where(
        Vocabulary.user_id == current_user.id
    ).order_by(desc(Vocabulary.created_at))

    result = await db.execute(stmt)
    vocab_list = result.scalars().all()

    return VocabularyListResponse(
        items=[VocabularyResponse.model_validate(v) for v in vocab_list],
        total=len(vocab_list)
    )


@router.delete("/{vocab_id}")
async def delete_vocabulary(
    vocab_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除生词本中的生词。

    只能删除自己添加的生词。
    """
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.id == vocab_id,
            Vocabulary.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    vocab = result.scalar_one_or_none()

    if not vocab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="生词不存在"
        )

    await db.delete(vocab)
    await db.commit()

    return {"success": True, "message": "生词已删除"}


@router.get("/check", response_model=dict)
async def check_vocabulary_exists(
    word: str,
    sentence: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    检查生词是否已存在于生词本中。
    """
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.user_id == current_user.id,
            Vocabulary.word == word,
            Vocabulary.sentence == sentence
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    return {
        "exists": existing is not None,
        "id": existing.id if existing else None
    }


@router.post("/batch-delete")
async def batch_delete_vocabulary(
    request: VocabularyBatchDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量删除生词本中的生词。

    只能删除自己添加的生词。
    """
    ids = request.ids
    if not ids:
        return {"success": True, "deleted_count": 0}

    # 删除属于当前用户的指定生词
    stmt = delete(Vocabulary).where(
        and_(
            Vocabulary.id.in_(ids),
            Vocabulary.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    await db.commit()

    return {"success": True, "deleted_count": result.rowcount}


@router.post("/export")
async def export_vocabulary(
    request: VocabularyExport,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导出生词本为Word文档。

    可以指定要隐藏的字段（用于默写练习）：
    - word: 英文单词
    - phonetic: 音标
    - translation: 中文翻译
    """
    if not request.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要导出的生词"
        )

    # 获取生词数据
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.id.in_(request.ids),
            Vocabulary.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    vocab_list = result.scalars().all()

    if not vocab_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要导出的生词"
        )

    # 创建Word文档
    doc = Document()

    # 添加标题
    title = doc.add_paragraph()
    title_run = title.add_run("生词本默写练习")
    title_run.bold = True
    title_run.font.size = Pt(22)  # 2号
    set_run_font(title_run, TITLE_FONT_NAME, Pt(22))
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # 添加表头
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Light Grid Accent 1'

    # 设置表头样式
    hidden_fields = request.hidden_fields or []

    # 确定列顺序
    # 如果同时默写 word 和 translation，顺序为：音标、英文、中文
    # 如果只默写 translation，顺序为：英文、音标、中文
    # 其他情况默认：英文、音标、中文
    if 'word' in hidden_fields and 'translation' in hidden_fields:
        # 同时默写英文和中文：音标、英文、中文
        header_cells = table.rows[0].cells
        header_cells[0].text = '音标'
        header_cells[1].text = '英文单词'
        header_cells[2].text = '中文翻译'
    elif 'translation' in hidden_fields:
        # 只默写中文：英文、音标、中文
        header_cells = table.rows[0].cells
        header_cells[0].text = '英文单词'
        header_cells[1].text = '音标'
        header_cells[2].text = '中文翻译'
    else:
        # 默认：英文、音标、中文
        header_cells = table.rows[0].cells
        header_cells[0].text = '英文单词'
        header_cells[1].text = '音标'
        header_cells[2].text = '中文翻译'

    # 设置表头样式（居中、四号）
    for cell in header_cells:
        if cell.paragraphs[0].runs:
            cell.paragraphs[0].runs[0].bold = True
            cell.paragraphs[0].runs[0].font.size = Pt(14)  # 四号
            set_run_font(cell.paragraphs[0].runs[0], TABLE_FONT_NAME, Pt(14))
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        # 设置垂直居中
        set_cell_vertical_center(cell)

    # 添加数据行
    for vocab in vocab_list:
        row = table.add_row()
        row_cells = row.cells

        if 'word' in hidden_fields and 'translation' in hidden_fields:
            # 同时默写：音标、英文、中文
            row_cells[0].text = vocab.phonetic or ''  # 音标
            row_cells[1].text = ''  # 英文留空
            row_cells[2].text = ''  # 中文留空
        elif 'translation' in hidden_fields:
            # 只默写中文：英文、音标、中文
            row_cells[0].text = ''  # 英文留空
            row_cells[1].text = vocab.phonetic or ''  # 音标
            row_cells[2].text = ''  # 中文留空
        elif 'word' in hidden_fields:
            # 只默写英文：音标、英文、中文
            row_cells[0].text = vocab.phonetic or ''  # 音标
            row_cells[1].text = ''  # 英文留空
            row_cells[2].text = vocab.translation or ''  # 中文
        else:
            # 默认全部显示
            row_cells[0].text = vocab.word or ''
            row_cells[1].text = vocab.phonetic or ''
            row_cells[2].text = vocab.translation or ''

        # 设置数据行样式（居中、四号字体）
        for cell in row_cells:
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            # 设置字体大小和样式
            if cell.paragraphs[0].runs:
                cell.paragraphs[0].runs[0].font.size = Pt(14)  # 四号
                set_run_font(cell.paragraphs[0].runs[0], TABLE_FONT_NAME, Pt(14))
            # 设置垂直居中
            set_cell_vertical_center(cell)

    # 保存到内存
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    # 返回文件流
    from datetime import datetime
    from urllib.parse import quote
    filename = f"vocabulary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

    return StreamingResponse(
        iter([file_stream.getvalue()]),
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}'
        }
    )


def highlight_word_in_sentence(sentence: str, word: str) -> str:
    """将句子中的目标单词加粗标红"""
    import re
    # 精确匹配单词（区分大小写），用 <b> 和 <span> 包裹
    pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
    return pattern.sub(f'<b><span style="color:red;">{word}</span></b>', sentence)


@router.post("/export/apkg")
async def export_vocabulary_apkg(
    request: VocabularyExport,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导出生词本为 Anki APKG 文件。

    正面：单词所在句子（目标单词加粗标红）
    背面：句子翻译
    如无句子，使用词典第一个例句；无例句则只保留单词和翻译
    """
    if not request.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要导出的生词"
        )

    # 获取生词数据
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.id.in_(request.ids),
            Vocabulary.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    vocab_list = result.scalars().all()

    if not vocab_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要导出的生词"
        )

    # 创建 Anki 模型 - 正面的句子和背面的翻译
    model_id = 1607392320
    model = genanki.Model(
        model_id,
        'EnglishReadVoyage Sentence Card',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Front}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{Back}}',
            },
        ],
        css='''
            .card {
                font-family: Arial;
                font-size: 20px;
                text-align: center;
                color: black;
                background-color: white;
            }
            .card {
                color: #333;
            }
        '''
    )

    # 创建牌组
    deck_id = 2059400111
    deck = genanki.Deck(deck_id, 'EnglishReadVoyage生词本')

    # 遍历生词，创建卡片
    for vocab in vocab_list:
        word = vocab.word or ''
        translation = vocab.translation or ''
        sentence_translation = vocab.sentence_translation or ''

        # 确定正面内容
        front_content = ''

        if vocab.sentence:
            # 使用生词本中的句子
            front_content = highlight_word_in_sentence(vocab.sentence, word)
        else:
            # 查询词典获取例句
            dict_result = await dictionary_service.lookup(word, source='local')
            if dict_result:
                # 找到第一个例句
                example_found = False
                for meaning in dict_result.meanings or []:
                    for definition in meaning.definitions or []:
                        if definition.example:
                            front_content = highlight_word_in_sentence(definition.example, word)
                            example_found = True
                            break
                    if example_found:
                        break

                if not example_found:
                    # 没有例句，只显示单词
                    front_content = f'<b>{word}</b>'

        # 确定背面内容：句子翻译 + --- + 单词翻译
        back_parts = []
        if sentence_translation:
            back_parts.append(sentence_translation)
        back_parts.append(translation)
        back_content = '\n---\n'.join(back_parts)

        note = genanki.Note(model=model, fields=[front_content, back_content])
        deck.add_note(note)

    # 生成 APKG 文件
    import tempfile
    from datetime import datetime
    import uuid

    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(suffix='.apkg', delete=False)
    temp_path = temp_file.name
    temp_file.close()

    deck.write_to_file(temp_path)

    # 读取文件内容
    with open(temp_path, 'rb') as f:
        apkg_data = f.read()

    # 删除临时文件
    import os
    os.unlink(temp_path)

    # 返回文件流
    filename = f"vocabulary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.apkg"

    return StreamingResponse(
        iter([apkg_data]),
        media_type='application/x-apkg',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}'
        }
    )


@router.post("/update-sentence-translations")
async def update_sentence_translations(
    request: VocabularyBatchDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量更新选中生词的句子翻译。

    仅更新有句子但无句子翻译的生词。
    无句子的生词会被跳过。
    """
    if not request.ids:
        return {"success": True, "updated_count": 0, "skipped_count": 0}

    # 获取所有需要处理的生词（一次查询）
    stmt = select(Vocabulary).where(
        and_(
            Vocabulary.id.in_(request.ids),
            Vocabulary.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    all_vocabs = result.scalars().all()

    # 区分需要更新的和需要跳过的
    vocab_to_update = []
    skipped_count = 0
    for vocab in all_vocabs:
        if vocab.sentence and vocab.sentence_translation is None:
            vocab_to_update.append(vocab)
        elif not vocab.sentence or vocab.sentence == "":
            skipped_count += 1

    # 批量更新翻译
    updated_count = 0
    for vocab in vocab_to_update:
        sentence_trans = await _get_sentence_translation(db, current_user.id, vocab.sentence)
        if sentence_trans:
            vocab.sentence_translation = sentence_trans
        else:
            vocab.sentence_translation = "请配置百度翻译api"
        updated_count += 1

    await db.commit()

    return {
        "success": True,
        "updated_count": updated_count,
        "skipped_count": skipped_count
    }
