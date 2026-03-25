<template>
  <van-popover
    v-model:show="visible"
    placement="bottom-end"
    :actions="actions"
    close-on-click-outside
    teleport="body"
    @select="onSelect"
  >
    <template #reference>
      <slot />
    </template>
  </van-popover>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PopoverAction } from '@/types'

interface Props {
  show: boolean
  actions: PopoverAction[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'select': [action: PopoverAction]
}>()

const visible = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value)
})

const onSelect = (action: PopoverAction) => {
  emit('select', action)
}
</script>
