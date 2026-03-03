<template>
  <div class="reader">
    <van-nav-bar
      :title="pageTitle"
      left-text="返回"
      left-arrow
      fixed
      placeholder
      @click-left="goBack"
    >
      <template #right>
        <div class="nav-icon-btn" :class="{ 'playing': isPlayingAll }" @click="togglePlayAll">
          <van-icon :name="isPlayingAll ? 'pause-circle-o' : 'play-circle-o'" />
        </div>
        <div class="nav-icon-btn" @click="openDictionaryDialog">
          <van-icon name="search" />
        </div>
        <div class="nav-icon-btn" @click="openEditDialog">
          <van-icon name="description" />
        </div>
      </template>
    </van-nav-bar>

    <div v-if="loading" class="loading-box">
      <van-loading type="spinner" vertical>加载书籍中...</van-loading>
    </div>

    <!-- 阅读模式：分页显示内容 -->
    <div v-else class="reader-content">
      <!-- 页面内容区域 -->
      <div
        class="page-content"
        :class="{ 'landscape': isLandscape }"
        v-html="currentPageContent"
        @click="handleContentClick"
        @touchstart="handleTouchStart"
        @touchend="handleTouchEnd"
        @touchmove="handleTouchMove"
        @contextmenu="handleContextMenu"
      ></div>

      <!-- 分页控制栏 -->
      <div v-if="totalPagesCount > 1" class="pagination-bar">
        <div class="page-btn" :class="{ 'disabled': currentPage <= 0 }" @click="goToPrevPage">
          <van-icon name="arrow-left" />
          <span>上一页</span>
        </div>
        <div class="page-indicator" @click="showPagePicker = true">
          <span class="current-page">{{ currentPage + 1 }}</span>
          <span class="page-separator">/</span>
          <span class="total-pages">{{ totalPagesCount }}</span>
        </div>
        <div class="page-btn" :class="{ 'disabled': currentPage >= totalPagesCount - 1 }" @click="goToNextPage">
          <span>下一页</span>
          <van-icon name="arrow" />
        </div>
      </div>
    </div>

    <!-- 页码选择器 -->
    <van-popup
      v-model:show="showPagePicker"
      position="bottom"
      round
    >
      <div class="page-picker-content">
        <div class="page-picker-header">
          <span>跳转到页面</span>
          <van-icon name="cross" class="close-btn" @click="showPagePicker = false" />
        </div>
        <div class="page-picker-grid">
          <div
            v-for="pageNum in totalPagesCount"
            :key="pageNum"
            class="page-number-item"
            :class="{ 'active': currentPage === pageNum - 1 }"
            @click="jumpToPage(pageNum - 1)"
          >
            {{ pageNum }}
          </div>
        </div>
      </div>
    </van-popup>

    <!-- Audio element for TTS -->
    <audio
      ref="audioPlayer"
      style="display: none"
      @ended="handleAudioEnded"
      @error="handleAudioError"
    ></audio>

    <!-- 编辑对话框 -->
    <BookEditDialog
      v-model="showEditDialog"
      :book-id="bookId"
      :title="bookTitle"
      :initial-content="rawEditContent"
      @saved="loadBookContent"
    />

    <!-- 词典输入对话框（非模态） -->
    <van-popup
      v-model:show="showDictionaryInputDialog"
      position="top"
      round
      :overlay="false"
      :style="{ top: '60px', right: '10px', left: 'auto', width: '280px', position: 'absolute' }"
    >
      <div class="dictionary-input-popup">
        <div class="dictionary-input-header">
          <span class="dictionary-input-title">查词典</span>
          <van-icon name="cross" class="dictionary-input-close" @click="showDictionaryInputDialog = false" />
        </div>
        <div class="dictionary-input-content">
          <van-field
            v-model="dictionaryInputWord"
            placeholder="请输入英文单词"
            clearable
            autofocus
            @keyup.enter="handleDictionaryInputConfirm"
          >
            <template #button>
              <van-button size="small" type="primary" @click="handleDictionaryInputConfirm">查询</van-button>
            </template>
          </van-field>
        </div>
      </div>
    </van-popup>

    <!-- 单词翻译弹窗 -->
    <van-popup
      v-model:show="showDictPopup"
      position="bottom"
      round
      :style="{ maxHeight: '60%' }"
      @click-overlay="handleDictPopupOverlayClick"
    >
      <div class="dict-popup-content" @click="handleDictPopupContentClick">
        <div v-if="dictLoading" class="dict-loading">
          <van-loading type="spinner" size="24px" />
          <span>查询中...</span>
        </div>
        <div v-else-if="dictError" class="dict-error">
          <van-icon name="warning-o" size="32" color="#ee0a24" />
          <p>{{ dictError }}</p>
        </div>
        <div v-else-if="dictData" class="dict-result">
          <!-- ECDICT 格式显示 -->
          <template v-if="dictData.source === 'ecdict'">
            <div class="dict-header">
              <h3 class="dict-word">{{ dictData.word }}</h3>
             
              <span v-if="dictData.phonetic" class="dict-phonetic">{{ dictData.phonetic }}</span>
               <van-button
                class="vocab-btn"
                size="mini"
                type="primary"
                icon="plus"
                :loading="addingToVocabulary"
                @click="addToVocabulary"
              >
                生词本
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
          </template>
          <!-- API 格式显示（保持原有） -->
          <template v-else>
            <div class="dict-header">
              <h3 class="dict-word">{{ dictData.word }}</h3>
              <van-button
                class="vocab-btn"
                size="mini"
                type="primary"
                icon="plus"
                :loading="addingToVocabulary"
                @click="addToVocabulary"
              >
                生词本
              </van-button>
              <span v-if="dictData.phonetic" class="dict-phonetic">{{ dictData.phonetic }}</span>
              <van-icon
                v-if="dictData.phonetics?.[0]?.audio"
                name="volume-o"
                class="dict-audio-btn"
                @click="playPhoneticAudio(dictData.phonetics[0].audio)"
              />
            </div>
            <div class="dict-meanings">
              <div
                v-for="(meaning, idx) in dictData.meanings.slice(0, 3)"
                :key="idx"
                class="dict-meaning-item"
              >
                <div class="dict-pos">{{ meaning.partOfSpeech }}</div>
                <ol class="dict-def-list">
                  <li
                    v-for="(def, dIdx) in meaning.definitions.slice(0, 2)"
                    :key="dIdx"
                    class="dict-def-item"
                  >
                    <p class="dict-def-text">{{ def.definition }}</p>
                    <p v-if="def.example" class="dict-def-example">"{{ def.example }}"</p>
                  </li>
                </ol>
              </div>
            </div>
          </template>
        </div>
      </div>
    </van-popup>

    <!-- 第二个单词翻译弹窗（在弹窗内点击单词时显示） -->
    <van-popup
      v-model:show="showSecondDictPopup"
      position="bottom"
      round
      :style="{ maxHeight: '50%' }"
    >
      <div class="dict-popup-content">
        <div v-if="secondDictLoading" class="dict-loading">
          <van-loading type="spinner" size="24px" />
          <span>查询中...</span>
        </div>
        <div v-else-if="secondDictError" class="dict-error">
          <van-icon name="warning-o" size="32" color="#ee0a24" />
          <p>{{ secondDictError }}</p>
        </div>
        <div v-else-if="secondDictData" class="dict-result">
          <!-- ECDICT 格式显示 -->
          <template v-if="secondDictData.source === 'ecdict'">
            <div class="dict-header">
              <h3 class="dict-word">{{ secondDictData.word }}</h3>
              <span v-if="secondDictData.phonetic" class="dict-phonetic">{{ secondDictData.phonetic }}</span>
              <van-button
                class="vocab-btn"
                size="mini"
                type="primary"
                icon="plus"
                :loading="addingToVocabulary"
                @click="addSecondWordToVocabulary"
              >
                生词本
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
          </template>
          <!-- API 格式显示 -->
          <template v-else>
            <div class="dict-header">
              <h3 class="dict-word">{{ secondDictData.word }}</h3>
              <van-button
                class="vocab-btn"
                size="mini"
                type="primary"
                icon="plus"
                :loading="addingToVocabulary"
                @click="addSecondWordToVocabulary"
              >
                生词本
              </van-button>
              <span v-if="secondDictData.phonetic" class="dict-phonetic">{{ secondDictData.phonetic }}</span>
              <van-icon
                v-if="secondDictData.phonetics?.[0]?.audio"
                name="volume-o"
                class="dict-audio-btn"
                @click="playPhoneticAudio(secondDictData.phonetics[0].audio)"
              />
            </div>
            <div class="dict-meanings">
              <div
                v-for="(meaning, idx) in secondDictData.meanings.slice(0, 3)"
                :key="idx"
                class="dict-meaning-item"
              >
                <div class="dict-pos">{{ meaning.partOfSpeech }}</div>
                <ol class="dict-def-list">
                  <li
                    v-for="(def, dIdx) in meaning.definitions.slice(0, 2)"
                    :key="dIdx"
                    class="dict-def-item"
                  >
                    <p class="dict-def-text">{{ def.definition }}</p>
                    <p v-if="def.example" class="dict-def-example">"{{ def.example }}"</p>
                  </li>
                </ol>
              </div>
            </div>
          </template>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import md5 from 'blueimp-md5'
