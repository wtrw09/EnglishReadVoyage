<template>
  <!-- 修改封面对话框 -->
  <van-dialog
    :show="show"
    title="修改封面"
    show-cancel-button
    @confirm="handleSave"
    @update:show="(val: boolean) => emit('update:show', val)"
  >
    <div class="cover-dialog-content">
      <!-- 预览 -->
      <div class="cover-preview">
        <img v-if="previewCover" :src="previewCover" alt="封面预览" />
        <i v-else class="fas fa-book" style="font-size: 60px; color: #dcdee0;"></i>
      </div>

      <!-- 操作按钮 -->
      <div class="cover-actions">
        <van-button type="primary" size="small" @click="triggerCoverUpload">
          上传封面
        </van-button>
        <van-button size="small" @click="openCoverPicker">
          从书籍中选择
        </van-button>
        <van-button size="small" @click="useDefaultCover">
          默认封面
        </van-button>
      </div>

      <input
        ref="coverInput"
        type="file"
        accept="image/*"
        hidden
        @change="onCoverSelected"
      />
    </div>
  </van-dialog>

  <!-- 从md资源选择 -->
  <van-popup
    v-model:show="showPicker"
    position="bottom"
    round
  >
    <div class="cover-picker">
      <div class="cover-picker-title">选择图片作为封面</div>
      <div class="cover-picker-content">
        <div v-if="mdImages.length > 0" class="cover-picker-grid">
          <div
            v-for="img in mdImages"
            :key="img"
            class="cover-picker-item"
            :class="{ selected: selectedMdImage === img }"
            @click="selectMdImage(img)"
          >
            <img :src="img" />
          </div>
        </div>
        <van-empty v-else description="该书籍没有可用的图片资源" />
      </div>
      <div class="cover-picker-footer">
        <van-button type="primary" block @click="confirmMdImage" :disabled="mdImages.length === 0">确定</van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { useCover } from '../composables/useCover'

defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved'): void
}>()

const {
  coverInput,
  previewCover,
  showCoverPicker,
  mdImages,
  selectedMdImage,
  openCoverPicker,
  triggerCoverUpload,
  onCoverSelected,
  selectMdImage,
  useDefaultCover,
  saveCover,
} = useCover()

const showPicker = showCoverPicker

const handleSave = async () => {
  await saveCover()
  emit('saved')
}

const confirmMdImage = () => {
  if (selectedMdImage.value) {
    previewCover.value = selectedMdImage.value
  }
  showCoverPicker.value = false
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
