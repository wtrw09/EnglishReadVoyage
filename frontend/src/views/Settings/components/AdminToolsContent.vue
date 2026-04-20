/**
 * AdminToolsContent.vue - 管理员工具内容
 *
 * 功能：管理员专用工具
 * - 修复书籍数据（同步数据库）
 * - 压缩书籍图片
 * - 预编译缓存
 * - 查看 Docker 日志
 */
<template>
  <div class="admin-tools-content">
    <!-- 功能按钮列表 -->
    <van-cell-group inset title="书籍管理工具">
      <van-cell
        title="修复书籍数据"
        label="扫描 Books 目录并同步数据库记录，检查语音配置文件完整性"
        is-link
        @click="handleSyncBooks"
      >
        <template #icon>
          <i class="fas fa-sync-alt tool-icon"></i>
        </template>
      </van-cell>
      
      <van-cell
        title="压缩书籍图片"
        label="将 jpg/jpeg/png/bmp 格式图片压缩并转换为 WebP 格式"
        is-link
        @click="handleCompressImages"
      >
        <template #icon>
          <i class="fas fa-compress-arrows-alt tool-icon"></i>
        </template>
      </van-cell>
      
      <van-cell
        title="预编译缓存"
        label="预编译书籍可加快首次加载速度（约3500倍提升）"
        is-link
        @click="handlePrecompile"
      >
        <template #icon>
          <i class="fas fa-bolt tool-icon"></i>
        </template>
        <template #value>
          <van-tag v-if="precompileStatus.cache_percentage !== undefined" 
                   :type="precompileStatus.cache_percentage === 100 ? 'success' : 'warning'">
            {{ precompileStatus.cache_percentage }}%
          </van-tag>
        </template>
      </van-cell>
      
      <van-cell
        title="补充翻译+中文语音"
        label="检查所有书籍，补充缺少的翻译和中文语音"
        is-link
        @click="handleSupplementAll"
      >
        <template #icon>
          <i class="fas fa-language tool-icon"></i>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 预编译进度弹窗 -->
    <van-dialog
      v-model:show="showPrecompileProgress"
      title="预编译缓存"
      :show-confirm-button="false"
      :show-cancel-button="!precompileLoading"
      cancel-button-text="关闭"
      @cancel="showPrecompileProgress = false"
    >
      <div style="padding: 20px;">
        <van-progress :percentage="precompileProgress" />
        <p style="text-align: center; margin-top: 10px; color: #666;">
          {{ precompileMessage }}
        </p>
      </div>
    </van-dialog>

    <!-- 补充翻译进度弹窗 -->
    <van-dialog
      v-model:show="showSupplementProgress"
      title="补充翻译+中文语音"
      :close-on-click-overlay="false"
      :show-confirm-button="!supplementLoading"
      :show-cancel-button="supplementLoading"
      confirm-button-text="关闭"
      cancel-button-text="取消"
      @confirm="showSupplementProgress = false"
      @cancel="handleCancelSupplement"
    >
      <div style="padding: 20px;">
        <van-progress :percentage="supplementProgress" />
        <p style="text-align: center; margin-top: 10px; color: #666;">
          {{ supplementMessage }}
        </p>
      </div>
    </van-dialog>

    <!-- 音频修复结果弹窗 -->
    <AudioFixDialog
      v-model:show="showAudioErrorDialog"
      :fixed-list="audioFixedList"
      :error-list="audioErrorList"
      @edit-book="handleEditBookFromAudioFix"
    />

    <!-- 书籍编辑弹窗 -->
    <BookEditDialog
      v-model="showBookEditDialog"
      :book-id="currentEditBookId"
      :title="currentEditBookTitle"
      :initial-content="currentEditBookContent"
      @saved="handleBookEditSaved"
      @closed="handleBookEditClosed"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showConfirmDialog, showNotify, showLoadingToast, closeToast } from 'vant'
import { useAuthStore, api } from '@/store/auth'
import AudioFixDialog from '@/components/AudioFixDialog.vue'
import BookEditDialog from '@/components/BookEditDialog.vue'

// 组件名称，用于在 Settings.vue 中识别组件
defineOptions({
  name: 'AdminToolsContent'
})

const authStore = useAuthStore()

// 预编译进度
const showPrecompileProgress = ref(false)
const precompileProgress = ref(0)
const precompileMessage = ref('')
const precompileLoading = ref(false)
const precompileStatus = ref<{ cached_books?: number; total_books?: number; cache_percentage?: number }>({})

