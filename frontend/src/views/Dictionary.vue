/**
 * Dictionary.vue - 词典查询页面
 *
 * 功能：
 * - 搜索单词或词组
 * - 显示查询结果
 * - 横屏时右侧显示查询历史
 * - 点击历史记录可快速查询
 * - 支持添加到生词本
 */
<template>
  <div class="dictionary-page">
    <!-- 顶部导航栏 -->
    <van-nav-bar
      title="词典查询"
      left-text="返回"
      left-arrow
      fixed
      placeholder
      @click-left="goBack"
    >
      <template #right>
        <!-- 横屏模式下保持按钮形式 -->
        <div v-if="isLandscape" class="nav-dictionary-selector">
          <van-button
            v-for="dict in dictionaryOptions"
            :key="dict.value"
            :type="dictionaryPageSource === dict.value ? 'primary' : 'default'"
            size="small"
            @click="switchDictionary(dict.value)"
          >
            {{ dict.label }}
          </van-button>
        </div>
        <!-- 竖屏模式下使用下拉选择器 -->
        <div v-else class="nav-dictionary-selector">
          <van-button size="small" @click="showDictionaryPicker = true">
            {{ getCurrentDictionaryLabel() }}
            <van-icon name="arrow-down" style="margin-left: 4px;" />
          </van-button>
        </div>
      </template>
    </van-nav-bar>

    <!-- 词典选择弹出层 -->
    <van-popup
      v-model:show="showDictionaryPicker"
      position="top"
      round
      class="dict-picker-popup"
    >
      <div class="dict-picker-content">
        <div class="dict-picker-title">选择词典来源</div>
        <van-cell-group inset>
          <van-cell
            v-for="dict in dictionaryOptions"
            :key="dict.value"
            :title="dict.label"
            clickable
            @click="selectDictionary(dict.value)"
          >
            <template #right-icon>
              <van-icon
                v-if="dictionaryPageSource === dict.value"
                name="success"
                color="#1989fa"
              />
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </van-popup>

    <!-- 搜索框 -->
    <div class="search-container">
      <van-search
        v-model="searchWord"
        placeholder="输入单词或词组查询"
        show-action
        :clearable="true"
        @search="handleSearch"
        @clear="clearSearch"
      >
        <template #action>
          <van-button type="primary" size="small" @click="handleSearch" :loading="searching">
            查询
          </van-button>
        </template>
      </van-search>
    </div>

    <!-- 主内容区域 -->
    <div class="main-content" :class="{ 'landscape': isLandscape }">
      <!-- 查询结果区域 -->
      <div class="result-area">
        <!-- 空状态 -->
        <div v-if="!searchWord && !dictData && !dictError" class="empty-state">
          <i class="fas fa-book-open" style="font-size: 48px; color: #ccc;"></i>
          <p>输入单词或词组开始查询</p>
        </div>

        <!-- 查询结果 -->
        <div v-else-if="dictData" class="dict-result-container" @click="handleDictResultClick">
          <!-- ECDICT 格式显示 -->
          <template v-if="dictData.source === 'ecdict'">
            <div class="dict-header">
              <h3 class="dict-word">{{ dictData.word }}</h3>
              <span class="dict-source-tag">{{ getSourceLabel(dictData.source) }}</span>
              <span v-if="dictData.phonetic" class="dict-phonetic">{{ dictData.phonetic }}</span>
              <WordPronunciation :word="dictData.word" accent="auto" />
              <van-button
                class="vocab-btn"
                size="mini"
                type="primary"
                :loading="addingToVocabulary"
                @click="addToVocabulary"
              >
                <i class="fas fa-plus" style="margin-right: 4px;"></i>生词本
              </van-button>
              <div v-if="dictData.tag" class="dict-tags">
                <span v-for="(tag, idx) in formatTags(dictData.tag)" :key="idx" class="dict-tag">{{ tag }}</span>
              </div>
            </div>
            <!-- 中文翻译 -->
            <div v-if="dictData.translation" class="dict-translation">
              <div class="dict-section-title">中文释义</div>
              <div class="dict-translation-content">{{ dictData.translation }}</div>
            </div>
            <!-- 分隔线 -->
            <div v-if="dictData.translation && dictData.definition" class="dict-divider"></div>
            <!-- 英文释义 -->
            <div v-if="dictData.definition" class="dict-definition">
              <div class="dict-section-title">英文释义</div>
              <div class="dict-definition-content">{{ dictData.definition }}</div>
            </div>
            <!-- 时态变换 -->
            <div v-if="dictData.exchange" class="dict-exchange">
              <div class="dict-section-title">词形变换</div>
              <div class="dict-exchange-content">{{ formatExchange(dictData.exchange) }}</div>
            </div>
            <!-- 相关词组 -->
            <div v-if="dictData.related_phrases && dictData.related_phrases.length > 0" class="dict-related-phrases">
              <div class="dict-section-title">相关词组</div>
              <div class="dict-phrases-list">
                <div v-for="(item, idx) in dictData.related_phrases" :key="idx" 
                  class="dict-phrase-item"
                  @click="handlePhraseClick(item.phrase, item.translation)">
                  <span class="dict-phrase">{{ item.phrase }}</span>
                  <span class="dict-phrase-translation">{{ item.translation }}</span>
                </div>
              </div>
            </div>
          </template>
          <!-- API 格式显示 -->
          <template v-else>
            <div class="dict-header">
              <h3 class="dict-word">{{ dictData.word }}</h3>
              <span class="dict-source-tag">{{ getSourceLabel(dictData.source) }}</span>
              <span v-if="dictData.phonetic" class="dict-phonetic">{{ dictData.phonetic }}</span>
              <WordPronunciation :word="dictData.word" accent="auto" />
              <van-button
                class="vocab-btn"
                size="mini"
                type="primary"
                :loading="addingToVocabulary"
                @click="addToVocabulary"
              >
                <i class="fas fa-plus" style="margin-right: 4px;"></i>生词本
              </van-button>
            </div>
            <!-- 词源 -->
            <div v-if="dictData.origin" class="dict-origin">
              <div class="dict-section-title">词源</div>
              <div class="dict-origin-content">{{ dictData.origin }}</div>
            </div>
            <!-- 释义列表 -->
            <div class="dict-meanings">
              <template v-for="(meaning, idx) in dictData.meanings" :key="idx">
                <div class="dict-pos-title">{{ idx + 1 }}. {{ meaning.partOfSpeech }}</div>
                <div class="dict-definitions">
                  <div v-for="(def, dIdx) in meaning.definitions" :key="dIdx" class="dict-def-item">
                    <div class="dict-definition-text">
                      <span class="dict-label">释义：</span>
                      {{ def.definition }}
                    </div>
                    <div v-if="def.example" class="dict-example-text">
                      <span class="dict-label">例句：</span>
                      "{{ def.example }}"
                    </div>
                    <div v-if="def.synonyms?.length" class="dict-synonyms-text">
                      <span class="dict-label">同义词：</span>
                      {{ def.synonyms.join('；') }}
                    </div>
                    <div v-if="def.antonyms?.length" class="dict-antonyms-text">
                      <span class="dict-label">反义词：</span>
                      {{ def.antonyms.join('；') }}
                    </div>
                  </div>
                </div>
                <!-- 韦氏词典Thesaurus同义词/相关词 -->
                <div v-if="meaning.synonyms?.length" class="dict-mw-synonyms">
                  <span class="dict-label">同义词：</span>
                  <span class="dict-mw-words">{{ meaning.synonyms.join('；') }}</span>
                </div>
                <div v-if="meaning.related_words?.length" class="dict-mw-related">
                  <span class="dict-label">相关词：</span>
                  <span class="dict-mw-words">{{ meaning.related_words.join('；') }}</span>
                </div>
              </template>
            </div>
            <!-- 韦氏词典全局Thesaurus同义词 -->
            <div v-if="dictData.thesaurus_synonyms?.length" class="dict-thesaurus-section">
              <div class="dict-section-title">Thesaurus 同义词</div>
              <div class="dict-thesaurus-words">
                <span
                  v-for="(syn, sIdx) in dictData.thesaurus_synonyms"
                  :key="sIdx"
                  class="dict-thesaurus-word"
                  @click="lookupSecondWord(syn)"
                >{{ syn }}</span>
              </div>
            </div>
            <!-- 韦氏词典全局Thesaurus反义词 -->
            <div v-if="dictData.thesaurus_antonyms?.length" class="dict-thesaurus-section">
              <div class="dict-section-title">Thesaurus 反义词</div>
              <div class="dict-thesaurus-words dict-antonyms-words">
                <span
                  v-for="(ant, aIdx) in dictData.thesaurus_antonyms"
                  :key="aIdx"
                  class="dict-thesaurus-word"
                  @click="lookupSecondWord(ant)"
                >{{ ant }}</span>
              </div>
            </div>
            <!-- 韦氏词典习语 -->
            <div v-if="dictData.idioms?.length" class="dict-idioms-section">
              <div class="dict-section-title">习语</div>
              <div class="dict-idioms-list">
                <div v-for="(idiom, iIdx) in dictData.idioms" :key="iIdx" class="dict-idiom-item">
                  <span class="dict-idiom-phrase" @click="lookupSecondWord(idiom.phrase)">{{ idiom.phrase }}</span>
                  <span class="dict-idiom-def">{{ idiom.definition }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="dictError" class="error-state">
          <i class="fas fa-triangle-exclamation" style="font-size: 32px; color: #ee0a24;"></i>
          <p>{{ dictError }}</p>
        </div>

        <!-- 加载状态 -->
        <div v-else-if="searching" class="loading-state">
          <van-loading type="spinner" size="24px" />
          <span>查询中...</span>
        </div>
      </div>

      <!-- 横屏时显示查询历史 -->
      <div v-if="isLandscape" class="history-area">
        <div class="history-header">
          <span class="history-title">查询历史</span>
          <span v-if="historyList.length > 0" class="history-clear" @click="confirmClearHistory">清空</span>
        </div>
        <div class="history-list">
          <div v-if="historyLoading" class="history-loading">
            <van-loading type="spinner" size="20px" />
          </div>
          <div v-else-if="historyList.length === 0" class="history-empty">
            暂无查询记录
          </div>
          <div
            v-else
            v-for="item in historyList"
            :key="item.id"
            class="history-item"
            @click="handleHistoryClick(item.word)"
          >
            <span class="history-word">{{ item.word }}</span>
            <span class="history-time">{{ formatTime(item.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 第二个单词翻译弹窗（在词典结果区域点击单词时显示） -->
    <van-popup
      v-model:show="showSecondDictPopup"
      position="bottom"
      round
      class="dict-second-popup"
    >
      <div class="dict-popup-content">
        <div v-if="secondDictLoading" class="dict-loading">
          <van-loading type="spinner" size="24px" />
          <span>查询中...</span>
        </div>
        <div v-else-if="secondDictError" class="dict-error">
          <i class="fas fa-triangle-exclamation" style="font-size: 32px; color: #ee0a24;"></i>
          <p>{{ secondDictError }}</p>
        </div>
        <div v-else-if="secondDictData" class="dict-result">
          <!-- ECDICT 格式显示 -->
          <template v-if="secondDictData.source === 'ecdict'">
            <div class="dict-header">
              <h3 class="dict-word">{{ secondDictData.word }}</h3>
              <span class="dict-source-tag">{{ getSourceLabel(secondDictData.source) }}</span>
              <span v-if="secondDictData.phonetic" class="dict-phonetic">{{ secondDictData.phonetic }}</span>
              <WordPronunciation :word="secondDictData.word" accent="auto" />
              <van-button
                class="vocab-btn"
                size="mini"
                type="primary"
                :loading="addingToVocabulary"
                @click="addSecondWordToVocabulary"
              >
                <i class="fas fa-plus" style="margin-right: 4px;"></i>生词本
              </van-button>
              <div v-if="secondDictData.tag" class="dict-tags">
                <span v-for="(tag, idx) in formatTags(secondDictData.tag)" :key="idx" class="dict-tag">{{ tag }}</span>
              </div>
            </div>
            <!-- 中文翻译 -->
            <div v-if="secondDictData.translation" class="dict-translation">
              <div class="dict-section-title">中文释义</div>
              <div class="dict-translation-content">{{ secondDictData.translation }}</div>
            </div>
            <!-- 分隔线 -->
            <div v-if="secondDictData.translation && secondDictData.definition" class="dict-divider"></div>
            <!-- 英文释义 -->
            <div v-if="secondDictData.definition" class="dict-definition">
              <div class="dict-section-title">英文释义</div>
              <div class="dict-definition-content">{{ secondDictData.definition }}</div>
            </div>
            <!-- 时态变换 -->
            <div v-if="secondDictData.exchange" class="dict-exchange">
              <div class="dict-section-title">词形变换</div>
              <div class="dict-exchange-content">{{ formatExchange(secondDictData.exchange) }}</div>
            </div>
            <!-- 相关词组 -->
            <div v-if="secondDictData.related_phrases && secondDictData.related_phrases.length > 0" class="dict-related-phrases">
              <div class="dict-section-title">相关词组</div>
              <div class="dict-phrases-list">
                <div v-for="(item, idx) in secondDictData.related_phrases" :key="idx" 
                  class="dict-phrase-item"
                  @click="handlePhraseClick(item.phrase, item.translation)">
                  <span class="dict-phrase">{{ item.phrase }}</span>
                  <span class="dict-phrase-translation">{{ item.translation }}</span>
                </div>
              </div>
            </div>
          </template>
          <!-- API 格式显示 -->
          <template v-else>
            <div class="dict-header">
              <h3 class="dict-word">{{ secondDictData.word }}</h3>
              <span class="dict-source-tag">{{ getSourceLabel(secondDictData.source) }}</span>
              <span v-if="secondDictData.phonetic" class="dict-phonetic">{{ secondDictData.phonetic }}</span>
              <WordPronunciation :word="secondDictData.word" accent="auto" />
              <van-button
                class="vocab-btn"
                size="mini"
                type="primary"
                :loading="addingToVocabulary"
                @click="addSecondWordToVocabulary"
              >
                <i class="fas fa-plus" style="margin-right: 4px;"></i>生词本
              </van-button>
            </div>
            <!-- 词源 -->
            <div v-if="secondDictData.origin" class="dict-origin">
              <div class="dict-section-title">词源</div>
              <div class="dict-origin-content">{{ secondDictData.origin }}</div>
            </div>
            <!-- 释义列表 -->
            <div class="dict-meanings">
              <template v-for="(meaning, idx) in secondDictData.meanings" :key="idx">
                <div class="dict-pos-title">{{ idx + 1 }}. {{ meaning.partOfSpeech }}</div>
                <div class="dict-definitions">
                  <div v-for="(def, dIdx) in meaning.definitions" :key="dIdx" class="dict-def-item">
                    <div class="dict-definition-text">
                      <span class="dict-label">释义：</span>
                      {{ def.definition }}
                    </div>
                    <div v-if="def.example" class="dict-example-text">
                      <span class="dict-label">例句：</span>
                      "{{ def.example }}"
                    </div>
                    <div v-if="def.synonyms?.length" class="dict-synonyms-text">
                      <span class="dict-label">同义词：</span>
                      {{ def.synonyms.join('；') }}
                    </div>
                    <div v-if="def.antonyms?.length" class="dict-antonyms-text">
                      <span class="dict-label">反义词：</span>
                      {{ def.antonyms.join('；') }}
                    </div>
                  </div>
                </div>
                <!-- 韦氏词典Thesaurus同义词/相关词 -->
                <div v-if="meaning.synonyms?.length" class="dict-mw-synonyms">
                  <span class="dict-label">同义词：</span>
                  <span class="dict-mw-words">{{ meaning.synonyms.join('；') }}</span>
                </div>
                <div v-if="meaning.related_words?.length" class="dict-mw-related">
                  <span class="dict-label">相关词：</span>
                  <span class="dict-mw-words">{{ meaning.related_words.join('；') }}</span>
                </div>
              </template>
            </div>
            <!-- 韦氏词典全局Thesaurus同义词 -->
            <div v-if="secondDictData.thesaurus_synonyms?.length" class="dict-thesaurus-section">
              <div class="dict-section-title">Thesaurus 同义词</div>
              <div class="dict-thesaurus-words">
                <span
                  v-for="(syn, sIdx) in secondDictData.thesaurus_synonyms"
                  :key="sIdx"
                  class="dict-thesaurus-word"
                  @click="lookupSecondWord(syn)"
                >{{ syn }}</span>
              </div>
            </div>
            <!-- 韦氏词典全局Thesaurus反义词 -->
            <div v-if="secondDictData.thesaurus_antonyms?.length" class="dict-thesaurus-section">
              <div class="dict-section-title">Thesaurus 反义词</div>
              <div class="dict-thesaurus-words dict-antonyms-words">
                <span
                  v-for="(ant, aIdx) in secondDictData.thesaurus_antonyms"
                  :key="aIdx"
                  class="dict-thesaurus-word"
                  @click="lookupSecondWord(ant)"
                >{{ ant }}</span>
              </div>
            </div>
            <!-- 韦氏词典习语 -->
            <div v-if="secondDictData.idioms?.length" class="dict-idioms-section">
              <div class="dict-section-title">习语</div>
              <div class="dict-idioms-list">
                <div v-for="(idiom, iIdx) in secondDictData.idioms" :key="iIdx" class="dict-idiom-item">
                  <span class="dict-idiom-phrase" @click="lookupSecondWord(idiom.phrase)">{{ idiom.phrase }}</span>
                  <span class="dict-idiom-def">{{ idiom.definition }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { api } from '@/store/auth'
import WordPronunciation from '@/components/WordPronunciation.vue'
import { useDictionarySettings } from './Home/composables/useDictionarySettings'

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
    // 韦氏词典Thesaurus特有
    synonyms?: string[]
    related_words?: string[]
  }>
  source?: string
  tag?: string
  translation?: string
  definition?: string
  exchange?: string
  origin?: string
  related_phrases?: Array<{ phrase: string; translation: string }>
  // 韦氏词典Thesaurus特有
  thesaurus_synonyms?: string[]
  thesaurus_antonyms?: string[]
  idioms?: Array<{ phrase: string; definition: string }>
}

interface HistoryItem {
  id: number
  word: string
  created_at: string
}

// 词典源显示名称映射
const dictionarySourceLabels: Record<string, string> = {
  'ecdict': '本地词典',
  'local': '本地词典',
  'api': 'FreeDictionary',
  'merriam-webster': '韦氏词典',
  'merriam-webster-learners': '韦氏词典'
}

// 获取词典源显示名称
const getSourceLabel = (source?: string): string => {
  if (!source) return '在线词典'
  return dictionarySourceLabels[source] || '在线词典'
}

const router = useRouter()

// 使用全局词典设置状态
// 注意：这里使用 dictionaryPageSource（词典页面专用），与设置页面的 dictionarySource 独立
const {
  dictionaryPageSource,
  saveDictionaryPageSettings,
  loadDictionarySettings
} = useDictionarySettings()

// 下拉选择器状态
const showDictionaryPicker = ref(false)

// 获取当前词典显示名称
const getCurrentDictionaryLabel = (): string => {
  const option = dictionaryOptions.find(opt => opt.value === dictionaryPageSource.value)
  return option?.label || '选择词典'
}

// 选择词典（从弹出层选择）
const selectDictionary = async (source: string) => {
  showDictionaryPicker.value = false
  await switchDictionary(source)
}

// 搜索相关状态
const searchWord = ref('')
const searching = ref(false)
const dictData = ref<DictionaryData | null>(null)
const dictError = ref('')

// 生词本相关状态
const addingToVocabulary = ref(false)

// 历史记录相关状态
const historyList = ref<HistoryItem[]>([])
const historyLoading = ref(false)

// 横屏状态
const isLandscape = ref(false)

// 词典选择 - 直接使用全局状态
const dictionaryOptions = [
  { value: 'local', label: '本地ECDICT' },
  { value: 'api', label: '在线FreeDictionary' },
  { value: 'merriam-webster', label: '韦氏词典' },
]

// 第二个弹窗相关状态（点击弹窗内单词时显示）
const showSecondDictPopup = ref(false)
const secondDictLoading = ref(false)
const secondDictError = ref('')
const secondDictData = ref<DictionaryData | null>(null)

// 返回上一页
const goBack = () => {
  router.back()
}

// 检测屏幕方向
const checkOrientation = () => {
  isLandscape.value = window.innerWidth > window.innerHeight
}

// 切换词典
const switchDictionary = async (source: string) => {
  if (dictionaryPageSource.value === source) return
  
  const currentWord = searchWord.value.trim()
  
  // 更新词典页面专用状态
  dictionaryPageSource.value = source
  
  // 保存到数据库（使用独立字段 dictionary_page_source）
  await saveDictionaryPageSettings()
  
  // 如果当前有查询单词，用新词典重新查询
  if (currentWord && dictData.value) {
    await handleSearch()
  }
}

// 处理搜索
const handleSearch = async () => {
  const word = searchWord.value.trim()
  if (!word) {
    showToast('请输入单词或词组')
    return
  }

  searching.value = true
  dictError.value = ''
  dictData.value = null

  try {
    // 查询单词，使用词典页面专用的词典来源
    const res = await api.get<DictionaryData>(`/dictionary/lookup?word=${encodeURIComponent(word)}&source=${dictionaryPageSource.value}`)
    dictData.value = res.data

    // 添加到历史记录
    await api.post(`/dictionary/history?word=${encodeURIComponent(word)}`)

    // 刷新历史列表
    loadHistory()
  } catch (error: any) {
    dictError.value = error.response?.data?.detail || '查询失败'
  } finally {
    searching.value = false
  }
}

// 清空搜索
const clearSearch = () => {
  searchWord.value = ''
  dictData.value = null
  dictError.value = ''
}

// 添加到生词本
const addToVocabulary = async () => {
  if (!dictData.value) return

  addingToVocabulary.value = true
  try {
    let translation = ''
    if (dictData.value.translation) {
      translation = dictData.value.translation
    } else if (dictData.value.meanings && dictData.value.meanings.length > 0) {
      translation = dictData.value.meanings
        .map(m => m.definitions.map(d => d.definition).join('; '))
        .join('; ')
    }

    await api.post('/vocabulary/', {
      word: dictData.value.word,
      phonetic: dictData.value.phonetic || '',
      translation: translation,
      sentence: '',
      book_name: '词典查询'
    })
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

// 加载历史记录
const loadHistory = async () => {
  historyLoading.value = true
  try {
    const res = await api.get<{items: HistoryItem[], total: number}>('/dictionary/history?limit=100')
    historyList.value = res.data.items || []
  } catch (error) {
    console.error('加载历史记录失败:', error)
  } finally {
    historyLoading.value = false
  }
}

// 清空历史记录
const clearHistory = async () => {
  try {
    await api.delete('/dictionary/history')
    historyList.value = []
    showToast('历史记录已清空')
  } catch (error) {
    showToast('清空失败')
  }
}

// 确认清空历史
const confirmClearHistory = async () => {
  try {
    await showConfirmDialog({
      title: '确认清空',
      message: '确定要清空所有查询历史吗？'
    })
    await clearHistory()
  } catch {
    // 用户取消
  }
}

// 点击历史记录（左侧载入翻译）
const handleHistoryClick = (word: string) => {
  // 如果已经是当前显示的单词，不重复查询
  if (searchWord.value === word && dictData.value?.word === word) {
    return
  }
  searchWord.value = word
  handleSearch()
}

// 点击词组
const handlePhraseClick = (phrase: string, _translation: string) => {
  // 使用弹窗显示词组查询结果，而不是直接替换当前页面
  lookupSecondWord(phrase)
}

// 查询第二个单词（在弹窗内点击单词）
const lookupSecondWord = async (word: string) => {
  if (!word) return

  showSecondDictPopup.value = true
  secondDictLoading.value = true
  secondDictError.value = ''
  secondDictData.value = null

  try {
    // 查询单词，使用词典页面专用的词典来源
    const res = await api.get<DictionaryData>(`/dictionary/lookup?word=${encodeURIComponent(word)}&source=${dictionaryPageSource.value}`)
    secondDictData.value = res.data
  } catch (error: any) {
    secondDictError.value = error.response?.data?.detail || '查询失败'
  } finally {
    secondDictLoading.value = false
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

// 处理词典结果区域点击（查找点击的单词）
const handleDictResultClick = (e: MouseEvent) => {
  // 如果第二个弹窗已经打开，不再处理
  if (showSecondDictPopup.value) return

  const target = e.target as HTMLElement

  // 检查点击的是否是英文文本
  const word = getWordFromClick(e, target)
  if (word && /^[a-zA-Z]+$/.test(word)) {
    lookupSecondWord(word)
  }
}

// 添加第二个弹窗中的单词到生词本
const addSecondWordToVocabulary = async () => {
  if (!secondDictData.value) return

  addingToVocabulary.value = true
  try {
    let translation = ''
    if (secondDictData.value.translation) {
      translation = secondDictData.value.translation
    } else if (secondDictData.value.meanings && secondDictData.value.meanings.length > 0) {
      translation = secondDictData.value.meanings
        .map(m => m.definitions.map(d => d.definition).join('; '))
        .join('; ')
    }

    await api.post('/vocabulary/', {
      word: secondDictData.value.word,
      phonetic: secondDictData.value.phonetic || '',
      translation: translation,
      sentence: '',
      book_name: '词典查询'
    })
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

// 格式化时间
const formatTime = (dateStr: string) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return `${date.getMonth() + 1}/${date.getDate()}`
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

onMounted(() => {
  checkOrientation()
  window.addEventListener('resize', checkOrientation)
  loadHistory()
  loadDictionarySettings()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkOrientation)
})
</script>

<style scoped>
.dictionary-page {
  min-height: 100vh;
  background: #f7f8fa;
}

.search-container {
  padding: 12px;
  background: #fff;
}

.dictionary-selector {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  padding: 0 4px;
}

.dictionary-selector .van-button {
  flex: 1;
}

.nav-dictionary-selector {
  display: flex;
  gap: 8px;
}

.nav-dictionary-selector .van-button {
  font-size: 12px;
  padding: 0 12px;
}

.main-content {
  display: flex;
  flex-direction: column;
  padding: 12px;
  height: calc(100vh - 140px);
  overflow: hidden;
}

.main-content.landscape {
  flex-direction: row;
  gap: 12px;
}

.result-area {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}

.history-area {
  width: 200px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  max-height: calc(100vh - 150px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.history-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.history-clear {
  font-size: 12px;
  color: #1989fa;
  cursor: pointer;
}

.history-list {
  flex: 1;
  overflow-y: auto;
}

.history-loading {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.history-empty {
  text-align: center;
  color: #999;
  font-size: 12px;
  padding: 20px 0;
}

.history-item {
  display: flex;
  flex-direction: column;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: #f7f8fa;
}

.history-word {
  font-size: 14px;
  color: #333;
}

.history-time {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #999;
}

.empty-state p {
  margin-top: 12px;
  font-size: 14px;
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #999;
}

.error-state p {
  margin-top: 12px;
  font-size: 14px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #666;
  gap: 10px;
}

/* 词典结果样式 */
.dict-result-container {
  background: #fff;
  border-radius: 8px;
  padding: 0;
  max-height: calc(100vh - 180px);
  overflow-y: auto;
}

.dict-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 16px 12px 16px;
  border-bottom: 1px solid #eee;
  flex-wrap: wrap;
  background: #fff;
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

.dict-origin {
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}

.dict-origin-content {
  font-size: 13px;
  color: #666;
  line-height: 1.6;
}

.dict-meanings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dict-pos-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  padding: 8px 0 4px;
}

.dict-definitions {
  padding: 0 0 8px;
}

.dict-def-item {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #f0f0f0;
}

.dict-def-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.dict-label {
  color: #999;
  font-size: 12px;
}

.dict-definition-text {
  font-size: 14px;
  color: #333;
  line-height: 1.6;
  margin-bottom: 4px;
}

.dict-example-text {
  font-size: 13px;
  color: #666;
  font-style: italic;
  margin: 4px 0;
  padding-left: 8px;
  border-left: 2px solid #e3f2fd;
}

.dict-synonyms-text,
.dict-antonyms-text {
  font-size: 12px;
  color: #1989fa;
  margin-top: 4px;
}

/* 韦氏词典特有样式 */
.dict-mw-synonyms,
.dict-mw-related {
  font-size: 12px;
  color: #1989fa;
  margin-top: 4px;
  padding-left: 8px;
}

.dict-mw-words {
  color: #666;
}

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

/* 第二个弹窗样式 */
.dict-popup-content {
  padding: 0 16px 16px 16px;
  max-height: 50vh;
  overflow-y: auto;
}

.dict-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #666;
  gap: 10px;
}

.dict-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #999;
}

.dict-error p {
  margin-top: 12px;
  font-size: 14px;
}

/* 词典选择弹窗样式 */
.dict-picker-popup {
  overflow: visible !important;
}

.dict-picker-popup :deep(.van-popup__wrapper) {
  overflow: visible !important;
}

/* 第二个弹窗样式 */
.dict-second-popup :deep(.van-popup__wrapper) {
  overflow: hidden auto !important;
  max-height: 50vh !important;
}

/* 确保弹窗内标题也有白色背景 */
.dict-second-popup .dict-header {
  background: #fff;
}

.dict-picker-content {
  padding: 16px 0;
}

.dict-picker-title {
  font-size: 14px;
  font-weight: 500;
  color: #969799;
  padding: 0 16px 12px;
}
</style>
