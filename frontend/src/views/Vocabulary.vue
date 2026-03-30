<template>
  <div class="vocabulary-page">
    <!-- 顶部导航栏 -->
    <van-nav-bar
      title="生词本"
      left-text="返回"
      left-arrow
      fixed
      placeholder
      @click-left="goBack"
    >
      <template #right>
        <i class="fas fa-right-left" size="20" @click="openMemoryMode" style="margin-right: 12px; cursor: pointer; color: #333;"></i>
        <i class="fas fa-download" size="20" @click="openExportDialog" style="cursor: pointer; color: #333;"></i>
      </template>
    </van-nav-bar>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <van-loading type="spinner" size="24px" />
      <span>加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="vocabularyList.length === 0" class="empty-container">
      <i class="fas fa-clipboard-list" style="font-size: 48px; color: #ccc;"></i>
      <p>暂无生词</p>
      <p class="empty-tip">在阅读时长按单词查词，点击"加入生词本"即可添加</p>
    </div>

    <!-- 生词列表 -->
    <div v-else class="vocabulary-list">
      <van-swipe-cell
        v-for="item in vocabularyList"
        :key="item.id"
        class="vocabulary-item"
      >
        <div class="word-card"
             :class="{ 'has-checkbox': isMultiSelect }"
             @click="handleWordClick(item)"
             @contextmenu.prevent="confirmDelete(item)"
             @longpress="confirmDelete(item)">
          <!-- 多选复选框 -->
          <div v-if="isMultiSelect" class="word-checkbox" @click.stop>
            <input type="checkbox" :checked="selectedWords.includes(item.id)" @change="toggleWordSelect(item.id)" />
          </div>
          <div class="word-header">
            <span class="word-text">{{ item.word }}</span>
            <span v-if="item.phonetic" class="word-phonetic">{{ item.phonetic }}</span>
          </div>
          <div class="word-sentence" v-if="item.sentence">
            {{ item.sentence }}
          </div>
        </div>

        <!-- 左滑删除 -->
        <template #right>
          <van-button
            square
            type="danger"
            text="删除"
            class="delete-btn"
            @click="deleteVocabulary(item.id)"
          />
        </template>
      </van-swipe-cell>
    </div>

    <!-- 生词详情弹窗 -->
    <van-popup
      v-model:show="showDetailDialog"
      position="bottom"
      round
      :style="{ maxHeight: '70%' }"
    >
      <div class="detail-popup-header">
        <span class="detail-popup-title">{{ selectedWord?.word }}<i 
          class="fas fa-volume-up detail-speak-btn"
          :class="{ 'speaking': isSpeaking }"
          @click="speakWord"
        ></i></span>
        <i class="fas fa-xmark detail-popup-close" @click="showDetailDialog = false" style="font-size: 20px; color: #999; cursor: pointer; padding: 4px;"></i>
      </div>
      <div class="word-detail" v-if="selectedWord">
        <div class="detail-section" v-if="selectedWord.phonetic">
          <div class="detail-label">音标</div>
          <div class="detail-phonetic">{{ selectedWord.phonetic }}</div>
        </div>

        <div class="detail-section" v-if="selectedWord.translation">
          <div class="detail-label">中文释义</div>
          <div class="detail-translation">{{ selectedWord.translation }}</div>
        </div>

        <div class="detail-section" v-if="selectedWord.sentence">
          <div class="detail-label">所在句子</div>
          <div class="detail-sentence">{{ selectedWord.sentence }}</div>
        </div>

        <div class="detail-section" v-if="selectedWord.book_name">
          <div class="detail-label">来源书籍</div>
          <div class="detail-book">
            <i class="fas fa-bookmark"></i>
            <span>{{ selectedWord.book_name }}</span>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-label">添加时间</div>
          <div class="detail-date">{{ formatDateTime(selectedWord.created_at) }}</div>
        </div>
      </div>
    </van-popup>

    <!-- 右键删除菜单 -->
    <van-popup
      v-model:show="showDeleteMenu"
      :style="{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }"
      round
      class="context-menu"
    >
      <van-cell-group>
        <van-cell title="选择更多" clickable @click="enableMultiSelect" v-if="!isMultiSelect" />
        <van-cell title="添加记忆" clickable @click="openMemoryForItem" />
        <van-cell title="删除" clickable @click="onDeleteSelect" />
      </van-cell-group>
    </van-popup>

    <!-- 批量操作栏 -->
    <div v-if="isMultiSelect" class="batch-actions">
      <van-button type="primary" size="small" plain @click="selectAllWords">
        {{ isAllSelected ? '取消全选' : '全选' }}
      </van-button>
      <van-button type="warning" size="small" @click="openBatchMemoryMode" :disabled="selectedWords.length === 0">
        添加记忆
      </van-button>
      <van-button type="danger" size="small" @click="batchDeleteWords" :disabled="selectedWords.length === 0">
        删除 ({{ selectedWords.length }})
      </van-button>
    </div>

    <!-- 选择记忆模式弹窗 -->
    <van-popup
      v-model:show="showMemoryModeSelect"
      position="bottom"
      round
    >
      <div class="memory-mode-select-popup">
        <div class="memory-mode-select-title">选择记忆模式</div>
        <van-radio-group v-model="tempMemoryMode">
          <van-cell-group inset>
            <van-cell title="记英文（显示中文）" clickable @click="tempMemoryMode = 'english'">
              <template #right-icon>
                <van-radio name="english" />
              </template>
            </van-cell>
            <van-cell title="记中文（显示英文）" clickable @click="tempMemoryMode = 'chinese'">
              <template #right-icon>
                <van-radio name="chinese" />
              </template>
            </van-cell>
          </van-cell-group>
        </van-radio-group>
        <div class="memory-mode-select-btns">
          <van-button @click="showMemoryModeSelect = false">取消</van-button>
          <van-button type="primary" @click="confirmMemoryMode">确定</van-button>
        </div>
      </div>
    </van-popup>

    <!-- 记忆模式弹窗 -->
    <van-popup
      v-model:show="showMemoryDialog"
      position="bottom"
      round
      :style="{ maxHeight: '80%' }"
    >
      <div class="memory-popup-header">
        <span class="memory-popup-title">记忆模式</span>
        <i class="fas fa-xmark memory-popup-close" @click="showMemoryDialog = false" style="font-size: 20px; color: #999; cursor: pointer; padding: 4px;"></i>
      </div>

      <!-- 选择单词 -->
      <div v-if="!memoryModeStarted" class="memory-select">
        <div class="memory-select-header">
          <p class="memory-tip">请先选择要练习的单词</p>
          <van-button size="small" type="primary" plain @click="selectAllMemoryWords">
            {{ isAllMemorySelected ? '取消全选' : '全选' }}
          </van-button>
        </div>
        <van-checkbox-group v-model="memorySelectedIds">
          <van-cell-group inset>
            <van-cell
              v-for="item in vocabularyList"
              :key="item.id"
              clickable
              @click="toggleMemorySelect(item.id)"
            >
              <template #title>
                <span>{{ item.word }}</span>
              </template>
              <template #right-icon>
                <van-checkbox
                  :name="item.id"
                  shape="square"
                  @click="toggleMemorySelect(item.id)"
                />
              </template>
            </van-cell>
          </van-cell-group>
        </van-checkbox-group>

        <div class="memory-mode-select">
          <p class="memory-tip">选择记忆模式</p>
          <van-radio-group v-model="memoryMode">
            <van-cell-group inset>
              <van-cell title="记英文" clickable @click="memoryMode = 'english'">
                <template #right-icon>
                  <van-radio name="english" />
                </template>
              </van-cell>
              <van-cell title="记中文" clickable @click="memoryMode = 'chinese'">
                <template #right-icon>
                  <van-radio name="chinese" />
                </template>
              </van-cell>
            </van-cell-group>
          </van-radio-group>
        </div>

        <div class="memory-start-btn">
          <van-button
            type="primary"
            block
            :disabled="memorySelectedIds.length === 0"
            @click="startMemoryMode"
          >
            开始练习
          </van-button>
        </div>
      </div>

      <!-- 记忆练习界面 -->
      <div v-else class="memory-practice">
        <div class="memory-progress">
          {{ currentMemoryIndex + 1 }} / {{ memorySelectedVocab.length }}
        </div>

        <!-- 记忆卡片 -->
        <div
          class="memory-card"
          @touchstart="onCardTouchStart"
          @touchend="onCardTouchEnd"
          @mousedown="onCardMouseDown"
          @mouseup="onCardMouseUp"
          @mouseleave="onCardMouseLeave"
        >
          <div class="memory-card-content">
            <!-- 记英文模式：显示中文，隐藏英文 -->
            <template v-if="memoryMode === 'english'">
              <div class="memory-translation">{{ currentMemoryVocab?.translation || '' }}</div>
              <div
                class="memory-word"
                :class="{ hidden: !showMemoryContent }"
              >
                {{ currentMemoryVocab?.word || '' }}
              </div>
              <div v-if="!showMemoryContent" class="memory-hint">长按显示英文</div>
              <div v-if="showMemoryContent" class="memory-hint">松开隐藏英文</div>
            </template>

            <!-- 记中文模式：显示英文，隐藏中文 -->
            <template v-else>
              <div class="memory-word">{{ currentMemoryVocab?.word || '' }}</div>
              <div
                class="memory-translation"
                :class="{ hidden: !showMemoryContent }"
              >
                {{ currentMemoryVocab?.translation || '' }}
              </div>
              <div v-if="!showMemoryContent" class="memory-hint">长按显示中文</div>
              <div v-if="showMemoryContent" class="memory-hint">松开隐藏中文</div>
            </template>
          </div>
        </div>

        <!-- 取消按钮 -->
        <div class="memory-cancel" v-if="showMemoryContent">
          <van-button type="default" size="small" @click="hideMemoryContent">
            取消（隐藏答案）
          </van-button>
        </div>

        <!-- 导航按钮 -->
        <div class="memory-nav">
          <van-button
            @click="prevMemoryCard"
          >
            <i class="fas fa-arrow-left" />
          </van-button>
          <van-button type="primary" @click="exitMemoryMode">
            退出
          </van-button>
          <van-button
            @click="nextMemoryCard"
          >
            <i class="fas fa-arrow-right" />
          </van-button>
        </div>
      </div>
    </van-popup>

    <!-- 导出Word弹窗 -->
    <van-popup
      v-model:show="showExportDialog"
      position="bottom"
      round
      :style="{ maxHeight: '60%' }"
    >
      <div class="export-popup-header">
        <span class="export-popup-title">导出Word文档</span>
        <i class="fas fa-xmark export-popup-close" @click="showExportDialog = false" style="font-size: 20px; color: #999; cursor: pointer; padding: 4px;"></i>
      </div>

      <div class="export-content">
        <div class="export-select-header">
          <p class="export-tip">请先选择要导出的单词</p>
          <van-button size="small" type="primary" plain @click="selectAllExportWords">
            {{ isAllExportSelected ? '取消全选' : '全选' }}
          </van-button>
        </div>
        <van-checkbox-group v-model="exportSelectedIds">
          <van-cell-group inset>
            <van-cell
              v-for="item in vocabularyList"
              :key="item.id"
              clickable
              @click="toggleExportSelect(item.id)"
            >
              <template #title>
                <span>{{ item.word }}</span>
              </template>
              <template #right-icon>
                <van-checkbox
                  :name="item.id"
                  shape="square"
                  @click="toggleExportSelect(item.id)"
                />
              </template>
            </van-cell>
          </van-cell-group>
        </van-checkbox-group>

        <p class="export-tip">选择要默写的字段（默写用）</p>
        <van-checkbox-group v-model="exportHiddenFields">
          <van-cell-group inset>
            <van-cell title="英文单词" clickable @click="toggleHiddenField('word')">
              <template #right-icon>
                <van-checkbox name="word" shape="square" @click="toggleHiddenField('word')" />
              </template>
            </van-cell>
            <van-cell title="音标" clickable @click="toggleHiddenField('phonetic')">
              <template #right-icon>
                <van-checkbox name="phonetic" shape="square" @click="toggleHiddenField('phonetic')" />
              </template>
            </van-cell>
            <van-cell title="中文翻译" clickable @click="toggleHiddenField('translation')">
              <template #right-icon>
                <van-checkbox name="translation" shape="square" @click="toggleHiddenField('translation')" />
              </template>
            </van-cell>
          </van-cell-group>
        </van-checkbox-group>

        <div class="export-btn">
          <van-button
            type="primary"
            block
            :disabled="exportSelectedIds.length === 0"
            :loading="exportLoading"
            @click="exportToWord"
          >
            导出Word文档
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { api } from '@/store/auth'

