/**
 * DictResultPopup.vue - 词典结果弹窗组件
 *
 * 功能：
 * - 显示单词查询结果
 * - 支持 ECDICT 和 FreeDictionaryAPI 两种显示格式
 * - 支持播放发音
 * - 支持添加到生词本
 * - 支持点击单词触发二次查询
 */
<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    :style="{ maxHeight: '60%' }"
    @update:show="handleUpdateShow"
    @click-overlay="handleOverlayClick"
  >
    <div class="dict-popup-content" @click="handleContentClick">
      <div v-if="loading" class="dict-loading">
        <van-loading type="spinner" size="24px" />
        <span>查询中...</span>
      </div>
      <div v-else-if="error" class="dict-error">
        <i class="fas fa-triangle-exclamation" style="font-size: 32px; color: #ee0a24;"></i>
        <p>{{ error }}</p>
      </div>
      <div v-else-if="data" class="dict-result">
        <!-- ECDICT 格式显示 -->
        <template v-if="data.source === 'ecdict'">
          <div class="dict-header">
            <h3 class="dict-word">{{ data.word }}</h3>
            <span class="dict-source-tag">本地词典</span>
            <span v-if="data.phonetic" class="dict-phonetic">{{ data.phonetic }}</span>
            <WordPronunciation :word="data.word" accent="auto" />
            <van-button
              class="vocab-btn"
              size="mini"
              type="primary"
              :loading="addingToVocabulary"
              @click="handleAddToVocabulary"
            >
              <i class="fas fa-plus" style="margin-right: 4px;"></i>生词本
            </van-button>
            <div v-if="data.tag" class="dict-tags">
              <span v-for="(tag, idx) in formatTags(data.tag)" :key="idx" class="dict-tag">{{ tag }}</span>
            </div>
          </div>
          <!-- 中文翻译 -->
          <div v-if="data.translation" class="dict-translation">
            <div class="dict-section-title">中文释义</div>
            <div class="dict-translation-content">{{ data.translation }}</div>
          </div>
          <!-- 句子翻译结果 -->
          <div v-if="sentenceText" class="dict-sentence-translation">
            <div class="dict-section-title">句子翻译</div>
            <div class="dict-sentence-original">{{ sentenceText }}</div>
            <div v-if="sentenceLoading" class="dict-sentence-loading">翻译中...</div>
            <div v-else-if="sentenceError" class="dict-sentence-error">{{ sentenceError }}</div>
            <div v-else class="dict-sentence-translated">{{ data.sentence_translation || '' }}</div>
          </div>
          <!-- 分隔线 -->
          <div v-if="data.translation && data.definition" class="dict-divider"></div>
          <!-- 英文释义 -->
          <div v-if="data.definition" class="dict-definition">
            <div class="dict-section-title">英文释义</div>
            <div class="dict-definition-content">{{ data.definition }}</div>
          </div>
          <!-- 时态变换 -->
          <div v-if="data.exchange" class="dict-exchange">
            <div class="dict-section-title">词形变换</div>
            <div class="dict-exchange-content">{{ formatExchange(data.exchange) }}</div>
          </div>
          <!-- 相关词组（词组查询不显示） -->
          <div v-if="!props.isPhrase && data.related_phrases && data.related_phrases.length > 0" class="dict-related-phrases">
            <div class="dict-section-title">相关词组</div>
            <div class="dict-phrases-list">
              <div v-for="(item, idx) in data.related_phrases" :key="idx" 
                class="dict-phrase-item"
                @contextmenu="handlePhraseContextMenu($event, item.phrase, item.translation)"
                @touchstart="handlePhraseTouchStart($event, item)"
                @touchend="handlePhraseTouchEnd(item.phrase, item.translation)">
                <span class="dict-phrase">{{ item.phrase }}</span>
                <span class="dict-phrase-translation">{{ item.translation }}</span>
              </div>
            </div>
          </div>
        </template>
        <!-- API 格式显示 -->
        <template v-else>
          <div class="dict-header">
            <h3 class="dict-word">{{ data.word }}</h3>
            <span class="dict-source-tag">{{ sourceLabel }}</span>
            <span v-if="data.phonetic" class="dict-phonetic">{{ data.phonetic }}</span>
            <WordPronunciation :word="data.word" accent="auto" />
            <van-button
              class="vocab-btn"
              size="mini"
              type="primary"
              :loading="addingToVocabulary"
              @click="handleAddToVocabulary"
            >
              <i class="fas fa-plus" style="margin-right: 4px;"></i>生词本
            </van-button>
          </div>
          <!-- 词源 -->
          <div v-if="data.origin" class="dict-origin">
            <div class="dict-section-title">词源</div>
            <div class="dict-origin-content">{{ data.origin }}</div>
          </div>
          <!-- 释义列表 -->
          <div class="dict-meanings">
            <template v-for="(meaning, idx) in data.meanings" :key="idx">
              <!-- 词性标题 -->
              <div class="dict-pos-title">{{ idx + 1 }}. {{ meaning.partOfSpeech }}</div>
              <!-- 该词性下的所有释义 -->
              <div class="dict-definitions">
                <div
                  v-for="(def, dIdx) in meaning.definitions"
                  :key="dIdx"
                  class="dict-def-item"
                >
                  <!-- 释义 -->
                  <div class="dict-definition-text">
                    <span class="dict-label">释义：</span>
                    {{ def.definition }}
                  </div>
                  <!-- 例句 -->
                  <div v-if="def.example" class="dict-example-text">
                    <span class="dict-label">例句：</span>
                    "{{ def.example }}"
                  </div>
                  <!-- 同义词 -->
                  <div v-if="def.synonyms?.length" class="dict-synonyms-text">
                    <span class="dict-label">同义词：</span>
                    {{ def.synonyms.join('；') }}
                  </div>
                  <!-- 反义词 -->
                  <div v-if="def.antonyms?.length" class="dict-antonyms-text">
                    <span class="dict-label">反义词：</span>
                    {{ def.antonyms.join('；') }}
                  </div>
                </div>
              </div>
            </template>
          </div>
          <!-- 句子翻译结果 -->
          <div v-if="sentenceText" class="dict-sentence-translation">
            <div class="dict-section-title">句子翻译</div>
            <div class="dict-sentence-original">{{ sentenceText }}</div>
            <div v-if="sentenceLoading" class="dict-sentence-loading">翻译中...</div>
            <div v-else-if="sentenceError" class="dict-sentence-error">{{ sentenceError }}</div>
            <div v-else class="dict-sentence-translated">{{ data.sentence_translation || '' }}</div>
          </div>
          <!-- 韦氏词典Thesaurus同义词 -->
          <div v-if="data.thesaurus_synonyms?.length" class="dict-thesaurus-section">
            <div class="dict-section-title">Thesaurus 同义词</div>
            <div class="dict-thesaurus-words">
              <span
                v-for="(syn, sIdx) in data.thesaurus_synonyms"
                :key="sIdx"
                class="dict-thesaurus-word"
              >{{ syn }}</span>
            </div>
          </div>
          <!-- 韦氏词典Thesaurus反义词 -->
          <div v-if="data.thesaurus_antonyms?.length" class="dict-thesaurus-section">
            <div class="dict-section-title">Thesaurus 反义词</div>
            <div class="dict-thesaurus-words dict-antonyms-words">
              <span
                v-for="(ant, aIdx) in data.thesaurus_antonyms"
                :key="aIdx"
                class="dict-thesaurus-word"
              >{{ ant }}</span>
            </div>
          </div>
          <!-- 韦氏词典习语 -->
          <div v-if="data.idioms?.length" class="dict-idioms-section">
            <div class="dict-section-title">习语</div>
            <div class="dict-idioms-list">
              <div v-for="(idiom, iIdx) in data.idioms" :key="iIdx" class="dict-idiom-item">
                <span class="dict-idiom-phrase">{{ idiom.phrase }}</span>
                <span class="dict-idiom-def">{{ idiom.definition }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { showToast } from 'vant'
import { api } from '@/store/auth'
import WordPronunciation from '@/components/WordPronunciation.vue'

// 词典源显示名称映射
const dictionarySourceLabels: Record<string, string> = {
  'ecdict': '本地词典',
  'local': '本地词典',
  'ecdict (fallback)': '本地词典',
  'api': 'FreeDictionary',
  'dictionaryapi.dev': 'FreeDictionary',
  'dictionaryapi.dev (fallback)': 'FreeDictionary',
  'merriam-webster': '韦氏词典',
  'merriam-webster-learners': '韦氏词典',
  'phrase_translation': '词组翻译'
}

// 获取词典源显示名称
const sourceLabel = computed(() => {
  if (!props.data?.source) return '在线词典'
  return dictionarySourceLabels[props.data.source] || '在线词典'
})

interface DictionaryData {
  word: string
  phonetic?: string
  phonetics: Array<{ text?: string; audio?: string; accent?: string }>
  meanings: Array<{
    partOfSpeech: string
    definitions: Array<{
      definition: string
      example?: string
      synonyms: string[]
      antonyms: string[]
    }>
  }>
  source?: string
  tag?: string
  translation?: string
  definition?: string
  exchange?: string
  origin?: string
  baidu_translation?: string
  sentence_translation?: string
  related_phrases?: Array<{ phrase: string; translation: string }>
  // 韦氏词典Thesaurus特有
  thesaurus_synonyms?: string[]
  thesaurus_antonyms?: string[]
  idioms?: Array<{ phrase: string; definition: string }>
}

const props = defineProps<{
  show: boolean
  data: DictionaryData | null
  loading: boolean
  error: string
  sentenceText?: string
  sentenceLoading?: boolean
  sentenceError?: string
  /** 是否为词组查询（词组查询不显示相关词组） */
  isPhrase?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'add-to-vocabulary', word: string, translation: string, phonetic: string): void
  (e: 'lookup-word', word: string): void
  (e: 'lookup-phrase', phrase: string, translation: string): void
}>()

