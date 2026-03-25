<template>
  <van-dialog
    v-model:show="visible"
    title="修改封面"
    show-cancel-button
    @confirm="onConfirm"
    @cancel="onCancel"
  >
    <div class="cover-dialog-content">
      <!-- 预览 -->
      <div class="cover-preview">
        <img v-if="previewImage" :src="previewImage" alt="封面预览" />
        <van-icon v-else name="book" size="60" color="#dcdee0" />
      </div>

      <!-- 操作按钮 -->
      <div class="cover-actions">
        <van-button type="primary" size="small" @click="triggerUpload">
          上传封面
        </van-button>
        <van-button size="small" @click="onOpenPicker">
          从书籍中选择
        </van-button>
        <van-button size="small" @click="onUseDefault">
          默认封面
        </van-button>
      </div>

      <input
        ref="fileInputRef"
        type="file"
        accept="image/*"
        hidden
        @change="onFileSelected"
      />
    </div>
  </van-dialog>

  <!-- 图片选择器 -->
  <van-popup v-model:show="showPicker" position="bottom" round>
    <div class="cover-picker">
      <div class="cover-picker-title">选择图片作为封面</div>
      <div class="cover-picker-content">
        <div v-if="images.length > 0" class="cover-picker-grid">
          <div
            v-for="img in images"
            :key="img"
            class="cover-picker-item"
            :class="{ selected: selectedImage === img }"
            @click="onSelectImage(img)"
          >
            <img :src="img" />
          </div>
        </div>
        <van-empty v-else description="该书籍没有可用的图片资源" />
      </div>
      <div class="cover-picker-footer">
        <van-button
          type="primary"
          block
          @click="onConfirmPicker"
          :disabled="images.length === 0"
        >
          确定
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Props {
  show: boolean
  previewImage: string
  images: string[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'update:previewImage': [value: string]
  'upload': [file: File]
  'confirm': [imageUrl: string]
}>()

// 本地状态
const showPicker = ref(false)
const selectedImage = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

// 计算属性
const visible = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value)
})

// 监听previewImage变化
watch(() => props.previewImage, (newValue) => {
  if (!newValue) {
    selectedImage.value = ''
  }
}, { immediate: true })

// 方法
const triggerUpload = () => {
  fileInputRef.value?.click()
}

const onFileSelected = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    emit('upload', file)
  }
  // 清空input
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const onOpenPicker = () => {
  showPicker.value = true
}

const onSelectImage = (img: string) => {
  selectedImage.value = img
}

const onConfirmPicker = () => {
  if (selectedImage.value) {
    emit('update:previewImage', selectedImage.value)
  }
  showPicker.value = false
}

const onUseDefault = () => {
  emit('update:previewImage', '')
}

const onConfirm = () => {
  emit('confirm', props.previewImage)
}

const onCancel = () => {
  // 重置预览
  selectedImage.value = ''
}
</script>

<style scoped>
.cover-dialog-content {
  padding: 16px;
}

.cover-preview {
  width: 120px;
  height: 160px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  border-radius: 8px;
  overflow: hidden;
}

.cover-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cover-picker {
  padding: 16px;
  max-height: 60vh;
  display: flex;
  flex-direction: column;
}

.cover-picker-title {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 12px;
  text-align: center;
  flex-shrink: 0;
}

.cover-picker-content {
  flex: 1;
  overflow-y: auto;
  min-height: 150px;
  max-height: 40vh;
}

.cover-picker-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.cover-picker-footer {
  flex-shrink: 0;
  margin-top: 12px;
}

.cover-picker-item {
  aspect-ratio: 1;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
}

.cover-picker-item.selected {
  border-color: #1989fa;
}

.cover-picker-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