interface VocabularyItem {
  id: number
  word: string
  phonetic?: string
  translation?: string
  sentence?: string
  book_name?: string
  created_at: string
}

const router = useRouter()
const loading = ref(true)
const vocabularyList = ref<VocabularyItem[]>([])
const showDetailDialog = ref(false)
const selectedWord = ref<VocabularyItem | null>(null)
const showDeleteMenu = ref(false)
const deleteItemId = ref<number | null>(null)

// 朗读相关状态
const isSpeaking = ref(false)  // 朗读状态
let currentWordAudio: HTMLAudioElement | null = null  // 当前播放音频

// 多选模式相关
const isMultiSelect = ref(false)
const selectedWords = ref<number[]>([])

// 记忆模式相关
const showMemoryDialog = ref(false)
const showMemoryModeSelect = ref(false)
const memoryModeStarted = ref(false)
const memorySelectedIds = ref<number[]>([])
const memoryMode = ref<'english' | 'chinese'>('chinese')
const tempMemoryMode = ref<'english' | 'chinese'>('chinese')
const currentMemoryIndex = ref(0)
const showMemoryContent = ref(false)
const memoryLongPressTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const isFromBatch = ref(false) // 标记是否来自批量选择

// 导出Word相关
const showExportDialog = ref(false)
const exportSelectedIds = ref<number[]>([])
const exportHiddenFields = ref<string[]>(['word', 'translation'])
const exportLoading = ref(false)

