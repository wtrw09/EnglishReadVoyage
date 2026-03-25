import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showNotify, showToast } from 'vant'
import { useAuthStore } from '@/store/auth'
import { uploadWithProgress, uploadWithStream } from '@/utils/upload'
import type { DuplicateCheckResult, DuplicateBook, NewBook } from '@/types'

export function useBookImport() {
  const router = useRouter()
  const authStore = useAuthStore()

  // 状态
  const showImportDialog = ref(false)
  const importCategoryId = ref(0)
  const importing = ref(false)
  const importCompleted = ref(false)
  const selectedFile = ref<File | null>(null)
  const selectedFiles = ref<File[]>([])
  const isBatchImport = ref(false)
  const isBatchMdImport = ref(false)
  const isZipImport = ref(false)
  const isDragOver = ref(false)
  const importProgress = ref(0)
  const importStatus = ref('')
  const uploading = ref(false)
  const uploadProgress = ref(0)
  const uploadStatus = ref('')
  const currentBookId = ref('')
  const overwriteMode = ref('')

  // 重复检测相关
  const showDuplicateDialog = ref(false)
  const duplicateCheckResult = ref<DuplicateCheckResult>({
    has_duplicates: false,
    duplicate_books: [],
    new_books: [],
    total_books: 0
  })
  const selectedDuplicateBooks = ref<string[]>([])
  const importAction = ref<'skip' | 'overwrite' | 'selected' | null>(null)

  // 导入完成后选择对话框
  const showChoiceDialog = ref(false)

  // 计算属性
  const hasSelectedFile = computed(() => selectedFile.value !== null || selectedFiles.value.length > 0)

  // 打开导入对话框
  const openImportDialog = (categoryId: number) => {
    importCategoryId.value = categoryId
    showImportDialog.value = true
  }

  // 关闭导入对话框
  const closeImportDialog = () => {
    showImportDialog.value = false
  }

  // 重置所有状态
  const resetState = () => {
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

  // 处理文件拖放
  const onFileDrop = (event: DragEvent) => {
    isDragOver.value = false
    if (importing.value) return

    const files = event.dataTransfer?.files
    if (files && files.length > 0) {
      handleFile(files[0])
    }
  }

  // 处理文件选择
  const onFileSelected = (files: FileList | null) => {
    if (!files || files.length === 0) return

    if (files.length === 1) {
      handleFile(files[0])
    } else {
      // 多文件处理（只接受MD文件）
      handleMultipleFiles(Array.from(files))
    }
  }

  // 处理单个文件
  const handleFile = (file: File) => {
    if (!file.name.endsWith('.md') && !file.name.endsWith('.zip')) {
      showNotify({ type: 'danger', message: '只支持 .md 或 .zip 格式的文件' })
      return
    }

    if (!authStore.isLoggedIn) {
      showToast('请先登录')
      router.push('/login')
      return
    }

    // 如果之前已完成导入，重置状态
    if (importCompleted.value) {
      resetState()
    }

    selectedFile.value = file
    selectedFiles.value = []
    isBatchImport.value = false
  }

  // 处理多个文件
  const handleMultipleFiles = (files: File[]) => {
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
      router.push('/login')
      return
    }

    if (importCompleted.value) {
      resetState()
    }

    selectedFiles.value = mdFiles
    isBatchImport.value = true
  }

  // 检查ZIP文件重复
  const checkZipDuplicates = async (file: File): Promise<DuplicateCheckResult> => {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const result = await uploadWithProgress({
        url: '/api/v1/books/check-zip-duplicates',
        formData,
        statusText: '正在上传ZIP检查重复'
      })

      if (!result.ok) {
        return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
      }

      return result.data || { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    } catch (error) {
      console.error('检查重复书籍失败:', error)
      return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    }
  }

  // 检查MD文件重复
  const checkMdDuplicates = async (files: File[]): Promise<DuplicateCheckResult> => {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    try {
      const result = await uploadWithProgress({
        url: '/api/v1/books/check-md-duplicates',
        formData,
        statusText: '正在上传文件检查重复'
      })

      if (!result.ok) {
        return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
      }

      return result.data || { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    } catch (error) {
      console.error('检查MD文件重复书籍失败:', error)
      return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    }
  }

  // 确认导入
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
      // ZIP文件：先检查重复
      if (isZipImport.value) {
        isBatchMdImport.value = false
        const duplicateCheck = await checkZipDuplicates(selectedFile.value)

        if (duplicateCheck.has_duplicates) {
          duplicateCheckResult.value = duplicateCheck
          showDuplicateDialog.value = true
          importStatus.value = ''
          return
        }

        return await doImportZip(false, undefined)
      }

      // 单文件MD：先用文件名检查是否存在
      const filename = selectedFile.value.name
      const checkResponse = await fetch(`/api/v1/books/check/${encodeURIComponent(filename)}`, {
        headers: { 'Authorization': `Bearer ${authStore.token}` }
      })

      if (!checkResponse.ok) {
        throw new Error('检查书籍失败')
      }

      const checkData = await checkResponse.json()

      if (checkData.exists) {
        // 书籍已存在，需要覆盖确认
        return { type: 'confirm_overwrite', bookId: checkData.book_id, title: checkData.title }
      } else {
        return await doImport(false)
      }
    } catch (error) {
      console.error('检查书籍失败:', error)
      return await doImport(false)
    }
  }

  // 执行单文件导入
  const doImport = async (overwrite: boolean, existingBookId?: string) => {
    if (!selectedFile.value) return

    importing.value = true
    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = '正在导入...'
    overwriteMode.value = existingBookId || ''

    try {
      const formData = new FormData()
      formData.append('file', selectedFile.value)

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

      await uploadWithStream({
        url: apiPath,
        formData,
        statusText: '正在上传文件',
        onProgress: (progress) => {
          uploadProgress.value = progress
        },
        onStatusChange: (status) => {
          uploadStatus.value = status
        },
        onStreamData: (data) => {
          importProgress.value = data.percentage || 0
          importStatus.value = data.message || ''

          if (data.success === true) {
            showNotify({ type: 'success', message: data.message, duration: 1500 })
            currentBookId.value = data.book_id || overwriteMode.value || ''
            importCompleted.value = true
            if (!isZipImport.value && !isBatchImport.value) {
              showChoiceDialog.value = true
            }
          } else if (data.success === false) {
            showNotify({ type: 'danger', message: data.message })
          }
        }
      })
    } catch (error: any) {
      console.error('导入书籍失败:', error)
      showNotify({ type: 'danger', message: error.message || '导入失败，请重试' })
    } finally {
      importing.value = false
      uploading.value = false
    }
  }

  // 执行ZIP导入
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

      await uploadWithStream({
        url: apiPath,
        formData,
        statusText: '正在上传ZIP文件',
        onProgress: (progress) => {
          uploadProgress.value = progress
        },
        onStatusChange: (status) => {
          uploadStatus.value = status
        },
        onStreamData: (data) => {
          importProgress.value = data.percentage || 0
          importStatus.value = data.message || ''

          if (data.success === true) {
            showNotify({ type: 'success', message: data.message, duration: 1500 })
            currentBookId.value = data.book_id || ''
            importCompleted.value = true
          } else if (data.success === false) {
            showNotify({ type: 'danger', message: data.message })
          }
        }
      })
    } catch (error: any) {
      console.error('导入书籍失败:', error)
      showNotify({ type: 'danger', message: error.message || '导入失败，请重试' })
    } finally {
      importing.value = false
      uploading.value = false
    }
  }

  // 批量导入MD文件
  const handleBatchImport = async () => {
    if (selectedFiles.value.length === 0) return

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

        const result = await uploadWithProgress({
          url: apiPath,
          formData,
          statusText: `正在上传 (${i + 1}/${totalFiles}): ${file.name}`,
          onProgress: (progress) => {
            importProgress.value = Math.min(baseProgress + Math.round(progress / totalFiles), 99)
          }
        })

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

    if (successCount > 0) {
      showNotify({ type: 'success', message: `成功导入 ${successCount} 本书籍`, duration: 2000 })
    }
  }

  // 根据用户选择执行批量导入（带重复处理）
  const doBatchImportWithAction = async () => {
    if (selectedFiles.value.length === 0 || !importAction.value) return

    importing.value = true
    importProgress.value = 0
    importStatus.value = '正在导入书籍...'

    const skipBookIds = new Set<string>()
    const overwriteBookIds = new Set<string>()

    if (importAction.value === 'skip') {
      duplicateCheckResult.value.duplicate_books.forEach((b: DuplicateBook) => skipBookIds.add(b.book_id))
    } else if (importAction.value === 'overwrite') {
      duplicateCheckResult.value.duplicate_books.forEach((b: DuplicateBook) => overwriteBookIds.add(b.book_id))
    } else if (importAction.value === 'selected') {
      selectedDuplicateBooks.value.forEach(id => overwriteBookIds.add(id))
      duplicateCheckResult.value.duplicate_books.forEach((b: DuplicateBook) => {
        if (!selectedDuplicateBooks.value.includes(b.book_id)) {
          skipBookIds.add(b.book_id)
        }
      })
    }

    const filenameToBookId = new Map<string, string>()
    duplicateCheckResult.value.duplicate_books.forEach((b: DuplicateBook) => {
      filenameToBookId.set(b.filename, b.book_id)
    })
    duplicateCheckResult.value.new_books.forEach((b: NewBook) => {
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

        const result = await uploadWithProgress({
          url: apiPath,
          formData,
          statusText: `正在上传 (${i + 1}/${totalFiles}): ${file.name}`,
          onProgress: (progress) => {
            importProgress.value = Math.min(baseProgress + Math.round(progress / totalFiles), 99)
          }
        })

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
    isBatchMdImport.value = false
    selectedDuplicateBooks.value = []

    if (successCount > 0) {
      showNotify({ type: 'success', message: `成功导入 ${successCount} 本书籍`, duration: 2000 })
    }
  }

  // 重复书籍处理
  const toggleDuplicateSelect = (bookId: string) => {
    const index = selectedDuplicateBooks.value.indexOf(bookId)
    if (index === -1) {
      selectedDuplicateBooks.value.push(bookId)
    } else {
      selectedDuplicateBooks.value.splice(index, 1)
    }
  }

  const selectAllDuplicates = () => {
    selectedDuplicateBooks.value = duplicateCheckResult.value.duplicate_books.map((b: DuplicateBook) => b.book_id)
  }

  const clearAllDuplicates = () => {
    selectedDuplicateBooks.value = []
  }

  // 导入操作处理
  const handleImportWithOverwrite = () => {
    showDuplicateDialog.value = false
    importAction.value = 'overwrite'
    if (isBatchMdImport.value) {
      doBatchImportWithAction()
    } else {
      const bookIds = duplicateCheckResult.value.duplicate_books.map((b: DuplicateBook) => b.book_id)
      doImportZip(false, bookIds)
    }
  }

  const handleImportSkipDuplicates = () => {
    showDuplicateDialog.value = false
    importAction.value = 'skip'
    selectedDuplicateBooks.value = []
    if (isBatchMdImport.value) {
      doBatchImportWithAction()
    } else {
      doImportZip(true, undefined)
    }
  }

  const handleImportSelected = () => {
    showDuplicateDialog.value = false
    importAction.value = 'selected'
    if (isBatchMdImport.value) {
      doBatchImportWithAction()
    } else {
      doImportZip(false, selectedDuplicateBooks.value)
    }
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

  return {
    // 状态
    showImportDialog,
    importCategoryId,
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
    showDuplicateDialog,
    duplicateCheckResult,
    selectedDuplicateBooks,
    hasSelectedFile,

    // 方法
    openImportDialog,
    closeImportDialog,
    resetState,
    onFileDrop,
    onFileSelected,
    handleImportConfirm,
    doImport,
    doImportZip,
    handleBatchImport,
    toggleDuplicateSelect,
    selectAllDuplicates,
    clearAllDuplicates,
    handleImportWithOverwrite,
    handleImportSkipDuplicates,
    handleImportSelected,
    cancelImport
  }
}
