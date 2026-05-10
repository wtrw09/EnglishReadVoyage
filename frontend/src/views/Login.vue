/**
 * Login.vue - 登录页面
 *
 * 功能：
 * - 用户登录（用户名/密码）
 * - 账户激活（通过邀请码）
 * - 表单验证和错误提示
 */
<template>
  <div class="login-page">
    <van-nav-bar 
      :title="isActivateMode ? '账户激活' : '用户登录'" 
      :left-arrow="isActivateMode"
      @click-left="switchToLogin"
      fixed 
      placeholder 
    />
    
    <div class="login-content">
      <div class="logo-area">
        <i class="fas fa-list logo-icon" />
        <h2>英语阅读之旅</h2>
        <p>{{ isActivateMode ? '请输入邀请码激活账户' : '请登录以继续' }}</p>
      </div>

      <!-- 自动登录状态（所有平台） -->
      <div v-if="autoLoggingIn" class="server-status checking">
        <van-loading type="spinner" size="18" /> 自动登录中...
      </div>

      <!-- 服务端状态提示（仅原生壳） -->
      <template v-if="nativeShell && !autoLoggingIn">
        <div v-if="serverStatus === 'checking'" class="server-status checking">
          <van-loading type="spinner" size="18" /> 正在检查服务端连接...
        </div>
        <div v-else-if="serverStatus === 'unreachable'" class="server-status unreachable">
          <i class="fas fa-exclamation-triangle"></i>
          <span>无法连接到服务端，请修改服务端地址</span>
          <van-button size="mini" plain type="primary" :disabled="isHealthChecking" @click="retryCheck">重试连接</van-button>
        </div>
      </template>

      <!-- 登录表单 -->
      <van-form v-if="!isActivateMode" @submit="onSubmit" class="login-form">
        <van-cell-group inset>
          <van-field
            v-model="form.username"
            name="username"
            label="用户名"
            placeholder="请输入用户名"
            :rules="[{ required: true, message: '请填写用户名' }]"
            left-icon="fa-user"
            :right-icon="usernameHistoryList.length > 0 ? 'arrow-down' : ''"
            :disabled="nativeShell && serverStatus === 'unreachable'"
            @click-right-icon="onUsernameClick"
          />
          <van-field
            v-model="form.password"
            type="password"
            name="password"
            label="密码"
            placeholder="请输入密码"
            :rules="[{ required: true, message: '请填写密码' }]"
            left-icon="fa-lock"
            :disabled="nativeShell && serverStatus === 'unreachable'"
          />
        </van-cell-group>

        <div class="checkbox-area">
          <van-checkbox v-model="rememberMe" shape="square" size="18">
            记住我
          </van-checkbox>
        </div>

        <div class="submit-area">
          <van-button
            round
            block
            :type="nativeShell && serverStatus === 'unreachable' ? 'default' : 'primary'"
            native-type="submit"
            :loading="authStore.loading"
            :disabled="nativeShell && serverStatus === 'unreachable'"
          >
            {{ nativeShell && serverStatus === 'unreachable' ? '服务端不可用' : '登录' }}
          </van-button>
        </div>

        <div class="switch-mode">
          <span class="text-link" @click="switchToActivate">激活账户</span>
          <span v-if="nativeShell" class="text-link divider">|</span>
          <span v-if="nativeShell" class="text-link" @click="goServerConfig">修改服务端地址</span>
        </div>
      </van-form>

      <!-- 激活表单 -->
      <van-form v-else @submit="onActivateSubmit" class="login-form">
        <van-cell-group inset>
          <van-field
            v-model="activateForm.invitationCode"
            name="invitationCode"
            label="邀请码"
            placeholder="请输入邀请码"
            :rules="[{ required: true, message: '请填写邀请码' }]"
            left-icon="fa-ticket"
          />
          <van-field
            v-model="activateForm.password"
            type="password"
            name="password"
            label="设置密码"
            placeholder="请设置登录密码"
            :rules="[{ required: true, message: '请设置密码' }]"
            left-icon="fa-lock"
          />
          <van-field
            v-model="activateForm.confirmPassword"
            type="password"
            name="confirmPassword"
            label="确认密码"
            placeholder="请再次输入密码"
            :rules="[
              { required: true, message: '请确认密码' },
              { validator: validateConfirmPassword, message: '两次输入的密码不一致' }
            ]"
            left-icon="fa-lock"
          />
        </van-cell-group>

        <div class="submit-area">
          <van-button
            round
            block
            type="primary"
            native-type="submit"
            :loading="authStore.loading"
          >
            激活
          </van-button>
        </div>

      </van-form>

      <!-- 历史用户名选择弹出框 -->
      <van-popup
        v-model:show="showUsernamePicker"
        position="bottom"
        round
        closeable
        title="选择历史账户"
      >
        <div class="history-title">选择历史账户</div>
        <van-cell-group>
          <van-cell
            v-for="item in usernameHistoryList"
            :key="item"
            :title="item"
            icon="contact"
            is-link
            @click="selectHistoryUser(item)"
          />
        </van-cell-group>
        <div class="history-clear-area">
          <van-button plain size="small" type="danger" @click="clearHistory">清除历史记录</van-button>
        </div>
      </van-popup>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showNotify } from 'vant'
