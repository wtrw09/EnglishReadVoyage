import { ref } from 'vue'
import { showNotify } from 'vant'
import { downloadWithProgress } from '@/utils/upload'

export function useBookExport() {
  // 状态
  const showExportProgressDialog = ref(false)
  const exportProgress = ref(0)
  const exportStatus = ref('')
  const exportCurrentBook = ref('')

  // 导出书籍
  const exportBooks = async (bookIds: string[]): Promise<void> => {
    if (bookIds.length === 0) {
      showNotify({ type: 'warning', message: '请先选择要导出的书籍' })
      return
    }

    // 初始化进度状态
    showExportProgressDialog.value = true
    exportProgress.value = 0
    exportStatus.value = '正在准备导出...'
    exportCurrentBook.value = ''

    const totalBooks = bookIds.length
    let simulatedProgress = 0

    // 打包阶段的模拟进度（因为后端不支持流式进度）
    const progressInterval = setInterval(() => {
      if (simulatedProgress < 50) {
        simulatedProgress += 2
        exportProgress.value = simulatedProgress
        exportStatus.value = `正在打包书籍 (${totalBooks} 本)...`
      }
    }, 500)

    try {
      await downloadWithProgress({
        url: '/api/v1/books/export',
        method: 'POST',
        body: { book_ids: bookIds },
        onProgress: (loaded, total) => {
          clearInterval(progressInterval)

          if (total > 0) {
            // 从50%开始计算下载进度，到95%
            const downloadPercent = Math.round((loaded / total) * 45) + 50
            exportProgress.value = Math.min(downloadPercent, 95)

            const loadedMB = (loaded / 1024 / 1024).toFixed(1)
            const totalMB = (total / 1024 / 1024).toFixed(1)
            exportStatus.value = `正在下载 ${loadedMB}MB / ${totalMB}MB`
            exportCurrentBook.value = `共 ${totalBooks} 本书籍`
          } else {
            exportProgress.value = 70
            const loadedMB = (loaded / 1024 / 1024).toFixed(1)
            exportStatus.value = `正在下载 ${loadedMB}MB...`
          }
        },
        onComplete: (blob, filename) => {
          exportProgress.value = 100
          exportStatus.value = '导出完成！'
          exportCurrentBook.value = filename

          // 下载文件
          const url = window.URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = url
          link.download = filename
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          window.URL.revokeObjectURL(url)

          // 延迟关闭对话框
          setTimeout(() => {
            showExportProgressDialog.value = false
            showNotify({ type: 'success', message: '书籍导出成功', duration: 1500 })
          }, 800)
        }
      })
    } catch (error: any) {
      showExportProgressDialog.value = false
      console.error('导出书籍失败:', error)
      showNotify({ type: 'danger', message: error.message || '导出失败' })
      throw error
    }
  }

  // 关闭导出进度对话框
  const closeExportDialog = () => {
    showExportProgressDialog.value = false
  }

  return {
    showExportProgressDialog,
    exportProgress,
    exportStatus,
    exportCurrentBook,
    exportBooks,
    closeExportDialog
  }
}
