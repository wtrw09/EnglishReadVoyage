"""
spaCy 断句工具模块
提供英语文本的智能断句功能
"""

import re
from typing import Optional

import spacy


# 全局 spaCy 模型缓存
_nlp_model: Optional[spacy.language.Language] = None


def get_nlp_model() -> spacy.language.Language:
    """
    获取 spaCy NLP 模型（带缓存）

    返回:
        加载好的 spaCy 模型
    """
    global _nlp_model

    if _nlp_model is None:
        try:
            # 尝试使用 en_core_web_sm.load() 加载模型
            import en_core_web_sm
            _nlp_model = en_core_web_sm.load()
        except Exception:
            try:
                # 如果失败，尝试使用 spacy.load
                _nlp_model = spacy.load("en_core_web_sm")
            except Exception:
                # 如果都不存在，使用 sentencizer
                _nlp_model = spacy.blank("en")
                _nlp_model.add_pipe("sentencizer")

    return _nlp_model


def is_dialogue_attribution(line: str) -> bool:
    """
    判断是否是简短的对话归属句（如 "Bonk asks."）

    参数:
        line: 待检测的文本行

    返回:
        是否是对话归属句
    """
    # 去掉末尾的标点后再匹配
    cleaned = re.sub(r'[.!?]+$', '', line.strip())
    return bool(re.match(r'^[A-Z][a-z]+\s+(asks|says|tells|answers|replies|shouts|whispers)$', cleaned, re.IGNORECASE))


def preprocess_markdown(text: str) -> str:
    """
    预处理 markdown 文本：
    1. 移除图片标记
    2. 将标题转换为独立句子
    3. 处理段落的换行合并

    参数:
        text: 原始 markdown 文本

    返回:
        预处理后的文本
    """
    lines = text.split('\n')
    result_lines = []
    buffer = ""

    for line in lines:
        line = line.strip()

        if not line:
            if buffer:
                result_lines.append(buffer)
                buffer = ""
            continue

        # 移除图片标记
        if line.startswith('![') or line.startswith('./'):
            if buffer:
                result_lines.append(buffer)
                buffer = ""
            continue

        # 处理标题
        if line.startswith('#'):
            if buffer:
                result_lines.append(buffer)
                buffer = ""
            title_text = re.sub(r'^#+\s*', '', line)
            if title_text:
                result_lines.append(title_text)
            continue

        # 移除 HTML 注释
        if line.startswith('<!--') or line.endswith('-->'):
            continue

        # 合并跨行的对话归属
        if is_dialogue_attribution(line) and buffer:
            buffer = buffer.rstrip() + " " + line
            result_lines.append(buffer)
            buffer = ""
            continue

        if buffer:
            result_lines.append(buffer)
        buffer = line

    if buffer:
        result_lines.append(buffer)

    # 处理每行：确保有结束标点
    processed_texts = []
    for line in result_lines:
        line = re.sub(r'\s+', ' ', line).strip()
        if not line:
            continue
        # 只在没有标点时添加句号
        if line and line[-1] not in '.!?':
            line = line + '.'
        processed_texts.append(line)

    return '  '.join(processed_texts)


def post_process_sentences(sentences: list[str]) -> list[str]:
    """
    后处理断句结果

    参数:
        sentences: spaCy 初步断句结果

    返回:
        处理后的句子列表
    """
    result = []
    i = 0
    while i < len(sentences):
        sent = sentences[i].strip()
        if not sent:
            i += 1
            continue

        # 清理多余的句号（但保留结尾的引号）
        sent = re.sub(r'\.{2,}', '.', sent)
        # 如果有结尾的引号+句号，先去掉句号再检查是否需要添加
        if sent.endswith('".') or sent.endswith("'."):
            sent = sent[:-1]

        # 检查是否需要与下一句合并
        if i + 1 < len(sentences):
            next_sent = sentences[i + 1].strip()

            # 合并条件：当前句以引号开头+以 ?! 结尾，下一句是简短对话归属句
            sent_stripped = sent.rstrip()
            if sent_stripped.endswith('"'):
                sent_stripped = sent_stripped[:-1]
            last_char = sent_stripped[-1] if sent_stripped else ''

            if (sent.startswith('"') and
                last_char in '?!' and
                len(next_sent) < 30 and
                is_dialogue_attribution(next_sent)):
                # 合并并添加句号，清理多余的句号
                merged = sent.rstrip('?!').rstrip() + ' ' + next_sent.rstrip('.!?')
                merged = re.sub(r'\.{2,}', '.', merged)
                sent = merged + '.'
                i += 2
            else:
                i += 1
        else:
            i += 1

        sent = re.sub(r'\s+', ' ', sent).strip()

        # 合并很短的句子（如 "near the barn."）到上一句
        if (len(result) > 0 and
            len(sent) < 20 and
            not sent.startswith('"') and
            not sent[0].isupper()):
            result[-1] = result[-1].rstrip('.') + ' ' + sent
        elif sent:
            result.append(sent)

    return result


def split_sentences(text: str) -> list[str]:
    """
    使用 spaCy 进行断句（主入口函数）

    参数:
        text: 待断句的文本

    返回:
        句子列表
    """
    nlp = get_nlp_model()
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents]
    return post_process_sentences(sentences)
