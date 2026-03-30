/**
 * TTS 设置 Composable
 * 集中管理所有TTS相关的状态和方法
 * 
 * 注意：状态定义在函数外部，确保所有组件共享同一状态
 */
import { ref, computed, watch } from 'vue'
import { showNotify, showToast } from 'vant'
import { api } from '@/store/auth'
import type { DefaultTtsConfig, VoiceItem } from '../types'

// ========== 模块级共享状态 ==========

const showTtsSettingsDialog = ref(false)
const ttsServiceName = ref('edge-tts')
const ttsVoice = ref('')
const ttsSpeed = ref(1.0)
const ttsApiUrl = ref('')
const ttsVoiceZh = ref('')
const ttsAppId = ref('')
const ttsAccessKey = ref('')
const ttsResourceId = ref('')
const ttsSiliconFlowApiKey = ref('')
const ttsSiliconFlowModel = ref('')
const ttsEdgeTtsVoice = ref('')
const ttsMinimaxApiKey = ref('')
const ttsMinimaxModel = ref('')
const ttsMinimaxVoice = ref('')
const ttsMinimaxSpeed = ref(1.0)
const ttsAzureSubscriptionKey = ref('')
const ttsAzureRegion = ref('')
const ttsAzureVoice = ref('')
const ttsAzureVoiceZh = ref('')
const ttsAzureSpeed = ref(1.0)
const ttsSettingsLoaded = ref(false)  // TTS设置是否已从数据库加载

const defaultTtsConfig = ref<DefaultTtsConfig>({
  service_name: 'edge-tts',
  voice: 'en-US-AriaNeural',
  voice_zh: '',
  speed: 1.0,
  api_url: 'http://localhost:8880/v1/audio/speech',
  app_id: '',
  access_key: '',
  resource_id: '',
  siliconflow_api_key: '',
  siliconflow_model: 'fnlp/MOSS-TTSD-v0.5',
  siliconflow_voice: 'anna',
  siliconflow_voice_zh: '',
  edge_tts_voice: 'en-US-AriaNeural',
  edge_tts_voice_zh: 'zh-CN-XiaoxiaoNeural',
  edge_tts_speed: 1.0,
  minimax_api_key: '',
  minimax_model: 'speech-2.8-hd',
  minimax_voice: 'male-qn-qingse',
  minimax_voice_zh: 'male-qn-qingse',
  minimax_speed: 1.0,
  azure_subscription_key: '',
  azure_region: '',
  azure_voice: 'en-US-JennyNeural',
  azure_voice_zh: 'zh-CN-XiaoxiaoNeural',
  azure_speed: 1.0,
  kokoro_voice_zh: 'zf_001',
  kokoro_voice: 'bf_v0isabella',
  doubao_voice: 'en_male_corey_emo_v2_mars_bigtts',
  doubao_voice_zh: 'zh_female_shuangkuaisisi_emo_v2_mars_bigtts'
})

// 语音列表（共享状态）
const ttsVoices = ref<VoiceItem[]>([])
const edgeTtsVoices = ref<VoiceItem[]>([])
const minimaxVoices = ref<VoiceItem[]>([])
const edgeTtsVoicesZh = ref<VoiceItem[]>([])
const minimaxVoicesZh = ref<VoiceItem[]>([])
const kokoroVoicesZh = ref<VoiceItem[]>([])
const azureVoices = ref<VoiceItem[]>([])
const azureVoicesZh = ref<VoiceItem[]>([])

// 测试相关状态
const minimaxUsageChecking = ref(false)
const azureUsageChecking = ref(false)
const ttsTesting = ref(false)
const ttsTestingZh = ref(false)
const azureVoicesLoading = ref(false)  // Azure音色列表加载状态
const azureVoicesZhLoading = ref(false)  // Azure中文音色列表加载状态

// 测试文本（常量）
const ttsTestText = "She practiced the piano sonata with grace and concentration."
const ttsTestTextZh = "她认真练习钢琴奏鸣曲，展现出优雅与专注。"

let currentTestAudio: HTMLAudioElement | null = null
let currentTestAudioZh: HTMLAudioElement | null = null

// 硅基流动固定模型和语音列表（常量）
const siliconflowModels = [
  { id: 'fnlp/MOSS-TTSD-v0.5', name: 'MOSS TTSD v0.5' },
  { id: 'FunAudioLLM/CosyVoice2-0.5B', name: 'CosyVoice2 0.5B' },
  { id: 'IndexTeam/IndexTTS-2', name: 'IndexTTS 2' }
]

const siliconflowVoices = [
  { id: 'anna', name: 'Anna' },
  { id: 'alex', name: 'Alex' },
  { id: 'bella', name: 'Bella' },
  { id: 'benjamin', name: 'Benjamin' },
  { id: 'charles', name: 'Charles' },
  { id: 'claire', name: 'Claire' },
  { id: 'david', name: 'David' },
  { id: 'diana', name: 'Diana' }
]

