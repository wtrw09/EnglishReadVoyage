// 书籍相关类型定义

export interface Book {
  id: string
  title: string
  level: string
  file_path: string
  page_count: number
  cover_path?: string
  is_read?: number
}

export interface BookGroup {
  id: number
  name: string
  type: string
  books: Book[]
}

export interface PopoverAction {
  text: string
  icon: string
  key: string
}

// TTS 相关类型
export type TtsServiceName = 'kokoro-tts' | 'doubao-tts' | 'siliconflow-tts' | 'edge-tts' | 'minimax-tts'

export interface TtsVoice {
  id: string
  name: string
}

export interface TtsConfig {
  service_name: TtsServiceName
  voice: string
  speed: number
  api_url: string
  app_id: string
  access_key: string
  resource_id: string
  siliconflow_api_key: string
  siliconflow_model: string
  siliconflow_voice: string
  edge_tts_voice: string
  edge_tts_speed: number
  minimax_api_key: string
  minimax_model: string
  minimax_voice: string
  minimax_speed: number
}

// 导入相关类型
export interface DuplicateCheckResult {
  has_duplicates: boolean
  duplicate_books: DuplicateBook[]
  new_books: NewBook[]
  total_books: number
}

export interface DuplicateBook {
  book_id: string
  title: string
  filename: string
}

export interface NewBook {
  book_id: string
  title: string
  filename: string
}

// 导出相关类型
export interface ExportProgress {
  percentage: number
  status: string
  currentBook?: string
}

// 翻译 API 类型
export interface TranslationApi {
  id: number
  app_id: string
  is_active: boolean
}

// 用户设置类型
export interface UserSettings {
  dictionary: {
    dictionary_source: 'api' | 'local'
  }
  phonetic?: {
    accent: 'uk' | 'us'
  }
  tts?: Partial<TtsConfig>
  ui?: {
    hide_read_books_map?: Record<number, boolean>
  }
}

// 音频修复相关类型
export interface AudioErrorItem {
  book_id?: string
  title: string
  issues: string[]
}

export interface AudioFixedItem {
  book_id?: string
  title: string
  fixed_fields: string[]
  warnings: string[]
}
