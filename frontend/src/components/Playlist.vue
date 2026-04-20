/**
 * Playlist.vue - 播放列表组件
 *
 * 功能：管理播放队列中的书籍
 * - 显示书籍封面和标题
 * - 拖拽排序（长按拖动手柄）
 * - 多种排序方式（默认、书名、添加时间）
 * - 悬停显示播放按钮
 * - 移除和清空操作
 */
<template>
  <div class="playlist-container">
    <div class="playlist-header">
      <span>播放列表 ({{ items.length }})</span>
      <div class="header-actions">
        <!-- 排序模式切换 -->
        <div class="sort-mode-wrapper">
          <i
            :class="[isSortMode ? 'fas fa-check' : 'fas fa-right-left', 'sort-mode-icon', { 'active': isSortMode }]"
            @click="toggleSortMode"
          />
          <span v-if="isSortMode" class="sort-mode-text">完成</span>
        </div>
        <!-- 排序选项弹窗 -->
        <van-popover
          v-model:show="showSortMenu"
          placement="bottom-end"
          :offset="[0, 8]"
        >
          <div class="sort-menu">
            <div
              v-for="option in sortOptions"
              :key="option.value"
              class="sort-menu-item"
              :class="{ 'active': currentSort === option.value }"
              @click="handleSortSelect(option.value)"
            >
              <i :class="option.icon" />
              <span>{{ option.label }}</span>
            </div>
          </div>
          <template #reference>
            <div v-if="!isSortMode" class="header-icon-wrapper">
              <i class="fas fa-arrow-up header-icon" />
            </div>
          </template>
        </van-popover>
        <i class="fas fa-trash header-icon" @click="$emit('clear')" />
      </div>
    </div>
    <div class="playlist-body">
      <!-- 拖拽排序模式 -->
      <draggable
        v-if="isSortMode"
        v-model="localItems"
        item-key="id"
        handle=".drag-handle"
        ghost-class="dragging-ghost"
        drag-class="dragging"
        @end="handleDragEnd"
      >
        <template #item="{ element, index }">
          <div
            class="playlist-item sort-item"
            :class="{ 'active': index === currentIndex }"
          >
            <div class="drag-handle">
              <i class="fas fa-bars" />
            </div>
            <div class="playlist-item-content">
              <img
                v-if="element.book_cover"
                :src="element.book_cover"
                class="playlist-item-cover"
                loading="lazy"
                decoding="async"
              />
              <div v-else class="playlist-item-placeholder">
                <i class="fas fa-book" />
              </div>
              <span class="playlist-item-title">{{ element.book_title }}</span>
            </div>
            <i
              class="fas fa-xmark playlist-item-remove-btn"
              @click.stop="$emit('remove', element.id)"
            />
          </div>
        </template>
      </draggable>
      <!-- 普通模式 -->
      <template v-else>
        <div
          v-for="(item, index) in displayItems"
          :key="item.id"
          class="playlist-item"
          :class="{ 'active': index === currentIndex }"
          @mouseenter="hoveredIndex = index"
          @mouseleave="hoveredIndex = null"
        >
          <div class="playlist-item-content">
            <img
              v-if="item.book_cover"
              :src="item.book_cover"
              class="playlist-item-cover"
              loading="lazy"
              decoding="async"
            />
            <div v-else class="playlist-item-placeholder">
              <i class="fas fa-book" />
            </div>
            <span class="playlist-item-title">{{ item.book_title }}</span>
            <!-- 播放按钮：悬停或当前播放时显示 -->
            <div
              v-if="hoveredIndex === index || (index === currentIndex && isPlaying)"
              class="playlist-item-play-btn"
              @click.stop="$emit('play', index)"
            >
              <i :class="index === currentIndex && isPlaying ? 'fas fa-circle-pause' : 'fas fa-circle-play'" />
            </div>
          </div>
          <i
            class="fas fa-xmark playlist-item-remove-btn"
            @click.stop="$emit('remove', item.id)"
          />
        </div>
      </template>
      <div v-if="items.length === 0" class="empty-playlist">
        <i class="fas fa-music" style="font-size: 48px;" />
        <p>播放列表为空</p>
        <van-button type="primary" size="small" @click="$emit('add')">
          添加书籍
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import draggable from 'vuedraggable'

interface PlaylistItem {
  id: number
  book_id: string
  book_title: string
  book_cover: string | null
  sort_order: number
  added_at: string
}

type SortType = 'default' | 'name' | 'nameDesc' | 'addedTime' | 'addedTimeDesc'

interface Props {
  items: PlaylistItem[]
  currentIndex: number
  isPlaying: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  play: [index: number]
  remove: [itemId: number]
  clear: []
  add: []
  reorder: [itemOrders: { item_id: number; sort_order: number }[]]
}>()

// 悬停状态
const hoveredIndex = ref<number | null>(null)

