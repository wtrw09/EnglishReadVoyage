/**
 * AudiobookPlayer.vue - 听书播放器
 *
 * 功能：
 * - 播放书籍的语音内容（中英文双语）
 * - 朗读模式设置（英文→中文、英文×2→中文等）
 * - 播放列表管理（添加、移除、排序）
 * - 定时关闭功能
 * - 音频进度控制（播放、暂停、上一句、下一句）
 * - 响应式布局（横屏/竖屏）
 */
<template>
  <div class="audiobook-player" :class="{ 'landscape': isLandscape }">
    <!-- 主内容区 - 新布局：左侧播放器 + 右侧播放列表 -->
    <div class="player-layout">
      <!-- 左侧区域：导航栏 + 封面 + 控制按钮 -->
      <div class="left-section">
        <!-- 顶部导航 -->
        <div class="player-nav">
          <div class="nav-left" @click="goBack">
            <i class="fas fa-chevron-left"></i>
          </div>
          <div class="nav-title">听书模式</div>
          <div class="nav-right">
            <div class="nav-icon-btn playlist-toggle-btn" @click="showPlaylist = true">
              <i class="fas fa-list"></i>
            </div>
            <div class="nav-icon-btn" @click="showAddBooks = true">
              <i class="fas fa-plus"></i>
            </div>
          </div>
        </div>

        <!-- 书籍封面区域 -->
        <div class="book-cover-section">
          <div class="cover-container">
            <img
              v-if="currentBook?.book_cover"
              :src="buildStaticUrl(currentBook.book_cover)"
              class="book-cover"
              alt="书籍封面"
              loading="lazy"
              decoding="async"
            />
            <div v-else class="book-cover-placeholder">
              <i class="fas fa-book"></i>
            </div>
          </div>
          <h2 class="book-title">{{ currentBook?.book_title || '暂无书籍' }}</h2>
          <!-- 定时器状态和朗读模式显示在封面区域 -->
          <div class="status-info-row">
            <p v-if="sleepTimer && sleepTimerType" class="timer-status">
              <i class="fas fa-clock"></i>
              <span v-if="sleepTimerType === 'time'">
                {{ sleepTimerRemaining > 0 ? sleepTimerRemainingLabel + '后关闭' : sleepTimer + '分钟后关闭' }}
              </span>
              <span v-else-if="sleepTimerType === 'episode'">还剩{{ episodesToPlay }}集</span>
            </p>
            <p v-if="isBilingualMode && hasChineseAudio && currentBookTotalDuration > 0" class="read-mode-display">
              <i class="fas fa-volume-up"></i>
              <span>{{ getCurrentModeDisplay() }}</span>
            </p>
          </div>
        </div>

        <!-- 播放控制区 -->
        <div class="player-controls">
          <!-- 书籍整体进度 + 音频播放进度 -->
          <div v-if="currentBookTotalDuration > 0" class="book-progress-section">
            <div class="book-progress-info">
              <span class="book-progress-label">书籍进度</span>
              <span class="book-progress-value">{{ bookProgressPercent }}%</span>
            </div>
            <!-- 可拖动的书籍进度条 -->
            <div class="audio-progress-wrapper">
              <span class="audio-time current">{{ formatTime(isDragging ? seekProgressTime : bookProgressTime) }}</span>
              <van-slider
                :model-value="isDragging ? seekProgressTime : bookProgressTime"
                :max="currentBookTotalDuration"
                :step="0.1"
                :disabled="currentBookTotalDuration === 0"
                active-color="#07c160"
                inactive-color="#e0e0e0"
                bar-height="4px"
                @update:model-value="onSliderUpdate"
                @drag-start="onSeekStart"
                @drag-end="onSeekEnd"
                @change="onSliderChange"
              >
                <template #button>
                  <div class="slider-button"></div>
                </template>
              </van-slider>
              <span class="audio-time total">{{ formatTime(currentBookTotalDuration) }}</span>
            </div>
          </div>

          <!-- 控制按钮 -->
          <div class="control-buttons">
            <div class="control-btn" @click="togglePlayMode">
              <i :class="['fas', playModeIcon]"></i>
            </div>
            <div class="control-btn" @click="prevBook">
              <i class="fas fa-chevron-left"></i>
            </div>
            <div class="control-btn play-btn" @click="togglePlay">
              <i :class="['fas', isPlaying ? 'fa-pause-circle' : 'fa-play-circle']"></i>
            </div>
            <div class="control-btn" @click="nextBook">
              <i class="fas fa-chevron-right"></i>
            </div>
            <!-- 中英文对照模式按钮：始终可见（无中文音频时点击仍可打开对话框查看提示） -->
            <div
              class="control-btn"
              :class="{ 'active': isBilingualMode && hasChineseAudio }"
              @click="toggleBilingualMode"
              title="中英文对照"
            >
              <i class="fas fa-language"></i>
            </div>
            <div class="control-btn" @click="showSleepTimerSettings">
              <i :class="['fas', (sleepTimer ?? 0) > 0 ? 'fa-clock' : 'fa-regular fa-clock']"></i>
            </div>
          </div>


        </div>
      </div>

      <!-- 右侧区域：播放列表 -->
      <div v-if="playlist.items.length > 0" class="playlist-section">
        <Playlist
          :items="playlist.items"
          :current-index="currentBookIndex"
          :is-playing="isPlaying"
          @play="playBookAtIndex"
          @remove="removeBook"
          @clear="confirmClearPlaylist"
          @add="showAddBooks = true"
          @reorder="handleReorder"
        />
      </div>
    </div>

    <!-- 播放列表抽屉（仅竖屏显示） -->
    <van-popup
      v-model:show="showPlaylist"
      position="right"
      :style="{ width: '80%', height: '100%' }"
    >
      <Playlist
        :items="playlist.items"
        :current-index="currentBookIndex"
        :is-playing="isPlaying"
        @play="playBookAtIndex"
        @remove="removeBook"
        @clear="confirmClearPlaylist"
        @add="showAddBooks = true"
      />
    </van-popup>

    <!-- 定时关闭设置弹窗 -->
    <van-popup
      v-model:show="showSleepTimer"
      position="bottom"
      round
      :style="{ height: 'auto' }"
    >
      <div class="sleep-timer-popup">
        <div class="popup-header">
          <span>定时</span>
          <i class="fas fa-xmark close-icon" @click="showSleepTimer = false"></i>
        </div>

        <!-- 上次定时 / 倒计时显示 -->
        <div v-if="lastTimerMinutes > 0 || sleepTimerRemaining > 0" class="last-timer-section">
          <div class="last-timer-label">
            <span v-if="sleepTimerRemaining > 0">{{ sleepTimerRemainingLabel }}后停止</span>
            <span v-else>上次定时 {{ lastTimerLabel }}</span>
          </div>
          <van-switch
            :model-value="sleepTimerRemaining > 0"
            size="20px"
            @update:model-value="onLastTimerToggle"
          />
        </div>

        <!-- 按时间 -->
        <div class="timer-section">
          <div class="section-title-row">
            <span class="section-title">按时间</span>
            <div class="finish-current-option" @click="finishCurrentEnabled = !finishCurrentEnabled">
              <i :class="['fas', finishCurrentEnabled ? 'fa-check-square' : 'fa-square', 'check-icon', { 'checked': finishCurrentEnabled }]"></i>
              <span :class="{ 'checked': finishCurrentEnabled }">播完整集声音再停止</span>
            </div>
          </div>
          <div class="timer-options time-options">
            <div
              v-for="option in timeTimerOptions"
              :key="option.value"
              class="timer-option"
              :class="{ 'active': sleepTimerType === 'time' && sleepTimer === option.value }"
              @click="setTimeTimer(option.value)"
            >
              {{ option.label }}
            </div>
          </div>
        </div>

        <!-- 按集数 -->
        <div class="timer-section">
          <div class="section-title">按集数</div>
          <div class="timer-options episode-options">
            <div
              v-for="option in episodeTimerOptions"
              :key="option.value"
              class="timer-option"
              :class="{ 'active': sleepTimerType === 'episode' && sleepTimer === option.value }"
              @click="setEpisodeTimer(option.value)"
            >
              {{ option.label }}
            </div>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 自定义时间选择弹窗 -->
    <van-popup
      v-model:show="showCustomTimer"
      position="bottom"
      round
      :style="{ height: 'auto' }"
    >
      <div class="custom-timer-popup">
        <div class="popup-header">
          <span>自定义关闭</span>
          <i class="fas fa-xmark close-icon" @click="showCustomTimer = false"></i>
        </div>
        <div class="custom-timer-inputs">
          <div class="timer-input-item">
            <span class="input-label">小时</span>
            <van-stepper v-model="customHours" :min="0" :max="23" integer />
          </div>
          <div class="timer-input-item">
            <span class="input-label">分钟</span>
            <van-stepper v-model="customMinutes" :min="0" :max="59" integer />
          </div>
        </div>
        <div class="custom-timer-actions">
          <van-button class="cancel-btn" @click="showCustomTimer = false">取消</van-button>
          <van-button type="danger" class="confirm-btn" @click="confirmCustomTimer">确认</van-button>
        </div>
      </div>
    </van-popup>

    <!-- 添加书籍弹窗 -->
    <van-popup
      v-model:show="showAddBooks"
      position="bottom"
      round
      :style="{ height: '85%' }"
    >
      <div class="add-books-popup">
        <div class="popup-header">
          <span>添加书籍</span>
          <van-button
            type="primary"
            size="small"
            :disabled="selectedBookIds.length === 0"
            @click="addSelectedBooks"
          >
            添加 ({{ selectedBookIds.length }})
          </van-button>
        </div>
        <div class="books-list">
          <div
            v-for="group in filteredAvailableBooks"
            :key="group.group_id"
            class="book-group"
          >
            <div class="group-header" @click="toggleGroup(group.group_id)">
              <van-checkbox
                :model-value="isGroupSelected(group)"
                @update:model-value="() => toggleSelectGroup(group)"
                @click.stop
              />
              <span class="group-name">{{ group.group_name }}</span>
              <i :class="['fas', expandedGroups.includes(group.group_id) ? 'fa-chevron-down' : 'fa-chevron-right']"></i>
            </div>
            <div v-show="expandedGroups.includes(group.group_id)" class="group-books">
              <div
                v-for="book in group.books"
                :key="book.id"
                class="book-item"
                @click="toggleBookSelection(book.id)"
              >
                <van-checkbox
                  :model-value="selectedBookIds.includes(book.id)"
                  @update:model-value="() => toggleBookSelection(book.id)"
                  @click.stop
                />
                <img
                  v-if="book.cover_path"
                  :src="buildStaticUrl(book.cover_path)"
                  class="book-thumb"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="book-thumb-placeholder">
                  <i class="fas fa-book"></i>
                </div>
                <span class="book-name">{{ book.title }}</span>
              </div>
            </div>
          </div>
          <div v-if="filteredAvailableBooks.length === 0" class="empty-books-list">
            <i class="fas fa-check-circle" style="font-size: 48px; color: #07c160;"></i>
            <p>所有书籍都已添加到播放列表</p>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 朗读模式设置对话框 -->
    <BilingualModeDialog
      v-model:show="showBilingualModeDialog"
      :current-preset-id="userReadConfig.presetId"
      :current-segments="userReadConfig.segments"
      :missing-zh-count="missingZhCount"
      :has-chinese-audio="hasChineseAudio"
      @confirm="handleBilingualModeConfirm"
    />

    <!-- 音频完整性检查弹窗 -->
    <van-popup
      v-model:show="showAudioCheck"
      :close-on-click-overlay="false"
      round
      :style="{ width: '85%', padding: '24px 20px' }"
      @close="onAudioCheckClose"
    >
      <div class="audio-check-popup">
        <div class="check-title">
          <van-loading v-if="isChecking" type="spinner" size="24px" />
          <i v-else class="fas fa-triangle-exclamation warning-icon"></i>
          <span>{{ isChecking ? '正在检查音频完整性...' : '音频完整性检查结果' }}</span>
        </div>

        <!-- 检查中显示进度条 -->
        <div v-if="isChecking" class="check-progress">
          <van-progress
            :percentage="checkProgress"
            :show-pivot="false"
            color="#07c160"
            track-color="#e0e0e0"
          />
          <p class="check-progress-text">正在检查第 {{ checkedCount }} / {{ totalBooksCount }} 本书籍</p>
        </div>

        <!-- 检查完成显示结果 -->
        <div v-else class="check-result">
          <div class="result-summary">
            <div class="result-item">
              <span class="label">英文完整:</span>
              <span class="value success">{{ checkResult.complete_books_en }} / {{ checkResult.total_books }}</span>
            </div>
            <div class="result-item">
              <span class="label">中文完整:</span>
              <span class="value" :class="checkResult.complete_books_zh === checkResult.total_books ? 'success' : 'warning'">
                {{ checkResult.complete_books_zh }} / {{ checkResult.total_books }}
              </span>
            </div>
          </div>

          <!-- 缺失音频的书籍列表 -->
          <div v-if="incompleteBooks.length > 0" class="incomplete-list">
            <p class="incomplete-title">以下书籍缺少音频（缺少的语言将自动跳过）：</p>
            <div
              v-for="book in incompleteBooks"
              :key="book.book_id"
              class="incomplete-item"
            >
              <span class="book-name">{{ book.book_title }}</span>
              <span class="missing-info">
                <span v-if="!book.is_complete_en" class="missing-badge en">英文{{ book.missing_en }}</span>
                <span v-if="!book.is_complete_zh" class="missing-badge zh">中文{{ book.missing_zh }}</span>
              </span>
            </div>
          </div>
        </div>

        <!-- 按钮 -->
        <div class="check-actions">
          <van-button
            v-if="isChecking"
            type="default"
            size="small"
            @click="cancelCheck"
          >
            取消
          </van-button>
          <template v-else>
            <van-button type="primary" block @click="closeAudioCheck">
              我知道了
            </van-button>
          </template>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  showToast,
  showConfirmDialog
} from 'vant'
import { showErrorDialog } from '@/utils/message'
import { api } from '@/store/auth'
import { buildStaticUrl } from '@/utils/apiBase'
import {
  createPlaylistPlayer,
  buildBilingualPlaylist,
  type PlaylistPlayer,
  type BilingualSegmentConfig
} from '@/utils/nativeAudio'
import Playlist from '@/components/Playlist.vue'
import BilingualModeDialog from '@/components/BilingualModeDialog.vue'