// 补充翻译进度
const showSupplementProgress = ref(false)
const supplementProgress = ref(0)
const supplementMessage = ref('')
const supplementLoading = ref(false)
let currentSupplementReader: ReadableStreamDefaultReader | null = null

// 取消补充翻译
const handleCancelSupplement = async () => {
  if (currentSupplementReader) {
    currentSupplementReader.cancel()
    currentSupplementReader = null
  }
  try {
    await api.post('/books/admin/books/supplement-all/cancel')
    supplementMessage.value = '正在取消...'
  } catch (error) {
    console.error('取消失败:', error)
  }
  supplementLoading.value = false
  showSupplementProgress.value = false
}

// 音频修复结果
const showAudioErrorDialog = ref(false)
const audioErrorList = ref<any[]>([])
const audioFixedList = ref<any[]>([])

// 书籍编辑弹窗
const showBookEditDialog = ref(false)
const currentEditBookId = ref('')
const currentEditBookTitle = ref('')
const currentEditBookContent = ref('')

// 加载预编译状态
const loadPrecompileStatus = async () => {
  try {
    const res = await api.get('/books/precompile/status')
    precompileStatus.value = res.data
  } catch (error) {
    console.error('加载预编译状态失败:', error)
  }
}

// 修复书籍数据
const handleSyncBooks = async () => {
  showConfirmDialog({
    title: '修复书籍数据',
    message: '将扫描 Books 目录并同步数据库记录，同时检查语音配置文件完整性，是否继续？'
  }).then(async () => {
    showLoadingToast({ message: '正在同步书籍...', forbidClick: true, duration: 0 })
    try {
      const res = await api.post('/books/sync')
      closeToast()
      const messages: string[] = []
      if (res.data.fixed?.length > 0) messages.push(`修复 ${res.data.fixed.length} 本`)
      if (res.data.added?.length > 0) messages.push(`新增 ${res.data.added.length} 本`)
      if (res.data.removed?.length > 0) messages.push(`删除无效书籍 ${res.data.removed.length} 本`)
      if (res.data.errors?.length > 0) messages.push(`${res.data.errors.length} 本出错`)
      if (res.data.audio_fixed?.length > 0) messages.push(`自动修复语音配置 ${res.data.audio_fixed.length} 本`)
      
      if (messages.length === 0) {
        showNotify({ type: 'success', message: '无需修复，数据已同步' })
      } else {
        showNotify({ type: 'success', message: messages.join('，') })
      }
      
      if (res.data.audio_fixed?.length > 0 || res.data.audio_errors?.length > 0) {
        audioFixedList.value = res.data.audio_fixed || []
        audioErrorList.value = res.data.audio_errors || []
        showAudioErrorDialog.value = true
      }
    } catch (error: any) {
      closeToast()
      showNotify({ type: 'danger', message: error.response?.data?.detail || '同步失败' })
    }
  }).catch(() => {})
}

// 压缩书籍图片
const handleCompressImages = async () => {
  showConfirmDialog({
    title: '压缩书籍图片',
    message: '将扫描所有书籍，将jpg/jpeg/png/bmp格式图片压缩并转换为WebP格式，是否继续？'
  }).then(async () => {
    showLoadingToast({ message: '正在压缩图片...', forbidClick: true, duration: 0 })
    try {
      const res = await api.post('/books/compress-images')
      closeToast()
      const messages: string[] = []
      if (res.data.processed_books > 0) messages.push(`处理 ${res.data.processed_books} 本书籍`)
      if (res.data.converted_images > 0) messages.push(`转换 ${res.data.converted_images} 张图片`)
      if (res.data.skipped_images > 0) messages.push(`跳过 ${res.data.skipped_images} 张`)
      if (res.data.errors?.length > 0) messages.push(`${res.data.errors.length} 个错误`)
      
      if (messages.length === 0) {
        showNotify({ type: 'success', message: '所有图片已是WebP格式，无需转换' })
      } else {
        showNotify({ type: 'success', message: messages.join('，') })
      }
    } catch (error: any) {
      closeToast()
      showNotify({ type: 'danger', message: error.response?.data?.detail || '压缩失败' })
    }
  }).catch(() => {})
}

