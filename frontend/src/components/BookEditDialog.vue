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
        <div class="header-actions">
          <van-popover
            v-model:show="showAudioPopover"
            placement="bottom-end"
            :actions="audioActions"
            :disabled="generatingAudio"
            @select="handleAudioSelect"
          >
            <template #reference>
              <van-button
                size="small"
                type="warning"
                :loading="generatingAudio"
              >
                {{ generatingAudio ? '生成中...' : '生成语音' }}
              </van-button>
            </template>
          </van-popover>
          <van-button size="small" type="primary" :disabled="saving || !isModified" :loading="saving" @click="handleSave">保存</van-button>
        </div>
      </div>
      <!-- 生成音频进度显示 -->
      <div v-if="generatingAudio" class="audio-progress">
        <van-progress :percentage="audioProgress" :stroke-width="6" :show-pivot="true" />
        <div class="progress-info">
          <span class="progress-msg">{{ audioProgressMsg }}</span>
          <van-button
            size="small"
            type="danger"
            :loading="cancelling"
            @click="handleCancelAudioTask"
          >
            取消
          </van-button>
        </div>
      </div>
      <div class="edit-body">
        <BookEditor
          ref="bookEditorRef"
          v-model="content"
          :book-id="bookId"
          @save="handleSave"
        />
      </div>
    </div>
  </van-popup>

  <!-- 翻译模式选择 ActionSheet -->
  <van-action-sheet
    v-model:show="showGenerateModeSheet"
    :title="generateModeTitle"
    :actions="generateModeActions"
    @select="onGenerateModeSelect"
  />

  <!-- 翻译失败列表对话框 -->
  <van-popup
    v-model:show="showFailedDialog"
    position="bottom"
    round
    :style="{ height: '70%', width: '100%' }"
    closeable
  >
    <div class="failed-translation-dialog">
      <div class="failed-dialog-header">
        <h3>翻译失败列表</h3>
        <p class="failed-hint">以下句子翻译失败，请重试或手动输入翻译</p>
      </div>

      <div class="failed-list">
        <div
          v-for="(sentence, index) in failedSentences"
          :key="index"
          class="failed-item"
        >
          <div class="failed-text">
            <div class="sentence-text">{{ sentence.text }}</div>
            <div class="error-msg">{{ sentence.error }}</div>
          </div>
          <div class="failed-actions">
            <van-button
              size="small"
              type="primary"
              :loading="currentRetryingIndex === index"
              @click="retryTranslate(index)"
            >
              重试
            </van-button>
            <van-button
              size="small"
              type="default"
              @click="handleManualInput(index)"
            >
              手动输入
            </van-button>
          </div>
        </div>
      </div>

      <div class="failed-dialog-footer">
        <van-button type="default" @click="closeFailedDialog">关闭</van-button>
      </div>
    </div>
  </van-popup>

  <!-- 断句预览对话框 -->
  <van-popup
    v-model:show="showSentencePreview"
    position="bottom"
    round
    :style="{ height: '90%', width: '100%' }"
    closeable
    class="sentence-preview-popup"
  >
    <div class="sentence-preview-dialog">
      <div class="preview-header">
        <h3>断句预览</h3>
        <p class="preview-hint">点击句子可编辑，确认后进行翻译和双语生成</p>
      </div>

      <div class="preview-stats">
        <span v-if="!loadingPreview">共 {{ previewSentences.length }} 个句子</span>
        <van-loading v-else size="small">分析中...</van-loading>
        <span v-if="hasEditedSentences && !loadingPreview" class="edited-badge">有修改</span>
      </div>

      <div class="preview-list">
        <van-loading v-if="loadingPreview" type="spinner" class="preview-loading" />
        <template v-else>
          <div
            v-for="(sentence, index) in previewSentences"
            :key="`${sentence.page}-${sentence.index}`"
            class="preview-item"
            @click="editSentence(index)"
          >
            <div class="sentence-index">{{ index + 1 }}</div>
            <div class="sentence-content">
              <div class="sentence-text">{{ sentence.text }}</div>
              <div class="sentence-meta">第 {{ sentence.page + 1 }} 页，第 {{ sentence.index + 1 }} 句</div>
            </div>
            <van-icon name="edit" class="edit-icon" />
          </div>
        </template>
      </div>

      <div class="preview-footer">
        <van-button type="default" @click="closeSentencePreview">取消</van-button>
        <van-button
          type="primary"
          :loading="savingEdits"
          @click="saveSentenceEdits"
        >
          {{ saveButtonText }}
        </van-button>
      </div>
    </div>
  </van-popup>

  <!-- 句子编辑对话框 -->
  <van-popup
    v-model:show="showSentenceEdit"
    position="bottom"
    round
    :style="{ height: '50%', width: '100%' }"
    closeable
  >
    <div class="sentence-edit-dialog">
      <div class="edit-header">
        <h3>编辑句子</h3>
        <p class="edit-meta">第 {{ editingSentence?.page! + 1 }} 页，第 {{ editingSentence?.index! + 1 }} 句</p>
      </div>
      <div class="edit-content">
        <van-field
          v-model="editingText"
          type="textarea"
          placeholder="请输入句子内容"
          :rows="3"
          autosize
        />
      </div>
      <div class="edit-footer">
        <van-button type="default" @click="cancelEdit">取消</van-button>
        <van-button type="primary" @click="confirmEdit">确定</van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { showToast } from 'vant'
