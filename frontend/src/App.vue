<template>
  <!-- 原生壳标识class，用于CSS安全区域适配 -->
  <div id="app-root" :class="{ 'is-native-shell': isNativeShell(), 'is-capacitor-shell': isCapacitorNative() }">
    <!-- 全局网络状态通知栏（可关闭，点击可手动重连） -->
    <div
      v-if="networkStatus !== 'online' && !dismissed"
      class="network-banner"
      :class="'banner-' + networkStatus"
      @click="handleBannerClick"
    >
      <!-- 检测中：统一显示加载动画，不区分状态类型 -->
      <template v-if="isChecking">
        <i class="fas fa-spinner fa-spin"></i>
        <span>正在检测连接...</span>
      </template>
      <template v-else-if="networkStatus === 'offline'">
        <i class="fas fa-wifi"></i>
        <span>网络已断开，请检查网络连接</span>
      </template>
      <template v-else-if="networkStatus === 'serverUnreachable'">
        <i class="fas fa-exclamation-triangle"></i>
        <span>无法连接到服务器，点击重试连接</span>
      </template>
      <template v-else-if="networkStatus === 'tokenExpired'">
        <i class="fas fa-user-lock"></i>
        <span>登录已过期，请点击重新登录</span>
        <i class="fas fa-chevron-right"></i>
      </template>
      <!-- 检测中禁用关闭按钮 -->
      <i v-if="!isChecking" class="fas fa-xmark banner-close" @click.stop="dismissed = true"></i>
    </div>

    <!-- 页面内容 -->
    <router-view v-slot="{ Component }">
      <keep-alive include="Home">
        <component :is="Component" />
      </keep-alive>
    </router-view>
  </div>

  <!-- 连接管理面板（仅原生壳：Android Capacitor / HarmonyOS WebView） -->
  <van-action-sheet
    v-if="isNativeShell()"
    v-model:show="showConnectionSheet"
    title="连接管理"
    :close-on-click-action="false"
  >
    <div class="connection-sheet">
      <!-- 诊断信息 -->
      <div class="sheet-section">
        <div class="diag-row">
          <span class="diag-label">连接状态</span>
          <span class="diag-value" :class="'status-' + networkStatus">
            <template v-if="networkStatus === 'serverUnreachable'">服务器不可达</template>
            <template v-else-if="networkStatus === 'offline'">网络已断开</template>
            <template v-else>{{ networkStatus }}</template>
          </span>
        </div>
        <div class="diag-row">
          <span class="diag-label">服务器地址</span>
          <span class="diag-value diag-url">{{ currentServerUrl }}</span>
        </div>
        <div class="diag-row">
          <span class="diag-label">检测方式</span>
          <span class="diag-value">心跳检测间隔 30 秒</span>
        </div>
      </div>

      <!-- 历史可用地址 -->
      <div v-if="serverList.length" class="sheet-section">
        <div class="url-list-title">历史可用地址</div>
        <div
          v-for="server in serverList"
          :key="server.url"
          class="url-item"
          :class="{ active: server.url === currentServerUrl }"
          @click="switchToServer(server)"
        >
          <div class="url-info">
            <span class="url-name">{{ server.name || '未命名' }}</span>
            <span class="url-text">{{ server.url }}</span>
          </div>
          <van-tag v-if="server.url === currentServerUrl" plain type="primary">当前</van-tag>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="sheet-actions">
        <van-button
          round
          block
          type="primary"
          :loading="isChecking"
          @click="handleSheetRetry"
        >
          重新检查连接
        </van-button>
        <van-button
          round
          block
          plain
          type="default"
          @click="handleSheetChangeServer"
        >
          修改服务器地址
        </van-button>
      </div>

      <div class="sheet-footer-hint">
        连接恢复后此面板将自动关闭
      </div>
    </div>
  </van-action-sheet>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useNetworkStatus } from '@/utils/useNetworkStatus'
import {
  getServerBaseUrl,
  isNativeShell,
  isCapacitorNative,
  getVerifiedServerList,
  setServerBaseUrl,
  type ServerEntry
} from '@/utils/apiBase'

const router = useRouter()
const { status: networkStatus, checkConnection } = useNetworkStatus()

// 用户手动关闭横幅后，新的异常状态出现时重新显示
const dismissed = ref(localStorage.getItem('bannerDismissed') === 'true')
watch(dismissed, (val) => {
  localStorage.setItem('bannerDismissed', String(val))
})
// 点击重连时的加载中状态，提供视觉反馈
const isChecking = ref(false)
// ActionSheet 面板显示控制
const showConnectionSheet = ref(false)
// 历史可用服务器列表
const serverList = ref<ServerEntry[]>(getVerifiedServerList())
// 当前服务器地址显示
const currentServerUrl = computed(() => {
  const url = getServerBaseUrl()
  return url || '未配置'
})
// Toast 防抖：5 秒内不重复弹出恢复提示
const lastRecoveryToast = ref(0)
watch(networkStatus, (newStatus, oldStatus) => {
  // 状态恢复时自动关闭连接管理面板
  if (newStatus === 'online' && showConnectionSheet.value) {
    showConnectionSheet.value = false
  }

  // 如果状态变为 online：横幅自动隐藏（v-if 控制）
  if (newStatus === 'online') {
    if (oldStatus !== 'online') {
      const now = Date.now()
      if (now - lastRecoveryToast.value > 5000) {
        showToast({ type: 'success', message: '网络连接已恢复', duration: 1500 })
        lastRecoveryToast.value = now
      }
    }
    return
  }
  // 新的异常状态（与之前不同），重置关闭状态，让横幅重新显示
  if (oldStatus !== newStatus) {
    dismissed.value = false
  }
})

