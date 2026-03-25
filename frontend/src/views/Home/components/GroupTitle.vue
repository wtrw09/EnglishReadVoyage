<template>
  <div
    class="group-title"
    @contextmenu.prevent="onContextMenu"
  >
    <div v-if="isMultiSelect" class="group-checkbox">
      <input
        type="checkbox"
        :checked="isSelected"
        @change.stop="onToggleSelect"
      />
    </div>
    <span class="group-name">{{ group.name }}</span>
    <span class="book-count">({{ group.books.length }})</span>
  </div>
</template>

<script setup lang="ts">
import type { BookGroup } from '@/types'

interface Props {
  group: BookGroup
  isMultiSelect: boolean
  isSelected: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  'toggle-select': []
  'contextmenu': [event: MouseEvent]
}>()

const onToggleSelect = () => {
  emit('toggle-select')
}

const onContextMenu = (event: MouseEvent) => {
  emit('contextmenu', event)
}
</script>

<style scoped>
.group-title {
  display: flex;
  align-items: center;
}

.group-checkbox {
  display: flex;
  align-items: center;
  margin-right: 8px;
}

.group-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #1989fa;
}

.group-name {
  font-size: 16px;
  font-weight: 500;
}

.book-count {
  font-size: 12px;
  color: #969799;
  margin-left: 8px;
}
</style>
