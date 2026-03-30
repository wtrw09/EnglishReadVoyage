<template>
  <div class="settings-page">
    <!-- 顶部导航栏 -->
    <van-nav-bar
      title="高级设置"
      left-arrow
      fixed
      placeholder
      z-index="300"
      @click-left="handleBack"
    >
      <template #right>
        <van-button
          type="primary"
          size="small"
          :disabled="!hasUnsavedChanges"
          @click="handleSave"
        >
          <template #icon>
            <i class="fas fa-check"></i>
          </template>
          保存
        </van-button>
      </template>
    </van-nav-bar>

    <!-- 标签页切换 -->
    <van-tabs
      v-model:active="activeTab"
      sticky
      offset-top="46"
      line-width="40px"
      :before-change="beforeTabChange"
    >
      <van-tab
        v-for="(tab, index) in settingTabs"
        :key="tab.key"
        :title="tab.title"
        :name="tab.key"
      >
        <!-- 设置内容区域 -->
        <div class="settings-content">
          <component
            :is="tab.component"
            ref="contentRefs"
            :is-admin="authStore.isAdmin"
            @change="handleContentChange"
          />
        </div>
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, markRaw, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showNotify, showConfirmDialog } from 'vant'
import { useAuthStore } from '@/store/auth'
import { useTtsSettings } from '@/views/Home/composables/useTtsSettings'
import { useDictionarySettings } from '@/views/Home/composables/useDictionarySettings'

// 设置内容组件
import TtsSettingsContent from '@/views/Settings/components/TtsSettingsContent.vue'
import DictionarySettingsContent from '@/views/Settings/components/DictionarySettingsContent.vue'
import PhoneticSettingsContent from '@/views/Settings/components/PhoneticSettingsContent.vue'
import AdminToolsContent from '@/views/Settings/components/AdminToolsContent.vue'

// 设置标签页配置
interface SettingTab {
  key: string
  title: string
  component: any
}

const baseTabs: SettingTab[] = [
  { key: 'dict', title: '词典', component: markRaw(DictionarySettingsContent) },
  { key: 'phonetic', title: '音标', component: markRaw(PhoneticSettingsContent) },
]

// 管理员可见标签
const adminTabs: SettingTab[] = [
  { key: 'tools', title: '工具', component: markRaw(AdminToolsContent) },
  { key: 'tts', title: '朗读', component: markRaw(TtsSettingsContent) },
]

// 根据用户角色决定显示的标签页
const authStore = useAuthStore()
const settingTabs = computed(() => {
  return authStore.isAdmin ? [...adminTabs, ...baseTabs] : baseTabs
})

// 加载设置
const { loadUserSettings } = useTtsSettings()
const { loadDictionaryStatus, loadTranslationSettings } = useDictionarySettings()

const router = useRouter()
// 管理员默认加载工具标签页，普通用户默认加载第一个标签页
const defaultTab = computed(() => authStore.isAdmin ? 'tools' : settingTabs.value[0]?.key || 'dict')
const activeTab = ref('')
const contentRefs = ref<any[]>([])
const showSaveToast = ref(false)
const saveMessage = ref('')
const hasUnsavedChanges = ref(false)

// 当前标签页标题
const currentTabTitle = computed(() => {
  const tab = settingTabs.value.find(t => t.key === activeTab.value)
  return tab?.title || '设置'
})

// 标签页切换前检查
const beforeTabChange = async (_name: string) => {
  if (hasUnsavedChanges.value) {
    // 使用确认对话框让用户选择
    return new Promise<boolean>((resolve) => {
      showConfirmDialog({
        title: '当前设置未保存',
        message: '有未保存的更改，是否保存？',
        confirmButtonText: '保存',
        cancelButtonText: '仍然离开',
        showCancelButton: true,
      }).then(async () => {
        // 用户选择保存
        await handleSave()
        resolve(true)
      }).catch((action: string) => {
        if (action === 'cancel') {
          // 用户选择仍然离开
          hasUnsavedChanges.value = false
          resolve(true)
        } else {
          // 用户选择取消
          resolve(false)
        }
      })
    })
  }
  return true
}

// 处理内容变更
const handleContentChange = () => {
  hasUnsavedChanges.value = true
}

// 返回上一页
const handleBack = () => {
  if (hasUnsavedChanges.value) {
    showNotify({
      type: 'warning',
      message: '有未保存的更改',
      duration: 2000
    })
  }
  router.back()
}

// 保存当前标签页设置
const handleSave = async () => {
  const currentIndex = settingTabs.value.findIndex(t => t.key === activeTab.value)
  if (contentRefs.value[currentIndex]?.save) {
    try {
      await contentRefs.value[currentIndex].save()
      hasUnsavedChanges.value = false
      saveMessage.value = '保存成功'
      showSaveToast.value = true
    } catch (error) {
      // 错误已在子组件中处理
    }
  }
}

// 页面加载时加载用户设置
onMounted(async () => {
  // 设置初始标签页
  activeTab.value = defaultTab.value
  await loadUserSettings()
  await Promise.all([
    loadDictionaryStatus(),
    loadTranslationSettings()
  ])
})
</script>

<style lang="less" scoped>
.settings-page {
  min-height: 100vh;
  background: #f7f8fa;
}

.settings-content {
  padding: 12px;
  padding-bottom: 80px;
  background: #f7f8fa;
  box-sizing: border-box;
}

/* 标签页样式优化 - 去除指示线，使用背景色区分 */
:deep(.van-tabs) {
  .van-tabs__wrap {
    background: #fff;
    border-bottom: 1px solid #eee;
  }

  .van-tab {
    font-size: 14px;
    color: #646566;
    background: transparent;
    transition: all 0.3s;

    &.van-tab--active {
      color: #1989fa;
      font-weight: 600;
      background: #e3f2fd;
      border-radius: 4px;
    }
  }

  .van-tabs__line {
    display: none !important;
  }
}

/* 响应式布局 */
@media (orientation: landscape) {
  :deep(.van-tabs) {
    display: flex;

    .van-tabs__wrap {
      width: 140px;
      height: auto;
      flex-shrink: 0;
      border-right: 1px solid #eee;
      border-bottom: none;
    }

    .van-tabs__nav {
      flex-direction: column;
      padding: 8px 0;
    }

    .van-tab {
      padding: 16px;
      text-align: left;
    }

    .van-tabs__content {
      flex: 1;
    }
  }

  .settings-content {
    min-height: auto;
  }
}
</style>