// 路由
const router = useRouter()

// 响应式状态
const isLandscape = ref(false)
const isPlaying = ref(false)
const currentBookIndex = ref(0)
const currentAudioIndex = ref(0)
const totalAudioFiles = ref(0)
const sleepTimer = ref<number | null>(null)
const sleepTimerType = ref<'time' | 'episode' | null>(null)
const sleepTimerInterval = ref<number | null>(null)
const episodesToPlay = ref(0) // 按集数定时剩余集数

// 弹窗显示状态
const showPlaylist = ref(false)
const showSleepTimer = ref(false)
const showAddBooks = ref(false)
const showCustomTimer = ref(false)
const showBilingualModeDialog = ref(false)

// 音频完整性检查状态
const showAudioCheck = ref(false)
const isChecking = ref(false)
const checkProgress = ref(0)
const checkedCount = ref(0)
const totalBooksCount = ref(0)
const checkResult = ref<{
  total_books: number
  complete_books_en: number
  complete_books_zh: number
  results: Array<{
    book_id: string
    book_title: string
    total_sentences: number
    en_audio_count: number
    zh_audio_count: number
    missing_en: number
    missing_zh: number
    is_complete_en: boolean
    is_complete_zh: boolean
  }>
}>({
  total_books: 0,
  complete_books_en: 0,
  complete_books_zh: 0,
  results: []
})

// 计算不完整的书籍
const incompleteBooks = computed(() => {
  if (!checkResult.value.results) return []
  return checkResult.value.results.filter(
    book => !book.is_complete_en || !book.is_complete_zh
  )
})

// 朗读模式配置
interface ReadSegment {
  lang: 'en' | 'zh'
  count: number
}

// 读取保存的设置
const loadSavedReadConfig = () => {
  const saved = localStorage.getItem('bilingualReadConfig')
  if (saved) {
    try {
      userReadConfig.value = JSON.parse(saved)
      // 恢复双语模式状态
      isBilingualMode.value = true
      userEnabledBilingual.value = true  // 标记用户主动启用了双语模式
    } catch (e) {
      // 解析失败，使用默认
    }
  }
}