import { api } from '@/store/auth'
import BookEditDialog from '@/components/BookEditDialog.vue'

interface SentenceMapping {
  page: number
  index: number
  text: string
  audio_file: string
}

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
    }>
  }>
  source?: string
  tag?: string
  translation?: string
  definition?: string
  exchange?: string
}

const route = useRoute()
const router = useRouter()
const bookId = route.params.id as string
const bookTitle = ref('')
const bookPath = ref('')
const loading = ref(true)
const audioPlayer = ref<HTMLAudioElement | null>(null)
const currentSentence = ref<HTMLElement | null>(null)
const isPlayingAll = ref(false)

// 句子映射：key = "text_hash", value = { audio_file, text }
const sentencesMap = ref<Record<string, SentenceMapping>>({})

// 计算文本的 MD5 哈希（与后端一致）
const md5Hash = (text: string): string => {
  return md5(text)
}

// 编辑相关状态
const showEditDialog = ref(false)
const rawEditContent = ref('')

// 词典查询相关状态
const showDictPopup = ref(false)
const dictLoading = ref(false)
const dictError = ref('')
const dictData = ref<DictionaryData | null>(null)
let longPressTimer: number | null = null
let isLongPress = false
let currentTouchTarget: HTMLElement | null = null

// 词典输入对话框状态
const showDictionaryInputDialog = ref(false)
const dictionaryInputWord = ref('')

