import { ref } from 'vue'
import { useAuthStore } from '@/store/auth'

export interface UploadOptions {
  url: string
  formData: FormData
  statusText?: string
  onProgress?: (progress: number) => void
  onStatusChange?: (status: string) => void
}

export interface UploadResult {
  ok: boolean
  data: any
}

export interface UploadState {
  uploading: boolean
  progress: number
  status: string
}

/**
 * 创建上传状态管理
 */
export function useUploadState() {
  const uploading = ref(false)
  const progress = ref(0)
  const status = ref('')

  const reset = () => {
    uploading.value = false
    progress.value = 0
    status.value = ''
  }

  const setUploading = (value: boolean) => {
    uploading.value = value
  }

  const setProgress = (value: number) => {
    progress.value = value
  }

  const setStatus = (value: string) => {
    status.value = value
  }

  return {
    uploading,
    progress,
    status,
    reset,
    setUploading,
    setProgress,
    setStatus
  }
}

/**
 * 带进度回调的上传函数
 */
export function uploadWithProgress(options: UploadOptions): Promise<UploadResult> {
  const { url, formData, statusText = '正在上传', onProgress, onStatusChange } = options
  const authStore = useAuthStore()

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    // 监听上传进度
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const percentComplete = Math.round((event.loaded / event.total) * 100)
        onProgress?.(percentComplete)
        onStatusChange?.(`${statusText}... ${percentComplete}%`)
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

    // 设置请求
    xhr.open('POST', url)
    xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
    xhr.send(formData)
  })
}

/**
 * 带进度和流式响应的上传函数（用于导入书籍）
 */
export interface StreamUploadOptions extends UploadOptions {
  onStreamData?: (data: any) => void
  onComplete?: () => void
}

export function uploadWithStream(options: StreamUploadOptions): Promise<void> {
  const { url, formData, statusText = '正在上传', onProgress, onStatusChange, onStreamData, onComplete } = options
  const authStore = useAuthStore()

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    // 监听上传进度
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const percentComplete = Math.round((event.loaded / event.total) * 100)
        onProgress?.(percentComplete)
        if (percentComplete >= 95) {
          onStatusChange?.('后端处理中，请稍候...')
        } else {
          onStatusChange?.(`${statusText}... ${percentComplete}%`)
        }
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const text = xhr.responseText
          // 解析SSE消息
          const matches = text.matchAll(/data: (\{.*?\})/g)
          for (const match of matches) {
            try {
              const data = JSON.parse(match[1])
              onStreamData?.(data)
            } catch (e) {
              console.error('解析SSE数据失败:', e)
            }
          }
          onComplete?.()
          resolve()
        } catch (e) {
          resolve()
        }
      } else {
        reject(new Error('导入请求失败'))
      }
    })

    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed'))
    })

    xhr.addEventListener('abort', () => {
      reject(new Error('Upload aborted'))
    })

    // 设置请求
    xhr.open('POST', url)
    xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
    xhr.send(formData)
  })
}

/**
 * 下载文件并监听进度
 */
export interface DownloadOptions {
  url: string
  method?: string
  body?: any
  onProgress?: (loaded: number, total: number) => void
  onComplete?: (blob: Blob, filename: string) => void
}

export function downloadWithProgress(options: DownloadOptions): Promise<void> {
  const { url, method = 'GET', body, onProgress, onComplete } = options
  const authStore = useAuthStore()

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open(method, url)
    xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
    if (body) {
      xhr.setRequestHeader('Content-Type', 'application/json')
    }
    xhr.responseType = 'blob'

    let totalSize = 0

    // 从响应头获取文件大小
    xhr.addEventListener('readystatechange', () => {
      if (xhr.readyState === 2) {
        const contentLength = xhr.getResponseHeader('Content-Length')
        if (contentLength) {
          totalSize = parseInt(contentLength, 10)
        }
      }
    })

    // 监听下载进度
    xhr.addEventListener('progress', (event) => {
      onProgress?.(event.loaded, totalSize || event.total)
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const blob = xhr.response

        // 获取文件名
        const contentDisposition = xhr.getResponseHeader('content-disposition')
        let filename = 'download'
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/i)
          if (filenameMatch) {
            filename = decodeURIComponent(filenameMatch[1].trim().replace(/"/g, ''))
          }
        }

        onComplete?.(blob, filename)
        resolve()
      } else {
        reject(new Error('Download failed'))
      }
    })

    xhr.addEventListener('error', () => {
      reject(new Error('Network error'))
    })

    xhr.addEventListener('abort', () => {
      reject(new Error('Download cancelled'))
    })

    xhr.send(body ? JSON.stringify(body) : null)
  })
}
