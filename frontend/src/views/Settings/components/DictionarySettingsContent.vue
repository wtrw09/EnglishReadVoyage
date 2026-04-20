/**
 * DictionarySettingsContent.vue - 词典设置内容
 *
 * 功能：词典来源和翻译设置
 * - 选择查词来源（在线API / 本地ECDICT）
 * - 配置百度翻译 API
 * - 测试翻译功能
 */
<template>
  <div class="dictionary-settings-content">
    <!-- 词典来源 -->
    <van-cell-group inset title="词典来源">
      <van-radio-group v-model="dictionarySource">
        <van-cell
          title="FreeDictionaryAPI"
          label="使用在线词典API，需要网络连接"
          clickable
          @click="dictionarySource = 'api'"
        >
          <template #right-icon>
            <van-radio name="api" />
          </template>
        </van-cell>
        <van-cell
          title="韦氏词典"
          :label="merriamWebsterConfigured ? 'Merriam-Webster，含同义词/反义词' : '需管理员配置API Key方可使用'"
          clickable
          @click="handleMerriamWebsterClick"
        >
          <template #right-icon>
            <van-radio name="merriam-webster" />
          </template>
        </van-cell>
        <van-cell
          title="本地ECDICT"
          :label="ecdictAvailable ? '使用本地词典，无需网络' : '本地词典未安装'"
          :clickable="ecdictAvailable"
          :class="{ 'disabled-cell': !ecdictAvailable }"
          @click="ecdictAvailable && (dictionarySource = 'local')"
        >
          <template #right-icon>
            <van-radio name="local" :disabled="!ecdictAvailable" />
          </template>
        </van-cell>
      </van-radio-group>
    </van-cell-group>

    <!-- 百度翻译API设置（仅管理员可见） -->
    <van-cell-group
      v-if="isAdmin"
      inset
      title="翻译API设置"
      class="baidu-settings-group"
    >
      <template v-if="translationApis.length === 0">
        <van-cell title="APP ID">
          <template #value>
            <van-field
              v-model="newBaiduAppId"
              placeholder="百度翻译APP ID"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="APP Key">
          <template #value>
            <van-field
              v-model="newBaiduAppKey"
              placeholder="百度翻译APP Key"
              type="password"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell>
          <van-button
            type="primary"
            block
            :loading="addingApi"
            @click="handleAddApi"
          >
            添加百度翻译API
          </van-button>
        </van-cell>
      </template>

      <template v-else>
        <van-cell title="APP ID">
          <template #value>
            <span class="app-id-display">{{ translationApis[0]?.app_id }}</span>
          </template>
        </van-cell>
        <van-cell title="API状态">
          <template #value>
            <van-switch
              v-model="translationApis[0].is_active"
              size="small"
              @change="handleSaveApi"
            />
          </template>
        </van-cell>
        <van-cell>
          <template #value>
            <van-button
              size="small"
              type="danger"
              plain
              @click="handleDeleteApi(translationApis[0].id)"
            >
              删除
            </van-button>
          </template>
        </van-cell>
        <div class="translation-hint">
          已配置百度翻译API（用于句子翻译）
        </div>
      </template>
    </van-cell-group>

    <!-- 韦氏词典API设置（仅管理员可见） -->
    <van-cell-group
      v-if="isAdmin"
      inset
      title="韦氏词典API设置"
      class="merriam-settings-group"
    >
      <template v-if="!merriamWebsterConfigured">
        <van-cell title="Learner's Dictionary Key">
          <template #value>
            <van-field
              v-model="newMerriamLearnersKey"
              placeholder="韦氏词典API Key"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="Thesaurus Key">
          <template #value>
            <van-field
              v-model="newMerriamThesaurusKey"
              placeholder="同义词词典API Key（可选）"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell>
          <van-button
            type="primary"
            block
            :loading="savingMerriamSettings"
            @click="handleSaveMerriamWebster"
          >
            保存韦氏词典配置
          </van-button>
        </van-cell>
      </template>

      <template v-else>
        <van-cell title="Learner's Dictionary">
          <template #value>
            <van-icon name="success" color="#07c160" />
            <span style="margin-left: 4px; color: #07c160;">已配置</span>
          </template>
        </van-cell>
        <van-cell title="Thesaurus">
          <template #value>
            <span v-if="merriamWebsterHasThesaurus">
              <van-icon name="success" color="#07c160" />
              <span style="margin-left: 4px; color: #07c160;">已配置</span>
            </span>
            <span v-else style="color: #969799;">未配置</span>
          </template>
        </van-cell>
        <van-cell>
          <template #value>
            <van-button
              size="small"
              type="danger"
              plain
              @click="handleDeleteMerriamWebster"
            >
              删除配置
            </van-button>
          </template>
        </van-cell>
      </template>
    </van-cell-group>

    <!-- 说明 -->
    <div class="settings-tip">
      <i class="fas fa-info-circle" style="flex-shrink: 0;"></i>
      <span>词典用于查询单词释义和发音</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { showNotify, showToast } from 'vant'
