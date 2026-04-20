/**
 * BilingualModeDialog.vue - 双语朗读模式设置对话框
 *
 * 功能说明：
 * - 提供预设朗读模式选择（英文→中文、英文×2→中文、仅英文等）
 * - 支持自定义朗读模式，用户可自由组合朗读段并设置重复次数
 * - 实时预览当前选择的朗读模式效果
 * - 检测并提示书籍中缺失中文音频的句子数量
 *
 * Props：
 * - show: 控制对话框显示
 * - currentPresetId: 当前选中的预设ID
 * - currentSegments: 当前自定义朗读段配置
 * - missingZhCount: 缺失中文音频的句子数量
 *
 * Events：
 * - update:show: 关闭对话框时触发
 * - confirm: 确认选择时触发，参数为 (presetId, segments)
 */
<template>
  <van-popup
    v-model:show="visible"
    round
    position="bottom"
    :style="{ height: 'auto' }"
    :close-on-click-overlay="false"
  >
    <div class="bilingual-mode-dialog">
      <!-- 标题 -->
      <div class="dialog-header">
        <i class="fas fa-volume-high header-icon" />
        <span>朗读模式设置</span>
        <i class="fas fa-xmark close-icon" @click="handleClose" />
      </div>

      <!-- 标签页切换 -->
      <div class="tab-switch">
        <div
          class="tab-item"
          :class="{ 'active': activeTab === 'preset' }"
          @click="activeTab = 'preset'"
        >
          预设模式
        </div>
        <div
          class="tab-item"
          :class="{ 'active': activeTab === 'custom' }"
          @click="activeTab = 'custom'"
        >
          自定义
        </div>
      </div>

      <!-- 预设模式选择 -->
      <div v-show="activeTab === 'preset'" class="preset-section">
        <div class="preset-grid">
          <div
            v-for="preset in presets"
            :key="preset.id"
            class="preset-item"
            :class="{ 'active': selectedPresetId === preset.id && !isCustomMode }"
            @click="selectPreset(preset.id)"
          >
            <div class="preset-name">{{ preset.name }}</div>
            <div class="preset-desc">{{ preset.description }}</div>
          </div>
        </div>
      </div>

      <!-- 自定义模式 -->
      <div v-show="activeTab === 'custom'" class="custom-section">
        <div class="custom-segments">
          <div
            v-for="(segment, index) in customSegments"
            :key="index"
            class="segment-item"
          >
            <!-- 语言选择 -->
            <div class="segment-lang">
              <i :class="segment.lang === 'en' ? 'fas fa-file-lines' : 'fas fa-comment'" />
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
            <i class="fas fa-xmark delete-btn" @click="removeSegment(index)" />
          </div>
        </div>
        <!-- 添加按钮 -->
        <div class="add-segment-btns">
          <van-button
            class="add-btn"
            type="primary"
            plain
            size="small"
            @click="addSegment('en')"
          >
            <i class="fas fa-plus" style="margin-right: 4px;"></i>
            添加英文
          </van-button>
          <van-button
            class="add-btn"
            type="warning"
            plain
            size="small"
            @click="addSegment('zh')"
          >
            <i class="fas fa-plus" style="margin-right: 4px;"></i>
            添加中文
          </van-button>
        </div>
      </div>

      <!-- 当前选中模式显示 -->
      <div class="current-mode-section">
        <div class="section-label">当前选中的模式</div>
        <div class="current-mode-display">
          {{ currentModeName }}
        </div>
      </div>

      <!-- 预览 -->
      <div class="preview-section">
        <div class="section-label">预览</div>
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
      </div>

      <!-- 音频可用性警告 -->
      <div v-if="missingZhCount > 0" class="warning-section">
        <i class="fas fa-triangle-exclamation warning-icon" />
        <span>当前书籍有 <strong>{{ missingZhCount }}</strong> 个句子缺少中文音频，缺少中文时将自动跳过</span>
      </div>

      <!-- 按钮区域 -->
      <div class="dialog-actions">
        <van-button class="cancel-btn" @click="handleClose">取消</van-button>
        <van-button type="primary" class="confirm-btn" @click="handleConfirm">确定</van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

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

interface Props {
  show: boolean
  // 当前选中的预设ID
  currentPresetId?: string
  // 当前的自定义配置
  currentSegments?: ReadSegment[]
  // 缺少中文音频的数量
  missingZhCount?: number
}

const props = withDefaults(defineProps<Props>(), {
  currentPresetId: 'en1-zh1',
  currentSegments: () => [
    { lang: 'en', count: 1 },
    { lang: 'zh', count: 1 }
  ],
  missingZhCount: 0
})

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'confirm', presetId: string, segments: ReadSegment[]): void
}>()

// 内部状态
const visible = ref(props.show)
const activeTab = ref<'preset' | 'custom'>('preset')
const selectedPresetId = ref(props.currentPresetId)
const customSegments = ref<ReadSegment[]>([])
const isCustomMode = ref(false)