// 保存设置
const saveReadConfig = () => {
  localStorage.setItem('bilingualReadConfig', JSON.stringify(userReadConfig.value))
}

// 当前朗读模式配置
const userReadConfig = ref<{
  presetId: string
  segments: ReadSegment[]
}>({
  presetId: 'en1-zh1',
  segments: [
    { lang: 'en', count: 1 },
    { lang: 'zh', count: 1 }
  ]
})

// 当前正在播放的段索引（用于双语模式）
const currentSegmentIndex = ref(0)
// 当前段的重复计数
const currentSegmentRepeat = ref(0)

// 标记是否正在切换书籍（用于 prev/next/playBookAtIndex 切书时屏蔽瞬时 error toast）
const isSwitchingBook = ref(false)

// 定时器设置
const lastTimerMinutes = ref(30) // 上次定时分钟数
const lastTimerEnabled = ref(false)
const finishCurrentEnabled = ref(false) // 播完整集再停止
const customHours = ref(0)
const customMinutes = ref(30)
const sleepTimerRemaining = ref(0) // 倒计时剩余秒数

// 播放列表数据
const playlist = ref({
  id: 0,
  name: '默认播放列表',
  play_mode: 'sequential',
  sleep_timer: null as number | null,
  current_book_index: 0,
  items: [] as PlaylistItem[],
  created_at: '',
  updated_at: ''
})

// 可添加的书籍
const availableBooks = ref<BookGroup[]>([])
const selectedBookIds = ref<string[]>([])
const expandedGroups = ref<number[]>([])

// 过滤掉已在播放列表中的书籍
const filteredAvailableBooks = computed(() => {
  // 获取已在播放列表中的书籍ID
  const playlistBookIds = new Set(playlist.value.items.map(item => item.book_id))

  return availableBooks.value.map(group => ({
    ...group,
    books: group.books.filter(book => !playlistBookIds.has(book.id))
  })).filter(group => group.books.length > 0)
})

// 音频播放器（PlaylistPlayer 实例，跨端：Web / Capacitor / 鸿蒙桥均适配）
// manageMediaSession=false：外层自己接管锁屏控件（需要切 prev/nextBook）
const player: PlaylistPlayer = createPlaylistPlayer({ manageMediaSession: false })
// 记录当前 player 加载的书籍Id，避免重复 setTracks
let tracksLoadedForBookId = ''

// 按时间定时选项
const timeTimerOptions = [
  { label: '15分', value: 15 },
  { label: '30分', value: 30 },
  { label: '60分', value: 60 },
  { label: '90分', value: 90 },
  { label: '自定义', value: -1 }
]

// 按集数定时选项
const episodeTimerOptions = [
  { label: '播完本集', value: 1 },
  { label: '播完2集', value: 2 },
  { label: '播完3集', value: 3 },
  { label: '播完5集', value: 5 }
]

// 类型定义
interface PlaylistItem {
  id: number
  book_id: string
  book_title: string
  book_cover: string | null
  sort_order: number
  added_at: string
}

interface Book {
  id: string
  title: string
  cover_path: string | null
  level: string
}

interface BookGroup {
  group_id: number
  group_name: string
  books: Book[]
}

interface AudioInfo {
  text_hash: string
  text: string
  translation: string
  audio_url: string
  audio_url_zh: string
  duration: number
  duration_zh: number
}

// 计算属性
const currentBook = computed(() => {
  if (playlist.value.items.length === 0) return null
  return playlist.value.items[currentBookIndex.value] || null
})


// 计算上次定时显示文本
const lastTimerLabel = computed(() => {
  const minutes = lastTimerMinutes.value
  if (minutes < 60) {
    return `${minutes}分钟`
  } else {
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    return mins > 0 ? `${hours}小时${mins}分` : `${hours}小时`
  }
})

// 倒计时显示文本
const sleepTimerRemainingLabel = computed(() => {
  const totalSeconds = sleepTimerRemaining.value
  if (totalSeconds <= 0) return ''

  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  if (hours > 0) {
    return `${hours}小时${minutes}分${seconds}秒`
  } else if (minutes > 0) {
    return `${minutes}分${seconds}秒`
  } else {
    return `${seconds}秒`
  }
})

// 播放模式图标映射（Font Awesome）
const playModeIcon = computed(() => {
  const mode = playlist.value.play_mode
  switch (mode) {
    case 'single':
      return 'fa-repeat' // 单曲循环
    case 'sequential':
      return 'fa-arrow-right-arrow-left' // 列表顺序
    case 'random':
      return 'fa-shuffle' // 列表随机
    default:
      return 'fa-arrow-right-arrow-left'
  }
})

// 播放模式文字提示
const playModeText = computed(() => {
  const mode = playlist.value.play_mode
  switch (mode) {
    case 'single':
      return '单曲循环'
    case 'sequential':
      return '列表顺序播放'
    case 'random':
      return '列表随机播放'
    default:
      return '列表顺序播放'
  }
})