import { api } from '@/store/auth'
import { useDictionarySettings } from '../../Home/composables/useDictionarySettings'

defineProps<{
  isAdmin?: boolean
}>()

// 组件名称，用于在 Settings.vue 中识别组件
defineOptions({
  name: 'DictionarySettingsContent'
})

const {
  dictionarySource,
  ecdictAvailable,
  translationApis,
  newBaiduAppId,
  newBaiduAppKey,
  loadDictionaryStatus,
  loadTranslationSettings,
  saveDictionarySettings,
  addBaiduApi,
  saveTranslationApi,
  deleteTranslationApi,
} = useDictionarySettings()

// 韦氏词典配置状态
const merriamWebsterConfigured = ref(false)
const merriamWebsterHasThesaurus = ref(false)
const newMerriamLearnersKey = ref('')
const newMerriamThesaurusKey = ref('')
const savingMerriamSettings = ref(false)

// 加载韦氏词典配置
const loadMerriamWebsterSettings = async () => {
  try {
    const res = await api.get('/merriam-webster/settings')
    merriamWebsterConfigured.value = res.data.configured
    merriamWebsterHasThesaurus.value = res.data.has_thesaurus_key
  } catch (error: any) {
    // 404 表示后端不支持或未部署韦氏词典功能，但仍让用户可选
    if (error.response?.status === 404) {
      merriamWebsterConfigured.value = false
      merriamWebsterHasThesaurus.value = false
      console.warn('韦氏词典API暂未部署，用户仍可选择该选项但需管理员配置')
    } else {
      console.error('加载韦氏词典配置失败:', error)
    }
  }
}

// 点击韦氏词典选项
const handleMerriamWebsterClick = () => {
  dictionarySource.value = 'merriam-webster'
}

// 保存韦氏词典配置
const handleSaveMerriamWebster = async () => {
  if (!newMerriamLearnersKey.value) {
    showNotify({ type: 'warning', message: '请填写韦氏词典Learner\'s Dictionary API Key' })
    return
  }
  savingMerriamSettings.value = true
  try {
    await api.put('/merriam-webster/settings', {
      learners_key: newMerriamLearnersKey.value,
      thesaurus_key: newMerriamThesaurusKey.value || null
    })
    showNotify({ type: 'success', message: '韦氏词典配置已保存' })
    merriamWebsterConfigured.value = true
    merriamWebsterHasThesaurus.value = !!newMerriamThesaurusKey.value
    newMerriamLearnersKey.value = ''
    newMerriamThesaurusKey.value = ''
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
  } finally {
    savingMerriamSettings.value = false
  }
}

// 删除韦氏词典配置
const handleDeleteMerriamWebster = async () => {
  try {
    await api.delete('/merriam-webster/settings')
    showNotify({ type: 'success', message: '韦氏词典配置已删除' })
    merriamWebsterConfigured.value = false
    merriamWebsterHasThesaurus.value = false
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
  }
}

const emit = defineEmits(['change'])

// 组件本地的初始化标志，区分加载数据和用户修改
const componentInitialized = ref(false)

// 监听值变化，区分加载时的变化和用户操作
watch(dictionarySource, (newVal, oldVal) => {
  // 只有在组件初始化完成后，且值确实发生变化才触发 change
  if (componentInitialized.value && newVal !== oldVal) {
    emit('change')
  }
})

const addingApi = ref(false)

// 页面加载时获取数据
onMounted(async () => {
  await Promise.all([
    loadDictionaryStatus(),
    loadTranslationSettings(),
    loadMerriamWebsterSettings()
  ])
  // 数据加载完成后，延迟启用 change 检测
  // 确保 watch 在组件初始化标志设置前不会触发
  setTimeout(() => {
    componentInitialized.value = true
  }, 100)
})

// 添加API
const handleAddApi = async () => {
  if (!newBaiduAppId.value || !newBaiduAppKey.value) {
    showNotify({ type: 'warning', message: '请填写完整的APP ID和APP Key' })
    return
  }
  addingApi.value = true
  try {
    await addBaiduApi()
    showToast({ message: '添加成功' })
  } finally {
    addingApi.value = false
  }
}

// 保存API
const handleSaveApi = () => {
  saveTranslationApi()
}

// 删除API
const handleDeleteApi = (apiId: number) => {
  deleteTranslationApi(apiId)
}

// 暴露保存方法
defineExpose({
  save: async () => {
    console.log('DictionarySettingsContent.save 被调用')
    await saveDictionarySettings()
  }
})
</script>

<style lang="less" scoped>
.dictionary-settings-content {
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

.disabled-cell {
  opacity: 0.5;
}

.baidu-settings-group {
  margin-top: 12px;
}

.merriam-settings-group {
  margin-top: 12px;
}

.app-id-display {
  font-family: monospace;
  color: #646566;
}

.translation-hint {
  text-align: center;
  font-size: 12px;
  color: #969799;
  padding: 12px;
  background: #f7f8fa;
  margin: 0;
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