// 排序模式
const isSortMode = ref(false)
const showSortMenu = ref(false)
const currentSort = ref<SortType>('default')

// 本地副本用于拖拽排序
const localItems = ref<PlaylistItem[]>([...props.items])

// 监听 props.items 变化，更新本地副本
watch(() => props.items, (newItems) => {
  if (!isSortMode.value) {
    localItems.value = [...newItems]
  }
}, { deep: true })

// 排序选项
const sortOptions: { label: string; value: SortType; icon: string }[] = [
  { label: '默认顺序', value: 'default', icon: 'fa-right-left' },
  { label: '书名升序', value: 'name', icon: 'fa-arrow-up' },
  { label: '书名降序', value: 'nameDesc', icon: 'fa-arrow-down' },
  { label: '添加时间升序', value: 'addedTime', icon: 'fa-clock' },
  { label: '添加时间降序', value: 'addedTimeDesc', icon: 'fa-clock' },
]

// 根据排序方式显示的项目
const displayItems = computed(() => {
  const items = [...props.items]
  switch (currentSort.value) {
    case 'name':
      return items.sort((a, b) => a.book_title.localeCompare(b.book_title))
    case 'nameDesc':
      return items.sort((a, b) => b.book_title.localeCompare(a.book_title))
    case 'addedTime':
      return items.sort((a, b) => new Date(a.added_at).getTime() - new Date(b.added_at).getTime())
    case 'addedTimeDesc':
      return items.sort((a, b) => new Date(b.added_at).getTime() - new Date(a.added_at).getTime())
    default:
      return items
  }
})

// 切换排序模式
const toggleSortMode = () => {
  if (isSortMode.value) {
    // 退出排序模式，保存排序
    isSortMode.value = false
  } else {
    // 进入排序模式
    localItems.value = [...props.items]
    isSortMode.value = true
  }
}

// 处理拖拽结束
const handleDragEnd = () => {
  // 生成新的排序信息
  const itemOrders = localItems.value.map((item, index) => ({
    item_id: item.id,
    sort_order: index
  }))
  emit('reorder', itemOrders)
}

// 处理排序选择
const handleSortSelect = (sortType: SortType) => {
  currentSort.value = sortType
  showSortMenu.value = false
}
</script>

<style scoped lang="less">
.playlist-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

.playlist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
  font-weight: 600;
  font-size: 16px;

  i {
    font-size: 18px;
    color: #666;
    cursor: pointer;

    &:hover {
      color: #ee0a24;
    }
  }
}

.playlist-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.playlist-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  transition: background 0.2s;

  &:hover,
  &.active {
    background: #f0f0f0;
  }

  .playlist-item-content {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    min-width: 0;
    overflow: hidden;

    .playlist-item-cover,
    .playlist-item-placeholder {
      width: 32px;
      height: 44px;
      border-radius: 4px;
      object-fit: cover;
      flex-shrink: 0;
    }

    .playlist-item-placeholder {
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f5f5f5;

      i {
        font-size: 24px;
        color: #ccc;
      }
    }

    .playlist-item-title {
      flex: 1;
      font-size: 14px;
      color: #333;
      line-height: 1.5;
      word-break: break-word;
    }

    .playlist-item-play-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      flex-shrink: 0;

      i {
        font-size: 20px;
        color: #07c160;

        &:hover {
          opacity: 0.8;
        }
      }
    }
  }

  .playlist-item-remove-btn {
    padding: 6px;
    color: #999;
    cursor: pointer;
    font-size: 16px;
    flex-shrink: 0;

    &:hover {
      color: #ee0a24;
    }
  }
}

.empty-playlist {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #999;

  p {
    margin: 16px 0;
  }
}

/* 头部操作按钮 */
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.header-icon {
  font-size: 18px;
  color: #666;
  cursor: pointer;

  &:hover {
    color: #ee0a24;
  }
}

/* 排序模式 */
.sort-mode-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.sort-mode-icon {
  font-size: 18px;
  color: #666;
  cursor: pointer;

  &:hover,
  &.active {
    color: #07c160;
  }
}

.sort-mode-text {
  font-size: 12px;
  color: #07c160;
}

/* 排序菜单 */
.sort-menu {
  padding: 8px 0;
  min-width: 140px;
}

.sort-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 14px;
  color: #333;

  &:hover {
    background: #f5f5f5;
  }

  &.active {
    color: #07c160;
    background: #f0f9f0;
  }

  i {
    font-size: 16px;
  }
}

/* 拖拽排序样式 */
.sort-item {
  .drag-handle {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
    cursor: grab;
    color: #999;

    &:active {
      cursor: grabbing;
    }

    i {
      font-size: 18px;
    }
  }
}

.dragging-ghost {
  opacity: 0.5;
  background: #f0f0f0;
}

.dragging {
  opacity: 0.8;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
</style>
