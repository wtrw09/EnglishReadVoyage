/**
 * TrainingMode.vue - 听力训练模式组件
 *
 * 功能：
 * - 句子列表垂直滚动显示（可点击跳转）
 * - 极简控制栏（上一句/复读/播放暂停/下一句/倍速）
 * - 训练工具条（单句强化/影子跟读/默写模式）
 * - 倍速选择弹出面板
 * - 训练设置面板（显示模式、播完行为等）
 *
 * Props：
 * - sentences: 句子完整列表（全量渲染，可自由滚动）
 * - isPlaying: 是否正在播放
 * - isWaitingAfterReinforce: 强化播完后是否等待用户操作
 * - playbackRate: 当前倍速
 * - displayMode: 显示模式 (en/en-zh/zh)
 * - trainingMode: 训练模式 (shadow/dictation)
 * - sentenceRepeatCount: 单句重复播放次数
 * - shadowGapSeconds: 影子跟读间隔秒数
 * - currentSentenceIndex: 当前句子索引
 * - totalSentences: 总句子数
 * - afterPlayBehavior: 播完行为 (wait/auto)
 *
 * Events：
 * - prev-sentence: 上一句
 * - next-sentence: 下一句
 * - replay-sentence: 复读
 * - toggle-play: 切换播放/暂停
 * - seek-to-sentence: 点击句子跳转
 * - update:displayMode: 显示模式变更
 * - update:trainingMode: 训练模式变更
 * - update:sentenceRepeatCount: 重复次数变更
 * - update:playbackRate: 倍速变更
 * - update:afterPlayBehavior: 播完行为变更
 */
