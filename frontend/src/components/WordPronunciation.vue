/**
 * WordPronunciation.vue - 单词发音组件
 *
 * 功能：
 * - 使用有道词典API获取单词发音
 * - 支持英式/美式发音切换
 * - 根据用户设置的音标偏好自动选择
 * - 提供统一的单词发音播放接口
 */
<template>
  <div class="word-pronunciation">
    <van-loading v-if="loading" type="spinner" size="16px" class="pronunciation-loading" />
    <template v-else-if="audioUrl">
      <i
        class="fas fa-volume-up pronunciation-icon"
        :class="{ 'playing': isPlaying }"
        @click="playAudio"
      />
      <span v-if="showAccent" class="pronunciation-accent">{{ accentLabel }}</span>
    </template>
    <i v-else class="fas fa-volume-mute pronunciation-icon pronunciation-muted" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '@/store/auth'

interface Props {
  word: string
  accent?: 'uk' | 'us' | 'auto'  // 'auto' 表示使用用户设置
  size?: 'small' | 'normal' | 'large'
  showAccent?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  accent: 'auto',
  size: 'normal',
  showAccent: false
})

// 状态
const loading = ref(false)
const audioUrl = ref<string | null>(null)
const currentAccent = ref<'uk' | 'us'>('uk')
const isPlaying = ref(false)
const userAccent = ref<'uk' | 'us'>('uk')

// 计算属性
const accentLabel = computed(() => currentAccent.value === 'uk' ? '英' : '美')

// 获取用户音标偏好
const loadUserAccent = async () => {
  try {
    const res = await api.get<{ accent: 'uk' | 'us' }>('/settings/phonetic')
    if (res.data.accent) {
      userAccent.value = res.data.accent
    }
  } catch (error) {
    console.error('加载用户音标设置失败:', error)
  }
}

// 获取发音URL
const fetchPronunciation = async () => {
  if (!props.word) {
    audioUrl.value = null
    return
  }

  loading.value = true
  try {
    // 确定使用哪种口音
    const targetAccent = props.accent === 'auto' ? userAccent.value : props.accent
    currentAccent.value = targetAccent

    // 调用后端API获取发音
    const res = await api.get<{
      word: string
      audio_url: string | null
      accent: 'uk' | 'us' | null
    }>(`/pronunciation/${encodeURIComponent(props.word)}?accent=${targetAccent}`)

    if (res.data.audio_url) {
      audioUrl.value = res.data.audio_url
      if (res.data.accent) {
        currentAccent.value = res.data.accent
      }
    } else {
      audioUrl.value = null
    }
  } catch (error) {
    audioUrl.value = null
  } finally {
    loading.value = false
  }
}

// 播放音频
const playAudio = () => {
  if (!audioUrl.value) return
  const audio = new Audio(audioUrl.value)
  isPlaying.value = true

  audio.addEventListener('ended', () => {
    isPlaying.value = false
  })

  audio.addEventListener('error', (e) => {
    isPlaying.value = false
  })

  audio.play().catch(err => {
    isPlaying.value = false
  })
}

// 监听单词变化
watch(() => props.word, () => {
  fetchPronunciation()
}, { immediate: true })

// 监听口音变化
watch(() => props.accent, () => {
  fetchPronunciation()
})

onMounted(() => {
  loadUserAccent()
})

// 暴露方法供外部调用
defineExpose({
  playAudio,
  refresh: fetchPronunciation
})
</script>

<style scoped>
.word-pronunciation {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.pronunciation-loading {
  color: #1989fa;
}

.pronunciation-icon {
  font-size: 20px;
  color: #1989fa;
  cursor: pointer;
  padding: 4px;
  transition: all 0.2s;
}

.pronunciation-icon:hover {
  color: #0570db;
  transform: scale(1.1);
}

.pronunciation-icon.playing {
  animation: pulse 0.5s ease-in-out infinite;
}

.pronunciation-muted {
  color: #ccc;
  cursor: not-allowed;
}

.pronunciation-accent {
  font-size: 12px;
  color: #666;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.1);
  }
}
</style>
