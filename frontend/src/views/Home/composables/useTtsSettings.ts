import { ref, computed, watch } from 'vue'
import { showNotify, showConfirmDialog } from 'vant'
import { api } from '@/store/auth'
import type { TtsServiceName, TtsVoice, TtsConfig } from '@/types'

// 豆包TTS音色列表
const doubaoVoices: TtsVoice[] = [
  { id: 'en_male_corey_emo_v2_mars_bigtts', name: '英式英语 - Corey' },
  { id: 'en_female_nadia_tips_emo_v2_mars_bigtts', name: '英式英语 - Nadia' },
  { id: 'zh_female_shuangkuaisisi_emo_v2_mars_bigtts', name: '中文/英式 - 爽快思思(多情感)' },
  { id: 'en_female_candice_emo_v2_mars_bigtts', name: '美式英语 - Candice' },
  { id: 'en_female_skye_emo_v2_mars_bigtts', name: '美式英语 - Serena' },
  { id: 'en_male_glen_emo_v2_mars_bigtts', name: '美式英语 - Glen' },
  { id: 'en_male_sylus_emo_v2_mars_bigtts', name: '美式英语 - Sylus' },
  { id: 'zh_female_yingyujiaoyu_mars_bigtts', name: '中文/英式 - Tina老师' },
  { id: 'en_female_emily_mars_bigtts', name: '英式英语 - Emily' },
  { id: 'zh_male_xudong_conversation_wvae_bigtts', name: '英式英语 - Daniel' },
  { id: 'en_female_anna_mars_bigtts', name: '英式英语 - Anna' },
  { id: 'zh_female_shuangkuaisisi_moon_bigtts', name: '中文/美式 - 爽快思思/Skye' },
]

// 硅基流动固定模型和语音列表
const siliconflowModels = [
  { id: 'fnlp/MOSS-TTSD-v0.5', name: 'MOSS TTSD v0.5' },
  { id: 'FunAudioLLM/CosyVoice2-0.5B', name: 'CosyVoice2 0.5B' },
  { id: 'IndexTeam/IndexTTS-2', name: 'IndexTTS 2' }
]

const siliconflowVoices: TtsVoice[] = [
  { id: 'anna', name: 'Anna' },
  { id: 'alex', name: 'Alex' },
  { id: 'bella', name: 'Bella' },
  { id: 'benjamin', name: 'Benjamin' },
  { id: 'charles', name: 'Charles' },
  { id: 'claire', name: 'Claire' },
  { id: 'david', name: 'David' },
  { id: 'diana', name: 'Diana' }
]

