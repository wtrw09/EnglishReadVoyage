<template>
  <!-- 朗读设置弹窗 -->
  <van-dialog
    :show="show"
    title="朗读设置"
    show-cancel-button
    confirm-button-text="保存"
    cancel-button-text="取消"
    @confirm="handleSave"
    @closed="handleClosed"
    @update:show="(val: boolean) => emit('update:show', val)"
  >
    <div class="settings-dialog-content">
      <!-- 服务名称 -->
      <van-field label="服务名称">
        <template #input>
          <select v-model="ttsServiceName" class="tts-voice-select">
            <option value="kokoro-tts">Kokoro TTS (本地)</option>
            <option value="doubao-tts">豆包 TTS (在线)</option>
            <option value="siliconflow-tts">硅基流动 TTS (在线)</option>
            <option value="edge-tts">Edge-TTS (微软在线)</option>
            <option value="minimax-tts">MiniMax TTS (speech-2.8-hd)</option>
            <option value="azure-tts">Azure TTS (Neural)</option>
          </select>
        </template>
      </van-field>

      <!-- 语音选择 -->
      <van-field label="英文音色">
        <template #input>
          <select v-model="ttsVoice" class="tts-voice-select">
            <option value="" disabled>请选择英文音色</option>
            <option v-for="voice in availableVoices" :key="voice.id" :value="voice.id">
              {{ voice.name }}
            </option>
          </select>
        </template>
      </van-field>

      <!-- 中文音色选择 -->
      <van-field label="中文音色">
        <template #input>
          <select v-model="ttsVoiceZh" class="tts-voice-select">
            <option value="" disabled>请选择中文音色</option>
            <option v-for="voice in availableVoicesZh" :key="voice.id" :value="voice.id">
              {{ voice.name }}
            </option>
          </select>
        </template>
      </van-field>

      <!-- 朗读速度 (硅基流动和MiniMax不支持) -->
      <template v-if="ttsServiceName !== 'siliconflow-tts'">
        <van-field label="朗读速度" placeholder="1.0">
          <template #input>
            <input
              :value="ttsSpeed.toFixed(1)"
              type="number"
              step="0.1"
              min="0.25"
              max="4.0"
              class="tts-speed-input"
              @input="handleSpeedInput"
            />
            <span class="speed-unit">x</span>
          </template>
        </van-field>
        <div class="field-hint">
          范围: {{ ttsServiceName === 'kokoro-tts' || ttsServiceName === 'minimax-tts' ? '0.25 - 4.0' : '0.5 - 2.0' }} (默认 1.0)
        </div>
      </template>

      <!-- 豆包TTS配置 -->
      <template v-if="ttsServiceName === 'doubao-tts'">
        <van-field v-model="ttsAppId" label="APP ID" placeholder="豆包APP ID" />
        <van-field v-model="ttsAccessKey" label="Access Key" placeholder="豆包Access Key" type="password" />
        <van-field v-model="ttsResourceId" label="Resource ID" placeholder="seed-tts-1.0" />
      </template>

      <!-- 硅基流动TTS配置 -->
      <template v-if="ttsServiceName === 'siliconflow-tts'">
        <van-field v-model="ttsSiliconFlowApiKey" label="API Key" placeholder="硅基流动API Key" type="password" />
        <van-field label="模型选择">
          <template #input>
            <select v-model="ttsSiliconFlowModel" class="tts-voice-select">
              <option value="" disabled>请选择模型</option>
              <option v-for="model in siliconflowModels" :key="model.id" :value="model.id">
                {{ model.name }}
              </option>
            </select>
          </template>
        </van-field>
      </template>

      <!-- MiniMax TTS配置 -->
      <template v-if="ttsServiceName === 'minimax-tts'">
        <van-field v-model="ttsMinimaxApiKey" label="API Key" placeholder="留空使用系统默认" type="password" />
        <van-field v-model="ttsMinimaxModel" label="模型" placeholder="speech-2.8-hd" />
        <div class="field-hint">Token Plan Plus用户每日4000字符限额</div>
        <van-button
          type="default"
          size="small"
          plain
          class="usage-check-btn"
          :loading="minimaxUsageChecking"
          :disabled="minimaxUsageChecking"
          @click="handleCheckUsage"
        >
          {{ minimaxUsageChecking ? '查询中...' : '查询剩余配额' }}
        </van-button>
      </template>

      <!-- Azure TTS配置 -->
      <template v-if="ttsServiceName === 'azure-tts'">
        <van-field v-model="ttsAzureSubscriptionKey" label="Subscription Key" placeholder="Azure API密钥" type="password" />
        <van-field v-model="ttsAzureRegion" label="区域" placeholder="例如: eastasia" />
        <div class="field-hint">QPS限制: 100次/秒</div>
        <van-button
          type="default"
          size="small"
          plain
          class="usage-check-btn"
          :loading="azureUsageChecking"
          :disabled="azureUsageChecking"
          @click="handleCheckAzureUsage"
        >
          {{ azureUsageChecking ? '查询中...' : '查询使用量' }}
        </van-button>
        <!-- Azure 音色列表加载提示 -->
        <div v-if="azureVoicesLoading || azureVoicesZhLoading" class="field-hint loading-hint">
          🔄 正在获取音色列表（首次加载较慢，请耐心等待）...
        </div>
      </template>

      <!-- 服务地址 (仅在使用Kokoro时显示) -->
      <van-field
        v-if="ttsServiceName === 'kokoro-tts'"
        v-model="ttsApiUrl"
        label="服务地址"
        placeholder="留空使用系统默认"
        :rules="[{ validator: validateUrl, message: '地址必须以 http:// 或 https:// 开头' }]"
      >
        <template #label>
          <i class="fas fa-info-circle field-info-icon" @click="showUrlHelp" style="color: #1989fa; margin-left: 4px; cursor: pointer;"></i>
        </template>
      </van-field>
      <div v-if="ttsServiceName === 'kokoro-tts'" class="field-hint">
        当前默认: {{ defaultTtsConfig.api_url }}
      </div>

      <!-- 测试按钮 -->
      <div class="tts-test-section">
        <van-button
          type="primary"
          size="small"
          :loading="ttsTesting"
          @click="handleTest"
        >
          <i class="fas fa-play" style="margin-right: 4px;"></i>
          测试朗读
        </van-button>
        <p class="test-text">{{ ttsTestText }}</p>
      </div>

      <!-- 中文测试按钮 -->
      <div v-if="availableVoicesZh.length > 0" class="tts-test-section">
        <van-button
          type="primary"
          size="small"
          :loading="ttsTestingZh"
          @click="handleTestZh"
        >
          <i class="fas fa-play" style="margin-right: 4px;"></i>
          测试中文
        </van-button>
        <p class="test-text">{{ ttsTestTextZh }}</p>
      </div>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { useTtsSettings } from '../composables/useTtsSettings'

defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'saved'): void
}>()

const {
  ttsServiceName,
  ttsVoice,
  ttsSpeed,
  ttsApiUrl,
  ttsVoiceZh,
  ttsAppId,
  ttsAccessKey,
  ttsResourceId,
  ttsSiliconFlowApiKey,
  ttsSiliconFlowModel,
  ttsMinimaxApiKey,
  ttsMinimaxModel,
  ttsAzureSubscriptionKey,
  ttsAzureRegion,
  ttsAzureVoice,
  ttsAzureVoiceZh,
  ttsAzureSpeed,
  defaultTtsConfig,
  siliconflowModels,
  availableVoices,
  availableVoicesZh,
  minimaxUsageChecking,
  azureUsageChecking,
  azureVoicesLoading,  // Azure音色列表加载状态
  azureVoicesZhLoading,  // Azure中文音色列表加载状态
  ttsTesting,
  ttsTestingZh,
  ttsTestText,
  ttsTestTextZh,
  handleCheckMinimaxUsage,
  handleCheckAzureUsage,
  testTts,
  testTtsZh,
  validateTtsUrl,
  showTtsUrlHelp,
  saveTtsSettings,
} = useTtsSettings()

const handleSave = async () => {
  await saveTtsSettings()
  emit('saved')
}

const handleClosed = () => {
  // 对话框关闭时不自动播放测试
}

const handleSpeedInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  ttsSpeed.value = Math.round(parseFloat(target.value) * 10) / 10
}

const handleCheckUsage = () => {
  handleCheckMinimaxUsage()
}

const handleTest = () => {
  testTts()
}

const handleTestZh = () => {
  testTtsZh()
}

const validateUrl = (value: string) => {
  return validateTtsUrl(value)
}

const showUrlHelp = () => {
  showTtsUrlHelp()
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

.field-info-icon {
  margin-left: 4px;
  color: #1989fa;
  font-size: 14px;
  cursor: pointer;
}

.field-hint {
  font-size: 12px;
  color: #969799;
  padding: 4px 16px 12px;
  margin-top: 0;
}

.usage-check-btn {
  margin: 12px 16px;
  width: calc(100% - 32px);
}

.loading-hint {
  color: #1989fa;
  animation: pulse 1.5s infinite;
  padding: 8px 16px !important;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
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
