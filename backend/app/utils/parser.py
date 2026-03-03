"""用于将书籍转换为带TTS注释的HTML的Markdown解析器工具"""
import re
import markdown


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

    def _wrap_sentences(self, html: str, page_idx: int = 0) -> str:
        """
        用带有data-tts属性的<span>标签包装句子以供TTS播放

        参数:
            html: 带有包装div的HTML内容
            page_idx: 页面索引

        返回:
            句子被包装在TTS就绪span中的HTML
        """
        sentence_idx = 0  # 每个页面内的句子索引

        def replacer(match):
            nonlocal sentence_idx
            tag_open = match.group(1)
            content = match.group(4)
            tag_close = match.group(5)

            # 如果已经在忽略的div内则跳过
            if 'class="ignored-content"' in tag_open:
                return f"{tag_open}{content}{tag_close}"

            if content and ('<img' in content or '<table' in content):
                return f"{tag_open}{content}{tag_close}"

            # 移除MD格式字符（标题标记和加粗斜体标记）
            # 先移除标题标记 (# ## ### 等)
            content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
            # 移除加粗、斜体等标记
            content = re.sub(r'[*_]+', '', content)

            # 分句逻辑：先按换行分割（每行是一个独立句子），再按句号分割
            lines = content.split('\n')
            sentences = []
            for line in lines:
                line = line.strip()
                if not line or len(line) < 3:
                    continue
                # 按句号分割
                parts = re.split(r'(?<=[.])\s*', line)
                for part in parts:
                    part = part.strip()
                    if part:
                        sentences.append(part)
            wrapped_sentences = []
            for s in sentences:
                s = s.strip()
                if s:
                    # 移除HTML标签（如<br />）用于data-tts，确保哈希匹配
                    text_for_tts = re.sub(r'<[^>]+>', '', s)
                    # 移除双引号和单引号
                    text_for_tts = text_for_tts.replace('"', '').replace("'", "")
                    # 移除非英文、非数字、非基本标点的字符（保留字母、数字、空格和基本标点）
                    text_for_tts = re.sub(r'[^\w\s.,!?;:\-]', '', text_for_tts)
                    # 清理多余空格
                    text_for_tts = re.sub(r'\s+', ' ', text_for_tts).strip()
                    safe_text = text_for_tts.replace('"', '&quot;')
                    wrapped_sentences.append(
                        f'<span class="tts-sentence" data-tts="{safe_text}" data-page-index="{page_idx}" data-sentence-index="{sentence_idx}">{s}</span>'
                    )
                    sentence_idx += 1

            return f"{tag_open}{' '.join(wrapped_sentences)}{tag_close}"

        # 匹配<p>, <li>, <h1-6>
        # 分组: 1: 开始标签, 2: 标签名, 3: 可选属性, 4: 内容, 5: 结束标签
        pattern = r'(<(p|li|h[1-6])( [^>]*)?>)(.*?)(</\2>)'
        return re.sub(pattern, replacer, html, flags=re.DOTALL)