// 预编译缓存
const handlePrecompile = async () => {
  try {
    const statusRes = await api.get('/books/precompile/status')
    const status = statusRes.data
    showConfirmDialog({
      title: '预编译缓存',
      message: `当前缓存: ${status.cached_books}/${status.total_books} 本 (${status.cache_percentage}%)\n\n预编译可加快书籍首次加载速度（约3500倍提升），是否开始编译未缓存的书籍？`
    }).then(async () => {
      showPrecompileProgress.value = true
      precompileProgress.value = 0
      precompileMessage.value = '正在准备...'
      precompileLoading.value = true
      try {
        const response = await fetch('/api/v1/books/precompile', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${authStore.token}` }
        })
        if (!response.ok) throw new Error(`请求失败: ${response.status}`)
        const reader = response.body?.getReader()
        const decoder = new TextDecoder()
        if (!reader) throw new Error('无法读取响应流')
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                precompileProgress.value = data.percentage || 0
                precompileMessage.value = data.message || ''
              } catch (e) {}
            }
          }
        }
        precompileLoading.value = false
        precompileMessage.value = '编译完成！'
        precompileProgress.value = 100
        await loadPrecompileStatus()
        setTimeout(() => {
          showPrecompileProgress.value = false
          showNotify({ type: 'success', message: '预编译完成' })
        }, 1500)
      } catch (error: any) {
        showPrecompileProgress.value = false
        precompileLoading.value = false
        showNotify({ type: 'danger', message: error.message || '预编译失败' })
      }
    }).catch(() => {})
  } catch (error) {}
}

// 补充翻译+中文语音
const handleSupplementAll = async () => {
  showConfirmDialog({
    title: '补充翻译+中文语音',
    message: '将检查所有书籍，补充缺少的翻译和中文语音（不会覆盖已有内容），是否继续？'
  }).then(async () => {
    showSupplementProgress.value = true
    supplementProgress.value = 0
    supplementMessage.value = '正在准备...'
    supplementLoading.value = true
    try {
      const response = await fetch('/api/v1/books/admin/books/supplement-all', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authStore.token}` }
      })
      if (!response.ok) throw new Error(`请求失败: ${response.status}`)
      currentSupplementReader = response.body?.getReader() as ReadableStreamDefaultReader<Uint8Array> | null
      const decoder = new TextDecoder()
      if (!currentSupplementReader) throw new Error('无法读取响应流')
      let buffer = ''
      while (true) {
        const { done, value } = await currentSupplementReader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              supplementProgress.value = data.percentage || 0
              supplementMessage.value = data.message || ''
            } catch (e) {}
          }
        }
      }
      currentSupplementReader = null
      supplementLoading.value = false
      supplementProgress.value = 100
      setTimeout(() => {
        showSupplementProgress.value = false
        showNotify({ type: 'success', message: '翻译和中文语音补充完成' })
      }, 1500)
    } catch (error: any) {
      currentSupplementReader = null
      showSupplementProgress.value = false
      supplementLoading.value = false
      showNotify({ type: 'danger', message: error.message || '补充失败' })
    }
  }).catch(() => {})
}

// 从音频修复弹窗点击编辑书籍
const handleEditBookFromAudioFix = async (bookId: string) => {
  showAudioErrorDialog.value = false
  
  // 加载书籍信息
  showLoadingToast({ message: '正在加载书籍...', forbidClick: true, duration: 0 })
  try {
    // 先获取标题
    const titleRes = await api.get<{ title: string }>(`/books/${encodeURIComponent(bookId)}`)
    currentEditBookId.value = bookId
    currentEditBookTitle.value = titleRes.data.title
    
    // 再获取内容
    const contentRes = await api.get<{ content: string }>(`/books/${encodeURIComponent(bookId)}/content`)
    currentEditBookContent.value = contentRes.data.content || ''
    
    closeToast()
    showBookEditDialog.value = true
  } catch (error: any) {
    closeToast()
    showNotify({ type: 'danger', message: error.response?.data?.detail || '加载书籍失败' })
  }
}

// 书籍编辑保存后处理
const handleBookEditSaved = () => {
  showBookEditDialog.value = false
  // 重新调用修复书籍数据，让用户可以继续修改其他书籍
  handleSyncBooks()
}

// 书籍编辑关闭后处理
const handleBookEditClosed = () => {
  showBookEditDialog.value = false
  // 重新调用修复书籍数据，让用户可以继续修改其他书籍
  handleSyncBooks()
}

onMounted(() => {
  loadPrecompileStatus()
})

defineExpose({
  save: async () => {
    // 管理员工具不需要保存
    return true
  }
})
</script>

<style lang="less" scoped>
.admin-tools-content {
  padding: 12px;
  padding-bottom: 80px;
}

.tool-icon {
  font-size: 20px;
  color: #1989fa;
  margin-right: 8px;
  width: 24px;
  text-align: center;
}
</style>
