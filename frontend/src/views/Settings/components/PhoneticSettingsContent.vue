/**
 * PhoneticSettingsContent.vue - 音标设置内容
 *
 * 功能：音标显示偏好
 * - 选择英式/美式音标
 * - 音标对比示例展示
 */
<template>
  <div class="phonetic-settings-content">
    <van-cell-group inset title="音标设置">
      <van-radio-group v-model="phoneticAccent">
        <van-cell
          title="英式音标 (UK)"
          label="使用英式发音音标，如 /həˈləʊ/"
          clickable
          :class="{ 'active-accent': phoneticAccent === 'uk' }"
          @click="phoneticAccent = 'uk'"
        >
          <template #right-icon>
            <van-radio name="uk" />
          </template>
        </van-cell>
        <van-cell
          title="美式音标 (US)"
          label="使用美式发音音标，如 /həˈloʊ/"
          clickable
          :class="{ 'active-accent': phoneticAccent === 'us' }"
          @click="phoneticAccent = 'us'"
        >
          <template #right-icon>
            <van-radio name="us" />
          </template>
        </van-cell>
      </van-radio-group>
    </van-cell-group>

    <!-- 音标对比示例 -->
    <van-cell-group inset title="音标示例对比" class="phonetic-examples">
      <div class="example-item">
        <div class="example-word">hello</div>
        <div class="example-phonetics">
          <div class="phonetic-item">
            <span class="phonetic-label">UK</span>
            <span class="phonetic-value">/həˈləʊ/</span>
          </div>
          <div class="phonetic-item">
            <span class="phonetic-label">US</span>
            <span class="phonetic-value">/həˈloʊ/</span>
          </div>
        </div>
      </div>
      <div class="example-item">
        <div class="example-word">tomato</div>
        <div class="example-phonetics">
          <div class="phonetic-item">
            <span class="phonetic-label">UK</span>
            <span class="phonetic-value">/təˈmɑːtəʊ/</span>
          </div>
          <div class="phonetic-item">
            <span class="phonetic-label">US</span>
            <span class="phonetic-value">/təˈmeɪtoʊ/</span>
          </div>
        </div>
      </div>
      <div class="example-item">
        <div class="example-word">schedule</div>
        <div class="example-phonetics">
          <div class="phonetic-item">
            <span class="phonetic-label">UK</span>
            <span class="phonetic-value">/ˈʃedjuːl/</span>
          </div>
          <div class="phonetic-item">
            <span class="phonetic-label">US</span>
            <span class="phonetic-value">/ˈskedʒuːl/</span>
          </div>
        </div>
      </div>
    </van-cell-group>

    <!-- 说明 -->
    <div class="settings-tip">
      <i class="fas fa-info-circle" style="flex-shrink: 0;"></i>
      <span>音标设置影响词典查询时显示的音标类型</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { showNotify } from 'vant'
import { api } from '@/store/auth'

// 组件名称，用于在 Settings.vue 中识别组件
defineOptions({
  name: 'PhoneticSettingsContent'
})

const phoneticAccent = ref<'uk' | 'us'>('uk')
const emit = defineEmits(['change'])

// 组件本地的初始化标志，区分加载数据和用户修改
const componentInitialized = ref(false)

// 监听值变化，通知父组件
watch(phoneticAccent, (newVal, oldVal) => {
  // 只有在组件初始化完成后，且值确实发生变化才触发 change
  if (componentInitialized.value && newVal !== oldVal) {
    emit('change')
  }
})

// 页面加载时获取设置
onMounted(async () => {
  await loadCurrentSettings()
  // 数据加载完成后，延迟启用 change 检测
  setTimeout(() => {
    componentInitialized.value = true
  }, 50)
})

// 加载当前设置
const loadCurrentSettings = async () => {
  try {
    const res = await api.get('/settings/phonetic')
    if (res.data?.accent) {
      phoneticAccent.value = res.data.accent
    }
  } catch (error) {
    console.error('加载音标设置失败:', error)
  }
}

// 暴露保存方法
defineExpose({
  save: async () => {
    try {
      await api.put('/settings/phonetic', {
        accent: phoneticAccent.value
      })
      showNotify({ type: 'success', message: '音标设置已保存' })
    } catch (error: any) {
      console.error('保存音标设置失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
      throw error
    }
  }
})
</script>

<style lang="less" scoped>
.phonetic-settings-content {
  padding-bottom: 24px;
}

:deep(.van-cell-group) {
  margin-bottom: 12px;

  .van-cell-group__title {
    font-size: 13px;
    color: #969799;
    padding: 8px 16px;
  }
}

.active-accent {
  background: #f0fff4;

  :deep(.van-cell__title) {
    color: #07c160;
  }
}

.phonetic-examples {
  margin-top: 12px;

  .example-item {
    padding: 12px 16px;

    &:not(:last-child) {
      border-bottom: 1px solid #eee;
    }
  }

  .example-word {
    font-size: 18px;
    font-weight: 600;
    color: #333;
    margin-bottom: 8px;
  }

  .example-phonetics {
    display: flex;
    gap: 24px;
  }

  .phonetic-item {
    display: flex;
    align-items: center;
    gap: 8px;

    .phonetic-label {
      font-size: 12px;
      padding: 2px 8px;
      border-radius: 4px;
      background: #f0f0f0;
      color: #666;
    }

    .phonetic-value {
      font-family: 'Menlo', 'Monaco', monospace;
      font-size: 14px;
      color: #333;
    }
  }
}

.settings-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 12px;
  padding: 12px;
  background: #f0f9ff;
  border-radius: 8px;
  font-size: 13px;
  color: #1989fa;
}
</style>