export const useTtsSettings = () => {

  // ========== 豆包TTS音色列表 ==========

  const doubaoVoices = [
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

  const doubaoVoicesZh = [
    { id: 'zh_female_shuangkuaisisi_emo_v2_mars_bigtts', name: '爽快思思(多情感)' },
    { id: 'zh_female_yingyujiaoyu_mars_bigtts', name: 'Tina老师' },
    { id: 'zh_female_shuangkuaisisi_moon_bigtts', name: '爽快思思/Skye' },
  ]

  // ========== 计算属性 ==========

  // 根据服务类型获取对应的语音列表
  const availableVoices = computed(() => {
    if (ttsServiceName.value === 'doubao-tts') return doubaoVoices
    if (ttsServiceName.value === 'siliconflow-tts') return siliconflowVoices

    let result: VoiceItem[]
    if (ttsServiceName.value === 'edge-tts') result = edgeTtsVoices.value
    else if (ttsServiceName.value === 'minimax-tts') result = minimaxVoices.value
    else if (ttsServiceName.value === 'azure-tts') {
      // Azure 正在加载时：先显示数据库保存的语音 + 加载提示
      if (azureVoicesLoading.value) {
        const voicesList = azureVoices.value.length > 0 ? azureVoices.value : []
        // 如果有选中的语音但列表为空，添加兜底选项
        if (voicesList.length === 0 && ttsVoice.value) {
          return [{ id: ttsVoice.value, name: ttsVoice.value + ' (当前使用)' }, { id: 'loading', name: '🔄 正在获取音色列表...' }]
        }
        // 如果列表有内容但正在重新加载，只显示已有内容
        return voicesList
      }
      result = azureVoices.value
    }
    else result = ttsVoices.value // kokoro-tts

    // 兆底逻辑：列表未加载完成时，如果当前选中値存在，先添加为临时选项保证显示
    if (result.length === 0 && ttsVoice.value) {
      return [{ id: ttsVoice.value, name: ttsVoice.value + ' (当前使用)' }]
    }
    return result
  })

  // 根据服务类型获取对应的中文语音列表
  const availableVoicesZh = computed(() => {
    let result: VoiceItem[] = []
    if (ttsServiceName.value === 'doubao-tts') result = doubaoVoicesZh
    else if (ttsServiceName.value === 'siliconflow-tts') result = siliconflowVoices
    else if (ttsServiceName.value === 'edge-tts') result = edgeTtsVoicesZh.value
    else if (ttsServiceName.value === 'minimax-tts') result = minimaxVoicesZh.value
    else if (ttsServiceName.value === 'azure-tts') {
      // Azure 正在加载时：先显示数据库保存的语音 + 加载提示
      if (azureVoicesZhLoading.value) {
        const voicesList = azureVoicesZh.value.length > 0 ? azureVoicesZh.value : []
        // 如果有选中的语音但列表为空，添加兜底选项
        if (voicesList.length === 0 && ttsVoiceZh.value) {
          return [{ id: ttsVoiceZh.value, name: ttsVoiceZh.value + ' (当前使用)' }, { id: 'loading', name: '🔄 正在获取音色列表...' }]
        }
        // 如果列表有内容但正在重新加载，只显示已有内容
        return voicesList
      }
      result = azureVoicesZh.value
    }
    else result = kokoroVoicesZh.value

    // 兼底逻辑：列表未加载完成时，如果当前选中値存在，先添加为临时选项保证显示
    if (result.length === 0 && ttsVoiceZh.value) {
      result = [{ id: ttsVoiceZh.value, name: ttsVoiceZh.value + ' (当前使用)' }]
    }

    console.log(`[availableVoicesZh] 服务: ${ttsServiceName.value}, 结果长度: ${result.length}, edgeTtsVoicesZh长度: ${edgeTtsVoicesZh.value.length}`)
    return result
  })

  // ========== 加载方法 ==========

  /**
   * 加载TTS语音列表
   */
  const loadTtsVoices = async () => {
    try {
      const res = await api.get('/settings/tts/voices')
      if (Array.isArray(res.data)) {
        ttsVoices.value = res.data.map((v: string) => ({ id: v, name: v }))
      } else {
        ttsVoices.value = res.data.voices || []
      }

      if (ttsServiceName.value === 'kokoro-tts' && ttsVoice.value) {
        const voiceExists = ttsVoices.value.some((v) => v.id === ttsVoice.value)
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

  /**
   * 将 Edge-TTS 语音 ID 转换为显示名称
   */
  const formatEdgeTtsVoiceName = (voiceId: string): string => {
    if (!voiceId) return ''

    const regionNames: Record<string, string> = {
      'en-US': '美式英语',
      'en-GB': '英式英语',
    }

    const parts = voiceId.split('-')
    if (parts.length < 3) return voiceId

    const regionCode = `${parts[0]}-${parts[1]}`
    const regionName = regionNames[regionCode] || regionCode

    const voiceName = parts.slice(2).join('-')
      .replace(/Neural$/, '')
      .replace(/Multilingual$/, '')

    return `${regionName} - ${voiceName}`
  }

  /**
   * 加载Edge-TTS语音列表
   */
  const loadEdgeTtsVoices = async () => {
    try {
      const res = await api.get('/settings/tts/edge/voices')
      if (res.data.voices && res.data.voices.length > 0) {
        edgeTtsVoices.value = res.data.voices
        if (ttsVoice.value && ttsServiceName.value === 'edge-tts') {
          const voiceExists = edgeTtsVoices.value.some((v) => v.id === ttsVoice.value)
          if (!voiceExists) {
            edgeTtsVoices.value.unshift({
              id: ttsVoice.value,
              name: formatEdgeTtsVoiceName(ttsVoice.value) + ' (当前使用)'
            })
          }
        }
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

  /**
   * 加载MiniMax TTS语音列表
   */
  const loadMinimaxVoices = async () => {
    try {
      const res = await api.get('/settings/tts/minimax/voices')
      if (res.data.error) {
        console.warn('获取MiniMax语音列表失败:', res.data.error)
        minimaxVoices.value = []
      } else if (res.data.voices && res.data.voices.length > 0) {
        minimaxVoices.value = res.data.voices
        if (ttsVoice.value && ttsServiceName.value === 'minimax-tts') {
          const voiceExists = minimaxVoices.value.some((v) => v.id === ttsVoice.value)
          if (!voiceExists) {
            minimaxVoices.value.unshift({
              id: ttsVoice.value,
              name: ttsVoice.value + ' (当前使用)'
            })
          }
        }
      } else {
        minimaxVoices.value = []
      }
    } catch (error) {
      console.error('加载MiniMax语音列表失败:', error)
      minimaxVoices.value = []
    }
  }

  /**
   * 加载Edge-TTS中文语音列表
   */
  const loadEdgeTtsVoicesZh = async () => {
    try {
      const res = await api.get('/settings/tts/edge/voices/zh')
      console.log('[Edge TTS 中文音色] API 返回:', res.data)
      if (res.data.voices && res.data.voices.length > 0) {
        edgeTtsVoicesZh.value = res.data.voices
        console.log('[Edge TTS 中文音色] 已加载', res.data.voices.length, '个音色')
        if (ttsVoiceZh.value && ttsServiceName.value === 'edge-tts') {
          const voiceExists = edgeTtsVoicesZh.value.some((v) => v.id === ttsVoiceZh.value)
          if (!voiceExists) {
            edgeTtsVoicesZh.value.unshift({
              id: ttsVoiceZh.value,
              name: ttsVoiceZh.value + ' (当前使用)'
            })
          }
        }
      } else {
        console.warn('[Edge TTS 中文音色] 返回为空:', res.data)
        edgeTtsVoicesZh.value = []
      }
    } catch (error) {
      console.error('加载Edge-TTS中文语音列表失败:', error)
      edgeTtsVoicesZh.value = []
    }
  }

  /**
   * 加载MiniMax中文语音列表
   */
  const loadMinimaxVoicesZh = async () => {
    try {
      const res = await api.get('/settings/tts/minimax/voices/zh')
      if (res.data.error) {
        console.warn('获取MiniMax中文语音列表失败:', res.data.error)
        minimaxVoicesZh.value = []
      } else if (res.data.voices && res.data.voices.length > 0) {
        minimaxVoicesZh.value = res.data.voices
        if (ttsVoiceZh.value && ttsServiceName.value === 'minimax-tts') {
          const voiceExists = minimaxVoicesZh.value.some((v) => v.id === ttsVoiceZh.value)
          if (!voiceExists) {
            minimaxVoicesZh.value.unshift({
              id: ttsVoiceZh.value,
              name: ttsVoiceZh.value + ' (当前使用)'
            })
          }
        }
      } else {
        minimaxVoicesZh.value = []
      }
    } catch (error) {
      console.error('加载MiniMax中文语音列表失败:', error)
      minimaxVoicesZh.value = []
    }
  }

  /**
   * 加载Kokoro中文语音列表
   */
  const loadKokoroVoicesZh = async () => {
    try {
      const res = await api.get('/settings/tts/kokoro/voices/zh')
      if (res.data.voices && res.data.voices.length > 0) {
        kokoroVoicesZh.value = res.data.voices
        if (ttsVoiceZh.value && ttsServiceName.value === 'kokoro-tts') {
          const voiceExists = kokoroVoicesZh.value.some((v) => v.id === ttsVoiceZh.value)
          if (!voiceExists) {
            kokoroVoicesZh.value.unshift({
              id: ttsVoiceZh.value,
              name: ttsVoiceZh.value + ' (当前使用)'
            })
          }
        }
      } else {
        kokoroVoicesZh.value = []
      }
    } catch (error) {
      console.error('加载Kokoro中文语音列表失败:', error)
      kokoroVoicesZh.value = []
    }
  }

  /**
   * 加载Azure TTS语音列表
   */
  const loadAzureVoices = async () => {
    azureVoicesLoading.value = true
    try {
      const res = await api.get('/settings/tts/azure/voices')
      if (res.data.error) {
        console.warn('获取Azure语音列表失败:', res.data.error)
        azureVoices.value = []
      } else if (res.data.voices && res.data.voices.length > 0) {
        azureVoices.value = res.data.voices
        if (ttsVoice.value && ttsServiceName.value === 'azure-tts') {
          const voiceExists = azureVoices.value.some((v) => v.id === ttsVoice.value)
          if (!voiceExists) {
            azureVoices.value.unshift({
              id: ttsVoice.value,
              name: ttsVoice.value + ' (当前使用)'
            })
          }
        }
      } else {
        azureVoices.value = []
      }
    } catch (error) {
      console.error('加载Azure语音列表失败:', error)
      azureVoices.value = []
    } finally {
      azureVoicesLoading.value = false
    }
  }

  /**
   * 加载Azure TTS中文语音列表
   */
  const loadAzureVoicesZh = async () => {
    azureVoicesZhLoading.value = true
    try {
      const res = await api.get('/settings/tts/azure/voices/zh')
      if (res.data.error) {
        console.warn('获取Azure中文语音列表失败:', res.data.error)
        azureVoicesZh.value = []
      } else if (res.data.voices && res.data.voices.length > 0) {
        azureVoicesZh.value = res.data.voices
        if (ttsVoiceZh.value && ttsServiceName.value === 'azure-tts') {
          const voiceExists = azureVoicesZh.value.some((v) => v.id === ttsVoiceZh.value)
          if (!voiceExists) {
            azureVoicesZh.value.unshift({
              id: ttsVoiceZh.value,
              name: ttsVoiceZh.value + ' (当前使用)'
            })
          }
        }
      } else {
        azureVoicesZh.value = []
      }
    } catch (error) {
      console.error('加载Azure中文语音列表失败:', error)
      azureVoicesZh.value = []
    } finally {
      azureVoicesZhLoading.value = false
    }
  }

  /**
   * 检查Azure用量
   */
  const checkMinimaxUsage = async () => {
    try {
      console.log('开始查询MiniMax用量...')
      const res = await api.get('/settings/tts/minimax/usage')
      console.log('MiniMax用量响应:', res.data)
      if (res.data.error) {
        showNotify({ type: 'warning', message: res.data.error })
        return null
      }
      return res.data
    } catch (error: any) {
      console.error('检查MiniMax用量失败:', error)
      showNotify({ type: 'warning', message: error.message || '无法查询MiniMax用量' })
      return null
    }
  }

  /**
   * 查询MiniMax用量（带UI显示）
   */
  const handleCheckMinimaxUsage = async () => {
    minimaxUsageChecking.value = true
    try {
      const usage = await checkMinimaxUsage()
      console.log('[DEBUG] MiniMax usage response:', JSON.stringify(usage, null, 2))
      if (usage && usage.model_remains) {
        const speechHdRemain = usage.model_remains.find((item: any) =>
          item.model_name && item.model_name.toLowerCase().includes('speech-hd')
        )

        let message = ''

        if (speechHdRemain) {
          const dailyRemaining = speechHdRemain.current_interval_usage_count || 0
          const dailyTotal = speechHdRemain.current_interval_total_count || 0
          const dailyUsed = dailyTotal - dailyRemaining
          const weeklyRemaining = speechHdRemain.current_weekly_usage_count || 0
          const weeklyTotal = speechHdRemain.current_weekly_total_count || 0
          const weeklyUsed = weeklyTotal - weeklyRemaining

          message = `【speech-hd 语音配额】\n\n`
          if (dailyTotal > 0) {
            message += `今日配额: ${dailyTotal} 字符\n已用: ${dailyUsed} 字符\n剩余: ${dailyRemaining} 字符\n\n`
          }
          if (weeklyTotal > 0) {
            message += `本周配额: ${weeklyTotal} 字符\n已用: ${weeklyUsed} 字符\n剩余: ${weeklyRemaining} 字符`
          }
        } else {
          message = '未找到 speech-hd 配额信息'
        }

        showNotify({ type: 'primary', message })
      }
    } finally {
      minimaxUsageChecking.value = false
    }
  }

  /**
   * 检查Azure用量
   */
  const checkAzureUsage = async (days: number = 30) => {
    try {
      console.log('开始查询Azure TTS用量...')
      const res = await api.get(`/settings/tts/azure/usage?days=${days}`)
      console.log('Azure用量响应:', res.data)
      if (res.data.error) {
        showNotify({ type: 'warning', message: res.data.error })
        return null
      }
      return res.data
    } catch (error: any) {
      console.error('检查Azure用量失败:', error)
      showNotify({ type: 'warning', message: error.message || '无法查询Azure用量' })
      return null
    }
  }

  /**
   * 查询Azure用量（带UI显示）
   */
  const handleCheckAzureUsage = async () => {
    azureUsageChecking.value = true
    try {
      const usage = await checkAzureUsage(30)
      if (usage) {
        let message = '【Azure TTS 用量查询】\n\n'
        if (usage.message) {
          message += usage.message + '\n\n'
        }
        if (usage.note) {
          message += usage.note
        }
        showNotify({ type: 'primary', message })
      }
    } finally {
      azureUsageChecking.value = false
    }
  }

  // ========== TTS测试方法 ==========

  /**
   * 停止TTS测试播放
   */
  const stopTtsTest = () => {
    if (currentTestAudio) {
      currentTestAudio.pause()
      currentTestAudio.currentTime = 0
      currentTestAudio = null
      ttsTesting.value = false
    }
  }

  /**
   * 停止中文TTS测试播放
   */
  const stopTtsTestZh = () => {
    if (currentTestAudioZh) {
      currentTestAudioZh.pause()
      currentTestAudioZh.currentTime = 0
      currentTestAudioZh = null
      ttsTestingZh.value = false
    }
  }

  /**
   * 测试TTS朗读
   */
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

      if (ttsServiceName.value === 'azure-tts') {
        requestBody.azure_subscription_key = ttsAzureSubscriptionKey.value || null
        requestBody.azure_region = ttsAzureRegion.value || null
      }

      const response = await fetch('/api/v1/tts/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
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

  /**
   * 测试中文TTS朗读
   */
  const testTtsZh = async () => {
    if (currentTestAudioZh) {
      stopTtsTestZh()
      showNotify({ type: 'success', message: '已停止播放', duration: 1000 })
      return
    }

    ttsTestingZh.value = true
    try {
      const voice = ttsVoiceZh.value || defaultTtsConfig.value.voice_zh || defaultTtsConfig.value.voice
      const speed = ttsSpeed.value ?? 1.0

      const requestBody: any = {
        text: ttsTestTextZh,
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

      if (ttsServiceName.value === 'azure-tts') {
        requestBody.azure_subscription_key = ttsAzureSubscriptionKey.value || null
        requestBody.azure_region = ttsAzureRegion.value || null
      }

      const response = await fetch('/api/v1/tts/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
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
        currentTestAudioZh = new Audio(audioSrc)
        if (ttsServiceName.value === 'doubao-tts' && speed !== 1.0) {
          currentTestAudioZh.playbackRate = speed
        }
        currentTestAudioZh.play()
        showNotify({ type: 'success', message: '正在播放中文测试语音', duration: 1500 })

        currentTestAudioZh.onended = () => {
          currentTestAudioZh = null
        }
      } else if (data.url) {
        currentTestAudioZh = new Audio(data.url)
        if (ttsServiceName.value === 'doubao-tts' && speed !== 1.0) {
          currentTestAudioZh.playbackRate = speed
        }
        currentTestAudioZh.play()
        showNotify({ type: 'success', message: '正在播放中文测试语音', duration: 1500 })

        currentTestAudioZh.onended = () => {
          currentTestAudioZh = null
        }
      } else {
        throw new Error('未获取到音频数据')
      }
    } catch (error: any) {
      console.error('中文TTS测试失败:', error)
      const errorMsg = error.message || '朗读测试失败'
      if (ttsServiceName.value === 'doubao-tts' && errorMsg.includes('app_id')) {
        showNotify({ type: 'danger', message: '豆包TTS需要配置APP ID和Access Key，请在设置中填写' })
      } else if (ttsServiceName.value === 'siliconflow-tts' && errorMsg.includes('api_key')) {
        showNotify({ type: 'danger', message: '硅基流动TTS需要配置API Key，请在设置中填写' })
      } else {
        showNotify({ type: 'danger', message: errorMsg })
      }
    } finally {
      ttsTestingZh.value = false
    }
  }

  // ========== 验证和保存方法 ==========

  /**
   * 验证TTS URL格式
   */
  const validateTtsUrl = (value: string) => {
    if (!value || value.trim() === '') return true
    return value.startsWith('http://') || value.startsWith('https://')
  }

  /**
   * 显示TTS URL帮助
   */
  const showTtsUrlHelp = () => {
    showToast({
      message: '设置自定义Kokoro TTS服务地址，留空则使用系统默认配置',
      duration: 3000
    })
  }

  /**
   * 保存朗读设置
   */
  const saveTtsSettings = async () => {
    if (ttsApiUrl.value && !validateTtsUrl(ttsApiUrl.value)) {
      showNotify({ type: 'warning', message: '服务地址必须以 http:// 或 https:// 开头' })
      return
    }

    const isKokoro = ttsServiceName.value === 'kokoro-tts'
    const isSiliconFlow = ttsServiceName.value === 'siliconflow-tts'
    const isEdgeTts = ttsServiceName.value === 'edge-tts'
    const isMinimax = ttsServiceName.value === 'minimax-tts'
    const isAzure = ttsServiceName.value === 'azure-tts'

    if (isKokoro && (ttsSpeed.value < 0.25 || ttsSpeed.value > 4.0)) {
      showNotify({ type: 'warning', message: 'Kokoro 朗读速度必须在 0.25 到 4.0 之间' })
      return
    }
    if (isMinimax && (ttsSpeed.value < 0.25 || ttsSpeed.value > 4.0)) {
      showNotify({ type: 'warning', message: 'MiniMax 朗读速度必须在 0.25 到 4.0 之间' })
      return
    }
    if ((isEdgeTts || isAzure || !isKokoro && !isSiliconFlow && !isMinimax) && (ttsSpeed.value < 0.5 || ttsSpeed.value > 2.0)) {
      showNotify({ type: 'warning', message: '朗读速度必须在 0.5 到 2.0 之间' })
      return
    }

    try {
      const requestBody: any = {
        service_name: ttsServiceName.value.trim() || 'kokoro-tts'
      }

      if (isKokoro) {
        requestBody.kokoro_voice = ttsVoice.value.trim()
        requestBody.kokoro_speed = ttsSpeed.value
        requestBody.kokoro_api_url = ttsApiUrl.value.trim() || null
        requestBody.kokoro_voice_zh = ttsVoiceZh.value.trim() || null
      } else if (isSiliconFlow) {
        requestBody.siliconflow_api_key = ttsSiliconFlowApiKey.value.trim() || null
        requestBody.siliconflow_model = ttsSiliconFlowModel.value.trim() || null
        requestBody.siliconflow_voice = ttsVoice.value.trim()
        requestBody.siliconflow_voice_zh = ttsVoiceZh.value.trim() || null
      } else if (isEdgeTts) {
        requestBody.edge_tts_voice = ttsVoice.value.trim()
        requestBody.edge_tts_speed = ttsSpeed.value
        requestBody.edge_tts_voice_zh = ttsVoiceZh.value.trim() || null
      } else if (isMinimax) {
        requestBody.minimax_api_key = ttsMinimaxApiKey.value.trim() || null
        requestBody.minimax_voice = ttsVoice.value.trim()
        requestBody.minimax_speed = ttsSpeed.value
        requestBody.minimax_model = ttsMinimaxModel.value.trim() || 'speech-2.8-hd'
        requestBody.minimax_voice_zh = ttsVoiceZh.value.trim() || null
      } else if (isAzure) {
        requestBody.azure_subscription_key = ttsAzureSubscriptionKey.value.trim() || null
        requestBody.azure_region = ttsAzureRegion.value.trim() || null
        requestBody.azure_voice = ttsVoice.value.trim()
        requestBody.azure_speed = ttsSpeed.value
        requestBody.azure_voice_zh = ttsVoiceZh.value.trim() || null
      } else {
        requestBody.doubao_voice = ttsVoice.value.trim()
        requestBody.doubao_speed = ttsSpeed.value
        requestBody.doubao_app_id = ttsAppId.value.trim() || null
        requestBody.doubao_access_key = ttsAccessKey.value.trim() || null
        requestBody.doubao_resource_id = ttsResourceId.value.trim() || null
        requestBody.doubao_voice_zh = ttsVoiceZh.value.trim() || null
      }

      await api.put('/settings/tts', requestBody)
      showNotify({ type: 'success', message: '朗读设置已保存', duration: 1500 })
    } catch (error: any) {
      console.error('保存朗读设置失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
    }
  }

  /**
   * 加载用户设置
   */
  const loadUserSettings = async () => {
    try {
      const res = await api.get('/settings/')

      const serviceName = res.data.tts?.service_name || 'edge-tts'

      let voice = ''
      let voiceZh = ''
      let speed = 1.0

      switch (serviceName) {
        case 'kokoro-tts':
          voice = res.data.tts?.kokoro_voice || 'bf_v0isabella'
          voiceZh = res.data.tts?.kokoro_voice_zh || 'zf_001'
          speed = res.data.tts?.kokoro_speed ?? 1.0
          break
        case 'doubao-tts':
          voice = res.data.tts?.doubao_voice || 'en_male_corey_emo_v2_mars_bigtts'
          voiceZh = res.data.tts?.doubao_voice_zh || 'zh_female_shuangkuaisisi_emo_v2_mars_bigtts'
          speed = res.data.tts?.doubao_speed ?? 1.0
          break
        case 'siliconflow-tts':
          voice = res.data.tts?.siliconflow_voice || 'anna'
          voiceZh = res.data.tts?.siliconflow_voice_zh || 'anna'
          speed = 1.0
          break
        case 'edge-tts':
          voice = res.data.tts?.edge_tts_voice || 'en-US-AriaNeural'
          voiceZh = res.data.tts?.edge_tts_voice_zh || 'zh-CN-XiaoxiaoNeural'
          speed = res.data.tts?.edge_tts_speed ?? 1.0
          break
        case 'minimax-tts':
          voice = res.data.tts?.minimax_voice || 'male-qn-qingse'
          voiceZh = res.data.tts?.minimax_voice_zh || 'male-qn-qingse'
          speed = res.data.tts?.minimax_speed ?? 1.0
          break
        case 'azure-tts':
          voice = res.data.tts?.azure_voice || 'en-US-JennyNeural'
          voiceZh = res.data.tts?.azure_voice_zh || 'zh-CN-XiaoxiaoNeural'
          speed = res.data.tts?.azure_speed ?? 1.0
          break
        default:
          voice = 'en-US-AriaNeural'
          voiceZh = 'zh-CN-XiaoxiaoNeural'
          speed = 1.0
      }

      defaultTtsConfig.value = {
        service_name: serviceName,
        voice: voice,
        voice_zh: voiceZh,
        speed: speed,
        api_url: res.data.tts?.kokoro_api_url || '',
        app_id: res.data.tts?.doubao_app_id || '',
        access_key: res.data.tts?.doubao_access_key || '',
        resource_id: res.data.tts?.doubao_resource_id || '',
        siliconflow_api_key: res.data.tts?.siliconflow_api_key || '',
        siliconflow_model: res.data.tts?.siliconflow_model || 'fnlp/MOSS-TTSD-v0.5',
        siliconflow_voice: res.data.tts?.siliconflow_voice || 'anna',
        siliconflow_voice_zh: res.data.tts?.siliconflow_voice_zh || 'anna',
        edge_tts_voice: res.data.tts?.edge_tts_voice || 'en-US-AriaNeural',
        edge_tts_voice_zh: res.data.tts?.edge_tts_voice_zh || 'zh-CN-XiaoxiaoNeural',
        edge_tts_speed: res.data.tts?.edge_tts_speed ?? 1.0,
        minimax_api_key: res.data.tts?.minimax_api_key || '',
        minimax_model: res.data.tts?.minimax_model || 'speech-2.8-hd',
        minimax_voice: res.data.tts?.minimax_voice || 'male-qn-qingse',
        minimax_voice_zh: res.data.tts?.minimax_voice_zh || 'male-qn-qingse',
        minimax_speed: res.data.tts?.minimax_speed ?? 1.0,
        azure_subscription_key: res.data.tts?.azure_subscription_key || '',
        azure_region: res.data.tts?.azure_region || '',
        azure_voice: res.data.tts?.azure_voice || 'en-US-JennyNeural',
        azure_voice_zh: res.data.tts?.azure_voice_zh || 'zh-CN-XiaoxiaoNeural',
        azure_speed: res.data.tts?.azure_speed ?? 1.0,
        kokoro_voice_zh: res.data.tts?.kokoro_voice_zh || 'zf_001',
        kokoro_voice: res.data.tts?.kokoro_voice || 'bf_v0isabella',
        doubao_voice: res.data.tts?.doubao_voice || 'en_male_corey_emo_v2_mars_bigtts',
        doubao_voice_zh: res.data.tts?.doubao_voice_zh || 'zh_female_shuangkuaisisi_emo_v2_mars_bigtts'
      }

      ttsServiceName.value = defaultTtsConfig.value.service_name
      ttsVoice.value = voice
      ttsVoiceZh.value = voiceZh
      ttsSpeed.value = speed
      ttsApiUrl.value = defaultTtsConfig.value.api_url || ''
      ttsAppId.value = defaultTtsConfig.value.app_id || ''
      ttsAccessKey.value = defaultTtsConfig.value.access_key || ''
      ttsResourceId.value = defaultTtsConfig.value.resource_id || ''
      ttsSiliconFlowApiKey.value = res.data.tts?.siliconflow_api_key || ''
      ttsSiliconFlowModel.value = res.data.tts?.siliconflow_model || 'fnlp/MOSS-TTSD-v0.5'
      ttsEdgeTtsVoice.value = res.data.tts?.edge_tts_voice || 'en-US-AriaNeural'
      ttsMinimaxApiKey.value = res.data.tts?.minimax_api_key || ''
      ttsMinimaxModel.value = res.data.tts?.minimax_model || 'speech-2.8-hd'
      ttsMinimaxVoice.value = res.data.tts?.minimax_voice || 'male-qn-qingse'
      ttsMinimaxSpeed.value = res.data.tts?.minimax_speed ?? 1.0
      ttsAzureSubscriptionKey.value = res.data.tts?.azure_subscription_key || ''
      ttsAzureRegion.value = res.data.tts?.azure_region || ''
      ttsAzureVoice.value = res.data.tts?.azure_voice || 'en-US-JennyNeural'
      ttsAzureVoiceZh.value = res.data.tts?.azure_voice_zh || 'zh-CN-XiaoxiaoNeural'
      ttsAzureSpeed.value = res.data.tts?.azure_speed ?? 1.0
      ttsSettingsLoaded.value = true  // 标记为已加载
    } catch (error) {
      console.error('加载用户设置失败:', error)
    }
  }

  // ========== 显示TTS设置弹窗 ==========
  const openTtsSettings = () => {
    // 第一步：立即显示对话框（用已缓存的 defaultTtsConfig 值，无需等待任何请求）
    showTtsSettingsDialog.value = true

    // 第二步：异步加载数据库设置，不阻塞对话框显示
    setTimeout(async () => {
      await loadUserSettings()

      // 加载完数据库后，添加当前选中値的临时选项（兑底，确保下拉框有値显示）
      if (ttsVoice.value) {
        if (ttsServiceName.value === 'edge-tts') {
          if (!edgeTtsVoices.value.some(v => v.id === ttsVoice.value)) {
            edgeTtsVoices.value.unshift({ id: ttsVoice.value, name: formatEdgeTtsVoiceName(ttsVoice.value) + ' (当前使用)' })
          }
        } else if (ttsServiceName.value === 'minimax-tts') {
          if (!minimaxVoices.value.some(v => v.id === ttsVoice.value)) {
            minimaxVoices.value.unshift({ id: ttsVoice.value, name: ttsVoice.value + ' (当前使用)' })
          }
        } else if (ttsServiceName.value === 'kokoro-tts') {
          if (!ttsVoices.value.some(v => v.id === ttsVoice.value)) {
            ttsVoices.value.unshift({ id: ttsVoice.value, name: ttsVoice.value + ' (当前使用)' })
          }
        }
      }

      if (ttsVoiceZh.value) {
        if (ttsServiceName.value === 'edge-tts') {
          if (!edgeTtsVoicesZh.value.some(v => v.id === ttsVoiceZh.value)) {
            edgeTtsVoicesZh.value.unshift({ id: ttsVoiceZh.value, name: ttsVoiceZh.value + ' (当前使用)' })
          }
        } else if (ttsServiceName.value === 'minimax-tts') {
          if (!minimaxVoicesZh.value.some(v => v.id === ttsVoiceZh.value)) {
            minimaxVoicesZh.value.unshift({ id: ttsVoiceZh.value, name: ttsVoiceZh.value + ' (当前使用)' })
          }
        } else if (ttsServiceName.value === 'kokoro-tts') {
          if (!kokoroVoicesZh.value.some(v => v.id === ttsVoiceZh.value)) {
            kokoroVoicesZh.value.unshift({ id: ttsVoiceZh.value, name: ttsVoiceZh.value + ' (当前使用)' })
          }
        }
      }

      // 第三步：异步加载网络音色列表，不阻塞数据库设置显示
      loadTtsVoices()
      loadEdgeTtsVoices()
      loadMinimaxVoices()
      loadEdgeTtsVoicesZh()
      loadMinimaxVoicesZh()
      loadKokoroVoicesZh()
      // 不在这里调用 Azure 语音列表，只在打开朗读设置对话框时加载
    }, 0)
  }

  // ========== 监听服务切换，从数据库恢复该服务的设置 ==========
  watch(ttsServiceName, (newService, oldService) => {
    if (newService !== oldService && oldService !== undefined) {
      // 第一阶段：立即从 defaultTtsConfig 恢复数据库设置（无需等待网络）
      switch (newService) {
        case 'kokoro-tts':
          ttsVoice.value = defaultTtsConfig.value.kokoro_voice || 'bf_v0isabella'
          ttsSpeed.value = defaultTtsConfig.value.speed ?? 1.0
          ttsVoiceZh.value = defaultTtsConfig.value.kokoro_voice_zh || 'zf_001'
          break
        case 'siliconflow-tts':
          ttsVoice.value = defaultTtsConfig.value.siliconflow_voice || 'anna'
          ttsSiliconFlowModel.value = defaultTtsConfig.value.siliconflow_model || 'fnlp/MOSS-TTSD-v0.5'
          ttsVoiceZh.value = defaultTtsConfig.value.siliconflow_voice_zh || 'anna'
          break
        case 'edge-tts':
          ttsVoice.value = defaultTtsConfig.value.edge_tts_voice || 'en-US-AriaNeural'
          ttsSpeed.value = defaultTtsConfig.value.edge_tts_speed ?? 1.0
          ttsVoiceZh.value = defaultTtsConfig.value.edge_tts_voice_zh || 'zh-CN-XiaoxiaoNeural'
          break
        case 'minimax-tts':
          ttsVoice.value = defaultTtsConfig.value.minimax_voice || 'male-qn-qingse'
          ttsSpeed.value = defaultTtsConfig.value.minimax_speed ?? 1.0
          ttsMinimaxModel.value = defaultTtsConfig.value.minimax_model || 'speech-2.8-hd'
          ttsVoiceZh.value = defaultTtsConfig.value.minimax_voice_zh || 'male-qn-qingse'
          break
        case 'azure-tts':
          ttsVoice.value = defaultTtsConfig.value.azure_voice || 'en-US-JennyNeural'
          ttsSpeed.value = defaultTtsConfig.value.azure_speed ?? 1.0
          ttsVoiceZh.value = defaultTtsConfig.value.azure_voice_zh || 'zh-CN-XiaoxiaoNeural'
          ttsAzureSubscriptionKey.value = defaultTtsConfig.value.azure_subscription_key || ''
          ttsAzureRegion.value = defaultTtsConfig.value.azure_region || ''
          break
        default: // doubao-tts
          ttsVoice.value = defaultTtsConfig.value.doubao_voice || 'en_male_corey_emo_v2_mars_bigtts'
          ttsSpeed.value = defaultTtsConfig.value.speed ?? 1.0
          ttsResourceId.value = defaultTtsConfig.value.resource_id || 'seed-tts-1.0'
          ttsVoiceZh.value = defaultTtsConfig.value.doubao_voice_zh || 'zh_female_shuangkuaisisi_emo_v2_mars_bigtts'
          break
      }

      // 第二阶段：异步加载语音列表（不阻塞UI）
      setTimeout(async () => {
        switch (newService) {
          case 'kokoro-tts': {
            // 并行加载英文和中文音色
            await Promise.all([
              loadTtsVoices(),
              loadKokoroVoicesZh()
            ])
            const voice = ttsVoice.value
            if (voice && !ttsVoices.value.some(v => v.id === voice)) {
              ttsVoices.value.unshift({ id: voice, name: voice + ' (当前使用)' })
            }
            const voiceZh = ttsVoiceZh.value
            if (voiceZh && !kokoroVoicesZh.value.some(v => v.id === voiceZh)) {
              kokoroVoicesZh.value.unshift({ id: voiceZh, name: voiceZh + ' (当前使用)' })
            }
            break
          }
          case 'siliconflow-tts':
            // 硅基流动语音列表是静态的，无需加载
            break
          case 'edge-tts': {
            // 并行加载英文和中文音色
            await Promise.all([
              loadEdgeTtsVoices(),
              loadEdgeTtsVoicesZh()
            ])
            const voice = ttsVoice.value
            if (voice && !edgeTtsVoices.value.some(v => v.id === voice)) {
              edgeTtsVoices.value.unshift({ id: voice, name: formatEdgeTtsVoiceName(voice) + ' (当前使用)' })
            }
            const voiceZh = ttsVoiceZh.value
            if (voiceZh && !edgeTtsVoicesZh.value.some(v => v.id === voiceZh)) {
              edgeTtsVoicesZh.value.unshift({ id: voiceZh, name: voiceZh + ' (当前使用)' })
            }
            break
          }
          case 'minimax-tts': {
            // 并行加载英文和中文音色
            await Promise.all([
              loadMinimaxVoices(),
              loadMinimaxVoicesZh()
            ])
            const voice = ttsVoice.value
            if (voice && !minimaxVoices.value.some(v => v.id === voice)) {
              minimaxVoices.value.unshift({ id: voice, name: voice + ' (当前使用)' })
            }
            const voiceZh = ttsVoiceZh.value
            if (voiceZh && !minimaxVoicesZh.value.some(v => v.id === voiceZh)) {
              minimaxVoicesZh.value.unshift({ id: voiceZh, name: voiceZh + ' (当前使用)' })
            }
            break
          }
          case 'azure-tts': {
            // 并行加载英文和中文音色
            await Promise.all([
              loadAzureVoices(),
              loadAzureVoicesZh()
            ])
            const voice = ttsVoice.value
            if (voice && !azureVoices.value.some(v => v.id === voice)) {
              azureVoices.value.unshift({ id: voice, name: voice + ' (当前使用)' })
            }
            const voiceZh = ttsVoiceZh.value
            if (voiceZh && !azureVoicesZh.value.some(v => v.id === voiceZh)) {
              azureVoicesZh.value.unshift({ id: voiceZh, name: voiceZh + ' (当前使用)' })
            }
            break
          }
          default: // doubao-tts 语音列表是静态的，无需加载
            break
        }
      }, 0)
    }
  })

  // ========== 监听对话框打开，只在打开时才加载语音列表 ==========
  watch(showTtsSettingsDialog, async (isOpen) => {
    if (isOpen) {
      // 对话框打开时，延迟加载语音列表
      setTimeout(async () => {
        switch (ttsServiceName.value) {
          case 'kokoro-tts': {
            // 并行加载英文和中文音色
            const [voiceList] = await Promise.all([
              loadTtsVoices(),
              loadKokoroVoicesZh()
            ])
            const voice = ttsVoice.value
            if (voice && !ttsVoices.value.some(v => v.id === voice)) {
              ttsVoices.value.unshift({ id: voice, name: voice + ' (当前使用)' })
            }
            const voiceZh = ttsVoiceZh.value
            if (voiceZh && !kokoroVoicesZh.value.some(v => v.id === voiceZh)) {
              kokoroVoicesZh.value.unshift({ id: voiceZh, name: voiceZh + ' (当前使用)' })
            }
            break
          }
          case 'siliconflow-tts':
            // 硅基流动语音列表是静态的，无需加载
            break
          case 'edge-tts': {
            // 并行加载英文和中文音色
            await Promise.all([
              loadEdgeTtsVoices(),
              loadEdgeTtsVoicesZh()
            ])
            const voice = ttsVoice.value
            if (voice && !edgeTtsVoices.value.some(v => v.id === voice)) {
              edgeTtsVoices.value.unshift({ id: voice, name: formatEdgeTtsVoiceName(voice) + ' (当前使用)' })
            }
            const voiceZh = ttsVoiceZh.value
            if (voiceZh && !edgeTtsVoicesZh.value.some(v => v.id === voiceZh)) {
              edgeTtsVoicesZh.value.unshift({ id: voiceZh, name: voiceZh + ' (当前使用)' })
            }
            break
          }
          case 'minimax-tts': {
            // 并行加载英文和中文音色
            await Promise.all([
              loadMinimaxVoices(),
              loadMinimaxVoicesZh()
            ])
            const voice = ttsVoice.value
            if (voice && !minimaxVoices.value.some(v => v.id === voice)) {
              minimaxVoices.value.unshift({ id: voice, name: voice + ' (当前使用)' })
            }
            const voiceZh = ttsVoiceZh.value
            if (voiceZh && !minimaxVoicesZh.value.some(v => v.id === voiceZh)) {
              minimaxVoicesZh.value.unshift({ id: voiceZh, name: voiceZh + ' (当前使用)' })
            }
            break
          }
          case 'azure-tts': {
            // 并行加载英文和中文音色
            await Promise.all([
              loadAzureVoices(),
              loadAzureVoicesZh()
            ])
            const voice = ttsVoice.value
            if (voice && !azureVoices.value.some(v => v.id === voice)) {
              azureVoices.value.unshift({ id: voice, name: voice + ' (当前使用)' })
            }
            const voiceZh = ttsVoiceZh.value
            if (voiceZh && !azureVoicesZh.value.some(v => v.id === voiceZh)) {
              azureVoicesZh.value.unshift({ id: voiceZh, name: voiceZh + ' (当前使用)' })
            }
            break
          }
          default: // doubao-tts 语音列表是静态的，无需加载
            break
        }
      }, 100) // 延迟100ms确保对话框动画开始
    }
  })

  return {
    // 状态
    showTtsSettingsDialog,
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
    ttsEdgeTtsVoice,
    ttsMinimaxApiKey,
    ttsMinimaxModel,
    ttsMinimaxSpeed,
    ttsAzureSubscriptionKey,
    ttsAzureRegion,
    ttsAzureVoice,
    ttsAzureVoiceZh,
    ttsAzureSpeed,
    defaultTtsConfig,
    ttsSettingsLoaded,  // 设置加载完成标志
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

    // 方法
    loadUserSettings,
    loadTtsVoices,
    formatEdgeTtsVoiceName,
    loadEdgeTtsVoices,
    loadMinimaxVoices,
    loadEdgeTtsVoicesZh,
    loadMinimaxVoicesZh,
    loadKokoroVoicesZh,
    loadAzureVoices,
    loadAzureVoicesZh,
    handleCheckMinimaxUsage,
    handleCheckAzureUsage,
    stopTtsTest,
    stopTtsTestZh,
    testTts,
    testTtsZh,
    validateTtsUrl,
    showTtsUrlHelp,
    saveTtsSettings,
    openTtsSettings,
  }
}
