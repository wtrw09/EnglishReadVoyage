"""用于将书籍转换为带TTS注释的HTML的Markdown解析器工具"""
import re
import markdown
from typing import List

from app.utils.sentence_splitter import split_sentences


def normalize_text_for_tts(text: str) -> str:
    """统一的文本规范化函数，用于 TTS 哈希匹配
    
    规则：
    1. 去除前后空白
    2. 将多个连续空白字符（空格、制表符等）替换为单个空格
    
    注意：不修改原始文本内容（不添加句号、不移除引号等）
    """
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


class MarkdownParser:
    """解析markdown文件并转换为带TTS句子包装的HTML"""
    
    def __init__(self):
        """使用扩展初始化markdown解析器"""
        self.md = markdown.Markdown(extensions=['tables', 'fenced_code'])

    def parse_file(self, file_path: str) -> list[str]:
        """
        解析markdown文件并返回HTML页面列表。

        Args:
            file_path: markdown文件的绝对路径

        Returns:
            HTML字符串列表，每页一个
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. 预处理：完全移除忽略块
        content = re.sub(r'<!--\s*ignore\s*-->(.*?)<!--\s*/ignore\s*-->', '', content, flags=re.DOTALL)

        # 2. 按分页标记---分割
        pages_raw = re.split(r'\n---\n', content)

        parsed_pages = []
        for page_idx, page_raw in enumerate(pages_raw):
            html = self.md.convert(page_raw)

            # 3. 处理HTML以包装句子在<span data-tts="...">中，带page和sentence索引
            html = self._wrap_sentences(html, page_idx)

            parsed_pages.append(html)

        return parsed_pages

    def _add_text_wrapper(self, html: str) -> str:
        """
        添加text-wrapper div以实现与图像的并排布局
        
        参数:
            html: 原始HTML内容
            
        返回:
            包装了div的HTML
        """
        # 1. 按标题分割以识别部分
        # 这样可以在分割列表中将标题标签作为独立部分保留
        sections = re.split(r'(<h[1-6][^>]*>.*?</h[1-6]>)', html, flags=re.DOTALL)
        
        processed_sections = []
        current_header = ""
        current_content = []

        def flush_section():
            if not current_header and not current_content:
                return ""
            
            body_html = "".join(current_content).strip()
            if not body_html:
                return current_header
            
            # 如果主体包含图像，本部分的主体使用并排布局
            if '<img' in body_html:
                # 将主体分为图像和非图像部分
                parts = re.split(r'(<p[^>]*><img.*?</p>)', body_html, flags=re.DOTALL)
                text_parts = []
                img_parts = []
                for p in parts:
                    if '<img' in p:
                        img_parts.append(p)
                    elif p.strip():
                        text_parts.append(p)
                
                # 将它们包装在前端可以定位的容器中
                wrapped_text = f'<div class="text-wrapper">{"".join(text_parts)}</div>'
                wrapped_imgs = f'<div class="image-wrapper">{"".join(img_parts)}</div>'
                return f'<div class="book-section">{current_header}<div class="section-body">{wrapped_text}{wrapped_imgs}</div></div>'
            else:
                # 无图像，只是正常流但为了保持一致性而包装
                return f'<div class="book-section">{current_header}<div class="text-wrapper">{body_html}</div></div>'

        for part in sections:
            if not part:
                continue
            if re.match(r'<h[1-6]', part):
                # 发现新部分，刷新前一个部分
                processed_sections.append(flush_section())
                current_header = part
                current_content = []
            else:
                current_content.append(part)
        
        # 刷新最后一个部分
        processed_sections.append(flush_section())
        return "".join(processed_sections)

    def _split_into_sentences(self, text: str) -> list[str]:
        """
        使用 spaCy 进行智能断句

        参数:
            text: 待分割的文本

        返回:
            句子列表
        """
        return split_sentences(text)

    @staticmethod
    def extract_sentences_from_content(content: str) -> List[dict]:
        """
        从markdown内容中提取句子列表（与朗读断句逻辑一致）

        参数:
            content: markdown页面内容

        返回:
            句子列表，每个元素包含 page, index, text
        """
        # 移除忽略标记
        ignore_pattern = r'<!--\s*ignore\s*-->.*?<!--\s*/ignore\s*-->'
        content = re.sub(ignore_pattern, '', content, flags=re.DOTALL | re.IGNORECASE)

        # 移除图片
        content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', content)

        # 将 <br> 标签转为换行符
        content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)

        # 移除HTML标签
        content = re.sub(r'<[^>]+>', '', content)

        # 移除markdown链接
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

        # 移除MD格式字符
        # 移除标题标记
        content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
        # 移除加粗、斜体等标记
        content = re.sub(r'[*_]+', '', content)

        # 只替换空格和制表符，保留换行符
        content = re.sub(r'[ \t]+', ' ', content).strip()

        # 段落分割逻辑（与 _wrap_text_content 一致）
        raw_paragraphs = re.split(r'\n\s*\n', content)
        paragraphs = []
        for raw_para in raw_paragraphs:
            title_parts = re.split(r'(?=^#\s)', raw_para, flags=re.MULTILINE)
            for part in title_parts:
                part = part.strip()
                if part:
                    paragraphs.append(part)

        sentences = []
        for para_idx, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # 如果段落是纯小写字母的单词短语，作为完整句子处理
            if re.match(r'^[a-z]+(?:\s+[a-z]+)*$', paragraph):
                if paragraph.strip():
                    sentences.append(paragraph.strip())
                continue

            # 移除段落中的换行
            paragraph = re.sub(r'\n+', ' ', paragraph)

            # 去除句首的序号
            paragraph = re.sub(r'^\d+[\.)]\s*', '', paragraph)
            paragraph = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]+\s*', '', paragraph)

            # 使用智能断句
            parts = split_sentences(paragraph)
            for part in parts:
                part = part.strip()
                if part and len(part) >= 1:
                    sentences.append(part)

        return sentences

    def _wrap_text_content(self, content: str, page_idx: int, sentence_idx: list) -> str:
        """
        对纯文本内容进行句子包装

        参数:
            content: 纯文本内容（可能包含HTML标签）
            page_idx: 页面索引
            sentence_idx: 可变列表，用于跟踪句子索引 [current_idx]

        返回:
            包装了TTS span的HTML内容
        """
        # 先移除HTML标签，获取纯文本
        content = re.sub(r'<[^>]+>', ' ', content)

        # 移除MD格式字符（标题标记和加粗斜体标记）
        content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'[*_]+', '', content)

        # 将 <br> 标签替换为换行符
        content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)

        # 分句逻辑：先按段落分割，再在每个段落内断句
        # 段落分隔符：空行（连续换行）或标题行（# 开头）或单独的数字序号
        # 先按空行分割，然后再按标题行分割

        # 先按空行分割段落
        raw_paragraphs = re.split(r'\n\s*\n', content)

        # 进一步分割段落，将标题（# 开头）单独分割出来
        paragraphs = []
        for raw_para in raw_paragraphs:
            # 按标题行分割（# 开头的内容）
            title_parts = re.split(r'(?=^#\s)', raw_para, flags=re.MULTILINE)
            for part in title_parts:
                part = part.strip()
                if part:
                    paragraphs.append(part)

        sentences = []
        for para_idx, paragraph in enumerate(paragraphs):
            # 清理段落内容
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # 如果段落是纯小写字母的单词短语（如 "cotton shirts"），作为完整句子处理
            if re.match(r'^[a-z]+(?:\s+[a-z]+)*$', paragraph):
                if paragraph.strip():
                    sentences.append((paragraph.strip(), para_idx))
                continue

            # 移除段落中的换行，替换为空格
            paragraph = re.sub(r'\n+', ' ', paragraph)

            # 去除句首的序号（如 "1.", "2.", "①" 等）
            paragraph = re.sub(r'^\d+[\.)]\s*', '', paragraph)
            paragraph = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]+\s*', '', paragraph)

            # 正常段落使用智能断句
            parts = self._split_into_sentences(paragraph)
            for part in parts:
                part = part.strip()
                if part and len(part) >= 1:
                    sentences.append((part, para_idx))

        wrapped_sentences = []
        prev_block_idx = None
        for s, block_idx in sentences:
            normalized = normalize_text_for_tts(s)
            if not normalized:
                continue
            safe_text = normalized.replace('"', '&quot;')
            if prev_block_idx is not None and block_idx != prev_block_idx:
                wrapped_sentences.append('<br>')
            wrapped_sentences.append(
                f'<span class="tts-sentence" data-tts="{safe_text}" data-page-index="{page_idx}" data-sentence-index="{sentence_idx[0]}">{s}</span>'
            )
            prev_block_idx = block_idx
            sentence_idx[0] += 1

        return ' '.join(wrapped_sentences)

    def _wrap_sentences(self, html: str, page_idx: int = 0) -> str:
        """
        用带有data-tts属性的<span>标签包装句子以供TTS播放

        参数:
            html: 带有包装div的HTML内容
            page_idx: 页面索引

        返回:
            句子被包装在TTS就绪span中的HTML
        """
        sentence_idx = [0]  # 使用列表以便在嵌套函数中修改

        def replacer(match):
            tag_open = match.group(1)
            content = match.group(4)
            tag_close = match.group(5)

            # 如果已经在忽略的div内则跳过
            if 'class="ignored-content"' in tag_open:
                return f"{tag_open}{content}{tag_close}"

            # 如果包含表格，完全跳过
            if content and '<table' in content:
                return f"{tag_open}{content}{tag_close}"

            # 如果包含图片，分离图片和文本，只对文本进行包装
            if content and '<img' in content:
                # 使用正则分割出 <img> 标签
                img_pattern = r'(<img[^>]*>)'
                parts = re.split(img_pattern, content)

                processed_parts = []
                for part in parts:
                    if re.match(r'<img', part):
                        # 图片标签，原样保留
                        processed_parts.append(part)
                    elif part.strip():
                        # 文本部分，进行句子包装
                        wrapped = self._wrap_text_content(part, page_idx, sentence_idx)
                        if wrapped:
                            processed_parts.append(wrapped)

                return f"{tag_open}{' '.join(processed_parts)}{tag_close}"

            # 纯文本内容，进行句子包装
            wrapped = self._wrap_text_content(content, page_idx, sentence_idx)
            return f"{tag_open}{wrapped}{tag_close}"

        # 匹配<p>, <li>, <h1-6>
        # 分组: 1: 开始标签, 2: 标签名, 3: 可选属性, 4: 内容, 5: 结束标签
        pattern = r'(<(p|li|h[1-6])( [^>]*)?>)(.*?)(</\2>)'
        return re.sub(pattern, replacer, html, flags=re.DOTALL)
