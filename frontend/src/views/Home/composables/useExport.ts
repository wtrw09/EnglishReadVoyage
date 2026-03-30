/**
 * 导出功能 Composable
 * 集中管理所有导出相关的状态和方法
 */
import { ref } from 'vue'
import { showNotify } from 'vant'
import { useAuthStore } from '@/store/auth'

export const useExport = () => {
  const authStore = useAuthStore()

  // ========== 导出相关状态 ==========

  // 导出进度对话框显示状态
  const showExportProgressDialog = ref(false)

  // 导出进度
  const exportProgress = ref(0)

  // 导出状态文本
  const exportStatus = ref('')

  // 当前正在导出的书籍
  const exportCurrentBook = ref('')

  // 导出完成回调
  let onExportComplete: (() => void) | null = null

  // ========== 导出方法 ==========

  /**
   * 设置导出完成回调
   */
  const setOnExportComplete = (callback: (() => void) | null) => {
    onExportComplete = callback
  }

  /**
   * 导出书籍通用函数
   */
  const exportBooks = async (bookIds: string[]) => {
    showExportProgressDialog.value = true
    exportProgress.value = 0
    exportStatus.value = '正在准备导出...'
    exportCurrentBook.value = ''

    try {
      const totalBooks = bookIds.length
      let simulatedProgress = 0

      // 打包阶段的模拟进度
      const progressInterval = setInterval(() => {
        if (simulatedProgress < 50) {
          simulatedProgress += 2
          exportProgress.value = simulatedProgress
          exportStatus.value = `正在打包书籍 (${totalBooks} 本)...`
        }
      }, 500)

      return new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', '/api/v1/books/export')
        xhr.setRequestHeader('Content-Type', 'application/json')
        xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
        xhr.responseType = 'blob'

        let totalSize = 0

        xhr.addEventListener('progress', (event) => {
          clearInterval(progressInterval)

          if (totalSize === 0) {
            const contentLength = xhr.getResponseHeader('Content-Length')
            if (contentLength) {
              totalSize = parseInt(contentLength, 10)
            }
          }

          const loaded = event.loaded
          const total = totalSize || event.total

          if (total > 0) {
            const downloadPercent = Math.round((loaded / total) * 45) + 50
            exportProgress.value = Math.min(downloadPercent, 95)

            const loadedMB = (loaded / 1024 / 1024).toFixed(1)
            const totalMB = (total / 1024 / 1024).toFixed(1)
            exportStatus.value = `正在下载 ${loadedMB}MB / ${totalMB}MB`
          } else {
            exportProgress.value = 70
            const loadedMB = (loaded / 1024 / 1024).toFixed(1)
            exportStatus.value = `正在下载 ${loadedMB}MB...`
          }
        })

        xhr.addEventListener('readystatechange', () => {
          if (xhr.readyState === 2) {
            const contentLength = xhr.getResponseHeader('Content-Length')
            if (contentLength) {
              totalSize = parseInt(contentLength, 10)
              clearInterval(progressInterval)
              const totalMB = (totalSize / 1024 / 1024).toFixed(1)
              exportStatus.value = `正在下载 0MB / ${totalMB}MB`
            }
          }
        })

        xhr.addEventListener('load', () => {
          clearInterval(progressInterval)

          if (xhr.status >= 200 && xhr.status < 300) {
            const contentDisposition = xhr.getResponseHeader('content-disposition')
            let filename = 'books_export.zip'
            if (contentDisposition) {
              const filenameMatch = contentDisposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/i)
              if (filenameMatch) {
                filename = decodeURIComponent(filenameMatch[1].trim().replace(/"/g, ''))
              }
            }

            exportProgress.value = 100
            exportStatus.value = '导出完成！'
            exportCurrentBook.value = filename

            const blob = xhr.response
            const url = window.URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = filename
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            window.URL.revokeObjectURL(url)

            setTimeout(() => {
              showExportProgressDialog.value = false
              showNotify({ type: 'success', message: '书籍导出成功', duration: 1500 })
              if (onExportComplete) {
                setTimeout(() => onExportComplete!(), 100)
              }
            }, 800)

            resolve()
          } else {
            showExportProgressDialog.value = false
            reject(new Error('导出失败'))
          }
        })

        xhr.addEventListener('error', () => {
          clearInterval(progressInterval)
          showExportProgressDialog.value = false
          reject(new Error('网络错误'))
        })

        xhr.addEventListener('abort', () => {
          clearInterval(progressInterval)
          showExportProgressDialog.value = false
          reject(new Error('导出已取消'))
        })

        xhr.send(JSON.stringify({ book_ids: bookIds }))
      })
    } catch (error: any) {
      showExportProgressDialog.value = false
      console.error('导出书籍失败:', error)
      showNotify({ type: 'danger', message: error.message || '导出失败' })
    }
  }

  /**
   * 导出单本书籍
   */
  const exportSingleBook = async (bookId: string) => {
    await exportBooks([bookId])
  }

  /**
   * 导出选中的书籍
   */
  const exportSelectedBooks = async (selectedBooks: string[]) => {
    if (selectedBooks.length === 0) {
      showNotify({ type: 'warning', message: '请先选择要导出的书籍' })
      return
    }
    await exportBooks(selectedBooks)
  }

  return {
    // 状态
    showExportProgressDialog,
    exportProgress,
    exportStatus,
    exportCurrentBook,

    // 方法
    exportBooks,
    exportSingleBook,
    exportSelectedBooks,
    setOnExportComplete,
  }
}