// 第二个词典弹窗状态（用于在弹窗内点击单词查询）
const showSecondDictPopup = ref(false)
const secondDictLoading = ref(false)
const secondDictError = ref('')
const secondDictData = ref<DictionaryData | null>(null)
const secondDictSentence = ref('')

// 生词本相关状态
const addingToVocabulary = ref(false)
const currentSentenceText = ref('')  // 保存当前查词所在的句子

// 分页相关状态
const currentPage = ref(0)
const showPagePicker = ref(false)
const touchStartX = ref(0)
const touchStartY = ref(0)
const isSwiping = ref(false)

// 渐进式预加载相关状态
const pages = ref<(string | null)[]>([])  // 页面缓存数组，null表示未加载
const pageLoadStatus = ref<Record<number, 'loading' | 'loaded' | 'error'>>({})
const totalPages = ref(0)
const isInitialLoading = ref(true)

// 预加载配置
const PRELOAD_AHEAD = 2  // 预加载后面2页
const PRELOAD_BEHIND = 1  // 预加载前面1页

// 总页数
const totalPagesCount = computed(() => totalPages.value)

// 当前页内容
const currentPageContent = computed(() => {
  const pageIndex = currentPage.value
  if (pageIndex < pages.value.length && pages.value[pageIndex]) {
    return pages.value[pageIndex]
  }
  // 如果页面未加载，返回加载占位
  return '<div class="page-loading"><div style="padding: 40px; text-align: center; color: #999;"><span>加载中...</span></div></div>'
})

// 页面标题（显示当前页码）
const pageTitle = computed(() => {
  if (totalPages.value <= 1) return bookTitle.value
  return `${bookTitle.value} (${currentPage.value + 1}/${totalPages.value})`
})

// 检查页面是否已加载
const isPageLoaded = (pageIndex: number) => {
  return !!pages.value[pageIndex]
}



const goBack = () => {
  stopPlayAll()
  router.back()
}

