<template>
  <div class="read-mode-content">
    <!-- 模式选择 -->
    <van-cell-group inset title="朗读模式">
      <van-cell
        title="英文→中文"
        description="英文×1 → 中文×1"
        is-link
        :class="{ 'active-preset': selectedPresetId === 'en1-zh1' && !isCustomMode }"
        @click="selectPreset('en1-zh1')"
      >
        <template #right-icon>
          <van-radio name="en1-zh1" :model-value="selectedPresetId === 'en1-zh1' && !isCustomMode" />
        </template>
      </van-cell>
      <van-cell
        title="英文→中文→英文"
        description="英文×1 → 中文×1 → 英文×1"
        is-link
        :class="{ 'active-preset': selectedPresetId === 'en1-zh1-en1' && !isCustomMode }"
        @click="selectPreset('en1-zh1-en1')"
      >
        <template #right-icon>
          <van-radio name="en1-zh1-en1" :model-value="selectedPresetId === 'en1-zh1-en1' && !isCustomMode" />
        </template>
      </van-cell>
      <van-cell
        title="英文×2→中文"
        description="英文×2 → 中文×1"
        is-link
        :class="{ 'active-preset': selectedPresetId === 'en2-zh1' && !isCustomMode }"
        @click="selectPreset('en2-zh1')"
      >
        <template #right-icon>
          <van-radio name="en2-zh1" :model-value="selectedPresetId === 'en2-zh1' && !isCustomMode" />
        </template>
      </van-cell>
      <van-cell
        title="仅英文"
        description="仅播放英文"
        is-link
        :class="{ 'active-preset': selectedPresetId === 'en-only' && !isCustomMode }"
        @click="selectPreset('en-only')"
      >
        <template #right-icon>
          <van-radio name="en-only" :model-value="selectedPresetId === 'en-only' && !isCustomMode" />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 自定义模式 -->
    <van-cell-group inset title="自定义模式">
      <div class="custom-segments">
        <div
          v-for="(segment, index) in customSegments"
          :key="index"
          class="segment-item"
        >
          <!-- 语言显示 -->
          <div class="segment-lang">
            <i :class="segment.lang === 'en' ? 'fas fa-file-lines' : 'fas fa-comment'"></i>
            <span>{{ segment.lang === 'en' ? '英文' : '中文' }}</span>
          </div>
          <!-- 重复次数 -->
          <div class="segment-count">
            <span>×</span>
            <van-stepper
              v-model="segment.count"
              :min="1"
              :max="5"
              integer
              size="small"
            />
          </div>
          <!-- 删除按钮 -->
          <i class="fas fa-xmark delete-btn" @click="removeSegment(index)" style="font-size: 16px; color: #999; cursor: pointer; padding: 4px;"></i>
        </div>
      </div>
      <!-- 添加按钮 -->
      <div class="add-segment-btns">
        <van-button
          class="add-btn"
          @click="addSegment('en')"
        >
          <i class="fas fa-plus" style="margin-right: 4px;"></i>
          添加英文
        </van-button>
        <van-button
          class="add-btn"
          type="warning"
          @click="addSegment('zh')"
        >
          <i class="fas fa-plus" style="margin-right: 4px;"></i>
          添加中文
        </van-button>
      </div>
      <div class="custom-tip">
        <i class="fas fa-info-circle" style="color: #969799;"></i>
        <span>点击启用自定义模式</span>
      </div>
    </van-cell-group>

    <!-- 当前模式预览 -->
    <van-cell-group inset title="当前模式预览">
      <div class="preview-display">
        <template v-for="(segment, index) in currentSegments" :key="index">
          <span
            class="preview-item"
            :class="segment.lang"
          >
            {{ segment.lang === 'en' ? 'EN' : 'ZH' }}
            <span v-if="segment.count > 1" class="count-badge">×{{ segment.count }}</span>
          </span>
          <span v-if="index < currentSegments.length - 1" class="preview-arrow">→</span>
        </template>
      </div>
      <div class="current-mode-name">
        {{ currentModeName }}
      </div>
    </van-cell-group>

    <!-- 说明 -->
    <div class="settings-tip">
      <i class="fas fa-info-circle" style="flex-shrink: 0;"></i>
      <span>朗读模式用于双语阅读时的语音播放顺序设置</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showNotify } from 'vant'
import { api } from '@/store/auth'

// 朗读段配置
interface ReadSegment {
  lang: 'en' | 'zh'
  count: number
}

// 朗读模式预设
interface ReadPreset {
  id: string
  name: string
  description: string
  segments: ReadSegment[]
}

