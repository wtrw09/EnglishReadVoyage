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
        for page_raw in pages_raw:
            html = self.md.convert(page_raw)
            
            # 3. 将非图像内容包装在text-wrapper中以实现并排布局
            html = self._add_text_wrapper(html)

            # 4. 处理HTML以包装句子在<span data-tts="...">中
            html = self._wrap_sentences(html)
            
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

    def _wrap_sentences(self, html: str) -> str:
        """
        用带有data-tts属性的<span>标签包装句子以供TTS播放
        
        参数:
            html: 带有包装div的HTML内容
            
        返回:
            句子被包装在TTS就绪span中的HTML
        """
        def replacer(match):
            tag_open = match.group(1)
            content = match.group(4)
            tag_close = match.group(5)
            
            # 如果已经在忽略的div内则跳过
            if 'class="ignored-content"' in tag_open:
                return f"{tag_open}{content}{tag_close}"

            if content and ('<img' in content or '<table' in content):
                return f"{tag_open}{content}{tag_close}"
            
            # 分成句子：按句号(.)或换行符(\n)分割
            # 使用(?<=\.)确保句号与句子在一起
            sentences = re.split(r'(?<=\.)|\n+', content)
            wrapped_sentences = []
            for s in sentences:
                s = s.strip()
                if s:
                    safe_text = s.replace('"', '&quot;')
                    wrapped_sentences.append(f'<span class="tts-sentence" data-tts="{safe_text}">{s}</span>')
            
            return f"{tag_open}{' '.join(wrapped_sentences)}{tag_close}"

        # 匹配<p>, <li>, <h1-6>
        # 分组: 1: 开始标签, 2: 标签名, 3: 可选属性, 4: 内容, 5: 结束标签
        pattern = r'(<(p|li|h[1-6])( [^>]*)?>)(.*?)(</\2>)'
        return re.sub(pattern, replacer, html, flags=re.DOTALL)