// 格式化时间显示 (秒 -> mm:ss)
const formatTime = (seconds: number): string => {
  if (!seconds || seconds < 0) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 当前播放进度（由 PlaylistPlayer 回调驱动，毫秒）
const currentGlobalMs = ref(0)

// 当前书籍整体进度（秒，供 slider/时间显示使用）
const bookProgressTime = computed(() => currentGlobalMs.value / 1000)

// 当前书籍整体进度百分比
const bookProgressPercent = computed(() => {
  if (currentBookTotalDuration.value <= 0) return 0
  // 拖动时使用拖动位置的进度
  const progressTime = isDragging.value ? seekProgressTime.value : bookProgressTime.value
  return Math.min(100, Math.round((progressTime / currentBookTotalDuration.value) * 100))
})

// 方法
const checkOrientation = () => {
  isLandscape.value = window.innerWidth > window.innerHeight
}

// === 调试辅助：排查 Capacitor Android 安全区域问题 ===
const debugLayout = (source: string) => {
  const el = document.querySelector('.audiobook-player')
  const navEl = document.querySelector('.player-nav')
  const rect = el?.getBoundingClientRect()
  const navRect = navEl?.getBoundingClientRect()

  // 从计算样式中读取 safe-area-inset-top
  const dummy = document.createElement('div')
  dummy.style.cssText = 'position:fixed;top:env(safe-area-inset-top, 0px);visibility:hidden'
  document.body.appendChild(dummy)
  const safeTop = parseFloat(getComputedStyle(dummy).top)
  document.body.removeChild(dummy)

  const info = {
    source,
    isNativeShell: document.getElementById('app-root')?.classList.contains('is-native-shell'),
    windowInnerHeight: window.innerHeight,
    documentClientHeight: document.documentElement.clientHeight,
    screenHeight: screen.height,
    playerTop: rect?.top,
    playerHeight: rect?.height,
    playerBottom: rect?.bottom,
    navTop: navRect?.top,
    navHeight: navRect?.height,
    safeAreaInsetTop: safeTop,
    currentBookTotalDuration: currentBookTotalDuration.value,
  }
  console.log('[AudiobookPlayer:debugLayout]', JSON.stringify(info, null, 2))
}
// ==================================================
const goBack = () => {
  router.back()
}

// 加载播放列表
const loadPlaylist = async () => {
  try {
    const res = await api.get('/audiobook/playlist')
    playlist.value = res.data
    currentBookIndex.value = playlist.value.current_book_index

    // 如果有当前书籍，加载音频信息
    if (currentBook.value) {
      await loadBookAudioInfo(currentBook.value.book_id)
    }
  } catch (error) {
    console.error('加载播放列表失败:', error)
    showErrorDialog('加载播放列表失败')
  }
}

// 当前书籍的音频列表
const currentBookAudioList = ref<AudioInfo[]>([])
const currentBookTotalDuration = ref(0) // 当前书籍总时长（秒）
const hasChineseAudio = ref(false)  // 是否有中文音频
const isBilingualMode = ref(false)  // 是否启用中英文对照模式
const missingZhCount = ref(0)  // 缺少中文音频的句子数量
const userEnabledBilingual = ref(false)  // 用户是否主动启用了双语模式

// 播放进度
const currentTime = ref(0) // 当前播放时间（秒）
const duration = ref(0) // 当前音频总时长（秒）
const isDragging = ref(false) // 是否正在拖动进度条
const seekProgressTime = ref(0) // 拖动时的临时进度时间（秒）

// 根据当前书籍音频列表与双语配置重建 playlist tracks
const rebuildTracksForCurrentBook = (): boolean => {
  const book = currentBook.value
  if (!book || currentBookAudioList.value.length === 0) {
    player.setTracks([])
    tracksLoadedForBookId = ''
    return false
  }

  const items = currentBookAudioList.value.map(a => ({
    audio_url: buildStaticUrl(a.audio_url),
    audio_url_zh: a.audio_url_zh ? buildStaticUrl(a.audio_url_zh) : undefined,
    duration: a.duration,
    duration_zh: a.duration_zh,
    text_hash: a.text_hash,
    bookId: book.book_id
  }))

  // 统一走 buildBilingualPlaylist，保证时长累加口径一致：
  //   - 未启用双语：config=undefined -> 默认每句英文×1
  //   - 启用双语 + 有中文：按用户原配置
  //   - 启用双语 + 无中文：将中文段 count 置 0（buildBilingualPlaylist 会跳过），
  //     英文段保持用户配置的重复次数 -> 总时长 = 英文时长 × 英文count × 句数
  let effectiveConfig: BilingualSegmentConfig | undefined
  if (isBilingualMode.value) {
    if (hasChineseAudio.value) {
      effectiveConfig = userReadConfig.value
    } else {
      effectiveConfig = {
        segments: userReadConfig.value.segments.map(s =>
          s.lang === 'zh' ? { ...s, count: 0 } : { ...s }
        )
      }
    }
  }

  const tracks = buildBilingualPlaylist(items, effectiveConfig)

  player.setTracks(tracks)
  tracksLoadedForBookId = book.book_id
  return tracks.length > 0
}

// 前端兜底：若后端返回的 duration 有缺失，先并发探测每段音频的真实时长再 rebuild，
// 避免 rebuildTracksForCurrentBook 用 0 构造 timeline 导致"总时长=0、播一句涨一点"。
const probeAudioDuration = (url: string, timeoutMs = 3000): Promise<number> => {
  return new Promise((resolve) => {
    if (!url) { resolve(0); return }
    const el = document.createElement('audio')
    el.preload = 'metadata'
    let done = false
    const finish = (d: number) => {
      if (done) return
      done = true
      el.src = ''
      try { el.remove() } catch { /* ignore */ }
      resolve(Number.isFinite(d) && d > 0 ? d : 0)
    }
    el.addEventListener('loadedmetadata', () => finish(el.duration))
    el.addEventListener('error', () => finish(0))
    el.src = url
    setTimeout(() => finish(0), timeoutMs)
  })
}

const fillMissingDurationsFallback = async (list: AudioInfo[]): Promise<boolean> => {
  // 最多并发 6 个探测请求，避免小书一次性发太多
  const tasks: Array<() => Promise<void>> = []
  let patched = false
  for (const a of list) {
    if ((!a.duration || a.duration <= 0) && a.audio_url) {
      tasks.push(async () => {
        const sec = await probeAudioDuration(buildStaticUrl(a.audio_url))
        if (sec > 0) { a.duration = sec; patched = true }
      })
    }
    if ((!a.duration_zh || a.duration_zh <= 0) && a.audio_url_zh) {
      tasks.push(async () => {
        const sec = await probeAudioDuration(buildStaticUrl(a.audio_url_zh))
        if (sec > 0) { a.duration_zh = sec; patched = true }
      })
    }
  }
  const CONCURRENCY = 6
  let idx = 0
  const workers = Array.from({ length: Math.min(CONCURRENCY, tasks.length) }, async () => {
    while (idx < tasks.length) {
      const i = idx++
      try { await tasks[i]() } catch { /* ignore */ }
    }
  })
  await Promise.all(workers)
  return patched
}

// 加载书籍音频信息
const loadBookAudioInfo = async (bookId: string) => {
  try {
    const res = await api.get(`/audiobook/books/${bookId}/audio`)
    currentBookAudioList.value = res.data.audio_list
    totalAudioFiles.value = res.data.total
    hasChineseAudio.value = res.data.has_chinese || false

    // 检查缺少中文音频的数量
    if (res.data.audio_list && res.data.audio_list.length > 0) {
      const enCount = res.data.audio_list.filter((a: AudioInfo) => a.audio_url).length
      const zhCount = res.data.audio_list.filter((a: AudioInfo) => a.audio_url_zh).length
      missingZhCount.value = enCount - zhCount
    } else {
      missingZhCount.value = 0
    }

    // 如果没有中文音频且用户没有主动启用双语模式，则关闭双语模式
    if (!hasChineseAudio.value && !userEnabledBilingual.value) {
      isBilingualMode.value = false
    }

    currentAudioIndex.value = 0
    currentTime.value = 0
    duration.value = 0
    seekProgressTime.value = 0
    currentGlobalMs.value = 0
    currentSegmentIndex.value = 0
    currentSegmentRepeat.value = 0

    // 兜底：如果后端返回了 duration 缺失的句子，先并发探测真实时长补齐，再 rebuild
    const needFallback = currentBookAudioList.value.some(
      a => (a.audio_url && (!a.duration || a.duration <= 0)) ||
           (a.audio_url_zh && (!a.duration_zh || a.duration_zh <= 0))
    )
    if (needFallback) {
      await fillMissingDurationsFallback(currentBookAudioList.value)
    }

    // 重建 tracks（setTracks 同步 emit timelineupdate → 回调会立即更新 currentBookTotalDuration，
    // 后端 total_duration 不考虑用户朗读配置（英文×n），不要拿来做备胎，否则会覆盖正确值）
    rebuildTracksForCurrentBook()
  } catch (error) {
    console.error('加载音频信息失败:', error)
    currentBookAudioList.value = []
    totalAudioFiles.value = 0
    currentBookTotalDuration.value = 0
    currentTime.value = 0
    duration.value = 0
    missingZhCount.value = 0
    player.setTracks([])
    tracksLoadedForBookId = ''
  }
}

// 播放控制
const togglePlay = async () => {
  if (!currentBook.value) {
    showToast('请先添加书籍到播放列表')
    return
  }

  if (isPlaying.value) {
    pauseAudio()
  } else {
    // 如果是双语模式，先检查音频完整性
    if (isBilingualMode.value) {
      const hasIncomplete = await checkAudioCompletenessQuiet()
      if (hasIncomplete) {
        // 有缺失的音频，弹出对话框提醒
        showAudioCheck.value = true
      } else {
        // 所有音频完整，直接播放
        await playAudio()
      }
    } else {
      await playAudio()
    }
  }
}

// 静默检查音频完整性，返回是否有缺失
const checkAudioCompletenessQuiet = async (): Promise<boolean> => {
  try {
    const res = await api.get('/audiobook/playlist/audio-check')
    checkResult.value = res.data

    // 检查是否有缺失的音频
    const hasIncomplete = res.data.results.some(
      (book: { is_complete_en: boolean; is_complete_zh: boolean }) =>
        !book.is_complete_en || !book.is_complete_zh
    )
    return hasIncomplete
  } catch (error) {
    console.error('检查音频完整性失败:', error)
    // 检查失败时默认不弹窗，直接播放
    return false
  }
}

// 取消检查
const cancelCheck = () => {
  showAudioCheck.value = false
  isChecking.value = false
}

// 音频检查弹出框关闭时自动播放
const onAudioCheckClose = () => {
  // 弹出框关闭后自动播放
  playAudio()
}

// 关闭音频检查弹出框（播放由 @close 事件触发）
const closeAudioCheck = () => {
  showAudioCheck.value = false
}

const playAudio = async () => {
  if (!currentBook.value) return

  // 检查是否有音频文件
  if (currentBookAudioList.value.length === 0) {
    showToast('该书籍暂无音频文件')
    return
  }

  try {
    // 无中文音频降级由 rebuildTracksForCurrentBook 统一处理（中文段 count 置 0 跳过，
    // 保留英文段重复次数），playAudio 不再干预 isBilingualMode 状态。

    // 如果当前 player 的 tracks 不是本书，重建
    if (tracksLoadedForBookId !== currentBook.value.book_id) {
      rebuildTracksForCurrentBook()
    }

    isPlaying.value = true
    await player.play()
  } catch (error) {
    console.error('播放失败:', error)
    showErrorDialog('播放失败')
    isPlaying.value = false
  }
}

const pauseAudio = () => {
  player.pause()
  isPlaying.value = false
}

// 切换书籍
const prevBook = async () => {
  try {
    const res = await api.get('/audiobook/playlist/next?direction=prev&force=true')
    if (res.data.has_next) {
      // 记录当前播放状态
      const wasPlaying = isPlaying.value
      // 标记正在切换书籍，避免显示错误提示
      isSwitchingBook.value = true
      // 先停止当前播放（player 会在 setTracks 时清理旧 track）
      player.pause()
      isPlaying.value = false

      currentBookIndex.value = res.data.index
      currentAudioIndex.value = 0

      // 始终加载新书籍音频信息（无论是否播放）
      await loadBookAudioInfo(res.data.book_id)

      // 如果之前在播放，继续播放
      if (wasPlaying) {
        await playAudio()
      }
      // 延迟重置切换标记
      setTimeout(() => { isSwitchingBook.value = false }, 100)
    }
  } catch (error) {
    console.error('切换书籍失败:', error)
    isSwitchingBook.value = false
  }
}

const nextBook = async () => {
  try {
    const res = await api.get('/audiobook/playlist/next?direction=next&force=true')
    if (res.data.has_next) {
      // 记录当前播放状态
      const wasPlaying = isPlaying.value
      // 标记正在切换书籍，避免显示错误提示
      isSwitchingBook.value = true
      // 先停止当前播放（player 会在 setTracks 时清理旧 track）
      player.pause()
      isPlaying.value = false

      currentBookIndex.value = res.data.index
      currentAudioIndex.value = 0

      // 始终加载新书籍音频信息（无论是否播放）
      await loadBookAudioInfo(res.data.book_id)

      // 如果之前在播放，继续播放
      if (wasPlaying) {
        await playAudio()
      }
      // 延迟重置切换标记
      setTimeout(() => { isSwitchingBook.value = false }, 100)
    }
  } catch (error) {
    console.error('切换书籍失败:', error)
    isSwitchingBook.value = false
  }
}

const playBookAtIndex = async (index: number) => {
  if (index < 0 || index >= playlist.value.items.length) return

  // 点击的是当前书籍
  if (index === currentBookIndex.value) {
    if (isPlaying.value) {
      // 正在播放中，不做任何事
      return
    } else {
      // 未播放，开始播放
      await playAudio()
      return
    }
  }

  const bookId = playlist.value.items[index].book_id

  // 标记正在切换书籍，避免显示错误提示
  isSwitchingBook.value = true
  // 先停止当前播放（player 会在 setTracks 时清理旧 track）
  player.pause()
  isPlaying.value = false

  currentBookIndex.value = index
  currentAudioIndex.value = 0

  // 更新服务器端的当前索引
  try {
    await api.put('/audiobook/playlist/settings', {
      current_book_index: index
    })
  } catch (error) {
    console.error('更新播放索引失败:', error)
  }

  // 切换书籍后加载音频并播放
  await loadBookAudioInfo(bookId)
  await playAudio()
  // 延迟重置切换标记
  setTimeout(() => { isSwitchingBook.value = false }, 100)
}

// 播放模式切换（单曲 -> 顺序 -> 随机 -> 单曲）
const togglePlayMode = async () => {
  const modes = ['single', 'sequential', 'random']
  const currentIndex = modes.indexOf(playlist.value.play_mode)
  const nextIndex = (currentIndex + 1) % modes.length
  const newMode = modes[nextIndex]
  await setPlayMode(newMode)
}

const setPlayMode = async (mode: string) => {
  try {
    await api.put('/audiobook/playlist/settings', {
      play_mode: mode
    })
    playlist.value.play_mode = mode
    showToast(`已切换到${playModeText.value}`)
  } catch (error) {
    console.error('设置播放模式失败:', error)
    showErrorDialog('设置失败')
  }
}

// 睡眠定时器
// 切换中英文对照模式 - 打开设置对话框
const toggleBilingualMode = () => {
  showBilingualModeDialog.value = true
}

// 确认朗读模式设置
const handleBilingualModeConfirm = (presetId: string, segments: ReadSegment[]) => {
  userReadConfig.value = {
    presetId,
    segments
  }
  isBilingualMode.value = true
  userEnabledBilingual.value = true  // 标记用户主动启用了双语模式
  saveReadConfig()
  
  // 重置播放状态，从头开始
  player.pause()
  isPlaying.value = false
  currentAudioIndex.value = 0
  currentTime.value = 0
  currentGlobalMs.value = 0
  currentSegmentIndex.value = 0
  currentSegmentRepeat.value = 0

  // 朗读模式变更 → 重建 tracks（timelineupdate 事件会同步更新总时长）
  if (currentBookAudioList.value.length > 0) {
    rebuildTracksForCurrentBook()
  }

  showToast(`已启用朗读模式: ${getPresetName(presetId)}`)
}

// 获取预设名称
// 获取朗读模式名称
const getPresetName = (presetId: string): string => {
  const presetNames: Record<string, string> = {
    'en1-zh1': '英文→中文',
    'en1-zh1-en1': '英文→中文→英文',
    'en2-zh1': '英文×2→中文',
    'en-only': '仅英文'
  }
  if (presetNames[presetId]) {
    return presetNames[presetId]
  }
  // 自定义模式：生成本地化的名称
  const config = userReadConfig.value
  if (config.segments && config.segments.length > 0) {
    const parts = config.segments.map(s => {
      const lang = s.lang === 'en' ? 'EN' : 'ZH'
      return s.count > 1 ? `${lang}×${s.count}` : lang
    })
    return parts.join('→')
  }
  return '自定义'
}

// 获取当前朗读模式的简短描述
const getCurrentModeDisplay = (): string => {
  const config = userReadConfig.value
  if (!config.segments || config.segments.length === 0) {
    return ''
  }
  return config.segments.map(s => {
    const lang = s.lang === 'en' ? 'EN' : 'ZH'
    return s.count > 1 ? `${lang}×${s.count}` : lang
  }).join('→')
}

const showSleepTimerSettings = () => {
  showSleepTimer.value = true
}

// 设置按时间定时
const setTimeTimer = (minutes: number) => {
  if (minutes === -1) {
    // 打开自定义时间选择
    showCustomTimer.value = true
    return
  }

  sleepTimerType.value = 'time'
  sleepTimer.value = minutes
  lastTimerMinutes.value = minutes
  episodesToPlay.value = 0
  startSleepTimer()
  showSleepTimer.value = false
  showToast(`已设置 ${minutes} 分钟后关闭`)
}

// 设置按集数定时
const setEpisodeTimer = (episodes: number) => {
  sleepTimerType.value = 'episode'
  sleepTimer.value = episodes
  episodesToPlay.value = episodes
  startSleepTimer()
  showSleepTimer.value = false
  showToast(`已设置播完 ${episodes} 集后关闭`)
}

// 启动定时器
const startSleepTimer = () => {
  // 清除现有定时器
  if (sleepTimerInterval.value) {
    clearInterval(sleepTimerInterval.value)
    sleepTimerInterval.value = null
  }

  if (sleepTimerType.value === 'time' && sleepTimer.value && sleepTimer.value > 0) {
    sleepTimerRemaining.value = sleepTimer.value * 60 // 转换为秒
    sleepTimerInterval.value = window.setInterval(() => {
      sleepTimerRemaining.value--
      if (sleepTimerRemaining.value <= 0) {
        executeSleepTimer()
      }
    }, 1000)
  }
}

// 执行定时关闭
const executeSleepTimer = () => {
  pauseAudio()
  clearSleepTimer()
  showToast('定时关闭已生效')
}

// 清除定时器
const clearSleepTimer = () => {
  if (sleepTimerInterval.value) {
    clearInterval(sleepTimerInterval.value)
    sleepTimerInterval.value = null
  }
  sleepTimer.value = null
  sleepTimerType.value = null
  sleepTimerRemaining.value = 0
  episodesToPlay.value = 0
  lastTimerEnabled.value = false
}



// 上次定时开关
const onLastTimerToggle = (enabled: boolean | string | number) => {
  const isEnabled = typeof enabled === 'boolean' ? enabled : Boolean(enabled)
  if (isEnabled) {
    sleepTimerType.value = 'time'
    sleepTimer.value = lastTimerMinutes.value
    episodesToPlay.value = 0
    startSleepTimer()
    showToast(`已启用上次定时 ${lastTimerMinutes.value} 分钟`)
  } else {
    clearSleepTimer()
    showToast('已取消定时关闭')
  }
}

// 自定义时间选择
const confirmCustomTimer = () => {
  const totalMinutes = customHours.value * 60 + customMinutes.value
  if (totalMinutes > 0) {
    sleepTimerType.value = 'time'
    sleepTimer.value = totalMinutes
    lastTimerMinutes.value = totalMinutes
    episodesToPlay.value = 0
    startSleepTimer()
    showToast(`已设置 ${totalMinutes} 分钟后关闭`)
  }
  showCustomTimer.value = false
  showSleepTimer.value = false
}

// 打开自定义时间选择器时重置默认值
watch(showCustomTimer, (show) => {
  if (show) {
    // 重置为默认值
    customHours.value = 0
    customMinutes.value = 30
  }
})

// 监听双语模式或朗读配置变化 → 重建 tracks，时长由 timelineupdate 事件自动同步
watch([isBilingualMode, userReadConfig], () => {
  if (currentBookAudioList.value.length > 0) {
    rebuildTracksForCurrentBook()
  }
}, { deep: true })

// 播放列表管理
const confirmClearPlaylist = () => {
  showConfirmDialog({
    title: '清空播放列表',
    message: '确定要清空播放列表吗？'
  }).then(async () => {
    try {
      await api.delete('/audiobook/playlist/clear')
      playlist.value.items = []
      currentBookIndex.value = 0
      pauseAudio()
      showToast('播放列表已清空')
    } catch (error) {
      console.error('清空播放列表失败:', error)
      showErrorDialog('清空失败')
    }
  }).catch(() => {
    // 取消
  })
}

const removeBook = async (itemId: number) => {
  try {
    await api.delete(`/audiobook/playlist/items/${itemId}`)
    // 从本地列表移除
    const index = playlist.value.items.findIndex(item => item.id === itemId)
    if (index !== -1) {
      playlist.value.items.splice(index, 1)
      if (index < currentBookIndex.value) {
        currentBookIndex.value--
      } else if (index === currentBookIndex.value) {
        currentAudioIndex.value = 0
        if (isPlaying.value) {
          await playAudio()
        }
      }
    }
    showToast('已移除')
  } catch (error) {
    console.error('移除书籍失败:', error)
    showErrorDialog('移除失败')
  }
}

// 处理重新排序
const handleReorder = async (itemOrders: { item_id: number; sort_order: number }[]) => {
  try {
    await api.put('/audiobook/playlist/reorder', { item_orders: itemOrders })
    // 更新本地排序
    const sortedItems = itemOrders
      .map(order => playlist.value.items.find(item => item.id === order.item_id))
      .filter((item): item is PlaylistItem => item !== undefined)
    playlist.value.items = sortedItems
    showToast('排序已保存')
  } catch (error) {
    console.error('保存排序失败:', error)
    showErrorDialog('保存排序失败')
    // 重新加载播放列表
    await loadPlaylist()
  }
}

// 添加书籍
const loadAvailableBooks = async () => {
  try {
    const res = await api.get('/audiobook/playlist/books')
    availableBooks.value = res.data
    // 默认展开第一个分组
    if (availableBooks.value.length > 0) {
      expandedGroups.value = [availableBooks.value[0].group_id]
    }
  } catch (error) {
    console.error('加载书籍列表失败:', error)
    showErrorDialog('加载书籍列表失败')
  }
}

const toggleGroup = (groupId: number) => {
  const index = expandedGroups.value.indexOf(groupId)
  if (index === -1) {
    expandedGroups.value.push(groupId)
  } else {
    expandedGroups.value.splice(index, 1)
  }
}

const isGroupSelected = (group: BookGroup) => {
  const groupBookIds = group.books.map(b => b.id)
  return groupBookIds.every(id => selectedBookIds.value.includes(id))
}

const toggleSelectGroup = (group: BookGroup) => {
  const groupBookIds = group.books.map(b => b.id)
  const allSelected = isGroupSelected(group)

  if (allSelected) {
    // 取消全选
    selectedBookIds.value = selectedBookIds.value.filter(
      id => !groupBookIds.includes(id)
    )
  } else {
    // 全选
    const newIds = groupBookIds.filter(id => !selectedBookIds.value.includes(id))
    selectedBookIds.value.push(...newIds)
  }
}

const toggleBookSelection = (bookId: string) => {
  const index = selectedBookIds.value.indexOf(bookId)
  if (index === -1) {
    selectedBookIds.value.push(bookId)
  } else {
    selectedBookIds.value.splice(index, 1)
  }
}

const addSelectedBooks = async () => {
  if (selectedBookIds.value.length === 0) return

  try {
    await api.post('/audiobook/playlist/books', {
      book_ids: selectedBookIds.value
    })
    showToast(`已添加 ${selectedBookIds.value.length} 本书籍`)
    selectedBookIds.value = []
    showAddBooks.value = false
    await loadPlaylist()
  } catch (error) {
    console.error('添加书籍失败:', error)
    showErrorDialog('添加失败')
  }
}

// 音频事件处理（响应 player 的 ended 事件 → 整本书 playlist 播完）
const handleAudioEnded = () => {
  // 重置本书内局部索引
  currentTime.value = 0
  duration.value = 0
  currentAudioIndex.value = 0
  currentSegmentIndex.value = 0
  currentSegmentRepeat.value = 0
  currentGlobalMs.value = 0

  // 按集数定时：播完整本书算一集
  if (sleepTimerType.value === 'episode' && episodesToPlay.value > 0) {
    episodesToPlay.value--
    if (episodesToPlay.value <= 0) {
      executeSleepTimer()
      return
    }
    nextBook()
    return
  }

  // 按时间定时 + 播完整集：到点后等本集结束再停
  if (sleepTimerType.value === 'time' && finishCurrentEnabled.value && sleepTimerInterval.value === null) {
    executeSleepTimer()
    return
  }

  // 本书播完：单曲循环 → 重播本书；否则下一本
  if (playlist.value.play_mode === 'single') {
    // 本书已播到末尾，player.currentIndex 停在最后一个 track
    // 必须先 seekToTrack(0, 0) 回到头部再 play()，否则 audio.play() 将从 duration 处启动会立即再次 ended
    void (async () => {
      try {
        await player.seekToTrack(0, 0)
        await player.play()
      } catch (e) {
        console.error('单曲循环重播失败:', e)
      }
    })()
  } else {
    nextBook()
  }
}

// 已在文件顶部声明了 isSwitchingBook（用于 prev/next/playBookAtIndex 切书时屏蔽 error toast）

// 拖动开始 - 进入拖动状态，初始化拖动位置
// 拖动期间允许 player 继续播放，由 progress 事件的 isDragging 分支避免覆盖 seekProgressTime
const onSeekStart = () => {
  if (isDragging.value) return
  isDragging.value = true
  seekProgressTime.value = bookProgressTime.value
}

// 滑块值更新时触发（拖动过程中或点击轨道时）
const onSliderUpdate = (value: number) => {
  if (!isDragging.value) {
    isDragging.value = true
    seekProgressTime.value = bookProgressTime.value
  }
  seekProgressTime.value = value
}

// 根据书籍进度时间跳转到对应位置
// 由 PlaylistPlayer 内部统一按全局毫秒时间轴定位，自动跨 track 定位
const seekToBookPosition = async (targetTime: number) => {
  if (!currentBookAudioList.value.length) return
  const safeTime = Math.max(0, targetTime)
  const totalMs = player.getTotalDurationMs()
  const targetMs = totalMs > 0 ? Math.min(Math.round(safeTime * 1000), totalMs) : Math.round(safeTime * 1000)
  currentGlobalMs.value = targetMs
  try {
    await player.seekGlobal(targetMs)
  } catch (err) {
    console.error('seek 失败:', err)
  }
}

// 拖动结束 - 更新播放位置
const onSeekEnd = () => {
  if (!isDragging.value) return
  seekToBookPosition(seekProgressTime.value)
  isDragging.value = false
}

// 滑块值变化后触发（点击轨道或拖动结束时）
// 注意：change 事件在 drag-end 之后触发，也在点击轨道时触发
const onSliderChange = (_value: number) => {
  if (isDragging.value) {
    // 拖动结束，执行跳转
    seekToBookPosition(seekProgressTime.value)
    isDragging.value = false
  }
  // 如果 isDragging 已经是 false，说明已经由其他方式处理过了
}

// 监听当前书籍变化，自动加载音频列表
watch(currentBook, async (newBook: PlaylistItem | null) => {
  if (newBook) {
    await loadBookAudioInfo(newBook.book_id)
  } else {
    currentBookAudioList.value = []
    totalAudioFiles.value = 0
  }
})

// 生命周期
onMounted(() => {
  checkOrientation()
  window.addEventListener('resize', checkOrientation)
  setupMediaSession()

  // === 调试信息：排查 Capacitor Android 安全区域问题 ===
  debugLayout('mounted')
  window.addEventListener('resize', () => debugLayout('resize'))
  // ==================================================

  // 绑定 PlaylistPlayer 事件
  player.on('progress', ({ globalMs }) => {
    if (!isDragging.value) currentGlobalMs.value = globalMs
  })
  player.on('timelineupdate', ({ totalMs }) => {
    currentBookTotalDuration.value = Math.max(0, totalMs / 1000)
  })
  player.on('trackchange', ({ index }) => {
    // 保留 currentAudioIndex 跟随底层 track 变化（仅在非双语模式下高度一致，双语模式下有序推进也合理）
    currentAudioIndex.value = Math.max(0, index)
  })
  player.on('ended', ({ completed }) => {
    if (completed) handleAudioEnded()
  })
  player.on('state', (state) => {
    if (state === 'playing') isPlaying.value = true
    else if (state === 'paused' || state === 'stopped') isPlaying.value = false
  })
  player.on('error', ({ message }) => {
    if (isSwitchingBook.value) return
    console.error('播放器错误:', message)
    showErrorDialog('音频加载失败: ' + (message || '未知错误'))
    isPlaying.value = false
  })
  // 先恢复用户双语配置（仅读 localStorage + 改 ref，此时 currentBookAudioList 为空，watch 被守卫拦住），
  // 再加载播放列表 → loadBookAudioInfo 里的 rebuildTracksForCurrentBook 将从第一次就用正确配置，避免重复 rebuild
  loadSavedReadConfig()
  loadPlaylist()
  loadAvailableBooks()
})

// MediaSession API：在 Android Capacitor WebView 中提供锁屏/通知栏控件
function setupMediaSession() {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return
  try {
    const mediaSession = (navigator as any).mediaSession
    mediaSession.setActionHandler('play', () => {
      if (!isPlaying.value) togglePlay()
    })
    mediaSession.setActionHandler('pause', () => {
      if (isPlaying.value) togglePlay()
    })
    mediaSession.setActionHandler('previoustrack', () => { prevBook() })
    mediaSession.setActionHandler('nexttrack', () => { nextBook() })
  } catch (e) {
    // 不支持时静默忽略
  }
}

// 更新锁屏/通知栏展示的元数据
function updateMediaMetadata() {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return
  const MediaMetadataCtor = (window as any).MediaMetadata
  if (!MediaMetadataCtor) return
  const book = currentBook.value
  if (!book) return
  try {
    const cover = book.book_cover ? buildStaticUrl(book.book_cover) : ''
    ;(navigator as any).mediaSession.metadata = new MediaMetadataCtor({
      title: book.book_title || '',
      artist: 'EnglishReadVoyage',
      album: book.book_title || '',
      artwork: cover ? [{ src: cover, sizes: '512x512', type: 'image/jpeg' }] : []
    })
  } catch (e) {
    // 忽略
  }
}

// 当当前书籍变化时同步元数据
watch(currentBook, () => {
  updateMediaMetadata()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkOrientation)
  clearSleepTimer()
  // 清理 MediaSession 全局 handler，避免组件卸载后锁屏键还能回调到旧实例
  if (typeof navigator !== 'undefined' && 'mediaSession' in navigator) {
    try {
      const ms: any = (navigator as any).mediaSession
      ;['play', 'pause', 'previoustrack', 'nexttrack', 'seekto', 'seekbackward', 'seekforward'].forEach(action => {
        try { ms.setActionHandler(action, null) } catch { /* 部分 action 不支持时忽略 */ }
      })
      try { ms.metadata = null } catch { /* ignore */ }
    } catch { /* ignore */ }
  }
  try {
    player.destroy()
  } catch (e) {
    // 忽略
  }
})
</script>

