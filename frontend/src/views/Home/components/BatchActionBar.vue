<template>
  <div class="batch-actions">
    <van-button type="primary" size="small" plain @click="onSelectAll">
      {{ isAllSelected ? '取消全选' : '全选' }}
    </van-button>
    <van-button type="primary" size="small" plain @click="onSelectGroup">
      全选当前分组
    </van-button>
    <van-button
      type="primary"
      size="small"
      icon="down"
      @click="onExport"
      :disabled="selectedCount === 0"
    >
      导出 ({{ selectedCount }})
    </van-button>
    <van-button
      type="primary"
      size="small"
      @click="onMove"
      :disabled="selectedCount === 0"
    >
      移动到 ({{ selectedCount }})
    </van-button>
    <van-button
      v-if="isAdmin"
      type="danger"
      size="small"
      @click="onDelete"
      :disabled="selectedCount === 0"
    >
      删除 ({{ selectedCount }})
    </van-button>
    <van-button size="small" @click="onCancel">
      取消
    </van-button>
  </div>
</template>

<script setup lang="ts">
interface Props {
  selectedCount: number
  isAllSelected: boolean
  isAdmin: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  'select-all': []
  'select-group': []
  'export': []
  'move': []
  'delete': []
  'cancel': []
}>()

const onSelectAll = () => emit('select-all')
const onSelectGroup = () => emit('select-group')
const onExport = () => emit('export')
const onMove = () => emit('move')
const onDelete = () => emit('delete')
const onCancel = () => emit('cancel')
</script>

<style scoped>
.batch-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  padding: 10px 16px;
  display: flex;
  justify-content: center;
  gap: 12px;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
  z-index: 100;
}
</style>
