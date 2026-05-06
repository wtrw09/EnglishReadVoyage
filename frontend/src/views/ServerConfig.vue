<!--
  ServerConfig.vue - 服务端地址配置页

  仅 Capacitor 原生态需要：WebView 运行在 https://localhost，必须告诉 App 后端服务在哪。
  浏览器态也可以访问此页手动切换服务端，但不会被路由守卫强制进入。
-->
<template>
  <div class="server-config-page">
    <van-nav-bar
      title="服务端地址设置"
      :left-arrow="canGoBack"
      @click-left="handleBack"
      fixed
      placeholder
    />

    <div class="content">
      <div class="logo-area">
        <i class="fas fa-server logo-icon" />
        <h2>英语阅读之旅</h2>
        <p>请输入后端服务地址以继续</p>
      </div>

      <van-cell-group inset>
        <van-field
          v-model="serverUrl"
          label="服务地址"
          placeholder="如 http://192.168.1.100:8888"
          clearable
          :error-message="errorMsg"
        />
      </van-cell-group>

      <div class="tips">
        <p>• 支持 http 或 https</p>
        <p>• 请确保手机与服务端处于同一局域网或可直接访问</p>
        <p>• 示例：http://192.168.1.100:8888 或 https://api.example.com</p>
      </div>

      <!-- 历史可用地址（仅原生壳） -->
      <div v-if="nativeShell && verifiedUrls.length" class="history-section">
        <div class="history-title">历史可用地址</div>
        <div
          v-for="url in verifiedUrls"
          :key="url"
          class="history-item"
          :class="{ active: url === savedUrl }"
        >
          <span class="history-url">{{ url }}</span>
          <van-tag v-if="url === savedUrl" type="primary" class="current-tag">当前</van-tag>
          <div class="history-actions">
            <van-button size="mini" type="primary" plain @click="selectUrl(url)">使用</van-button>
            <van-button size="mini" type="danger" plain @click="deleteUrl(url)">删除</van-button>
          </div>
        </div>
      </div>

      <div class="actions">
        <van-button
          round
          block
          type="primary"
          :loading="testing"
          loading-text="测试连接中..."
          @click="handleSave"
        >
          测试并保存
        </van-button>

        <van-button
          v-if="savedUrl"
          round
          block
          plain
          type="default"
          class="clear-btn"
          @click="handleClear"
        >
          清除已保存地址
        </van-button>
      </div>

      <div v-if="savedUrl" class="current">
        当前：{{ savedUrl }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showDialog } from 'vant'
import {
  getServerBaseUrl,
  setServerBaseUrl,
  clearServerBaseUrl,
  hasServerBaseUrl,
  isNativeShell,
  getVerifiedUrls,
  addVerifiedUrl,
  removeVerifiedUrl
} from '@/utils/apiBase'

const router = useRouter()

const serverUrl = ref(getServerBaseUrl())
const savedUrl = ref(getServerBaseUrl())
const errorMsg = ref('')
const testing = ref(false)
const verifiedUrls = ref(getVerifiedUrls())

const nativeShell = computed(() => isNativeShell())
const canGoBack = computed(() => hasServerBaseUrl())

// 归一化：去空白、去尾斜杠、缺协议头时自动补 http://
function normalize(url: string): string {
  let v = url.trim().replace(/\/+$/, '')
  if (v && !/^https?:\/\//i.test(v)) {
    v = 'http://' + v
  }
  return v
}

function validate(url: string): string | null {
  if (!url) return '服务地址不能为空'
  if (!/^https?:\/\//i.test(url)) return '地址必须以 http:// 或 https:// 开头'
  try {
    new URL(url)
  } catch {
    return '地址格式不正确'
  }
  return null
}

// Capacitor 原生态下 localhost/127.0.0.1 指向手机本身，会连不上宿主后端
function isLoopbackHost(url: string): boolean {
  try {
    const h = new URL(url).hostname.toLowerCase()
    return h === 'localhost' || h === '127.0.0.1' || h === '[::1]'
  } catch {
    return false
  }
}

async function testConnection(url: string): Promise<boolean> {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 8000)
    // 优先请求一个已知存在的轻量级端点，避免根路径 404 被误判为不联通
    const res = await fetch(`${url}/api/v1/dictionary/status`, { signal: controller.signal })
    clearTimeout(timer)
    return res.ok
  } catch {
    return false
  }
}