<style scoped lang="less">
.audiobook-player {
  /* 使用 svh (Small Viewport Height) 确保在移动端正确处理地址栏 */
  height: 100svh;
  /* 回退到 dvh 和 vh */
  height: 100dvh;
  height: 100vh;
  background: linear-gradient(180deg, #f5f5f5 0%, #fff 100%);
  overflow: hidden;
  /* 确保在原生壳中精确定位 */
  position: relative;

  // 新布局：左右分栏
  .player-layout {
    display: flex;
    height: 100%;
  }

  // 左侧区域：导航 + 封面 + 控制
  .left-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    overflow: hidden;
  }

  // 自定义导航栏
  .player-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: #fff;
    border-bottom: 1px solid #eee;
    flex-shrink: 0;

    .nav-left {
      width: 36px;
      height: 36px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;

      .fas {
        font-size: 20px;
        color: #333;
      }
    }

    .nav-title {
      font-size: 17px;
      font-weight: 600;
      color: #333;
    }

    .nav-right {
      display: flex;
      gap: 8px;
    }
  }

  .nav-icon-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.05);
    cursor: pointer;
    transition: background 0.2s;

    &:active {
      background: rgba(0, 0, 0, 0.1);
    }

    .fas {
      font-size: 18px;
      color: #333;
    }
  }

  // 播放列表切换按钮：宽屏时隐藏（因为右侧已经显示播放列表）
  .playlist-toggle-btn {
    display: none;
  }

  // 右侧播放列表区域
  .playlist-section {
    width: 33.333%;
    max-width: 360px;
    border-left: 1px solid #eee;
    display: flex;
    flex-direction: column;
    background: #fff;
    overflow: hidden;
  }
}