// 朗读模式预设
const presets: ReadPreset[] = [
  {
    id: 'en1-zh1',
    name: '英文→中文',
    description: '英文×1 → 中文×1',
    segments: [
      { lang: 'en', count: 1 },
      { lang: 'zh', count: 1 }
    ]
  },
  {
    id: 'en1-zh1-en1',
    name: '英文→中文→英文',
    description: '英文×1 → 中文×1 → 英文×1',
    segments: [
      { lang: 'en', count: 1 },
      { lang: 'zh', count: 1 },
      { lang: 'en', count: 1 }
    ]
  },
  {
    id: 'en2-zh1',
    name: '英文×2→中文',
    description: '英文×2 → 中文×1',
    segments: [
      { lang: 'en', count: 2 },
      { lang: 'zh', count: 1 }
    ]
  },
  {
    id: 'en-only',
    name: '仅英文',
    description: '仅播放英文',
    segments: [
      { lang: 'en', count: 1 }
    ]
  }
]

// 状态
const selectedPresetId = ref('en1-zh1')
const customSegments = ref<ReadSegment[]>([
  { lang: 'en', count: 1 },
  { lang: 'zh', count: 1 }
])
const isCustomMode = ref(false)

// 当前模式名称
const currentModeName = computed(() => {
  if (isCustomMode.value) {
    return `自定义 (${customSegments.value.length}段)`
  }
  const preset = presets.find(p => p.id === selectedPresetId.value)
  return preset?.name || ''
})

// 当前朗读段
const currentSegments = computed(() => {
  if (isCustomMode.value) {
    return customSegments.value
  }
  const preset = presets.find(p => p.id === selectedPresetId.value)
  return preset?.segments || []
})

// 页面加载时获取当前设置
onMounted(async () => {
  await loadCurrentSettings()
})

// 加载当前设置
const loadCurrentSettings = async () => {
  try {
    const res = await api.get('/settings/')
    if (res.data?.tts?.read_preset_id) {
      const presetId = res.data.tts.read_preset_id
      const isPreset = presets.some(p => p.id === presetId)
      if (isPreset) {
        selectedPresetId.value = presetId
        isCustomMode.value = false
      } else if (res.data.tts?.read_segments) {
        customSegments.value = res.data.tts.read_segments
        isCustomMode.value = true
      }
    }
  } catch (error) {
    console.error('加载朗读模式设置失败:', error)
  }
}

// 选择预设
const selectPreset = (presetId: string) => {
  selectedPresetId.value = presetId
  isCustomMode.value = false
}

// 添加朗读段
const addSegment = (lang: 'en' | 'zh') => {
  customSegments.value.push({ lang, count: 1 })
  isCustomMode.value = true
}

// 删除朗读段
const removeSegment = (index: number) => {
  if (customSegments.value.length > 1) {
    customSegments.value.splice(index, 1)
  }
}

// 暴露保存方法
defineExpose({
  save: async () => {
    const requestBody: any = {
      read_preset_id: isCustomMode.value ? null : selectedPresetId.value,
      read_segments: isCustomMode.value ? customSegments.value : null
    }

    try {
      await api.put('/settings/tts', requestBody)
      showNotify({ type: 'success', message: '朗读模式已保存' })
    } catch (error: any) {
      console.error('保存朗读模式设置失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
      throw error
    }
  }
})
</script>

<style lang="less" scoped>
.read-mode-content {
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

.active-preset {
  background: #f0fff4;

  :deep(.van-cell__title) {
    color: #07c160;
  }
}

.custom-segments {
  padding: 12px 16px;
}

.segment-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f5f5f5;
  border-radius: 8px;
  margin-bottom: 8px;

  .segment-lang {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 500;
    color: #333;

    i {
      font-size: 18px;
      color: #666;
    }
  }

  .segment-count {
    display: flex;
    align-items: center;
    gap: 4px;

    span {
      font-size: 16px;
      font-weight: 600;
      color: #333;
    }
  }

  .delete-btn {
    font-size: 16px;
    color: #999;
    cursor: pointer;
    padding: 4px;

    &:active {
      color: #ee0a24;
    }
  }
}

.add-segment-btns {
  display: flex;
  gap: 12px;
  padding: 0 16px 12px;

  .add-btn {
    flex: 1;
    height: 40px;
    border-radius: 8px;
    font-size: 14px;
  }
}

.custom-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 12px;
  color: #969799;
  background: #f7f8fa;
}

.preview-display {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
  margin: 12px 16px;
}

.preview-item {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 600;

  &.en {
    background: #e6f7ff;
    color: #1890ff;
  }

  &.zh {
    background: #fff7e6;
    color: #fa8c16;
  }

  .count-badge {
    margin-left: 4px;
    font-size: 12px;
    opacity: 0.8;
  }
}

.preview-arrow {
  color: #999;
  font-size: 14px;
}

.current-mode-name {
  text-align: center;
  padding: 8px 16px 16px;
  font-size: 15px;
  font-weight: 500;
  color: #333;
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
