import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios, { type AxiosInstance } from 'axios'

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
}

export interface ApiSuccess<T> {
  success: true
  data?: T
}

export type ApiResult<T> = ApiSuccess<T> | ApiError

// 创建 axios 实例
export const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
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

// 请求拦截器添加 token
api.interceptors.request.use((config) => {
  const tokenValue = localStorage.getItem('token')
  const isPublicEndpoint = publicEndpoints.some(endpoint => config.url?.includes(endpoint))

  if (tokenValue) {
    config.headers.Authorization = `Bearer ${tokenValue}`
  } else if (!isPublicEndpoint) {
    // 非公开接口且没有 token 时才打印警告
    console.warn('[API Request] No token found in localStorage for:', config.url)
  }
  return config
})

// 响应拦截器处理认证错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
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
      
      // 401 Unauthorized - Token 过期或无效
      // 但排除登录接口，登录失败返回 401 是正常的业务错误
      const url = error.config?.url || ''
      const isLoginRequest = url.includes('/auth/login') || url.includes('/auth/activate')
      
      if (error.response?.status === 401 && !isLoginRequest) {
        console.warn('[API Response] 401 Unauthorized - Token expired or invalid')

        // 清除本地存储的 token 和用户信息
        localStorage.removeItem('token')
        localStorage.removeItem('user')

        // 跳转到登录页面
        window.location.href = '/login'
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
  async function login(username: string, password: string): Promise<ApiResult<void>> {
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
      
      console.log('[Login] Token saved to localStorage:', localStorage.getItem('token'))
      
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
        if (detail) {
          errorMessage = Array.isArray(detail) ? detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ') : String(detail)
        } else if (error.message) {
          errorMessage = error.message
        }
        return { 
          success: false, 
          message: errorMessage
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
