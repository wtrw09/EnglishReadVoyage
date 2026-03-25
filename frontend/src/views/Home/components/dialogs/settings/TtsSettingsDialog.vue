<template>
  <van-dialog
    v-model:show="visible"
    title="朗读设置"
    show-cancel-button
    confirm-button-text="保存"
    cancel-button-text="取消"
    @confirm="onConfirm"
    @closed="onClosed"
  >
    <div class="settings-dialog-content">
      <!-- 服务名称 -->
      <van-field label="服务名称">
        <template #input>
          <select v-model="localServiceName" class="tts-voice-select">
            <option value="kokoro-tts">Kokoro TTS (本地)</option>
            <option value="doubao-tts">豆包 TTS (在线)</option>
            <option value="siliconflow-tts">硅基流动 TTS (在线)</option>
            <option value="edge-tts">Edge-TTS (微软在线)</option>
            <option value="minimax-tts">MiniMax TTS (speech-2.8-hd)</option>
          </select>
        </template>
      </van-field>

      <!-- 语音选择 -->
      <van-field label="语音类型">
        <template #input>
          <select v-model="localVoice" class="tts-voice-select">
            <option value="" disabled>请选择语音类型</option>
            <option v-for="voice in availableVoices" :key="voice.id" :value="voice.id">
              {{ voice.name }}
            </option>
          </select>
        </template>
      </van-field>

      <!-- 朗读速度 -->
      <template v-if="supportsSpeed">
        <van-field label="朗读速度" placeholder="1.0">
          <template #input>
            <input
              :value="localSpeed.toFixed(1)"
              type="number"
              step="0.1"
              :min="speedRange.min"
              :max="speedRange.max"
              class="tts-speed-input"
              @input="onSpeedInput"
            />
            <span class="speed-unit">x</span>
          </template>
        </van-field>
        <div class="field-hint">
          范围: {{ speedRange.min }} - {{ speedRange.max }} (默认 1.0)
        </div>
      </template>

      <!-- 豆包TTS配置 -->
      <template v-if="localServiceName === 'doubao-tts'">
        <van-field
          v-model="localAppId"
          label="APP ID"
          placeholder="豆包APP ID"
        />
        <van-field
          v-model="localAccessKey"
          label="Access Key"
          placeholder="豆包Access Key"
          type="password"
        />
        <van-field
          v-model="localResourceId"
          label="Resource ID"
          placeholder="seed-tts-1.0"
        />
      </template>

      <!-- 硅基流动TTS配置 -->
      <template v-if="localServiceName === 'siliconflow-tts'">
        <van-field
          v-model="localSiliconFlowApiKey"
          label="API Key"
          placeholder="硅基流动API Key"
          type="password"
        />
        <van-field label="模型选择">
          <template #input>
            <select v-model="localSiliconFlowModel" class="tts-voice-select">
              <option value="" disabled>请选择模型</option>
              <option v-for="model in siliconflowModels" :key="model.id" :value="model.id">
                {{ model.name }}
              </option>
            </select>
          </template>
        </van-field>
      </template>

      <!-- MiniMax TTS配置 -->
      <template v-if="localServiceName === 'minimax-tts'">
        <van-field
          v-model="localMinimaxApiKey"
          label="API Key"
          placeholder="留空使用系统默认"
          type="password"
        />
        <van-field
          v-model="localMinimaxModel"
          label="模型"
          placeholder="speech-2.8-hd"
        />
        <div class="field-hint">
          Token Plan Plus用户每日4000字符限额
        </div>
        <van-button
          type="default"
          size="small"
          plain
          class="usage-check-btn"
          :loading="isCheckingUsage"
          :disabled="isCheckingUsage"
          @click="onCheckUsage"
        >
          {{ isCheckingUsage ? '查询中...' : '查询剩余配额' }}
        </van-button>
      </template>

      <!-- Kokoro服务地址 -->
      <van-field
        v-if="localServiceName === 'kokoro-tts'"
        v-model="localApiUrl"
        label="服务地址"
        placeholder="留空使用系统默认"
      >
        <template #label>
          <span>服务地址</span>
          <van-icon name="info-o" class="field-info-icon" @click="onShowUrlHelp" />
        </template>
      </van-field>

      <!-- 测试按钮 -->
      <div class="tts-test-section">
        <van-button
          type="primary"
          size="small"
          icon="play-circle-o"
          :loading="isTesting"
          @click="onTest"
        >
          {{ isTesting ? '测试中...' : '测试朗读' }}
        </van-button>
        <p class="test-text">{{ testText }}</p>
      </div>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { showToast } from 'vant'
import type { TtsServiceName, TtsVoice } from '@/types'

