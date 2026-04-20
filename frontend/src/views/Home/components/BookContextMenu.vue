/**
 * BookContextMenu.vue - 书籍右键菜单
 *
 * 功能：书籍操作菜单
 * - 标记已读/未读
 * - 重命名、导出、移动、修改封面
 * - 多选模式、批量操作
 * - 删除书籍
 */
<template>
  <!-- 书籍右键菜单 -->
  <van-popup
    :show="show"
    :style="{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }"
    round
    class="context-menu"
    @update:show="$emit('update:show', $event)"
  >
    <van-cell-group>
      <van-cell
        :title="book?.is_read ? '标记为未读' : '标记为已读'"
        clickable
        @click="$emit('toggle-read')"
      />
      <van-cell title="重命名" clickable @click="$emit('rename')" v-if="!isMultiSelect || selectedCount === 1" />
      <van-cell title="选择更多" clickable @click="$emit('enable-multi-select')" v-if="!isMultiSelect" />
      <van-cell title="导出书籍" clickable @click="$emit('export')" />
      <van-cell :title="isMultiSelect && selectedCount > 1 ? '批量移动到其他分组' : '移动到其他分组'" clickable @click="$emit('move')" />
      <van-cell title="修改封面" clickable @click="$emit('change-cover')" v-if="!isMultiSelect || selectedCount === 1" />
      <van-cell :title="isMultiSelect && selectedCount > 1 ? '批量删除' : '删除'" clickable @click="$emit('delete')" v-if="isAdmin" />
    </van-cell-group>
  </van-popup>
</template>

<script setup lang="ts">
import type { Book } from '../types'

defineProps<{
  show: boolean
  book: Book | null
  isMultiSelect: boolean
  selectedCount: number
  isAdmin: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-read'): void
  (e: 'rename'): void
  (e: 'enable-multi-select'): void
  (e: 'export'): void
  (e: 'move'): void
  (e: 'change-cover'): void
  (e: 'delete'): void
  (e: 'update:show', value: boolean): void
}>()

const handleUpdateShow = (value: boolean) => {
  emit('update:show', value)
}
</script>

<style scoped>
.context-menu {
  position: fixed !important;
  width: 150px;
  top: 50% !important;
  left: 50% !important;
  transform: translate(-50%, -50%) !important;
}
</style>
