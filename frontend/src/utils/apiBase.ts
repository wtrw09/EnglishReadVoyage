/**
 * API 基地址工具
 *
 * 浏览器开发态：同源（通过 Vite dev-server 代理转发到后端）。
 * 浏览器生产态：同源（Nginx 反代到后端）。
 * Capacitor 原生态：WebView 运行于 https://localhost，必须使用绝对地址访问后端；
 *   地址由用户在 ServerConfig 页面输入并持久化到 localStorage。
 */

const STORAGE_KEY = 'server_base_url'
const VERIFIED_SERVERS_KEY = 'server_verified_list'
const OLD_VERIFIED_URLS_KEY = 'server_verified_urls'

// ---- 数据迁移：从旧格式（URL 数组）迁移到新格式（ServerEntry 数组） ----
;(function migrateOldData(): void {
  try {
    const oldRaw = localStorage.getItem(OLD_VERIFIED_URLS_KEY)
    if (!oldRaw) return
    // 旧数据存在且新数据已存在时跳过迁移
    if (localStorage.getItem(VERIFIED_SERVERS_KEY)) return
    const oldArr = JSON.parse(oldRaw)
    if (!Array.isArray(oldArr)) return
    const entries = oldArr
      .filter((u): u is string => typeof u === 'string' && u.length > 0)
      .map(url => ({
        url: url.replace(/\/+$/, ''),
        name: generateDefaultName(url),
        lastUsed: Date.now()
      }))
    if (entries.length > 0) {
      localStorage.setItem(VERIFIED_SERVERS_KEY, JSON.stringify(entries))
    }
    // 迁移完成后删除旧数据
    localStorage.removeItem(OLD_VERIFIED_URLS_KEY)
  } catch {
    // 迁移失败不影响主流程
  }
})()

/** 服务器条目接口 */
export interface ServerEntry {
  url: string;
  name: string;
  lastUsed: number;
}

/** 服务器名称最大长度 */
export const MAX_SERVER_NAME_LENGTH = 20;

/** 根据 URL 获取服务器名称（从已验证列表或默认） */
export function getServerName(url: string): string {
  const list = getVerifiedServerList();
  const normalized = normalizeUrl(url);
  const entry = list.find(e => normalizeUrl(e.url) === normalized);
  return entry?.name || '';
}

/** 获取已验证的服务器完整列表（按最后使用时间倒序） */
export function getVerifiedServerList(): ServerEntry[] {
  try {
    const raw = localStorage.getItem(VERIFIED_SERVERS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    // 过滤无效条目并按最后使用时间倒序
    return arr
      .filter((e): e is ServerEntry =>
        typeof e === 'object' && e !== null &&
        typeof e.url === 'string' &&
        typeof e.name === 'string' &&
        typeof e.lastUsed === 'number'
      )
      .sort((a, b) => b.lastUsed - a.lastUsed);
  } catch {
    return [];
  }
}

/** 获取已验证的服务端地址列表（仅 URL，用于向后兼容） */
export function getVerifiedUrls(): string[] {
  return getVerifiedServerList().map(e => e.url);
}

/** 归一化 URL（去尾部斜杠） */
function normalizeUrl(url: string): string {
  return url.replace(/\/+$/, '');
}

/** 添加或更新已验证的服务器（带名称） */
export function addVerifiedServer(url: string, name: string = ''): void {
  const list = getVerifiedServerList();
  const normalized = normalizeUrl(url);
  const existingIndex = list.findIndex(e => normalizeUrl(e.url) === normalized);
  
  const entry: ServerEntry = {
    url: normalized,
    name: name || generateDefaultName(normalized),
    lastUsed: Date.now()
  };
  
  if (existingIndex >= 0) {
    // 更新现有条目（保留名称如果新名称为空）
    if (!name && list[existingIndex].name) {
      entry.name = list[existingIndex].name;
    }
    list[existingIndex] = entry;
  } else {
    list.unshift(entry);
  }
  
  // 限制最多保存 20 条
  const trimmed = list.slice(0, 20);
  localStorage.setItem(VERIFIED_SERVERS_KEY, JSON.stringify(trimmed));
}

/** 生成默认服务器名称 */
function generateDefaultName(url: string): string {
  try {
    const hostname = new URL(url).hostname;
    // 取主机名最后一段或 IP 地址的前三段
    const parts = hostname.split('.');
    if (parts.length > 2) {
      return parts.slice(-2).join('.');
    }
    return hostname;
  } catch {
    return '服务器';
  }
}

/** 添加地址到已验证列表（去重，向后兼容） */
export function addVerifiedUrl(url: string): void {
  addVerifiedServer(url);
}

/** 更新服务器名称 */
export function updateServerName(url: string, newName: string): void {
  const list = getVerifiedServerList();
  const normalized = normalizeUrl(url);
  const index = list.findIndex(e => normalizeUrl(e.url) === normalized);
  
  if (index >= 0) {
    list[index].name = newName.slice(0, MAX_SERVER_NAME_LENGTH);
    localStorage.setItem(VERIFIED_SERVERS_KEY, JSON.stringify(list));
  }
}

/** 从已验证列表中移除指定地址 */
export function removeVerifiedServer(url: string): void {
  const list = getVerifiedServerList();
  const normalized = normalizeUrl(url);
  const filtered = list.filter(e => normalizeUrl(e.url) !== normalized);
  localStorage.setItem(VERIFIED_SERVERS_KEY, JSON.stringify(filtered));
}

/** 从已验证列表中移除指定地址（向后兼容） */
export function removeVerifiedUrl(url: string): void {
  removeVerifiedServer(url);
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

// ---- 原生壳检测 ----

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

// ---- 服务器选择（供外部使用） ----

/** 清除单个服务器（同时清除当前选中如果匹配） */
export function clearServerEntry(url: string): void {
  removeVerifiedServer(url)
  if (getServerBaseUrl() === normalizeUrl(url)) {
    clearServerBaseUrl()
  }
}
