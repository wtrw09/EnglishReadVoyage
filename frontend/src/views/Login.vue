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
        <van-icon name="list-switch" class="logo-icon" />
        <h2>英语阅读之旅</h2>
        <p>{{ isActivateMode ? '请输入邀请码激活账户' : '请登录以继续' }}</p>
      </div>

      <!-- 登录表单 -->
      <van-form v-if="!isActivateMode" @submit="onSubmit" class="login-form">
        <van-cell-group inset>
          <van-field
            v-model="form.username"
            name="username"
            label="用户名"
            placeholder="请输入用户名"
            :rules="[{ required: true, message: '请填写用户名' }]"
            left-icon="user-o"
          />
          <van-field
            v-model="form.password"
            type="password"
            name="password"
            label="密码"
            placeholder="请输入密码"
            :rules="[{ required: true, message: '请填写密码' }]"
            left-icon="lock"
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
            登录
          </van-button>
        </div>

        <div class="switch-mode">
          <span class="text-link" @click="switchToActivate">激活账户</span>
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
            left-icon="coupon-o"
          />
          <van-field
            v-model="activateForm.password"
            type="password"
            name="password"
            label="设置密码"
            placeholder="请设置登录密码"
            :rules="[{ required: true, message: '请设置密码' }]"
            left-icon="lock"
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
            left-icon="lock"
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showNotify } from 'vant'
import { useAuthStore } from '@/store/auth'

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

// 切换到登录模式
const switchToLogin = () => {
  isActivateMode.value = false
}

// 验证确认密码
const validateConfirmPassword = (value: string) => {
  return value === activateForm.password
}

// 登录提交
const onSubmit = async () => {
  const result = await authStore.login(form.username, form.password)
  
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
}

.text-link {
  font-size: 14px;
  color: #1989fa;
  cursor: pointer;

  &:active {
    opacity: 0.7;
  }
}
</style>
