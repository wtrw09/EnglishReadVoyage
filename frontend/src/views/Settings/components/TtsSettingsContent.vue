<template>
  <div class="tts-settings-content">
    <!-- 服务名称 -->
    <van-cell-group inset title="服务选择">
      <van-cell title="TTS 服务">
        <template #value>
          <select v-model="ttsServiceName" class="tts-select">
            <option value="kokoro-tts">Kokoro TTS (本地)</option>
            <option value="doubao-tts">豆包 TTS (在线)</option>
            <option value="siliconflow-tts">硅基流动 TTS (在线)</option>
            <option value="edge-tts">Edge-TTS (微软在线)</option>
            <option value="minimax-tts">MiniMax TTS</option>
            <option value="azure-tts">Azure TTS (Neural)</option>
          </select>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 语音选择 -->
    <van-cell-group inset title="音色设置">
      <!-- 英文音色选择 -->
      <van-cell title="英文音色">
        <template #value>
          <select v-model="ttsVoice" class="tts-select">
            <option value="" disabled>请选择英文音色</option>
            <option v-for="voice in availableVoices" :key="voice.id" :value="voice.id">
              {{ voice.name }}
            </option>
          </select>
        </template>
      </van-cell>

      <!-- 中文音色选择 -->
      <van-cell title="中文音色">
        <template #value>
          <select v-model="ttsVoiceZh" class="tts-select">
            <option value="" disabled>请选择中文音色</option>
            <option v-for="voice in availableVoicesZh" :key="voice.id" :value="voice.id">
              {{ voice.name }}
            </option>
          </select>
        </template>
      </van-cell>

      <!-- 朗读速度 -->
      <van-cell
        v-if="ttsServiceName !== 'siliconflow-tts'"
        title="朗读速度"
      >
        <template #value>
          <div class="speed-control">
            <input
              :value="ttsSpeed.toFixed(1)"
              type="number"
              step="0.1"
              min="0.25"
              max="4.0"
              class="speed-input"
              @input="handleSpeedInput"
            />
            <span class="speed-unit">x</span>
          </div>
        </template>
      </van-cell>
      <div v-if="ttsServiceName !== 'siliconflow-tts'" class="field-hint">
        范围: {{ ttsServiceName === 'kokoro-tts' || ttsServiceName === 'minimax-tts' ? '0.25 - 4.0' : '0.5 - 2.0' }} (默认 1.0)
      </div>
    </van-cell-group>

    <!-- 服务配置 -->
    <van-cell-group
      v-if="showServiceConfig"
      inset
      :title="serviceConfigTitle"
    >
      <!-- 豆包TTS配置 -->
      <template v-if="ttsServiceName === 'doubao-tts'">
        <van-cell title="APP ID">
          <template #value>
            <van-field
              v-model="ttsAppId"
              placeholder="豆包APP ID"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="Access Key">
          <template #value>
            <van-field
              v-model="ttsAccessKey"
              placeholder="豆包Access Key"
              type="password"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="Resource ID">
          <template #value>
            <van-field
              v-model="ttsResourceId"
              placeholder="seed-tts-1.0"
              input-align="right"
            />
          </template>
        </van-cell>
      </template>

      <!-- 硅基流动TTS配置 -->
      <template v-if="ttsServiceName === 'siliconflow-tts'">
        <van-cell title="API Key">
          <template #value>
            <van-field
              v-model="ttsSiliconFlowApiKey"
              placeholder="硅基流动API Key"
              type="password"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="模型选择">
          <template #value>
            <select v-model="ttsSiliconFlowModel" class="tts-select">
              <option value="" disabled>请选择模型</option>
              <option v-for="model in siliconflowModels" :key="model.id" :value="model.id">
                {{ model.name }}
              </option>
            </select>
          </template>
        </van-cell>
      </template>

      <!-- MiniMax TTS配置 -->
      <template v-if="ttsServiceName === 'minimax-tts'">
        <van-cell title="API Key">
          <template #value>
            <van-field
              v-model="ttsMinimaxApiKey"
              placeholder="留空使用系统默认"
              type="password"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="模型">
          <template #value>
            <van-field
              v-model="ttsMinimaxModel"
              placeholder="speech-2.8-hd"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="剩余配额">
          <template #value>
            <van-button
              type="primary"
              size="small"
              plain
              :loading="minimaxUsageChecking"
              @click="handleCheckUsage"
            >
              {{ minimaxUsageChecking ? '查询中...' : '查询' }}
            </van-button>
          </template>
        </van-cell>
        <div class="field-hint">
          Token Plan Plus用户每日4000字符限额
        </div>
      </template>

      <!-- Kokoro TTS配置 -->
      <template v-if="ttsServiceName === 'kokoro-tts'">
        <van-cell title="服务地址">
          <template #label>
            <i class="fas fa-info-circle" @click="showUrlHelp" style="color: #1989fa; margin-left: 4px; cursor: pointer;"></i>
          </template>
          <template #value>
            <van-field
              v-model="ttsApiUrl"
              placeholder="留空使用系统默认"
              input-align="right"
            />
          </template>
        </van-cell>
        <div class="field-hint">
          当前默认: {{ defaultTtsConfig.api_url }}
        </div>
      </template>

      <!-- Azure TTS配置 -->
      <template v-if="ttsServiceName === 'azure-tts'">
        <van-cell title="Subscription Key">
          <template #value>
            <van-field
              v-model="ttsAzureSubscriptionKey"
              placeholder="Azure API密钥"
              type="password"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="区域">
          <template #value>
            <van-field
              v-model="ttsAzureRegion"
              placeholder="例如: eastasia"
              input-align="right"
            />
          </template>
        </van-cell>
        <van-cell title="用量查询">
          <template #value>
            <van-button
              type="primary"
              size="small"
              plain
              :loading="azureUsageChecking"
              @click="handleCheckAzureUsage"
            >
              {{ azureUsageChecking ? '查询中...' : '查询' }}
            </van-button>
          </template>
        </van-cell>
        <div class="field-hint">
          QPS限制: 100次/秒
        </div>
      </template>
    </van-cell-group>

    <!-- 测试区域 -->
    <van-cell-group inset title="测试">
      <van-cell>
        <template #title>
          <van-button
            type="primary"
            size="small"
            :loading="ttsTesting"
            @click="handleTest"
          >
            <i class="fas fa-play" style="margin-right: 4px;"></i>
            测试朗读
          </van-button>
        </template>
      </van-cell>
      <p class="test-text">{{ ttsTestText }}</p>

      <van-cell v-if="availableVoicesZh.length > 0">
        <template #title>
          <van-button
            type="primary"
            size="small"
            :loading="ttsTestingZh"
            @click="handleTestZh"
          >
            <i class="fas fa-play" style="margin-right: 4px;"></i>
            测试中文
          </van-button>
        </template>
      </van-cell>
      <p v-if="availableVoicesZh.length > 0" class="test-text">{{ ttsTestTextZh }}</p>
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onUnmounted } from 'vue'
import { useTtsSettings } from '../../Home/composables/useTtsSettings'

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
  defaultTtsConfig,
  siliconflowModels,
  availableVoices,
  availableVoicesZh,
  minimaxUsageChecking,
  azureUsageChecking,
  handleCheckAzureUsage,
  ttsTesting,
  ttsTestingZh,
  ttsTestText,
  ttsTestTextZh,
  ttsSettingsLoaded,
  handleCheckMinimaxUsage,
  testTts,
  testTtsZh,
  validateTtsUrl,
  showTtsUrlHelp,
  saveTtsSettings,
} = useTtsSettings()

