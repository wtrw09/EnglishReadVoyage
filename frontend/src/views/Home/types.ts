/**
 * Home.vue 类型定义文件
 * 集中管理所有接口和类型定义
 */

// 书籍接口
export interface Book {
  id: string
  title: string
  level: string
  file_path: string
  page_count: number
  cover_path?: string
  is_read?: number
}

// 分组接口
export interface BookGroup {
  id: number
  name: string
  type: string
  books: Book[]
}

// Popover 操作项接口
export interface PopoverAction {
  text: string
  icon: string
  key: string
}

// 默认 TTS 配置
export interface DefaultTtsConfig {
  service_name: string
  voice: string
  voice_zh: string
  speed: number
  api_url: string
  app_id: string
  access_key: string
  resource_id: string
  siliconflow_api_key: string
  siliconflow_model: string
  siliconflow_voice: string
  siliconflow_voice_zh: string
  edge_tts_voice: string
  edge_tts_voice_zh: string
  edge_tts_speed: number
  minimax_api_key: string
  minimax_model: string
  minimax_voice: string
  minimax_voice_zh: string
  minimax_speed: number
  azure_subscription_key: string
  azure_region: string
  azure_voice: string
  azure_voice_zh: string
  azure_speed: number
  kokoro_voice: string
  kokoro_voice_zh: string
  doubao_voice: string
  doubao_voice_zh: string
}

// 语音项
export interface VoiceItem {
  id: string
  name: string
}

// 重复书籍项
export interface DuplicateBook {
  book_id: string
  title: string
  filename?: string
}

// 重复检测结果
export interface DuplicateCheckResult {
  has_duplicates: boolean
  duplicate_books: DuplicateBook[]
  new_books: DuplicateBook[]
  total_books: number
}

// 移动书籍相关
export interface CategoryItem {
  id: number
  name: string
}

// 预编译缓存状态
export interface PrecompileCacheStatus {
  total: number
  cached: number
  percentage: number
}

// 音频修复结果项
export interface AudioFixedItem {
  book_id?: string
  title: string
  fixed_fields: string[]
  warnings: string[]
}

// 音频错误项
export interface AudioErrorItem {
  book_id?: string
  title: string
  issues: string[]
}

// 翻译 API 接口
export interface TranslationApi {
  id: number
  app_id: string
  is_active: boolean
}

// 硅基流动模型
export interface SiliconflowModel {
  id: string
  name: string
}

// 硅基流动语音
export interface SiliconflowVoice {
  id: string
  name: string
}

// BookEditDialog 组件引用类型
export interface BookEditDialogRef {
  closeImagePreview: () => void
}

// 预编译进度响应
export interface PrecompileProgress {
  percentage: number
  message: string
}

// 补充翻译进度响应
export interface SupplementProgress {
  percentage: number
  message: string
  success?: boolean
}

// 导入结果
export interface ImportResult {
  success: boolean
  message: string
  book_id?: string
}

// 书籍重命名响应
export interface RenameResult {
  new_id: string
  new_title: string
  new_cover_path?: string
}

// 上传结果
export interface UploadResult {
  ok: boolean
  data?: any
}

// TTS 测试请求体
export interface TtsTestRequest {
  text: string
  voice: string
  speed: number
  service_name: string
  siliconflow_api_key?: string | null
  siliconflow_model?: string | null
  minimax_api_key?: string | null
  minimax_model?: string | null
}

// 书籍封面检查标记
export type CoverCheckedBooks = Set<string>
