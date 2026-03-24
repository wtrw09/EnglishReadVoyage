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
        <!-- 播放按钮：始终显示 -->
        <div class="nav-icon-btn" :class="{ 'playing': isPlayingAll }" @click="togglePlayAll">
          <van-icon :name="isPlayingAll ? 'pause-circle-o' : 'play-circle-o'" />
        </div>
        <!-- 横屏直接显示的按钮 -->
        <div class="nav-icon-btn nav-more-actions" @click="openDictionaryDialog">
          <van-icon name="search" />
        </div>
        <div v-if="authStore.isAdmin" class="nav-icon-btn nav-more-actions" @click="openEditDialog">
          <van-icon name="description" />
        </div>
        <div v-if="authStore.isAdmin" class="nav-icon-btn nav-more-actions" @click="checkBookAudio">
          <van-icon name="warning-o" />
        </div>
        <!-- 竖屏更多菜单 -->
        <van-popover
          v-model:show="showMorePopover"
          placement="bottom-end"
          :actions="moreActions"
          @select="onMoreActionSelect"
        >
          <template #reference>
            <div class="nav-icon-btn nav-more-trigger">
              <van-icon name="ellipsis" />
            </div>
          </template>
        </van-popover>
      </template>
    </van-nav-bar>

    <div v-if="loading" class="loading-box">
      <van-loading type="spinner" vertical>加载书籍中...</van-loading>
    </div>

    <!-- 阅读模式：分页显示内容 -->
    <div v-else class="reader-content">
      <!-- 页面内容区域 -->
      <!-- 内容过长时使用虚拟滚动，否则直接渲染 -->
      <template v-if="useVirtualScroll">
        <VirtualContent
          class="page-content"
          :class="{ 'landscape': isLandscape }"
          :content="currentPageContent"
          @click="handleContentClick"
          @contextmenu="handleContextMenu"
        />
      </template>
      <div
        v-else
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
              <span class="dict-source-tag">本地词典</span>
              <span v-if="dictData.phonetic" class="dict-phonetic">{{ dictData.phonetic }}</span>
              <van-loading v-if="dictPhoneticLoading" type="spinner" size="16px" class="dict-audio-btn" />
              <van-icon
                v-else-if="dictPhoneticAudio"
                name="volume-o"
                class="dict-audio-btn"
                @click="playPhoneticAudio(dictPhoneticAudio)"
              />
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
            <!-- 句子翻译结果 -->
            <div v-if="currentSentenceText" class="dict-sentence-translation">
              <div class="dict-section-title">句子翻译</div>
              <div class="dict-sentence-original">{{ currentSentenceText }}</div>
              <div v-if="dictSentenceLoading" class="dict-sentence-loading">翻译中...</div>
              <div v-else-if="dictSentenceError" class="dict-sentence-error">{{ dictSentenceError }}</div>
              <div v-else class="dict-sentence-translated">{{ dictData.sentence_translation || '' }}</div>
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
                <div v-for="(item, idx) in dictData.related_phrases" :key="idx" class="dict-phrase-item">
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
              <span class="dict-source-tag">在线词典</span>
              <span v-if="dictData.phonetic" class="dict-phonetic">{{ dictData.phonetic }}</span>
              <van-icon
                v-if="dictData.phonetics?.[0]?.audio"
                name="volume-o"
                class="dict-audio-btn"
                @click="playPhoneticAudio(dictData.phonetics[0].audio)"
              />
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
            <!-- 句子翻译结果 -->
            <div v-if="currentSentenceText" class="dict-sentence-translation">
              <div class="dict-section-title">句子翻译</div>
              <div class="dict-sentence-original">{{ currentSentenceText }}</div>
              <div v-if="dictSentenceLoading" class="dict-sentence-loading">翻译中...</div>
              <div v-else-if="dictSentenceError" class="dict-sentence-error">{{ dictSentenceError }}</div>
              <div v-else class="dict-sentence-translated">{{ dictData.sentence_translation || '' }}</div>
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
              <span class="dict-source-tag">本地词典</span>
              <span v-if="secondDictData.phonetic" class="dict-phonetic">{{ secondDictData.phonetic }}</span>
              <van-loading v-if="secondDictPhoneticLoading" type="spinner" size="16px" class="dict-audio-btn" />
              <van-icon
                v-else-if="secondDictPhoneticAudio"
                name="volume-o"
                class="dict-audio-btn"
                @click="playPhoneticAudio(secondDictPhoneticAudio)"
              />
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
            <!-- 句子翻译结果 -->
            <div v-if="secondDictSentenceLoading || secondDictData.sentence_translation || secondDictSentenceError" class="dict-sentence-translation">
              <div class="dict-section-title">句子翻译</div>
              <div v-if="secondDictSentenceLoading" class="dict-sentence-loading">翻译中...</div>
              <div v-else-if="secondDictSentenceError" class="dict-sentence-error">{{ secondDictSentenceError }}</div>
              <template v-else>
                <div class="dict-sentence-original">{{ secondDictSentence }}</div>
                <div class="dict-sentence-translated">{{ secondDictData.sentence_translation }}</div>
              </template>
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
                <div v-for="(item, idx) in secondDictData.related_phrases" :key="idx" class="dict-phrase-item">
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
              <span class="dict-source-tag">在线词典</span>
              <span v-if="secondDictData.phonetic" class="dict-phonetic">{{ secondDictData.phonetic }}</span>
              <van-icon
                v-if="secondDictData.phonetics?.[0]?.audio"
                name="volume-o"
                class="dict-audio-btn"
                @click="playPhoneticAudio(secondDictData.phonetics[0].audio)"
              />
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
            <!-- 句子翻译结果 -->
            <div v-if="secondDictSentenceLoading || secondDictData.sentence_translation || secondDictSentenceError" class="dict-sentence-translation">
              <div class="dict-section-title">句子翻译</div>
              <div v-if="secondDictSentenceLoading" class="dict-sentence-loading">翻译中...</div>
              <div v-else-if="secondDictSentenceError" class="dict-sentence-error">{{ secondDictSentenceError }}</div>
              <template v-else>
                <div class="dict-sentence-original">{{ secondDictSentence }}</div>
                <div class="dict-sentence-translated">{{ secondDictData.sentence_translation }}</div>
              </template>
            </div>
          </template>
        </div>
      </div>
    </van-popup>

    <!-- 音频检查修复弹窗 -->
    <AudioFixDialog
      v-model:show="showAudioFixDialog"
      :fixed-list="audioFixedList"
      :error-list="audioErrorList"
      :book-id="bookId"
      @edit-book="handleEditBookFromAudioFix"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import md5 from 'blueimp-md5'
