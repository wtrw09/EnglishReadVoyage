import { ref } from 'vue'
import type { Book, BookGroup } from '@/types'

export interface ContextMenuPosition {
  x: number
  y: number
}

export function useContextMenu() {
  // 书籍右键菜单状态
  const showBookContextMenu = ref(false)
  const bookContextMenuPos = ref<ContextMenuPosition>({ x: 0, y: 0 })
  const contextMenuBook = ref<Book | null>(null)
  const contextMenuGroupId = ref(0)

  // 分组右键菜单状态
  const showGroupContextMenu = ref(false)
  const groupContextMenuPos = ref<ContextMenuPosition>({ x: 0, y: 0 })
  const contextMenuGroup = ref<BookGroup | null>(null)

  // 显示书籍右键菜单
  const showBookMenu = (book: Book, groupId: number, event?: MouseEvent) => {
    contextMenuBook.value = book
    contextMenuGroupId.value = groupId

    if (event) {
      // 计算菜单位置，确保不超出屏幕
      const menuWidth = 150
      const menuHeight = 280
      const x = Math.min(event.clientX, window.innerWidth - menuWidth)
      const y = Math.min(event.clientY, window.innerHeight - menuHeight)
      bookContextMenuPos.value = { x, y }
    } else {
      // 居中显示
      bookContextMenuPos.value = {
        x: (window.innerWidth - 150) / 2,
        y: (window.innerHeight - 280) / 2
      }
    }

    showBookContextMenu.value = true
  }

  // 关闭书籍右键菜单
  const closeBookMenu = () => {
    showBookContextMenu.value = false
  }

  // 显示分组右键菜单
  const showGroupMenu = (group: BookGroup, event: MouseEvent) => {
    contextMenuGroup.value = group

    // 计算菜单位置，确保不超出屏幕
    const menuWidth = 150
    const menuHeight = 120
    const x = Math.min(event.clientX, window.innerWidth - menuWidth)
    const y = Math.min(event.clientY, window.innerHeight - menuHeight)
    groupContextMenuPos.value = { x, y }

    showGroupContextMenu.value = true
  }

  // 关闭分组右键菜单
  const closeGroupMenu = () => {
    showGroupContextMenu.value = false
  }

  // 获取当前上下文书籍
  const getContextBook = (): Book | null => {
    return contextMenuBook.value
  }

  // 获取当前上下文分组
  const getContextGroup = (): BookGroup | null => {
    return contextMenuGroup.value
  }

  return {
    // 状态
    showBookContextMenu,
    bookContextMenuPos,
    contextMenuBook,
    contextMenuGroupId,
    showGroupContextMenu,
    groupContextMenuPos,
    contextMenuGroup,

    // 方法
    showBookMenu,
    closeBookMenu,
    showGroupMenu,
    closeGroupMenu,
    getContextBook,
    getContextGroup
  }
}
