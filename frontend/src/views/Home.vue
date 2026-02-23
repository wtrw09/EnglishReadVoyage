<template>
  <div class="home">
    <van-nav-bar title="英语分级阅读" fixed placeholder>
      <template #right>
        <van-popover
          v-model:show="showPopover"
          placement="bottom-end"
          :actions="popoverActions"
          @select="onPopoverSelect"
        >
          <template #reference>
            <van-icon name="user-circle-o" size="24" color="#1989fa" />
          </template>
        </van-popover>
      </template>
    </van-nav-bar>
    
    <div class="content">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text="没有更多了"
        @load="onLoad"
      >
        <van-cell
          v-for="book in books"
          :key="book.id"
          :title="book.title"
          :label="`Level: ${book.level} | ${book.page_count} 页`"
          is-link
          @click="openBook(book.id)"
        >
          <template #icon>
            <van-icon name="description" class="book-icon" />
          </template>
        </van-cell>
      </van-list>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showNotify } from 'vant'
import { useAuthStore, api } from '@/store/auth'

interface Book {
  id: number
  title: string
  level: string
  page_count: number
}

interface PopoverAction {
  text: string
  icon: string
  key: string
}

const router = useRouter()
const authStore = useAuthStore()
const books = ref<Book[]>([])
const loading = ref(false)
const finished = ref(false)
const showPopover = ref(false)

const popoverActions = computed<PopoverAction[]>(() => {
  const actions: PopoverAction[] = []
  
  if (authStore.isAdmin) {
    actions.push({ text: '用户管理', icon: 'friends-o', key: 'users' })
  } else {
    actions.push({ text: '个人信息', icon: 'user-o', key: 'users' })
  }
  
  actions.push({ text: '退出登录', icon: 'logout', key: 'logout' })
  
  return actions
})

const onPopoverSelect = (action: PopoverAction) => {
  if (action.key === 'users') {
    router.push('/users')
  } else if (action.key === 'logout') {
    showConfirmDialog({
      title: '确认退出',
      message: '确定要退出登录吗？'
    }).then(() => {
      authStore.logout()
      showNotify('已退出登录')
      router.push('/login')
    }).catch(() => {
      // 取消操作
    })
  }
}

const onLoad = async () => {
  try {
    const res = await api.get<Book[]>('/books')
    books.value = res.data
    loading.value = false
    finished.value = true
  } catch (error) {
    console.error('加载书籍失败:', error)
    loading.value = false
    finished.value = true
  }
}

const openBook = (id: number) => {
  router.push(`/book/${id}`)
}
</script>

<style scoped>
.content {
  padding-bottom: 50px;
}
.book-icon {
  margin-right: 10px;
  font-size: 24px;
  color: #1989fa;
  align-self: center;
}
</style>
