<template>
  <div class="audiobook-player" :class="{ 'landscape': isLandscape }">
    <!-- 主内容区 - 新布局：左侧播放器 + 右侧播放列表 -->
    <div class="player-layout">
      <!-- 左侧区域：导航栏 + 封面 + 控制按钮 -->
      <div class="left-section">
        <!-- 顶部导航 -->
        <div class="player-nav">
          <div class="nav-left" @click="goBack">
            <van-icon name="arrow-left" />
          </div>
          <div class="nav-title">听书模式</div>
          <div class="nav-right">
            <div class="nav-icon-btn playlist-toggle-btn" @click="showPlaylist = true">
              <van-icon name="list-switch" />
            </div>
            <div class="nav-icon-btn" @click="showAddBooks = true">
              <van-icon name="plus" />
            </div>
          </div>
        </div>

        <!-- 书籍封面区域 -->
        <div class="book-cover-section">
          <div class="cover-container">
            <img
              v-if="currentBook?.book_cover"
              :src="currentBook.book_cover"
              class="book-cover"
              alt="书籍封面"
            />
            <div v-else class="book-cover-placeholder">
              <van-icon name="book-o" />
            </div>
          </div>
          <h2 class="book-title">{{ currentBook?.book_title || '暂无书籍' }}</h2>
          <!-- 定时器状态显示 -->
          <p v-if="sleepTimer && sleepTimerType" class="timer-status">
            <van-icon name="clock-o" />
            <span v-if="sleepTimerType === 'time'">
              {{ sleepTimerRemaining > 0 ? sleepTimerRemainingLabel + '后关闭' : sleepTimer + '分钟后关闭' }}
            </span>
            <span v-else-if="sleepTimerType === 'episode'">还剩{{ episodesToPlay }}集</span>
          </p>
        </div>

        <!-- 播放控制区 -->
        <div class="player-controls">
          <!-- 书籍整体进度 -->
          <div v-if="currentBookTotalDuration > 0" class="book-progress-section">
            <div class="book-progress-info">
              <span class="book-progress-label">书籍进度</span>
              <span class="book-progress-value">{{ bookProgressPercent }}%</span>
            </div>
            <div class="book-progress-bar">
              <div class="book-progress-fill" :style="{ width: bookProgressPercent + '%' }"></div>
            </div>
            <div class="book-progress-time">
              {{ formatTime(bookProgressTime) }} / {{ formatTime(currentBookTotalDuration) }}
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
          <van-icon name="cross" class="close-icon" @click="showSleepTimer = false" />
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
              <van-icon :name="finishCurrentEnabled ? 'checked' : 'circle'" :class="['check-icon', { 'checked': finishCurrentEnabled }]" />
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
          <van-icon name="cross" class="close-icon" @click="showCustomTimer = false" />
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
              <van-icon :name="expandedGroups.includes(group.group_id) ? 'arrow-down' : 'arrow'" />
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
                  :src="book.cover_path"
                  class="book-thumb"
                />
                <div v-else class="book-thumb-placeholder">
                  <van-icon name="book-o" />
                </div>
                <span class="book-name">{{ book.title }}</span>
              </div>
            </div>
          </div>
          <div v-if="filteredAvailableBooks.length === 0" class="empty-books-list">
            <van-icon name="success" size="48" color="#07c160" />
            <p>所有书籍都已添加到播放列表</p>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 音频元素 -->
    <audio
      ref="audioPlayer"
      @ended="handleAudioEnded"
      @error="handleAudioError"
      @timeupdate="handleTimeUpdate"
    ></audio>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  showToast,
  showConfirmDialog,
  showNotify
} from 'vant'
import { api } from '@/store/auth'
import Playlist from '@/components/Playlist.vue'

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

// 音频播放器引用
const audioPlayer = ref<HTMLAudioElement | null>(null)

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
  audio_url: string
  duration: number
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

// 当前书籍整体进度（已播放音频时长 + 当前音频进度）
const bookProgressTime = computed(() => {
  let played = 0
  // 累加已播放完的音频时长
  for (let i = 0; i < currentAudioIndex.value; i++) {
    played += currentBookAudioList.value[i]?.duration || 0
  }
  // 加上当前音频的进度
  played += currentTime.value
  return played
})

