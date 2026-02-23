<template>
  <div class="reader">
    <van-nav-bar
      :title="bookTitle"
      left-text="返回"
      left-arrow
      fixed
      placeholder
      @click-left="goBack"
    />
    
    <div v-if="loading" class="loading-box">
      <van-loading type="spinner" vertical>加载书籍中...</van-loading>
    </div>

    <van-swipe
      v-else
      ref="swipeRef"
      class="my-swipe"
      :loop="false"
      :show-indicators="true"
      @change="onPageChange"
    >
      <van-swipe-item v-for="(page, index) in pages" :key="index">
        <div :id="'page-' + index" class="page-content" v-html="page" @click="handleContentClick"></div>
      </van-swipe-item>
    </van-swipe>

    <!-- Control Bar -->
    <div class="control-bar van-hairline--top">
      <van-button
        icon="arrow-left"
        size="small"
        round
        :disabled="currentPage === 0"
        @click="prevPage"
      >上一页</van-button>

      <van-button
        :icon="isPlayingAll ? 'pause-circle-o' : 'play-circle-o'"
        type="primary"
        size="small"
        round
        plain
        @click="togglePlayAll"
      >
        {{ isPlayingAll ? '停止' : '全文朗读' }}
      </van-button>
      
      <div class="page-info pc-only">
        {{ currentPage + 1 }} / {{ pages.length }}
      </div>

      <van-button
        icon="arrow"
        icon-position="right"
        size="small"
        round
        :disabled="currentPage === pages.length - 1"
        @click="nextPage"
      >下一页</van-button>
    </div>

    <!-- Audio element for TTS -->
    <audio 
      ref="audioPlayer" 
      style="display: none" 
      @ended="handleAudioEnded"
      @error="handleAudioError"
    ></audio>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, type SwipeInstance } from 'vant'
import { api } from '@/store/auth'

interface BookData {
  title: string
  pages: string[]
}

interface TTSResponse {
  url: string
}

const route = useRoute()
const router = useRouter()
const bookId = route.params.id as string
const bookTitle = ref('')
const pages = ref<string[]>([])
const loading = ref(true)
const audioPlayer = ref<HTMLAudioElement | null>(null)
const currentSentence = ref<HTMLElement | null>(null)
const swipeRef = ref<SwipeInstance | null>(null)
const currentPage = ref(0)
const isPlayingAll = ref(false)

const goBack = () => {
  stopPlayAll()
  router.back()
}

const onPageChange = (index: number) => {
  currentPage.value = index
}

const prevPage = () => {
  swipeRef.value?.prev()
}

const nextPage = () => {
  swipeRef.value?.next()
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowLeft') {
    prevPage()
  } else if (e.key === 'ArrowRight') {
    nextPage()
  } else if (e.key === ' ') {
    e.preventDefault() // 防止滚动
    togglePlayAll()
  }
}

const loadBook = async () => {
  try {
    const res = await api.get<BookData>(`/books/${bookId}`)
    bookTitle.value = res.data.title
    pages.value = res.data.pages
    loading.value = false
  } catch (error) {
    showToast('加载失败')
    console.error(error)
  }
}

const playSentence = async (el: HTMLElement) => {
  const text = el.getAttribute('data-tts')
  if (!text) return

  // 高亮当前句子
  if (currentSentence.value) {
    currentSentence.value.classList.remove('active-sentence')
  }
  currentSentence.value = el
  el.classList.add('active-sentence')
  
  // 确保在视图中可见
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })

  try {
    const res = await api.get<TTSResponse>('/tts', { params: { text } })
    if (res.data.url && audioPlayer.value) {
      audioPlayer.value.src = res.data.url
      audioPlayer.value.play()
    }
  } catch (error) {
    console.error('TTS失败:', error)
    showToast('语音合成失败')
    if (isPlayingAll.value) stopPlayAll()
  }
}

const handleContentClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (target.classList.contains('tts-sentence')) {
    stopPlayAll()
    playSentence(target)
  }
}