<template>
  <div class="training-layout">
    <!-- 句子列表区域（可垂直滚动） -->
    <div class="sentence-list-wrapper">
      <div class="sentence-list" ref="sentenceContainerRef">
        <div v-for="(item, index) in sentences" :key="index"
             class="sentence-line"
             :class="{ current: index === currentSentenceIndex }"
             @click="$emit('seek-to-sentence', index)">
          <div v-if="displayMode === 'en' || displayMode === 'en-zh'"
               class="sentence-text"
               :class="{
                 'dictation-glass': trainingMode === 'dictation' && index !== dictationActiveSentenceIndex,
                 'dictation-hidden': trainingMode === 'shadow' && !isRevealed && index === currentSentenceIndex
               }">
            {{ item.text }}
          </div>
          <div v-if="displayMode === 'en-zh' || displayMode === 'zh'"
               class="sentence-translation"
               :class="{
                 'dictation-glass': trainingMode === 'dictation' && index !== dictationActiveSentenceIndex,
                 'dictation-hidden': trainingMode === 'shadow' && !isRevealed && index === currentSentenceIndex
               }">
            {{ item.translation }}
          </div>
        </div>
      </div>

    </div>

    <!-- 句子进度条 -->
    <div class="sentence-progress">
      <div class="progress-info">
        <span class="progress-label">句子进度</span>
        <span class="progress-value">{{ isTrainingDragging && trainingDragIndex >= 0 ? Math.round(trainingDragIndex) + 1 : currentSentenceIndex + 1 }} / {{ totalSentences }}</span>
      </div>
      <div class="sentence-progress-wrapper">
        <van-slider
          :model-value="isTrainingDragging && trainingDragIndex >= 0 ? trainingDragIndex : currentSentenceIndex"
          :max="totalSentences - 1"
          :step="0.01"
          active-color="#07c160"
          inactive-color="#e0e0e0"
          bar-height="4px"
          @update:model-value="onTrainingSliderUpdate"
          @drag-start="onTrainingDragStart"
          @change="onTrainingSliderChange"
          @drag-end="onTrainingDragEnd"
        >
          <template #button>
            <div class="slider-button"></div>
          </template>
        </van-slider>
      </div>
    </div>

    <!-- 极简控制栏 -->
    <div class="training-controls">
      <div class="ctrl-btn" @click="$emit('prev-sentence')">
        <i class="fas fa-backward-step"></i>
      </div>
      <div class="ctrl-btn" @click="$emit('replay-sentence')">
        <i class="fas fa-rotate-left"></i>
      </div>
      <div class="ctrl-btn play-btn" @click="$emit('toggle-play')">
        <i :class="['fas', isPlaying ? 'fa-pause-circle' : 'fa-play-circle']"></i>
      </div>
      <div class="ctrl-btn" @click="$emit('next-sentence')">
        <i class="fas fa-forward-step"></i>
      </div>
      <div class="ctrl-btn rate-btn" @click="showSpeedPicker = true">
        <span class="rate-text">{{ playbackRate }}x</span>
      </div>
    </div>

    <!-- 训练工具条 -->
    <div class="training-toolbar">
      <!-- 单句强化重复次数（始终可用，非模式） -->
      <div class="tool-btn"
           :class="{ active: sentenceRepeatCount > 1 }"
           @click="cycleRepeatCount"
           title="每个句子重复播放次数">
        <i class="fas fa-arrows-rotate"></i>
        <span>{{ sentenceRepeatCount }}x</span>
      </div>
      <!-- 影子跟读 -->
      <div class="tool-btn" :class="{ active: trainingMode === 'shadow' }"
           @click="toggleTrainingMode('shadow')">
        <i class="fas fa-microphone"></i>
        <span v-if="trainingMode === 'shadow'">{{ shadowGapSeconds }}s</span>
      </div>
      <!-- 默写模式 -->
      <div class="tool-btn" :class="{ active: trainingMode === 'dictation' }"
           @click="toggleTrainingMode('dictation')">
        <i class="fas fa-pen"></i>
      </div>
      <!-- 跟读模式隐藏按钮（仅跟读模式可见） -->
      <div v-if="trainingMode === 'shadow'" class="tool-btn"
           :class="{ active: !isRevealed }"
           @click="toggleReveal"
           title="隐藏/显示文字">
        <i :class="['fas', isRevealed ? 'fa-eye' : 'fa-eye-slash']"></i>
      </div>
      <!-- 等待状态提示 -->
      <span v-if="isWaitingAfterReinforce" class="waiting-hint">
        <i class="fas fa-arrow-pointer"></i> 选择下一步操作
      </span>
      <!-- 设置齿轮 -->
      <div class="tool-btn settings-btn" @click="showTrainingSettings = true">
        <i class="fas fa-gear"></i>
      </div>
    </div>

    <!-- 倍速选择弹出面板 -->
    <van-popup v-model:show="showSpeedPicker" position="bottom" round>
      <div class="speed-picker">
        <div class="popup-header">
          <span>播放速度</span>
          <i class="fas fa-xmark close-icon" @click="showSpeedPicker = false"></i>
        </div>
        <div class="speed-options">
          <div v-for="rate in RATE_OPTIONS" :key="rate"
               class="speed-option"
               :class="{ active: playbackRate === rate }"
               @click="selectRate(rate)">
            {{ rate }}x
            <i v-if="playbackRate === rate" class="fas fa-check"></i>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 训练设置弹出面板 -->
    <van-action-sheet v-model:show="showTrainingSettings" title="训练设置">
      <div class="training-settings-content">
        <!-- 显示模式 -->
        <div class="setting-row">
          <span class="setting-label">显示模式</span>
          <div class="setting-options">
            <span class="option-chip" :class="{ active: displayMode === 'en' }"
                  @click="$emit('update:displayMode', 'en')">仅英文</span>
            <span class="option-chip" :class="{ active: displayMode === 'en-zh' }"
                  @click="$emit('update:displayMode', 'en-zh')">中英对照</span>
            <span class="option-chip" :class="{ active: displayMode === 'zh' }"
                  @click="$emit('update:displayMode', 'zh')">仅中文</span>
          </div>
        </div>
        <!-- 默认训练模式 -->
        <div class="setting-row">
          <span class="setting-label">默认模式</span>
          <div class="setting-options">
            <span class="option-chip" :class="{ active: trainingMode === 'shadow' }"
                  @click="toggleTrainingMode('shadow')">跟读</span>
            <span class="option-chip" :class="{ active: trainingMode === 'dictation' }"
                  @click="toggleTrainingMode('dictation')">默写</span>
          </div>
        </div>
        <!-- 播完行为 -->
        <div class="setting-row">
          <span class="setting-label">播完行为</span>
          <div class="setting-options">
            <span class="option-chip" :class="{ active: afterPlayBehavior === 'wait' }"
                  @click="$emit('update:afterPlayBehavior', 'wait')">等待指令</span>
            <span class="option-chip" :class="{ active: afterPlayBehavior === 'auto' }"
                  @click="$emit('update:afterPlayBehavior', 'auto')">自动继续</span>
          </div>
        </div>
        <!-- 默写模式：播放完成后显示中文翻译（仅默写模式可见） -->
        <template v-if="trainingMode === 'dictation'">
          <div class="setting-row">
            <span class="setting-label">显示中文翻译</span>
            <van-switch :model-value="dictationShowTranslation"
                        @update:model-value="$emit('update:dictationShowTranslation', $event)"
                        size="24px" />
          </div>
          <div class="setting-row" v-if="dictationShowTranslation">
            <span class="setting-label">翻译停留(秒)</span>
            <van-stepper :model-value="dictationTranslationDuration" :min="1" :max="30" integer
                         @update:model-value="$emit('update:dictationTranslationDuration', $event)" />
          </div>
        </template>
      </div>
    </van-action-sheet>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'

