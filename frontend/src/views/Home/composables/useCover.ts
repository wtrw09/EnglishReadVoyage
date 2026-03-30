/**
 * 封面设置 Composable
 * 集中管理所有封面相关的状态和方法
 */
import { ref } from 'vue'
import { showNotify } from 'vant'
import { api } from '@/store/auth'
import type { Book } from '../types'

export const useCover = () => {
  // ========== 封面相关状态 ==========

  // 修改封面对话框显示状态
  const showCoverDialog = ref(false)

  // 封面文件输入引用
  const coverInput = ref<HTMLInputElement | null>(null)

  // 封面预览
  const previewCover = ref('')

  // 图片选择器显示状态
  const showCoverPicker = ref(false)

  // MD文件中的图片列表
  const mdImages = ref<string[]>([])

  // 选中的MD图片
  const selectedMdImage = ref('')

  // 当前操作的书籍
  const currentCoverBook = ref<Book | null>(null)

  // ========== 封面相关方法 ==========

  /**
   * 打开修改封面对话框
   */
  const openCoverDialog = async (book: Book) => {
    currentCoverBook.value = book
    showCoverDialog.value = true
    previewCover.value = getBookCover(book) || ''
    selectedMdImage.value = ''
    mdImages.value = []

    // 加载书籍信息以获取书籍路径
    try {
      const bookRes = await api.get<{ book_path: string }>(`/books/${book.id}`)
      const bookFolder = bookRes.data.book_path

      // 加载书籍内容
      const contentRes = await api.get<{ content: string }>(`/books/${book.id}/content-file`)
      const content = contentRes.data.content

      // 提取markdown中的所有图片
      const localImages: string[] = []
      const allImgMatches = content.match(/!\[([^\]]*)\]\(([^)]+)\)/g) || []

      for (const match of allImgMatches) {
        const urlMatch = match.match(/!\[([^\]]*)\]\(([^)]+)\)/)
        if (urlMatch) {
          const url = urlMatch[2]
          // 过滤掉http开头的远程图片
          if (!url.startsWith('http://') && !url.startsWith('https://')) {
            localImages.push(url)
          }
        }
      }

      // 转换相对路径为完整URL
      mdImages.value = localImages.map((url: string) => {
        let resultUrl = url

        if (url.startsWith('./assets/')) {
          resultUrl = `/books/${bookFolder}/assets/${url.replace('./assets/', '')}`
        } else if (url.startsWith('assets/')) {
          resultUrl = `/books/${bookFolder}/assets/${url.replace('assets/', '')}`
        } else if (url.startsWith('../')) {
          resultUrl = `/books/${url.replace('../', '')}`
        } else {
          resultUrl = `/books/${bookFolder}/assets/${url}`
        }

        return resultUrl
      })
    } catch (error) {
      console.error('加载书籍内容失败:', error)
    }
  }

  /**
   * 获取书籍封面URL
   */
  const getBookCover = (book: Book): string => {
    if (book.cover_path) {
      const timestamp = Date.now()
      return book.cover_path.includes('?') ? `${book.cover_path}&t=${timestamp}` : `${book.cover_path}?t=${timestamp}`
    }
    return ''
  }

  /**
   * 打开图片选择器
   */
  const openCoverPicker = () => {
    showCoverPicker.value = true
  }

  /**
   * 触发封面上传
   */
  const triggerCoverUpload = () => {
    coverInput.value?.click()
  }

  /**
   * 处理封面文件选择
   */
  const onCoverSelected = (event: Event) => {
    const target = event.target as HTMLInputElement
    const file = target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        previewCover.value = e.target?.result as string
      }
      reader.readAsDataURL(file)
    }
  }

  /**
   * 从md图片中选择
   */
  const selectMdImage = (img: string) => {
    selectedMdImage.value = img
  }

  /**
   * 确认选择md图片
   */
  const confirmMdImage = () => {
    if (selectedMdImage.value) {
      previewCover.value = selectedMdImage.value
    }
    showCoverPicker.value = false
  }

  /**
   * 使用默认封面
   */
  const useDefaultCover = () => {
    previewCover.value = ''
  }

  /**
   * 保存封面
   */
  const saveCover = async () => {
    if (!currentCoverBook.value) return

    try {
      let coverPath = previewCover.value

      // 如果是base64图片，需要上传
      if (coverPath.startsWith('data:')) {
        const res = await fetch(coverPath)
        const blob = await res.blob()
        const formData = new FormData()
        formData.append('file', blob, 'cover.webp')

        const uploadRes = await fetch(`/api/v1/books/upload-cover?book_id=${currentCoverBook.value.id}`, {
          method: 'POST',
          body: formData,
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
          }
        })
        const uploadData = await uploadRes.json()
        coverPath = uploadData.path
      }

      // 保存封面路径到数据库
      await api.put(`/books/${currentCoverBook.value.id}/cover`, {
        cover_path: coverPath
      })

      showNotify({ type: 'success', message: '封面保存成功', duration: 1500 })
      showCoverDialog.value = false
    } catch (error: any) {
      console.error('保存封面失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '保存封面失败' })
    }
  }

  /**
   * 关闭封面对话框
   */
  const closeCoverDialog = () => {
    showCoverDialog.value = false
    currentCoverBook.value = null
  }

  return {
    // 状态
    showCoverDialog,
    coverInput,
    previewCover,
    showCoverPicker,
    mdImages,
    selectedMdImage,

    // 方法
    openCoverDialog,
    getBookCover,
    openCoverPicker,
    triggerCoverUpload,
    onCoverSelected,
    selectMdImage,
    confirmMdImage,
    useDefaultCover,
    saveCover,
    closeCoverDialog,
  }
}