const addingToVocabulary = ref(false)

const handleUpdateShow = (value: boolean) => {
  emit('update:show', value)
}

const handleOverlayClick = () => {
  emit('update:show', false)
}

// 格式化词形变换
const formatExchange = (exchange: string): string => {
  if (!exchange) return ''
  const mapping: Record<string, string> = {
    'p:': '过去式: ',
    'd:': '过去分词: ',
    '3:': '第三人称: ',
    's:': '复数: ',
    'i:': '现在分词: ',
    'r:': '比较级: ',
    't:': '最高级: ',
    '0:': '原型: ',
    '1:': '变形: '
  }
  return exchange.split('/').map(item => {
    for (const [key, label] of Object.entries(mapping)) {
      if (item.startsWith(key)) {
        return label + item.slice(key.length)
      }
    }
    return item
  }).join(' / ')
}

// 标签映射表
const tagMapping: Record<string, string> = {
  'zk': '中考',
  'gk': '高考',
  'cet4': '四级',
  'cet6': '六级',
  'ielts': '雅思',
  'toefl': '托福',
  'gre': 'GRE',
  'gmat': 'GMAT',
  'sat': 'SAT',
  'ky': '考研'
}

// 格式化标签
const formatTags = (tag: string): string[] => {
  if (!tag) return []
  return tag.split(/\s+/).map(t => tagMapping[t] || t)
}

