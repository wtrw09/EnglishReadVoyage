/**
 * 词典/翻译设置 Composable
 * 集中管理所有词典和翻译相关的状态和方法
 */
import { ref } from 'vue'
import { showNotify, showToast, showConfirmDialog } from 'vant'
import { api } from '@/store/auth'
import type { TranslationApi } from '../types'

// 全局响应式状态（模块级别，所有组件共享）
const showDictionarySettingsDialog = ref(false)
// 设置页面的词典来源（对应 database 的 dictionary_source 字段）
const dictionarySource = ref('local')
// 词典查询页面的词典来源（对应 database 的 dictionary_page_source 字段）
// 这是独立的，与 dictionarySource 互不影响
const dictionaryPageSource = ref('local')
const ecdictAvailable = ref(false)
const dictionarySettingsLoaded = ref(false)

export const useDictionarySettings = () => {
  // ========== 词典设置弹窗 ==========

  // ========== 音标设置弹窗 ==========

  const showPhoneticSettingsDialog = ref(false)

  // 音标口音
  const phoneticAccent = ref('uk')

  // ========== 翻译API相关 ==========

  const translationApis = ref<TranslationApi[]>([])
  const selectedTranslationApiId = ref<number | null>(null)
  const newBaiduAppId = ref('')
  const newBaiduAppKey = ref('')

  // ========== 方法 ==========

  /**
   * 加载词典状态
   */
  const loadDictionaryStatus = async () => {
    try {
      const res = await api.get('/dictionary/status')
      ecdictAvailable.value = res.data.ecdict_available
      // 并行加载词典设置和翻译API，减少加载时间
      await Promise.all([
        loadDictionarySettings(),
        loadTranslationSettings()
      ])
      dictionarySettingsLoaded.value = true  // 标记为已加载
    } catch (error) {
      console.error('loadDictionaryStatus 失败:', error)
      // 即使失败也尝试加载其他设置
      await Promise.all([
        loadDictionarySettings(),
        loadTranslationSettings()
      ])
      dictionarySettingsLoaded.value = true  // 标记为已加载
    }
  }

  /**
   * 加载用户词典设置（轻量级）
   * 同时加载 dictionary_source 和 dictionary_page_source
   */
  const loadDictionarySettings = async () => {
    try {
      const res = await api.get('/settings/dictionary')
      // 设置页面的词典来源（dictionary_source）
      dictionarySource.value = res.data.dictionary_source || 'local'
      // 词典查询页面的词典来源（dictionary_page_source）
      dictionaryPageSource.value = res.data.dictionary_page_source || 'local'
    } catch (error) {
      console.error('loadDictionarySettings 失败:', error)
      // 使用默认值
      dictionarySource.value = 'local'
      dictionaryPageSource.value = 'local'
    }
  }

  /**
   * 保存设置页面的词典设置（dictionary_source）
   */
  const saveDictionarySettings = async () => {
    console.log('saveDictionarySettings 被调用，dictionarySource:', dictionarySource.value)

    // 如果选择韦氏词典，需要检查是否已配置 API Key
    if (dictionarySource.value === 'merriam-webster') {
      try {
        const res = await api.get('/merriam-webster/settings')
        if (!res.data.configured) {
          showNotify({
            type: 'warning',
            message: '韦氏词典需要管理员先配置 API Key',
            duration: 2000
          })
          return
        }
      } catch (error: any) {
        showNotify({
          type: 'warning',
          message: '韦氏词典需要管理员先配置 API Key',
          duration: 2000
        })
        return
      }
    }

    try {
      // 只保存 dictionary_source，不影响 dictionary_page_source
      const payload: any = {
        dictionary_source: dictionarySource.value
      }

      const response = await api.put('/settings/dictionary', payload)
      console.log('保存词典设置成功:', response.data)
      showNotify({ type: 'success', message: '词典设置已保存', duration: 1500 })
      showDictionarySettingsDialog.value = false
    } catch (error: any) {
      console.error('保存词典设置失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
    }
  }

  /**
   * 保存词典查询页面的词典设置（dictionary_page_source）
   */
  const saveDictionaryPageSettings = async () => {
    console.log('saveDictionaryPageSettings 被调用，dictionaryPageSource:', dictionaryPageSource.value)

    // 如果选择韦氏词典，需要检查是否已配置 API Key
    if (dictionaryPageSource.value === 'merriam-webster') {
      try {
        const res = await api.get('/merriam-webster/settings')
        if (!res.data.configured) {
          showNotify({
            type: 'warning',
            message: '韦氏词典需要管理员先配置 API Key',
            duration: 2000
          })
          return
        }
      } catch (error: any) {
        showNotify({
          type: 'warning',
          message: '韦氏词典需要管理员先配置 API Key',
          duration: 2000
        })
        return
      }
    }

    try {
      const payload: any = {
        dictionary_page_source: dictionaryPageSource.value
      }

      const response = await api.put('/settings/dictionary', payload)
      console.log('保存词典页面设置成功:', response.data)
    } catch (error: any) {
      console.error('保存词典页面设置失败:', error)
    }
  }

  /**
   * 保存音标设置
   */
  const savePhoneticSettings = async () => {
    try {
      await api.put('/settings/phonetic', {
        accent: phoneticAccent.value
      })
      showNotify({ type: 'success', message: '音标设置已保存', duration: 1500 })
      showPhoneticSettingsDialog.value = false
    } catch (error: any) {
      console.error('保存音标设置失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
    }
  }

  /**
   * 加载翻译设置
   */
  const loadTranslationSettings = async () => {
    try {
      const res = await api.get('/translation/settings')
      selectedTranslationApiId.value = res.data.selected_api_id
      translationApis.value = res.data.apis || []
    } catch (error) {
      console.error('loadTranslationSettings 失败:', error)
    }
  }

  /**
   * 添加百度翻译API
   */
  const addBaiduApi = async () => {
    if (!newBaiduAppId.value || !newBaiduAppKey.value) {
      showToast('请填写APP ID和APP Key')
      return
    }

    try {
      await api.post('/translation/apis', {
        name: '百度翻译',
        app_id: newBaiduAppId.value,
        app_key: newBaiduAppKey.value,
        is_active: true
      })
      showNotify({ type: 'success', message: '百度翻译API已添加', duration: 1500 })
      newBaiduAppId.value = ''
      newBaiduAppKey.value = ''
      // 自动选中新添加的API
      await loadTranslationSettings()
      if (translationApis.value.length > 0) {
        await saveSelectedTranslationApi(translationApis.value[0].id)
      }
    } catch (error: any) {
      console.error('添加翻译API失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '添加失败' })
    }
  }

  /**
   * 保存选中的翻译API
   */
  const saveSelectedTranslationApi = async (apiId: number | null) => {
    try {
      await api.put('/translation/select', null, {
        params: { api_id: apiId }
      })
      selectedTranslationApiId.value = apiId
    } catch (error: any) {
      console.error('切换翻译API失败:', error)
    }
  }

  /**
   * 更新翻译API启用状态
   */
  const saveTranslationApi = async () => {
    if (translationApis.value.length === 0) return

    try {
      await api.put(`/translation/apis/${translationApis.value[0].id}`, {
        name: '百度翻译',
        app_id: translationApis.value[0].app_id,
        app_key: '', // 不更新app_key
        is_active: translationApis.value[0].is_active
      })
    } catch (error: any) {
      console.error('更新翻译API失败:', error)
    }
  }

  /**
   * 删除翻译API
   */
  const deleteTranslationApi = async (apiId: number) => {
    try {
      await showConfirmDialog({
        title: '确认删除',
        message: '确定要删除百度翻译API吗？'
      })
      await api.delete(`/translation/apis/${apiId}`)
      showNotify({ type: 'success', message: '翻译API已删除', duration: 1500 })
      await loadTranslationSettings()
    } catch (error: any) {
      if (error !== 'cancel') {
        console.error('删除翻译API失败:', error)
        showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
      }
    }
  }

  /**
   * 打开词典设置弹窗
   */
  const openDictionarySettings = async () => {
    // 重新加载词典状态和翻译设置，确保组件获取最新数据
    await Promise.all([
      loadDictionaryStatus(),
      loadTranslationSettings()
    ])
    showDictionarySettingsDialog.value = true
  }

  return {
    // 词典设置（设置页面用）
    showDictionarySettingsDialog,
    dictionarySource,
    // 词典查询页面专用词典
    dictionaryPageSource,
    ecdictAvailable,
    loadDictionaryStatus,
    loadDictionarySettings,
    saveDictionarySettings,
    saveDictionaryPageSettings,
    openDictionarySettings,

    // 音标设置
    showPhoneticSettingsDialog,
    phoneticAccent,
    savePhoneticSettings,

    // 翻译API
    translationApis,
    selectedTranslationApiId,
    newBaiduAppId,
    newBaiduAppKey,
    loadTranslationSettings,
    addBaiduApi,
    saveSelectedTranslationApi,
    saveTranslationApi,
    deleteTranslationApi,
    dictionarySettingsLoaded,  // 设置加载完成标志
  }
}