// 判断导出是否全选
const isAllExportSelected = computed(() => {
  return vocabularyList.value.length > 0 && exportSelectedIds.value.length === vocabularyList.value.length
})

// 全选/取消全选导出单词
const selectAllExportWords = () => {
  if (isAllExportSelected.value) {
    exportSelectedIds.value = []
  } else {
    exportSelectedIds.value = vocabularyList.value.map(item => item.id)
  }
}

// 计算是否全选
const isAllSelected = computed(() => {
  return vocabularyList.value.length > 0 && selectedWords.value.length === vocabularyList.value.length
})

// 返回上一页
const goBack = () => {
  router.back()
}

// 加载生词列表
const loadVocabulary = async () => {
  loading.value = true
  try {
    const res = await api.get('/vocabulary/')
    vocabularyList.value = res.data.items || []
  } catch (error) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

// 显示生词详情
const showWordDetail = (item: VocabularyItem) => {
  selectedWord.value = item
  showDetailDialog.value = true
}

// 朗读单词（使用有道词典发音）
const speakWord = async () => {
  if (!selectedWord.value?.word) return

  if (isSpeaking.value) {
    // 停止播放
    if (currentWordAudio) {
      currentWordAudio.pause()
      currentWordAudio.currentTime = 0
      currentWordAudio = null
    }
    isSpeaking.value = false
    return
  }

  isSpeaking.value = true
  try {
    // 调用发音API获取音频URL
    const res = await api.get<{ audio_url: string | null }>(`/pronunciation/${encodeURIComponent(selectedWord.value.word)}`)
    
    if (res.data.audio_url) {
      currentWordAudio = new Audio(res.data.audio_url)
      currentWordAudio.play()
      currentWordAudio.onended = () => {
        isSpeaking.value = false
        currentWordAudio = null
      }
      currentWordAudio.onerror = () => {
        isSpeaking.value = false
        currentWordAudio = null
        showToast('播放失败')
      }
    } else {
      isSpeaking.value = false
      showToast('未找到发音')
    }
  } catch (error) {
    console.error('朗读失败:', error)
    isSpeaking.value = false
    showToast('朗读失败')
  }
}

// 确认删除（右键菜单）
const confirmDelete = (item: VocabularyItem) => {
  deleteItemId.value = item.id
  showDeleteMenu.value = true
}

// 右键菜单选择删除
const onDeleteSelect = () => {
  if (deleteItemId.value !== null) {
    deleteVocabulary(deleteItemId.value)
    showDeleteMenu.value = false
  }
}

// 删除生词
const deleteVocabulary = async (id: number) => {
  try {
    await api.delete(`/vocabulary/${id}`)
    showToast('已删除')
    // 重新加载列表
    loadVocabulary()
  } catch (error) {
    showToast('删除失败')
  }
}

// 格式化日期时间
const formatDateTime = (dateStr: string) => {
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

// 处理单词点击
const handleWordClick = (item: VocabularyItem) => {
  if (isMultiSelect.value) {
    toggleWordSelect(item.id)
  } else {
    showWordDetail(item)
  }
}

// 进入多选模式
const enableMultiSelect = () => {
  isMultiSelect.value = true
  showDeleteMenu.value = false
}

// 退出多选模式
const disableMultiSelect = () => {
  isMultiSelect.value = false
  selectedWords.value = []
}

// 切换选择状态
const toggleWordSelect = (id: number) => {
  const index = selectedWords.value.indexOf(id)
  if (index === -1) {
    selectedWords.value.push(id)
  } else {
    selectedWords.value.splice(index, 1)
  }
}

// 全选/取消全选
const selectAllWords = () => {
  if (isAllSelected.value) {
    selectedWords.value = []
  } else {
    selectedWords.value = vocabularyList.value.map(item => item.id)
  }
}

// 批量删除
const batchDeleteWords = async () => {
  if (selectedWords.value.length === 0) return
  try {
    await api.post('/vocabulary/batch-delete', { ids: selectedWords.value })
    showToast(`已删除 ${selectedWords.value.length} 个单词`)
    disableMultiSelect()
    loadVocabulary()
  } catch (error) {
    showToast('删除失败')
  }
}

// ============ 记忆模式相关函数 ============

// 打开记忆模式弹窗
const openMemoryMode = () => {
  memorySelectedIds.value = []
  memoryMode.value = 'chinese'
  memoryModeStarted.value = false
  currentMemoryIndex.value = 0
  showMemoryContent.value = false
  showMemoryDialog.value = true
}

// 切换记忆模式单词选择
const toggleMemorySelect = (id: number) => {
  const index = memorySelectedIds.value.indexOf(id)
  if (index === -1) {
    memorySelectedIds.value.push(id)
  } else {
    memorySelectedIds.value.splice(index, 1)
  }
}

// 判断是否全选了所有单词
const isAllMemorySelected = computed(() => {
  return vocabularyList.value.length > 0 && memorySelectedIds.value.length === vocabularyList.value.length
})

// 全选/取消全选记忆模式单词
const selectAllMemoryWords = () => {
  if (isAllMemorySelected.value) {
    memorySelectedIds.value = []
  } else {
    memorySelectedIds.value = vocabularyList.value.map(item => item.id)
  }
}

// 获取选中的生词列表
const memorySelectedVocab = computed(() => {
  return vocabularyList.value.filter(item => memorySelectedIds.value.includes(item.id))
})

// 当前显示的生词
const currentMemoryVocab = computed(() => {
  return memorySelectedVocab.value[currentMemoryIndex.value] || null
})

// 开始记忆模式
const startMemoryMode = () => {
  if (memorySelectedIds.value.length === 0) return
  memoryModeStarted.value = true
  currentMemoryIndex.value = 0
  showMemoryContent.value = false
}

// 退出记忆模式
const exitMemoryMode = () => {
  memoryModeStarted.value = false
  showMemoryContent.value = false
}

// 上一张卡片
const prevMemoryCard = () => {
  if (currentMemoryIndex.value > 0) {
    currentMemoryIndex.value--
    showMemoryContent.value = false
  }
}

// 下一张卡片
const nextMemoryCard = () => {
  if (currentMemoryIndex.value < memorySelectedVocab.value.length - 1) {
    currentMemoryIndex.value++
    showMemoryContent.value = false
  }
}

// 长按显示内容 - 触摸开始
const onCardTouchStart = () => {
  memoryLongPressTimer.value = setTimeout(() => {
    showMemoryContent.value = true
  }, 100)
}

// 长按显示内容 - 触摸结束
const onCardTouchEnd = () => {
  if (memoryLongPressTimer.value) {
    clearTimeout(memoryLongPressTimer.value)
    memoryLongPressTimer.value = null
  }
}

// 长按显示内容 - 鼠标按下
const onCardMouseDown = () => {
  memoryLongPressTimer.value = setTimeout(() => {
    showMemoryContent.value = true
  }, 100)
}

// 长按显示内容 - 鼠标释放
const onCardMouseUp = () => {
  if (memoryLongPressTimer.value) {
    clearTimeout(memoryLongPressTimer.value)
    memoryLongPressTimer.value = null
  }
  // 鼠标松开时隐藏内容
  showMemoryContent.value = false
}

// 鼠标离开卡片时隐藏内容
const onCardMouseLeave = () => {
  showMemoryContent.value = false
}

// 隐藏记忆内容
const hideMemoryContent = async () => {
  // 获取当前单词ID
  const currentWordId = currentMemoryVocab.value?.id
  showMemoryContent.value = false
  exitMemoryMode()
  showMemoryDialog.value = false

  // 如果有当前单词ID，删除它
  if (currentWordId) {
    try {
      await api.delete(`/vocabulary/${currentWordId}`)
      showToast('已删除')
      loadVocabulary()
    } catch (error) {
      showToast('删除失败')
    }
  }
}

// 为单个单词添加记忆
const openMemoryForItem = () => {
  showDeleteMenu.value = false
  memorySelectedIds.value = [deleteItemId.value!]
  tempMemoryMode.value = 'chinese'
  isFromBatch.value = false
  showMemoryModeSelect.value = true
}

// 批量添加记忆
const openBatchMemoryMode = () => {
  memorySelectedIds.value = [...selectedWords.value]
  tempMemoryMode.value = 'chinese'
  isFromBatch.value = true
  showMemoryModeSelect.value = true
}

// 确认记忆模式
const confirmMemoryMode = () => {
  memoryMode.value = tempMemoryMode.value
  memoryModeStarted.value = true
  currentMemoryIndex.value = 0
  showMemoryContent.value = false
  showMemoryModeSelect.value = false
  showMemoryDialog.value = true

  // 如果不是来自批量选择，关闭多选模式
  if (!isFromBatch.value) {
    disableMultiSelect()
  }
}

// ============ 导出Word相关函数 ============

// 打开导出弹窗
const openExportDialog = () => {
  exportSelectedIds.value = []
  exportHiddenFields.value = ['word', 'translation']
  exportLoading.value = false
  showExportDialog.value = true
}

// 切换导出单词选择
const toggleExportSelect = (id: number) => {
  const index = exportSelectedIds.value.indexOf(id)
  if (index === -1) {
    exportSelectedIds.value.push(id)
  } else {
    exportSelectedIds.value.splice(index, 1)
  }
}

// 切换隐藏字段
const toggleHiddenField = (field: string) => {
  const index = exportHiddenFields.value.indexOf(field)
  if (index === -1) {
    exportHiddenFields.value.push(field)
  } else {
    exportHiddenFields.value.splice(index, 1)
  }
}

// 导出Word文档
const exportToWord = async () => {
  if (exportSelectedIds.value.length === 0) return

  exportLoading.value = true
  try {
    const response = await api.post('/vocabulary/export', {
      ids: exportSelectedIds.value,
      hidden_fields: exportHiddenFields.value
    }, {
      responseType: 'blob'
    })

    // 创建下载链接
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `生词本_${new Date().toISOString().slice(0, 10)}.docx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    showToast('导出成功')
    showExportDialog.value = false
  } catch (error) {
    showToast('导出失败')
  } finally {
    exportLoading.value = false
  }
}

// 页面加载时获取数据
onMounted(() => {
  loadVocabulary()
})

// 监听详情弹窗关闭，停止朗读
watch(showDetailDialog, (newVal) => {
  if (!newVal && currentWordAudio) {
    currentWordAudio.pause()
    currentWordAudio.currentTime = 0
    currentWordAudio = null
    isSpeaking.value = false
  }
})
</script>

<style scoped>
.vocabulary-page {
  min-height: 100vh;
  background: #f7f8fa;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #999;
  gap: 12px;
}

.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #999;
}

.empty-container p {
  margin: 8px 0 0;
  font-size: 16px;
}

.empty-tip {
  font-size: 14px !important;
  color: #bbb;
  text-align: center;
  padding: 0 40px;
  margin-top: 12px !important;
}

.vocabulary-list {
  padding: 12px;
}

.vocabulary-item {
  margin-bottom: 8px;
}

.word-card {
  position: relative;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.word-card.has-checkbox {
  padding-left: 40px;
}

.word-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.word-text {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.word-phonetic {
  font-size: 14px;
  color: #666;
  font-family: 'Times New Roman', serif;
}

.word-sentence {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.word-date {
  font-size: 12px;
  color: #bbb;
}

.delete-btn {
  height: 100%;
}

/* 详情弹窗样式 */
.word-detail {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

/* 详情弹窗头部样式 */
.detail-popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.detail-popup-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.detail-popup-close {
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 4px;
}

.detail-popup-close:hover {
  color: #666;
}

.detail-speak-btn {
  margin-left: 4px;
  cursor: pointer;
  color: #1989fa;
  font-size: 18px;
  transition: all 0.3s;
}

.detail-speak-btn:hover {
  color: #1277d8;
}

.detail-speak-btn.speaking {
  color: #07c160;
  animation: speak-pulse 1s infinite;
}

@keyframes speak-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}

.detail-section {
  margin-bottom: 16px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 6px;
}

.detail-phonetic {
  font-size: 16px;
  color: #666;
  font-family: 'Times New Roman', serif;
}

.detail-translation {
  font-size: 15px;
  color: #333;
  line-height: 1.6;
}

.detail-sentence {
  font-size: 14px;
  color: #555;
  line-height: 1.6;
  padding: 10px;
  background: #f7f8fa;
  border-radius: 6px;
}

.detail-book {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #666;
}

.detail-date {
  font-size: 13px;
  color: #999;
}

/* 批量操作栏 */
.batch-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 12px 20px;
  background: #fff;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
  z-index: 100;
}

/* 多选复选框 */
.word-checkbox {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
}

.word-checkbox input {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

/* ============ 记忆模式样式 ============ */
.memory-popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.memory-popup-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.memory-popup-close {
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 4px;
}

.memory-select {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.memory-tip {
  font-size: 14px;
  color: #666;
  margin: 12px 0;
}

.memory-select-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
}

.memory-select-header .memory-tip {
  margin: 0;
}

.memory-mode-select {
  margin-top: 16px;
}

.memory-start-btn {
  margin: 20px 16px;
}

.memory-practice {
  padding: 20px;
}

.memory-progress {
  text-align: center;
  font-size: 14px;
  color: #999;
  margin-bottom: 20px;
}

.memory-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 40px 20px;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  user-select: none;
}

.memory-card-content {
  text-align: center;
}

.memory-word {
  font-size: 28px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 12px;
}

.memory-translation {
  font-size: 20px;
  color: #fff;
  margin-bottom: 12px;
}

.memory-word.hidden,
.memory-translation.hidden {
  filter: blur(8px);
}

.memory-hint {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 12px;
}

.memory-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 30px;
  padding: 0 20px;
}

.memory-nav .van-button {
  width: 80px;
}

.memory-cancel {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

/* 记忆模式选择弹窗 */
.memory-mode-select-popup {
  padding: 20px;
}

.memory-mode-select-title {
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 16px;
  color: #333;
}

.memory-mode-select-btns {
  display: flex;
  justify-content: space-around;
  margin-top: 20px;
}

/* ============ 导出Word样式 ============ */
.export-popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.export-popup-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.export-popup-close {
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 4px;
}

.export-content {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.export-tip {
  font-size: 14px;
  color: #666;
  margin: 12px 0;
}

.export-select-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  margin-bottom: 10px;
}

.export-select-header .export-tip {
  margin: 0;
  flex: 1;
}

.export-select-header .van-button {
  flex-shrink: 0;
  height: 32px;
  line-height: 32px;
}

.export-btn {
  margin: 20px 16px;
}
</style>