import { api, useAuthStore } from '@/store/auth'
import VirtualContent from '@/components/VirtualContent.vue'

// 懒加载编辑和音频检查对话框（代码分割）
const BookEditDialog = defineAsyncComponent(() => import('@/components/BookEditDialog.vue'))
const AudioFixDialog = defineAsyncComponent(() => import('@/components/AudioFixDialog.vue'))

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
  baidu_translation?: string
  sentence_translation?: string
  related_phrases?: Array<{ phrase: string; translation: string }>
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const bookId = ref('')

// 页面句子缓存：key = pageIndex, value = [{ index, text }]
const pageSentencesCache = ref<Record<number, { index: number; text: string }[]>>({})

// 监听路由参数变化，确保 bookId 正确获取
watch(() => route.params.id, (newId: string | string[] | undefined) => {
  if (newId) {
    // 清除页面句子缓存（切换书籍时）
    pageSentencesCache.value = {}
    bookId.value = Array.isArray(newId) ? newId[0] : newId
  }
}, { immediate: true })

const bookTitle = ref('')
const bookPath = ref('')
const loading = ref(true)
const audioPlayer = ref<HTMLAudioElement | null>(null)
const currentSentence = ref<HTMLElement | null>(null)
const isPlayingAll = ref(false)

// 更多菜单
const showMorePopover = ref(false)
const moreActions = computed(() => {
  const actions = [{ text: '查词', icon: 'search' }]
  if (authStore.isAdmin) {
    actions.push({ text: '编辑', icon: 'description' })
    actions.push({ text: '检查音频', icon: 'warning-o' })
  }
  return actions
})
const onMoreActionSelect = (action: { text: string }) => {
  switch (action.text) {
    case '查词':
      openDictionaryDialog()
      break
    case '编辑':
      openEditDialog()
      break
    case '检查音频':
      checkBookAudio()
      break
  }
}

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
const dictSentenceLoading = ref(false)  // 句子翻译加载状态
const dictSentenceError = ref('')  // 句子翻译错误信息
const dictPhoneticLoading = ref(false)  // 发音加载状态
const dictPhoneticAudio = ref<string | null>(null)  // 发音音频URL
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
const secondDictSentenceLoading = ref(false)  // 句子翻译加载状态
const secondDictSentenceError = ref('')  // 句子翻译错误信息
const secondDictPhoneticLoading = ref(false)  // 发音加载状态
const secondDictPhoneticAudio = ref<string | null>(null)  // 发音音频URL

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