import { useAuthStore, getRememberedCredentials, getHistoryUsernames, getCredentialsByUsername, clearRememberedCredentials } from '@/store/auth'
import { isNativeShell, getServerBaseUrl } from '@/utils/apiBase'
import { useNetworkStatus } from '@/utils/useNetworkStatus'

interface LoginForm {
  username: string
  password: string
}

interface ActivateForm {
  invitationCode: string
  password: string
  confirmPassword: string
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 是否为激活模式
const isActivateMode = ref(false)

// 服务端连接状态（仅原生壳）
const serverStatus = ref<'checking' | 'reachable' | 'unreachable'>('reachable')
const isHealthChecking = ref(false)
const nativeShell = computed(() => isNativeShell())
const { checkConnection, status: networkStatus } = useNetworkStatus()
const rememberMe = ref(true)
const autoLoggingIn = ref(false)

// 用户名历史选择
const showUsernamePicker = ref(false)
const usernameHistoryList = computed(() => getHistoryUsernames())

function onUsernameClick() {
  if (nativeShell.value && serverStatus.value === 'unreachable') return
  if (usernameHistoryList.value.length === 0) return
  showUsernamePicker.value = true
}

function selectHistoryUser(username: string) {
  showUsernamePicker.value = false
  form.username = username
  const creds = getCredentialsByUsername(username)
  form.password = creds ? creds.password : ''
}

function clearHistory() {
  showUsernamePicker.value = false
  clearRememberedCredentials()
  form.username = ''
  form.password = ''
}

// 登录表单
const form = reactive<LoginForm>({
  username: '',
  password: ''
})

// 激活表单
const activateForm = reactive<ActivateForm>({
  invitationCode: '',
  password: '',
  confirmPassword: ''
})

// 切换到激活模式
const switchToActivate = () => {
  isActivateMode.value = true
}

// 跳转服务端配置页
const goServerConfig = () => {
  router.push({ name: 'ServerConfig' })
}

// 切换到登录模式
const switchToLogin = () => {
  isActivateMode.value = false
}

// 验证确认密码
const validateConfirmPassword = (value: string) => {
  return value === activateForm.password
}

// 加载完成后检查服务端状态
onMounted(() => {
  if (isNativeShell()) {
    checkServerHealth()
  } else {
    // Web 浏览器：无需健康检查，直接尝试自动登录
    tryAutoLogin()
  }
})

// ========== 健康检查 ==========

let healthCheckSeq = 0

async function checkServerHealth() {
  if (!getServerBaseUrl()) {
    serverStatus.value = 'unreachable'
    return
  }
  const seq = ++healthCheckSeq
  isHealthChecking.value = true
  serverStatus.value = 'checking'
  await checkConnection()
  // 过期响应忽略，防止快速多次重试时状态被旧结果覆盖
  if (seq !== healthCheckSeq) return
  serverStatus.value = networkStatus.value === 'online' ? 'reachable' : 'unreachable'
  isHealthChecking.value = false
  if (networkStatus.value === 'online') await tryAutoLogin()
}

async function tryAutoLogin() {
  if (!authStore.isLoggedIn) {
    // 手动退出登录后不自动登录，只填充凭据到表单
    const isManualLogout = sessionStorage.getItem('manual_logout') === 'true'
    if (isManualLogout) {
      sessionStorage.removeItem('manual_logout')
      fillSavedCredentials()
      return
    }

    autoLoggingIn.value = true
    const result = await authStore.autoLogin()
    autoLoggingIn.value = false
    if (result.success) {
      const redirect = route.query.redirect as string
      router.replace(redirect || '/')
    } else {
      console.log('[AutoLogin] Failed:', result.message)
      fillSavedCredentials()
    }
  }
}

/** 将保存的凭据填充到表单（可能没有凭据） */
function fillSavedCredentials() {
  const creds = getRememberedCredentials()
  if (creds) {
    form.username = creds.username
    form.password = creds.password
  }
}

function retryCheck() {
  checkServerHealth()
}

// 登录提交
const onSubmit = async () => {
  const result = await authStore.login(form.username, form.password, rememberMe.value)
  
  if (result.success) {
    showNotify({ type: 'success', message: '登录成功', duration: 1500 })
    // 跳转到之前尝试访问的页面或首页
    const redirect = route.query.redirect as string
    router.replace(redirect || '/')
  } else {
    // 只清除密码，保留用户名
    form.password = ''
    showNotify({ type: 'danger', message: result.message })
  }
}

// 激活提交
const onActivateSubmit = async () => {
  const result = await authStore.activateAccount(
    activateForm.invitationCode,
    activateForm.password
  )
  
  if (result.success) {
    showNotify({
      type: 'success',
      message: '激活成功，请使用新密码登录',
      duration: 1500,
      onClose: () => {
        // 清空激活表单并切换到登录模式
        activateForm.invitationCode = ''
        activateForm.password = ''
        activateForm.confirmPassword = ''
        isActivateMode.value = false
      }
    })
  } else {
    showNotify({ type: 'danger', message: result.message })
  }
}
</script>

<style scoped lang="less">
.login-page {
  min-height: 100vh;
  background: #f7f8fa;
}

.login-content {
  padding: 20px;
}

.logo-area {
  text-align: center;
  padding: 40px 0;

  .logo-icon {
    font-size: 80px;
    color: #1989fa;
  }

  h2 {
    margin: 16px 0 8px;
    font-size: 24px;
    color: #323233;
  }

  p {
    margin: 0;
    font-size: 14px;
    color: #969799;
  }
}

.login-form {
  margin-top: 20px;
}

.checkbox-area {
  margin: 12px 16px;
}

.submit-area {
  margin: 24px 16px;
}

.tips {
  text-align: center;
  margin-top: 32px;

  p {
    font-size: 12px;
    color: #969799;
  }
}

.switch-mode {
  text-align: center;
  margin-top: 16px;

  .divider {
    margin: 0 8px;
    color: #dcdee0;
    cursor: default;
  }
}

.text-link {
  font-size: 14px;
  color: #1989fa;
  cursor: pointer;

  &:active {
    opacity: 0.7;
  }
}

.server-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin: 0 4px 16px;
  border-radius: 8px;
  font-size: 13px;

  &.checking {
    background: #f0f9ff;
    color: #1989fa;
  }

  &.unreachable {
    background: #fff2f0;
    color: #ee0a24;
    border: 1px solid #ffccc7;

    i {
      font-size: 16px;
    }

    span {
      flex: 1;
    }
  }
}

.history-title {
  padding: 20px 16px 12px;
  font-size: 16px;
  font-weight: 500;
  color: #323233;
}

.history-clear-area {
  padding: 12px 16px 24px;
  text-align: center;
}
</style>
