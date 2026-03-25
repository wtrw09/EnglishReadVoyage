import { ref, computed } from 'vue'
import type { Book, BookGroup } from '@/types'

export interface UseBookSelectionOptions {
  getVisibleBooks: (group: BookGroup) => Book[]
}

export function useBookSelection(options: UseBookSelectionOptions) {
  const { getVisibleBooks } = options

  // 状态
  const isMultiSelect = ref(false)
  const selectedBooks = ref<string[]>([])
  const currentGroupId = ref(0)

  // 计算属性
  const isAllSelected = computed(() => {
    const allIds = getAllVisibleBookIds()
    return allIds.length > 0 && allIds.every(id => selectedBooks.value.includes(id))
  })

  const selectedCount = computed(() => selectedBooks.value.length)

  // 获取所有可见书籍ID
  const getAllVisibleBookIds = (): string[] => {
    // 注意：这里需要在实际使用时传入 groups
    return []
  }

  // 启用多选模式
  const enableMultiSelect = (initialBookId?: string, groupId?: number) => {
    isMultiSelect.value = true
    if (groupId !== undefined) {
      currentGroupId.value = groupId
    }
    if (initialBookId) {
      selectedBooks.value = [initialBookId]
    }
  }

  // 取消多选模式
  const cancelMultiSelect = () => {
    isMultiSelect.value = false
    selectedBooks.value = []
    currentGroupId.value = 0
  }

  // 切换书籍选中状态
  const toggleBookSelect = (bookId: string) => {
    const index = selectedBooks.value.indexOf(bookId)
    if (index === -1) {
      selectedBooks.value.push(bookId)
    } else {
      selectedBooks.value.splice(index, 1)
    }
  }

  // 判断书籍是否被选中
  const isBookSelected = (bookId: string): boolean => {
    return selectedBooks.value.includes(bookId)
  }

  // 全选/取消全选（传入当前所有可见书籍ID）
  const selectAllBooks = (allVisibleIds: string[]) => {
    if (isAllSelected.value) {
      selectedBooks.value = []
    } else {
      selectedBooks.value = [...allVisibleIds]
    }
  }

  // 全选指定分组的书籍
  const selectAllBooksInGroup = (group: BookGroup) => {
    const groupBookIds = getVisibleBooks(group).map(b => b.id)
    const newSelection = [...new Set([...selectedBooks.value, ...groupBookIds])]
    selectedBooks.value = newSelection
  }

  // 判断某个分组是否已全选
  const isGroupAllSelected = (group: BookGroup): boolean => {
    const visibleBooks = getVisibleBooks(group)
    if (visibleBooks.length === 0) return false
    return visibleBooks.every(book => selectedBooks.value.includes(book.id))
  }

  // 切换分组选择
  const toggleGroupSelect = (group: BookGroup) => {
    const visibleBooks = getVisibleBooks(group)
    const groupBookIds = visibleBooks.map(b => b.id)
    const isCurrentlyAllSelected = isGroupAllSelected(group)

    if (isCurrentlyAllSelected) {
      selectedBooks.value = selectedBooks.value.filter(id => !groupBookIds.includes(id))
    } else {
      selectedBooks.value = [...new Set([...selectedBooks.value, ...groupBookIds])]
    }
  }

  return {
    // 状态
    isMultiSelect,
    selectedBooks,
    currentGroupId,
    isAllSelected,
    selectedCount,

    // 方法
    enableMultiSelect,
    cancelMultiSelect,
    toggleBookSelect,
    isBookSelected,
    selectAllBooks,
    selectAllBooksInGroup,
    isGroupAllSelected,
    toggleGroupSelect
  }
}
