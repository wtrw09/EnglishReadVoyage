import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios, { type AxiosInstance } from 'axios'
import { getServerBaseUrl, isNativeShell } from '@/utils/apiBase'
import { useNetworkStatus } from '@/utils/useNetworkStatus'

// 类型定义
export interface User {
  id: number
  username: string
  role: string
  is_active: boolean
  created_at: string
}

export interface UserDetail extends User {
  invitation_code?: string
  invitation_expires?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
  role: string
}

export interface CreateUserResponse {
  user: User
  invitation_code: string
  invitation_expires: string
}

export interface ApiError {
  success: false
  message: string
  code?: 'network_error' | 'auth_error' | 'server_error'
}

export interface ApiSuccess<T> {
  success: true
  data?: T
}

export type ApiResult<T> = ApiSuccess<T> | ApiError

// 创建 axios 实例
// baseURL 留空，改由请求拦截器根据 ServerConfig 动态拼接，使同一份前端在浏览器/Capacitor 下都能工作
export const api: AxiosInstance = axios.create({
  timeout: 600000,  // 压缩图片等耗时操作可能需要较长时间，增加到10分钟
  headers: {
    'Content-Type': 'application/json'
  }
})

// 添加响应拦截器，处理 502 错误自动重试
let retryCount = 0
const MAX_RETRIES = 3
const RETRY_DELAY = 2000 // 2秒

api.interceptors.response.use(
  (response) => {
    retryCount = 0 // 重置重试计数
    // 502 重试成功后恢复 online 状态（拦截器先注册后执行，重试成功时网络状态拦截器的 serverUnreachable 仍残留）
    const { setOnline } = useNetworkStatus()
    setOnline()
    return response
  },
  async (error) => {
    const originalRequest = error.config

    // 如果是 502 错误且未超过重试次数
    if (error.response?.status === 502 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true
      retryCount++

      if (retryCount <= MAX_RETRIES) {
        console.log(`[API] 502错误，第 ${retryCount} 次重试，${RETRY_DELAY / 1000}秒后...`)
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY))
        return api(originalRequest)
      }
    }

    retryCount = 0
    return Promise.reject(error)
  }
)

// 不需要 token 的公开接口列表
const publicEndpoints = ['/auth/login', '/auth/activate']
const REMEMBER_CREDS_KEY = 'remember_creds'

// ---- 记住我凭据管理（多账户支持）----
// 存储结构：{ lastUsedUsername: string, accounts: { [username]: 编码后的密码 } }

interface CredentialsStore {
  lastUsedUsername: string
  accounts: Record<string, string> // username -> encoded password
}

export function encodePassword(pwd: string): string {
  return btoa(encodeURIComponent(pwd))
}

export function decodePassword(encoded: string): string {
  return decodeURIComponent(atob(encoded))
}

