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
import { useDictionarySettings } from '../../Home/composables/useDictionarySettings'

defineProps<{
  isAdmin?: boolean
}>()

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
  dictionarySettingsLoaded,
} = useDictionarySettings()

const emit = defineEmits(['change'])

// 监听值变化，通知父组件（只在加载完成后）
watch(dictionarySource, () => {
  if (dictionarySettingsLoaded.value) {
    emit('change')
  }
})

const addingApi = ref(false)

// 页面加载时获取数据
onMounted(async () => {
  await Promise.all([
    loadDictionaryStatus(),
    loadTranslationSettings()
  ])
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