// 加载指定范围的页面
const loadPages = async (startPage: number, endPage: number) => {
  // 过滤掉已加载或正在加载的页面
  const pagesToLoad: number[] = []
  for (let i = startPage; i < endPage; i++) {
    if (i >= 0 && !isPageLoaded(i) && pageLoadStatus.value[i] !== 'loading') {
      pagesToLoad.push(i)
    }
  }

  if (pagesToLoad.length === 0) return

  // 标记为加载中
  pagesToLoad.forEach(p => pageLoadStatus.value[p] = 'loading')

  try {
    // 计算连续范围进行批量加载
    const minPage = Math.min(...pagesToLoad)
    const maxPage = Math.max(...pagesToLoad) + 1

    console.log('Loading pages:', minPage, 'to', maxPage)
    const res = await api.get(`/books/${bookId}/pages`, {
      params: { start_page: minPage, end_page: maxPage }
    })

    const data = res.data
    console.log('Loaded data:', data.title, 'total pages:', data.page_count)
    bookPath.value = data.book_path
    bookTitle.value = data.title

    // 修复图片路径并缓存页面
    const baseUrl = `/books/${data.book_path}`
    const newPages = [...pages.value]
    data.pages.forEach((page: string, idx: number) => {
      const pageIndex = data.start_page + idx
      newPages[pageIndex] = page.replace(/src="\.\/assets\//g, `src="${baseUrl}/assets/`)
      pageLoadStatus.value[pageIndex] = 'loaded'
    })
    pages.value = newPages

    // 更新总页数（首次加载时）
    if (totalPages.value === 0) {
      totalPages.value = data.page_count
    }

  } catch (error) {
    console.error('加载页面失败:', error)
    pagesToLoad.forEach(p => pageLoadStatus.value[p] = 'error')
  }
}

// 智能预加载策略
const preloadPages = () => {
  const current = currentPage.value

  // 计算需要预加载的范围
  const preloadStart = Math.max(0, current - PRELOAD_BEHIND)
  const preloadEnd = Math.min(totalPages.value, current + PRELOAD_AHEAD + 1)

  // 异步加载（不阻塞）
  setTimeout(() => {
    loadPages(preloadStart, preloadEnd)
  }, 100)
}

// 跳转到指定页面
const jumpToPage = async (pageIndex: number) => {
  if (pageIndex < 0 || pageIndex >= totalPages.value) return

  currentPage.value = pageIndex
  showPagePicker.value = false

  // 滚动到顶部
  const contentEl = document.querySelector('.page-content')
  if (contentEl) {
    contentEl.scrollTop = 0
  }

  // 如果目标页面未加载，立即加载
  if (!isPageLoaded(pageIndex)) {
    await loadPages(pageIndex, pageIndex + 1)
  }

  // 触发预加载
  preloadPages()
}

// 上一页
const goToPrevPage = () => {
  if (currentPage.value > 0) {
    jumpToPage(currentPage.value - 1)
  }
}

// 下一页
const goToNextPage = () => {
  if (currentPage.value < totalPages.value - 1) {
    jumpToPage(currentPage.value + 1)
  }
}

// 处理键盘事件（方向键翻页）
const handleKeyDown = (e: KeyboardEvent) => {
  // 左方向键：上一页
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    goToPrevPage()
    return
  }
  // 右方向键：下一页
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    goToNextPage()
    return
  }
  // PageUp：上一页
  if (e.key === 'PageUp') {
    e.preventDefault()
    goToPrevPage()
    return
  }
  // PageDown：下一页
  if (e.key === 'PageDown') {
    e.preventDefault()
    goToNextPage()
    return
  }
}

// 打开编辑对话框
const openEditDialog = async () => {
  // 加载原始MD内容
  try {
    const res = await api.get<{ content: string }>(`/books/${bookId}/content`)
    rawEditContent.value = res.data.content
  } catch (error) {
    showToast('加载内容失败')
    console.error(error)
    return
  }
  showEditDialog.value = true
}

// 打开词典输入对话框
const openDictionaryDialog = () => {
  dictionaryInputWord.value = ''
  showDictionaryInputDialog.value = true
}

// 处理词典输入确认
const handleDictionaryInputConfirm = () => {
  const word = dictionaryInputWord.value.trim()
  if (word) {
    showDictionaryInputDialog.value = false
    lookupWord(word)
  } else {
    showToast('请输入单词')
  }
}

// 编辑保存后重新加载书籍内容
const loadBookContent = async () => {
  await loadBook()
}


// 初始加载：只加载第1页和基本信息
const loadBook = async () => {
  isInitialLoading.value = true
  loading.value = true

  try {
    // 先加载第1页和基本信息
    await loadPages(0, 1)

    // 后台预加载第2、3页
    preloadPages()

    // 加载句子映射
    if (bookPath.value) {
      await loadSentencesMap(`/books/${bookPath.value}`)
    }

  } catch (error) {
    showToast('加载失败')
    console.error(error)
  } finally {
    isInitialLoading.value = false
    loading.value = false
  }
}

// 加载句子映射文件
const loadSentencesMap = async (baseUrl: string) => {
  try {
    // 添加时间戳防止缓存
    const timestamp = Date.now()
    const res = await fetch(`${baseUrl}/audio/sentences.json?t=${timestamp}`)
    if (res.ok) {
      const data: SentenceMapping[] = await res.json()
      // 构建映射: key = "text_hash"（与音频文件名一致）
      data.forEach((item) => {
        // 根据文本计算哈希值，生成对应的音频文件名
        const hash = md5Hash(item.text)
        // 自动填充 audio_file 字段
        item.audio_file = `${hash}.mp3`
        sentencesMap.value[hash] = item
      })
      console.log('Loaded sentences map:', Object.keys(sentencesMap.value).length, 'entries')
    }
  } catch (e) {
    console.log('没有预生成的句子映射')
  }
}

const playSentence = async (el: HTMLElement) => {
  const text = el.dataset.tts
  console.log('Play sentence text:', JSON.stringify(text), 'dataset:', el.dataset)

  // 高亮当前句子
  if (currentSentence.value) {
    currentSentence.value.classList.remove('active-sentence')
  }
  currentSentence.value = el
  el.classList.add('active-sentence')

  // 确保在视图中可见
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })

  // 尝试使用预生成音频（通过文本哈希查找）
  if (text && audioPlayer.value) {
    const hash = md5Hash(text)
    const mapping = sentencesMap.value[hash]
    console.log('Looking for audio by hash:', hash, mapping)
    if (mapping && mapping.audio_file) {
      // 先暂停当前播放，避免冲突
      audioPlayer.value.pause()
      // 添加时间戳防止音频缓存
      const timestamp = Date.now()
      audioPlayer.value.src = `/books/${bookPath.value}/audio/${mapping.audio_file}?t=${timestamp}`
      // 使用 Promise 处理播放，避免中断错误
      const playPromise = audioPlayer.value.play()
      if (playPromise !== undefined) {
        playPromise.catch((error) => {
          if (error.name !== 'AbortError') {
            console.error('音频播放失败:', error)
          }
        })
      }
      return
    }
  }

  // 没有预生成音频，提示用户
  showToast('缺少语音，请先生成再使用')
  if (isPlayingAll.value) stopPlayAll()
}

const handleContentClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (target.classList.contains('tts-sentence')) {
    // 点击句子时停止全文朗读，然后播放该句子
    stopPlayAll()
    playSentence(target)
  } else {
    // 点击书籍其他位置，停止朗读
    stopPlayAll()
  }
}

// 长按相关事件处理
const handleTouchStart = (e: TouchEvent) => {
  const target = e.target as HTMLElement

  // 保存触摸起始位置用于滑动检测
  const touch = e.touches[0]
  touchStartX.value = touch.clientX
  touchStartY.value = touch.clientY
  isSwiping.value = false

  // 只在tts-sentence上处理长按查词
  if (!target.classList.contains('tts-sentence')) return

  currentTouchTarget = target
  isLongPress = false
  longPressTimer = window.setTimeout(() => {
    isLongPress = true
    // 获取触摸位置处的单词
    const word = getWordAtPosition(target, touch.clientX, touch.clientY)
    if (word) {
      // 获取句子文本
      const sentence = target.textContent || ''
      lookupWord(word, sentence)
    }
  }, 500) // 500ms 长按触发
}

const handleTouchEnd = (e: TouchEvent) => {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }

  // 处理滑动翻页
  if (isSwiping.value) {
    const touch = e.changedTouches[0]
    const diffX = touchStartX.value - touch.clientX
    const diffY = touchStartY.value - touch.clientY

    // 水平滑动距离大于垂直滑动，且水平滑动超过50px才触发翻页
    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
      if (diffX > 0) {
        // 向左滑动，下一页
        goToNextPage()
      } else {
        // 向右滑动，上一页
        goToPrevPage()
      }
    }
    currentTouchTarget = null
    return
  }

  // 如果不是长按且不是滑动，则触发朗读
  if (!isLongPress && currentTouchTarget) {
    const target = e.target as HTMLElement
    if (target.classList.contains('tts-sentence')) {
      stopPlayAll()
      playSentence(target)
    }
  }
  currentTouchTarget = null
}

const handleTouchMove = (e: TouchEvent) => {
  const touch = e.touches[0]
  const diffX = Math.abs(touch.clientX - touchStartX.value)
  const diffY = Math.abs(touch.clientY - touchStartY.value)

  // 如果水平移动超过10px，认为是滑动操作
  if (diffX > 10 && diffX > diffY) {
    isSwiping.value = true
    // 滑动时取消长按
    if (longPressTimer) {
      clearTimeout(longPressTimer)
      longPressTimer = null
    }
  }

  // 垂直滑动超过10px也取消长按
  if (diffY > 10) {
    if (longPressTimer) {
      clearTimeout(longPressTimer)
      longPressTimer = null
    }
  }
}

// 鼠标右键查词（电脑端）
const handleContextMenu = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.classList.contains('tts-sentence')) return

  // 阻止默认右键菜单
  e.preventDefault()

  // 获取选中的文本或光标位置的单词
  const selection = window.getSelection()
  let word = ''

  if (selection && selection.toString().trim()) {
    // 如果有选中的文本，使用选中的内容
    word = selection.toString().trim()
  } else {
    // 否则获取鼠标位置的单词
    word = getWordAtPosition(target, e.clientX, e.clientY)
  }

  if (word) {
    // 获取句子文本
    const sentence = target.textContent || ''
    lookupWord(word, sentence)
  }
}

// 从文本中提取单词
const extractWord = (text: string): string => {
  // 清理文本并提取第一个有效单词
  const cleaned = text.trim().replace(/[^a-zA-Z\s]/g, ' ')
  const words = cleaned.split(/\s+/).filter(w => w.length > 0)
  return words[0] || ''
}

// 获取指定位置的单词
const getWordAtPosition = (element: HTMLElement, x: number, y: number): string => {
  const text = element.textContent || ''

  // 使用 Range 和 TextRange 来检测位置对应的文本
  let range: Range | null = null

  // 尝试使用 caretPositionFromPoint (标准方法)
  if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(x, y)
    if (pos) {
      range = document.createRange()
      range.setStart(pos.offsetNode, pos.offset)
      range.setEnd(pos.offsetNode, pos.offset)
    }
  }
  // 尝试使用 caretRangeFromPoint (WebKit 方法)
  else if ((document as any).caretRangeFromPoint) {
    range = (document as any).caretRangeFromPoint(x, y)
  }

  if (range) {
    // 扩展范围以获取单词边界
    const textNode = range.startContainer
    if (textNode.nodeType === Node.TEXT_NODE) {
      const textContent = textNode.textContent || ''
      let startOffset = range.startOffset
      let endOffset = range.startOffset

      // 向前查找单词边界
      while (startOffset > 0 && /[a-zA-Z]/.test(textContent[startOffset - 1])) {
        startOffset--
      }

      // 向后查找单词边界
      while (endOffset < textContent.length && /[a-zA-Z]/.test(textContent[endOffset])) {
        endOffset++
      }

      const word = textContent.substring(startOffset, endOffset)
      if (word.length > 0) {
        return word
      }
    }
  }

  // 降级方案：返回第一个单词
  return extractWord(text)
}

// 查询单词
const lookupWord = async (word: string, sentence: string = '') => {
  if (!word) return

  // 清除文本选择（移动端长按后屏蔽系统选择游标，不影响电脑端鼠标选择）
  const selection = window.getSelection()
  if (selection) {
    selection.removeAllRanges()
  }

  showDictPopup.value = true
  dictLoading.value = true
  dictError.value = ''
  dictData.value = null
  currentSentenceText.value = sentence  // 保存当前句子

  try {
    const res = await api.get<DictionaryData>(`/dictionary/lookup?word=${encodeURIComponent(word)}`)
    dictData.value = res.data
  } catch (error: any) {
    dictError.value = error.response?.data?.detail || '查询失败'
  } finally {
    dictLoading.value = false
  }
}

// 查询第二个单词（在弹窗内点击单词）
const lookupSecondWord = async (word: string, sentence: string = '') => {
  if (!word) return

  showSecondDictPopup.value = true
  secondDictLoading.value = true
  secondDictError.value = ''
  secondDictData.value = null
  secondDictSentence.value = sentence

  try {
    const res = await api.get<DictionaryData>(`/dictionary/lookup?word=${encodeURIComponent(word)}`)
    secondDictData.value = res.data
  } catch (error: any) {
    secondDictError.value = error.response?.data?.detail || '查询失败'
  } finally {
    secondDictLoading.value = false
  }
}

// 处理词典弹窗内容点击（查找点击的单词）
const handleDictPopupContentClick = (e: MouseEvent) => {
  // 如果第二个弹窗已经打开，不再处理
  if (showSecondDictPopup.value) return

  const target = e.target as HTMLElement

  // 检查点击的是否是英文文本
  const word = getWordFromClick(e, target)
  if (word && /^[a-zA-Z]+$/.test(word)) {
    lookupSecondWord(word)
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

// 处理第一个弹窗的遮罩层点击
const handleDictPopupOverlayClick = () => {
  // 如果第二个弹窗打开，先关闭第二个
  if (showSecondDictPopup.value) {
    showSecondDictPopup.value = false
  }
}

// 播放音标音频
const playPhoneticAudio = (audioUrl: string) => {
  const audio = new Audio(audioUrl)
  audio.play()
}

// 添加到生词本
const addToVocabulary = async () => {
  if (!dictData.value) return

  addingToVocabulary.value = true
  try {
    // 获取翻译内容
    let translation = ''
    if (dictData.value.translation) {
      translation = dictData.value.translation
    } else if (dictData.value.meanings && dictData.value.meanings.length > 0) {
      // 从 API 格式的释义中提取
      translation = dictData.value.meanings
        .map(m => m.definitions.map(d => d.definition).join('; '))
        .join('; ')
    }

    await api.post('/vocabulary/', {
      word: dictData.value.word,
      phonetic: dictData.value.phonetic || '',
      translation: translation,
      sentence: currentSentenceText.value,
      book_name: bookTitle.value
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

// 添加第二个单词到生词本
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
      sentence: secondDictSentence.value,
      book_name: bookTitle.value
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

// 格式化词形变换
const formatExchange = (exchange: string): string => {
  if (!exchange) return ''
  // 将 p:went/d:gone/3:goes 格式化为更易读的形式
  const mapping: Record<string, string> = {
    'p:': '过去式: ',
    'd:': '过去分词: ',
    '3:': '第三人称: ',
    's:': '复数: ',
    'i:': '现在分词: ',
    'r:': '比较级: ',
    't:': '最高级: '
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

// 全文朗读/停止朗读切换
const togglePlayAll = () => {
  if (isPlayingAll.value) {
    stopPlayAll()
  } else {
    startPlayAll()
  }
}

// 开始全文朗读（从当前页开始）
const startPlayAll = () => {
  const allSentences = Array.from(document.querySelectorAll('.tts-sentence')) as HTMLElement[]
  if (allSentences.length === 0) {
    showToast('没有可朗读的内容')
    return
  }
  isPlayingAll.value = true
  playSentence(allSentences[0])
}

// 朗读下一页的句子
const playNextPage = async () => {
  if (currentPage.value < totalPages.value - 1) {
    const nextPageIndex = currentPage.value + 1

    // 确保下一页已加载
    if (!isPageLoaded(nextPageIndex)) {
      await loadPages(nextPageIndex, nextPageIndex + 1)
    }

    goToNextPage()

    // 页面切换后，等待DOM更新再开始朗读
    setTimeout(() => {
      const allSentences = Array.from(document.querySelectorAll('.tts-sentence')) as HTMLElement[]
      if (allSentences.length > 0 && isPlayingAll.value) {
        playSentence(allSentences[0])
      }
    }, 100)
  } else {
    stopPlayAll()
    showToast('阅读完成')
  }
}

const stopPlayAll = () => {
  isPlayingAll.value = false
  if (audioPlayer.value) {
    audioPlayer.value.pause()
  }
}

const handleAudioEnded = () => {
  if (isPlayingAll.value) {
    // 查找当前句子的下一句
    const allSentences = Array.from(document.querySelectorAll('.tts-sentence')) as HTMLElement[]
    const currentIndex = allSentences.indexOf(currentSentence.value!)

    if (currentIndex !== -1 && currentIndex < allSentences.length - 1) {
      // 当前页还有下一句
      playSentence(allSentences[currentIndex + 1])
    } else {
      // 当前页朗读完毕，尝试翻到下一页
      playNextPage()
    }
  }
}

const handleAudioError = () => {
  console.error('音频播放错误')
  if (isPlayingAll.value) stopPlayAll()
}

// 横屏状态检测
const isLandscape = ref(false)

// 检测屏幕方向
const checkOrientation = () => {
  isLandscape.value = window.innerWidth > window.innerHeight
}

// 监听屏幕方向变化
const handleResize = () => {
  checkOrientation()
}

onMounted(async () => {
  await loadBook()
  // 检查URL参数，如果edit=true则自动打开编辑对话框
  if (route.query.edit === 'true') {
    openEditDialog()
  }
  // 添加键盘事件监听
  window.addEventListener('keydown', handleKeyDown)
  // 初始化横屏检测
  checkOrientation()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  // 清理工作
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('resize', handleResize)
})
</script>

<style lang="less">
.reader {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fdfdfd;
  position: relative;
}

/* 导航栏图标按钮样式 */
.nav-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  margin-left: 4px;
  cursor: pointer;
  border-radius: 50%;
  transition: all 0.2s;
  flex-shrink: 0;

  .van-icon {
    font-size: 20px;
    color: #1989fa;
  }

  &:hover {
    background: rgba(25, 137, 250, 0.1);
  }

  /* 播放中状态：圆形背景衬托 */
  &.playing {
    background: #1989fa;

    .van-icon {
      color: #fff;
    }

    &:hover {
      background: #1677d9;
    }
  }
}

/* 导航栏布局调整 */
:deep(.van-nav-bar) {
  .van-nav-bar__left {
    padding-left: 8px;
  }

  .van-nav-bar__right {
    padding-right: 8px;
  }

  .van-nav-bar__title {
    max-width: 60%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding: 0 4px;
  }
}

/* 阅读内容容器 */
.reader-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-content {
  flex: 1;
  padding: 12px;
  box-sizing: border-box;
  overflow-y: auto;
  font-size: 18px;
  line-height: 1.6;
  color: #333;

  /* 隐藏滚动条 */
  scrollbar-width: none;
  &::-webkit-scrollbar { display: none; }

  /* 保持markdown原始格式 */
  h1, h2, h3, h4, h5, h6 {
    margin: 16px 0 8px 0;
  }

  p {
    margin: 8px 0;
  }

  img {
    display: block;
    max-width: 80%;
    height: auto;
    margin: 12px auto;
    border-radius: 6px;
  }

  /* 横屏状态下图片缩小50% */
  &.landscape {
    img {
      max-width: 40%;
    }
  }

  ul, ol {
    padding-left: 24px;
    margin: 8px 0;
  }

  li {
    margin: 4px 0;
  }

  /* TTS句子样式 */
  .tts-sentence {
    cursor: pointer;
    border-bottom: 1px dashed transparent;
    transition: all 0.3s;

    &:hover {
      background-color: rgba(25, 137, 250, 0.05);
    }
  }

  .active-sentence {
    background-color: rgba(25, 137, 250, 0.15) !important;
    border-bottom: 1px dashed #1989fa;
  }
}

/* 分页控制栏 */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #fff;
  border-top: 1px solid #eee;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);

  .page-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px 12px;
    font-size: 14px;
    color: #1989fa;
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.2s;

    &:hover {
      background: rgba(25, 137, 250, 0.1);
    }

    &:active {
      background: rgba(25, 137, 250, 0.2);
    }

    &.disabled {
      color: #ccc;
      cursor: not-allowed;

      &:hover {
        background: transparent;
      }
    }

    .van-icon {
      font-size: 16px;
    }
  }

  .page-indicator {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 16px;
    background: #f5f5f5;
    border-radius: 16px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: #e8e8e8;
    }

    .current-page {
      font-size: 16px;
      font-weight: 600;
      color: #1989fa;
    }

    .page-separator {
      font-size: 14px;
      color: #999;
    }

    .total-pages {
      font-size: 14px;
      color: #666;
    }
  }
}

/* 页码选择器 */
.page-picker-content {
  padding: 16px;

  .page-picker-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    font-size: 16px;
    font-weight: 500;
    color: #333;

    .close-btn {
      font-size: 20px;
      color: #999;
      cursor: pointer;

      &:hover {
        color: #666;
      }
    }
  }

  .page-picker-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
    max-height: 300px;
    overflow-y: auto;

    .page-number-item {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 12px;
      font-size: 14px;
      color: #333;
      background: #f5f5f5;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        background: #e8e8e8;
      }

      &:active {
        background: #ddd;
      }

      &.active {
        background: #1989fa;
        color: #fff;
      }
    }
  }
}

/* 编辑区域样式 */
.edit-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.editor-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  padding: 16px;
  box-sizing: border-box;
}

/* 编辑器包裹容器 */
.editor-wrapper {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;

  .highlight-layer {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    padding: 0;
    font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
    font-size: 14px;
    line-height: 21px;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-y: auto;
    pointer-events: none;
    z-index: 1;
    color: transparent;

    .highlight,
    mark {
      background-color: #ffe066 !important;
      color: transparent !important;
      border-radius: 2px;
    }
  }

  .editor-textarea {
    position: relative;
    z-index: 2;
    flex: 1;
    width: 100%;
    min-height: 100%;
    background: transparent;
    color: #333;
    caret-color: #333;
    font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
    font-size: 14px;
    line-height: 21px;
    padding: 0;
    margin: 0;
    resize: none;
    border: none;
    outline: none;
    box-sizing: border-box;
    overflow-y: auto;
  }
}

.loading-box {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.ignored-content {
  color: #777;
  font-size: 0.95em;
  border-left: 3px solid #eee;
  padding-left: 10px;
  margin: 10px 0;
}

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

.dict-meaning-item {
  display: flex;
  gap: 12px;
}

.dict-pos {
  flex-shrink: 0;
  font-size: 14px;
  color: #1989fa;
  font-weight: 500;
  min-width: 50px;
}

.dict-def-list {
  margin: 0;
  padding-left: 20px;
  flex: 1;
}

.dict-def-item {
  margin-bottom: 10px;
}

.dict-def-text {
  font-size: 15px;
  color: #333;
  line-height: 1.5;
  margin: 0 0 4px 0;
}

.dict-def-example {
  font-size: 13px;
  color: #888;
  font-style: italic;
  margin: 0;
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

/* 词典输入对话框样式（非模态） */
.dictionary-input-popup {
  padding: 12px 16px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

.dictionary-input-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.dictionary-input-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.dictionary-input-close {
  font-size: 16px;
  color: #999;
  cursor: pointer;
  padding: 4px;
}

.dictionary-input-close:hover {
  color: #666;
}

.dictionary-input-content {
  .van-field {
    padding: 8px 0;
  }
}
</style>