async function handleSave() {
  const url = normalize(serverUrl.value)
  const err = validate(url)
  if (err) {
    errorMsg.value = err
    return
  }
  errorMsg.value = ''

  // Capacitor 原生壳下填 localhost 是常见误用，主动提示用户确认
  if (isNativeShell() && isLoopbackHost(url)) {
    const confirmed = await showDialog({
      title: '提示',
      message: 'APP 里的 localhost/127.0.0.1 指的是手机本身，而不是你的电脑或服务器。\n\n请改为：\n• 模拟器：http://10.0.2.2:端口\n• 真机同网段：http://电脑局域IP:端口\n\n仍要继续保存吗？',
      showCancelButton: true,
      confirmButtonText: '继续',
      cancelButtonText: '改填'
    }).then(() => true).catch(() => false)
    if (!confirmed) return
  }

  testing.value = true
  const ok = await testConnection(url)
  testing.value = false

  if (!ok) {
    errorMsg.value = '无法连通该地址，请确认服务端已启动且网络可达'
    return
  }

  setServerBaseUrl(url)
  addVerifiedUrl(url)
  savedUrl.value = url
  serverUrl.value = url
  verifiedUrls.value = getVerifiedUrls()
  showToast({ type: 'success', message: '已保存', duration: 1000 })
}

function handleClear() {
  clearServerBaseUrl()
  savedUrl.value = ''
  serverUrl.value = ''
  showToast({ type: 'success', message: '已清除', duration: 1000 })
}

function selectUrl(url: string) {
  serverUrl.value = url
  errorMsg.value = ''

  testing.value = true
  testConnection(url).then(ok => {
    testing.value = false
    if (!ok) {
      errorMsg.value = '无法连通该地址，请确认服务端已启动且网络可达'
      return
    }
    setServerBaseUrl(url)
    addVerifiedUrl(url)
    savedUrl.value = url
    verifiedUrls.value = getVerifiedUrls()
    showToast({ type: 'success', message: '已切换', duration: 1000 })
  })
}

function deleteUrl(url: string) {
  removeVerifiedUrl(url)
  verifiedUrls.value = getVerifiedUrls()
  showToast({ type: 'success', message: '已删除', duration: 800 })
}

function handleBack() {
  if (canGoBack.value) router.back()
}
</script>

<style scoped lang="less">
.server-config-page {
  min-height: 100vh;
  background: #f7f8fa;
}
.content {
  padding: 20px;
}
.logo-area {
  text-align: center;
  padding: 32px 0 24px;

  .logo-icon {
    font-size: 64px;
    color: #1989fa;
  }

  h2 {
    margin: 12px 0 6px;
    font-size: 22px;
    color: #323233;
  }

  p {
    margin: 0;
    font-size: 14px;
    color: #969799;
  }
}
.tips {
  margin: 16px 4px 24px;

  p {
    margin: 4px 0;
    font-size: 12px;
    color: #969799;
  }
}
.actions {
  margin: 0 16px;

  .clear-btn {
    margin-top: 12px;
  }
}
.current {
  margin-top: 16px;
  text-align: center;
  font-size: 12px;
  color: #646566;
  word-break: break-all;
  padding: 0 16px;
}
.history-section {
  margin: 16px 4px;
}
.history-title {
  font-size: 14px;
  color: #323233;
  font-weight: 500;
  margin-bottom: 8px;
  padding: 0 12px;
}
.history-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  word-break: break-all;

  &.active {
    border: 1px solid #1989fa;
  }
}
.history-url {
  flex: 1;
  color: #323233;
  margin-right: 8px;
}
.current-tag {
  margin-right: 8px;
  flex-shrink: 0;
}
.history-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
</style>
