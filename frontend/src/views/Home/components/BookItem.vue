/**
 * BookItem.vue - 书籍列表项组件
 *
 * 功能：单个书籍的显示和交互
 * - 显示封面、标题、阅读进度
 * - 点击跳转阅读器/听书
 * - 长按/右键显示操作菜单
 * - 多选模式支持
 */
<template>
  <van-swipe-cell
    :ref="(el) => { if (el) swipeCellRefs[book.id] = el }"
    :disabled="disabled"
    :stop-propagation="true"
    @open="handleSwipeOpen"
  >
    <div
      class="book-item"
      :class="{ 'selected': isSelected, 'is-read': book.is_read }"
      @click="handleClick"
      @contextmenu.prevent="handleContextMenu"
      @longpress="handleContextMenu"
    >
      <!-- 多选复选框 -->
      <div v-if="showCheckbox" class="book-checkbox" @click.stop>
        <input
          type="checkbox"
          :checked="isSelected"
          @change="handleCheckboxChange"
        />
      </div>

      <!-- 封面图片 -->
      <div class="book-cover" :class="{ 'landscape': isLandscape }" @click.stop="handleCoverClick">
        <template v-if="coverUrl">
          <img
            :src="coverUrl"
            :alt="book.title"
            loading="lazy"
            decoding="async"
            @error="handleCoverError"
          />
        </template>
        <template v-else>
          <i class="fas fa-book" style="font-size: 32px; color: #dcdee0;"></i>
        </template>
        <!-- 已读标记 -->
        <div v-if="book.is_read" class="read-badge">
          <i class="fas fa-check" style="font-size: 12px; color: #fff;"></i>
        </div>
      </div>

      <!-- 书籍信息 -->
      <div class="book-info">
        <span class="book-title">{{ book.title }}</span>
        <span class="book-meta">Level: {{ book.level }} | {{ book.page_count }} 页</span>
      </div>
    </div>

    <!-- 左侧滑动：标记为未读 -->
    <template #left>
      <div class="swipe-action unread" @click="markAsRead(0)">
        <i class="fas fa-xmark" style="font-size: 24px; color: #fff;"></i>
        <span>未读</span>
      </div>
    </template>

    <!-- 右侧滑动：标记为已读 -->
    <template #right>
      <div class="swipe-action read" @click="markAsRead(1)">
        <i class="fas fa-check" style="font-size: 24px; color: #fff;"></i>
        <span>已读</span>
      </div>
    </template>
  </van-swipe-cell>
</template>

<script setup lang="ts">
import type { Book } from '../types'

const props = defineProps<{
  book: Book
  groupId: number
  isSelected?: boolean
  showCheckbox?: boolean
  disabled?: boolean
  isLandscape?: boolean
  coverUrl?: string
  coverErrorMap?: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'click', book: Book, groupId: number): void
  (e: 'contextmenu', event: MouseEvent, book: Book, groupId: number): void
  (e: 'checkbox-change', bookId: string): void
  (e: 'cover-click', book: Book): void
  (e: 'swipe-open', event: { position: 'left' | 'right' }, book: Book): void
  (e: 'mark-read', bookId: string, isRead: number): void
}>()

// swipe-cell 组件引用
const swipeCellRefs = defineModel<Record<string, any>>('swipeCellRefs', { default: () => ({}) })

const handleClick = () => {
  emit('click', props.book, props.groupId)
}

const handleContextMenu = (event: MouseEvent) => {
  emit('contextmenu', event, props.book, props.groupId)
}

const handleCheckboxChange = () => {
  emit('checkbox-change', props.book.id)
}

const handleCoverClick = () => {
  emit('cover-click', props.book)
}

const handleSwipeOpen = (event: { position: 'left' | 'right' }) => {
  emit('swipe-open', event, props.book)
}

const markAsRead = (isRead: number) => {
  emit('mark-read', props.book.id, isRead)
  // 关闭滑动菜单
  const swipeCell = swipeCellRefs.value[props.book.id]
  if (swipeCell && swipeCell.close) {
    swipeCell.close()
  }
}

const handleCoverError = (event: Event) => {
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
}
</script>

<style scoped>
.book-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid #f5f5f5;
  cursor: pointer;
}

.book-item:last-child {
  border-bottom: none;
}

.book-item:hover {
  background: #f7f8fa;
}

.book-item.selected {
  background: #e6f7ff;
}

.book-item.is-read {
  opacity: 0.7;
}

.book-item.is-read .book-title {
  text-decoration: line-through;
  color: #969799;
}

.book-checkbox {
  margin-right: 8px;
  display: flex;
  align-items: center;
}

.book-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.book-cover {
  position: relative;
  width: 60px;
  height: 80px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.book-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.book-cover.landscape {
  width: 80px;
  height: 60px;
}

.read-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  background: #07c160;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.book-info {
  flex: 1;
  margin-left: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.book-title {
  font-size: 15px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.book-meta {
  font-size: 12px;
  color: #969799;
  margin-top: 4px;
}

/* 滑动操作样式 */
.swipe-action {
  height: 100%;
  width: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  gap: 4px;
}

.swipe-action.unread {
  background: #ff976a;
}

.swipe-action.read {
  background: #07c160;
}
</style>
