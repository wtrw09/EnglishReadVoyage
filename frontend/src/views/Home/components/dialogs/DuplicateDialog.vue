<template>
  <van-dialog
    v-model:show="visible"
    title="发现重复书籍"
    :show-confirm-button="false"
    :show-cancel-button="false"
    :close-on-click-overlay="false"
  >
    <div class="duplicate-dialog-content">
      <p class="duplicate-hint">
        ZIP文件中共 {{ result.total_books }} 本书籍，
        其中 {{ result.duplicate_books?.length || 0 }} 本已存在，
        {{ result.new_books?.length || 0 }} 本为新书籍
      </p>

      <!-- 重复书籍列表 -->
      <div v-if="result.duplicate_books?.length > 0" class="duplicate-section">
        <p class="duplicate-section-title">已存在书籍（请选择要覆盖的）：</p>
        <div class="duplicate-list">
          <div
            v-for="book in result.duplicate_books"
            :key="book.book_id"
            class="duplicate-item selectable"
            @click="toggleSelect(book.book_id)"
          >
            <div class="duplicate-checkbox">
              <input
                type="checkbox"
                :checked="selectedBooks.includes(book.book_id)"
                @click.stop
                @change="toggleSelect(book.book_id)"
              />
            </div>
            <span class="duplicate-title">《{{ book.title }}》</span>
            <span class="duplicate-status">已存在</span>
          </div>
        </div>
        <div class="duplicate-select-all">
          <van-button type="primary" size="mini" plain @click="selectAll">
            全选
          </van-button>
          <van-button type="default" size="mini" plain @click="clearAll">
            清空
          </van-button>
        </div>
      </div>

      <!-- 新书籍列表 -->
      <div v-if="result.new_books?.length > 0" class="duplicate-section">
        <p class="duplicate-section-title">新书籍（将被导入）：</p>
        <div class="duplicate-list new-books">
          <div
            v-for="book in result.new_books"
            :key="book.book_id"
            class="duplicate-item"
          >
            <span class="duplicate-title">《{{ book.title }}》</span>
            <span class="duplicate-status new">新书籍</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="duplicate-actions">
        <van-button
          v-if="selectedBooks.length > 0"
          type="primary"
          size="small"
          @click="onImportSelected"
        >
          覆盖选中 ({{ selectedBooks.length }})
        </van-button>
        <template v-else>
          <van-button type="primary" size="small" @click="onOverwriteAll">
            覆盖全部
          </van-button>
          <van-button type="default" size="small" @click="onSkipAll">
            跳过全部
          </van-button>
        </template>
        <van-button size="small" @click="onCancel">
          取消
        </van-button>
      </div>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DuplicateCheckResult } from '@/types'

interface Props {
  show: boolean
  result: DuplicateCheckResult
  selectedBooks: string[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'update:selectedBooks': [value: string[]]
  'overwriteAll': []
  'skipAll': []
  'importSelected': []
  'cancel': []
}>()

// 计算属性
const visible = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value)
})

// 方法
const toggleSelect = (bookId: string) => {
  const index = props.selectedBooks.indexOf(bookId)
  let newSelection = [...props.selectedBooks]
  if (index === -1) {
    newSelection.push(bookId)
  } else {
    newSelection.splice(index, 1)
  }
  emit('update:selectedBooks', newSelection)
}

const selectAll = () => {
  const allIds = props.result.duplicate_books.map(b => b.book_id)
  emit('update:selectedBooks', allIds)
}

const clearAll = () => {
  emit('update:selectedBooks', [])
}

const onOverwriteAll = () => {
  emit('overwriteAll')
}

const onSkipAll = () => {
  emit('skipAll')
}

const onImportSelected = () => {
  emit('importSelected')
}

const onCancel = () => {
  visible.value = false
  emit('cancel')
}
</script>

<style scoped>
.duplicate-dialog-content {
  padding: 16px;
  max-height: 70vh;
  overflow-y: auto;
}

.duplicate-hint {
  margin-bottom: 12px;
  color: #646566;
  font-size: 14px;
}

.duplicate-section {
  margin-bottom: 16px;
}

.duplicate-section-title {
  font-size: 13px;
  color: #969799;
  margin-bottom: 8px;
  font-weight: 500;
}

.duplicate-list {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 8px;
}

.duplicate-list.new-books {
  background: #f7f8fa;
}

.duplicate-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
}

.duplicate-item:last-child {
  border-bottom: none;
}

.duplicate-item.selectable {
  cursor: pointer;
}

.duplicate-item.selectable:hover {
  background: #f7f8fa;
}

.duplicate-checkbox {
  margin-right: 8px;
  display: flex;
  align-items: center;
}

.duplicate-checkbox input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.duplicate-title {
  font-size: 14px;
  color: #333;
  flex: 1;
}

.duplicate-status {
  font-size: 12px;
  color: #ff976a;
  background: #fff5f0;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}

.duplicate-status.new {
  color: #07c160;
  background: #e8f5e9;
}

.duplicate-select-all {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  justify-content: flex-end;
}

.duplicate-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;
}
</style>