function getCredentialsStore(): CredentialsStore | null {
  try {
    const raw = localStorage.getItem(REMEMBER_CREDS_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (typeof data !== 'object' || data === null) return null
    // 检查新格式 { lastUsedUsername, accounts }
    if (typeof data.accounts === 'object' && data.accounts !== null) {
      return data as CredentialsStore
    }
    // 旧格式 { username, password } — 忽略，重新保存时会用新格式重建
    return null
  } catch {
    return null
  }
}

function saveCredentialsStore(store: CredentialsStore): void {
  localStorage.setItem(REMEMBER_CREDS_KEY, JSON.stringify(store))
}

export function saveRememberedCredentials(username: string, password: string): void {
  const store = getCredentialsStore() || { lastUsedUsername: '', accounts: {} }
  store.accounts[username] = encodePassword(password)
  store.lastUsedUsername = username
  saveCredentialsStore(store)
}

export function getRememberedCredentials(): { username: string; password: string } | null {
  const store = getCredentialsStore()
  if (!store || !store.lastUsedUsername) return null
  const encoded = store.accounts[store.lastUsedUsername]
  if (!encoded) return null
  return { username: store.lastUsedUsername, password: decodePassword(encoded) }
}

/** 获取所有历史用户名列表 */
export function getHistoryUsernames(): string[] {
  const store = getCredentialsStore()
  return store ? Object.keys(store.accounts) : []
}

/** 根据用户名获取保存的凭据 */
export function getCredentialsByUsername(username: string): { username: string; password: string } | null {
  const store = getCredentialsStore()
  if (!store || !store.accounts[username]) return null
  return { username, password: decodePassword(store.accounts[username]) }
}

export function clearRememberedCredentials(): void {
  localStorage.removeItem(REMEMBER_CREDS_KEY)
}

/** 移除指定用户名的凭据 */
export function removeCredentialsByUsername(username: string): void {
  const store = getCredentialsStore()
  if (!store) return
  delete store.accounts[username]
  if (store.lastUsedUsername === username) {
    const usernames = Object.keys(store.accounts)
    store.lastUsedUsername = usernames.length > 0 ? usernames[0] : ''
  }
  if (Object.keys(store.accounts).length === 0) {
    localStorage.removeItem(REMEMBER_CREDS_KEY)
  } else {
    saveCredentialsStore(store)
  }
}

// 请求拦截器：动态 baseURL + 附加 token + 离线预检
api.interceptors.request.use((config) => {
  // 动态 baseURL：浏览器态同源（空串 + /api/v1 相对路径），Capacitor 原生态拼用户输入的服务端地址
  config.baseURL = `${getServerBaseUrl()}/api/v1`

  const tokenValue = localStorage.getItem('token')
  const isPublicEndpoint = publicEndpoints.some(endpoint => config.url?.includes(endpoint))

  if (tokenValue) {
    config.headers.Authorization = `Bearer ${tokenValue}`
  } else if (!isPublicEndpoint) {
    // 非公开接口且没有 token 时才打印警告
    console.warn('[API Request] No token found in localStorage for:', config.url)
  }

  // 客户端离线预检：避免请求卡住超时
  // 原生壳（Android/HarmonyOS WebView）中 navigator.onLine 可能不可靠，跳过预检
  if (!navigator.onLine && !isPublicEndpoint && !isNativeShell()) {
    const { setOffline } = useNetworkStatus()
    setOffline()
    // Axios v1.x 使用 CanceledError（取代了旧版的 Cancel）
    return Promise.reject(new axios.CanceledError('网络已断开，请求已取消'))
  }

  return config
})

// 响应拦截器处理认证错误 + 网络错误分类
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (axios.isAxiosError(error)) {
      // 打印详细错误信息
      console.error('[API Response Error]', {
        message: error.message,
        code: error.code,
        status: error.response?.status,
        statusText: error.response?.statusText,
        url: error.config?.url,
        method: error.config?.method,
      })

      const url = error.config?.url || ''
      const isLoginRequest = url.includes('/auth/login') || url.includes('/auth/activate')

      // 共享状态引用
      const { setServerUnreachable, setTokenExpired } = useNetworkStatus()

      // ========== 场景 0: 预检取消（离线时请求拦截器主动取消的请求）==========
      // 此时状态已经由请求拦截器设为 offline，不需要再处理
      if (axios.isCancel(error)) {
        return Promise.reject(error)
      }

      // ========== 场景 1: 网络不可达（无响应）==========
      // !error.response 已覆盖：ERR_NETWORK、ECONNABORTED、超时等各种无响应情况
      if (!error.response) {
        if (!isLoginRequest) {
          console.warn('[API Response] 网络不可达, code:', error.code)
          setServerUnreachable()
        }
        return Promise.reject(error)
      }

      // ========== 场景 2: Token 失效 (401) ==========
      // 但排除登录接口，登录失败返回 401 是正常的业务错误
      if (error.response?.status === 401 && !isLoginRequest) {
        console.warn('[API Response] 401 Unauthorized - Token expired or invalid')
        setTokenExpired()

        // 同步清理 Pinia store + localStorage，避免路由守卫读到"已登录"状态把用户踢回 Home
        try {
          useAuthStore().logout()
        } catch (err) {
          // 极端情况下 Pinia 未就绪时的兜底
          console.error('[API Response] Failed to logout Pinia store on 401', err)
          localStorage.removeItem('token')
          localStorage.removeItem('user')
        }

        // 跳转到登录页面
        import('@/router').then(({ default: router }) => {
          if (router.currentRoute.value.name !== 'Login') {
            router.replace({ name: 'Login' })
          }
        })
        return Promise.reject(error)
      }

      // ========== 场景 3: 服务端异常 (5xx) ==========
      // 仅网关/代理类错误 (502/503/504) 表示服务器不可达
      // 500 是服务器内部错误，服务器本身是可达的
      if (error.response && error.response.status >= 500) {
        const status = error.response.status
        console.warn('[API Response] 服务端异常, status:', status)
        if (status >= 502 && status <= 504) {
          setServerUnreachable()
        }
        // 500 不触发网络状态变化，仅 console 记录
        return Promise.reject(error)
      }
    }
    return Promise.reject(error)
  }
)

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string>(localStorage.getItem('token') || '')
  const user = ref<User | null>(JSON.parse(localStorage.getItem('user') || 'null'))
  const users = ref<UserDetail[]>([])
  const loading = ref(false)

  // Getters
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const currentUser = computed(() => user.value)

  // Actions
  
  // 登录
  async function login(username: string, password: string, rememberMe: boolean = false): Promise<ApiResult<void>> {
    loading.value = true
    try {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)

      console.log('[Login] Sending request...')
      const response = await api.post<LoginResponse>('/auth/login-detail', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      })
      
      console.log('[Login] Response:', response.data)
      console.log('[Login] access_token:', response.data.access_token)
      
      token.value = response.data.access_token
      user.value = {
        id: response.data.user_id,
        username: response.data.username,
        role: response.data.role,
        is_active: true,
        created_at: new Date().toISOString()
      }
      
      // 保存到本地存储
      localStorage.setItem('token', token.value)
      localStorage.setItem('user', JSON.stringify(user.value))
      
      // 记住我：缓存凭据
      if (rememberMe) {
        saveRememberedCredentials(username, password)
      }
      
      console.log('[Login] Token saved to localStorage:', localStorage.getItem('token'))
      
      // 登录成功后重置网络状态（清除 tokenExpired 等标记）
      const { setOnline } = useNetworkStatus()
      setOnline()
      
      return { success: true }
    } catch (error) {
      console.error('[Login] Error caught:', error)
      if (axios.isAxiosError(error)) {
        console.error('[Login] Axios error details:', {
          message: error.message,
          code: error.code,
          status: error.response?.status,
          statusText: error.response?.statusText,
          data: error.response?.data,
        })
        // 处理后端返回的错误消息，确保是字符串
        const detail = error.response?.data?.detail
        let errorMessage = '登录失败'
        let errorCode: 'network_error' | 'auth_error' | 'server_error' | undefined
        if (detail) {
          errorMessage = Array.isArray(detail) ? detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ') : String(detail)
          errorCode = error.response?.status === 401 ? 'auth_error' : undefined
        } else if (error.message) {
          errorMessage = error.message
          // 无响应 → 网络错误
          if (!error.response) {
            errorCode = 'network_error'
          }
        }
        return { 
          success: false, 
          message: errorMessage,
          code: errorCode
        }
      }
      return { success: false, message: '登录失败: ' + String(error) }
    } finally {
      loading.value = false
    }
  }

  // 退出登录
  function logout(): void {
    token.value = ''
    user.value = null
    users.value = []
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    // 记住我凭据不清除，保留用于下次自动填充
    // 设置 session 级别标记，防止回到登录页时自动登录
    sessionStorage.setItem('manual_logout', 'true')
  }

  // 激活账户
  async function activateAccount(invitationCode: string, password: string): Promise<ApiResult<void>> {
    loading.value = true
    try {
      await api.post('/auth/activate', {
        invitation_code: invitationCode,
        password: password
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      })
      return { success: true }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return {
          success: false,
          message: error.response?.data?.detail || '激活失败'
        }
      }
      return { success: false, message: '激活失败' }
    } finally {
      loading.value = false
    }
  }

  // 自动登录（使用缓存的凭据）
  async function autoLogin(): Promise<ApiResult<void>> {
    const creds = getRememberedCredentials()
    if (!creds) {
      return { success: false, message: '没有缓存的凭据' }
    }
    if (isLoggedIn.value) {
      return { success: true }
    }
    const result = await login(creds.username, creds.password, false)
    // 网络错误保留凭据供重试，认证错误也不清除（用户可在表单中修改密码）
    return result
  }

  // 获取当前用户信息
  async function fetchCurrentUser(): Promise<ApiResult<User>> {
    try {
      const response = await api.get<User>('/auth/me')
      user.value = response.data
      return { success: true, data: response.data }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '获取用户信息失败'
        }
      }
      return { success: false, message: '获取用户信息失败' }
    }
  }

  // 更新当前用户信息
  async function updateCurrentUser(username: string): Promise<ApiResult<User>> {
    try {
      const response = await api.patch<User>('/auth/me', { username })
      user.value = response.data
      localStorage.setItem('user', JSON.stringify(user.value))
      return { success: true, data: response.data }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '更新用户信息失败'
        }
      }
      return { success: false, message: '更新用户信息失败' }
    }
  }

  // ==================== 管理员功能 ====================

  // 获取所有用户
  async function fetchUsers(): Promise<ApiResult<UserDetail[]>> {
    try {
      const response = await api.get<UserDetail[]>('/auth/users')
      users.value = response.data
      return { success: true, data: response.data }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '获取用户列表失败'
        }
      }
      return { success: false, message: '获取用户列表失败' }
    }
  }

  // 创建用户
  async function createUser(username: string): Promise<ApiResult<CreateUserResponse>> {
    try {
      const response = await api.post<CreateUserResponse>('/auth/users', { username }, {
        headers: {
          'Content-Type': 'application/json'
        }
      })
      return { success: true, data: response.data }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '创建用户失败'
        }
      }
      return { success: false, message: '创建用户失败' }
    }
  }

  // 更新用户
  async function updateUser(userId: number, data: { username?: string; role?: string }): Promise<ApiResult<UserDetail>> {
    try {
      const response = await api.patch<UserDetail>(`/auth/users/${userId}`, data)
      return { success: true, data: response.data }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '更新用户失败'
        }
      }
      return { success: false, message: '更新用户失败' }
    }
  }

  // 删除用户
  async function deleteUser(userId: number): Promise<ApiResult<void>> {
    try {
      await api.delete(`/auth/users/${userId}`)
      return { success: true }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '删除用户失败'
        }
      }
      return { success: false, message: '删除用户失败' }
    }
  }

  // 重置用户密码(管理员)
  async function resetPassword(userId: number, newPassword: string): Promise<ApiResult<void>> {
    try {
      await api.post(`/auth/users/${userId}/reset-password`, { new_password: newPassword })
      return { success: true }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '重置密码失败'
        }
      }
      return { success: false, message: '重置密码失败' }
    }
  }

  // 获取用户邀请码(管理员)
  async function getUserInvitationCode(userId: number): Promise<ApiResult<UserDetail>> {
    try {
      const response = await api.get<UserDetail>(`/auth/users/${userId}/invitation-code`)
      return { success: true, data: response.data }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '获取邀请码失败'
        }
      }
      return { success: false, message: '获取邀请码失败' }
    }
  }

  // 当前用户修改自己的密码
  async function changePassword(oldPassword: string, newPassword: string): Promise<ApiResult<void>> {
    try {
      await api.post('/auth/me/change-password', {
        old_password: oldPassword,
        new_password: newPassword
      })
      return { success: true }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return { 
          success: false, 
          message: error.response?.data?.detail || '修改密码失败'
        }
      }
      return { success: false, message: '修改密码失败' }
    }
  }

  return {
    // State
    token,
    user,
    users,
    loading,
    // Getters
    isLoggedIn,
    isAdmin,
    currentUser,
    // Actions
    login,
    logout,
    autoLogin,
    fetchCurrentUser,
    updateCurrentUser,
    fetchUsers,
    createUser,
    updateUser,
    deleteUser,
    resetPassword,
    getUserInvitationCode,
    changePassword,
    activateAccount
  }
})
