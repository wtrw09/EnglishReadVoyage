<template>
  <van-popup
    v-model:show="show"
    position="right"
    :style="{ width: '100%', height: '100%' }"
    :close-on-click-overlay="false"
    teleport="body"
  >
    <div class="edit-dialog-content">
      <div class="edit-header">
        <van-button size="small" :disabled="loading" @click="handleClose">关闭</van-button>
        <span class="edit-title">{{ title }}</span>
        <van-button size="small" type="warning" :loading="generatingAudio" @click="handleGenerateAudio">
          {{ generatingAudio ? '生成中...' : '生成语音' }}
        </van-button>
        <van-button size="small" type="primary" :loading="saving" @click="handleSave">保存</van-button>
      </div>
      <!-- 生成音频进度显示 -->
      <div v-if="generatingAudio" class="audio-progress">
        <van-progress :percentage="audioProgress" :stroke-width="6" :show-pivot="true" />
        <span class="progress-msg">{{ audioProgressMsg }}</span>
      </div>
      <div class="edit-body">
        <BookEditor
          v-model="content"
          @save="handleSave"
        />
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { showNotify } from 'vant'
import { api, useAuthStore } from '@/store/auth'
import BookEditor from './BookEditor.vue'

const authStore = useAuthStore()

interface Props {
  modelValue: boolean
  bookId: string
  title: string
  initialContent: string
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const show = ref(props.modelValue)
const content = ref(props.initialContent)
const saving = ref(false)
const generatingAudio = ref(false)
const audioProgress = ref(0)
const audioProgressMsg = ref('')

// 监听modelValue变化
watch(() => props.modelValue, (val) => {
  show.value = val
  if (val) {
    content.value = props.initialContent
  }
})

// 监听show变化
watch(show, (val) => {
  emit('update:modelValue', val)
})

// 监听initialContent变化
watch(() => props.initialContent, (val) => {
  if (props.modelValue) {
    content.value = val
  }
})

const loading = ref(false)

// 关闭
const handleClose = () => {
  show.value = false
}

// 保存
const handleSave = async () => {
  if (!props.bookId) {
    showNotify({ type: 'danger', message: '书籍ID无效' })
    return
  }

  saving.value = true
  try {
    const res = await api.put<{ success: boolean; message: string }>(`/books/${props.bookId}`, {
      content: content.value
    })

    if (!res.data.success) {
      showNotify({ type: 'danger', message: res.data.message })
      saving.value = false
      return
    }
    showNotify({ type: 'success', message: '保存成功', duration: 1500 })
    saving.value = false
    emit('saved')
  } catch (error: any) {
    showNotify({ type: 'danger', message: '保存失败' })
    saving.value = false
  }
}

// 生成音频
const handleGenerateAudio = async () => {
  if (!props.bookId) {
    showNotify({ type: 'danger', message: '书籍ID无效' })
    return
  }

  // 先保存当前内容
  saving.value = true
  try {
    const res = await api.put<{ success: boolean; message: string }>(`/books/${props.bookId}`, {
      content: content.value
    })

    if (!res.data.success) {
      showNotify({ type: 'danger', message: res.data.message })
      saving.value = false
      return
    }
    showNotify({ type: 'success', message: '内容已保存', duration: 1500 })
  } catch (error: any) {
    showNotify({ type: 'danger', message: '保存失败' })
    saving.value = false
    return
  }
  saving.value = false

  // 然后生成音频
  generatingAudio.value = true
  audioProgress.value = 0
  audioProgressMsg.value = '开始生成...'
  let hasError = false
  let errorMessage = ''

  try {
    const response = await fetch(`/api/v1/books/${props.bookId}/regenerate-audio`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    if (!response.ok) {
      throw new Error(`生成请求失败: ${response.status} ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法读取响应流')
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const matches = text.matchAll(/data: (\{.*?\})/g)
      let hasValidData = false

      for (const match of matches) {
        try {
          const data = JSON.parse(match[1])
          hasValidData = true

          if (data.percentage !== undefined) {
            audioProgress.value = data.percentage
            audioProgressMsg.value = data.message || ''
          }

          // 检测错误消息
          if (data.message && (
            data.message.includes('失败') ||
            data.message.includes('错误') ||
            data.message.includes('Error') ||
            data.message.includes('Failed')
          )) {
            hasError = true
            errorMessage = data.message
          }

          if (data.success === true) {
            showNotify({ type: 'success', message: data.message + '，请刷新页面后使用新语音', duration: 3000 })
          } else if (data.success === false) {
            hasError = true
            errorMessage = data.message
            showNotify({ type: 'danger', message: data.message })
          }
        } catch (e) {
          console.error('解析SSE数据失败:', e)
        }
      }

      // 如果没有解析到有效数据，可能是连接问题
      if (!hasValidData && text.trim()) {
        console.warn('收到无法解析的数据:', text)
      }
    }

    // 如果过程中检测到错误，显示最终错误提示
    if (hasError && errorMessage) {
      showNotify({ type: 'danger', message: `音频生成异常: ${errorMessage}` })
    }

  } catch (error: any) {
    console.error('生成音频失败:', error)
    hasError = true

    // 根据错误类型显示不同的错误消息
    if (error.message?.includes('fetch') || error.message?.includes('network') || error.name === 'TypeError') {
      errorMessage = '无法连接到服务器，请检查：\n1. 后端服务是否已启动\n2. TTS语音服务是否在线'
    } else {
      errorMessage = error.message || '生成音频失败'
    }

    showNotify({ type: 'danger', message: errorMessage })
  } finally {
    generatingAudio.value = false
    if (!hasError) {
      audioProgress.value = 0
      audioProgressMsg.value = ''
    } else {
      // 发生错误时保留进度条显示错误状态
      audioProgressMsg.value = errorMessage || '生成失败'
    }
  }
}
</script>

<style scoped>
.edit-dialog-content {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.edit-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-bottom: 1px solid #eee;
}

.edit-title {
  flex: 1;
  font-size: 16px;
  font-weight: bold;
  text-align: center;
}

.edit-body {
  flex: 1;
  overflow: auto;
}

.audio-progress {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.progress-msg {
  font-size: 12px;
  color: #666;
  text-align: center;
}
</style>