import { api, useAuthStore } from '@/store/auth'
import { showErrorDialog, showWarningDialog } from '@/utils/message'
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
  (e: 'closed'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const show = ref(props.modelValue)
const content = ref(props.initialContent)
const originalContent = ref(props.initialContent) // 保存原始内容用于比较
const isModified = ref(false) // 是否已修改
const bookEditorRef = ref<{ closeImagePreview: () => void } | null>(null)
const saving = ref(false)
const generatingAudio = ref(false)
const audioProgress = ref(0)
const audioProgressMsg = ref('')
const cancelling = ref(false)

// AbortController 用于取消 fetch 请求
let audioAbortController: AbortController | null = null

// 翻译失败句子相关状态
const failedSentences = ref<{
  text: string
  translation: string | null
  error: string
  page: number
  index: number
}[]>([])
const showFailedDialog = ref(false)
const currentRetryingIndex = ref(-1)

// 下拉菜单状态
const showAudioPopover = ref(false)

// 下拉菜单选项
const audioActions = [
  { text: '翻译+生成双语', icon: 'play-circle-o' },
  { text: '预览断句', icon: 'orders-o' },
  { text: '生成英文语音', icon: 'music-o' },
  { text: '生成句子翻译', icon: 'chat-o' },
  { text: '生成中文语音', icon: 'volume-o' }
]

// 生成模式选择 ActionSheet 相关状态
const showGenerateModeSheet = ref(false)
const generateModeTitle = ref('')
const generateModeActions = ref<{ name: string; subname?: string }[]>([])

// 监听modelValue变化
watch(() => props.modelValue, (val) => {
  show.value = val
  if (val) {
    content.value = props.initialContent
    originalContent.value = props.initialContent
    isModified.value = false
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
    originalContent.value = val
    isModified.value = false
  }
})

// 监听content变化，检查是否已修改
watch(content, (newContent) => {
  if (newContent !== originalContent.value) {
    isModified.value = true
  }
})

const loading = ref(false)

// 断句预览相关状态
const showSentencePreview = ref(false)
const loadingPreview = ref(false) // 是否正在加载断句预览
const showSentenceEdit = ref(false)
const previewSentences = ref<{
  page: number
  index: number
  text: string
  edited?: boolean
}[]>([])
const editingSentence = ref<{ page: number; index: number } | null>(null)
const editingText = ref('')
const savingEdits = ref(false)
const hasEditedSentences = ref(false)
const shouldGenerateBilingual = ref(false) // 是否在保存后生成双语

// 计算保存按钮文案
const saveButtonText = computed(() => {
  if (shouldGenerateBilingual.value) {
    // 翻译+生成双语场景
    return hasEditedSentences.value ? '保存并生成双语音' : '确认并生成双语音'
  } else {
    // 仅预览断句场景
    return hasEditedSentences.value ? '保存' : '确认'
  }
})

// 辅助函数：仅在内容已修改时保存，然后执行后续操作
const saveIfModified = async (onSaved?: () => void): Promise<boolean> => {
  // 直接比较 content 和 originalContent，避免 isModified 不准确导致的误保存
  if (content.value === originalContent.value) {
    // 内容未修改，跳过保存
    console.log('[保存] 内容未修改，跳过保存')
    isModified.value = false // 同步修正 isModified 状态
    return true
  }

  if (!props.bookId) {
    showErrorDialog('书籍ID无效')
    return false
  }

  saving.value = true
  try {
    const res = await api.put<{ success: boolean; message: string }>(`/books/${props.bookId}`, {
      content: content.value
    })

    if (!res.data.success) {
      showErrorDialog(res.data.message)
      saving.value = false
      return false
    }
    showToast('内容已保存')
    // 保存成功后更新原始内容并重置修改标志
    originalContent.value = content.value
    isModified.value = false
    saving.value = false
    emit('saved')
    if (onSaved) onSaved()
    return true
  } catch (error: any) {
    showErrorDialog('保存失败')
    saving.value = false
    return false
  }
}

// 预览断句（保留原有逻辑，用于翻译+生成双语）
const handlePreviewSentences = async () => {
  // 设置标志：保存后需要生成双语
  shouldGenerateBilingual.value = true

  // 仅在内容已修改时保存
  const saved = await saveIfModified()
  if (!saved) return

  // 先显示预览弹窗和加载状态
  previewSentences.value = []
  hasEditedSentences.value = false
  showSentencePreview.value = true
  loadingPreview.value = true

  // 获取断句预览
  try {
    const res = await api.get<{
      total_count: number
      sentences: { page: number; index: number; text: string }[]
    }>(`/books/${props.bookId}/sentence-preview`)

    previewSentences.value = res.data.sentences.map(s => ({
      ...s,
      edited: false
    }))
    hasEditedSentences.value = false
  } catch (error: any) {
    showErrorDialog('获取断句预览失败: ' + (error.message || '未知错误'))
    showSentencePreview.value = false
  } finally {
    loadingPreview.value = false
  }
}

// 关闭断句预览
const closeSentencePreview = () => {
  showSentencePreview.value = false
}

// 仅预览断句（保存断句但不生成双语）
const handlePreviewSentencesOnly = async () => {
  // 设置标志：保存后不需要生成双语
  shouldGenerateBilingual.value = false

  // 仅在内容已修改时保存
  const saved = await saveIfModified()
  if (!saved) return

  // 先显示预览弹窗和加载状态
  previewSentences.value = []
  hasEditedSentences.value = false
  showSentencePreview.value = true
  loadingPreview.value = true

  // 获取断句预览
  try {
    const res = await api.get<{
      total_count: number
      sentences: { page: number; index: number; text: string }[]
    }>(`/books/${props.bookId}/sentence-preview`)

    previewSentences.value = res.data.sentences.map(s => ({
      ...s,
      edited: false
    }))
    hasEditedSentences.value = false
  } catch (error: any) {
    showErrorDialog('获取断句预览失败: ' + (error.message || '未知错误'))
    showSentencePreview.value = false
  } finally {
    loadingPreview.value = false
  }
}

// 编辑句子
const editSentence = (index: number) => {
  const sentence = previewSentences.value[index]
  if (!sentence) return

  editingSentence.value = { page: sentence.page, index: sentence.index }
  editingText.value = sentence.text
  showSentenceEdit.value = true
}

// 取消编辑
const cancelEdit = () => {
  showSentenceEdit.value = false
  editingSentence.value = null
  editingText.value = ''
}

// 确认编辑
const confirmEdit = () => {
  if (!editingSentence.value) return

  const { page, index } = editingSentence.value
  const sentenceIndex = previewSentences.value.findIndex(
    s => s.page === page && s.index === index
  )

  if (sentenceIndex !== -1) {
    previewSentences.value[sentenceIndex].text = editingText.value
    previewSentences.value[sentenceIndex].edited = true
    hasEditedSentences.value = true
  }

  showSentenceEdit.value = false
  editingSentence.value = null
  editingText.value = ''
}

// 保存修改并生成双语
const saveSentenceEdits = async () => {
  if (!props.bookId) {
    showErrorDialog('书籍ID无效')
    return
  }

  // 如果有修改，逐个保存到后端
  savingEdits.value = true
  try {
    const editedSentences = previewSentences.value.filter(s => s.edited)

    for (const sentence of editedSentences) {
      await api.put(`/books/${props.bookId}/sentence`, {
        page: sentence.page,
        index: sentence.index,
        text: sentence.text
      })
    }

    showToast('句子已保存')
    showSentencePreview.value = false

    // 刷新内容 - 使用 /content 端点获取原始 Markdown
    const res = await api.get(`/books/${props.bookId}/content`)
    content.value = res.data.content

    // 根据标志决定是否生成双语
    if (shouldGenerateBilingual.value) {
      // 继续执行翻译和生成双语
      await handleGenerateAll()
    }
    // 保存完成后重置状态
    savingEdits.value = false
  } catch (error: any) {
    showErrorDialog('保存句子失败: ' + (error.message || '未知错误'))
    savingEdits.value = false
  }
}

// 关闭
const handleClose = () => {
  // 关闭图片预览
  bookEditorRef.value?.closeImagePreview()
  show.value = false
  emit('closed')
}

// 保存（仅在内容已修改时保存）
const handleSave = async () => {
  // 仅在内容已修改时保存
  const saved = await saveIfModified()
  if (!saved) return

  showToast('保存成功')
}

// 处理下拉菜单选择
const handleAudioSelect = async (action: { text: string }) => {
  showAudioPopover.value = false
  if (action.text === '翻译并生成语音' || action.text === '翻译+生成双语') {
    // 先预览断句，确认后再生成双语
    await handlePreviewSentences()
  } else if (action.text === '预览断句') {
    // 仅预览断句，不生成双语
    await handlePreviewSentencesOnly()
  } else if (action.text === '生成英文语音') {
    await handleGenerateAudio()
  } else if (action.text === '生成句子翻译') {
    await handleGenerateTranslation()
  } else if (action.text === '生成中文语音') {
    await handleGenerateChineseAudio()
  }
}

// 检查音频状态并返回详细信息
const checkAudioStatus = async (bookId: string) => {
  try {
    const res = await api.get<{
      has_english_audio: boolean;
      has_chinese_audio: boolean;
      has_translation: boolean;
      english_audio_count: number;
      chinese_audio_count: number;
      translation_count: number;
      total_sentences: number;
      english_audio_complete: boolean;
      chinese_audio_complete: boolean;
      translation_complete: boolean;
    }>(`/books/${bookId}/check-chinese-audio`)
    return res.data
  } catch (error) {
    console.error('检查音频状态失败:', error)
    return null
  }
}

// 生成英文音频
// 生成英文语音
const handleGenerateAudio = async () => {
  if (!props.bookId) {
    showErrorDialog('书籍ID无效')
    return
  }

  // 检查英文音频状态
  const audioStatus = await checkAudioStatus(props.bookId)
  let forceGenerate = false

  if (audioStatus) {
    const { english_audio_complete, english_audio_count, total_sentences } = audioStatus

    // 英文音频的状态
    const enAudioStatus = english_audio_complete ? '已齐全' : `缺${total_sentences - english_audio_count}`

    if (english_audio_complete) {
      // 英文音频齐全，显示 ActionSheet（覆盖/取消）
      generateModeTitle.value = `英文音频(${enAudioStatus})。\n请选择：`
      generateModeActions.value = [
        { name: '覆盖', subname: '全部重新生成' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = true
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'english_audio'
      return
    } else if (english_audio_count > 0) {
      // 有部分英文音频，显示 ActionSheet（全覆盖/补充缺失/取消）
      generateModeTitle.value = `英文音频(${enAudioStatus})。\n请选择生成方式：`
      generateModeActions.value = [
        { name: '全覆盖', subname: '全部重新生成' },
        { name: '补充缺失', subname: '只生成缺失部分' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = false
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'english_audio'
      return
    } else {
      // 完全没有英文音频，显示 ActionSheet（生成/取消）
      console.log('[英文音频] 没有英文音频')
      generateModeTitle.value = `英文音频(${enAudioStatus})。\n请选择：`
      generateModeActions.value = [
        { name: '生成', subname: '开始生成' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = false
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'english_audio'
      return
    }
  } else {
    console.log('[英文音频] 检查状态失败，继续生成')
    // 直接生成
    await continueGenerateEnglishAudio(forceGenerate)
  }
}

// 继续生成英文音频
const continueGenerateEnglishAudio = async (forceGenerate: boolean) => {
  const bookId = props.bookId

  // 仅在内容已修改时保存
  const saved = await saveIfModified()
  if (!saved) return

  // 然后生成音频
  generatingAudio.value = true
  const forceParam = forceGenerate ? '?force=true' : ''
  audioProgress.value = 0
  audioProgressMsg.value = '开始生成英文音频...'
  let hasError = false
  let errorMessage = ''

  // 创建 AbortController
  audioAbortController = new AbortController()

  try {
    const response = await fetch(`/api/v1/books/${bookId}/regenerate-audio${forceParam}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      },
      signal: audioAbortController.signal
    })

    if (!response.ok) {
      throw new Error(`生成请求失败: ${response.status} ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法读取响应流')
    }

    // 解析完整的JSON对象（处理嵌套花括号）
    const parseJsonFromData = (dataStr: string): { json: string; endIndex: number } | null => {
      const start = dataStr.indexOf('{')
      if (start === -1) return null

      let depth = 0
      let inString = false
      let escapeNext = false

      for (let i = start; i < dataStr.length; i++) {
        const char = dataStr[i]

        if (escapeNext) {
          escapeNext = false
          continue
        }

        if (char === '\\') {
          escapeNext = true
          continue
        }

        if (char === '"') {
          inString = !inString
          continue
        }

        if (!inString) {
          if (char === '{') depth++
          else if (char === '}') {
            depth--
            if (depth === 0) {
              return { json: dataStr.slice(start, i + 1), endIndex: i + 1 }
            }
          }
        }
      }

      return null
    }

    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      let hasValidData = false

      // 处理所有完整的 SSE 消息
      while (true) {
        // 查找 "data: " 前缀
        const dataPrefixIndex = buffer.indexOf('data: ')
        if (dataPrefixIndex === -1) break

        const jsonStart = dataPrefixIndex + 6 // "data: " 长度
        const result = parseJsonFromData(buffer.slice(jsonStart))

        if (!result) {
          // JSON 不完整，等待更多数据
          break
        }

        const fullJson = result.json
        const totalEndIndex = jsonStart + result.endIndex

        try {
          const data = JSON.parse(fullJson)
          hasValidData = true

          if (data.percentage !== undefined) {
            // 修复：限制进度最大为100，防止异常值导致进度条显示超过100%
            audioProgress.value = Math.min(100, data.percentage)
            audioProgressMsg.value = data.message || ''
          }

          // 检测错误消息
          if (data.message && (
            data.message.includes('失败') ||
            data.message.includes('错误') ||
            data.message.includes('Error') ||
            data.message.includes('Failed') ||
            data.message.includes('需要') ||
            data.message.includes('未配置')
          )) {
            hasError = true
            errorMessage = data.message
          }

          if (data.success === true) {
            showToast(data.message)
          } else if (data.success === false) {
            hasError = true
            errorMessage = data.message
            showErrorDialog(data.message)
          }
        } catch (e) {
          console.error('解析SSE数据失败:', e, 'JSON:', fullJson)
        }

        // 移除已处理的数据
        buffer = buffer.slice(totalEndIndex).trimStart()
      }

      // 如果没有解析到有效数据，可能是连接问题
      if (!hasValidData && buffer.trim()) {
        console.warn('收到无法解析的数据:', buffer)
      }
    }

    // 如果过程中检测到错误，显示最终错误提示
    if (hasError && errorMessage) {
      showErrorDialog(`音频生成异常: ${errorMessage}`)
    }

  } catch (error: any) {
    // 检查是否是主动取消（AbortError）
    if (error.name === 'AbortError' || error instanceof DOMException || error.message?.includes('abort')) {
      // 主动取消，不显示错误
      return
    }

    console.error('生成音频失败:', error)

    hasError = true

    // 根据错误类型显示不同的错误消息
    if (error.message?.includes('fetch') || error.message?.includes('network') || error.name === 'TypeError') {
      errorMessage = '无法连接到服务器，请检查：\n1. 后端服务是否已启动\n2. TTS语音服务是否在线'
    } else {
      errorMessage = error.message || '生成音频失败'
    }

    showErrorDialog(errorMessage)
  } finally {
    generatingAudio.value = false
    audioAbortController = null
    if (!hasError) {
      audioProgress.value = 0
      audioProgressMsg.value = ''
    } else {
      // 发生错误时保留进度条显示错误状态
      audioProgressMsg.value = errorMessage || '生成失败'
    }
  }
}
const handleGenerateAll = async () => {
  if (!props.bookId) {
    showErrorDialog('书籍ID无效')
    return
  }

  // 检查翻译API是否配置
  try {
    const res = await api.get<{ configured: boolean; message: string }>('/translation/status')
    if (!res.data.configured) {
      showWarningDialog('请先配置百度翻译API，路径：主界面→设置→词典设置')
      return
    }
  } catch (error) {
    showErrorDialog('检查翻译API配置失败')
    return
  }

  // 检查是否已有中英文语音和翻译
  let forceGenerate = false
  try {
    const audioStatus = await checkAudioStatus(props.bookId)

    if (audioStatus) {
      const { english_audio_complete, chinese_audio_complete, translation_complete, total_sentences, english_audio_count, translation_count, chinese_audio_count } = audioStatus
      const allComplete = english_audio_complete && chinese_audio_complete && translation_complete

      // 各类别的完整状态
      const enAudioStatus = english_audio_complete ? '已齐全' : `缺${total_sentences - english_audio_count}`
      const cnAudioStatus = chinese_audio_complete ? '已齐全' : `缺${total_sentences - chinese_audio_count}`
      const transStatus = translation_complete ? '已齐全' : `缺${total_sentences - translation_count}`

      if (allComplete) {
        // 全部齐全，显示 ActionSheet（覆盖/取消）
        generateModeTitle.value = `英文音频(${enAudioStatus})、中文音频(${cnAudioStatus})、翻译(${transStatus})。\n请选择：`
        generateModeActions.value = [
          { name: '覆盖', subname: '全部重新生成' },
          { name: '取消', subname: '' }
        ]
        showGenerateModeSheet.value = true
        ;(window as any).__pendingForceGenerate = true
        ;(window as any).__pendingBookId = props.bookId
        ;(window as any).__pendingContent = content.value
        ;(window as any).__pendingAction = 'bilingual'
        return
      } else if (english_audio_count === 0 && translation_count === 0 && chinese_audio_count === 0) {
        // 完全没有音频和翻译，显示 ActionSheet（生成/取消）
        generateModeTitle.value = `英文音频(缺${total_sentences})、中文音频(缺${total_sentences})、翻译(缺${total_sentences})。\n请选择：`
        generateModeActions.value = [
          { name: '生成', subname: '开始生成' },
          { name: '取消', subname: '' }
        ]
        showGenerateModeSheet.value = true
        ;(window as any).__pendingForceGenerate = false
        ;(window as any).__pendingBookId = props.bookId
        ;(window as any).__pendingContent = content.value
        ;(window as any).__pendingAction = 'bilingual'
        return
      } else {
        // 有部分内容，显示"全覆盖"、"补充"、"取消"三个选项
        generateModeTitle.value = `英文音频(${enAudioStatus})、中文音频(${cnAudioStatus})、翻译(${transStatus})。\n请选择生成方式：`
        generateModeActions.value = [
          { name: '全覆盖', subname: '全部重新生成' },
          { name: '补充缺失', subname: '只生成缺失部分' },
          { name: '取消', subname: '' }
        ]
        showGenerateModeSheet.value = true
        ;(window as any).__pendingForceGenerate = false
        ;(window as any).__pendingBookId = props.bookId
        ;(window as any).__pendingContent = content.value
        ;(window as any).__pendingAction = 'bilingual'
        return
      }
    }
  } catch (error) {
    console.error('检查音频状态失败:', error)
    // 检查失败，继续尝试生成
    await continueGenerateAll(forceGenerate)
  }
}

// 处理生成模式选择
const onGenerateModeSelect = async (action: { name: string }) => {
  showGenerateModeSheet.value = false

  // 如果用户选择取消，直接返回
  if (action.name === '取消') {
    showToast('已取消')
    return
  }

  // 确定 forceGenerate 的值
  let forceGenerate = false
  if (action.name === '全覆盖' || action.name === '覆盖') {
    forceGenerate = true
  }

  // 检查是否是中文音频生成
  const pendingAction = (window as any).__pendingAction
  if (pendingAction === 'chinese_audio') {
    // 清理待处理状态
    ;(window as any).__pendingAction = null
    ;(window as any).__pendingBookId = null
    ;(window as any).__pendingContent = null
    ;(window as any).__pendingForceGenerate = null
    // 继续生成中文音频
    await continueGenerateChineseAudio(forceGenerate)
  } else if (pendingAction === 'english_audio') {
    // 清理待处理状态
    ;(window as any).__pendingAction = null
    ;(window as any).__pendingBookId = null
    ;(window as any).__pendingContent = null
    ;(window as any).__pendingForceGenerate = null
    // 继续生成英文音频
    await continueGenerateEnglishAudio(forceGenerate)
  } else if (pendingAction === 'translation') {
    // 清理待处理状态
    ;(window as any).__pendingAction = null
    ;(window as any).__pendingBookId = null
    ;(window as any).__pendingContent = null
    ;(window as any).__pendingForceGenerate = null
    // 继续生成翻译
    await continueGenerateTranslation(forceGenerate)
  } else {
    // 翻译+生成双语
    await continueGenerateAll(forceGenerate)
  }
}

// 继续执行翻译和生成（提取公共逻辑）
const continueGenerateAll = async (forceGenerate: boolean) => {
  if (!props.bookId) return

  // 仅在内容已修改时保存
  const saved = await saveIfModified()
  if (!saved) return

  // 调用中英文音频生成API
  generatingAudio.value = true
  audioProgress.value = 0
  audioProgressMsg.value = '开始生成翻译及中英文语音...'
  const forceParam = forceGenerate ? '?force=true' : ''
  let hasError = false
  let errorMessage = ''

  // 创建 AbortController
  audioAbortController = new AbortController()

  try {
    const response = await fetch(`/api/v1/books/${props.bookId}/regenerate-audio-bilingual${forceParam}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      },
      signal: audioAbortController.signal
    })

    if (!response.ok) {
      throw new Error(`生成请求失败: ${response.status} ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法读取响应流')
    }

    const parseJsonFromData = (dataStr: string): { json: string; endIndex: number } | null => {
      const start = dataStr.indexOf('{')
      if (start === -1) return null

      let depth = 0
      let inString = false
      let escapeNext = false

      for (let i = start; i < dataStr.length; i++) {
        const char = dataStr[i]

        if (escapeNext) {
          escapeNext = false
          continue
        }

        if (char === '\\') {
          escapeNext = true
          continue
        }

        if (char === '"') {
          inString = !inString
          continue
        }

        if (!inString) {
          if (char === '{') depth++
          else if (char === '}') {
            depth--
            if (depth === 0) {
              return { json: dataStr.slice(start, i + 1), endIndex: i + 1 }
            }
          }
        }
      }

      return null
    }

    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      let hasValidData = false

      while (true) {
        const dataPrefixIndex = buffer.indexOf('data: ')
        if (dataPrefixIndex === -1) break

        const jsonStart = dataPrefixIndex + 6
        const result = parseJsonFromData(buffer.slice(jsonStart))

        if (!result) {
          break
        }

        const fullJson = result.json
        const totalEndIndex = jsonStart + result.endIndex

        try {
          const data = JSON.parse(fullJson)
          hasValidData = true

          if (data.percentage !== undefined) {
            // 修复：限制进度最大为100，防止异常值导致进度条显示超过100%
            audioProgress.value = Math.min(100, data.percentage)
            audioProgressMsg.value = data.message || ''
          }

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
            showToast(data.message)
          } else if (data.success === false) {
            hasError = true
            errorMessage = data.message
            showErrorDialog(data.message)
          }
        } catch (e) {
          console.error('解析SSE数据失败:', e, 'JSON:', fullJson)
        }

        buffer = buffer.slice(totalEndIndex).trimStart()
      }

      if (!hasValidData && buffer.trim()) {
        console.warn('收到无法解析的数据:', buffer)
      }
    }

    if (hasError && errorMessage) {
      showErrorDialog(`生成异常: ${errorMessage}`)
    }

  } catch (error: any) {
    // 检查是否是主动取消（AbortError）
    if (error.name === 'AbortError' || error instanceof DOMException || error.message?.includes('abort')) {
      // 主动取消，不显示错误
      return
    }

    console.error('生成失败:', error)

    hasError = true

    if (error.message?.includes('fetch') || error.message?.includes('network') || error.name === 'TypeError') {
      errorMessage = '无法连接到服务器，请检查后端服务是否已启动'
    } else {
      errorMessage = error.message || '生成失败'
    }

    showErrorDialog(errorMessage)
  } finally {
    generatingAudio.value = false
    audioAbortController = null
    if (!hasError) {
      audioProgress.value = 0
      audioProgressMsg.value = ''
    } else {
      audioProgressMsg.value = errorMessage || '生成失败'
    }
  }
}

// 生成句子翻译
const handleGenerateTranslation = async () => {
  if (!props.bookId) {
    showErrorDialog('书籍ID无效')
    return
  }

  // 检查翻译API是否配置
  try {
    const res = await api.get<{ configured: boolean; message: string }>('/translation/status')
    if (!res.data.configured) {
      showWarningDialog('请先配置百度翻译API，路径：主界面→设置→词典设置')
      return
    }
  } catch (error) {
    showErrorDialog('检查翻译API配置失败')
    return
  }

  // 检查翻译状态
  const audioStatus = await checkAudioStatus(props.bookId)
  let forceGenerate = false

  if (audioStatus) {
    const { translation_complete, translation_count, total_sentences } = audioStatus

    // 翻译的状态
    const transStatus = translation_complete ? '已齐全' : `缺${total_sentences - translation_count}`

    if (translation_complete) {
      // 翻译齐全，显示 ActionSheet（覆盖/取消）
      generateModeTitle.value = `翻译(${transStatus})。\n请选择：`
      generateModeActions.value = [
        { name: '覆盖', subname: '全部重新生成' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = true
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'translation'
      return
    } else if (translation_count > 0) {
      // 有部分翻译，显示 ActionSheet（全覆盖/补充缺失/取消）
      generateModeTitle.value = `翻译(${transStatus})。\n请选择生成方式：`
      generateModeActions.value = [
        { name: '全覆盖', subname: '全部重新生成' },
        { name: '补充缺失', subname: '只生成缺失部分' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = false
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'translation'
      return
    } else {
      // 完全没有翻译，显示 ActionSheet（生成/取消）
      console.log('[翻译] 没有翻译')
      generateModeTitle.value = `翻译(${transStatus})。\n请选择：`
      generateModeActions.value = [
        { name: '生成', subname: '开始生成' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = false
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'translation'
      return
    }
  } else {
    console.log('[翻译] 检查状态失败，继续生成')
    // 直接生成
    await continueGenerateTranslation(forceGenerate)
  }
}

// 继续生成翻译
const continueGenerateTranslation = async (forceGenerate: boolean) => {
  const bookId = props.bookId

  // 仅在内容已修改时保存
  const saved = await saveIfModified()
  if (!saved) return

  // 然后生成翻译
  generatingAudio.value = true
  const forceParam = forceGenerate ? '?force=true' : ''
  audioProgress.value = 0
  audioProgressMsg.value = '开始生成翻译...'
  let hasError = false
  let errorMessage = ''

  // 创建 AbortController
  audioAbortController = new AbortController()

  try {
    const response = await fetch(`/api/v1/books/${bookId}/generate-translation${forceParam}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      },
      signal: audioAbortController.signal
    })

    if (!response.ok) {
      throw new Error(`生成请求失败: ${response.status} ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法读取响应流')
    }

    // 解析完整的JSON对象
    const parseJsonFromData = (dataStr: string): { json: string; endIndex: number } | null => {
      const start = dataStr.indexOf('{')
      if (start === -1) return null

      let depth = 0
      let inString = false
      let escapeNext = false

      for (let i = start; i < dataStr.length; i++) {
        const char = dataStr[i]

        if (escapeNext) {
          escapeNext = false
          continue
        }

        if (char === '\\') {
          escapeNext = true
          continue
        }

        if (char === '"') {
          inString = !inString
          continue
        }

        if (!inString) {
          if (char === '{') depth++
          else if (char === '}') {
            depth--
            if (depth === 0) {
              return { json: dataStr.slice(start, i + 1), endIndex: i + 1 }
            }
          }
        }
      }

      return null
    }

    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      let hasValidData = false

      while (true) {
        const dataPrefixIndex = buffer.indexOf('data: ')
        if (dataPrefixIndex === -1) break

        const jsonStart = dataPrefixIndex + 6
        const result = parseJsonFromData(buffer.slice(jsonStart))

        if (!result) {
          break
        }

        const fullJson = result.json
        const totalEndIndex = jsonStart + result.endIndex

        try {
          const data = JSON.parse(fullJson)
          hasValidData = true

          if (data.percentage !== undefined) {
            // 修复：限制进度最大为100，防止异常值导致进度条显示超过100%
            audioProgress.value = Math.min(100, data.percentage)
            audioProgressMsg.value = data.message || ''
          }

          if (data.message && (
            data.message.includes('失败') ||
            data.message.includes('错误') ||
            data.message.includes('Error') ||
            data.message.includes('Failed') ||
            data.message.includes('需要') ||
            data.message.includes('未配置')
          )) {
            hasError = true
            errorMessage = data.message
          }

          if (data.success === true) {
            showToast(data.message)
          } else if (data.success === false) {
            hasError = true
            errorMessage = data.message
            showErrorDialog(data.message)
          }
        } catch (e) {
          console.error('解析SSE数据失败:', e, 'JSON:', fullJson)
        }

        buffer = buffer.slice(totalEndIndex).trimStart()
      }

      if (!hasValidData && buffer.trim()) {
        console.warn('收到无法解析的数据:', buffer)
      }
    }

    if (hasError && errorMessage) {
      showErrorDialog(`翻译生成异常: ${errorMessage}`)
    }

  } catch (error: any) {
    // 检查是否是主动取消（AbortError）
    if (error.name === 'AbortError' || error instanceof DOMException || error.message?.includes('abort')) {
      // 主动取消，不显示错误
      return
    }

    console.error('生成翻译失败:', error)

    hasError = true

    if (error.message?.includes('fetch') || error.message?.includes('network') || error.name === 'TypeError') {
      errorMessage = '无法连接到服务器，请检查后端服务是否已启动'
    } else {
      errorMessage = error.message || '生成翻译失败'
    }

    showErrorDialog(errorMessage)
  } finally {
    generatingAudio.value = false
    audioAbortController = null
    if (!hasError) {
      audioProgress.value = 0
      audioProgressMsg.value = ''
      // 检查是否有翻译失败的句子
      await checkTranslationFailures()
    } else {
      audioProgressMsg.value = errorMessage || '生成失败'
    }
  }
}

// 检查翻译失败并显示对话框
const checkTranslationFailures = async () => {
  try {
    const res = await api.get<{
      success: boolean
      total_count: number
      success_count: number
      failed_count: number
      failed_sentences: {
        text: string
        translation: string | null
        error: string
        page: number
        index: number
      }[]
    }>(`/books/${props.bookId}/translation-status`)

    if (res.data.failed_count > 0) {
      failedSentences.value = res.data.failed_sentences
      showFailedDialog.value = true
    }
  } catch (error) {
    console.error('检查翻译状态失败:', error)
  }
}

// 重试翻译单个句子
const retryTranslate = async (index: number) => {
  const sentence = failedSentences.value[index]
  if (!sentence) return

  currentRetryingIndex.value = index
  try {
    const res = await api.post<{
      success: boolean
      message: string
      translation: string | null
    }>(`/books/${props.bookId}/retry-translate`, {
      text: sentence.text,
      page: sentence.page,
      index: sentence.index
    })

    if (res.data.success && res.data.translation) {
      showToast('翻译成功')
      // 从失败列表中移除
      failedSentences.value.splice(index, 1)
      // 如果没有更多失败，关闭对话框
      if (failedSentences.value.length === 0) {
        showFailedDialog.value = false
      }
    } else {
      showErrorDialog(res.data.message || '重试翻译失败')
    }
  } catch (error: any) {
    showErrorDialog(error.message || '重试翻译失败')
  } finally {
    currentRetryingIndex.value = -1
  }
}

// 手动输入翻译
const handleManualInput = async (index: number) => {
  const sentence = failedSentences.value[index]
  if (!sentence) return

  // 使用 showConfirmDialog 配合输入框
  try {
    const { showConfirmDialog } = await import('vant')

    // 创建一个带输入框的对话框
    const confirmed = await showConfirmDialog({
      title: '手动输入翻译',
      message: `<div style="text-align: left; padding: 10px 0;">
        <div style="margin-bottom: 8px; color: #666; font-size: 14px;">
          <strong>原文:</strong> ${sentence.text.substring(0, 100)}${sentence.text.length > 100 ? '...' : ''}
        </div>
        <input
          type="text"
          id="manual-translate-input"
          placeholder="请输入翻译"
          style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;"
        />
      </div>`,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      closeOnClickOverlay: false
    }).then(() => true).catch(() => false)

    if (!confirmed) return

    // 获取输入框的值
    const inputEl = document.getElementById('manual-translate-input') as HTMLInputElement
    const translation = inputEl?.value?.trim()

    if (!translation) {
      showToast('请输入翻译')
      return
    }

    try {
      const res = await api.put<{
        success: boolean
        message: string
      }>(`/books/${props.bookId}/translate-sentence`, {
        text: sentence.text,
        translation: translation
      })

      if (res.data.success) {
        showToast('保存成功')
        // 从失败列表中移除
        failedSentences.value.splice(index, 1)
        // 如果没有更多失败，关闭对话框
        if (failedSentences.value.length === 0) {
          showFailedDialog.value = false
        }
      } else {
        showErrorDialog(res.data.message || '保存失败')
      }
    } catch (error: any) {
      showErrorDialog(error.message || '保存失败')
    }
  } catch (error) {
    console.error('手动输入翻译失败:', error)
    showErrorDialog('手动输入功能暂时不可用')
  }
}

// 关闭失败对话框
const closeFailedDialog = () => {
  showFailedDialog.value = false
}

// 生成中文音频
const handleGenerateChineseAudio = async () => {
  console.log('[中文音频] 开始生成流程, bookId:', props.bookId)
  if (!props.bookId) {
    showErrorDialog('书籍ID无效')
    return
  }

  // 检查翻译API是否配置
  try {
    console.log('[中文音频] 检查翻译API配置...')
    const res = await api.get<{ configured: boolean; message: string }>('/translation/status')
    console.log('[中文音频] 翻译API状态:', res.data)
    if (!res.data.configured) {
      showWarningDialog('请先配置百度翻译API，路径：主界面→设置→词典设置')
      return
    }
  } catch (error) {
    console.error('[中文音频] 检查翻译API失败:', error)
    showErrorDialog('检查翻译API配置失败')
    return
  }

  // 检查中文音频状态
  let forceRegenerate = false  // 是否强制重新生成

  const audioStatus = await checkAudioStatus(props.bookId)

  if (audioStatus) {
    console.log('[中文音频] 检查结果:', audioStatus)
    const { chinese_audio_complete, chinese_audio_count, total_sentences, translation_count, translation_complete } = audioStatus

    // 中文音频和翻译的完整状态
    const cnAudioStatus = chinese_audio_complete ? '已齐全' : `缺${total_sentences - chinese_audio_count}`
    const transStatus = translation_complete ? '已齐全' : `缺${total_sentences - translation_count}`

    if (chinese_audio_complete && translation_complete) {
      // 中文音频和翻译都齐全，显示 ActionSheet（覆盖/取消）
      console.log('[中文音频] 中文音频和翻译都齐全，显示选择弹窗')
      generateModeTitle.value = `中文音频(${cnAudioStatus})、翻译(${transStatus})。\n请选择：`
      generateModeActions.value = [
        { name: '覆盖', subname: '全部重新生成' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = true
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'chinese_audio'
      return
    } else if (chinese_audio_count > 0 || translation_count > 0) {
      // 有部分中文音频或翻译，显示 ActionSheet（全覆盖/补充缺失/取消）
      generateModeTitle.value = `中文音频(${cnAudioStatus})、翻译(${transStatus})。\n请选择生成方式：`
      generateModeActions.value = [
        { name: '全覆盖', subname: '全部重新生成' },
        { name: '补充缺失', subname: '只生成缺失部分' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = false
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'chinese_audio'
      return
    } else {
      // 翻译不存在时，提示用户先生成翻译
      console.log('[中文音频] 没有中文音频和翻译')
      if (!translation_complete && translation_count === 0) {
        showWarningDialog('翻译尚未生成，请先生成翻译')
        return
      }
      // 显示 ActionSheet（生成/取消）
      generateModeTitle.value = `中文音频(${cnAudioStatus})、翻译(${transStatus})。\n请选择：`
      generateModeActions.value = [
        { name: '生成', subname: '开始生成' },
        { name: '取消', subname: '' }
      ]
      showGenerateModeSheet.value = true
      ;(window as any).__pendingForceGenerate = false
      ;(window as any).__pendingBookId = props.bookId
      ;(window as any).__pendingContent = content.value
      ;(window as any).__pendingAction = 'chinese_audio'
      return
    }
  } else {
    console.log('[中文音频] 检查状态失败，继续生成')
    // 直接生成
    await continueGenerateChineseAudio(forceRegenerate)
  }
}

// 继续生成中文音频
const continueGenerateChineseAudio = async (forceRegenerate: boolean) => {
  const bookId = props.bookId

  // 仅在内容已修改时保存
  const saved = await saveIfModified()
  if (!saved) return

  // 然后生成中文音频
  generatingAudio.value = true
  audioProgress.value = 0
  audioProgressMsg.value = '开始生成中文音频...'
  let hasError = false
  let errorMessage = ''

  // 创建 AbortController
  audioAbortController = new AbortController()

  try {
    // 传递 force 参数决定是否强制重新生成
    const forceParam = forceRegenerate ? '?force=true' : ''
    const response = await fetch(`/api/v1/books/${bookId}/generate-chinese-audio${forceParam}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      },
      signal: audioAbortController.signal
    })

    if (!response.ok) {
      throw new Error(`生成请求失败: ${response.status} ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法读取响应流')
    }

    const parseJsonFromData = (dataStr: string): { json: string; endIndex: number } | null => {
      const start = dataStr.indexOf('{')
      if (start === -1) return null

      let depth = 0
      let inString = false
      let escapeNext = false

      for (let i = start; i < dataStr.length; i++) {
        const char = dataStr[i]

        if (escapeNext) {
          escapeNext = false
          continue
        }

        if (char === '\\') {
          escapeNext = true
          continue
        }

        if (char === '"') {
          inString = !inString
          continue
        }

        if (!inString) {
          if (char === '{') depth++
          else if (char === '}') {
            depth--
            if (depth === 0) {
              return { json: dataStr.slice(start, i + 1), endIndex: i + 1 }
            }
          }
        }
      }

      return null
    }

    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      let hasValidData = false

      while (true) {
        const dataPrefixIndex = buffer.indexOf('data: ')
        if (dataPrefixIndex === -1) break

        const jsonStart = dataPrefixIndex + 6
        const result = parseJsonFromData(buffer.slice(jsonStart))

        if (!result) {
          break
        }

        const fullJson = result.json
        const totalEndIndex = jsonStart + result.endIndex

        try {
          const data = JSON.parse(fullJson)
          hasValidData = true

          if (data.percentage !== undefined) {
            // 修复：限制进度最大为100，防止异常值导致进度条显示超过100%
            audioProgress.value = Math.min(100, data.percentage)
            audioProgressMsg.value = data.message || ''
          }

          if (data.message && (
            data.message.includes('失败') ||
            data.message.includes('错误') ||
            data.message.includes('Error') ||
            data.message.includes('Failed') ||
            data.message.includes('需要') ||
            data.message.includes('未配置')
          )) {
            hasError = true
            errorMessage = data.message
          }

          if (data.success === true) {
            showToast(data.message)
          } else if (data.success === false) {
            hasError = true
            errorMessage = data.message
            // 特别处理 Edge-TTS 服务暂时不可用的情况
            if (data.message.includes('503') || data.message.includes('暂时不可用')) {
              showWarningDialog('Edge-TTS服务暂时不可用，已生成的音频会保留，下次点击将继续生成剩余部分')
            } else {
              showErrorDialog(data.message)
            }
          }
        } catch (e) {
          console.error('解析SSE数据失败:', e, 'JSON:', fullJson)
        }

        buffer = buffer.slice(totalEndIndex).trimStart()
      }

      if (!hasValidData && buffer.trim()) {
        console.warn('收到无法解析的数据:', buffer)
      }
    }

    if (hasError && errorMessage) {
      // 特别处理 Edge-TTS 服务暂时不可用的情况
      if (errorMessage.includes('503') || errorMessage.includes('暂时不可用')) {
        showWarningDialog('Edge-TTS服务暂时不可用，已生成的音频会保留，下次点击将继续生成剩余部分')
      } else {
        showErrorDialog(`中文音频生成异常: ${errorMessage}`)
      }
    }

  } catch (error: any) {
    // 检查是否是主动取消（AbortError）
    if (error.name === 'AbortError' || error instanceof DOMException || error.message?.includes('abort')) {
      // 主动取消，不显示错误
      return
    }

    console.error('生成中文音频失败:', error)

    hasError = true

    if (error.message?.includes('fetch') || error.message?.includes('network') || error.name === 'TypeError') {
      errorMessage = '无法连接到服务器，请检查：\n1. 后端服务是否已启动\n2. TTS语音服务是否在线'
    } else {
      errorMessage = error.message || '生成中文音频失败'
    }

    showErrorDialog(errorMessage)
  } finally {
    generatingAudio.value = false
    audioAbortController = null
    if (!hasError) {
      audioProgress.value = 0
      audioProgressMsg.value = ''
      // 检查是否有翻译失败的句子
      await checkTranslationFailures()
    } else {
      audioProgressMsg.value = errorMessage || '生成失败'
    }
  }
}

// 取消音频生成任务
const handleCancelAudioTask = async () => {
  if (!props.bookId) return

  cancelling.value = true
  try {
    // 调用后端取消端点
    await api.post(`/books/${props.bookId}/cancel-audio-task`)

    // 中止前端 fetch 请求
    if (audioAbortController) {
      audioAbortController.abort()
    }

    showToast('已取消')
  } catch (error: any) {
    console.error('取消任务失败:', error)
    // 忽略取消过程中的错误
  } finally {
    cancelling.value = false
    generatingAudio.value = false
    audioProgress.value = 0
    audioProgressMsg.value = ''
    audioAbortController = null
  }
}

// 暴露方法给父组件调用
defineExpose({
  // 关闭图片预览（代理 BookEditor 的方法）
  closeImagePreview: () => {
    bookEditorRef.value?.closeImagePreview()
  }
})
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

.edit-header :deep(.van-button) {
  flex-shrink: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.header-actions :deep(.van-button) {
  min-width: 72px;
}

/* 下拉菜单样式 */
:deep(.van-popover__action) {
  min-width: 160px;
  justify-content: flex-start;
}

:deep(.van-popover__action-text) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.edit-title {
  flex: 1;
  font-size: 16px;
  font-weight: bold;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
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

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-msg {
  font-size: 12px;
  color: #666;
  text-align: left;
}

/* 翻译失败对话框样式 */
.failed-translation-dialog {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.failed-dialog-header {
  flex-shrink: 0;
  margin-bottom: 16px;
}

.failed-dialog-header h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
}

.failed-hint {
  margin: 0;
  font-size: 14px;
  color: #666;
}

.failed-list {
  flex: 1;
  overflow-y: auto;
}

.failed-item {
  padding: 12px;
  border-bottom: 1px solid #eee;
}

.failed-item:last-child {
  border-bottom: none;
}

.failed-text {
  margin-bottom: 10px;
}

.sentence-text {
  font-size: 14px;
  color: #333;
  word-break: break-all;
  margin-bottom: 4px;
}

.error-msg {
  font-size: 12px;
  color: #f44;
}

.failed-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.failed-dialog-footer {
  flex-shrink: 0;
  padding-top: 16px;
  border-top: 1px solid #eee;
  text-align: center;
}

/* 断句预览对话框样式 */
.sentence-preview-popup {
  height: 90% !important;
  max-height: 90vh !important;
  overflow: hidden !important;
}

.sentence-preview-popup .van-popup__content {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden !important;
}

.sentence-preview-dialog {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom, 12px));
  box-sizing: border-box;
}

.preview-header {
  flex-shrink: 0;
  margin-bottom: 8px;
}

.preview-header h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
}

.preview-hint {
  margin: 0;
  font-size: 12px;
  color: #666;
}

.preview-stats {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #666;
}

.edited-badge {
  color: #ff9800;
  font-size: 12px;
}

.preview-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.preview-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 200px;
}

.preview-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}

.preview-item:active {
  background-color: #f5f5f5;
}

.sentence-index {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #1989fa;
  color: #fff;
  border-radius: 50%;
  font-size: 11px;
}

.sentence-content {
  flex: 1;
  min-width: 0;
}

.sentence-text {
  font-size: 14px;
  color: #333;
  word-break: break-all;
  line-height: 1.5;
}

.sentence-meta {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.edit-icon {
  flex-shrink: 0;
  color: #999;
  font-size: 18px;
}

.preview-footer {
  flex-shrink: 0;
  display: flex;
  gap: 12px;
  padding: 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom, 12px));
  box-sizing: border-box;
  border-top: 1px solid #eee;
}

.preview-footer button {
  flex: 1;
}

/* 句子编辑对话框样式 */
.sentence-edit-dialog {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.sentence-edit-dialog .edit-header {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.sentence-edit-dialog .edit-header h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
}

.sentence-edit-dialog .edit-meta {
  margin: 0;
  font-size: 12px;
  color: #666;
}

.sentence-edit-dialog .edit-content {
  flex: 1;
  overflow: auto;
}

.sentence-edit-dialog .edit-footer {
  flex-shrink: 0;
  display: flex;
  gap: 12px;
  padding-top: 16px;
}

.sentence-edit-dialog .edit-footer button {
  flex: 1;
}
</style>