// Props
const props = defineProps<{
  sentences: Array<{ text: string; translation: string }>
  isPlaying: boolean
  isWaitingAfterReinforce: boolean
  playbackRate: number
  displayMode: 'en' | 'en-zh' | 'zh'
  trainingMode: 'shadow' | 'dictation'
  sentenceRepeatCount: number
  shadowGapSeconds: number
  currentSentenceIndex: number
  totalSentences: number
  afterPlayBehavior: 'wait' | 'auto'
  dictationActiveSentenceIndex: number
  dictationShowTranslation: boolean
  dictationTranslationDuration: number
}>()

// Emits
const emit = defineEmits<{
  (e: 'prev-sentence'): void
  (e: 'next-sentence'): void
  (e: 'replay-sentence'): void
  (e: 'toggle-play'): void
  (e: 'seek-to-sentence', index: number): void
  (e: 'update:displayMode', mode: 'en' | 'en-zh' | 'zh'): void
  (e: 'update:trainingMode', mode: 'shadow' | 'dictation'): void
  (e: 'update:sentenceRepeatCount', count: number): void
  (e: 'update:playbackRate', rate: number): void
  (e: 'update:afterPlayBehavior', behavior: 'wait' | 'auto'): void
  (e: 'update:dictationShowTranslation', value: boolean): void
  (e: 'update:dictationTranslationDuration', value: number): void
}>()

// 内部状态
const RATE_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
const showSpeedPicker = ref(false)
const showTrainingSettings = ref(false)
const isRevealed = ref(true) // 跟读模式手动隐藏开关，默认显示文字

// 训练模式进度条拖动状态
const isTrainingDragging = ref(false)
const trainingDragIndex = ref(-1)

// 训练模式进度条变化处理
// change 事件在 drag-end 之前触发，通过 isTrainingDragging 区分拖拽和点击
const onTrainingSliderUpdate = (val: number) => {
  if (isTrainingDragging.value) {
    trainingDragIndex.value = val
  }
}

const onTrainingDragStart = () => {
  isTrainingDragging.value = true
  trainingDragIndex.value = props.currentSentenceIndex
}

const onTrainingSliderChange = (val: number) => {
  if (isTrainingDragging.value) {
    // 拖动结束：四舍五入到最近整数句子索引
    const seekTo = Math.round(trainingDragIndex.value)
    emit('seek-to-sentence', seekTo)
  } else {
    // 点击轨道：四舍五入到最近整数句子索引
    const seekTo = Math.round(val)
    emit('seek-to-sentence', seekTo)
  }
}

const onTrainingDragEnd = () => {
  isTrainingDragging.value = false
  trainingDragIndex.value = -1
}

// 句子容器引用，用于自动滚动到当前句
const sentenceContainerRef = ref<HTMLElement | null>(null)

/** 滚动当前句子到容器可视区中心 */
function scrollToCurrentSentence(): void {
  nextTick(() => {
    const container = sentenceContainerRef.value
    if (!container) return
    const currentEl = container.querySelector('.sentence-line.current')
    if (!(currentEl instanceof HTMLElement)) return
    currentEl.scrollIntoView({ block: 'center', behavior: 'instant' })
  })
}

// 监听句子切换自动滚动
watch(() => props.currentSentenceIndex, () => {
  scrollToCurrentSentence()
})

// 监听显示模式切换，重新滚动当前句到可视区中心（句子高度变化导致偏移）
watch(() => props.displayMode, () => {
  scrollToCurrentSentence()
})

// 首次挂载时滚动到第一个句子
onMounted(() => {
  scrollToCurrentSentence()
})

// 句子窗口数据到达后也触发滚动（解决首次数据延迟问题）
watch(() => props.sentences.length, (len) => {
  if (len > 0) {
    scrollToCurrentSentence()
  }
})

// 训练模式切换
const toggleTrainingMode = (mode: 'shadow' | 'dictation') => {
  const newMode = props.trainingMode === mode ? 'shadow' : mode
  emit('update:trainingMode', newMode)
}

// 句子重复次数循环
const cycleRepeatCount = () => {
  const next = props.sentenceRepeatCount >= 5 ? 1 : props.sentenceRepeatCount + 1
  emit('update:sentenceRepeatCount', next)
}

// 跟读模式隐藏/显示文字
const toggleReveal = () => {
  isRevealed.value = !isRevealed.value
}

// 选择倍速
const selectRate = (rate: number) => {
  emit('update:playbackRate', rate)
  showSpeedPicker.value = false
}
</script>

