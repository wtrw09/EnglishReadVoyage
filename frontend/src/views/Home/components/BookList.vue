/**
 * BookList.vue - 书籍列表组件
 *
 * 功能：分组显示书籍列表
 * - 可折叠分组（van-collapse）
 * - 多选模式和全选支持
 * - 分组右键菜单触发
 */
<template>
  <!-- 使用van-collapse实现可折叠分组 -->
  <van-collapse v-model="activeNames" accordion>
    <van-collapse-item
      v-for="group in filteredGroups"
      :key="group.id"
      :name="group.id"
      class="group-item"
      v-show="group.name !== '未分组' || group.books.length > 0"
    >
      <!-- 分组标题 -->
      <template #title>
        <div
          class="group-title"
          @contextmenu.prevent="showGroupContextMenu($event, group)"
          @longpress="showGroupContextMenu($event, group)"
        >
          <!-- 分组选择框（仅在多选模式下显示） -->
          <div v-if="isMultiSelect" class="group-checkbox">
            <input
              type="checkbox"
              :checked="isGroupAllSelected(group.id)"
              @change.stop="toggleGroupSelect(group.id)"
            />
          </div>
          <span class="group-name">{{ group.name }}</span>
          <span class="book-count">({{ group.books.length }})</span>
        </div>
      </template>

      <!-- 分组右侧操作 -->
      <template #right-icon>
        <div class="group-actions" @click.stop>
          <van-button
            type="primary"
            size="small"
            @click="$emit('import', group.id)"
            class="group-import-btn"
            v-if="isAdmin"
          >
            <i class="fas fa-plus"></i>
          </van-button>
        </div>
      </template>

      <!-- 书籍列表 -->
      <div class="book-list">
        <BookItem
          v-for="book in getVisibleBooks(group)"
          :key="book.id"
          :book="book"
          :group-id="group.id"
          :is-selected="selectedBooks.includes(book.id)"
          :show-checkbox="isMultiSelect"
          :disabled="isMultiSelect"
          :is-landscape="isLandscape"
          :cover-url="getBookCover(book)"
          :cover-error-map="coverErrorMap"
          v-model:swipe-cell-refs="swipeCellRefs"
          @click="handleBookClick"
          @contextmenu="handleBookContextMenu"
          @checkbox-change="toggleBookSelect"
          @cover-click="(book) => handleCoverClick(book, group.id)"
          @swipe-open="handleSwipeOpen"
          @mark-read="handleMarkBookAsRead"
        />
        <div v-if="getVisibleBooks(group).length === 0" class="empty-tip">
          {{ hideReadBooksMap[group.id] ? '该分组下暂无未读书籍' : '该分组下暂无书籍' }}
        </div>
      </div>
    </van-collapse-item>
  </van-collapse>

  <!-- 批量操作栏 -->
  <div v-if="isMultiSelect" class="batch-actions">
    <van-button type="primary" size="small" plain @click="$emit('select-all')">
      {{ isAllSelected ? '取消全选' : '全选' }}
    </van-button>
    <van-button type="primary" size="small" plain @click="$emit('select-current-group')">
      全选当前分组
    </van-button>
    <van-button type="primary" size="small" @click="$emit('export')" :disabled="selectedBooks.length === 0">
      <i class="fas fa-download" style="margin-right: 4px;"></i>
      导出 ({{ selectedBooks.length }})
    </van-button>
    <van-button type="primary" size="small" @click="$emit('move')" :disabled="selectedBooks.length === 0">
      移动到 ({{ selectedBooks.length }})
    </van-button>
    <van-button type="danger" size="small" v-if="isAdmin" @click="$emit('batch-delete')" :disabled="selectedBooks.length === 0">
      删除 ({{ selectedBooks.length }})
    </van-button>
    <van-button size="small" @click="$emit('cancel-multi-select')">
      取消
    </van-button>
  </div>

  <!-- 空状态 -->
  <van-empty
    v-if="filteredGroups.length === 0 && !loading"
    description="暂无书籍"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BookItem from './BookItem.vue'
import type { Book, BookGroup } from '../types'

const props = defineProps<{
  groups: BookGroup[]
  loading: boolean
  searchText: string
  activeNames: number | string | null
  isMultiSelect: boolean
  selectedBooks: string[]
  hideReadBooksMap: Record<number, boolean>
  coverErrorMap: Record<string, boolean>
  isAdmin: boolean
  isLandscape: boolean
}>()

const emit = defineEmits<{
  (e: 'update:activeNames', value: number | string | null): void
  (e: 'update:selectedBooks', value: string[]): void
  (e: 'import', groupId: number): void
  (e: 'select-all'): void
  (e: 'select-current-group'): void
  (e: 'export'): void
  (e: 'move'): void
  (e: 'batch-delete'): void
  (e: 'cancel-multi-select'): void
  (e: 'book-click', bookId: string, groupId: number): void
  (e: 'book-contextmenu', event: MouseEvent, book: Book, groupId: number): void
  (e: 'group-contextmenu', event: MouseEvent, group: BookGroup): void
  (e: 'mark-read', bookId: string, isRead: number): void
}>()