// 当前书籍整体进度百分比
const bookProgressPercent = computed(() => {
  if (currentBookTotalDuration.value <= 0) return 0
  return Math.min(100, Math.round((bookProgressTime.value / currentBookTotalDuration.value) * 100))
})


// 方法
const checkOrientation = () => {
  isLandscape.value = window.innerWidth > window.innerHeight
}

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
    showNotify({ type: 'danger', message: '加载播放列表失败' })
  }
}

// 当前书籍的音频列表
const currentBookAudioList = ref<AudioInfo[]>([])
const currentBookTotalDuration = ref(0) // 当前书籍总时长（秒）

// 播放进度
const currentTime = ref(0) // 当前播放时间（秒）
const duration = ref(0) // 当前音频总时长（秒）
const isDragging = ref(false) // 是否正在拖动进度条

// 加载书籍音频信息
const loadBookAudioInfo = async (bookId: string) => {
  try {
    const res = await api.get(`/audiobook/books/${bookId}/audio`)
    currentBookAudioList.value = res.data.audio_list
    totalAudioFiles.value = res.data.total
    currentBookTotalDuration.value = res.data.total_duration || 0
    currentAudioIndex.value = 0
    currentTime.value = 0
    duration.value = 0
  } catch (error) {
    console.error('加载音频信息失败:', error)
    currentBookAudioList.value = []
    totalAudioFiles.value = 0
    currentBookTotalDuration.value = 0
    currentTime.value = 0
    duration.value = 0
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
    await playAudio()
  }
}

const playAudio = async () => {
  if (!audioPlayer.value || !currentBook.value) return

  // 检查是否有音频文件
  if (currentBookAudioList.value.length === 0) {
    showToast('该书籍暂无音频文件')
    return
  }

  try {
    // 获取当前音频URL并播放
    const audioInfo = currentBookAudioList.value[currentAudioIndex.value]
    if (audioInfo) {
      audioPlayer.value.src = audioInfo.audio_url
      await audioPlayer.value.play()
      isPlaying.value = true
    }
  } catch (error) {
    console.error('播放失败:', error)
    showNotify({ type: 'danger', message: '播放失败' })
  }
}

const pauseAudio = () => {
  if (audioPlayer.value) {
    audioPlayer.value.pause()
    isPlaying.value = false
  }
}

