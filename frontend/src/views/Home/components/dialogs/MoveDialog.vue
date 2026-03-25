<template>
  <van-popup v-model:show="visible" position="bottom" round>
    <div class="move-dialog">
      <div class="move-dialog-header">
        <span>移动到分组</span>
        <van-icon name="cross" @click="visible = false" />
      </div>

      <div class="move-dialog-content">
        <van-radio-group v-model="selectedCategory">
          <van-cell-group>
            <van-cell
              v-for="cat in categories"
              :key="cat.id"
              clickable
              @click="selectedCategory = cat.id"
            >
              <template #title>
                <span>{{ cat.name }}</span>
              </template>
              <template #right-icon>
                <van-radio :name="cat.id" />
              </template>
            </van-cell>
          </van-cell-group>
        </van-radio-group>
      </div>

      <div class="move-dialog-footer">
        <van-button size="small" type="primary" plain @click="showAddNew = true">
          创建新分组
        </van-button>
        <van-button
          size="small"
          type="primary"
          :loading="isMoving"
          loading-text="移动中..."
          @click="onConfirm"
        >
          确定
        </van-button>
      </div>

      <!-- 创建新分组输入 -->
      <van-field
        v-if="showAddNew"
        v-model="newGroupName"
        placeholder="输入新分组名称"
        @keyup.enter="onCreateNew"
      >
        <template #button>
          <van-button size="small" type="primary" @click="onCreateNew">创建</van-button>
        </template>
      </van-field>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Category {
  id: number
  name: string
}

interface Props {
  show: boolean
  categories: Category[]
  isMoving: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'confirm': [categoryId: number]
  'createGroup': [name: string]
}>()

// 本地状态
const selectedCategory = ref(0)
const showAddNew = ref(false)
const newGroupName = ref('')

// 计算属性
const visible = computed({
  get: () => props.show,
  set: (value) => {
    emit('update:show', value)
    if (!value) {
      // 关闭时重置状态
      showAddNew.value = false
      newGroupName.value = ''
    }
  }
})

// 监听categories变化，设置默认选中
watch(() => props.categories, (newCategories) => {
  if (newCategories.length > 0 && selectedCategory.value === 0) {
    selectedCategory.value = newCategories[0].id
  }
}, { immediate: true })

// 方法
const onConfirm = () => {
  if (selectedCategory.value > 0) {
    emit('confirm', selectedCategory.value)
  }
}

const onCreateNew = () => {
  if (newGroupName.value.trim()) {
    emit('createGroup', newGroupName.value.trim())
    showAddNew.value = false
    newGroupName.value = ''
  }
}
</script>

<style scoped>
.move-dialog {
  max-height: 60vh;
  display: flex;
  flex-direction: column;
}

.move-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #eee;
  font-size: 16px;
  font-weight: 500;
}

.move-dialog-content {
  flex: 1;
  overflow-y: auto;
}

.move-dialog-footer {
  display: flex;
  justify-content: space-between;
  padding: 16px;
  gap: 12px;
  border-top: 1px solid #eee;
}
</style>
