"""词典查询服务，支持本地ECDICT和FreeDictionaryAPI。"""
import os
import sqlite3
import httpx
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status

from app.schemas.dictionary import DictionaryResponse, WordMeaning, WordDefinition, WordPhonetic


class DictionaryService:
    """词典服务类"""
    
    def __init__(self):
        self.ecdict_db_path = self._get_ecdict_path()
        self._ecdict_conn: Optional[sqlite3.Connection] = None
    
    def _get_ecdict_path(self) -> str:
        """获取ECDICT数据库路径"""
        # 优先使用环境变量配置的路径
        env_path = os.getenv("ECDICT_DB_PATH")
        if env_path and os.path.exists(env_path):
            return env_path
        
        # 默认路径：backend/data/ecdict.db
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        default_path = os.path.join(base_dir, "data", "ecdict.db")
        return default_path
    
    @property
    def ecdict_available(self) -> bool:
        """检查本地ECDICT是否可用"""
        return os.path.exists(self.ecdict_db_path)
    
    def _get_ecdict_connection(self) -> sqlite3.Connection:
        """获取ECDICT数据库连接"""
        if self._ecdict_conn is None:
            self._ecdict_conn = sqlite3.connect(self.ecdict_db_path)
            self._ecdict_conn.row_factory = sqlite3.Row
        return self._ecdict_conn
    
    def _parse_ecdict_definition(self, definition: str) -> List[Dict[str, Any]]:
        """解析ECDICT的定义字符串"""
        definitions = []
        if not definition:
            return definitions
        
        # ECDICT的定义格式通常是：词性. 释义1；释义2\n词性2. 释义...
        lines = definition.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 尝试解析词性和释义
            if '.' in line:
                parts = line.split('.', 1)
                part_of_speech = parts[0].strip()
                defs_text = parts[1].strip() if len(parts) > 1 else ""
                
                # 分割多个释义
                for def_text in defs_text.split('；'):
                    def_text = def_text.strip()
                    if def_text:
                        definitions.append({
                            "partOfSpeech": part_of_speech,
                            "definition": def_text,
                            "example": None
                        })
        
        return definitions
    
    def _format_phonetic(self, phonetic: str) -> str:
        """格式化音标，添加 // 包裹"""
        if not phonetic:
            return phonetic
        phonetic = phonetic.strip()
        # 如果已经有 / 或 [ 包裹，先移除
        if phonetic.startswith('/') and phonetic.endswith('/'):
            phonetic = phonetic[1:-1]
        elif phonetic.startswith('[') and phonetic.endswith(']'):
            phonetic = phonetic[1:-1]
        # 添加 // 包裹
        return f'/{phonetic}/'
    
    def _detect_accent_from_audio(self, audio_url: str) -> str:
        """从音频URL检测口音类型"""
        if not audio_url:
            return 'unknown'
        audio_lower = audio_url.lower()
        if '-uk' in audio_lower or '_uk' in audio_lower:
            return 'uk'
        elif '-us' in audio_lower or '_us' in audio_lower or '-au' in audio_lower:
            return 'us'
        return 'unknown'
    
    async def query_related_phrases(self, word: str) -> List[Dict[str, str]]:
        """
        查询相关词组。

        Args:
            word: 要查询的英文单词

        Returns:
            相关词组列表 [{phrase, translation}, ...]
        """
        if not self.ecdict_available:
            return []

        try:
            conn = self._get_ecdict_connection()
            word_lower = word.lower().strip()

            # 查询以 "{word} " 开头的词组（空格表示词组边界）
            # 使用 LIKE 匹配有空格的词组：word LIKE 'take %' AND word NOT LIKE 'take% %'
            # 这样可以排除 "takeover" 但保留 "take off"
            cursor = conn.execute(
                """SELECT word, translation, frq FROM stardict
                   WHERE word LIKE :pattern
                     AND word LIKE :pattern_with_space
                     AND word NOT LIKE :pattern_ellipsis
                     AND word NOT LIKE :word_plurals
                     AND LENGTH(word) <= :max_len
                   ORDER BY
                     CASE WHEN frq IS NULL OR frq = 0 THEN 1 ELSE 0 END,
                     frq ASC,
                     LENGTH(word) ASC
                   LIMIT 3000""",
                {
                    "pattern": f"{word_lower}%",
                    "pattern_with_space": "% %",
                    "pattern_ellipsis": "%...%",
                    "word_plurals": f"{word_lower}s%",
                    "max_len": len(word_lower) + 15
                }
            )
            rows = cursor.fetchall()

            # 常见介词列表，用于优先排序
            common_preps = ['of', 'to', 'in', 'on', 'at', 'for', 'with', 'by', 'from', 'as']

            phrases = []
            for row in rows:
                row_dict = dict(row)
                phrase = row_dict.get('word', '')
                translation = row_dict.get('translation')

                # 跳过没有翻译的词组
                if not phrase or not translation:
                    continue

                # 保留完整的词组形式（不去掉前缀）
                # 例如 "kind of" 保留为 "kind of"，而不是 "of"
                phrase_part = phrase
                if not phrase_part:
                    continue

                # 过滤掉包含单个字母的词组（如 "kind of f"）
                words = phrase_part.split()
                if any(len(w) == 1 for w in words):
                    continue

                # 处理翻译：只取第一个释义
                try:
                    trans = str(translation).split('\n')[0].split('；')[0].split(';')[0].strip()
                except Exception:
                    trans = str(translation).strip()

                # 即使翻译是乱码也保留，只要不为空
                if not trans:
                    trans = str(translation).strip() if translation else ''
                if not trans:
                    continue

                # 排序逻辑：
                # 优先显示常见固定搭配
                words = phrase_part.split()
                word_count = len(words)

                # 常见固定搭配/短语列表
                # of, to: 介词组合，也有用的如 "kind of", "take of"
                # off, out, up, away 等: 固定搭配，通常更有用
                common_phrases = ['off', 'out', 'away', 'down', 'up', 'over', 'care', 'place', 'action', 'effect',
                                  'part', 'note', 'risk', 'advantage', 'interest', 'break', 'chance', 'turn', 'of']

                # 判断
                if word_count == 2:
                    second_word = words[1].lower()
                    if second_word in common_phrases:
                        sort_score = 0  # 固定搭配优先
                    else:
                        sort_score = 1
                elif word_count == 3:
                    sort_score = 1
                else:
                    sort_score = 2

                phrases.append({
                    "phrase": phrase_part,
                    "translation": trans,
                    "_sort_score": sort_score,
                    "_len": len(phrase_part)
                })

            # 排序：优先固定搭配，然后按得分和长度
            phrases.sort(key=lambda x: (x["_sort_score"], x["_len"]))

            # 返回结果，去掉排序辅助字段
            return [{"phrase": p["phrase"], "translation": p["translation"]} for p in phrases[:5]]

        except Exception as e:
            print(f"查询相关词组失败: {e}")
            return []

    async def query_ecdict(self, word: str) -> Optional[DictionaryResponse]:
        """
        使用本地ECDICT查询单词。
        
        Args:
            word: 要查询的英文单词
            
        Returns:
            查询结果，如果未找到返回None
        """
        if not self.ecdict_available:
            return None
        
        try:
            conn = self._get_ecdict_connection()
            cursor = conn.execute(
                "SELECT * FROM stardict WHERE word = ? COLLATE NOCASE",
                (word.lower().strip(),)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # 解析ECDICT数据
            row_dict = dict(row)
            
            # 构建音标列表
            phonetics = []
            raw_phonetic = row_dict.get('phonetic', '')
            formatted_phonetic = None
            if raw_phonetic:
                # ECDICT音标格式化为 // 包裹，标记为未知口音
                formatted_phonetic = self._format_phonetic(raw_phonetic)
                phonetics.append(WordPhonetic(
                    text=formatted_phonetic,
                    audio=None,
                    accent='unknown'
                ))
            
            # 解析定义
            definition = row_dict.get('definition', '')
            translation = row_dict.get('translation', '')
            
            meanings = []
            
            # 优先使用translation字段（中文翻译）
            if translation:
                # 尝试解析translation字段，格式可能与definition类似
                parsed_translations = self._parse_ecdict_definition(translation)
                if parsed_translations:
                    # 按词性分组
                    pos_groups: Dict[str, List[Dict]] = {}
                    for d in parsed_translations:
                        pos = d.get('partOfSpeech', 'unknown')
                        if pos not in pos_groups:
                            pos_groups[pos] = []
                        pos_groups[pos].append(d)
                    
                    for pos, defs in pos_groups.items():
                        definitions = []
                        for d in defs:
                            definitions.append(WordDefinition(
                                definition=d['definition'],
                                example=d.get('example'),
                                synonyms=[]
                            ))
                        meanings.append(WordMeaning(
                            partOfSpeech=pos,
                            definitions=definitions
                        ))
                else:
                    # 如果无法解析，直接作为纯文本处理
                    meanings.append(WordMeaning(
                        partOfSpeech="释义",
                        definitions=[WordDefinition(
                            definition=translation,
                            example=None,
                            synonyms=[]
                        )]
                    ))
            
            # 如果没有中文翻译，回退到英文definition字段
            if not meanings and definition:
                parsed_defs = self._parse_ecdict_definition(definition)
                pos_groups: Dict[str, List[Dict]] = {}
                for d in parsed_defs:
                    pos = d.get('partOfSpeech', 'unknown')
                    if pos not in pos_groups:
                        pos_groups[pos] = []
                    pos_groups[pos].append(d)
                
                for pos, defs in pos_groups.items():
                    definitions = []
                    for d in defs:
                        definitions.append(WordDefinition(
                            definition=d['definition'],
                            example=d.get('example'),
                            synonyms=[]
                        ))
                    meanings.append(WordMeaning(
                        partOfSpeech=pos,
                        definitions=definitions
                    ))

            # 查询相关词组
            related_phrases = await self.query_related_phrases(word)

            return DictionaryResponse(
                word=row_dict.get('word', word),
                phonetic=formatted_phonetic,
                phonetics=phonetics,
                meanings=meanings,
                source="ecdict",
                tag=row_dict.get('tag'),
                translation=translation if translation else None,
                definition=definition if definition else None,
                exchange=row_dict.get('exchange'),
                related_phrases=related_phrases if related_phrases else None
            )
            
        except Exception as e:
            print(f"ECDICT查询失败: {e}")
            return None
    
    async def query_freedictionary(self, word: str) -> Optional[DictionaryResponse]:
        """
        使用FreeDictionaryAPI查询单词。
        
        Args:
            word: 要查询的英文单词
            
        Returns:
            查询结果，如果未找到返回None
        """
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower().strip()}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url)
                
                if response.status_code == 404:
                    return None
                
                response.raise_for_status()
                data = response.json()
                
                if not data or not isinstance(data, list):
                    return None
                
                # 解析第一个结果
                entry = data[0]
                
                # 构建音标列表
                phonetics = []
                for p in entry.get("phonetics", []):
                    if p.get("text") or p.get("audio"):
                        audio_url = p.get("audio") if p.get("audio") else None
                        phonetic_text = p.get("text")
                        # 格式化音标文本
                        if phonetic_text:
                            phonetic_text = self._format_phonetic(phonetic_text)
                        # 检测口音类型
                        accent = self._detect_accent_from_audio(audio_url) if audio_url else 'unknown'
                        phonetics.append(WordPhonetic(
                            text=phonetic_text,
                            audio=audio_url,
                            accent=accent
                        ))
                
                # 构建释义列表
                meanings = []
                for m in entry.get("meanings", []):
                    definitions = []
                    for d in m.get("definitions", []):
                        definitions.append(WordDefinition(
                            definition=d.get("definition", ""),
                            example=d.get("example"),
                            synonyms=d.get("synonyms", [])[:5]
                        ))
                    
                    if definitions:
                        meanings.append(WordMeaning(
                            partOfSpeech=m.get("partOfSpeech", "unknown"),
                            definitions=definitions[:3]
                        ))
                
                # 格式化主音标
                main_phonetic = entry.get("phonetic")
                if main_phonetic:
                    main_phonetic = self._format_phonetic(main_phonetic)
                
                return DictionaryResponse(
                    word=entry.get("word", word),
                    phonetic=main_phonetic,
                    phonetics=phonetics,
                    meanings=meanings,
                    source="dictionaryapi.dev"
                )
                
            except Exception as e:
                print(f"FreeDictionaryAPI查询失败: {e}")
                return None
    
    async def lookup(
        self,
        word: str,
        source: str = "api"
    ) -> DictionaryResponse:
        """
        查询单词，根据source选择查询方式。

        Args:
            word: 要查询的英文单词
            source: 词典来源，'local'、'api' 或 'baidu'

        Returns:
            单词的详细信息

        Raises:
            HTTPException: 如果单词未找到或服务错误
        """
        word = word.lower().strip()

        if source == "local":
            # 优先使用本地ECDICT
            result = await self.query_ecdict(word)
            if result:
                return result

            # 本地未找到，回退到API
            result = await self.query_freedictionary(word)
            if result:
                # 修改来源标记
                result.source = "dictionaryapi.dev (fallback)"
                return result

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到单词 '{word}' 的释义"
            )

        elif source == "baidu":
            # 百度翻译模式：优先使用本地ECDICT获取详细信息
            result = await self.query_ecdict(word)
            if result:
                return result

            # 本地未找到，回退到API
            result = await self.query_freedictionary(word)
            if result:
                result.source = "dictionaryapi.dev (fallback)"
                return result

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到单词 '{word}' 的释义"
            )

        else:  # source == "api"
            # 使用FreeDictionaryAPI
            result = await self.query_freedictionary(word)
            if result:
                return result

            # API未找到，尝试本地ECDICT
            result = await self.query_ecdict(word)
            if result:
                # 修改来源标记
                result.source = "ecdict (fallback)"
                return result

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到单词 '{word}' 的释义"
            )


# 全局词典服务实例 - 预热：启动时建立连接，加快首次查询
dictionary_service = DictionaryService()
if dictionary_service.ecdict_available:
    dictionary_service._get_ecdict_connection()