const togglePlayAll = () => {
  if (isPlayingAll.value) {
    stopPlayAll()
  } else {
    isPlayingAll.value = true
    // 从当前页的第一句话开始
    const pageEl = document.getElementById(`page-${currentPage.value}`)
    const firstSentence = pageEl?.querySelector('.tts-sentence') as HTMLElement | null
    if (firstSentence) {
      playSentence(firstSentence)
    } else {
      showToast('当前页没有可朗读内容')
      isPlayingAll.value = false
    }
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
    // 查找当前页的下一句话
    const pageEl = document.getElementById(`page-${currentPage.value}`)
    const allSentences = Array.from(pageEl?.querySelectorAll('.tts-sentence') || []) as HTMLElement[]
    const currentIndex = allSentences.indexOf(currentSentence.value!)
    
    if (currentIndex !== -1 && currentIndex < allSentences.length - 1) {
      // 播放同一页的下一句话
      playSentence(allSentences[currentIndex + 1])
    } else {
      // 当前页已完成，尝试下一页
      if (currentPage.value < pages.value.length - 1) {
        swipeRef.value?.next()
        // 等待页面过渡并查找第一句话
        setTimeout(() => {
          const nextPageEl = document.getElementById(`page-${currentPage.value}`)
          const firstSentence = nextPageEl?.querySelector('.tts-sentence') as HTMLElement | null
          if (firstSentence) {
            playSentence(firstSentence)
          } else {
            stopPlayAll()
            showToast('阅读完成')
          }
        }, 500)
      } else {
        stopPlayAll()
        showToast('全部阅读完成')
      }
    }
  }
}

const handleAudioError = () => {
  console.error('音频播放错误')
  if (isPlayingAll.value) stopPlayAll()
}

onMounted(() => {
  loadBook()
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<style lang="less">
.reader {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.my-swipe {
  flex: 1;
  background: #fdfdfd;
}

.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background: #fff;
  z-index: 100;

  .page-info {
    font-size: 14px;
    color: #666;
  }
}

@media (max-width: 768px) {
  .pc-only {
    display: none;
  }
}

.page-content {
  height: 100%;
  padding: 12px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  font-size: 18px;
  line-height: 1.4;
  color: #333;
  
  /* 解决某些图片无法完整显示的问题：确保 flex 子项可以缩小 */
  min-height: 0;

  /* 隐藏滚动条 */
  scrollbar-width: none;
  &::-webkit-scrollbar { display: none; }

  .book-section {
    display: flex;
    flex-direction: column;
    margin-bottom: 12px;
    flex-shrink: 0;

    h1, h2, h3, h4, h5, h6 {
      text-align: center;
      margin: 5px 0 10px 0;
      width: 100%;
    }
  }

  .section-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
  }

  /* 响应式：横屏或宽屏 PC 时切换为左右结构 */
  @media (min-aspect-ratio: 1/1) or (min-width: 1024px) {
    .section-body {
      flex-direction: row;
      align-items: center;
      gap: 20px;
    }

    .text-wrapper {
      flex: 1;
      order: 1;
    }

    .image-wrapper {
      flex: 1.2;
      order: 2;
    }
  }

  /* 通用图片容器样式 */
  .image-wrapper, p:has(img) {
    display: flex;
    flex-direction: column; /* 如果有多张图，垂直排列 */
    justify-content: center;
    align-items: center;
    width: 100%;
    margin: 5px 0;
    min-height: 0;
    
    img {
      display: block;
      max-width: 100%;
      max-height: 70vh; /* 限制最大高度，但不强制裁剪 */
      width: auto;
      height: auto;
      object-fit: scale-down; /* 缩放而不拉伸，绝不裁剪 */
      border-radius: 6px;
      flex-shrink: 1; /* 允许图片在空间不足时缩小 */
    }
  }

  /* 文本容器：内部段落紧凑 */
  .text-wrapper {
    flex: 1;
    p, li {
      margin-bottom: 4px;
    }
  }

  p, h1, h2, h3, h4, h5, h6, li {
    flex-shrink: 0;
    margin-bottom: 0;
  }

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
</style>