const emit = defineEmits(['change'])

// 监听 TTS 设置变化，通知父组件（只在用户实际修改时）
// 使用初始化状态标志，避免加载时误触发
let isInitializing = true
let initializationTimeout: ReturnType<typeof setTimeout> | null = null

// 组件挂载时，延迟启用 change 检测，等待数据加载完成
onMounted(() => {
  initializationTimeout = setTimeout(() => {
    isInitializing = false
  }, 500)
})

// 组件卸载时清理
onUnmounted(() => {
  if (initializationTimeout) {
    clearTimeout(initializationTimeout)
  }
})

watch([ttsServiceName, ttsVoice, ttsSpeed, ttsApiUrl, ttsVoiceZh, ttsAppId, ttsAccessKey, ttsResourceId, ttsSiliconFlowApiKey, ttsSiliconFlowModel, ttsMinimaxApiKey, ttsMinimaxModel], () => {
  // 只有在初始化完成后才触发 change
  if (!isInitializing && ttsSettingsLoaded.value) {
    emit('change')
  }
}, { deep: true })

// 是否显示服务配置区域
const showServiceConfig = computed(() => {
  return ['doubao-tts', 'siliconflow-tts', 'minimax-tts', 'kokoro-tts', 'azure-tts'].includes(ttsServiceName.value)
})

// 服务配置标题
const serviceConfigTitle = computed(() => {
  const titles: Record<string, string> = {
    'doubao-tts': '豆包配置',
    'siliconflow-tts': '硅基流动配置',
    'minimax-tts': 'MiniMax配置',
    'kokoro-tts': 'Kokoro配置',
    'azure-tts': 'Azure TTS配置'
  }
  return titles[ttsServiceName.value] || '服务配置'
})

// 速度输入处理
const handleSpeedInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  ttsSpeed.value = Math.round(parseFloat(target.value) * 10) / 10
}

// 检查使用量
const handleCheckUsage = () => {
  handleCheckMinimaxUsage()
}

// 测试朗读
const handleTest = () => {
  testTts()
}

// 测试中文
const handleTestZh = () => {
  testTtsZh()
}

// 显示URL帮助
const showUrlHelp = () => {
  showTtsUrlHelp()
}

// 暴露保存方法供父组件调用
defineExpose({
  save: async () => {
    if (ttsApiUrl.value && !validateTtsUrl(ttsApiUrl.value)) {
      throw new Error('服务地址必须以 http:// 或 https:// 开头')
    }
    await saveTtsSettings()
  }
})
</script>

<style lang="less" scoped>
.tts-settings-content {
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

.tts-select {
  width: 100%;
  max-width: 200px;
  height: 32px;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
  color: #323233;
  outline: none;
  padding: 0 8px;
}

.speed-control {
  display: flex;
  align-items: center;
  gap: 4px;
}

.speed-input {
  width: 60px;
  height: 28px;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  padding: 0 8px;
  font-size: 14px;
  text-align: right;
  outline: none;
}

.speed-unit {
  color: #969799;
  font-size: 14px;
}

.field-hint {
  font-size: 12px;
  color: #969799;
  padding: 8px 16px;
  background: #f7f8fa;
}

.info-icon {
  color: #1989fa;
  margin-right: 4px;
  cursor: pointer;
}

.test-text {
  margin: 0;
  padding: 8px 16px;
  font-size: 12px;
  color: #646566;
  line-height: 1.5;
  font-style: italic;
  background: #f7f8fa;
}
</style>