export function useTtsSettings() {
  // 状态
  const showTtsSettingsDialog = ref(false)
  const ttsServiceName = ref<TtsServiceName>('edge-tts')
  const ttsVoice = ref('')
  const ttsSpeed = ref(1.0)
  const ttsApiUrl = ref('')

  // 豆包TTS配置
  const ttsAppId = ref('')
  const ttsAccessKey = ref('')
  const ttsResourceId = ref('')

  // 硅基流动TTS配置
  const ttsSiliconFlowApiKey = ref('')
  const ttsSiliconFlowModel = ref('')

  // Edge-TTS配置
  const ttsEdgeTtsVoice = ref('')

  // MiniMax TTS配置
  const ttsMinimaxApiKey = ref('')
  const ttsMinimaxModel = ref('')
  const ttsMinimaxVoice = ref('')
  const ttsMinimaxSpeed = ref(1.0)

  // 默认配置
  const defaultTtsConfig = ref<TtsConfig>({
    service_name: 'edge-tts',
    voice: 'en-US-AriaNeural',
    speed: 1.0,
    api_url: 'http://localhost:8880/v1/audio/speech',
    app_id: '',
    access_key: '',
    resource_id: '',
    siliconflow_api_key: '',
    siliconflow_model: 'fnlp/MOSS-TTSD-v0.5',
    siliconflow_voice: 'anna',
    edge_tts_voice: 'en-US-AriaNeural',
    edge_tts_speed: 1.0,
    minimax_api_key: '',
    minimax_model: 'speech-2.8-hd',
    minimax_voice: 'male-qn-qingse',
    minimax_speed: 1.0
  })

  // 语音列表
  const ttsVoices = ref<TtsVoice[]>([])
  const edgeTtsVoices = ref<TtsVoice[]>([])
  const minimaxVoices = ref<TtsVoice[]>([])

  // 测试状态
  const ttsTesting = ref(false)
  const minimaxUsageChecking = ref(false)
  const ttsTestText = "She meticulously practiced the intricate piano sonata, her fingers dancing across the ivory keys with a grace that belied the immense concentration required."
  let currentTestAudio: HTMLAudioElement | null = null

  // 计算属性：当前可用的语音列表
  const availableVoices = computed((): TtsVoice[] => {
    switch (ttsServiceName.value) {
      case 'doubao-tts':
        return doubaoVoices
      case 'siliconflow-tts':
        return siliconflowVoices
      case 'edge-tts':
        return edgeTtsVoices.value
      case 'minimax-tts':
        return minimaxVoices.value
      default:
        return ttsVoices.value
    }
  })

  // 计算属性：是否支持语速调节
  const supportsSpeed = computed(() => {
    return ttsServiceName.value !== 'siliconflow-tts'
  })

  // 计算属性：语速范围
  const speedRange = computed(() => {
    if (ttsServiceName.value === 'kokoro-tts' || ttsServiceName.value === 'minimax-tts') {
      return { min: 0.25, max: 4.0 }
    }
    return { min: 0.5, max: 2.0 }
  })

  // 加载用户设置
  const loadUserSettings = async () => {
    try {
      const res = await api.get('/settings/')
      const settings = res.data

      // 获取服务名称
      const serviceName = settings.tts?.service_name || 'edge-tts'
      ttsServiceName.value = serviceName

      // 保存默认配置
      defaultTtsConfig.value = {
        service_name: serviceName,
        voice: settings.tts?.voice || 'en-US-AriaNeural',
        speed: settings.tts?.speed ?? 1.0,
        api_url: settings.tts?.kokoro_api_url || '',
        app_id: settings.tts?.doubao_app_id || '',
        access_key: settings.tts?.doubao_access_key || '',
        resource_id: settings.tts?.doubao_resource_id || '',
        siliconflow_api_key: settings.tts?.siliconflow_api_key || '',
        siliconflow_model: settings.tts?.siliconflow_model || 'fnlp/MOSS-TTSD-v0.5',
        siliconflow_voice: settings.tts?.siliconflow_voice || 'anna',
        edge_tts_voice: settings.tts?.edge_tts_voice || 'en-US-AriaNeural',
        edge_tts_speed: settings.tts?.edge_tts_speed ?? 1.0,
        minimax_api_key: settings.tts?.minimax_api_key || '',
        minimax_model: settings.tts?.minimax_model || 'speech-2.8-hd',
        minimax_voice: settings.tts?.minimax_voice || 'male-qn-qingse',
        minimax_speed: settings.tts?.minimax_speed ?? 1.0
      }

      // 设置当前值
      ttsVoice.value = defaultTtsConfig.value.voice
      ttsSpeed.value = defaultTtsConfig.value.speed
      ttsApiUrl.value = defaultTtsConfig.value.api_url
      ttsAppId.value = defaultTtsConfig.value.app_id
      ttsAccessKey.value = defaultTtsConfig.value.access_key
      ttsResourceId.value = defaultTtsConfig.value.resource_id
      ttsSiliconFlowApiKey.value = defaultTtsConfig.value.siliconflow_api_key
      ttsSiliconFlowModel.value = defaultTtsConfig.value.siliconflow_model
      ttsEdgeTtsVoice.value = defaultTtsConfig.value.edge_tts_voice
      ttsMinimaxApiKey.value = defaultTtsConfig.value.minimax_api_key
      ttsMinimaxModel.value = defaultTtsConfig.value.minimax_model
      ttsMinimaxVoice.value = defaultTtsConfig.value.minimax_voice
      ttsMinimaxSpeed.value = defaultTtsConfig.value.minimax_speed

    } catch (error) {
      console.error('加载用户设置失败:', error)
    }
  }

  // 加载Kokoro语音列表
  const loadTtsVoices = async () => {
    try {
      const res = await api.get('/settings/tts/voices')
      if (Array.isArray(res.data)) {
        ttsVoices.value = res.data.map((v: string) => ({ id: v, name: v }))
      } else {
        ttsVoices.value = res.data.voices || []
      }

      // 如果当前语音不在列表中，添加它
      if (ttsServiceName.value === 'kokoro-tts' && ttsVoice.value) {
        const voiceExists = ttsVoices.value.some(v => v.id === ttsVoice.value)
        const isKokoroVoice = /^[ab]f_/.test(ttsVoice.value) || /^[ab]m_/.test(ttsVoice.value)
        if (!voiceExists && isKokoroVoice) {
          ttsVoices.value.unshift({
            id: ttsVoice.value,
            name: ttsVoice.value + ' (当前使用)'
          })
        }
      }
    } catch (error) {
      console.error('加载语音列表失败:', error)
      ttsVoices.value = []
      showNotify({ type: 'warning', message: '无法获取语音列表，请检查本地TTS服务是否运行' })
    }
  }

  // 加载Edge-TTS语音列表
  const loadEdgeTtsVoices = async () => {
    try {
      const res = await api.get('/settings/tts/edge/voices')
      if (res.data.voices && res.data.voices.length > 0) {
        edgeTtsVoices.value = res.data.voices
      } else {
        edgeTtsVoices.value = []
        showNotify({ type: 'warning', message: '没有可用的Edge-TTS语音模型' })
      }
    } catch (error) {
      console.error('加载Edge-TTS语音列表失败:', error)
      edgeTtsVoices.value = []
      showNotify({ type: 'warning', message: '无法获取Edge-TTS语音列表，请确保edge-tts已安装' })
    }
  }

  // 加载MiniMax语音列表
  const loadMinimaxVoices = async () => {
    try {
      const res = await api.get('/settings/tts/minimax/voices')
      if (res.data.error) {
        console.warn('获取MiniMax语音列表失败:', res.data.error)
        minimaxVoices.value = []
      } else if (res.data.voices && res.data.voices.length > 0) {
        minimaxVoices.value = res.data.voices
      } else {
        minimaxVoices.value = []
      }
    } catch (error) {
      console.error('加载MiniMax语音列表失败:', error)
      minimaxVoices.value = []
    }
  }

  // 验证TTS URL格式
  const validateTtsUrl = (value: string): boolean => {
    if (!value || value.trim() === '') {
      return true
    }
    return value.startsWith('http://') || value.startsWith('https://')
  }

  // 停止TTS测试播放
  const stopTtsTest = () => {
    if (currentTestAudio) {
      currentTestAudio.pause()
      currentTestAudio.currentTime = 0
      currentTestAudio = null
      ttsTesting.value = false
    }
  }

  // 测试TTS朗读
  const testTts = async () => {
    if (currentTestAudio) {
      stopTtsTest()
      showNotify({ type: 'success', message: '已停止播放', duration: 1000 })
      return
    }

    ttsTesting.value = true
    try {
      const voice = ttsVoice.value || defaultTtsConfig.value.voice
      const speed = ttsSpeed.value ?? 1.0

      const requestBody: any = {
        text: ttsTestText,
        voice: voice,
        speed: speed,
        service_name: ttsServiceName.value
      }

      if (ttsServiceName.value === 'siliconflow-tts') {
        requestBody.siliconflow_api_key = ttsSiliconFlowApiKey.value || null
        requestBody.siliconflow_model = ttsSiliconFlowModel.value || null
      }

      if (ttsServiceName.value === 'minimax-tts') {
        requestBody.minimax_api_key = ttsMinimaxApiKey.value || null
        requestBody.minimax_model = ttsMinimaxModel.value || null
      }

      const response = await fetch('/api/v1/tts/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authStore.token}`
        },
        body: JSON.stringify(requestBody)
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'TTS请求失败' }))
        throw new Error(errorData.detail || 'TTS请求失败')
      }

      const data = await response.json()

      if (data.audio_data) {
        const audioSrc = `data:audio/mp3;base64,${data.audio_data}`
        currentTestAudio = new Audio(audioSrc)
        if (ttsServiceName.value === 'doubao-tts' && speed !== 1.0) {
          currentTestAudio.playbackRate = speed
        }
        currentTestAudio.play()
        showNotify({ type: 'success', message: '正在播放测试语音', duration: 1500 })

        currentTestAudio.onended = () => {
          currentTestAudio = null
          ttsTesting.value = false
        }
      } else if (data.url) {
        currentTestAudio = new Audio(data.url)
        if (ttsServiceName.value === 'doubao-tts' && speed !== 1.0) {
          currentTestAudio.playbackRate = speed
        }
        currentTestAudio.play()
        showNotify({ type: 'success', message: '正在播放测试语音', duration: 1500 })

        currentTestAudio.onended = () => {
          currentTestAudio = null
          ttsTesting.value = false
        }
      } else {
        throw new Error('未获取到音频数据')
      }
    } catch (error: any) {
      console.error('TTS测试失败:', error)
      const errorMsg = error.message || '朗读测试失败'
      if (ttsServiceName.value === 'doubao-tts' && errorMsg.includes('app_id')) {
        showNotify({ type: 'danger', message: '豆包TTS需要配置APP ID和Access Key，请在设置中填写' })
      } else if (ttsServiceName.value === 'siliconflow-tts' && errorMsg.includes('api_key')) {
        showNotify({ type: 'danger', message: '硅基流动TTS需要配置API Key，请在设置中填写' })
      } else {
        showNotify({ type: 'danger', message: errorMsg })
      }
    } finally {
      ttsTesting.value = false
    }
  }

  // 检查MiniMax用量
  const checkMinimaxUsage = async () => {
    minimaxUsageChecking.value = true
    try {
      const res = await api.get('/settings/tts/minimax/usage')
      if (res.data.error) {
        showNotify({ type: 'warning', message: res.data.error })
        return null
      }

      const usage = res.data
      if (usage && usage.model_remains) {
        const speechHdRemain = usage.model_remains.find((item: any) =>
          item.model_name && item.model_name.toLowerCase().includes('speech-hd')
        )

        if (speechHdRemain) {
          const dailyRemaining = speechHdRemain.current_interval_usage_count || 0
          const dailyTotal = speechHdRemain.current_interval_total_count || 0
          const dailyUsed = dailyTotal - dailyRemaining
          const weeklyRemaining = speechHdRemain.current_weekly_usage_count || 0
          const weeklyTotal = speechHdRemain.current_weekly_total_count || 0
          const weeklyUsed = weeklyTotal - weeklyRemaining

          let message = `【speech-hd 语音配额】\n\n`
          if (dailyTotal > 0) {
            message += `今日配额: ${dailyTotal} 字符\n已用: ${dailyUsed} 字符\n剩余: ${dailyRemaining} 字符\n\n`
          }
          if (weeklyTotal > 0) {
            message += `本周配额: ${weeklyTotal} 字符\n已用: ${weeklyUsed} 字符\n剩余: ${weeklyRemaining} 字符`
          }

          await showConfirmDialog({
            title: 'MiniMax 语音配额',
            message: message,
            confirmButtonText: '确定'
          })
        }
      }
    } catch (error: any) {
      console.error('检查MiniMax用量失败:', error)
      showNotify({ type: 'warning', message: error.message || '无法查询MiniMax用量' })
    } finally {
      minimaxUsageChecking.value = false
    }
  }

  // 保存TTS设置
  const saveTtsSettings = async (): Promise<boolean> => {
    // 验证URL格式
    if (ttsApiUrl.value && !validateTtsUrl(ttsApiUrl.value)) {
      showNotify({ type: 'warning', message: '服务地址必须以 http:// 或 https:// 开头' })
      return false
    }

    // 验证语速范围
    if (ttsSpeed.value < speedRange.value.min || ttsSpeed.value > speedRange.value.max) {
      showNotify({
        type: 'warning',
        message: `朗读速度必须在 ${speedRange.value.min} 到 ${speedRange.value.max} 之间`
      })
      return false
    }

    try {
      const requestBody: any = {
        service_name: ttsServiceName.value.trim() || 'edge-tts'
      }

      switch (ttsServiceName.value) {
        case 'kokoro-tts':
          requestBody.kokoro_voice = ttsVoice.value.trim()
          requestBody.kokoro_speed = ttsSpeed.value
          requestBody.kokoro_api_url = ttsApiUrl.value.trim() || null
          break
        case 'siliconflow-tts':
          requestBody.siliconflow_api_key = ttsSiliconFlowApiKey.value.trim() || null
          requestBody.siliconflow_model = ttsSiliconFlowModel.value.trim() || null
          requestBody.siliconflow_voice = ttsVoice.value.trim()
          break
        case 'edge-tts':
          requestBody.edge_tts_voice = ttsVoice.value.trim()
          requestBody.edge_tts_speed = ttsSpeed.value
          break
        case 'minimax-tts':
          requestBody.minimax_api_key = ttsMinimaxApiKey.value.trim() || null
          requestBody.minimax_voice = ttsVoice.value.trim()
          requestBody.minimax_speed = ttsSpeed.value
          requestBody.minimax_model = ttsMinimaxModel.value.trim() || 'speech-2.8-hd'
          break
        default:
          requestBody.doubao_voice = ttsVoice.value.trim()
          requestBody.doubao_speed = ttsSpeed.value
          requestBody.doubao_app_id = ttsAppId.value.trim() || null
          requestBody.doubao_access_key = ttsAccessKey.value.trim() || null
          requestBody.doubao_resource_id = ttsResourceId.value.trim() || null
      }

      await api.put('/settings/tts', requestBody)
      showNotify({ type: 'success', message: '朗读设置已保存', duration: 1500 })
      return true
    } catch (error: any) {
      console.error('保存朗读设置失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
      return false
    }
  }

  // 打开设置对话框
  const openTtsSettings = async () => {
    await loadTtsVoices()
    await loadEdgeTtsVoices()
    await loadMinimaxVoices()
    showTtsSettingsDialog.value = true
  }

  // 关闭设置对话框
  const closeTtsSettings = () => {
    showTtsSettingsDialog.value = false
    stopTtsTest()
  }

  // 监听服务切换，加载对应的语音列表
  watch(ttsServiceName, async (newService, oldService) => {
    if (newService !== oldService && oldService !== undefined) {
      switch (newService) {
        case 'kokoro-tts':
          await loadTtsVoices()
          break
        case 'edge-tts':
          await loadEdgeTtsVoices()
          break
        case 'minimax-tts':
          await loadMinimaxVoices()
          break
      }
    }
  })

  return {
    // 状态
    showTtsSettingsDialog,
    ttsServiceName,
    ttsVoice,
    ttsSpeed,
    ttsApiUrl,
    ttsAppId,
    ttsAccessKey,
    ttsResourceId,
    ttsSiliconFlowApiKey,
    ttsSiliconFlowModel,
    ttsEdgeTtsVoice,
    ttsMinimaxApiKey,
    ttsMinimaxModel,
    ttsMinimaxVoice,
    ttsMinimaxSpeed,
    ttsTesting,
    minimaxUsageChecking,
    ttsTestText,
    availableVoices,
    supportsSpeed,
    speedRange,
    siliconflowModels,
    siliconflowVoices,
    doubaoVoices,

    // 方法
    loadUserSettings,
    loadTtsVoices,
    loadEdgeTtsVoices,
    loadMinimaxVoices,
    validateTtsUrl,
    stopTtsTest,
    testTts,
    checkMinimaxUsage,
    saveTtsSettings,
    openTtsSettings,
    closeTtsSettings
  }
}

// 需要导入 authStore 用于测试功能
import { useAuthStore } from '@/store/auth'
let authStore = useAuthStore()