interface Props {
  show: boolean
  serviceName: TtsServiceName
  voice: string
  speed: number
  apiUrl: string
  appId: string
  accessKey: string
  resourceId: string
  siliconFlowApiKey: string
  siliconFlowModel: string
  minimaxApiKey: string
  minimaxModel: string
  availableVoices: TtsVoice[]
  supportsSpeed: boolean
  speedRange: { min: number; max: number }
  siliconflowModels: { id: string; name: string }[]
  isTesting: boolean
  isCheckingUsage: boolean
  testText: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'update:serviceName': [value: TtsServiceName]
  'update:voice': [value: string]
  'update:speed': [value: number]
  'update:apiUrl': [value: string]
  'update:appId': [value: string]
  'update:accessKey': [value: string]
  'update:resourceId': [value: string]
  'update:siliconFlowApiKey': [value: string]
  'update:siliconFlowModel': [value: string]
  'update:minimaxApiKey': [value: string]
  'update:minimaxModel': [value: string]
  'confirm': []
  'test': []
  'checkUsage': []
}>()

// 本地状态（用于双向绑定）
const localServiceName = ref<TtsServiceName>('edge-tts')
const localVoice = ref('')
const localSpeed = ref(1.0)
const localApiUrl = ref('')
const localAppId = ref('')
const localAccessKey = ref('')
const localResourceId = ref('')
const localSiliconFlowApiKey = ref('')
const localSiliconFlowModel = ref('')
const localMinimaxApiKey = ref('')
const localMinimaxModel = ref('')

// 计算属性
const visible = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value)
})

// 同步props到本地状态
watch(() => props.show, (isOpen) => {
  if (isOpen) {
    localServiceName.value = props.serviceName
    localVoice.value = props.voice
    localSpeed.value = props.speed
    localApiUrl.value = props.apiUrl
    localAppId.value = props.appId
    localAccessKey.value = props.accessKey
    localResourceId.value = props.resourceId
    localSiliconFlowApiKey.value = props.siliconFlowApiKey
    localSiliconFlowModel.value = props.siliconFlowModel
    localMinimaxApiKey.value = props.minimaxApiKey
    localMinimaxModel.value = props.minimaxModel
  }
}, { immediate: true })

// 监听本地变化，emit更新
watch(localServiceName, (value) => emit('update:serviceName', value))
watch(localVoice, (value) => emit('update:voice', value))
watch(localSpeed, (value) => emit('update:speed', value))
watch(localApiUrl, (value) => emit('update:apiUrl', value))
watch(localAppId, (value) => emit('update:appId', value))
watch(localAccessKey, (value) => emit('update:accessKey', value))
watch(localResourceId, (value) => emit('update:resourceId', value))
watch(localSiliconFlowApiKey, (value) => emit('update:siliconFlowApiKey', value))
watch(localSiliconFlowModel, (value) => emit('update:siliconFlowModel', value))
watch(localMinimaxApiKey, (value) => emit('update:minimaxApiKey', value))
watch(localMinimaxModel, (value) => emit('update:minimaxModel', value))

// 方法
const onSpeedInput = (event: Event) => {
  const value = parseFloat((event.target as HTMLInputElement).value)
  if (!isNaN(value)) {
    localSpeed.value = Math.round(value * 10) / 10
  }
}

const onShowUrlHelp = () => {
  showToast({
    message: '设置自定义Kokoro TTS服务地址，留空则使用系统默认配置',
    duration: 3000
  })
}

const onTest = () => {
  emit('test')
}

const onCheckUsage = () => {
  emit('checkUsage')
}

const onConfirm = () => {
  emit('confirm')
}

const onClosed = () => {
  // 关闭时停止测试
}
</script>

<style scoped>
.settings-dialog-content {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.settings-dialog-content .van-field {
  margin-bottom: 8px;
}

.settings-dialog-content .van-field:last-of-type {
  margin-bottom: 0;
}

.tts-voice-select {
  width: 100%;
  height: 32px;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
  color: #323233;
  outline: none;
  padding: 0 8px;
}

.tts-voice-select option {
  background: #fff;
  color: #323233;
}

.tts-speed-input {
  width: 80px;
  height: 24px;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  padding: 0 8px;
  font-size: 14px;
  color: #323233;
  outline: none;
}

.speed-unit {
  margin-left: 8px;
  color: #969799;
  font-size: 14px;
}

.field-hint {
  font-size: 12px;
  color: #969799;
  padding: 4px 16px 12px;
  margin-top: 0;
}

.field-info-icon {
  margin-left: 4px;
  color: #1989fa;
  font-size: 14px;
  cursor: pointer;
}

.usage-check-btn {
  margin: 12px 16px;
  width: calc(100% - 32px);
}

.tts-test-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
}

.test-text {
  margin-top: 8px;
  font-size: 12px;
  color: #646566;
  line-height: 1.5;
  font-style: italic;
}
</style>