// 添加到生词本
const handleAddToVocabulary = async () => {
  if (!props.data) return

  addingToVocabulary.value = true
  try {
    let translation = ''
    if (props.data.translation) {
      translation = props.data.translation
    } else if (props.data.meanings && props.data.meanings.length > 0) {
      translation = props.data.meanings
        .map(m => m.definitions.map(d => d.definition).join('; '))
        .join('; ')
    }

    emit('add-to-vocabulary', props.data.word, translation, props.data.phonetic || '')
    showToast('已加入生词本')
  } catch (error: any) {
    if (error.response?.status === 409) {
      showToast('该生词已存在')
    } else {
      showToast('添加失败')
    }
  } finally {
    addingToVocabulary.value = false
  }
}

// 处理弹窗内容点击（查找点击的单词）
const handleContentClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement

  // 检查点击的是否是英文文本
  const word = getWordFromClick(e, target)
  if (word && /^[a-zA-Z]+$/.test(word)) {
    emit('lookup-word', word)
  }
}

// 从点击事件中提取单词
const getWordFromClick = (e: MouseEvent, _target: HTMLElement): string => {
  // 如果有选中的文本，使用选中的内容
  const selection = window.getSelection()
  if (selection && selection.toString().trim()) {
    return selection.toString().trim()
  }

  // 否则尝试从点击位置获取单词
  let range: Range | null = null

  if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(e.clientX, e.clientY)
    if (pos) {
      range = document.createRange()
      range.setStart(pos.offsetNode, pos.offset)
      range.setEnd(pos.offsetNode, pos.offset)
    }
  } else if ((document as any).caretRangeFromPoint) {
    range = (document as any).caretRangeFromPoint(e.clientX, e.clientY)
  }

  if (range) {
    const textNode = range.startContainer
    if (textNode.nodeType === Node.TEXT_NODE) {
      const textContent = textNode.textContent || ''
      let startOffset = range.startOffset
      let endOffset = range.startOffset

      while (startOffset > 0 && /[a-zA-Z]/.test(textContent[startOffset - 1])) {
        startOffset--
      }

      while (endOffset < textContent.length && /[a-zA-Z]/.test(textContent[endOffset])) {
        endOffset++
      }

      return textContent.substring(startOffset, endOffset)
    }
  }

  return ''
}

// 词组触摸相关变量
let phraseLongPressTimer: any = null

// 处理词组右键菜单
const handlePhraseContextMenu = (e: MouseEvent, phrase: string, translation: string) => {
  e.preventDefault()
  emit('lookup-phrase', phrase, translation)
}

// 处理词组触摸开始
const handlePhraseTouchStart = (_e: TouchEvent, item: any) => {
  phraseLongPressTimer = setTimeout(() => {
    emit('lookup-phrase', item.phrase, item.translation)
    phraseLongPressTimer = null
  }, 500)
}

// 处理词组触摸结束
const handlePhraseTouchEnd = (_phrase: string, _translation: string) => {
  if (phraseLongPressTimer) {
    clearTimeout(phraseLongPressTimer)
    phraseLongPressTimer = null
  }
}
</script>