// 切换书籍
const prevBook = async () => {
  try {
    const res = await api.get('/audiobook/playlist/next?direction=prev')
    if (res.data.has_next) {
      // 记录当前播放状态
      const wasPlaying = isPlaying.value
      // 标记正在切换书籍，避免显示错误提示
      isSwitchingBook.value = true
      // 先停止当前播放
      if (audioPlayer.value) {
        audioPlayer.value.pause()
        audioPlayer.value.src = ''
      }
      isPlaying.value = false

      currentBookIndex.value = res.data.index
      currentAudioIndex.value = 0

      // 如果之前在播放，加载新书籍音频后继续播放
      if (wasPlaying) {
        await loadBookAudioInfo(res.data.book_id)
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
    const res = await api.get('/audiobook/playlist/next?direction=next')
    if (res.data.has_next) {
      // 记录当前播放状态
      const wasPlaying = isPlaying.value
      // 标记正在切换书籍，避免显示错误提示
      isSwitchingBook.value = true
      // 先停止当前播放
      if (audioPlayer.value) {
        audioPlayer.value.pause()
        audioPlayer.value.src = ''
      }
      isPlaying.value = false

      currentBookIndex.value = res.data.index
      currentAudioIndex.value = 0

      // 如果之前在播放，加载新书籍音频后继续播放
      if (wasPlaying) {
        await loadBookAudioInfo(res.data.book_id)
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

  const bookId = playlist.value.items[index].book_id

  // 记录当前播放状态
  const wasPlaying = isPlaying.value
  // 标记正在切换书籍，避免显示错误提示
  isSwitchingBook.value = true
  // 先停止当前播放
  if (audioPlayer.value) {
    audioPlayer.value.pause()
    audioPlayer.value.src = ''
  }
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

  // 如果之前在播放，加载新书籍音频后继续播放
  if (wasPlaying) {
    await loadBookAudioInfo(bookId)
    await playAudio()
  }
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
    showNotify({ type: 'danger', message: '设置失败' })
  }
}

// 睡眠定时器
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
      showNotify({ type: 'danger', message: '清空失败' })
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
    showNotify({ type: 'danger', message: '移除失败' })
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
    showNotify({ type: 'danger', message: '加载书籍列表失败' })
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
    showNotify({ type: 'danger', message: '添加失败' })
  }
}

// 音频事件处理
const handleAudioEnded = () => {
  // 重置当前音频进度
  currentTime.value = 0
  duration.value = 0

  // 检查按集数定时 - 播完整本书籍才算一集
  if (sleepTimerType.value === 'episode' && episodesToPlay.value > 0) {
    // 如果当前书籍还有未播放的音频，继续播放
    if (currentAudioIndex.value < currentBookAudioList.value.length - 1) {
      currentAudioIndex.value++
      playAudio()
      return
    }
    // 当前书籍播放完毕，集数减一
    episodesToPlay.value--
    if (episodesToPlay.value <= 0) {
      executeSleepTimer()
      return
    }
    // 还有剩余集数，切换到下一本书继续播放
    nextBook()
    return
  }

  // 检查按时间定时 + 播完整集选项
  if (sleepTimerType.value === 'time' && finishCurrentEnabled.value && sleepTimerInterval.value === null) {
    // 定时时间已到，且播完整集选项开启，现在停止
    executeSleepTimer()
    return
  }

  // 当前音频播放完毕，播放下一个音频或书籍
  if (currentAudioIndex.value < currentBookAudioList.value.length - 1) {
    currentAudioIndex.value++
    playAudio()
  } else {
    // 当前书籍的所有音频播放完毕，切换到下一本书
    nextBook()
  }
}

// 标记是否正在切换书籍（用于避免显示切换时的错误提示）
const isSwitchingBook = ref(false)

const handleAudioError = (e: Event) => {
  // 如果正在切换书籍，不显示错误（src被重置会触发error）
  if (isSwitchingBook.value) {
    return
  }
  // 检查是否真的加载失败（有src且不是当前页面URL）
  const target = e.target as HTMLAudioElement
  if (target.src && !target.src.includes(window.location.host)) {
    showNotify({ type: 'danger', message: '音频加载失败' })
    isPlaying.value = false
  }
}

const handleTimeUpdate = () => {
  if (audioPlayer.value && !isDragging.value) {
    currentTime.value = audioPlayer.value.currentTime || 0
    duration.value = audioPlayer.value.duration || 0
  }
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
  loadPlaylist()
  loadAvailableBooks()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkOrientation)
  clearSleepTimer()
  pauseAudio()
})
</script>

<style scoped lang="less">
.audiobook-player {
  height: 100vh;
  height: 100dvh;
  background: linear-gradient(180deg, #f5f5f5 0%, #fff 100%);
  overflow: hidden;

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

      .van-icon {
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

    .van-icon {
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
  padding: 20px;
  overflow-y: auto;
  min-height: 0;

  .cover-container {
    width: min(240px, 50vw);
    height: min(336px, 70vw);
    max-height: 50vh;
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

      .van-icon {
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

    .van-icon {
      font-size: 14px;
    }
  }
}

// 播放控制区
.player-controls {
  padding: 16px 20px 24px;
  background: #fff;
  border-top: 1px solid #eee;
  flex-shrink: 0;

  // 书籍整体进度
  .book-progress-section {
    margin-bottom: 16px;
    padding: 12px 0;
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

    .book-progress-bar {
      height: 4px;
      background: #e0e0e0;
      border-radius: 2px;
      overflow: hidden;
      margin-bottom: 6px;

      .book-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #07c160, #10b981);
        border-radius: 2px;
        transition: width 0.3s ease;
      }
    }

    .book-progress-time {
      font-size: 11px;
      color: #999;
      text-align: right;
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

          .van-icon {
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

// 移动端适配（窄屏幕）
@media (max-width: 768px) {
  .audiobook-player {
    .player-layout {
      flex-direction: column;
    }

    .playlist-section {
      display: none; // 移动端隐藏右侧播放列表，使用抽屉
    }

    // 移动端显示播放列表切换按钮
    .playlist-toggle-btn {
      display: flex;
    }

    .book-cover-section {
      .cover-container {
        width: min(200px, 60vw);
        height: min(280px, 84vw);
      }
    }
  }
}
</style>