async function handleBannerClick() {
  if (isChecking.value) return // 检测中忽略重复点击

  if (networkStatus.value === 'tokenExpired') {
    router.replace({ name: 'Login' })
    return
  }

  if (networkStatus.value === 'serverUnreachable' || networkStatus.value === 'offline') {
    if (isNativeShell()) {
      // 原生壳：弹出连接管理面板
      serverList.value = getVerifiedServerList()
      showConnectionSheet.value = true
    } else {
      // Web 浏览器：保留原有重试逻辑
      isChecking.value = true
      await checkConnection()
      isChecking.value = false
      // String() 返回 string 类型，绕过 TS 在 if 块内对窄化类型的不变感知
      if (String(networkStatus.value) !== 'online') {
        showToast({ type: 'fail', message: '连接失败', duration: 1500 })
      }
    }
  }
}

// 面板：重试连接
async function handleSheetRetry() {
  showConnectionSheet.value = false
  isChecking.value = true
  await checkConnection()
  isChecking.value = false
  // await 后重新读取运行时状态
  if (networkStatus.value !== 'online') {
    showToast({ type: 'fail', message: '连接失败', duration: 1500 })
  }
}

// 面板：跳转服务器配置页
async function handleSheetChangeServer() {
  showConnectionSheet.value = false
  // ServerConfig 路由标记为 guest，已登录用户会被守卫拦截跳回 Home
  // 先登出清理登录状态，确保可以正常进入配置页
  const { useAuthStore } = await import('@/store/auth')
  useAuthStore().logout()
  router.push({ name: 'ServerConfig' })
}

// 面板：切换到历史地址
async function switchToServer(server: ServerEntry) {
  showConnectionSheet.value = false
  const oldUrl = getServerBaseUrl()
  setServerBaseUrl(server.url)
  isChecking.value = true
  await checkConnection()
  isChecking.value = false
  // await 后重新读取运行时状态
  if (networkStatus.value === 'online') {
    // 新地址可达后才清除旧服务器的登录状态，确保回滚时不丢失登录状态
    const { useAuthStore } = await import('@/store/auth')
    useAuthStore().logout()
    const displayName = server.name || server.url
    showToast({ type: 'success', message: '已切换至: ' + displayName, duration: 1500 })
    // 需要重新登录获取新服务器上的 token
    router.replace({ name: 'Login' })
  } else {
    // 新地址不可达，回滚旧地址，保留用户登录状态
    setServerBaseUrl(oldUrl)
    showToast({ type: 'fail', message: '该地址也无法连通，已恢复原地址', duration: 2000 })
  }
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
  background-color: #f7f8fa;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica,
    Segoe UI, Arial, Roboto, 'PingFang SC', 'miui', 'Hiragino Sans GB', 'Microsoft Yahei',
    sans-serif;
}

/* 增加弹出菜单列宽 - Vant 4 Popover */
.van-popover .van-popover__action {
  min-width: 180px !important;
}

.van-popover .van-popover__action-text {
  min-width: 180px !important;
  white-space: nowrap !important;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Capacitor (Android) 安全区域适配 - 缩小 nav-bar placeholder 带来的顶部空隙 */
.is-capacitor-shell .home > .content {
  margin-top: -16px;
}

/* 全局网络状态栏 */
.network-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 13px;
  line-height: 1.4;
  cursor: pointer;
  z-index: 2001;
  position: relative;
}

/* 原生壳环境下网络横幅也需要安全区域适配 */
.is-native-shell .network-banner {
  padding-top: calc(10px + env(safe-area-inset-top, 0px));
}

.network-banner i {
  font-size: 14px;
}

.network-banner span {
  flex: 1;
}

.network-banner .fa-chevron-right {
  font-size: 12px;
  opacity: 0.6;
}

.banner-close {
  font-size: 16px !important;
  cursor: pointer;
  padding: 4px;
  margin-left: 8px;
  flex-shrink: 0;
  opacity: 0.7;
}

.banner-close:hover {
  opacity: 1;
}

.banner-offline {
  background: #ee0a24;
  color: #fff;
}

.banner-serverUnreachable {
  background: #ff976a;
  color: #fff;
}

.banner-tokenExpired {
  background: #ee0a24;
  color: #fff;
}

/* 连接管理面板 */
.connection-sheet {
  padding: 0 16px 20px;
}
.sheet-section {
  margin-bottom: 16px;
}
.diag-row {
  display: flex;
  align-items: center;
  padding: 8px 0;
  font-size: 13px;
  border-bottom: 1px solid #f5f5f5;
}
.diag-label {
  color: #969799;
  width: 80px;
  flex-shrink: 0;
}
.diag-value {
  flex: 1;
  color: #323233;
  text-align: right;
  word-break: break-all;
}
.diag-value.status-serverUnreachable {
  color: #ee0a24;
}
.diag-value.status-offline {
  color: #ee0a24;
}
.diag-value.status-tokenExpired {
  color: #ee0a24;
}
.diag-url {
  font-size: 12px;
}
.url-list-title {
  font-size: 14px;
  font-weight: 500;
  color: #323233;
  margin-bottom: 8px;
}
.url-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background: #f7f8fa;
  border-radius: 8px;
  margin-bottom: 6px;
  font-size: 13px;
  cursor: pointer;
}
.url-item:active {
  opacity: 0.7;
}
.url-item.active {
  border: 1px solid #1989fa;
  background: #f0f9ff;
}
.url-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.url-name {
  font-size: 14px;
  font-weight: 500;
  color: #323233;
}
.url-text {
  font-size: 12px;
  color: #969799;
  word-break: break-all;
}
.sheet-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
}
.sheet-footer-hint {
  text-align: center;
  font-size: 11px;
  color: #c8c9cc;
  margin-top: 12px;
}
</style>
