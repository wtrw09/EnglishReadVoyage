<template>
  <!-- 分组右键菜单 -->
  <van-popup
    :show="show"
    :style="{ top: position.y + 'px', left: position.x + 'px' }"
    round
    class="context-menu"
    @update:show="handleUpdateShow"
  >
    <van-cell-group>
      <van-cell
        :title="isHideRead ? '显示已读书籍' : '隐藏已读书籍'"
        clickable
        @click="$emit('toggle-hide-read')"
      />
      <van-cell title="修改名称" clickable @click="$emit('rename')" v-if="canRename" />
      <van-cell title="删除分组" clickable @click="$emit('delete')" v-if="canDelete" />
    </van-cell-group>
  </van-popup>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BookGroup } from '../types'

const props = defineProps<{
  show: boolean
  group: BookGroup | null
  position: { x: number; y: number }
  hideReadBooksMap: Record<number, boolean>
}>()

const emit = defineEmits<{
  (e: 'toggle-hide-read'): void
  (e: 'rename'): void
  (e: 'delete'): void
  (e: 'update:show', value: boolean): void
}>()

const handleUpdateShow = (value: boolean) => {
  emit('update:show', value)
}

const isHideRead = computed(() => {
  if (!props.group) return false
  return !!props.hideReadBooksMap[props.group.id]
})

const canRename = computed(() => {
  if (!props.group) return false
  return props.group.id !== 0 && props.group.name !== '未分组'
})

const canDelete = computed(() => {
  if (!props.group) return false
  return props.group.id !== 0 && props.group.name !== '未分组'
})
</script>

<style scoped>
.context-menu {
  position: fixed !important;
  width: 150px;
}
</style>
