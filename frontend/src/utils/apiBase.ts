/**
 * API 基地址工具
 *
 * 浏览器开发态：同源（通过 Vite dev-server 代理转发到后端）。
 * 浏览器生产态：同源（Nginx 反代到后端）。
 * Capacitor 原生态：WebView 运行于 https://localhost，必须使用绝对地址访问后端；
 *   地址由用户在 ServerConfig 页面输入并持久化到 localStorage。
 */

const STORAGE_KEY = 'server_base_url'
const VERIFIED_URLS_KEY = 'server_verified_urls'

/** 当前是否运行在 Capacitor 原生壳内 */
export function isCapacitorNative(): boolean {
  const cap = (window as any).Capacitor
  if (!cap) return false
  if (typeof cap.isNativePlatform === 'function') return cap.isNativePlatform()
  return !!cap.isNative
}

/** 当前是否运行在 HarmonyOS 原生壳内 */
export function isHarmonyNative(): boolean {
  return navigator.userAgent.includes('HarmonyOS')
    || location.protocol === 'resource:'
    || location.hostname === 'harmony.local'
}

/** 当前是否运行在原生壳内（Android Capacitor / HarmonyOS WebView） */
export function isNativeShell(): boolean {
  return isCapacitorNative() || isHarmonyNative()
}

// ---- 已验证地址历史管理 ----

/** 获取已验证的服务端地址列表 */
export function getVerifiedUrls(): string[] {
  try {
    const raw = localStorage.getItem(VERIFIED_URLS_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr.filter((u): u is string => typeof u === 'string') : []
  } catch {
    return []
  }
}

/** 将地址添加到已验证列表（去重） */
export function addVerifiedUrl(url: string): void {
  const list = getVerifiedUrls()
  const normalized = url.replace(/\/+$/, '')
  if (!list.includes(normalized)) {
    list.push(normalized)
    localStorage.setItem(VERIFIED_URLS_KEY, JSON.stringify(list))
  }
}

/** 从已验证列表中移除指定地址 */
export function removeVerifiedUrl(url: string): void {
  const list = getVerifiedUrls()
  const normalized = url.replace(/\/+$/, '')
  const filtered = list.filter(u => u !== normalized)
  localStorage.setItem(VERIFIED_URLS_KEY, JSON.stringify(filtered))
}

/** 判断当前保存的地址是否在已验证列表中 */
export function isCurrentUrlVerified(): boolean {
  const current = getServerBaseUrl()
  if (!current) return false
  return getVerifiedUrls().includes(current)
}

/** 获取已保存的服务端基地址（可能为空串） */
export function getServerBaseUrl(): string {
  const saved = localStorage.getItem(STORAGE_KEY) || ''
  return saved.replace(/\/+$/, '')
}

/** 是否已经配置过服务端地址 */
export function hasServerBaseUrl(): boolean {
  return !!localStorage.getItem(STORAGE_KEY)
}

/** 保存服务端基地址 */
export function setServerBaseUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/+$/, ''))
}

/** 清除服务端基地址 */
export function clearServerBaseUrl(): void {
  localStorage.removeItem(STORAGE_KEY)
}

/**
 * 拼接 API URL。
 * - path 可带或不带前导 '/'
 * - path 若已以 '/api/v1' 开头则直接拼接
 * - 浏览器态无 baseUrl 时返回相对路径（走 Vite / Nginx 代理）
 */
export function buildApiUrl(path: string): string {
  const base = getServerBaseUrl()
  const normalized = path.startsWith('/') ? path : '/' + path
  if (normalized.startsWith('/api/v1')) {
    return base + normalized
  }
  return base + '/api/v1' + normalized
}

/**
 * 拼接静态资源 URL，如 /books/xxx.jpg、/audio/xxx.mp3。
 * 仅在 Capacitor 原生态需要前置 base；浏览器态返回原相对路径。
 * 若传入的已是绝对 URL（http/https/data/blob/file），直接透传不做拼接。
 */
export function buildStaticUrl(path: string): string {
  if (!path) return path
  if (/^(https?:|data:|blob:|file:)/i.test(path)) {
    return path
  }
  const base = getServerBaseUrl()
  const normalized = path.startsWith('/') ? path : '/' + path
  return base + normalized
}
