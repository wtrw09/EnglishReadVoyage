/**
 * useNetworkStatus - 全局网络连接状态管理
 *
 * 职责：
 * - 被动检测网络连接状态（axios 请求结果驱动）
 * - 浏览器 online/offline 事件监听
 * - Capacitor 前后台切换自动检测
 * - 提供手动重试连接方法
 *
 * 使用方式：模块级单例，任意位置导入 useNetworkStatus() 获取同一个状态实例
 * 可在 axios 拦截器、Vue 组件、Pinia store 中安全使用
 */
import { ref, computed } from 'vue'
import { getServerBaseUrl, isNativeShell } from './apiBase'

// ---- 类型定义 ----

export type ConnectionStatus =
  | 'online'            // 一切正常，客户端网络连通且服务端可达
  | 'offline'           // 客户端网络断开（navigator.onLine = false）
  | 'serverUnreachable' // 客户端网络正常但服务端不可达
  | 'tokenExpired'      // Token 失效（服务端返回 401）

// ---- 模块级单例状态 ----

const status = ref<ConnectionStatus>('online')
const lastCheckTime = ref(0)

// 计算属性
const isOnline = computed(() => status.value === 'online')
const isOffline = computed(() => status.value !== 'online')

// ---- 内部工具函数 ----

/** 获取心跳检测用的轻量端点 */
function getHealthEndpoint(): string {
  const base = getServerBaseUrl()
  return `${base}/api/v1/dictionary/status`
}

/** 获取 Token 验证端点 */
function getMeEndpoint(): string {
  const base = getServerBaseUrl()
  return `${base}/api/v1/auth/me`
}

/** 从 localStorage 获取 token */
function getToken(): string | null {
  return localStorage.getItem('token')
}

// ---- 状态设置函数 ----

function setOnline(): void {
  if (status.value !== 'online') {
    status.value = 'online'
  }
  lastCheckTime.value = Date.now()
}

function setOffline(): void {
  if (status.value !== 'offline') {
    status.value = 'offline'
  }
  lastCheckTime.value = Date.now()
}

function setServerUnreachable(): void {
  if (status.value !== 'serverUnreachable') {
    status.value = 'serverUnreachable'
  }
  lastCheckTime.value = Date.now()
}

function setTokenExpired(): void {
  if (status.value !== 'tokenExpired') {
    status.value = 'tokenExpired'
  }
  lastCheckTime.value = Date.now()
}

// ---- 核心检测逻辑 ----

/** 立即检测服务端是否可达，返回 true 表示可达 */
async function pingServer(): Promise<boolean> {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5000)
    const res = await fetch(getHealthEndpoint(), {
      method: 'GET',
      signal: controller.signal,
    })
    clearTimeout(timer)
    return res.ok
  } catch {
    return false
  }
}

/** 当前 token 是否仍然有效（调用 /auth/me 验证）
 * 返回值：'valid' = 令牌有效 | 'expired' = 401 失效 | 'networkError' = 网络问题 */
async function verifyToken(): Promise<'valid' | 'expired' | 'networkError'> {
  const token = getToken()
  if (!token) return 'expired'

  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5000)
    const res = await fetch(getMeEndpoint(), {
      method: 'GET',
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
    clearTimeout(timer)

    if (res.status === 401) {
      // Token 已失效
      return 'expired'
    }
    // 500/502/503 等是服务端问题，不是 token 过期，按网络错误处理
    // 避免 checkConnection 误删用户 token
    if (!res.ok) {
      return 'networkError'
    }
    return 'valid'
  } catch (e) {
    // 区分超时（网络问题）和其他错误
    if (e instanceof DOMException && e.name === 'AbortError') {
      return 'networkError'
    }
    return 'networkError'
  }
}

/**
 * 执行一次完整的连接检查（手动触发）：
 * 1. 检查客户端网络
 * 2. 检测服务端可达性
 * 3. 恢复连接后验证 token
 *
 * 带并发防护 + URL 变化检测：服务端地址变更后自动启动新检查
 */
let checkConnectionPromise: Promise<void> | null = null
let checkConnectionBaseUrl: string = ''

async function checkConnection(): Promise<void> {
  const currentBaseUrl = getServerBaseUrl()
  // 仅当有进行中的请求且服务端地址未变化时才复用
  if (checkConnectionPromise && checkConnectionBaseUrl === currentBaseUrl) {
    return checkConnectionPromise
  }
  // URL 已变化或没有进行中请求：启动新的检测
  checkConnectionPromise = _doCheckConnection().finally(() => {
    checkConnectionPromise = null
    checkConnectionBaseUrl = ''
  })
  checkConnectionBaseUrl = currentBaseUrl
  return checkConnectionPromise
}

