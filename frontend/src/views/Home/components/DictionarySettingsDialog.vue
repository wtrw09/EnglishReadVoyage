/**
 * DictionarySettingsDialog.vue - 词典设置对话框
 *
 * 功能：快速词典设置
 * - 选择词典来源（在线API / 本地ECDICT）
 * - 简化版设置面板
 */
<template>
  <!-- 词典设置弹窗 -->
  <van-dialog
    :show="show"
    title="词典设置"
    show-cancel-button
    confirm-button-text="保存"
    cancel-button-text="取消"
    @confirm="handleSave"
    @update:show="(val: boolean) => emit('update:show', val)"
  >
    <div class="settings-dialog-content">
      <van-radio-group v-model="dictionarySource">
        <van-cell-group>
          <van-cell title="FreeDictionaryAPI (在线)" clickable @click="dictionarySource = 'api'">
            <template #right-icon>
              <van-radio name="api" />
            </template>
            <template #label>
              <span class="dict-label">使用在线词典API，需要网络连接</span>
            </template>
          </van-cell>
          <van-cell
            title="本地ECDICT"
            clickable
            @click="dictionarySource = 'local'"
            :class="{ 'disabled-cell': !ecdictAvailable }"
          >
            <template #right-icon>
              <van-radio name="local" :disabled="!ecdictAvailable" />
            </template>
            <template #label>
              <span class="dict-label">
                {{ ecdictAvailable ? '使用本地词典，无需网络' : '本地词典未安装' }}
              </span>
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>

      <!-- 百度翻译API设置 -->
      <div class="baidu-settings" v-if="isAdmin" style="margin-top: 16px;">
        <div class="baidu-settings-header">百度翻译API（用于句子翻译）</div>
        <div v-if="translationApis.length === 0" class="baidu-add-api">
          <van-field v-model="newBaiduAppId" label="APP ID" placeholder="百度翻译APP ID" />
          <van-field v-model="newBaiduAppKey" label="APP Key" placeholder="百度翻译APP Key" type="password" />
          <div class="baidu-add-btn">
            <van-button type="primary" block @click="handleAddApi">添加百度翻译API</van-button>
          </div>
        </div>
        <div v-else class="baidu-api-config">
          <van-cell-group>
            <van-cell title="APP ID">
              <template #value>
                <span class="app-id-display">{{ translationApis[0]?.app_id }}</span>
              </template>
            </van-cell>
            <van-cell title="状态">
              <template #value>
                <van-switch v-model="translationApis[0].is_active" size="small" @change="handleSaveApi" />
              </template>
            </van-cell>
          </van-cell-group>
          <div class="baidu-api-actions">
            <van-button size="small" type="danger" plain @click="handleDeleteApi(translationApis[0].id)">删除</van-button>
          </div>
          <div class="translation-hint">已配置百度翻译API（用于句子翻译）</div>
        </div>
      </div>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { useDictionarySettings } from '../composables/useDictionarySettings'
import { watch } from 'vue'

const props = defineProps<{
  show: boolean
  isAdmin: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved'): void
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
} = useDictionarySettings()

// 监听弹窗打开，加载数据
watch(() => props.show, async (newVal) => {
  if (newVal) {
    // 弹窗打开时加载数据
    await Promise.all([
      loadDictionaryStatus(),
      loadTranslationSettings()
    ])
  }
}, { immediate: true })

const handleSave = async () => {
  await saveDictionarySettings()
  emit('saved')
}

const handleAddApi = () => {
  addBaiduApi()
}

const handleSaveApi = () => {
  saveTranslationApi()
}

const handleDeleteApi = (apiId: number) => {
  deleteTranslationApi(apiId)
}
</script>

<style scoped>
.settings-dialog-content {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.dict-label {
  font-size: 12px;
  color: #969799;
}

.disabled-cell {
  opacity: 0.5;
}

.baidu-settings {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #eee;
}

.baidu-settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #323233;
}

.baidu-add-btn {
  margin-top: 12px;
}

.baidu-api-config {
  background: #f7f8fa;
  padding: 12px;
  border-radius: 8px;
}

.app-id-display {
  font-family: monospace;
}

.baidu-api-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.translation-hint {
  text-align: center;
  font-size: 12px;
  color: #969799;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 4px;
  margin-top: 12px;
}
</style>
