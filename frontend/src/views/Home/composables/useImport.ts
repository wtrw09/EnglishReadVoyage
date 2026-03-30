/**
 * 导入功能 Composable
 * 集中管理所有导入相关的状态和方法
 */
import { ref, computed } from 'vue'
import { showNotify, showToast, showConfirmDialog } from 'vant'
import { useAuthStore } from '@/store/auth'
import type { DuplicateCheckResult } from '../types'

export const useImport = () => {
  const authStore = useAuthStore()

  // ========== 导入相关状态 ==========

  // 导入对话框显示状态
  const showImportDialog = ref(false)

  // 导入目标分类ID
  const importCategoryId = ref(0)

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

  // 覆盖模式（已有书籍ID）
  const overwriteMode = ref('')

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

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100)
          uploadProgress.value = percentComplete
          if (percentComplete >= 95) {
            uploadStatus.value = '后端处理中，请稍候...'
          } else {
            uploadStatus.value = `${statusText}... ${percentComplete}%`
          }
        }
      })

      xhr.addEventListener('load', async () => {
        uploading.value = false
        uploadProgress.value = 0
        uploadStatus.value = ''

        importing.value = true
        importProgress.value = 0
        importStatus.value = '正在处理...'

        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const text = xhr.responseText
            const matches = text.matchAll(/data: (\{.*?\})/g)
            for (const match of matches) {
              try {
                const data = JSON.parse(match[1])
                importProgress.value = data.percentage || 0
                importStatus.value = data.message || ''

                if (data.success === true) {
                  showNotify({ type: 'success', message: data.message, duration: 1500 })
                  if (!data.book_id && overwriteMode.value) {
                    currentBookId.value = overwriteMode.value
                  } else {
                    currentBookId.value = data.book_id || ''
                  }
                  importCompleted.value = true
                  if (!isZipImport.value && !isBatchImport.value) {
                    showChoiceDialog.value = true
                  }
                } else if (data.success === false) {
                  showNotify({ type: 'danger', message: data.message })
                }
              } catch (e) {
                console.error('解析SSE数据失败:', e)
              }
            }
            resolve()
          } catch (e) {
            resolve()
          }
        } else {
          reject(new Error('导入请求失败'))
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

  // ========== 检查重复书籍 ==========

  /**
   * 检查ZIP文件中的重复书籍
   */
  const checkZipDuplicates = async (file: File): Promise<DuplicateCheckResult> => {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const result = await uploadWithProgress(
        '/api/v1/books/check-zip-duplicates',
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
        '/api/v1/books/check-zip-integrity',
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
        '/api/v1/books/check-zip-all',
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
      xhr.open('POST', '/api/v1/books/cleanup-failed-import')
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
        '/api/v1/books/check-md-duplicates',
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
   * 处理文件
   */
  const handleFile = async (file: File) => {
    if (!file.name.endsWith('.md') && !file.name.endsWith('.zip')) {
      showNotify({ type: 'danger', message: '只支持 .md 或 .zip 格式的文件' })
      return
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
    // 批量导入模式
    if (isBatchImport.value && selectedFiles.value.length > 0) {
      isBatchMdImport.value = true

      const duplicateCheck = await checkMdDuplicates(selectedFiles.value)

      if (duplicateCheck.has_duplicates) {
        duplicateCheckResult.value = duplicateCheck
        showDuplicateDialog.value = true
        importStatus.value = ''
        return
      }

      await handleBatchImport()
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
      if (isZipImport.value) {
        isBatchMdImport.value = false

        // 合并检查完整性+重复
        const checkResult = await checkZipAll(selectedFile.value)
        
        // 显示检查结果对话框
        importCheckResult.value = checkResult
        showImportCheckDialog.value = true
        importStatus.value = ''
        return
      }

      // 单个 MD 文件也使用 check-md-duplicates 接口检测重复
      const duplicateCheck = await checkMdDuplicates([selectedFile.value])

      if (duplicateCheck.has_duplicates) {
        duplicateCheckResult.value = duplicateCheck
        showDuplicateDialog.value = true
        importStatus.value = ''
        return
      }

      return await doImport(false)
    } catch (error: any) {
      console.error('检查书籍失败:', error)
      return await doImport(false)
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
        let apiPath = '/api/v1/books/import'
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
      let apiPath = '/api/v1/books/import'
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
      let apiPath = overwrite ? '/api/v1/books/import/overwrite' : '/api/v1/books/import'
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

  // ========== 重复书籍处理 ==========

  /**
   * 覆盖导入（导入所有书籍，包括重复的）
   */
  const handleImportWithOverwrite = () => {
    showDuplicateDialog.value = false
    importAction.value = 'overwrite'

    if (isBatchMdImport.value) {
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

    if (isBatchMdImport.value) {
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

    if (isBatchMdImport.value) {
      doBatchImportWithAction()
    } else {
      doImportZipWithAction()
    }
  }

  /**
   * 根据用户选择执行批量MD导入
   */
  const doBatchImportWithAction = async () => {
    if (selectedFiles.value.length === 0 || !importAction.value) return

    importing.value = true
    importProgress.value = 0
    importStatus.value = '正在导入书籍...'

    const skipBookIds = new Set<string>()
    const overwriteBookIds = new Set<string>()

    if (importAction.value === 'skip') {
      duplicateCheckResult.value.duplicate_books.forEach((b: any) => skipBookIds.add(b.book_id))
    } else if (importAction.value === 'overwrite') {
      duplicateCheckResult.value.duplicate_books.forEach((b: any) => overwriteBookIds.add(b.book_id))
    } else if (importAction.value === 'selected') {
      selectedDuplicateBooks.value.forEach(id => overwriteBookIds.add(id))
      duplicateCheckResult.value.duplicate_books.forEach((b: any) => {
        if (!selectedDuplicateBooks.value.includes(b.book_id)) {
          skipBookIds.add(b.book_id)
        }
      })
    }

    const filenameToBookId = new Map<string, string>()
    duplicateCheckResult.value.duplicate_books.forEach((b: any) => {
      filenameToBookId.set(b.filename, b.book_id)
    })
    duplicateCheckResult.value.new_books.forEach((b: any) => {
      filenameToBookId.set(b.filename, b.book_id)
    })

    const totalFiles = selectedFiles.value.length
    let successCount = 0
    let failCount = 0
    let skipCount = 0

    for (let i = 0; i < totalFiles; i++) {
      const file = selectedFiles.value[i]
      const bookId = filenameToBookId.get(file.name)
      const baseProgress = Math.round((i / totalFiles) * 100)

      if (bookId && skipBookIds.has(bookId)) {
        skipCount++
        importProgress.value = Math.min(baseProgress + Math.round(100 / totalFiles), 99)
        importStatus.value = `跳过 (${i + 1}/${totalFiles}): ${file.name}`
        continue
      }

      try {
        const formData = new FormData()
        formData.append('file', file)

        const categoryId = importCategoryId.value
        let apiPath = '/api/v1/books/import'
        const params = new URLSearchParams()

        if (categoryId) {
          params.append('category_id', categoryId.toString())
        }

        if (bookId && overwriteBookIds.has(bookId)) {
          params.append('overwrite_book_ids', bookId)
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
    const summary = skipCount > 0
      ? `批量导入完成: 成功 ${successCount} 本, 跳过 ${skipCount} 本, 失败 ${failCount} 本`
      : `批量导入完成: 成功 ${successCount} 本, 失败 ${failCount} 本`
    importStatus.value = summary
    importCompleted.value = true
    importing.value = false

    if (successCount > 0) {
      showNotify({ type: 'success', message: `成功导入 ${successCount} 本书籍`, duration: 2000 })
    }

    isBatchMdImport.value = false
    selectedDuplicateBooks.value = []
  }

  /**
   * 根据用户选择执行ZIP导入
   */
  const doImportZipWithAction = async () => {
    if (!selectedFile.value || !importAction.value) return

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

    await doImportZip(skipDuplicates, overwriteBookIds)
  }

  /**
   * 取消导入
   */
  /**
   * 完整性错误对话框 - 跳过并继续
   */
  const handleIntegrityErrorContinue = async () => {
    showIntegrityErrorDialog.value = false
    // 清理不完整的书籍
    await cleanupFailedImport(pendingIntegrityCleanup.value)
    pendingIntegrityCleanup.value = []
    integrityErrorBooks.value = []
    // 继续导入（不再重复检查）
    await doImportZip(false, undefined)
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
   * 合并检查对话框 - 确认导入
   */
  const handleImportCheckConfirm = async () => {
    showImportCheckDialog.value = false
    // 传入选择覆盖的书籍ID
    const selectedIds = importCheckResult.value.duplicate_books
      .filter(b => selectedDuplicateBooksForMerge.value.includes(b.title))
      .map(b => b.book_id)
    await doImportZip(true, selectedIds.length > 0 ? selectedIds : undefined)
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
    importAction.value = null
    selectedDuplicateBooks.value = []
    duplicateCheckResult.value = {
      has_duplicates: false,
      duplicate_books: [],
      new_books: [],
      total_books: 0
    }
  }

  // ========== 导出 ==========
  return {
    // 状态
    showImportDialog,
    importCategoryId,
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
  }
}