.book-cover-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px 16px;
  overflow-y: auto; // 允许垂直滚动
  min-height: 0;

  .cover-container {
    width: min(240px, 50vw);
    height: min(336px, 70vw);
    max-height: 35vh; // 减小最大高度，避免占用过多空间
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    background: #fff;

    .book-cover {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .book-cover-placeholder {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f0f0f0;

      .fas {
        font-size: 64px;
        color: #ccc;
      }
    }
  }

  .book-title {
    margin-top: 12px;
    font-size: clamp(16px, 5vw, 20px); /* 响应式字体 */
    font-weight: 600;
    color: #333;
    text-align: center;
    max-width: 80%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .timer-status {
    margin-top: 8px;
    font-size: 13px;
    color: #07c160;
    display: flex;
    align-items: center;
    gap: 4px;

    .fas {
      font-size: 14px;
    }
  }

  .read-mode-display {
    margin-top: 12px;
    font-size: 13px;
    color: #1989fa;
    display: flex;
    align-items: center;
    gap: 4px;

    .fas {
      font-size: 14px;
    }
  }

  // 状态信息行：水平排列
  .status-info-row {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 12px;
    margin-top: 8px;
    flex-wrap: wrap; // 允许在小屏幕上换行

    .timer-status,
    .read-mode-display {
      margin: 0;
    }
  }
}

// 播放控制区
.player-controls {
  padding: 12px 16px 16px; // 减小 padding
  background: #fff;
  border-top: 1px solid #eee;
  flex-shrink: 0;

  // 书籍整体进度
  .book-progress-section {
    margin-bottom: 12px;
    padding: 8px 0;
    background: transparent;
    border-radius: 0;

    .book-progress-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;

      .book-progress-label {
        font-size: 13px;
        color: #666;
      }

      .book-progress-value {
        font-size: 13px;
        font-weight: 600;
        color: #07c160;
      }
    }

    .book-progress-time {
      font-size: 11px;
      color: #999;
      text-align: right;
    }

    // 音频进度条容器
    .audio-progress-wrapper {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;

      .audio-time {
        font-size: 11px;
        color: #666;
        min-width: 40px;
        font-variant-numeric: tabular-nums;

        &.current {
          text-align: left;
        }

        &.total {
          text-align: right;
        }
      }

      .van-slider {
        flex: 1;

        .slider-button {
          width: 14px;
          height: 14px;
          border-radius: 50%;
          background: #07c160;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }
      }
    }
  }

  .control-buttons {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: clamp(20px, 6vw, 32px);

    .control-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: opacity 0.2s;

      &:active {
        opacity: 0.7;
      }

      .fas {
        font-size: 28px;
        color: #333;
      }

      &.play-btn .fas {
        font-size: 56px;
        color: #07c160;
      }

      &.active .fas {
        color: #1989fa;
      }
    }
  }
}

