<template>
  <van-dialog
    v-model:show="visible"
    title="语音配置检查结果"
    confirm-button-text="我知道了"
    :close-on-click-overlay="false"
  >
    <div class="audio-error-dialog-content">
      <!-- 显示修复成功的信息 -->
      <div v-if="audioFixedList.length > 0">
        <p class="audio-success-hint">以下书籍已自动修复：</p>
        <div
          v-for="item in audioFixedList"
          :key="item.title"
          class="audio-success-item"
        >
          <div
            class="audio-success-title"
            :class="{ 'clickable': (item.book_id || props.bookId) && (item.fixed_fields?.length > 0 || item.warnings?.length > 0) }"
            @click.stop.prevent="handleTitleClick(item)"
          >
            <span class="title-text">《{{ item.title }}》</span>
            <van-icon v-if="(item.book_id || props.bookId) && (item.fixed_fields?.length > 0 || item.warnings?.length > 0)" name="edit" class="edit-icon" />
          </div>
          <!-- 修复成功的字段（绿色） -->
          <ul v-if="item.fixed_fields?.length > 0" class="audio-success-details">
            <li v-for="field in item.fixed_fields" :key="field">{{ field }}</li>
          </ul>
          <!-- 警告信息（黄色） -->
          <ul v-if="item.warnings?.length > 0" class="audio-success-details">
            <li v-for="warning in item.warnings" :key="warning" class="audio-warning">{{ warning }}</li>
          </ul>
        </div>
      </div>
      <!-- 显示错误信息 -->
      <div v-if="audioErrorList.length > 0">
        <p class="audio-error-hint">以下书籍需要手动处理：</p>
        <div
          v-for="item in audioErrorList"
          :key="item.title"
          class="audio-error-item"
        >
          <!-- 调试信息：显示 book_id -->
          <div class="audio-error-title" :class="{ 'clickable': item.book_id }" @click.stop="item.book_id && emit('edit-book', item.book_id)">
            <span class="title-text">《{{ item.title }}》</span>
            <van-icon v-if="item.book_id" name="edit" class="edit-icon" />
          </div>
          <!-- 调试用：显示 book_id -->
          <div style="font-size: 10px; color: #999; margin-top: 2px;">book_id: {{ item.book_id || 'undefined (无法编辑)' }}</div>
          <ul class="audio-error-issues">
            <li v-for="issue in item.issues" :key="issue">{{ issue }}</li>
          </ul>
        </div>
      </div>
      <!-- 无问题提示 -->
      <div v-if="audioFixedList.length === 0 && audioErrorList.length === 0" class="audio-no-issue">
        <van-icon name="passed" size="32" color="#07c160" />
        <p>语音配置正常，无需修复</p>
      </div>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface AudioFixedItem {
  book_id?: string
  title: string
  fixed_fields: string[]
  warnings: string[]
}

interface AudioErrorItem {
  book_id?: string
  title: string
  issues: string[]
}

interface Props {
  show: boolean
  fixedList: AudioFixedItem[]
  errorList: AudioErrorItem[]
  bookId?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'edit-book', bookId: string): void
}>()

const visible = ref(props.show)
const audioFixedList = ref<AudioFixedItem[]>([])
const audioErrorList = ref<AudioErrorItem[]>([])

// 监听 props 变化
watch(() => props.show, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:show', val)
})

watch(() => props.fixedList, (val) => {
  audioFixedList.value = val
}, { immediate: true })

watch(() => props.errorList, (val) => {
  audioErrorList.value = val
  // 调试：打印 errorList 的详细信息
  console.log('【AudioFixDialog】audioErrorList:', JSON.stringify(val, null, 2))
}, { immediate: true })

// 点击书籍标题，触发编辑事件
const handleTitleClick = (item: AudioFixedItem) => {
  // 优先使用 item 中的 book_id，其次使用 props.bookId
  const bookId = item.book_id || props.bookId
  if (bookId && (item.fixed_fields?.length > 0 || item.warnings?.length > 0)) {
    emit('edit-book', bookId)
  }
}
</script>

<style lang="less" scoped>
.audio-error-dialog-content {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.audio-success-hint {
  font-size: 13px;
  color: #666;
  margin: 0 0 10px;
  line-height: 1.5;
}

.audio-success-item {
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #f0fff4;
  border-left: 3px solid #07c160;
  border-radius: 4px;
}

.audio-success-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  user-select: none;
  
  .title-text {
    flex: 1;
  }
  
  &.clickable {
    cursor: pointer;
    transition: all 0.2s;
    
    .title-text {
      color: #1890ff !important;
      text-decoration: underline;
    }
    
    &:hover .title-text {
      color: #40a9ff !important;
    }
    
    &:active .title-text {
      color: #096dd9 !important;
    }
  }
  
  .edit-icon {
    font-size: 14px;
    opacity: 0.6;
  }
}

.audio-success-details {
  margin: 0;
  padding-left: 18px;
}

.audio-success-details li {
  font-size: 12px;
  color: #07c160;
  line-height: 1.6;
}

.audio-success-details li.audio-warning {
  color: #ff976a;
}

.audio-error-hint {
  font-size: 13px;
  color: #666;
  margin: 0 0 10px;
  line-height: 1.5;
}

.audio-error-item {
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #fff8f8;
  border-left: 3px solid #ee0a24;
  border-radius: 4px;
}

.audio-error-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  user-select: none;

  .title-text {
    flex: 1;
  }

  &.clickable {
    cursor: pointer;
    transition: all 0.2s;

    .title-text {
      color: #1890ff !important;
      text-decoration: underline;
    }

    &:hover .title-text {
      color: #40a9ff !important;
    }

    &:active .title-text {
      color: #096dd9 !important;
    }
  }

  .edit-icon {
    font-size: 14px;
    opacity: 0.6;
  }
}

.audio-error-issues {
  margin: 0;
  padding-left: 18px;
}

.audio-error-issues li {
  font-size: 12px;
  color: #ee0a24;
  line-height: 1.6;
}

.audio-no-issue {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 0;
  color: #666;

  p {
    margin: 10px 0 0;
    font-size: 14px;
  }
}
</style>
