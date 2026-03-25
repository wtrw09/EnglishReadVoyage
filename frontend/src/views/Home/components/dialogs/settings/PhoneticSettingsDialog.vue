<template>
  <van-dialog
    v-model:show="visible"
    title="音标设置"
    show-cancel-button
    confirm-button-text="保存"
    cancel-button-text="取消"
    @confirm="onConfirm"
  >
    <div class="settings-dialog-content">
      <van-radio-group v-model="localAccent">
        <van-cell-group>
          <van-cell title="英式音标 (UK)" clickable @click="localAccent = 'uk'">
            <template #right-icon>
              <van-radio name="uk" />
            </template>
            <template #label>
              <span class="dict-label">使用英式发音音标，如 /həˈləʊ/</span>
            </template>
          </van-cell>
          <van-cell title="美式音标 (US)" clickable @click="localAccent = 'us'">
            <template #right-icon>
              <van-radio name="us" />
            </template>
            <template #label>
              <span class="dict-label">使用美式发音音标，如 /həˈloʊ/</span>
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  show: boolean
  accent: 'uk' | 'us'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'update:accent': [value: 'uk' | 'us']
  'save': []
}>()

const visible = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value)
})

const localAccent = computed({
  get: () => props.accent,
  set: (value) => emit('update:accent', value)
})

const onConfirm = () => {
  emit('save')
}
</script>

<style scoped>
.settings-dialog-content {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.dict-label {
  font-size: 12px;
  color: #969799;
}
</style>