// 监听 props 变化
watch(() => props.show, (val) => {
  visible.value = val
  if (val) {
    // 重置状态
    selectedPresetId.value = props.currentPresetId
    customSegments.value = JSON.parse(JSON.stringify(props.currentSegments || []))

    // 判断当前是预设还是自定义
    const isPreset = presets.some(p => p.id === props.currentPresetId)
    if (isPreset) {
      activeTab.value = 'preset'
      isCustomMode.value = false
    } else {
      activeTab.value = 'custom'
      isCustomMode.value = true
    }
  }
})

watch(visible, (val) => {
  emit('update:show', val)
})

// 当前模式名称
const currentModeName = computed(() => {
  if (activeTab.value === 'custom' || isCustomMode.value) {
    return `自定义 (${customSegments.value.length}段)`
  }
  const preset = presets.find(p => p.id === selectedPresetId.value)
  return preset?.name || ''
})

// 当前朗读段
const currentSegments = computed(() => {
  if (activeTab.value === 'custom' || isCustomMode.value) {
    return customSegments.value
  }
  const preset = presets.find(p => p.id === selectedPresetId.value)
  return preset?.segments || []
})

// 选择预设
const selectPreset = (presetId: string) => {
  selectedPresetId.value = presetId
  isCustomMode.value = false
}

// 添加朗读段
const addSegment = (lang: 'en' | 'zh') => {
  customSegments.value.push({ lang, count: 1 })
}

// 删除朗读段
const removeSegment = (index: number) => {
  if (customSegments.value.length > 1) {
    customSegments.value.splice(index, 1)
  }
}

// 关闭对话框
const handleClose = () => {
  visible.value = false
  emit('update:show', false)
}

// 确认选择
const handleConfirm = () => {
  const segments = currentSegments.value
  if (!segments || segments.length === 0) {
    return
  }

  let presetId: string
  if (activeTab.value === 'custom' || isCustomMode.value) {
    // 自定义模式：生成一个唯一的ID
    presetId = 'custom_' + Date.now()
  } else {
    presetId = selectedPresetId.value
  }

  emit('confirm', presetId, segments)
  handleClose()
}
</script>

<style lang="less" scoped>
.bilingual-mode-dialog {
  padding: 20px 16px 24px;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  margin-bottom: 20px;

  .header-icon {
    font-size: 20px;
    margin-right: 8px;
    color: #07c160;
  }

  span {
    font-size: 18px;
    font-weight: 600;
    color: #333;
  }

  .close-icon {
    position: absolute;
    right: 0;
    font-size: 20px;
    color: #999;
    cursor: pointer;
    padding: 4px;
  }
}

// 标签页切换
.tab-switch {
  display: flex;
  background: #f5f5f5;
  border-radius: 8px;
  padding: 4px;
  margin-bottom: 20px;

  .tab-item {
    flex: 1;
    text-align: center;
    padding: 10px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    color: #666;
    cursor: pointer;
    transition: all 0.2s;

    &.active {
      background: #fff;
      color: #07c160;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
  }
}

.section-label {
  font-size: 14px;
  font-weight: 500;
  color: #666;
  margin-bottom: 12px;
}

.preset-section {
  margin-bottom: 20px;

  .preset-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .preset-item {
    padding: 14px 12px;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s;
    background: #fff;

    &:active {
      background: #f5f5f5;
    }

    &.active {
      border-color: #07c160;
      background: #f0fff4;
    }

    .preset-name {
      font-size: 15px;
      font-weight: 600;
      color: #333;
      margin-bottom: 4px;
    }

    .preset-desc {
      font-size: 12px;
      color: #999;
    }

    &.active .preset-name {
      color: #07c160;
    }
  }
}

// 自定义模式
.custom-section {
  margin-bottom: 20px;

  .custom-segments {
    max-height: 200px;
    overflow-y: auto;
    margin-bottom: 12px;
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

      :deep(.van-stepper) {
        .van-stepper__input {
          width: 40px;
          font-size: 14px;
        }
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

    .add-btn {
      flex: 1;
      height: 40px;
      border-radius: 8px;
      font-size: 14px;
    }
  }
}

// 竖屏时垂直排列
@media (max-width: 480px) {
  .custom-section {
    .add-segment-btns {
      flex-direction: column;
    }
  }
}

.current-mode-section {
  margin-bottom: 20px;

  .current-mode-display {
    padding: 14px 16px;
    background: #f5f5f5;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 500;
    color: #333;
    text-align: center;
  }
}

.preview-section {
  margin-bottom: 20px;

  .preview-display {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
    padding: 16px;
    background: #f5f5f5;
    border-radius: 8px;
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
}

.warning-section {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: #fff7e6;
  border-radius: 8px;
  margin-bottom: 20px;

  .warning-icon {
    color: #fa8c16;
    font-size: 16px;
    flex-shrink: 0;
    margin-top: 2px;
  }

  span {
    font-size: 13px;
    color: #fa8c16;
    line-height: 1.5;

    strong {
      font-weight: 600;
    }
  }
}

.dialog-actions {
  display: flex;
  gap: 12px;

  .cancel-btn,
  .confirm-btn {
    flex: 1;
    height: 44px;
    border-radius: 8px;
    font-size: 15px;
  }

  .cancel-btn {
    background: #f5f5f5;
    color: #666;
    border: none;
  }

  .confirm-btn {
    background: #07c160;
    border: none;
  }
}
</style>
