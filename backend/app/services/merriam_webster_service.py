"""韦氏词典服务 - Merriam-Webster Learner's Dictionary 和 Thesaurus API"""
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database_models import MerriamWebsterAPI, User
from app.schemas.dictionary import (
    DictionaryResponse,
    WordMeaning,
    WordDefinition,
    WordPhonetic
)
from app.services.merriam_webster_cache_service import get_cache_service


class MerriamWebsterService:
    """韦氏词典服务类"""

    def __init__(self, learners_key: str, thesaurus_key: Optional[str] = None):
        """
        初始化韦氏词典服务

        Args:
            learners_key: Learner's Dictionary API Key
            thesaurus_key: Collegiate Thesaurus API Key (可选)
        """
        self.learners_key = learners_key
        self.thesaurus_key = thesaurus_key
        self.learners_base_url = "https://www.dictionaryapi.com/api/v3/references/learners/json"
        self.thesaurus_base_url = "https://www.dictionaryapi.com/api/v3/references/thesaurus/json"

    @staticmethod
    async def get_api_keys(db: AsyncSession, user_id: int) -> tuple:
        """
        从数据库获取用户的韦氏词典API Key

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            (learners_key, thesaurus_key) 或 (None, None)
        """
        print(f"[DEBUG MW.get_api_keys] user_id={user_id}")
        # 查找管理员的API配置
        result = await db.execute(
            select(MerriamWebsterAPI).where(
                MerriamWebsterAPI.user_id == user_id,
                MerriamWebsterAPI.is_active == True
            )
        )
        api_config = result.scalars().first()
        print(f"[DEBUG MW.get_api_keys] 用户自己的配置: {api_config}")

        if not api_config:
            # 尝试查找admin用户的配置
            print(f"[DEBUG MW.get_api_keys] 用户没有配置，查找admin用户...")
            admin_result = await db.execute(
                select(User).where(User.username == "admin")
            )
            admin_user = admin_result.scalars().first()
            print(f"[DEBUG MW.get_api_keys] admin_user: {admin_user}")
            if admin_user and admin_user.id != user_id:
                result = await db.execute(
                    select(MerriamWebsterAPI).where(
                        MerriamWebsterAPI.user_id == admin_user.id,
                        MerriamWebsterAPI.is_active == True
                    )
                )
                api_config = result.scalars().first()
                print(f"[DEBUG MW.get_api_keys] admin的配置: {api_config}")

        if not api_config:
            print(f"[DEBUG MW.get_api_keys] 没有找到任何韦氏词典配置，返回 (None, None)")
            return None, None

        print(f"[DEBUG MW.get_api_keys] 返回: (learners_key={'已配置' if api_config.learners_key else '未配置'}, thesaurus_key={'已配置' if api_config.thesaurus_key else '未配置'})")
        return api_config.learners_key, api_config.thesaurus_key

    def _parse_learners_response(self, data: List[Dict]) -> Optional[Dict]:
        """解析Learner's Dictionary响应"""
        if not data or not isinstance(data, list):
            return None

        # 第一个条目通常是主词条
        entry = data[0]
        if not isinstance(entry, dict):
            return None

        return entry

    def _extract_shortdef(self, entry: Dict) -> Optional[str]:
        """提取简短释义"""
        print(f"[DEBUG MW._extract_shortdef] 开始提取, entry keys: {list(entry.keys())}")
        shortdef = entry.get("app-shortdef")
        print(f"[DEBUG MW._extract_shortdef] app-shortdef: {shortdef}, 类型: {type(shortdef)}")

        # 如果是 dict 类型
        if isinstance(shortdef, dict):
            print(f"[DEBUG MW._extract_shortdef] 是 dict 类型")
            defs = shortdef.get("def", [])
            print(f"[DEBUG MW._extract_shortdef] defs: {defs}")
            if defs and isinstance(defs, list) and len(defs) > 0:
                # 移除 {bc} 标签
                text = defs[0]
                print(f"[DEBUG MW._extract_shortdef] text: {text}")
                if isinstance(text, str):
                    return text.replace("{bc}", "").strip()
        # 如果是 list 类型
        elif isinstance(shortdef, list) and len(shortdef) > 0:
            print(f"[DEBUG MW._extract_shortdef] 是 list 类型")
            text = shortdef[0]
            print(f"[DEBUG MW._extract_shortdef] text[0]: {text}, 类型: {type(text)}")
            if isinstance(text, str):
                return text.replace("{bc}", "").strip()
            elif isinstance(text, dict):
                # 可能是 {bc: "..."} 格式
                text = text.get("bc") or text.get("text") or str(text)
                return str(text).replace("{bc}", "").strip()
        
        # 尝试从其他字段获取释义
        print(f"[DEBUG MW._extract_shortdef] app-shortdef 为空，尝试其他字段")
        # 检查是否有 "shortdef" 字段（小写）
        shortdef_lower = entry.get("shortdef")
        print(f"[DEBUG MW._extract_shortdef] shortdef（小写）: {shortdef_lower}")
        if shortdef_lower:
            if isinstance(shortdef_lower, list) and len(shortdef_lower) > 0:
                return str(shortdef_lower[0]).strip()
            elif isinstance(shortdef_lower, str):
                return shortdef_lower.strip()
        
        return None

    def _extract_phonetics(self, entry: Dict) -> List[WordPhonetic]:
        """提取音标信息"""
        phonetics = []

        # 从 hwi (headword information) 获取音标
        hwi = entry.get("hwi", {})
        prs_list = hwi.get("prs", [])
        for pr in prs_list:
            ipa = pr.get("ipa", "")
            sound = pr.get("sound", {})
            audio_url = None
            if sound:
                # 音频文件URL格式
                audio_key = sound.get("audio", "")
                if audio_key:
                    audio_url = f"https://media.merriam-webster.com/audio/prons/en/us/mp3/{audio_key}.mp3"

            if ipa or audio_url:
                # 添加 // 包裹
                formatted_ipa = f"/{ipa}/" if ipa else None
                phonetics.append(WordPhonetic(
                    text=formatted_ipa,
                    audio=audio_url,
                    accent="us"  # Merriam-Webster 默认为美式发音
                ))
        
        # 如果 hwi.prs 为空，从 vrs (变体形式) 获取音标
        if not phonetics:
            vrs_list = entry.get("vrs", [])
            for vr in vrs_list:
                vr_prs = vr.get("prs", [])
                for pr in vr_prs:
                    ipa = pr.get("ipa", "")
                    sound = pr.get("sound", {})
                    audio_url = None
                    if sound:
                        audio_key = sound.get("audio", "")
                        if audio_key:
                            audio_url = f"https://media.merriam-webster.com/audio/prons/en/us/mp3/{audio_key}.mp3"
                    
                    if ipa or audio_url:
                        formatted_ipa = f"/{ipa}/" if ipa else None
                        phonetics.append(WordPhonetic(
                            text=formatted_ipa,
                            audio=audio_url,
                            accent="us"
                        ))

        return phonetics

    def _extract_idioms(self, entry: Dict) -> List[Dict[str, str]]:
        """提取习语/短语"""
        idioms = []
        dros = entry.get("dros", [])

        for dro in dros:
            phrase = dro.get("drp", "")
            def_list = dro.get("def", [])
            if def_list and isinstance(def_list, list):
                # 提取第一个释义
                sense_list = def_list[0].get("sseq", [])
                if sense_list:
                    for seq in sense_list:
                        if isinstance(seq, list) and len(seq) > 1:
                            sense = seq[1]
                            dt = sense.get("dt", [])
                            for d in dt:
                                if isinstance(d, list) and len(d) > 1 and d[0] == "text":
                                    definition = d[1].replace("{bc}", "").strip()
                                    if phrase and definition:
                                        idioms.append({
                                            "phrase": phrase,
                                            "definition": definition
                                        })
                                    break
                        break

        return idioms

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        清理韦氏词典文本中的格式化标记
        
        韦氏词典常用标记：
        - {bc} - 粗体继续
        - {it} - 斜体开始, {/it} - 斜体结束
        - {ldquo} - 左双引号 ", {rdquo} - 右双引号 "
        - {phrase} - 短语标记, {/phrase} - 短语结束
        - {wi} - 词索引开始, {/wi} - 词索引结束
        - {sx|word|num|} - 交叉引用
        """
        if not text:
            return text
        text = str(text)
        # 移除基础标记
        text = text.replace("{bc}", "").replace("{it}", "").replace("{/it}", "")
        # 移除引号标记
        text = text.replace("{ldquo}", '"').replace("{/ldquo}", '"').replace("{rdquo}", '"')
        # 移除短语标记
        text = text.replace("{phrase}", "").replace("{/phrase}", "")
        # 移除词索引标记
        text = text.replace("{wi}", "").replace("{/wi}", "")
        # 移除交叉引用标记（如 {sx|word||1}）
        import re
        text = re.sub(r'\{sx\|[^|]*\|([^|]*)\|[^}]*\}', r'\1', text)
        # 移除其他花括号标记
        text = re.sub(r'\{[^}]+\}', '', text)
        return text.strip()

    def _extract_from_dt(self, dt: list) -> tuple:
        """
        从 dt (definition text) 数组中提取释义和例句
        
        韦氏词典 dt 格式:
        - [['text', '定义文本'], ['wsgram', '语法标注'], ['vis', [{'t': '例句'}]]]
        
        Returns:
            (definition_text, example_text) 元组，如果没找到则返回 None
        """
        if not dt:
            return None
            
        print(f"[DEBUG MW._extract_from_dt] 开始提取, dt 长度: {len(dt)}")
        
        definition_text = None
        example_text = None
        
        for d in dt:
            if not isinstance(d, list) or len(d) < 2:
                print(f"[DEBUG MW._extract_from_dt] d 格式不对: {type(d)}")
                continue

            d_type = d[0]
            d_value = d[1]
            print(f"[DEBUG MW._extract_from_dt] d_type: '{d_type}', d_value 类型: {type(d_value)}")

            # 处理 'text' 类型 - 定义文本
            if d_type == "text":
                text = self._clean_text(d_value)
                if text and not definition_text:
                    definition_text = text
                    print(f"[DEBUG MW._extract_from_dt] 找到定义: {text[:50]}...")
            
            # 处理 'vis' 类型 - 例句
            # vis 格式: ['vis', [{'t': '例句文本'}]]
            elif d_type == "vis":
                print(f"[DEBUG MW._extract_from_dt] 处理 vis, value: {str(d_value)[:100]}")
                if isinstance(d_value, list) and len(d_value) > 0:
                    for vis_item in d_value:
                        if isinstance(vis_item, dict) and "t" in vis_item:
                            example_text = self._clean_text(vis_item["t"])
                            print(f"[DEBUG MW._extract_from_dt] 找到例句: {example_text[:50]}...")
                            break  # 只取第一个例句
            
            # 处理 'uns' 类型 - 使用说明
            elif d_type == "uns":
                print(f"[DEBUG MW._extract_from_dt] 处理 uns, value 类型: {type(d_value)}")
                if isinstance(d_value, list):
                    for item in d_value:
                        if isinstance(item, list) and len(item) >= 2:
                            item_type = item[0]
                            if item_type == "text" and not definition_text:
                                text = self._clean_text(item[1])
                                definition_text = text
                                print(f"[DEBUG MW._extract_from_dt] 找到定义(uns): {text[:50]}...")
                            elif item_type == "vis":
                                vis_list = item[1] if len(item) > 1 else []
                                if isinstance(vis_list, list) and len(vis_list) > 0:
                                    vis_item = vis_list[0]
                                    if isinstance(vis_item, dict) and "t" in vis_item:
                                        example_text = self._clean_text(vis_item["t"])
                                        print(f"[DEBUG MW._extract_from_dt] 找到例句(uns): {example_text[:50]}...")
        
        if definition_text:
            print(f"[DEBUG MW._extract_from_dt] 返回: 定义={definition_text[:30]}..., 例句={example_text[:30] if example_text else 'None'}...")
            return (definition_text, example_text)
        
        print(f"[DEBUG MW._extract_from_dt] 未找到定义")
        return None

    def _extract_definitions(self, entry: Dict) -> List[WordMeaning]:
        """
        提取释义列表
        
        韦氏词典数据结构（根据 dictionaryapi.com 官方文档）：
        - def: 包含 sseq (sense sequence)
        - sseq: [[sense_block], [sense_block], ...]
        - sense_block: [["sense", {sense_data}], ["sense", {sense_data}], ...]
          注意：同一个 block 可以有多个 sense
        - sense_data: {"sn": "1 a", "dt": [["text", "..."], ["vis", [{"t": "..."}]]]}
        """
        print(f"[DEBUG MW._extract_definitions] 开始提取, entry keys: {list(entry.keys())}")
        meanings = []
        fl = entry.get("fl", "")  # 词性
        print(f"[DEBUG MW._extract_definitions] fl (词性): '{fl}'")
        def_list = entry.get("def", [])
        print(f"[DEBUG MW._extract_definitions] def 列表长度: {len(def_list) if def_list else 0}")

        for def_item in def_list:
            if not isinstance(def_item, dict):
                print(f"[DEBUG MW._extract_definitions] def_item 不是 dict，跳过")
                continue

            sseq = def_item.get("sseq", [])
            print(f"[DEBUG MW._extract_definitions] sseq 长度: {len(sseq) if sseq else 0}")
            
            # sseq 结构: [[sense_block], [sense_block], ...]
            # sense_block: [["sense", {sn, dt}], ["sense", {...}], ...]
            for sense_block in sseq:
                print(f"[DEBUG MW._extract_definitions] 处理 sense_block, 类型: {type(sense_block)}")
                
                if not isinstance(sense_block, list):
                    print(f"[DEBUG MW._extract_definitions] sense_block 不是 list，跳过")
                    continue
                
                # 遍历 block 中的所有 sense
                for sense_item in sense_block:
                    if not isinstance(sense_item, list) or len(sense_item) < 2:
                        continue
                    
                    sense_label = sense_item[0]  # 应该是 "sense"
                    sense_data = sense_item[1]
                    
                    print(f"[DEBUG MW._extract_definitions] sense_label: '{sense_label}', sense_data 类型: {type(sense_data)}")
                    
                    if sense_label != "sense" or not isinstance(sense_data, dict):
                        continue
                    
                    # 提取 dt
                    dt = sense_data.get("dt", [])
                    if not dt:
                        continue
                    
                    print(f"[DEBUG MW._extract_definitions] dt 长度: {len(dt)}")
                    print(f"[DEBUG MW._extract_definitions] dt[0]: {str(dt[0])[:150]}")
                    
                    # 从 dt 提取定义和例句
                    result = self._extract_from_dt(dt)
                    if result and result[0]:
                        definition_text, example_text = result
                        meanings.append(WordMeaning(
                            partOfSpeech=fl or "unknown",
                            definitions=[WordDefinition(
                                definition=definition_text,
                                example=example_text,
                                synonyms=[],
                                antonyms=[]
                            )]
                        ))
                        print(f"[DEBUG MW._extract_definitions] 添加释义，当前总计: {len(meanings)}")

        print(f"[DEBUG MW._extract_definitions] 最终返回 {len(meanings)} 个释义")
        return meanings

    async def query_learners(self, word: str) -> Optional[Dict]:
        """
        查询 Learner's Dictionary

        Args:
            word: 要查询的单词

        Returns:
            解析后的词典数据
        """
        url = f"{self.learners_base_url}/{word.lower().strip()}?key={self.learners_key}"
        print(f"[DEBUG MW] query_learners - 单词: {word}, URL: {url}")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                print(f"[DEBUG MW] 发送请求到韦氏词典...")
                response = await client.get(url)
                print(f"[DEBUG MW] 响应状态码: {response.status_code}")

                if response.status_code == 404:
                    print(f"[DEBUG MW] 404 - 单词未找到")
                    return None

                response.raise_for_status()
                data = response.json()
                print(f"[DEBUG MW] 返回数据长度: {len(data) if isinstance(data, list) else 'N/A'}")

                if not data or not isinstance(data, list):
                    print(f"[DEBUG MW] 数据为空或非列表格式")
                    return None

                # 检查第一个条目是否是字符串（建议词）
                entry = data[0]
                print(f"[DEBUG MW] 第一个条目类型: {type(entry)}, 值: {entry if isinstance(entry, str) else 'dict'}")
                if isinstance(entry, str):
                    print(f"[DEBUG MW] 返回的是建议词: {entry}")
                    return None

                # 解析数据
                try:
                    shortdef = self._extract_shortdef(entry)
                    print(f"[DEBUG MW] shortdef: {shortdef}")
                except Exception as e:
                    print(f"[DEBUG MW] _extract_shortdef error: {e}")
                    shortdef = None

                try:
                    phonetics = self._extract_phonetics(entry)
                    print(f"[DEBUG MW] phonetics: {len(phonetics)} items")
                except Exception as e:
                    print(f"[DEBUG MW] _extract_phonetics error: {e}")
                    phonetics = []

                try:
                    meanings = self._extract_definitions(entry)
                    print(f"[DEBUG MW] meanings: {len(meanings)} items")
                except Exception as e:
                    print(f"[DEBUG MW] _extract_definitions error: {e}")
                    meanings = []

                try:
                    idioms = self._extract_idioms(entry)
                    print(f"[DEBUG MW] idioms: {len(idioms)} items")
                except Exception as e:
                    print(f"[DEBUG MW] _extract_idioms error: {e}")
                    idioms = []

                # 使用第一个音标作为 phonetic 字段（已格式化为 // 包裹）
                phonetic_text = phonetics[0].text if phonetics else None
                
                # 清理 headword 中的星号（韦氏词典用 * 标记音节划分，如 il*lus*trate）
                headword = entry.get("hwi", {}).get("hw", word)
                headword = headword.replace("*", "")
                
                result = {
                    "word": headword,
                    "phonetic": phonetic_text,
                    "phonetics": phonetics,
                    "meanings": meanings,
                    "idioms": idioms if idioms else None,
                    "source": "merriam-webster-learners"
                }
                print(f"[DEBUG MW] 返回结果: {result}")
                return result

        except Exception as e:
            print(f"[DEBUG MW] 异常: {e}")
            print(f"Merriam-Webster Learner's Dictionary 查询失败: {e}")
            return None

    def _parse_thesaurus_response(self, data: List[Dict]) -> Optional[Dict]:
        """解析Thesaurus响应"""
        if not data or not isinstance(data, list):
            return None

        entry = data[0]
        if not isinstance(entry, dict):
            return None

        return entry

    def _extract_thesaurus_synonyms_antonyms(self, entry: Dict) -> tuple:
        """
        提取同义词和反义词
        
        Thesaurus 数据结构（根据 dictionaryapi.com 官方文档）：
        - syns: [["word1", "word2"]] - 字符串数组
        - syn_list: [[{"wd": "word"}, ...]] - 对象数组
        - ant_list: [[{"wd": "word"}, ...]]
        - near_list: [[{"wd": "word"}, ...]]
        """
        synonyms = []
        antonyms = []
        
        # 1. 优先从 meta.syns 提取（字符串格式）
        meta = entry.get("meta", {})
        meta_syns = meta.get("syns", [])
        meta_ants = meta.get("ants", [])
        
        print(f"[DEBUG MW._extract_thesaurus] meta.syns: {meta_syns}")
        print(f"[DEBUG MW._extract_thesaurus] meta.ants: {meta_ants}")
        
        # 解析 meta.syns: [["word1", "word2"]]
        for syn_group in meta_syns:
            if isinstance(syn_group, list):
                for w in syn_group:
                    if isinstance(w, str) and w not in synonyms:
                        synonyms.append(w)
        
        # 解析 meta.ants: [["word1", "word2"]]
        for ant_group in meta_ants:
            if isinstance(ant_group, list):
                for w in ant_group:
                    if isinstance(w, str) and w not in antonyms:
                        antonyms.append(w)
        
        # 2. 从 syn_list 提取（对象格式）
        syn_list = entry.get("syn_list", [])
        print(f"[DEBUG MW._extract_thesaurus] syn_list: {syn_list[:2] if syn_list else 'None'}")
        
        for group in syn_list:
            if isinstance(group, list):
                for item in group:
                    if isinstance(item, dict) and "wd" in item:
                        word = item["wd"]
                        if word not in synonyms:
                            synonyms.append(word)
        
        # 3. 从 ant_list 提取
        ant_list = entry.get("ant_list", [])
        print(f"[DEBUG MW._extract_thesaurus] ant_list: {ant_list[:2] if ant_list else 'None'}")
        
        for group in ant_list:
            if isinstance(group, list):
                for item in group:
                    if isinstance(item, dict) and "wd" in item:
                        word = item["wd"]
                        if word not in antonyms:
                            antonyms.append(word)
        
        print(f"[DEBUG MW._extract_thesaurus] 最终 synonyms: {synonyms[:5]}, antonyms: {antonyms[:5]}")
        return synonyms, antonyms

    async def query_thesaurus(self, word: str) -> Optional[Dict]:
        """
        查询 Collegiate Thesaurus

        Args:
            word: 要查询的单词

        Returns:
            解析后的 Thesaurus 数据
        """
        print(f"[DEBUG MW.thesaurus] 查询 Thesaurus: {word}")
        if not self.thesaurus_key:
            print(f"[DEBUG MW.thesaurus] 没有配置 Thesaurus Key，跳过")
            return None

        url = f"{self.thesaurus_base_url}/{word.lower().strip()}?key={self.thesaurus_key}"
        print(f"[DEBUG MW.thesaurus] URL: {url}")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                print(f"[DEBUG MW.thesaurus] 发送请求...")
                response = await client.get(url)
                print(f"[DEBUG MW.thesaurus] 响应状态: {response.status_code}")

                if response.status_code == 404:
                    print(f"[DEBUG MW.thesaurus] 404 - 单词未找到")
                    return None

                response.raise_for_status()
                data = response.json()
                print(f"[DEBUG MW.thesaurus] 返回数据长度: {len(data) if isinstance(data, list) else 'N/A'}")

                if not data or not isinstance(data, list):
                    print(f"[DEBUG MW.thesaurus] 数据为空")
                    return None

                # 检查第一个条目是否是字符串
                entry = data[0]
                print(f"[DEBUG MW.thesaurus] 第一个条目类型: {type(entry)}")
                if isinstance(entry, str):
                    print(f"[DEBUG MW.thesaurus] 返回建议词: {entry}")
                    return None

                synonyms, antonyms = self._extract_thesaurus_synonyms_antonyms(entry)
                print(f"[DEBUG MW.thesaurus] synonyms: {len(synonyms)}, antonyms: {len(antonyms)}")

                result = {
                    "word": entry.get("meta", {}).get("id", word),
                    "synonyms": synonyms,
                    "antonyms": antonyms,
                    "source": "merriam-webster-thesaurus"
                }
                print(f"[DEBUG MW.thesaurus] 返回: {result}")
                return result

        except Exception as e:
            print(f"[DEBUG MW.thesaurus] 异常: {e}")
            print(f"Merriam-Webster Thesaurus 查询失败: {e}")
            return None

    async def lookup(self, word: str, use_cache: bool = True) -> Optional[DictionaryResponse]:
        """
        查询单词，合并 Learner's Dictionary 和 Thesaurus 结果
        支持离线缓存：首次查询从API获取并缓存，后续优先从缓存获取

        Args:
            word: 要查询的单词
            use_cache: 是否使用缓存（默认True）

        Returns:
            合并后的词典响应
        """
        print(f"[DEBUG MW.lookup] 开始查询单词: {word}, use_cache={use_cache}")

        # 1. 优先从缓存获取
        if use_cache:
            cache_service = get_cache_service()
            cached_data = cache_service.get_from_cache(word)
            if cached_data:
                print(f"[DEBUG MW.lookup] 从缓存命中: {word}")
                # 从缓存构建响应
                response = DictionaryResponse(
                    word=cached_data.get("word", word),
                    phonetic=cached_data.get("phonetic"),
                    phonetics=cached_data.get("phonetics", []),
                    meanings=cached_data.get("meanings", []),
                    source="merriam-webster",
                    idioms=cached_data.get("idioms"),
                    thesaurus_synonyms=cached_data.get("thesaurus_synonyms", []),
                    thesaurus_antonyms=cached_data.get("thesaurus_antonyms", [])
                )
                print(f"[DEBUG MW.lookup] 缓存命中返回, meanings={len(response.meanings)}")
                return response
            print(f"[DEBUG MW.lookup] 缓存未命中，将查询API并缓存: {word}")

        # 2. 缓存未命中，从API查询
        learners_data = await self.query_learners(word)
        print(f"[DEBUG MW.lookup] query_learners 返回: {learners_data}")
        thesaurus_data = await self.query_thesaurus(word)
        print(f"[DEBUG MW.lookup] query_thesaurus 返回: {thesaurus_data}")

        if not learners_data:
            print(f"[DEBUG MW.lookup] learners_data 为空，返回 None")
            return None

        # 构建响应
        response = DictionaryResponse(
            word=learners_data.get("word", word),
            phonetic=learners_data.get("phonetic"),
            phonetics=learners_data.get("phonetics", []),
            meanings=learners_data.get("meanings", []),
            source="merriam-webster",
            idioms=learners_data.get("idioms")
        )
        print(f"[DEBUG MW.lookup] 构建响应完成, meanings count: {len(response.meanings)}")

        # 合并 Thesaurus 数据
        if thesaurus_data:
            response.thesaurus_synonyms = thesaurus_data.get("synonyms", [])
            response.thesaurus_antonyms = thesaurus_data.get("antonyms", [])

        # 3. 保存到缓存（异步，不阻塞返回）
        if use_cache:
            cache_service = get_cache_service()
            # 提取音频URL（phonetics 是 WordPhonetic 对象列表）
            audio_url = None
            if learners_data.get("phonetics") and len(learners_data["phonetics"]) > 0:
                audio_url = learners_data["phonetics"][0].audio

            # 构建可序列化的缓存数据（将Pydantic对象转为dict）
            cache_data = {
                "word": learners_data.get("word", word),
                "phonetic": learners_data.get("phonetic"),
                "phonetics": [p.model_dump() for p in learners_data.get("phonetics", [])],
                "meanings": [m.model_dump() for m in learners_data.get("meanings", [])],
                "source": learners_data.get("source", "merriam-webster"),
                "idioms": learners_data.get("idioms"),
                "thesaurus_synonyms": response.thesaurus_synonyms or [],
                "thesaurus_antonyms": response.thesaurus_antonyms or []
            }
            asyncio.create_task(cache_service.save_to_cache(word, cache_data, audio_url))

        print(f"[DEBUG MW.lookup] 最终返回 response, word={response.word}, meanings={len(response.meanings)}")
        return response