// swipe-cell 组件引用
const swipeCellRefs = defineModel<Record<string, any>>('swipeCellRefs', { default: () => ({}) })

// 计算属性
const activeNames = computed({
  get: () => props.activeNames ?? undefined,
  set: (value) => emit('update:activeNames', value ?? null)
})

const selectedBooks = computed({
  get: () => props.selectedBooks,
  set: (value) => emit('update:selectedBooks', value)
})

// 过滤后的分组
const filteredGroups = computed(() => {
  const groups = props.groups.filter(group =>
    group.name !== '未分组' || group.books.length > 0
  )

  if (!props.searchText.trim()) {
    return groups
  }

  const keyword = props.searchText.toLowerCase().trim()
  return groups.map(group => ({
    ...group,
    books: group.books.filter(book =>
      book.title.toLowerCase().includes(keyword)
    )
  })).filter(group => group.books.length > 0)
})

// 是否已全选
const isAllSelected = computed(() => {
  const allIds = getAllVisibleBookIds()
  return allIds.length > 0 && allIds.every(id => props.selectedBooks.includes(id))
})

// 获取所有可见书籍ID
const getAllVisibleBookIds = (): string[] => {
  const ids: string[] = []
  for (const group of filteredGroups.value) {
    const visibleBooks = getVisibleBooks(group)
    for (const book of visibleBooks) {
      ids.push(book.id)
    }
  }
  return ids
}

// 获取可见的书籍
const getVisibleBooks = (group: BookGroup): Book[] => {
  if (props.hideReadBooksMap[group.id]) {
    return group.books.filter(book => !book.is_read)
  }
  return group.books
}

// 获取书籍封面
const getBookCover = (book: Book): string => {
  if (book.cover_path) {
    const timestamp = Date.now()
    return book.cover_path.includes('?') ? `${book.cover_path}&t=${timestamp}` : `${book.cover_path}?t=${timestamp}`
  }
  if (props.coverErrorMap[book.id]) {
    return ''
  }
  return ''
}

// 判断某个分组是否已全选
const isGroupAllSelected = (groupId: number): boolean => {
  const group = filteredGroups.value.find(g => g.id === groupId)
  if (!group) return false
  const visibleBooks = getVisibleBooks(group)
  if (visibleBooks.length === 0) return false
  return visibleBooks.every(book => props.selectedBooks.includes(book.id))
}

// 切换书籍选中
const toggleBookSelect = (bookId: string) => {
  const index = props.selectedBooks.indexOf(bookId)
  if (index === -1) {
    selectedBooks.value = [...props.selectedBooks, bookId]
  } else {
    selectedBooks.value = props.selectedBooks.filter(id => id !== bookId)
  }
}

// 切换分组选择
const toggleGroupSelect = (groupId: number) => {
  const group = filteredGroups.value.find(g => g.id === groupId)
  if (!group) return

  const visibleBooks = getVisibleBooks(group)
  const groupBookIds = visibleBooks.map(b => b.id)
  const isCurrentlyAllSelected = isGroupAllSelected(groupId)

  if (isCurrentlyAllSelected) {
    selectedBooks.value = props.selectedBooks.filter(id => !groupBookIds.includes(id))
  } else {
    selectedBooks.value = [...new Set([...props.selectedBooks, ...groupBookIds])]
  }
}

// 事件处理
const handleBookClick = (book: Book, groupId: number) => {
  emit('book-click', book.id, groupId)
}

const handleBookContextMenu = (event: MouseEvent, book: Book, groupId: number) => {
  emit('book-contextmenu', event, book, groupId)
}

const showGroupContextMenu = (event: MouseEvent, group: BookGroup) => {
  emit('group-contextmenu', event, group)
}

// 封面点击也触发书籍打开
const handleCoverClick = (book: Book, groupId: number) => {
  emit('book-click', book.id, groupId)
}

const handleSwipeOpen = async (event: { position: 'left' | 'right' }, book: Book) => {
  const isRead = event.position === 'right' ? 1 : 0
  emit('mark-read', book.id, isRead)
}

const handleMarkBookAsRead = (bookId: string, isRead: number) => {
  emit('mark-read', bookId, isRead)
}
</script>

<style scoped>
.group-item {
  margin-bottom: 8px;
  background: #fff;
}

.group-title {
  display: flex;
  align-items: center;
}

.group-checkbox {
  display: flex;
  align-items: center;
  margin-right: 8px;
}

.group-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #1989fa;
}

.group-name {
  font-size: 16px;
  font-weight: 500;
}

.book-count {
  font-size: 12px;
  color: #969799;
  margin-left: 8px;
}

.group-actions {
  display: flex;
  align-items: center;
}

.group-import-btn {
  min-width: 28px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
}

.book-list {
  padding: 0;
}

.empty-tip {
  text-align: center;
  padding: 20px;
  color: #969799;
  font-size: 14px;
}

/* 批量操作栏 */
.batch-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  padding: 10px 16px;
  display: flex;
  justify-content: center;
  gap: 12px;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
  z-index: 100;
}
</style>
