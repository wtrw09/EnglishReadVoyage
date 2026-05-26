/**
 * 导入功能 Composable
 * 集中管理所有导入相关的状态和方法
 */
import { ref, computed, nextTick } from 'vue'
import { showNotify, showToast, showConfirmDialog } from 'vant'
import { useAuthStore } from '@/store/auth'
import { buildApiUrl } from '@/utils/apiBase'
import type { DuplicateCheckResult, PrepareImportResponse } from '../types'

export const useImport = () => {
  const authStore = useAuthStore()

  // ========== 导入相关状态 ==========

  // 导入模式
  const importMode = ref<'normal' | 'mp3_lrc'>('normal')

  // 导入对话框显示状态
  const showImportDialog = ref(false)

  // 导入目标分类ID
  const importCategoryId = ref(0)

  // MP3+LRC 导入相关状态
  const showMp3LrcZhDialog = ref(false)
  const importedBookIds = ref<string[]>([])
  const needZhAudio = ref(false)
  const needTranslation = ref(false)  // 是否有书籍缺少翻译
  const showMp3LrcCheckDialog = ref(false)  // MP3+LRC 校验结果对话框

  // MP3+LRC 检查返回的 token（避免重复上传 ZIP）
  const lastMp3LrcCheckToken = ref<string | null>(null)

  const mp3LrcCheckResult = ref<{
    valid_pairs: { name: string }[]
    invalid_pairs: { name: string; reason: string }[]
    total: number
    message: string
  }>({
    valid_pairs: [],
    invalid_pairs: [],
    total: 0,
    message: ''
  })

  // 文件输入引用
  const fileInput = ref<HTMLInputElement | null>(null)

  // 导入中状态
  const importing = ref(false)

  // 导入完成状态
  const importCompleted = ref(false)

  // 选中的单个文件
  const selectedFile = ref<File | null>(null)

  // 选中的多个文件列表
  const selectedFiles = ref<File[]>([])

  // 是否为批量导入
  const isBatchImport = ref(false)

  // 是否为批量MD导入
  const isBatchMdImport = ref(false)

  // 是否为ZIP导入
  const isZipImport = ref(false)

  // 拖拽悬停状态
  const isDragOver = ref(false)

  // 导入进度
  const importProgress = ref(0)

  // 导入状态文本
  const importStatus = ref('')

  // 上传相关
  const uploading = ref(false)
  const uploadProgress = ref(0)
  const uploadStatus = ref('')

  // 当前导入的书籍ID
  const currentBookId = ref('')

  // 导入完成后选择对话框
  const showChoiceDialog = ref(false)

  // 中文语音生成进度
  const showZhAudioProgress = ref(false)
  const zhAudioProgress = ref(0)
  const zhAudioMessage = ref('')
  const zhAudioLoading = ref(false)

  // 覆盖模式（已有书籍ID）
  const overwriteMode = ref('')

  // ========== Token式导入相关状态 ==========

  // prepare-import 返回的token
  const uploadToken = ref('')
  // 文件类型: zip/md/batch_md
  const uploadFileType = ref('')
  // prepare-import 完整结果
  const prepareResult = ref<PrepareImportResponse | null>(null)

  // 合并检查对话框
  const showImportCheckDialog = ref(false)
  const importCheckResult = ref<{
    valid_books: string[]
    invalid_books: { title: string; reason: string }[]
    duplicate_books: { title: string; book_id: string }[]
    total: number
    message: string
  }>({
    valid_books: [],
    invalid_books: [],
    duplicate_books: [],
    total: 0,
    message: ''
  })
  // 合并对话框中已选择覆盖的书籍
  const selectedDuplicateBooksForMerge = ref<string[]>([])
  // 全选状态（用于UI绑定）
  const isSelectAllDuplicatesForMerge = ref(false)

  // 重复检测对话框
  const showDuplicateDialog = ref(false)

  // 旧的完整性检测对话框（保留用于其他场景）
  const showIntegrityErrorDialog = ref(false)
  const integrityErrorBooks = ref<{ name: string; reason: string }[]>([])
  const pendingIntegrityCleanup = ref<string[]>([])  // 待清理的不完整书籍

  // 重复检测结果
  const duplicateCheckResult = ref<DuplicateCheckResult>({
    has_duplicates: false,
    duplicate_books: [],
    new_books: [],
    total_books: 0
  })

  // 导入操作类型
  const importAction = ref<'skip' | 'overwrite' | 'selected' | null>(null)

  // 用户选中的重复书籍ID列表
  const selectedDuplicateBooks = ref<string[]>([])

  // ========== 计算属性 ==========

  // 是否有选中文件
  const hasSelectedFile = computed(() => selectedFile.value !== null || selectedFiles.value.length > 0)

  // ========== 上传工具函数 ==========

  /**
   * 带上传进度的请求函数
   */
  const uploadWithProgress = (
    url: string,
    formData: FormData,
    statusText: string = '正在上传'
  ): Promise<{ ok: boolean; data: any }> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100)
          uploadProgress.value = percentComplete
          uploadStatus.value = `${statusText}... ${percentComplete}%`
        }
      })

      xhr.addEventListener('load', () => {
        uploading.value = false
        uploadProgress.value = 0
        uploadStatus.value = ''

        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText)
            resolve({ ok: true, data })
          } catch (e) {
            resolve({ ok: true, data: null })
          }
        } else {
          resolve({ ok: false, data: null })
        }
      })

      xhr.addEventListener('error', () => {
        uploading.value = false
        uploadProgress.value = 0
        uploadStatus.value = ''
        reject(new Error('Upload failed'))
      })

      xhr.addEventListener('abort', () => {
        uploading.value = false
        uploadProgress.value = 0
        uploadStatus.value = ''
        reject(new Error('Upload aborted'))
      })

      xhr.open('POST', url)
      xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)

      uploading.value = true
      uploadProgress.value = 0
      uploadStatus.value = `${statusText}...`
      xhr.send(formData)
    })
  }

  /**
   * 带进度回调的上传函数（用于批量导入）
   */
  const uploadWithProgressCallback = (
    url: string,
    formData: FormData,
    statusText: string,
    onProgress: (progress: number) => void
  ): Promise<{ ok: boolean; data: any }> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100)
          onProgress(percentComplete)
          if (percentComplete >= 95) {
            importStatus.value = `${statusText}，后端处理中...`
          } else {
            importStatus.value = `${statusText}... ${percentComplete}%`
          }
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText)
            resolve({ ok: true, data })
          } catch (e) {
            resolve({ ok: true, data: null })
          }
        } else {
          resolve({ ok: false, data: null })
        }
      })

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'))
      })

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload aborted'))
      })

      xhr.open('POST', url)
      xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
      xhr.send(formData)
    })
  }

  /**
   * 带上传进度的流式请求函数（用于导入书籍）
   */
 const uploadWithProgressAndStream = (
    url: string,
    formData: FormData,
    statusText: string = '正在上传'
  ): Promise<void> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      let lastProcessedLen = 0

      // 处理增量 SSE 数据（使用按行分割，正确处理嵌套 JSON）
      const processSseData = async () => {
        const text = xhr.responseText
        if (text.length <= lastProcessedLen) return

        const chunk = text.slice(lastProcessedLen)
        lastProcessedLen = text.length

        // 按行分割，处理好 \n 和 \r\n
        const lines = chunk.split(/\r?\n/)
        for (const rawLine of lines) {
          const line = rawLine.trim()
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6)  // 去掉 "data: " 前缀
          if (!jsonStr) continue
          try {
            const data = JSON.parse(jsonStr)
            importProgress.value = data.percentage || 0
            importStatus.value = data.message || ''

            if (data.success === true) {
              showNotify({ type: 'success', message: data.message, duration: 1500 })
              if (!data.book_id && overwriteMode.value) {
                currentBookId.value = overwriteMode.value
              } else {
                currentBookId.value = data.book_id || ''
              }
              if (data.book_ids) {
                importedBookIds.value = data.book_ids
              }
              if (data.need_zh_audio) {
                needZhAudio.value = true
              }
              if (data.need_translation) {
                needTranslation.value = true
              }
              importCompleted.value = true
              if (!isZipImport.value && !isBatchImport.value && importMode.value !== 'mp3_lrc') {
                showChoiceDialog.value = true
              }
            } else if (data.success === false) {
              showNotify({ type: 'danger', message: data.message })
            }
            await nextTick()  // 每次消息后刷新 DOM
            // 短暂延迟确保浏览器渲染
            await new Promise(resolve => setTimeout(resolve, 20))
          } catch (e) {
            console.error('解析SSE数据失败:', e)
          }
        }
      }

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100)
          uploadProgress.value = percentComplete
          uploadStatus.value = `${statusText}... ${percentComplete}%`
        }
      })

      xhr.addEventListener('progress', async () => {
        if (xhr.readyState !== XMLHttpRequest.LOADING && xhr.readyState !== XMLHttpRequest.DONE) return
        // 首次收到响应数据，切换到"导入中"状态
        if (!importing.value) {
          uploading.value = false
          uploadProgress.value = 0
          uploadStatus.value = ''
          importing.value = true
          importProgress.value = 0
          importStatus.value = statusText
        }
        await processSseData()
      })

      xhr.addEventListener('load', async () => {
        uploading.value = false
        uploadProgress.value = 0
        uploadStatus.value = ''

        if (xhr.status >= 200 && xhr.status < 300) {
          importing.value = true
          importProgress.value = 0
          importStatus.value = statusText
          await processSseData()
          resolve()
        } else {
          let errMsg = '导入请求失败'
          try {
            const errData = JSON.parse(xhr.responseText)
            errMsg = errData.detail || errData.message || errMsg
          } catch {
            if (xhr.responseText) {
              errMsg = xhr.responseText.slice(0, 200)
            }
          }
          reject(new Error(errMsg))
        }
      })

      xhr.addEventListener('error', () => {
        uploading.value = false
        uploadProgress.value = 0
        uploadStatus.value = ''
        reject(new Error('Upload failed'))
      })

      xhr.addEventListener('abort', () => {
        uploading.value = false
        uploadProgress.value = 0
        uploadStatus.value = ''
        reject(new Error('Upload aborted'))
      })

      xhr.open('POST', url)
      xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)

      uploading.value = true
      uploadProgress.value = 0
      uploadStatus.value = `${statusText}...`
      xhr.send(formData)
    })
  }

  /**
   * 基于 token 的流式导入函数（无需重复上传文件，直接 SSE 读取进度）
   */
  const streamImportWithToken = (
    url: string
  ): Promise<void> => {
    return new Promise((resolve, reject) => {
      importing.value = true
      importProgress.value = 0
      importStatus.value = '正在导入...'

      const xhr = new XMLHttpRequest()
      let lastProcessedLen = 0

      const processSseData = async () => {
        const text = xhr.responseText
        if (text.length <= lastProcessedLen) return

        const chunk = text.slice(lastProcessedLen)
        lastProcessedLen = text.length

        const lines = chunk.split(/\r?\n/)
        for (const rawLine of lines) {
          const line = rawLine.trim()
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6)
          if (!jsonStr) continue
          try {
            const data = JSON.parse(jsonStr)
            importProgress.value = data.percentage || 0
            importStatus.value = data.message || ''

            if (data.success === true) {
              showNotify({ type: 'success', message: data.message, duration: 1500 })
              if (data.book_ids) {
                importedBookIds.value = data.book_ids
              }
              if (data.need_zh_audio) {
                needZhAudio.value = true
              }
              if (data.need_translation) {
                needTranslation.value = true
              }
              importCompleted.value = true
            } else if (data.success === false) {
              showNotify({ type: 'danger', message: data.message })
            }
            await nextTick()
            await new Promise(resolve => setTimeout(resolve, 20))
          } catch (e) {
            console.error('解析SSE数据失败:', e)
          }
        }
      }

      xhr.addEventListener('progress', async () => {
        if (xhr.readyState !== XMLHttpRequest.LOADING && xhr.readyState !== XMLHttpRequest.DONE) return
        await processSseData()
      })

      xhr.addEventListener('load', async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          await processSseData()
          resolve()
        } else {
          let errMsg = '导入请求失败'
          try {
            const errData = JSON.parse(xhr.responseText)
            errMsg = errData.detail || errData.message || errMsg
          } catch {
            if (xhr.responseText) {
              errMsg = xhr.responseText.slice(0, 200)
            }
          }
          reject(new Error(errMsg))
        }
      })

      xhr.addEventListener('error', () => {
        importing.value = false
        reject(new Error('Import request failed'))
      })

      xhr.addEventListener('abort', () => {
        importing.value = false
        reject(new Error('Import request aborted'))
      })

      xhr.open('POST', url)
      xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
      xhr.send()
    })
  }

  /**
   * 通过 token 确认导入（SSE流式进度）
   */
  const confirmWithStream = (token: string, options?: {
    skipDuplicates?: boolean
    overwriteBookIds?: string[]
  }): Promise<void> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      let lastProcessedLen = 0

      const processSseData = async () => {
        const text = xhr.responseText
        if (text.length <= lastProcessedLen) return

        const chunk = text.slice(lastProcessedLen)
        lastProcessedLen = text.length

        const lines = chunk.split(/\r?\n/)
        for (const rawLine of lines) {
          const line = rawLine.trim()
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6)
          if (!jsonStr) continue
          try {
            const data = JSON.parse(jsonStr)
            importProgress.value = data.percentage || 0
            importStatus.value = data.message || ''

            if (data.success === true) {
              showNotify({ type: 'success', message: data.message, duration: 1500 })
              if (data.book_id) {
                currentBookId.value = data.book_id
              }
              // MP3+LRC: 收集 book_ids 并标记需要中文语音
              if (data.book_ids) {
                importedBookIds.value = data.book_ids
              }
              if (data.need_zh_audio) {
                needZhAudio.value = true
              }
              importCompleted.value = true
              if (uploadFileType.value === 'md') {
                showChoiceDialog.value = true
              }
            } else if (data.success === false) {
              showNotify({ type: 'danger', message: data.message })
              importing.value = false
              resolve()  // 失败时 resolve，调用者通过状态判断结果
            }
            await nextTick()
            await new Promise(resolve => setTimeout(resolve, 20))
          } catch (e) {
            console.error('解析SSE数据失败:', e)
          }
        }
      }

      xhr.addEventListener('progress', async () => {
        if (xhr.readyState !== XMLHttpRequest.LOADING && xhr.readyState !== XMLHttpRequest.DONE) return
        // 首次收到响应数据，切换到"导入中"状态
        if (!importing.value) {
          importing.value = true
          importProgress.value = 0
          importStatus.value = '正在处理事务...'
        }
        await processSseData()
      })

      xhr.addEventListener('load', async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          if (!importing.value) {
            importing.value = true
            importProgress.value = 0
            importStatus.value = '正在处理事务...'
          }
          await processSseData()
          importing.value = false
          resolve()
        } else {
          let errMsg = '导入请求失败'
          try {
            const errData = JSON.parse(xhr.responseText)
            errMsg = errData.detail || errData.message || errMsg
          } catch {
            if (xhr.responseText) {
              errMsg = xhr.responseText.slice(0, 200)
            }
          }
          importing.value = false
          reject(new Error(errMsg))
        }
      })

      xhr.addEventListener('error', () => {
        importing.value = false
        reject(new Error('导入请求网络错误'))
      })

      xhr.addEventListener('abort', () => {
        importing.value = false
        reject(new Error('导入请求已取消'))
      })

      // 构建 URL + 查询参数
      let apiPath = buildApiUrl('/books/confirm-import')
      const params = new URLSearchParams()
      if (options?.skipDuplicates) {
        params.append('skip_duplicates', 'true')
      }
      if (options?.overwriteBookIds && options.overwriteBookIds.length > 0) {
        params.append('overwrite_book_ids', options.overwriteBookIds.join(','))
      }
      if (importCategoryId.value) {
        params.append('category_id', importCategoryId.value.toString())
      }
      if (params.toString()) {
        apiPath += `?${params.toString()}`
      }

      xhr.open('POST', apiPath)
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)

      importProgress.value = 0
      importStatus.value = '正在导入...'
      xhr.send(JSON.stringify({ token }))
    })
  }

  /**
   * 通过 token 取消导入
   */
  const cancelUploadByToken = async (token: string): Promise<void> => {
    if (!token) return
    try {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', buildApiUrl('/books/cancel-import'))
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
      xhr.send(JSON.stringify({ token }))
    } catch (e) {
      console.error('取消导入失败:', e)
    }
  }

  // ========== 检查重复书籍 ==========

  /**
   * 检查ZIP文件中的重复书籍
   */
  const checkZipDuplicates = async (file: File): Promise<DuplicateCheckResult> => {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const result = await uploadWithProgress(
        buildApiUrl('/books/check-zip-duplicates'),
        formData,
        '正在上传ZIP检查重复'
      )

      if (!result.ok) {
        return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
      }

      return result.data || { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    } catch (error) {
      console.error('检查重复书籍失败:', error)
      return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    }
  }

  /**
   * 检查ZIP文件完整性
   */
  const checkZipIntegrity = async (file: File): Promise<{
    is_valid: boolean
    books: any[]
    failed_books: string[]
    message: string
  }> => {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const result = await uploadWithProgress(
        buildApiUrl('/books/check-zip-integrity'),
        formData,
        '正在检查ZIP完整性'
      )

      if (!result.ok) {
        return { is_valid: false, books: [], failed_books: [], message: '检查失败' }
      }

      return result.data || { is_valid: false, books: [], failed_books: [], message: '' }
    } catch (error) {
      console.error('检查ZIP完整性失败:', error)
      return { is_valid: false, books: [], failed_books: [], message: '检查失败' }
    }
  }

  /**
   * 合并检查ZIP文件（完整性和重复）
   */
  const checkZipAll = async (file: File): Promise<{
    valid_books: string[]
    invalid_books: { title: string; reason: string }[]
    duplicate_books: { title: string; book_id: string }[]
    total: number
    message: string
  }> => {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const result = await uploadWithProgress(
        buildApiUrl('/books/check-zip-all'),
        formData,
        '正在检查ZIP文件'
      )

      if (!result.ok) {
        return { valid_books: [], invalid_books: [], duplicate_books: [], total: 0, message: '检查失败' }
      }

      return result.data || { valid_books: [], invalid_books: [], duplicate_books: [], total: 0, message: '' }
    } catch (error) {
      console.error('检查ZIP失败:', error)
      return { valid_books: [], invalid_books: [], duplicate_books: [], total: 0, message: '检查失败' }
    }
  }

  /**
   * 清理导入失败的书籍
   */
  const cleanupFailedImport = async (bookTitles: string[]) => {
    if (bookTitles.length === 0) return

    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', buildApiUrl('/books/cleanup-failed-import'))
      xhr.setRequestHeader('Content-Type', 'application/json')
      if (authStore.token) {
        xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
      }

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve()
        } else {
          console.error('清理失败书籍失败:', xhr.status)
          resolve()  // 不阻塞主流程
        }
      })

      xhr.addEventListener('error', () => {
        console.error('清理失败书籍请求失败')
        resolve()  // 不阻塞主流程
      })

      xhr.send(JSON.stringify(bookTitles))
    })
  }

  /**
   * 检查多个MD文件的重复书籍
   */
  const checkMdDuplicates = async (files: File[]): Promise<DuplicateCheckResult> => {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    try {
      const result = await uploadWithProgress(
        buildApiUrl('/books/check-md-duplicates'),
        formData,
        '正在上传文件检查重复'
      )

      if (!result.ok) {
        return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
      }

      return result.data || { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    } catch (error) {
      console.error('检查MD文件重复书籍失败:', error)
      return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    }
  }

  // ========== 重复书籍选择 ==========

  /**
   * 切换重复书籍选中状态
   */
  const toggleDuplicateSelect = (bookId: string) => {
    const index = selectedDuplicateBooks.value.indexOf(bookId)
    if (index === -1) {
      selectedDuplicateBooks.value.push(bookId)
    } else {
      selectedDuplicateBooks.value.splice(index, 1)
    }
  }

  /**
   * 全选所有重复书籍
   */
  const selectAllDuplicates = () => {
    selectedDuplicateBooks.value = duplicateCheckResult.value.duplicate_books.map((b: any) => b.book_id)
  }

  /**
   * 清空选中的重复书籍
   */
  const clearAllDuplicates = () => {
    selectedDuplicateBooks.value = []
  }

  // ========== 核心导入方法 ==========

  /**
   * 打开导入对话框
   */
  const openImportDialog = (categoryId: number) => {
    importCategoryId.value = categoryId
    showImportDialog.value = true
  }

  /**
   * 触发文件选择
   */
  const triggerFileInput = () => {
    if (!importing.value) {
      fileInput.value?.click()
    }
  }

  /**
   * 文件拖放处理
   */
  const onFileDrop = (event: DragEvent) => {
    isDragOver.value = false
    if (importing.value) return

    const files = event.dataTransfer?.files
    if (files && files.length > 0) {
      handleFile(files[0])
    }
  }

  /**
   * 文件选择处理
   */
  const onFileSelected = (event: Event) => {
    const target = event.target as HTMLInputElement
    const files = target.files

    if (files && files.length > 0) {
      if (files.length === 1) {
        handleFile(files[0])
      } else {
        handleMultipleFiles(Array.from(files))
      }
    }
  }

  /**
   * 切换导入模式
   */
  const switchImportMode = (mode: 'normal' | 'mp3_lrc') => {
    importMode.value = mode
    // 切换模式时清空已选文件
    selectedFile.value = null
    selectedFiles.value = []
    isBatchImport.value = false
    isBatchMdImport.value = false
    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = ''
    // 重置 MP3+LRC 相关状态
    needZhAudio.value = false
    needTranslation.value = false
    importedBookIds.value = []
    showMp3LrcZhDialog.value = false
    showMp3LrcCheckDialog.value = false
    // 清空文件输入元素的值，确保下次 @change 事件可触发
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }

  /**
   * 处理文件
   */
  const handleFile = async (file: File) => {
    if (importMode.value === 'mp3_lrc') {
      if (!file.name.endsWith('.zip')) {
        showNotify({ type: 'danger', message: 'MP3/LRC模式只支持 .zip 格式' })
        return
      }
    } else {
      if (!file.name.endsWith('.md') && !file.name.endsWith('.zip')) {
        showNotify({ type: 'danger', message: '只支持 .md 或 .zip 格式的文件' })
        return
      }
    }

    if (!authStore.isLoggedIn) {
      showToast('请先登录')
      return
    }

    resetImportState()
    selectedFile.value = file
    selectedFiles.value = []
    isBatchImport.value = false
  }

  /**
   * 处理多文件选择（批量导入MD文件）
   */
  const handleMultipleFiles = async (files: File[]) => {
    const mdFiles = files.filter(f => f.name.endsWith('.md'))

    if (mdFiles.length === 0) {
      showNotify({ type: 'danger', message: '请至少选择一个 .md 格式的文件' })
      return
    }

    if (mdFiles.length !== files.length) {
      showNotify({ type: 'warning', message: `已过滤非MD文件，共选择 ${mdFiles.length} 个MD文件` })
    }

    if (!authStore.isLoggedIn) {
      showToast('请先登录')
      return
    }

    resetImportState()
    selectedFiles.value = mdFiles
    isBatchImport.value = true
  }

  /**
   * 重置导入状态
   */
  const resetImportState = () => {
    if (importCompleted.value) {
      importCompleted.value = false
      importProgress.value = 0
      importStatus.value = ''
      currentBookId.value = ''
      isZipImport.value = false
      isBatchImport.value = false
      importAction.value = null
      selectedDuplicateBooks.value = []
      duplicateCheckResult.value = {
        has_duplicates: false,
        duplicate_books: [],
        new_books: [],
        total_books: 0
      }
    }
  }

  /**
   * 确认导入
   */
  const handleImportConfirm = async () => {
    // MP3+LRC 模式：先检查重复，再决定导入策略
    if (importMode.value === 'mp3_lrc') {
      return handleMp3LrcCheckAndImport()
    }

    // 批量导入模式
    if (isBatchImport.value && selectedFiles.value.length > 0) {
      isBatchMdImport.value = true

      const formData = new FormData()
      selectedFiles.value.forEach(f => {
        formData.append('files', f)
      })

      uploading.value = true
      uploadProgress.value = 0
      uploadStatus.value = '正在上传检查文件...'

      try {
        const result = await uploadWithProgress(
          buildApiUrl('/books/prepare-import'),
          formData,
          '正在上传检查'
        )

        if (result.ok && result.data) {
          uploadToken.value = result.data.token
          uploadFileType.value = result.data.file_type
          prepareResult.value = result.data

          const data = result.data
          const hasDuplicates = data.duplicate_books && data.duplicate_books.length > 0

          if (hasDuplicates) {
            duplicateCheckResult.value = {
              has_duplicates: true,
              duplicate_books: data.duplicate_books,
              new_books: data.valid_books.map((t: string) => ({ title: t, book_id: '' })),
              total_books: data.total_books
            }
            showDuplicateDialog.value = true
            importStatus.value = ''
            return
          }

          await confirmWithStream(uploadToken.value)
          return
        }
      } catch (error) {
        console.error('prepare-import批量MD失败:', error)
        showNotify({ type: 'danger', message: '上传检查失败' })
      } finally {
        uploading.value = false
        uploadProgress.value = 0
        uploadStatus.value = ''
      }
      return
    }

    // 单文件导入模式
    if (!selectedFile.value) {
      showNotify({ type: 'warning', message: '请先选择文件' })
      return
    }

    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = ''
    isZipImport.value = selectedFile.value.name.endsWith('.zip')

    try {
      // 1. 调用 prepare-import 一次上传+检查
      const formData = new FormData()
      formData.append('file', selectedFile.value)

      uploading.value = true
      uploadProgress.value = 0
      uploadStatus.value = '正在上传检查文件...'

      const result = await uploadWithProgress(
        buildApiUrl('/books/prepare-import'),
        formData,
        '正在上传检查'
      )

      uploading.value = false

      if (!result.ok || !result.data) {
        showNotify({ type: 'danger', message: '文件上传检查失败，请重试' })
        return
      }

      const data = result.data
      uploadToken.value = data.token
      uploadFileType.value = data.file_type
      prepareResult.value = data

      if (data.file_type === 'zip') {
        // ZIP: 显示合并检查结果
        importCheckResult.value = {
          valid_books: data.valid_books || [],
          invalid_books: data.invalid_books || [],
          duplicate_books: data.duplicate_books || [],
          total: data.total_books || 0,
          message: data.message || ''
        }
        showImportCheckDialog.value = true
        importStatus.value = ''
        return
      }

      // MD 文件: 检查重复
      const hasDuplicates = data.duplicate_books && data.duplicate_books.length > 0

      if (hasDuplicates) {
        isBatchMdImport.value = false
        duplicateCheckResult.value = {
          has_duplicates: true,
          duplicate_books: data.duplicate_books,
          new_books: data.valid_books.map((t: string) => ({ title: t, book_id: '' })),
          total_books: data.total_books
        }
        showDuplicateDialog.value = true
        importStatus.value = ''
        return
      }

      // 无重复，直接导入
      return await confirmWithStream(data.token)
    } catch (error: any) {
      console.error('prepare-import失败:', error)
      showNotify({ type: 'danger', message: '文件上传检查失败' })
    } finally {
      uploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = ''
    }
  }

  /**
   * 批量导入MD文件
   */
  const handleBatchImport = async () => {
    importing.value = true
    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = `正在批量导入 ${selectedFiles.value.length} 本书籍...`

    const totalFiles = selectedFiles.value.length
    let successCount = 0
    let failCount = 0

    for (let i = 0; i < totalFiles; i++) {
      const file = selectedFiles.value[i]
      const baseProgress = Math.round((i / totalFiles) * 100)

      try {
        const formData = new FormData()
        formData.append('file', file)

        const categoryId = importCategoryId.value
        let apiPath = buildApiUrl('/books/import')
        const params = new URLSearchParams()

        if (categoryId) {
          params.append('category_id', categoryId.toString())
        }

        if (params.toString()) {
          apiPath += `?${params.toString()}`
        }

        const result = await uploadWithProgressCallback(
          apiPath,
          formData,
          `正在上传 (${i + 1}/${totalFiles}): ${file.name}`,
          (progress) => {
            importProgress.value = Math.min(baseProgress + Math.round(progress / totalFiles), 99)
          }
        )

        if (result.ok) {
          successCount++
        } else {
          failCount++
          console.error(`导入失败: ${file.name}`)
        }
      } catch (error) {
        failCount++
        console.error(`导入异常: ${file.name}`, error)
      }
    }

    importProgress.value = 100
    importStatus.value = `批量导入完成: 成功 ${successCount} 本, 失败 ${failCount} 本`
    importCompleted.value = true
    importing.value = false
    showNotify({ type: 'success', message: `成功导入 ${successCount} 本书籍`, duration: 2000 })
  }

  /**
   * 执行ZIP导入（支持跳过重复和指定覆盖）
   */
  const doImportZip = async (skipDuplicates: boolean = false, overwriteBookIds?: string[]) => {
    if (!selectedFile.value) return

    importing.value = true
    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = '正在导入...'

    try {
      const formData = new FormData()
      formData.append('file', selectedFile.value)

      const categoryId = importCategoryId.value
      let apiPath = buildApiUrl('/books/import')
      const params = new URLSearchParams()

      if (skipDuplicates) {
        params.append('skip_duplicates', 'true')
      }

      if (overwriteBookIds && overwriteBookIds.length > 0) {
        params.append('overwrite_book_ids', overwriteBookIds.join(','))
      }

      if (categoryId) {
        params.append('category_id', categoryId.toString())
      }

      if (params.toString()) {
        apiPath += `?${params.toString()}`
      }

      await uploadWithProgressAndStream(apiPath, formData, '正在上传ZIP文件')
    } catch (error: any) {
      console.error('导入书籍失败:', error)
      const message = error.message || '导入失败，请重试'
      showNotify({ type: 'danger', message })
    } finally {
      importing.value = false
      if (fileInput.value) {
        fileInput.value.value = ''
      }
    }
  }

  /**
   * 执行导入
   */
  const doImport = async (overwrite: boolean, existingBookId?: string) => {
    importing.value = true
    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = '正在导入...'
    overwriteMode.value = existingBookId || ''

    try {
      const formData = new FormData()
      formData.append('file', selectedFile.value!)

      const categoryId = importCategoryId.value
      let apiPath = overwrite ? buildApiUrl('/books/import/overwrite') : buildApiUrl('/books/import')
      const params = new URLSearchParams()

      if (overwrite && existingBookId) {
        params.append('book_id', existingBookId)
      }

      if (categoryId) {
        params.append('category_id', categoryId.toString())
      }

      if (params.toString()) {
        apiPath += `?${params.toString()}`
      }

      await uploadWithProgressAndStream(apiPath, formData, '正在上传文件')
    } catch (error: any) {
      console.error('导入书籍失败:', error)
      const message = error.message || '导入失败，请重试'
      showNotify({ type: 'danger', message })
    } finally {
      importing.value = false
      if (fileInput.value) {
        fileInput.value.value = ''
      }
    }
  }

  /**
   * MP3+LRC 导入前置检查（检查重复，显示对话框，然后按用户选择导入）
   */
  const handleMp3LrcCheckAndImport = async () => {
    if (!selectedFile.value) {
      showNotify({ type: 'warning', message: '请先选择ZIP文件' })
      return
    }

    uploading.value = true
    uploadProgress.value = 0
    uploadStatus.value = '正在检查文件...'

    try {
      const formData = new FormData()
      formData.append('file', selectedFile.value)

      const result = await uploadWithProgress(
        buildApiUrl('/books/check-mp3-lrc-duplicates'),
        formData,
        '正在检查重复'
      )

      uploading.value = false
      uploadStatus.value = ''

      if (!result.ok || !result.data) {
        showNotify({ type: 'danger', message: '文件检查失败' })
        return
      }

      const data = result.data
      const token = data.check_token || null
      lastMp3LrcCheckToken.value = token

      // 保存校验结果，用于显示校验对话框
      mp3LrcCheckResult.value = {
        valid_pairs: data.new_books || [],
        invalid_pairs: data.invalid_pairs || [],
        total: data.total_books || 0,
        message: data.message || ''
      }

      // 如果有无效配对，先显示校验结果对话框
      if (data.invalid_pairs && data.invalid_pairs.length > 0) {
        showMp3LrcCheckDialog.value = true
        importStatus.value = ''
        return
      }

      // 有重复，显示对话框让用户选择
      if (data.has_duplicates && data.duplicate_books?.length > 0) {
        duplicateCheckResult.value = {
          has_duplicates: true,
          duplicate_books: data.duplicate_books || [],
          new_books: (data.new_books || []).map((b: any) => ({ title: b.title, book_id: b.book_id || '' })),
          total_books: data.total_books || 0
        }
        showDuplicateDialog.value = true
        importStatus.value = ''
        return
      }

      // 无重复，直接导入（使用 token 避免重复上传）
      await handleMp3LrcImport({ checkToken: token })
    } catch (error) {
      console.error('检查MP3+LRC重复失败:', error)
      showNotify({ type: 'danger', message: '检查失败，请重试' })
    } finally {
      uploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = ''
    }
  }

  /**
   * 执行 MP3+LRC 导入（直接上传到 /books/import-mp3-lrc）
   */
  const handleMp3LrcImport = async (options?: {
    skipDuplicates?: boolean
    overwriteBookIds?: string[]
    checkToken?: string | null
  }) => {
    if (!selectedFile.value && !options?.checkToken) {
      showNotify({ type: 'warning', message: '请先选择ZIP文件' })
      return
    }

    importing.value = true
    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = '正在解析MP3+LRC配对...'

    try {
      const categoryId = importCategoryId.value
      let apiPath = buildApiUrl('/books/import-mp3-lrc')
      const params = new URLSearchParams()

      if (categoryId) {
        params.append('category_id', categoryId.toString())
      }

      if (options?.skipDuplicates) {
        params.append('skip_duplicates', 'true')
      }

      if (options?.overwriteBookIds && options.overwriteBookIds.length > 0) {
        params.append('overwrite_book_ids', options.overwriteBookIds.join(','))
      }

      if (options?.checkToken) {
        // 使用 token，无需重复上传文件
        params.append('check_token', options.checkToken)
        apiPath += `?${params.toString()}`
        await streamImportWithToken(apiPath)
      } else {
        // 无 token，传统上传方式
        const formData = new FormData()
        formData.append('file', selectedFile.value!)
        if (params.toString()) {
          apiPath += `?${params.toString()}`
        }
        await uploadWithProgressAndStream(apiPath, formData, '正在导入MP3+LRC文件')
      }

      // 导入完成后检查是否需要显示中文语音/翻译提醒
      if (importedBookIds.value.length > 0) {
        if (needZhAudio.value || needTranslation.value) {
          showMp3LrcZhDialog.value = true
        }
      }
    } catch (error: any) {
      console.error('MP3+LRC导入失败:', error)
      const message = error.message || '导入失败，请确认ZIP包包含正确配对的MP3和LRC文件'
      showNotify({ type: 'danger', message })
    } finally {
      importing.value = false
      if (fileInput.value) {
        fileInput.value.value = ''
      }
    }
  }

  /**
   * MP3+LRC 校验结果对话框 - 跳过无效配对继续导入
   */
  const handleMp3LrcCheckContinue = async () => {
    showMp3LrcCheckDialog.value = false

    // 从之前 API 响应中获取有效配对和重复信息
    const data = mp3LrcCheckResult.value
    const validBooks = data.valid_pairs || []

    if (validBooks.length === 0) {
      showNotify({ type: 'warning', message: '没有可导入的有效配对' })
      return
    }

    // 如果有有效配对但没有检查过重复，需要检查
    // 之前 handleMp3LrcCheckAndImport 已经拿到了重复数据，但没用保存完整
    // 这里直接调用后端检查重复
    const token = lastMp3LrcCheckToken.value
    if (!token) {
      showNotify({ type: 'warning', message: '导入会话已过期，请重新选择文件' })
      return
    }

    await handleMp3LrcImport({
      checkToken: token,
      skipDuplicates: false
    })
  }

  /**
   * MP3+LRC 校验结果对话框 - 取消导入
   */
  const handleMp3LrcCheckCancel = () => {
    showMp3LrcCheckDialog.value = false
    // 清理临时文件
    if (lastMp3LrcCheckToken.value) {
      cancelUploadByToken(lastMp3LrcCheckToken.value)
      lastMp3LrcCheckToken.value = null
    }
    selectedFile.value = null
    importStatus.value = ''
  }

  /**
   * 导入后生成中文语音（SSE流式进度）
   */
  const handleGenerateChineseAudio = async () => {
    showMp3LrcZhDialog.value = false
    const bookIds = importedBookIds.value
    if (bookIds.length === 0) return

    // 显示进度弹窗
    showZhAudioProgress.value = true
    zhAudioLoading.value = true
    zhAudioProgress.value = 0
    zhAudioMessage.value = '准备生成中...'

    let successCount = 0
    let failCount = 0

    for (let i = 0; i < bookIds.length; i++) {
      const bookId = bookIds[i]
      zhAudioMessage.value = `第${i + 1}/${bookIds.length}本书 - 准备中...`

      try {
        // 使用 SSE 流式响应，实时更新进度直到生成完成
        const xhr = new XMLHttpRequest()
        let lastProcessedLen = 0
        let bookSuccess = false

        const processSseData = () => {
          const text = xhr.responseText
          if (text.length <= lastProcessedLen) return

          const chunk = text.slice(lastProcessedLen)
          lastProcessedLen = text.length

          const lines = chunk.split(/\r?\n/)
          for (const rawLine of lines) {
            const line = rawLine.trim()
            if (!line.startsWith('data: ')) continue
            const jsonStr = line.slice(6)
            if (!jsonStr) continue
            try {
              const data = JSON.parse(jsonStr)
              if (data.percentage !== undefined) {
                // 更新当前书籍的生成进度（基于整体进度桶叠加当前书籍内的百分比）
                const baseProgress = Math.round((i / bookIds.length) * 100)
                const bookProgress = Math.round((data.percentage / 100) * (100 / bookIds.length))
                zhAudioProgress.value = baseProgress + bookProgress
              }
              if (data.message) {
                zhAudioMessage.value = `第${i + 1}/${bookIds.length}本书 - ${data.message}`
              }
              if (data.success === true) {
                bookSuccess = true
              } else if (data.success === false) {
                bookSuccess = false
              }
            } catch (e) {
              // ignore parse errors
            }
          }
        }

        xhr.addEventListener('progress', () => {
          if (xhr.readyState !== XMLHttpRequest.LOADING && xhr.readyState !== XMLHttpRequest.DONE) return
          processSseData()
        })

        // 等待该书籍生成完成（在 readystatechange 中处理数据并 resolve）
        await new Promise<void>((resolve) => {
          xhr.addEventListener('readystatechange', () => {
            if (xhr.readyState === XMLHttpRequest.LOADING) {
              processSseData()
            } else if (xhr.readyState === XMLHttpRequest.DONE) {
              processSseData()
              if (xhr.status >= 200 && xhr.status < 300 && bookSuccess) {
                successCount++
              } else {
                failCount++
              }
              resolve()
            }
          })

          xhr.addEventListener('error', () => {
            failCount++
            resolve()
          })

          xhr.open('POST', buildApiUrl(`/books/${bookId}/generate-chinese-audio`))
          xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
          xhr.send()
        })
      } catch (e) {
        failCount++
        console.error(`生成中文语音失败: ${bookId}`, e)
      }
    }

    zhAudioProgress.value = 100
    zhAudioMessage.value = '生成完成'
    zhAudioLoading.value = false

    if (failCount === 0) {
      showNotify({ type: 'success', message: `中文语音生成完成 (${successCount}本)`, duration: 2000 })
    } else if (successCount > 0) {
      showNotify({ type: 'warning', message: `部分完成: ${successCount}本成功, ${failCount}本失败`, duration: 3000 })
    } else {
      showNotify({ type: 'danger', message: `中文语音生成失败 (${failCount}本)`, duration: 3000 })
    }
  }

  /**
   * 稍后生成中文语音
   */
  const handleMp3LrcZhLater = () => {
    showMp3LrcZhDialog.value = false
    showNotify({ type: 'warning', message: '可在书籍详情页的「补充中文语音」功能中生成', duration: 2000 })
  }

  // ========== 重复书籍处理 ==========

  /**
   * 覆盖导入（导入所有书籍，包括重复的）
   */
  const handleImportWithOverwrite = () => {
    showDuplicateDialog.value = false
    importAction.value = 'overwrite'

    if (importMode.value === 'mp3_lrc') {
      // 获取所有重复书籍的 ID，传递到后端以覆盖这些书籍
      const allDuplicateIds = duplicateCheckResult.value.duplicate_books.map((b: any) => b.book_id)
      handleMp3LrcImport({
        overwriteBookIds: allDuplicateIds,
        checkToken: lastMp3LrcCheckToken.value
      })
    } else if (isBatchMdImport.value) {
      doBatchImportWithAction()
    } else {
      doImportZipWithAction()
    }
  }

  /**
   * 跳过重复书籍导入
   */
  const handleImportSkipDuplicates = () => {
    showDuplicateDialog.value = false
    importAction.value = 'skip'
    selectedDuplicateBooks.value = []

    if (importMode.value === 'mp3_lrc') {
      handleMp3LrcImport({
        skipDuplicates: true,
        checkToken: lastMp3LrcCheckToken.value
      })
    } else if (isBatchMdImport.value) {
      doBatchImportWithAction()
    } else {
      doImportZipWithAction()
    }
  }

  /**
   * 覆盖选中的重复书籍
   */
  const handleImportSelected = () => {
    showDuplicateDialog.value = false
    importAction.value = 'selected'

    if (importMode.value === 'mp3_lrc') {
      handleMp3LrcImport({
        overwriteBookIds: [...selectedDuplicateBooks.value],
        checkToken: lastMp3LrcCheckToken.value
      })
    } else if (isBatchMdImport.value) {
      doBatchImportWithAction()
    } else {
      doImportZipWithAction()
    }
  }

  /**
   * 根据用户选择执行批量MD导入（Token式）
   */
  const doBatchImportWithAction = async () => {
    if (!uploadToken.value) return

    importing.value = true
    importProgress.value = 0
    importStatus.value = '正在导入书籍...'

    let overwriteBookIds: string[] | undefined = undefined

    if (importAction.value === 'overwrite') {
      overwriteBookIds = duplicateCheckResult.value.duplicate_books.map((b: any) => b.book_id)
    } else if (importAction.value === 'selected') {
      overwriteBookIds = selectedDuplicateBooks.value
    }

    const skipDuplicates = importAction.value === 'skip'

    try {
      await confirmWithStream(uploadToken.value, {
        skipDuplicates,
        overwriteBookIds
      })
    } catch (error) {
      console.error('Token式批量导入失败:', error)
      showNotify({ type: 'danger', message: '批量导入失败' })
    } finally {
      importing.value = false
      isBatchMdImport.value = false
      selectedDuplicateBooks.value = []
      uploadToken.value = ''
    }
  }

  /**
   * 根据用户选择执行ZIP导入（Token式）
   */
  const doImportZipWithAction = async () => {
    if (!uploadToken.value || !importAction.value) return

    importing.value = true
    importProgress.value = 0
    importStatus.value = '正在导入书籍...'

    const skipDuplicates = importAction.value === 'skip'

    let overwriteBookIds: string[] | undefined = undefined
    if (importAction.value === 'overwrite') {
      overwriteBookIds = duplicateCheckResult.value.duplicate_books.map((b: any) => b.book_id)
    } else if (importAction.value === 'selected') {
      overwriteBookIds = selectedDuplicateBooks.value
    }

    try {
      await confirmWithStream(uploadToken.value, {
        skipDuplicates,
        overwriteBookIds
      })
    } catch (error) {
      console.error('Token式ZIP导入失败:', error)
      showNotify({ type: 'danger', message: '导入失败' })
    } finally {
      importing.value = false
      uploadToken.value = ''
    }
  }

  /**
   * 取消导入
   */
  /**
   * 完整性错误对话框 - 跳过并继续
   */
  const handleIntegrityErrorContinue = async () => {
    showIntegrityErrorDialog.value = false
    if (!uploadToken.value) {
      // 降级：没有 token 时使用旧方式
      await cleanupFailedImport(pendingIntegrityCleanup.value)
      pendingIntegrityCleanup.value = []
      integrityErrorBooks.value = []
      return
    }
    pendingIntegrityCleanup.value = []
    integrityErrorBooks.value = []
    await confirmWithStream(uploadToken.value, {
      skipDuplicates: false
    })
  }

  /**
   * 完整性错误对话框 - 取消
   */
  const handleIntegrityErrorCancel = () => {
    showIntegrityErrorDialog.value = false
    pendingIntegrityCleanup.value = []
    integrityErrorBooks.value = []
  }

  /**
   * 合并检查对话框 - 确认导入（Token式）
   */
  const handleImportCheckConfirm = async () => {
    showImportCheckDialog.value = false
    // 传入选择覆盖的书籍ID
    const selectedIds = importCheckResult.value.duplicate_books
      .filter(b => selectedDuplicateBooksForMerge.value.includes(b.title))
      .map(b => b.book_id)

    if (!uploadToken.value) return

    await confirmWithStream(uploadToken.value, {
      skipDuplicates: true,
      overwriteBookIds: selectedIds.length > 0 ? selectedIds : undefined
    })
    // 重置选择
    selectedDuplicateBooksForMerge.value = []
  }

  /**
   * 合并检查对话框 - 取消
   */
  const handleImportCheckCancel = () => {
    showImportCheckDialog.value = false
    // 重置状态
    importCheckResult.value = {
      valid_books: [],
      invalid_books: [],
      duplicate_books: [],
      total: 0,
      message: ''
    }
    selectedDuplicateBooksForMerge.value = []
  }

  /**
   * 合并对话框 - 全选/取消全选切换
   */
  const handleSelectAllToggle = () => {
    if (isSelectAllDuplicatesForMerge.value) {
      // 全选
      selectedDuplicateBooksForMerge.value = importCheckResult.value.duplicate_books.map(b => b.title)
    } else {
      // 取消全选
      selectedDuplicateBooksForMerge.value = []
    }
  }

  /**
   * 合并对话框 - 切换重复书籍选择
   */
  const toggleDuplicateBookForMerge = (title: string) => {
    const index = selectedDuplicateBooksForMerge.value.indexOf(title)
    if (index > -1) {
      selectedDuplicateBooksForMerge.value.splice(index, 1)
    } else {
      selectedDuplicateBooksForMerge.value.push(title)
    }
    // 同步全选状态
    updateSelectAllState()
  }

  /**
   * 合并对话框 - 更新全选状态
   */
  const updateSelectAllState = () => {
    const total = importCheckResult.value.duplicate_books.length
    const selected = selectedDuplicateBooksForMerge.value.length
    isSelectAllDuplicatesForMerge.value = selected === total && total > 0
  }

  const cancelImport = () => {
    // 如果存在 token，清理后端临时文件
    if (uploadToken.value) {
      cancelUploadByToken(uploadToken.value)
      uploadToken.value = ''
      uploadFileType.value = ''
    }
    showDuplicateDialog.value = false
    importAction.value = null
    importing.value = false
    importStatus.value = ''
    selectedFile.value = null
    importProgress.value = 0
    selectedDuplicateBooks.value = []
    isBatchMdImport.value = false
  }

  /**
   * 关闭导入对话框
   */
  const closeImportDialog = () => {
    showImportDialog.value = false
  }

  /**
   * 导入对话框关闭后的回调（清空所有状态）
   */
  const onImportDialogClosed = () => {
    showChoiceDialog.value = false
    showDuplicateDialog.value = false
    selectedFile.value = null
    selectedFiles.value = []
    importProgress.value = 0
    importStatus.value = ''
    overwriteMode.value = ''
    importing.value = false
    importCompleted.value = false
    currentBookId.value = ''
    isZipImport.value = false
    isBatchImport.value = false
    isBatchMdImport.value = false
    // 清空文件输入元素的值，确保下次 @change 事件可触发
    if (fileInput.value) {
      fileInput.value.value = ''
    }
    importAction.value = null
    selectedDuplicateBooks.value = []
    duplicateCheckResult.value = {
      has_duplicates: false,
      duplicate_books: [],
      new_books: [],
      total_books: 0
    }
    // 重置 token 状态
    uploadToken.value = ''
    uploadFileType.value = ''
    prepareResult.value = null

    // 重置 MP3+LRC 状态
    importMode.value = 'normal'
    needZhAudio.value = false
    needTranslation.value = false
    importedBookIds.value = []
    showMp3LrcZhDialog.value = false
    showMp3LrcCheckDialog.value = false

    // 重置中文语音生成进度
    showZhAudioProgress.value = false
    zhAudioProgress.value = 0
    zhAudioMessage.value = ''
    zhAudioLoading.value = false
  }

  // ========== 导出 ==========
  return {
    // 状态
    showImportDialog,
    importCategoryId,
    importMode,
    fileInput,
    importing,
    importCompleted,
    selectedFile,
    selectedFiles,
    isBatchImport,
    isBatchMdImport,
    isZipImport,
    isDragOver,
    importProgress,
    importStatus,
    uploading,
    uploadProgress,
    uploadStatus,
    currentBookId,
    showChoiceDialog,
    overwriteMode,
    showDuplicateDialog,
    duplicateCheckResult,
    importAction,
    selectedDuplicateBooks,

    // MP3/LRC 导入
    showMp3LrcZhDialog,
    showMp3LrcCheckDialog,
    mp3LrcCheckResult,
    importedBookIds,
    needZhAudio,
    needTranslation,

    // 中文语音生成进度
    showZhAudioProgress,
    zhAudioProgress,
    zhAudioMessage,
    zhAudioLoading,

    // Token式导入
    uploadToken,
    uploadFileType,
    prepareResult,

    // 完整性检测
    showIntegrityErrorDialog,
    integrityErrorBooks,
    handleIntegrityErrorContinue,
    handleIntegrityErrorCancel,

    // 合并检查对话框
    showImportCheckDialog,
    importCheckResult,
    selectedDuplicateBooksForMerge,
    isSelectAllDuplicatesForMerge,
    handleImportCheckConfirm,
    handleImportCheckCancel,
    toggleDuplicateBookForMerge,
    handleSelectAllToggle,

    // 计算属性
    hasSelectedFile,

    // 方法
    openImportDialog,
    triggerFileInput,
    onFileDrop,
    onFileSelected,
    handleFile,
    handleMultipleFiles,
    handleImportConfirm,
    handleBatchImport,
    doImportZip,
    doImport,
    handleImportWithOverwrite,
    handleImportSkipDuplicates,
    handleImportSelected,
    doBatchImportWithAction,
    doImportZipWithAction,
    cancelImport,
    closeImportDialog,
    onImportDialogClosed,
    toggleDuplicateSelect,
    selectAllDuplicates,
    clearAllDuplicates,
    checkZipDuplicates,
    checkMdDuplicates,
    uploadWithProgress,
    uploadWithProgressCallback,
    uploadWithProgressAndStream,

    // Token式方法
    confirmWithStream,
    cancelUploadByToken,

    // MP3/LRC 方法
    switchImportMode,
    handleMp3LrcImport,
    handleMp3LrcCheckAndImport,
    handleMp3LrcCheckContinue,
    handleMp3LrcCheckCancel,
    handleGenerateChineseAudio,
    handleMp3LrcZhLater,
  }
}