<style scoped lang="less">
.training-layout {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sentence-list {
  height: 100%;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  scroll-behavior: smooth;
  padding: 12px 16px;
  touch-action: pan-y;
}

// 句子列表外层容器
.sentence-list-wrapper {
  flex: 1;
  overflow: hidden;
}



.sentence-progress {
  padding: 6px 16px;
  background: transparent;

  .progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;

    .progress-label {
      font-size: 13px;
      color: #666;
    }

    .progress-value {
      font-size: 13px;
      font-weight: 600;
      color: #07c160;
    }
  }

  .sentence-progress-wrapper {
    display: flex;
    align-items: center;
    gap: 10px;

    .van-slider {
      flex: 1;
      position: relative;

      .slider-button {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #07c160;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
      }
    }
  }
}

.sentence-line {
  padding: 12px 0;
  transition: all 0.3s ease;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  opacity: 0.35;
  text-align: center;

  // 句子当前句高亮（通过 .current 类的样式指示）
  &.current {
    opacity: 1;
    transform: scale(1.03);

    .sentence-text {
      color: var(--van-primary-color, #07c160);
      font-size: 20px;
      font-weight: 700;
    }
  }

  &:hover:not(.current) {
    opacity: 0.6;
  }
}

.sentence-text {
  font-size: 16px;
  color: #333;
  line-height: 1.6;

  &.dictation-hidden {
    color: transparent !important;
    user-select: none;
  }

  &.dictation-glass {
    filter: blur(6px);
    opacity: 0.6;
    transition: filter 0.3s ease, opacity 0.3s ease;
  }
}

.sentence-translation {
  font-size: 13px;
  color: #999;
  margin-top: 2px;

  &.dictation-hidden {
    color: transparent !important;
  }

  &.dictation-glass {
    filter: blur(6px);
    opacity: 0.6;
    transition: filter 0.3s ease, opacity 0.3s ease;
  }
}

// 极简控制栏
.training-controls {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 12px 0;

  .ctrl-btn {
    font-size: 20px;
    color: #333;
    cursor: pointer;
    padding: 8px;
    transition: color 0.2s;

    &:active {
      color: var(--van-primary-color, #07c160);
    }

    &.play-btn {
      font-size: 36px;
      color: var(--van-primary-color, #07c160);
    }

    &.rate-btn {
      min-width: 44px;
      text-align: center;

      .rate-text {
        font-size: 14px;
        font-weight: 600;
        color: var(--van-primary-color, #07c160);
      }
    }
  }
}

// 训练工具条
.training-toolbar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-top: 1px solid #eee;

  .tool-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    border-radius: 16px;
    font-size: 13px;
    color: #666;
    background: #f5f5f5;
    cursor: pointer;
    transition: all 0.2s;

    &.active {
      background: var(--van-primary-color, #07c160);
      color: #fff;
    }

    &.settings-btn {
      margin-left: 4px;
    }
  }

  .waiting-hint {
    font-size: 12px;
    color: var(--van-primary-color, #07c160);
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .training-progress {
    margin-left: auto;
    font-size: 12px;
    color: #999;
  }
}

// 倍速选择面板
.speed-picker {
  padding: 16px 20px 24px;

  .popup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 16px;
    font-weight: 600;
    padding-bottom: 16px;

    .close-icon {
      font-size: 20px;
      color: #999;
      cursor: pointer;
    }
  }

  .speed-options {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }

  .speed-option {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 12px;
    border-radius: 8px;
    background: #f5f5f5;
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;

    &.active {
      background: var(--van-primary-color, #07c160);
      color: #fff;
    }

    i {
      font-size: 12px;
    }
  }
}

// 训练设置面板
.training-settings-content {
  padding: 16px 20px 32px;

  .setting-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid #f0f0f0;

    &:last-child {
      border-bottom: none;
    }

    .setting-label {
      font-size: 14px;
      color: #333;
    }

    .setting-options {
      display: flex;
      gap: 8px;
    }

    .option-chip {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      background: #f0f0f0;
      color: #666;
      cursor: pointer;
      transition: all 0.2s;

      &.active {
        background: var(--van-primary-color, #07c160);
        color: #fff;
      }
    }
  }
}

// 移动端压缩
@media (max-width: 480px) {
  .training-controls {
    gap: 8px;

    .ctrl-btn {
      font-size: 18px;
      padding: 6px;

      &.play-btn {
        font-size: 32px;
      }
    }
  }

  .sentence-text {
    font-size: 14px;
  }

  .sentence-line {
    padding: 8px 0;

    &.current .sentence-text {
      font-size: 17px;
    }
  }

  .training-toolbar {
    gap: 6px;
    flex-wrap: wrap;
  }

  .sentence-list {
    padding: 8px 12px;
  }
}
</style>