// 音频检查相关状态
const showAudioFixDialog = ref(false)
const audioFixedList = ref<{ title: string; fixed_fields: string[]; warnings: string[] }[]>([])
const audioErrorList = ref<{ title: string; issues: string[] }[]>([])

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

// 检测当前页面内容是否过长（超过阈值启用虚拟滚动）
const LONG_CONTENT_THRESHOLD = 5000  // 字符数阈值
const useVirtualScroll = computed(() => {
  const content = currentPageContent.value
  // 移除 HTML 标签后计算纯文本长度
  const textOnly = content.replace(/<[^>]+>/g, '')
  return textOnly.length > LONG_CONTENT_THRESHOLD
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
    const MAX_CHUNK_SIZE = 5  // 每批最多 5 页，避免响应过大
    
    // 计算连续范围
    const minPage = Math.min(...pagesToLoad)
    const maxPage = Math.max(...pagesToLoad) + 1
    const range = maxPage - minPage
    
    console.log('Loading pages:', minPage, 'to', maxPage, 'range:', range)
    
    // 如果范围太大，分批请求
    if (range > MAX_CHUNK_SIZE) {
      const promises = []
      for (let i = minPage; i < maxPage; i += MAX_CHUNK_SIZE) {
        const chunkEnd = Math.min(i + MAX_CHUNK_SIZE, maxPage)
        console.log(`Chunk ${i} to ${chunkEnd}`)
        promises.push(
          api.get(`/books/${bookId.value}/pages`, {
            params: { start_page: i, end_page: chunkEnd, chunk_size: MAX_CHUNK_SIZE }
          })
        )
      }
      const results = await Promise.all(promises)
      
      // 合并结果
      results.forEach((res, idx) => {
        const data = res.data
        if (idx === 0) {
          // 第一个结果设置基本信息
          bookPath.value = data.book_path
          bookTitle.value = data.title
          if (totalPages.value === 0) {
            totalPages.value = data.page_count
          }
        }
        
        // 修复图片路径并缓存页面
        const baseUrl = `/books/${data.book_path}`
        const newPages = [...pages.value]
        data.pages.forEach((page: string, pageIndex: number) => {
          const actualIndex = data.start_page + pageIndex
          newPages[actualIndex] = page.replace(/src="\.\/assets\//g, `src="${baseUrl}/assets/`)
          pageLoadStatus.value[actualIndex] = 'loaded'
        })
        pages.value = newPages
      })
    } else {
      // 小范围直接请求
      const res = await api.get(`/books/${bookId.value}/pages`, {
        params: { start_page: minPage, end_page: maxPage, chunk_size: MAX_CHUNK_SIZE }
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
    const res = await api.get<{ content: string }>(`/books/${bookId.value}/content`)
    rawEditContent.value = res.data.content
  } catch (error) {
    showToast('加载内容失败')
    console.error(error)
    return
  }
  showEditDialog.value = true
}

// 从音频修复弹窗点击编辑书籍
const handleEditBookFromAudioFix = async (_targetBookId: string) => {
  // 关闭音频修复弹窗
  showAudioFixDialog.value = false
  // 打开编辑对话框
  await openEditDialog()
}

// 打开词典输入对话框
const openDictionaryDialog = () => {
  dictionaryInputWord.value = ''
  showDictionaryInputDialog.value = true
}

// 检查书籍音频配置
const checkBookAudio = async () => {
  try {
    const res = await api.post(`/books/${bookId.value}/check-audio`)
    const result = res.data
    
    // 设置弹窗数据
    audioFixedList.value = result.audio_fixed || []
    audioErrorList.value = result.audio_errors || []
    showAudioFixDialog.value = true
    
    // 如果有修复，重新加载句子映射
    if (result.audio_fixed?.length > 0) {
      if (bookPath.value) {
        await loadSentencesMap(`/books/${bookPath.value}`)
      }
    }
  } catch (error: any) {
    console.error('检查失败:', error)
    showToast(error.response?.data?.detail || '检查失败')
  }
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
  // 清空页面缓存和加载状态
  pages.value = []
  pageLoadStatus.value = {}
  totalPages.value = 0  // 重置总页数，让 loadPages 重新获取

  // 重新加载当前页面
  const current = currentPage.value
  loading.value = true
  try {
    await loadPages(current, current + 1)
    // 重新加载句子映射
    if (bookPath.value) {
      await loadSentencesMap(`/books/${bookPath.value}`)
    }
    // 预加载相邻页面
    preloadPages()
  } catch (error) {
    console.error('重新加载内容失败:', error)
  } finally {
    loading.value = false
  }
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
      const data = await res.json()
      // 支持两种格式：直接数组或 { sentences: [...], total_duration: ... }
      const sentences: SentenceMapping[] = Array.isArray(data) ? data : data.sentences || []
      // 构建映射: key = "text_hash"（与音频文件名一致）
      sentences.forEach((item) => {
        // 根据文本计算哈希值
        const hash = md5Hash(item.text.trim())
        // 如果后端没有返回 audio_file，则根据 hash 生成
        if (!item.audio_file) {
          item.audio_file = `${hash}.mp3`
        }
        sentencesMap.value[hash] = item
      })
      console.log('Loaded sentences map:', Object.keys(sentencesMap.value).length, 'entries')
    } else if (res.status === 404) {
      // 404 是正常情况（音频尚未生成），静默处理
      console.log('sentences.json 不存在，音频可能尚未生成')
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
    const hash = md5Hash(text.trim())
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

  // 没有预生成音频（包括：text为空、audioPlayer为null、sentencesMap中无记录）
  if (isPlayingAll.value) {
    // 全文朗读模式：显示提示并跳到下一句
    showToast('当前句子缺少语音，已跳过')
    // 使用 setTimeout 确保状态更新后再播放下一句
    setTimeout(() => {
      handleAudioEnded()
    }, 100)
  } else {
    // 单句播放模式：显示提示
    showToast('当前句子缺少语音，请先生成')
  }
}

const handleContentClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  // 向上查找最近的 .tts-sentence 元素（处理点击子元素的情况）
  const sentenceEl = target.closest('.tts-sentence') as HTMLElement | null
  if (sentenceEl) {
    // 点击句子时停止全文朗读，然后播放该句子
    stopPlayAll()
    playSentence(sentenceEl)
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

  // 向上查找最近的 .tts-sentence 元素（处理点击子元素的情况）
  const sentenceEl = target.closest('.tts-sentence') as HTMLElement | null
  if (!sentenceEl) return

  currentTouchTarget = sentenceEl
  isLongPress = false
  longPressTimer = window.setTimeout(async () => {
    isLongPress = true
    // 获取触摸位置处的单词
    let word = getWordAtPosition(sentenceEl, touch.clientX, touch.clientY)
    // 使用后端断句获取当前句子
    let sentence = await findSentenceForWord(sentenceEl, touch.clientX, touch.clientY)

    // 如果不是独立单词，使用整个句子
    if (!word && sentence) {
      word = sentence
      sentence = ''
    }

    if (word) {
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
    // 使用 currentTouchTarget 而不是 e.target，因为触摸结束时手指可能不在同一个元素上
    stopPlayAll()
    playSentence(currentTouchTarget)
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
const handleContextMenu = async (e: MouseEvent) => {
  console.log('Context menu triggered', e.target)
  const target = e.target as HTMLElement

  // 向上查找最近的 .tts-sentence 元素（处理点击子元素的情况）
  const sentenceEl = target.closest('.tts-sentence') as HTMLElement | null
  console.log('sentenceEl:', sentenceEl)
  if (!sentenceEl) {
    console.log('No sentence element found')
    return
  }

  // 阻止默认右键菜单
  e.preventDefault()

  // 尝试使用 Range 获取点击位置的文本
  let word = ''
  let sentence = ''

  // 使用 caretRangeFromPoint 获取点击位置的 Range
  let range: Range | null = null
  if ((document as any).caretRangeFromPoint) {
    range = (document as any).caretRangeFromPoint(e.clientX, e.clientY)
  } else if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(e.clientX, e.clientY)
    if (pos) {
      range = document.createRange()
      range.setStart(pos.offsetNode, pos.offset)
      range.setEnd(pos.offsetNode, pos.offset)
    }
  }

  if (range) {
    // 尝试选中点击位置附近的单词
    const textNode = range.startContainer
    if (textNode && textNode.nodeType === Node.TEXT_NODE) {
      const text = textNode.textContent || ''
      const offset = range.startOffset

      // 向前找单词边界
      let start = offset
      while (start > 0 && /[a-zA-Z]/.test(text[start - 1])) {
        start--
      }

      // 向后找单词边界
      let end = offset
      while (end < text.length && /[a-zA-Z]/.test(text[end])) {
        end++
      }

      if (start < end) {
        word = text.substring(start, end)
        // 清除选区
        const sel = window.getSelection()
        if (sel) sel.removeAllRanges()
      }
    }
  }

  // 无论是否找到单词，都获取句子
  if (sentenceEl.dataset.tts) {
    sentence = sentenceEl.dataset.tts
  }

  console.log('Word:', word, 'Sentence:', sentence)
  if (word || sentence) {
    await lookupWord(word, sentence)
  }
}

// 从后端加载指定页的句子
const loadPageSentencesFromApi = async (pageIndex: number): Promise<{ index: number; text: string }[]> => {
  // 如果已经有缓存，直接返回
  if (pageSentencesCache.value[pageIndex]) {
    return pageSentencesCache.value[pageIndex]
  }

  // 如果没有bookId，无法请求API
  if (!bookId.value) {
    return []
  }

  try {
    const res = await api.get<{ sentences: { index: number; text: string }[] }>(
      `/books/${bookId.value}/sentences?page=${pageIndex}`
    )
    const sentences = res.data.sentences || []
    // 缓存结果
    pageSentencesCache.value[pageIndex] = sentences
    return sentences
  } catch (error) {
    console.error('加载页面句子失败:', error)
    return []
  }
}

// 根据单词找到所属句子（使用后端断句）
const findSentenceForWord = async (element: HTMLElement, x: number, y: number): Promise<string> => {
  // 先尝试从后端API获取句子
  const sentences = await loadPageSentencesFromApi(currentPage.value)

  if (sentences.length > 0) {
    // 获取点击位置的单词
    const word = getWordAtPosition(element, x, y)
    if (!word) return ''

    // 遍历句子，找到包含该单词的句子
    for (const sentenceObj of sentences) {
      const sentenceText = sentenceObj.text
      // 检查句子是否包含该单词（作为完整单词，使用正则不区分大小写）
      const regex = new RegExp(`\\b${escapeRegExp(word)}\\b`, 'i')
      if (regex.test(sentenceText)) {
        return sentenceText
      }
    }
  }

  // 如果后端没有句子或没找到，回退到前端逻辑
  return getSentenceAtPosition(element, x, y)
}

// 转义正则特殊字符
const escapeRegExp = (str: string): string => {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}


// 提取当前位置所属的句子
const getSentenceAtPosition = (element: HTMLElement, x: number, y: number): string => {
  const text = element.textContent || ''
  if (!text) return ''

  // 尝试获取光标位置的偏移量
  let offset = 0
  if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(x, y)
    if (pos && pos.offsetNode && pos.offsetNode.nodeType === Node.TEXT_NODE) {
      const textNode = pos.offsetNode as ChildNode
      offset = Array.from(element.childNodes).indexOf(textNode) + pos.offset
    }
  } else if ((document as any).caretRangeFromPoint) {
    const range = (document as any).caretRangeFromPoint(x, y)
    if (range) {
      const textNode = range.startContainer
      if (textNode.nodeType === Node.TEXT_NODE) {
        const preCaretRange = range.cloneRange()
        preCaretRange.selectNodeContents(element)
        preCaretRange.setEnd(range.startContainer, range.startOffset)
        offset = preCaretRange.toString().length
      }
    }
  }

  // 向前查找句子开始
  let start = offset
  while (start > 0) {
    const char = text[start - 1]
    if (char === '.' || char === '!' || char === '?' || char === '\n') {
      break
    }
    start--
  }
  // 跳过空白字符
  while (start < offset && /\s/.test(text[start])) {
    start++
  }

  // 向后查找句子结束
  let end = offset
  while (end < text.length) {
    const char = text[end]
    if (char === '.' || char === '!' || char === '?' || char === '\n') {
      end++
      break
    }
    end++
  }

  const sentence = text.substring(start, end).trim()
  return sentence.length > 200 ? sentence.substring(0, 200) : sentence  // 限制长度
}

// 获取指定位置的单词
const getWordAtPosition = (_element: HTMLElement, x: number, y: number): string => {
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

      // 向前查找单词边界（遇到换行停止）
      while (startOffset > 0 && /[a-zA-Z]/.test(textContent[startOffset - 1])) {
        if (textContent[startOffset - 1] === '\n') break
        startOffset--
      }

      // 向后查找单词边界（遇到换行停止）
      while (endOffset < textContent.length && /[a-zA-Z]/.test(textContent[endOffset])) {
        if (textContent[endOffset] === '\n') break
        endOffset++
      }

      const word = textContent.substring(startOffset, endOffset)

      if (word.length > 0) {
        // 检查该文本节点中是否有换行符
        const hasNewLine = textContent.includes('\n')

        if (hasNewLine) {
          // 如果文本中有换行，用换行来判定行的边界
          const beforeWord = textContent.substring(0, startOffset)
          const afterWord = textContent.substring(endOffset)

          const lastNewLineBefore = beforeWord.lastIndexOf('\n')
          const nextNewLineAfter = afterWord.indexOf('\n')

          const lineStart = lastNewLineBefore >= 0 ? lastNewLineBefore + 1 : 0
          const lineEnd = nextNewLineAfter >= 0 ? endOffset + nextNewLineAfter : textContent.length

          const currentLine = textContent.substring(lineStart, lineEnd).trim()
          const wordsInLine = currentLine.split(/\s+/).filter(w => /^[a-zA-Z]+$/.test(w))

          // 只有当该行只有一个单词时才识别为单词
          if (wordsInLine.length === 1 && wordsInLine[0] === word) {
            return word
          }
        } else {
          // 如果文本中没有换行，检查整个文本节点是否只有一个单词
          const wordsInText = textContent.split(/\s+/).filter(w => /^[a-zA-Z]+$/.test(w))
          // 只有当整个文本节点只有一个单词时才识别为单词
          if (wordsInText.length === 1 && wordsInText[0] === word) {
            return word
          }
        }
      }
    }
  }

  // 降级方案：返回空字符串，由调用方处理
  return ''
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
  dictSentenceLoading.value = false
  dictPhoneticLoading.value = false
  dictPhoneticAudio.value = null
  currentSentenceText.value = sentence  // 保存当前句子

  try {
    // 查询单词
    const res = await api.get<DictionaryData>(`/dictionary/lookup?word=${encodeURIComponent(word)}`)
    dictData.value = res.data
  } catch (error: any) {
    dictError.value = error.response?.data?.detail || '查询失败'
    dictLoading.value = false
    return
  }

  // 单词查询完成后关闭 loading
  dictLoading.value = false

  // 获取发音（仅本地词典需要）
  if (dictData.value?.source === 'ecdict') {
    dictPhoneticLoading.value = true
    try {
      const pronRes = await api.get<{audio_url: string, accent: string}>(`/pronunciation/${encodeURIComponent(word)}`)
      if (pronRes.data.audio_url) {
        dictPhoneticAudio.value = pronRes.data.audio_url
      }
    } catch (pronError: any) {
      console.error('获取发音失败:', pronError)
    } finally {
      dictPhoneticLoading.value = false
    }
  }

  // 如果有句子，在后台单独请求句子翻译
  if (sentence) {
    dictSentenceLoading.value = true
    dictSentenceError.value = ''
    try {
      const transRes = await api.get<{translation: string}>(`/dictionary/translate-sentence?sentence=${encodeURIComponent(sentence)}`)
      if (dictData.value) {
        dictData.value.sentence_translation = transRes.data.translation
      }
    } catch (transError: any) {
      console.error('句子翻译失败:', transError)
      // 提取简短错误信息
      const errorMsg = transError.response?.data?.detail
      if (errorMsg) {
        // 提取关键错误信息，避免过长
        if (errorMsg.includes('未配置') || errorMsg.includes('请先')) {
          dictSentenceError.value = '翻译未配置'
        } else if (errorMsg.includes('联系管理员')) {
          dictSentenceError.value = '请联系管理员'
        } else if (errorMsg.includes('网络') || errorMsg.includes('超时')) {
          dictSentenceError.value = '网络错误'
        } else {
          dictSentenceError.value = '翻译失败'
        }
      }
    } finally {
      dictSentenceLoading.value = false
    }
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
  secondDictSentenceLoading.value = false
  secondDictPhoneticLoading.value = false
  secondDictPhoneticAudio.value = null

  try {
    // 查询单词
    const res = await api.get<DictionaryData>(`/dictionary/lookup?word=${encodeURIComponent(word)}`)
    secondDictData.value = res.data
  } catch (error: any) {
    secondDictError.value = error.response?.data?.detail || '查询失败'
    secondDictLoading.value = false
    return
  }

  // 单词查询完成后关闭 loading
  secondDictLoading.value = false

  // 获取发音（仅本地词典需要）
  if (secondDictData.value?.source === 'ecdict') {
    secondDictPhoneticLoading.value = true
    try {
      const pronRes = await api.get<{audio_url: string, accent: string}>(`/pronunciation/${encodeURIComponent(word)}`)
      if (pronRes.data.audio_url) {
        secondDictPhoneticAudio.value = pronRes.data.audio_url
      }
    } catch (pronError: any) {
      console.error('获取发音失败:', pronError)
    } finally {
      secondDictPhoneticLoading.value = false
    }
  }

  // 如果有句子，在后台单独请求句子翻译
  if (sentence) {
    secondDictSentenceLoading.value = true
    secondDictSentenceError.value = ''
    try {
      const transRes = await api.get<{translation: string}>(`/dictionary/translate-sentence?sentence=${encodeURIComponent(sentence)}`)
      if (secondDictData.value) {
        secondDictData.value.sentence_translation = transRes.data.translation
      }
    } catch (transError: any) {
      console.error('句子翻译失败:', transError)
      // 提取简短错误信息
      const errorMsg = transError.response?.data?.detail
      if (errorMsg) {
        if (errorMsg.includes('未配置') || errorMsg.includes('请先')) {
          secondDictSentenceError.value = '翻译未配置'
        } else if (errorMsg.includes('联系管理员')) {
          secondDictSentenceError.value = '请联系管理员'
        } else if (errorMsg.includes('网络') || errorMsg.includes('超时')) {
          secondDictSentenceError.value = '网络错误'
        } else {
          secondDictSentenceError.value = '翻译失败'
        }
      }
    } finally {
      secondDictSentenceLoading.value = false
    }
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
  if (!audioUrl) return
  const audio = new Audio(audioUrl)
  audio.play().catch(err => {
    console.error('播放发音失败:', err)
    showToast('播放失败')
  })
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

  // 检查是否有可用的语音
  let hasAnyAudio = false
  for (const sentence of allSentences) {
    const text = sentence.dataset.tts
    if (text) {
      const hash = md5Hash(text.trim())
      if (sentencesMap.value[hash]?.audio_file) {
        hasAnyAudio = true
        break
      }
    }
  }

  if (!hasAnyAudio) {
    showToast('当前页面缺少语音，请先生成')
    return
  }

  isPlayingAll.value = true
  playSentence(allSentences[0])
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
      // 当前页朗读完毕，停止播放
      stopPlayAll()
    }
  }
}

const handleAudioError = () => {
  console.error('音频播放错误')
  if (isPlayingAll.value) {
    // 全文朗读模式：显示提示并跳到下一句
    showToast('当前句子语音加载失败，已跳过')
    setTimeout(() => {
      handleAudioEnded()
    }, 100)
  } else {
    // 单句播放模式：显示提示
    showToast('当前句子语音加载失败，请重新生成')
  }
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

/* 竖屏：隐藏展开按钮，显示更多菜单 */
@media (orientation: portrait) {
  .nav-more-actions {
    display: none;
  }

  .nav-more-trigger {
    display: flex;
  }
}

/* 横屏：显示所有按钮，隐藏更多菜单 */
@media (orientation: landscape) {
  .nav-more-actions {
    display: flex;
  }

  .nav-more-trigger {
    display: none;
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

  /* 横屏状态下图片缩小为30% */
  &.landscape {
    img {
      max-width: 25%;
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
}

.dict-phrase {
  color: #1989fa;
  font-weight: 500;
  white-space: nowrap;
}

.dict-phrase-translation {
  color: #666;
}

/* 百度翻译结果样式 */
.dict-baidu-translation {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed #eee;
}

.dict-baidu-translation .dict-section-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dict-baidu-translation-content {
  font-size: 15px;
  color: #07c160;
  line-height: 1.6;
  margin-top: 6px;
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
