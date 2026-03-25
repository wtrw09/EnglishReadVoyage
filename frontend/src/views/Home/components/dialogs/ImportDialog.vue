<template>
  <van-dialog
    v-model:show="visible"
    title="导入书籍"
    :show-confirm-button="false"
    :show-cancel-button="false"
    :close-on-click-overlay="!isImporting"
    width="320px"
    @closed="onClosed"
  >
    <div class="import-dialog-content">
      <!-- 拖放区域 -->
      <div
        class="drop-zone"
        :class="{ 'drag-over': isDragOver, 'has-file': hasFile }"
        @dragenter.prevent="isDragOver = true"
        @dragover.prevent="isDragOver = true"
        @dragleave.prevent="isDragOver = false"
        @drop.prevent="onDrop"
        @click="triggerFileSelect"
      >
        <template v-if="hasFile">
          <van-icon name="description" size="40" color="#1989fa" />
          <p class="file-name">
            {{ selectedFiles.length > 0 ? `已选择 ${selectedFiles.length} 个文件` : selectedFile?.name }}
          </p>
          <p class="file-hint">点击更换文件</p>
        </template>
        <template v-else>
          <van-icon name="plus" size="40" color="#969799" />
          <p>拖拽MD或ZIP文件到这里，或点击选择</p>
          <p class="hint">支持 .md 和 .zip 格式，支持多选MD文件批量导入</p>
        </template>
      </div>

      <!-- 隐藏的文件输入 -->
      <input
        ref="fileInputRef"
        type="file"
        accept=".md,.zip"
        hidden
        multiple
        @change="onFileChange"
      />

      <!-- 上传/导入进度 -->
      <div v-if="showProgress" class="import-progress">
        <van-progress
          :percentage="progressPercentage"
          :stroke-width="8"
          :show-pivot="true"
        />
        <p class="import-status">{{ statusText }}</p>
      </div>

      <!-- 操作按钮 -->
      <div class="import-actions">
        <van-button
          type="primary"
          size="large"
          :disabled="!canStartImport"
          :loading="isImporting"
          @click="onConfirm"
        >
          {{ buttonText }}
        </van-button>
      </div>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  show: boolean
  isImporting: boolean
  importCompleted: boolean
  uploadProgress: number
  importProgress: number
  uploadStatus: string
  importStatus: string
  selectedFile: File | null
  selectedFiles: File[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'fileSelect': [files: FileList | null]
  'fileDrop': [event: DragEvent]
  'confirm': []
  'closed': []
}>()

// 本地状态
const isDragOver = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

// 计算属性
const visible = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value)
})

const hasFile = computed(() => {
  return props.selectedFile !== null || props.selectedFiles.length > 0
})

const showProgress = computed(() => {
  return props.isImporting || props.importCompleted || props.uploadProgress > 0
})

const progressPercentage = computed(() => {
  if (props.isImporting && props.selectedFiles.length > 0) {
    // 批量导入模式，显示导入进度
    return props.importProgress
  }
  // 单文件模式，显示上传或导入进度
  return props.uploadProgress > 0 ? props.uploadProgress : props.importProgress
})

const statusText = computed(() => {
  if (props.isImporting) {
    return props.uploadProgress > 0 ? props.uploadStatus : props.importStatus
  }
  return props.importStatus
})

const canStartImport = computed(() => {
  return hasFile.value && !props.isImporting
})

const buttonText = computed(() => {
  if (props.isImporting) {
    return props.uploadProgress > 0 ? '上传中...' : '导入中...'
  }
  if (props.importCompleted) {
    return '关闭'
  }
  return '开始导入'
})

// 方法
const triggerFileSelect = () => {
  if (!props.isImporting) {
    fileInputRef.value?.click()
  }
}

const onFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  emit('fileSelect', target.files)
  // 清空input，允许重复选择同一文件
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const onDrop = (event: DragEvent) => {
  isDragOver.value = false
  emit('fileDrop', event)
}

const onConfirm = () => {
  if (props.importCompleted) {
    visible.value = false
  } else {
    emit('confirm')
  }
}

const onClosed = () => {
  emit('closed')
}
</script>

<style scoped>
.import-dialog-content {
  padding: 16px;
  max-height: 70vh;
  overflow-y: auto;
}

.drop-zone {
  border: 2px dashed #dcdee0;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #f7f8fa;
}

.drop-zone:hover {
  border-color: #1989fa;
  background: #f0f8ff;
}

.drop-zone.drag-over {
  border-color: #1989fa;
  background: #e6f7ff;
}

.drop-zone.has-file {
  border-style: solid;
  border-color: #1989fa;
  background: #e6f7ff;
}

.drop-zone p {
  margin: 10px 0 0;
  color: #646566;
  font-size: 14px;
}

.drop-zone .hint {
  font-size: 12px;
  color: #969799;
}

.drop-zone .file-name {
  color: #1989fa;
  font-weight: 500;
  word-break: break-all;
}

.drop-zone .file-hint {
  font-size: 12px;
  color: #969799;
}

.import-progress {
  margin-top: 20px;
}

.import-status {
  margin-top: 8px;
  text-align: center;
  font-size: 12px;
  color: #969799;
}

.import-actions {
  margin-top: 20px;
}
</style>