// 定时关闭弹窗
.sleep-timer-popup {
  padding: 16px;

  .popup-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;

    .close-icon {
      font-size: 20px;
      color: #999;
      cursor: pointer;
      padding: 4px;
    }
  }

  .last-timer-section {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0;
    border-bottom: 1px solid #eee;
    margin-bottom: 20px;

    .last-timer-label {
      font-size: 16px;
      font-weight: 500;
      color: #333;
    }
  }

  .timer-section {
    margin-bottom: 24px;

    .section-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }

    .section-title {
      font-size: 15px;
      font-weight: 500;
      color: #333;
    }

    .finish-current-option {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      font-size: 13px;
      color: #999;

      .check-icon {
        font-size: 16px;

        &.checked {
          color: #07c160;
        }
      }

      span.checked {
        color: #07c160;
      }

      &:active {
        opacity: 0.7;
      }
    }
  }

  .timer-options {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;

    .timer-option {
      padding: 10px 16px;
      text-align: center;
      border: 1px solid #e0e0e0;
      border-radius: 20px;
      cursor: pointer;
      transition: all 0.2s;
      font-size: 14px;
      color: #333;
      background: #fff;

      &:active {
        background: #f5f5f5;
      }

      &.active {
        background: #fff;
        color: #07c160;
        border-color: #07c160;
      }
    }
  }

  .time-options {
    .timer-option {
      min-width: 56px;
    }
  }

  .episode-options {
    .timer-option {
      flex: 1;
      min-width: 70px;
    }
  }
}

