<template>
  <van-dialog
    v-model:show="visible"
    title="词典设置"
    show-cancel-button
    confirm-button-text="保存"
    cancel-button-text="取消"
    @confirm="onConfirm"
  >
    <div class="settings-dialog-content">
      <van-radio-group v-model="localSource">
        <van-cell-group>
          <van-cell title="FreeDictionaryAPI (在线)" clickable @click="localSource = 'api'">
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
            @click="localSource = 'local'"
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

      <!-- 百度翻译API设置（仅管理员可见） -->
      <div v-if="isAdmin" class="baidu-settings">
        <div class="baidu-settings-header">百度翻译API（用于句子翻译）</div>
        <div v-if="translationApis.length === 0" class="baidu-add-api">
          <van-field v-model="newAppId" label="APP ID" placeholder="百度翻译APP ID" />
          <van-field v-model="newAppKey" label="APP Key" placeholder="百度翻译APP Key" type="password" />
          <div class="baidu-add-btn">
            <van-button type="primary" block @click="onAddApi">添加百度翻译API</van-button>
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
                <van-switch v-model="translationApis[0].is_active" size="small" @change="onSaveApi" />
              </template>
            </van-cell>
          </van-cell-group>
          <div class="baidu-api-actions">
            <van-button size="small" type="danger" plain @click="onDeleteApi(translationApis[0].id)">删除</van-button>
          </div>
        </div>
      </div>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  show: boolean
  source: 'api' | 'local'
  ecdictAvailable: boolean
  isAdmin: boolean
  translationApis: { id: number; app_id: string; is_active: boolean }[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'update:source': [value: 'api' | 'local']
  'save': []
  'add-api': [appId: string, appKey: string]
  'delete-api': [apiId: number]
}>()

const visible = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value)
})

const localSource = computed({
  get: () => props.source,
  set: (value) => emit('update:source', value)
})

const newAppId = ref('')
const newAppKey = ref('')

const onAddApi = () => {
  if (newAppId.value.trim() && newAppKey.value.trim()) {
    emit('add-api', newAppId.value.trim(), newAppKey.value.trim())
    newAppId.value = ''
    newAppKey.value = ''
  }
}

const onSaveApi = () => {
  // 保存API状态
}

const onDeleteApi = (apiId: number) => {
  emit('delete-api', apiId)
}

const onConfirm = () => {
  emit('save')
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
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  color: #323233;
}

.baidu-add-btn {
  margin-top: 12px;
}

.baidu-api-actions {
  margin-top: 12px;
  text-align: right;
}

.app-id-display {
  font-size: 12px;
  color: #969799;
}
</style>
