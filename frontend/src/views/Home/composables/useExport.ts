/**
 * 导出功能 Composable
 * 集中管理所有导出相关的状态和方法
 */
import { ref } from 'vue'
import { showNotify } from 'vant'
import { useAuthStore } from '@/store/auth'
import { buildApiUrl, buildStaticUrl } from '@/utils/apiBase'

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

      // 打包阶段的模拟进度
      const progressInterval = setInterval(() => {
        if (exportProgress.value < 50) {
          exportProgress.value += 2
          exportStatus.value = `正在打包书籍 (${totalBooks} 本)...`
        }
      }, 500)

      // 1. 发送导出请求，获取下载 URL
      const url = buildApiUrl('/books/export')
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authStore.token}`,
        },
        body: JSON.stringify({ book_ids: bookIds }),
      })

      if (!resp.ok) {
        clearInterval(progressInterval)
        showExportProgressDialog.value = false
        showNotify({ type: 'danger', message: `导出失败 (${resp.status})`, duration: 2000 })
        return
      }

      const { download_url, filename } = await resp.json()

      clearInterval(progressInterval)

      exportProgress.value = 100
      exportStatus.value = '导出完成！'
      exportCurrentBook.value = filename

      // 2. 下载 ZIP 文件（绕过 XHR blob，直接用 URL 下载）
      await downloadZipFile(download_url, filename)

      setTimeout(() => {
        showExportProgressDialog.value = false
        showNotify({ type: 'success', message: '书籍导出成功', duration: 1500 })
        if (onExportComplete) {
          setTimeout(() => onExportComplete!(), 100)
        }
      }, 800)
    } catch (error: any) {
      showExportProgressDialog.value = false
      console.error('导出书籍失败:', error)
      showNotify({ type: 'danger', message: error.message || '导出失败' })
    }
  }

  /**
   * 下载 ZIP 文件（所有平台统一用 <a> 标签触发系统下载）
   * - Web 浏览器：通过 Vite 代理 / Nginx 同源下载
   * - 原生壳（Capacitor/HarmonyOS）：绝对 URL 触发系统下载管理器，零 JS 内存消耗
   */
  const downloadZipFile = (downloadUrl: string, filename: string) => {
    const isNative = window.location.protocol === 'file:' || window.location.protocol === 'resource:'
    const link = document.createElement('a')
    link.href = isNative ? buildStaticUrl(downloadUrl) : downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
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
