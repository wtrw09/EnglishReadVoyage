<template>
  <div class="playlist-container">
    <div class="playlist-header">
      <span>播放列表 ({{ items.length }})</span>
      <van-icon name="delete-o" @click="$emit('clear')" />
    </div>
    <div class="playlist-body">
      <div
        v-for="(item, index) in items"
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
          />
          <div v-else class="playlist-item-placeholder">
            <van-icon name="book-o" />
          </div>
          <span class="playlist-item-title">{{ item.book_title }}</span>
          <!-- 播放按钮：悬停或当前播放时显示 -->
          <div
            v-if="hoveredIndex === index || (index === currentIndex && isPlaying)"
            class="playlist-item-play-btn"
            @click.stop="$emit('play', index)"
          >
            <van-icon :name="index === currentIndex && isPlaying ? 'pause-circle' : 'play-circle'" />
          </div>
        </div>
        <van-icon
          name="cross"
          class="playlist-item-remove-btn"
          @click.stop="$emit('remove', item.id)"
        />
      </div>
      <div v-if="items.length === 0" class="empty-playlist">
        <van-icon name="music-o" size="48" />
        <p>播放列表为空</p>
        <van-button type="primary" size="small" @click="$emit('add')">
          添加书籍
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface PlaylistItem {
  id: number
  book_id: string
  book_title: string
  book_cover: string | null
  sort_order: number
  added_at: string
}

interface Props {
  items: PlaylistItem[]
  currentIndex: number
  isPlaying: boolean
}

const props = defineProps<Props>()

defineEmits<{
  play: [index: number]
  remove: [itemId: number]
  clear: []
  add: []
}>()

// 悬停状态
const hoveredIndex = ref<number | null>(null)
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

  .van-icon {
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

      .van-icon {
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

      .van-icon {
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
</style>