// 自定义时间选择弹窗
.custom-timer-popup {
  padding: 16px;

  .popup-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;

    .close-icon {
      font-size: 20px;
      color: #999;
      cursor: pointer;
      padding: 4px;
    }
  }

  .custom-timer-inputs {
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    gap: 20px;

    .timer-input-item {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .input-label {
        font-size: 16px;
        color: #333;
        font-weight: 500;
      }

      .van-stepper {
        .van-stepper__input {
          width: 60px;
          font-size: 16px;
        }
      }
    }
  }

  .custom-timer-actions {
    display: flex;
    gap: 12px;
    padding: 0 4px 8px;

    .cancel-btn {
      flex: 1;
      height: 44px;
      border-radius: 8px;
      font-size: 15px;
    }

    .confirm-btn {
      flex: 1;
      height: 44px;
      border-radius: 8px;
      font-size: 15px;
      background: #ee0a24;
      border-color: #ee0a24;
    }
  }
}

// 音频完整性检查弹窗
.audio-check-popup {
  .check-title {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-size: 17px;
    font-weight: 600;
    color: #333;
    margin-bottom: 20px;

    .warning-icon {
      font-size: 24px;
      color: #fa8c16;
    }
  }

  .check-progress {
    margin-bottom: 20px;

    .check-progress-text {
      text-align: center;
      font-size: 13px;
      color: #666;
      margin-top: 12px;
    }
  }

  .check-result {
    margin-bottom: 20px;

    .result-summary {
      display: flex;
      justify-content: space-around;
      padding: 16px;
      background: #f5f5f5;
      border-radius: 8px;
      margin-bottom: 16px;

      .result-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;

        .label {
          font-size: 13px;
          color: #666;
        }

        .value {
          font-size: 18px;
          font-weight: 600;

          &.success {
            color: #07c160;
          }

          &.warning {
            color: #fa8c16;
          }
        }
      }
    }

    .incomplete-list {
      max-height: 200px;
      overflow-y: auto;

      .incomplete-title {
        font-size: 13px;
        color: #666;
        margin-bottom: 12px;
      }

      .incomplete-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        background: #fff7e6;
        border-radius: 6px;
        margin-bottom: 8px;

        .book-name {
          font-size: 14px;
          color: #333;
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .missing-info {
          display: flex;
          gap: 6px;
          flex-shrink: 0;
        }

        .missing-badge {
          font-size: 12px;
          padding: 2px 6px;
          border-radius: 4px;

          &.en {
            background: #e6f7ff;
            color: #1890ff;
          }

          &.zh {
            background: #fff7e6;
            color: #fa8c16;
          }
        }
      }
    }
  }

  .check-actions {
    .van-button {
      width: 100%;
    }
  }
}

// 添加书籍弹窗
.add-books-popup {
  display: flex;
  flex-direction: column;
  height: 100%;

  .popup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid #eee;
    font-weight: 600;
  }

  .books-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .book-group {
    margin-bottom: 12px;

    .group-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px;
      background: #f5f5f5;
      border-radius: 8px;
      cursor: pointer;

      .group-name {
        flex: 1;
        font-weight: 600;
      }
    }

    .group-books {
      padding: 8px;

      .book-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px;
        cursor: pointer;
        border-radius: 4px;
        transition: background 0.2s;

        &:hover {
          background: #f5f5f5;
        }

        &:active {
          background: #e8e8e8;
        }

        .book-thumb,
        .book-thumb-placeholder {
          width: 40px;
          height: 56px;
          border-radius: 4px;
          object-fit: cover;
        }

        .book-thumb-placeholder {
          display: flex;
          align-items: center;
          justify-content: center;
          background: #f0f0f0;

          .fas {
            font-size: 20px;
            color: #ccc;
          }
        }

        .book-name {
          flex: 1;
          font-size: 14px;
          color: #333;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }
  }

  .empty-books-list {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    color: #999;

    p {
      margin-top: 16px;
    }
  }
}

// 横屏模式优化
.audiobook-player.landscape {
  .book-cover-section {
    padding: 12px 20px;

    .cover-container {
      width: min(180px, 35vh);
      height: min(252px, 49vh);
      max-height: 40vh;
    }

    .book-title {
      margin-top: 8px;
      font-size: clamp(14px, 3vh, 18px);
    }

    // 状态信息行：横屏模式下水平排列
    .status-info-row {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 16px;
      margin-top: 8px;

      .timer-status,
      .read-mode-display {
        margin: 0;
      }
    }
  }

  .player-controls {
    padding: 12px 20px 16px;

    .book-progress-section {
      margin-bottom: 12px;
      padding: 8px 0;
    }
  }
}

// 竖屏模式适配（基于宽高比判断，不是固定宽度）
.audiobook-player:not(.landscape) {
  .player-layout {
    flex-direction: column;
  }

  .playlist-section {
    display: none; // 竖屏隐藏右侧播放列表，使用抽屉
  }

  // 竖屏显示播放列表切换按钮
  .playlist-toggle-btn {
    display: flex;
  }

  .book-cover-section {
    .cover-container {
      width: min(160px, 50vw);
      height: min(224px, 70vw);
      max-height: 28vh; // 小屏幕上进一步减小封面高度
    }

    .book-title {
      margin-top: 6px; // 进一步减小间距
      font-size: clamp(14px, 4vw, 18px); // 减小字体
    }

    .status-info-row {
      margin-top: 6px;
      gap: 8px; // 减小状态信息间距

      .timer-status,
      .read-mode-display {
        font-size: 12px; // 减小字体
      }
    }
  }

  // 竖屏模式下减小控制按钮大小
  .player-controls {
    padding: 10px 12px 12px;

    .book-progress-section {
      margin-bottom: 10px;
      padding: 6px 0;

      .book-progress-info {
        margin-bottom: 6px;
      }
    }

    .control-buttons {
      gap: clamp(16px, 5vw, 24px);

      .control-btn {
        .fas {
          font-size: 24px; // 减小普通按钮图标
        }

        &.play-btn .fas {
          font-size: 48px; // 减小播放按钮图标
        }
      }
    }
  }
}
</style>