/** checkConnection 的真正实现 */
async function _doCheckConnection(): Promise<void> {
  // 第一步：用真实网络请求确认服务器可达性（不完全依赖 navigator.onLine）
  // navigator.onLine 可能不可靠（浏览器/OS 误报），直接 pingServer 更准确
  const serverAlive = await pingServer()
  if (!serverAlive) {
    // 服务器不可达，用 navigator.onLine 区分是客户端断网还是仅服务端问题
    if (!navigator.onLine) {
      setOffline()
    } else {
      setServerUnreachable()
    }
    return
  }

  // 第二步：服务端可达，如果之前是异常状态，需要验证 token
  const previousStatus = status.value
  if (previousStatus !== 'online') {
    // 之前断线过，检查 token 是否仍有效
    const token = getToken()
    if (token) {
      const tokenResult = await verifyToken()
      if (tokenResult === 'expired') {
        // Token 401 真正失效，触发登出流程
        setTokenExpired()
        // 清理本地 token
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        // 同步清理 Pinia store，避免路由守卫读到过期登录状态
        try {
          const { useAuthStore } = await import('@/store/auth')
          useAuthStore().logout()
        } catch {
          // Pinia 未就绪时的兜底，localStorage 已清理
        }
        return
      } else if (tokenResult === 'networkError') {
        // pingServer() 成功说明服务器可达，token 验证的网络错误可能是瞬时的
        // 设 serverUnreachable 而非保持离线，避免状态栏显示"网络已断开"（offline 横幅更严重）
        setServerUnreachable()
        return
      }
      // tokenResult === 'valid'：继续执行，下面会 setOnline()
    } else {
    }
  }

  setOnline()
}

// ---- 事件监听 ----

let offlineTimer: ReturnType<typeof setTimeout> | null = null

function handleOnline(): void {
  // 清除 pending 的离线确认，避免 online 后又被延迟的 timeout 设回 offline
  if (offlineTimer !== null) {
    clearTimeout(offlineTimer)
    offlineTimer = null
  }
  // 客户端网络恢复，立即检查服务端和 token
  checkConnection()
}

function handleOffline(): void {
  // 延迟确认，避免瞬时的网络切换（如睡眠唤醒、接口变更）导致误报
  // 有些浏览器在睡眠唤醒时先 off 再 on，立即设 offline 会导致横幅闪烁
  // 清除前一个定时器，防止连续 offline 事件堆积
  if (offlineTimer !== null) {
    clearTimeout(offlineTimer)
  }
  offlineTimer = setTimeout(() => {
    offlineTimer = null
    if (!navigator.onLine) {
      setOffline()
    } else {
    }
  }, 2000)
}

// ---- Capacitor 前后台监听 ----

async function setupCapacitorListener(): Promise<void> {
  try {
    const cap = (window as any).Capacitor
    if (!cap?.isNativePlatform?.()) return

    const { App } = await import('@capacitor/app')
    App.addListener('appStateChange', ({ isActive }: { isActive: boolean }) => {
      if (isActive) {
        checkConnection()
      }
    })
  } catch {
    // Capacitor 插件不可用，忽略
  }
}

// ---- 初始化 ----

let initialized = false

function initialize(): void {
  if (initialized) return
  initialized = true

  // 1. 初始状态检测：调用 checkConnection 用真实请求确认（不直接信任 navigator.onLine）
  checkConnection()

  // 2. 监听浏览器 online/offline 事件
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)

  // 3. 如果是原生壳，设置 Capacitor 监听
  if (isNativeShell()) {
    setupCapacitorListener()
  }
}

// 模块加载时自动初始化
initialize()

// ---- 导出 ----

export function useNetworkStatus() {
  return {
    /** 当前连接状态 */
    status,
    /** 是否处于正常在线状态 */
    isOnline,
    /** 是否处于离线状态（包括 serverUnreachable 和 tokenExpired） */
    isOffline,
    /** 上次检测时间戳 */
    lastCheckTime,

    // 状态设置方法（供 axios 拦截器等外部模块调用）
    setOnline,
    setOffline,
    setServerUnreachable,
    setTokenExpired,

    // 检测方法
    checkConnection: checkConnection,
    pingServer,
    verifyToken,
  }
}