<style scoped>
/* 词典弹窗样式 */
.dict-popup-content {
  padding: 20px;
  min-height: 200px;
}

.dict-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 0;
  color: #666;
}

.dict-error {
  text-align: center;
  padding: 40px 0;
  color: #666;
}

.dict-error p {
  margin-top: 10px;
}

.dict-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
  flex-wrap: wrap;
}

.dict-word {
  font-size: 24px;
  font-weight: bold;
  color: #333;
  margin: 0;
}

.dict-source-tag {
  font-size: 12px;
  color: #969799;
  background: #f7f8fa;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 8px;
}

.vocab-btn {
  margin-left: auto;
}

.vocab-btn :deep(.van-button__text) {
  font-size: 12px;
}

.dict-phonetic {
  font-size: 16px;
  color: #666;
  font-family: 'Times New Roman', serif;
}

.dict-audio-btn {
  font-size: 20px;
  color: #1989fa;
  cursor: pointer;
  padding: 4px;
}

.dict-meanings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ECDICT 特有样式 */
.dict-tags {
  display: flex;
  gap: 6px;
  margin-left: auto;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.dict-tag {
  font-size: 11px;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
}

.dict-section-title {
  font-size: 12px;
  color: #999;
  margin-bottom: 6px;
  font-weight: 500;
}

.dict-translation {
  margin-bottom: 16px;
}

.dict-translation-content {
  font-size: 15px;
  color: #333;
  line-height: 1.6;
  white-space: pre-line;
}

.dict-divider {
  height: 1px;
  background: #eee;
  margin: 16px 0;
}

.dict-definition {
  margin-bottom: 16px;
}

.dict-definition-content {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
  white-space: pre-line;
}

.dict-exchange {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #eee;
}

.dict-exchange-content {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
}

.dict-related-phrases {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #eee;
}

.dict-phrases-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dict-phrase-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
  user-select: none;
}

.dict-phrase {
  color: #1989fa;
  font-weight: 500;
  white-space: nowrap;
}

.dict-phrase-translation {
  color: #666;
}

/* 词源样式 */
.dict-origin {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}
.dict-origin-content {
  font-size: 13px;
  color: #666;
  line-height: 1.6;
}

/* 词性标题样式 */
.dict-pos-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  padding: 8px 16px 4px;
}

/* 释义容器 */
.dict-definitions {
  padding: 0 16px 8px;
}

/* 单个释义项 */
.dict-def-item {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #f0f0f0;
}
.dict-def-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

/* 释义/例句/同义词/反义词的通用标签样式 */
.dict-label {
  color: #999;
  font-size: 12px;
}

/* 释义文本 */
.dict-definition-text {
  font-size: 14px;
  color: #333;
  line-height: 1.6;
  margin-bottom: 4px;
}

/* 例句文本 */
.dict-example-text {
  font-size: 13px;
  color: #666;
  font-style: italic;
  margin: 4px 0 4px 0;
  padding-left: 8px;
  border-left: 2px solid #e3f2fd;
}

/* 同义词/反义词文本 */
.dict-synonyms-text,
.dict-antonyms-text {
  font-size: 12px;
  color: #1989fa;
  margin-top: 4px;
}

/* 句子翻译结果样式 */
.dict-sentence-translation {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed #eee;
}

.dict-sentence-original {
  font-size: 14px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 8px;
  font-style: italic;
}

.dict-sentence-translated {
  font-size: 15px;
  color: #07c160;
  line-height: 1.6;
}

.dict-sentence-loading {
  font-size: 14px;
  color: #969799;
  line-height: 1.6;
  margin-top: 4px;
}

.dict-sentence-error {
  font-size: 13px;
  color: #ee0a24;
  line-height: 1.5;
  margin-top: 4px;
}

/* Thesaurus 同义词/反义词样式 */
.dict-thesaurus-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed #eee;
}

.dict-thesaurus-words {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.dict-thesaurus-word {
  font-size: 13px;
  color: #1989fa;
  background: #f0f7ff;
  padding: 4px 10px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.dict-thesaurus-word:hover {
  background: #1989fa;
  color: #fff;
}

.dict-antonyms-words .dict-thesaurus-word {
  color: #ee0a24;
  background: #fff0f0;
}

.dict-antonyms-words .dict-thesaurus-word:hover {
  background: #ee0a24;
  color: #fff;
}

/* 习语样式 */
.dict-idioms-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed #eee;
}

.dict-idioms-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.dict-idiom-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: #f7f8fa;
  border-radius: 6px;
}

.dict-idiom-phrase {
  font-size: 14px;
  color: #1989fa;
  font-weight: 500;
  cursor: pointer;
}

.dict-idiom-def {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
}
</style>
