import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { hasServerBaseUrl, isNativeShell } from '@/utils/apiBase'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { requiresAuth: true, keepAlive: true }
  },
  {
    path: '/book/:id',
    name: 'Reader',
    component: () => import('@/views/Reader.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/server-config',
    name: 'ServerConfig',
    component: () => import('@/views/ServerConfig.vue'),
    meta: { guest: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true }
  },
  {
    path: '/users',
    name: 'UserManagement',
    component: () => import('@/views/UserManagement.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/vocabulary',
    name: 'Vocabulary',
    component: () => import('@/views/Vocabulary.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/audiobook',
    name: 'Audiobook',
    component: () => import('@/views/AudiobookPlayer.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/dictionary',
    name: 'Dictionary',
    component: () => import('@/views/Dictionary.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin/user-books/:userId',
    name: 'UserBookAssignment',
    component: () => import('@/components/UserBookAssignment.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  }
]

const router = createRouter({
  history: isNativeShell() ? createWebHashHistory() : createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  const isLoggedIn = authStore.isLoggedIn
  const isAdmin = authStore.isAdmin

  // 原生壳（Android Capacitor / HarmonyOS）且未配置服务端地址：强制进 ServerConfig 页
  if (isNativeShell() && !hasServerBaseUrl() && to.name !== 'ServerConfig') {
    next({ name: 'ServerConfig' })
    return
  }

  // 需要登录的页面
  if (to.meta.requiresAuth && !isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  // 需要管理员权限的页面
  if (to.meta.requiresAdmin && !isAdmin) {
    next({ name: 'Home' })
    return
  }

  // 游客页面（如登录页），已登录用户自动跳转
  if (to.meta.guest && isLoggedIn) {
    next({ name: 'Home' })
    return
  }

  next()
})

export default router
