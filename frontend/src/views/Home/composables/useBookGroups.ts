import { ref, computed } from 'vue'
import { showNotify, showConfirmDialog } from 'vant'
import { api } from '@/store/auth'
import type { Book, BookGroup } from '@/types'

export function useBookGroups() {
  // 状态
  const bookGroups = ref<BookGroup[]>([])
  const loading = ref(false)
  const searchText = ref('')
  const activeNames = ref<number>(0)

  // 隐藏已读书籍状态（按分组存储）
  const hideReadBooksMap = ref<Record<number, boolean>>({})

  // 封面错误缓存
  const coverErrorMap = ref<Record<string, boolean>>({})
  const coverCheckedBooks = ref<Set<string>>(new Set())

  // 计算属性：过滤后的分组
  const filteredGroups = computed(() => {
    const groups = bookGroups.value.filter(group =>
      group.name !== '未分组' || group.books.length > 0
    )

    if (!searchText.value.trim()) {
      return groups
    }

    const keyword = searchText.value.toLowerCase().trim()
    return groups.map(group => ({
      ...group,
      books: group.books.filter(book =>
        book.title.toLowerCase().includes(keyword)
      )
    })).filter(group => group.books.length > 0)
  })

  // 加载分组数据
  const loadGroups = async () => {
    loading.value = true
    try {
      // 清除封面错误缓存
      coverErrorMap.value = {}
      coverCheckedBooks.value.clear()

      const res = await api.get<BookGroup[]>('/categories/books/grouped')
      bookGroups.value = res.data

      // 默认展开第一个分组
      if (bookGroups.value.length > 0 && activeNames.value === 0) {
        activeNames.value = bookGroups.value[0].id
      }
    } catch (error) {
      console.error('加载分组失败:', error)
      showNotify({ type: 'danger', message: '加载分组失败' })
    } finally {
      loading.value = false
    }
  }

  // 获取可见的书籍（根据隐藏已读设置过滤）
  const getVisibleBooks = (group: BookGroup): Book[] => {
    if (hideReadBooksMap.value[group.id]) {
      return group.books.filter(book => !book.is_read)
    }
    return group.books
  }

  // 切换隐藏已读书籍状态
  const toggleHideReadBooks = async (groupId: number) => {
    hideReadBooksMap.value[groupId] = !hideReadBooksMap.value[groupId]

    try {
      await api.put('/settings/ui', {
        hide_read_books_map: hideReadBooksMap.value
      })
    } catch (error: any) {
      console.error('保存隐藏已读书籍设置失败:', error)
      showNotify({ type: 'danger', message: '保存设置失败', duration: 1500 })
    }
  }

  // 获取书籍封面
  const getBookCover = (book: Book): string => {
    if (book.cover_path) {
      const timestamp = Date.now()
      return book.cover_path.includes('?') ? `${book.cover_path}&t=${timestamp}` : `${book.cover_path}?t=${timestamp}`
    }

    if (coverErrorMap.value[book.id]) {
      return ''
    }

    if (coverCheckedBooks.value.has(book.id)) {
      return ''
    }

    return ''
  }

  // 处理封面加载错误
  const handleCoverError = (bookId: string) => {
    coverErrorMap.value[bookId] = true
    coverCheckedBooks.value.add(bookId)
  }

  // 标记书籍已读状态
  const markBookAsRead = async (bookId: string, isRead: number) => {
    try {
      await api.post(`/categories/books/${bookId}/read-status`, { is_read: isRead })

      // 更新本地状态
      for (const group of bookGroups.value) {
        const book = group.books.find(b => b.id === bookId)
        if (book) {
          book.is_read = isRead
          break
        }
      }

      const statusText = isRead ? '已读' : '未读'
      showNotify({ type: 'success', message: `已标记为${statusText}`, duration: 1000 })
    } catch (error: any) {
      console.error('标记已读状态失败:', error)
      showNotify({ type: 'danger', message: '标记失败' })
    }
  }

  // 添加分组
  const addGroup = async (name: string): Promise<boolean> => {
    if (!name.trim()) {
      showNotify({ type: 'warning', message: '请输入分组名称' })
      return false
    }

    try {
      await api.post('/categories', { name: name.trim() })
      showNotify({ type: 'success', message: '分组创建成功', duration: 1500 })
      await loadGroups()
      return true
    } catch (error: any) {
      console.error('创建分组失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '创建分组失败' })
      return false
    }
  }

  // 重命名分组
  const renameGroup = async (groupId: number, newName: string): Promise<boolean> => {
    if (!newName.trim()) {
      showNotify({ type: 'warning', message: '请输入分组名称' })
      return false
    }

    try {
      await api.put(`/categories/${groupId}`, { name: newName.trim() })
      showNotify({ type: 'success', message: '分组名称修改成功', duration: 1500 })
      await loadGroups()
      return true
    } catch (error: any) {
      console.error('修改分组名称失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '修改失败' })
      return false
    }
  }

  // 删除分组
  const deleteGroup = async (groupId: number, groupName: string): Promise<boolean> => {
    try {
      await showConfirmDialog({
        title: '确认删除',
        message: `确定要删除分组"${groupName}"吗？分组内的书籍将自动移动到未分组。`
      })

      await api.delete(`/categories/${groupId}`)
      showNotify({ type: 'success', message: '分组删除成功，书籍已移至未分组', duration: 1500 })
      await loadGroups()
      return true
    } catch (error: any) {
      if (error !== 'cancel') {
        console.error('删除分组失败:', error)
        showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
      }
      return false
    }
  }

  // 重命名书籍
  const renameBook = async (bookId: string, newTitle: string, oldTitle: string): Promise<boolean> => {
    if (!newTitle.trim()) {
      showNotify({ type: 'warning', message: '请输入书籍名称' })
      return false
    }

    if (newTitle.trim() === oldTitle) {
      return true
    }

    try {
      const res = await api.put(`/books/${bookId}/rename`, { new_title: newTitle.trim() })
      showNotify({ type: 'success', message: '书籍重命名成功', duration: 1500 })

      // 更新本地状态
      if (res.data.new_id) {
        for (const group of bookGroups.value) {
          const book = group.books.find(b => b.id === bookId)
          if (book) {
            book.id = res.data.new_id
            book.title = res.data.new_title
            book.cover_path = res.data.new_cover_path
            break
          }
        }
      }

      // 强制清空封面缓存
      coverErrorMap.value = {}
      coverCheckedBooks.value.clear()
      await loadGroups()

      return true
    } catch (error: any) {
      console.error('重命名书籍失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '重命名失败' })
      return false
    }
  }

  // 删除书籍
  const deleteBook = async (bookId: string, bookTitle: string): Promise<boolean> => {
    try {
      await showConfirmDialog({
        title: '确认删除',
        message: `确定要删除《${bookTitle}》吗？此操作不可恢复！`
      })

      // 先从UI中移除
      bookGroups.value = bookGroups.value.map(group => ({
        ...group,
        books: group.books.filter(book => book.id !== bookId)
      })).filter(group => group.books.length > 0)

      await api.delete(`/books/${bookId}`)
      showNotify({ type: 'success', message: '删除成功', duration: 1500 })
      await loadGroups()
      return true
    } catch (error: any) {
      if (error !== 'cancel') {
        console.error('删除失败:', error)
        showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
        await loadGroups()
      }
      return false
    }
  }

  // 批量删除书籍
  const batchDeleteBooks = async (bookIds: string[]): Promise<boolean> => {
    if (bookIds.length === 0) return false

    try {
      await showConfirmDialog({
        title: '确认删除',
        message: `确定要删除选中的 ${bookIds.length} 本书籍吗？此操作不可恢复！`
      })

      // 先从UI中移除
      const deletedBookIds = new Set(bookIds)
      bookGroups.value = bookGroups.value.map(group => ({
        ...group,
        books: group.books.filter(book => !deletedBookIds.has(book.id))
      })).filter(group => group.books.length > 0)

      for (const bookId of bookIds) {
        await api.delete(`/books/${bookId}`)
      }

      showNotify({ type: 'success', message: '删除成功', duration: 1500 })
      await loadGroups()
      return true
    } catch (error: any) {
      if (error !== 'cancel') {
        console.error('删除失败:', error)
        showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
        await loadGroups()
      }
      return false
    }
  }

  // 移动书籍到分组
  const moveBooksToCategory = async (bookIds: string[], categoryId: number): Promise<boolean> => {
    try {
      for (const bookId of bookIds) {
        await api.post('/categories/books', {
          book_id: bookId,
          category_id: categoryId
        })
      }

      showNotify({ type: 'success', message: '移动成功', duration: 1500 })
      await loadGroups()
      return true
    } catch (error: any) {
      console.error('移动失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '移动失败' })
      return false
    }
  }

  return {
    // 状态
    bookGroups,
    loading,
    searchText,
    activeNames,
    hideReadBooksMap,
    filteredGroups,

    // 方法
    loadGroups,
    getVisibleBooks,
    toggleHideReadBooks,
    getBookCover,
    handleCoverError,
    markBookAsRead,
    addGroup,
    renameGroup,
    deleteGroup,
    renameBook,
    deleteBook,
    batchDeleteBooks,
    moveBooksToCategory
  }
}
