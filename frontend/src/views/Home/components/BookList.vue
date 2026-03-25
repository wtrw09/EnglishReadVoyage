<template>
  <div class="book-list">
    <van-swipe-cell
      v-for="book in books"
      :key="book.id"
      :disabled="isMultiSelect"
      :stop-propagation="true"
      @open="(pos: any) => onSwipeOpen(pos, book)"
    >
      <div
        class="book-item"
        :class="{ 'selected': isSelected(book.id), 'is-read': book.is_read }"
        @click="onClick(book)"
        @contextmenu.prevent="(e) => onContextMenu(book, e)"
      >
        <div v-if="isMultiSelect" class="book-checkbox" @click.stop>
          <input
            type="checkbox"
            :checked="isSelected(book.id)"
            @change="onToggleSelect(book.id)"
          />
        </div>
        <div class="book-cover">
          <img
            v-if="book.cover_path"
            :src="getCoverUrl(book.cover_path)"
            :alt="book.title"
            loading="lazy"
            decoding="async"
            @error="onCoverError(book.id)"
          />
          <van-icon v-else name="book" size="32" color="#dcdee0" />
          <div v-if="book.is_read" class="read-badge">
            <van-icon name="success" size="12" color="#fff" />
          </div>
        </div>
        <div class="book-info">
          <span class="book-title">{{ book.title }}</span>
          <span class="book-meta">Level: {{ book.level }} | {{ book.page_count }} 页</span>
        </div>
      </div>

      <template #left>
        <div class="swipe-action unread" @click="onSwipeUnread(book.id)">
          <van-icon name="cross" size="24" color="#fff" />
          <span>未读</span>
        </div>
      </template>

      <template #right>
        <div class="swipe-action read" @click="onSwipeRead(book.id)">
          <van-icon name="success" size="24" color="#fff" />
          <span>已读</span>
        </div>
      </template>
    </van-swipe-cell>
    <div v-if="books.length === 0" class="empty-tip">
      该分组下暂无书籍
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Book } from '@/types'

interface Props {
  books: Book[]
  isMultiSelect: boolean
  selectedBooks: string[]
  groupId: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'toggle-select': [bookId: string]
  'click': [book: Book]
  'contextmenu': [book: Book, event: MouseEvent]
  'swipe-read': [bookId: string]
  'swipe-unread': [bookId: string]
}>()

const isSelected = (bookId: string): boolean => {
  return props.selectedBooks.includes(bookId)
}

const getCoverUrl = (coverPath: string): string => {
  const timestamp = Date.now()
  return coverPath.includes('?') ? `${coverPath}&t=${timestamp}` : `${coverPath}?t=${timestamp}`
}

const onToggleSelect = (bookId: string) => {
  emit('toggle-select', bookId)
}

const onClick = (book: Book) => {
  emit('click', book)
}

const onContextMenu = (book: Book, event: MouseEvent) => {
  emit('contextmenu', book, event)
}

const onSwipeOpen = (pos: { position: 'left' | 'right' }, book: Book) => {
  if (pos.position === 'left') {
    emit('swipe-unread', book.id)
  } else {
    emit('swipe-read', book.id)
  }
}

const onSwipeRead = (bookId: string) => {
  emit('swipe-read', bookId)
}

const onSwipeUnread = (bookId: string) => {
  emit('swipe-unread', bookId)
}

const onCoverError = (_bookId: string) => {
  // 封面加载失败处理 - 暂不需要额外操作
}
</script>

<style scoped>
.book-list {
  padding: 0;
}

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
  width: 60px;
  height: 80px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.book-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
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

.empty-tip {
  text-align: center;
  padding: 20px;
  color: #969799;
  font-size: 14px;
}

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
