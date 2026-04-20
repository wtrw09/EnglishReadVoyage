/**
 * Home.vue - 首页/书籍列表页面
 *
 * 功能：
 * - 显示用户的书籍列表，支持按分组折叠
 * - 搜索书籍
 * - 导入书籍（管理员）
 * - 跳转到阅读器、听书模式
 * - 管理分组（创建、编辑、删除、排序）
 * - 用户菜单（设置、退出登录等）
 */
<template>
  <div class="home">
    <!-- 顶部导航栏 -->
    <van-nav-bar fixed placeholder>
      <template #left>
        <div class="nav-left">
          <div class="nav-search">
            <i class="fas fa-search search-icon"></i>
            <input
              v-model="searchText"
              type="text"
              placeholder="搜索书籍..."
              class="search-input"
              @input="handleSearch"
            />
          </div>
          <i class="fas fa-plus nav-icon" @click="openImportDialog(0)" v-if="authStore.isAdmin"></i>
        </div>
      </template>
      <template #right>
        <div class="nav-actions">
          <!-- 书籍管理下拉菜单 -->
          <van-popover
            v-model:show="showBookPopover"
            placement="bottom-end"
            :actions="bookActions"
            close-on-click-outside
            teleport="body"
            @update:show="(show: boolean) => handlePopoverShow(show, 'book')"
            @select="onBookActionSelect"
          >
            <template #reference>
              <div class="nav-icon-btn">
                <i class="fas fa-bars"></i>
              </div>
            </template>
          </van-popover>
          <!-- 拓展功能下拉菜单 -->
          <van-popover
            v-model:show="showExpandPopover"
            placement="bottom-end"
            :actions="expandActions"
            close-on-click-outside
            teleport="body"
            @update:show="(show: boolean) => handlePopoverShow(show, 'expand')"
            @select="onExpandSelect"
          >
            <template #reference>
              <div class="nav-icon-btn">
                <i class="fas fa-th-large"></i>
              </div>
            </template>
            <template #action="{ action }">
              <div class="settings-action-item">
                <i :class="['fas', action.icon]"></i>
                <span>{{ action.text }}</span>
              </div>
            </template>
          </van-popover>
          <!-- 用户名下拉菜单 -->
          <van-popover
            v-model:show="showUserPopover"
            placement="bottom-end"
            :actions="userActions"
            close-on-click-outside
            teleport="body"
            @update:show="(show: boolean) => handlePopoverShow(show, 'user')"
            @select="onUserSelect"
          >
            <template #reference>
              <span class="username-link">{{ authStore.user?.username || '用户' }}</span>
            </template>
          </van-popover>
          <!-- 设置按钮（直接跳转） -->
          <div class="nav-icon-btn" @click="router.push('/settings')">
            <i class="fas fa-gear"></i>
          </div>
        </div>
      </template>
    </van-nav-bar>

    <!-- 内容区域 -->
    <div class="content">
      <BookList
        :groups="bookGroups"
        :loading="loading"
        :search-text="searchText"
        v-model:active-names="activeNames"
        :is-multi-select="isMultiSelect"
        v-model:selected-books="selectedBooks"
        :hide-read-books-map="hideReadBooksMap"
        :cover-error-map="coverErrorMap"
        :is-admin="authStore.isAdmin"
        :is-landscape="isLandscape"
        v-model:swipe-cell-refs="swipeCellRefs"
        @import="openImportDialog"
        @select-all="selectAllBooks"
        @select-current-group="selectAllBooksInCurrentGroup"
        @export="exportSelectedBooks"
        @move="batchMoveBooks"
        @batch-delete="batchDeleteBooks"
        @cancel-multi-select="cancelMultiSelect"
        @book-click="handleBookClick"
        @book-contextmenu="showContextMenu"
        @group-contextmenu="showGroupContextMenu"
        @mark-read="markBookAsRead"
      />
    </div>

    <!-- 导入对话框 -->
    <ImportDialog :import-state="importState" />

    <!-- 导出进度对话框 -->
    <van-dialog
      v-model:show="showExportProgressDialog"
      title="导出书籍"
      :show-confirm-button="false"
      :show-cancel-button="false"
      :close-on-click-overlay="false"
    >
      <div class="export-progress-content">
        <van-progress
          :percentage="exportProgress"
          :stroke-width="10"
          :show-pivot="true"
        />
        <p class="export-status">{{ exportStatus }}</p>
        <p v-if="exportCurrentBook" class="export-current-book">
          正在处理: {{ exportCurrentBook }}
        </p>
      </div>
    </van-dialog>

    <!-- 添加分组对话框 -->
    <van-dialog
      v-model:show="showAddGroupDialog"
      title="添加分组"
      show-cancel-button
      @confirm="handleAddGroup"
    >
      <van-field
        v-model="newGroupName"
        placeholder="请输入分组名称"
        label="分组名称"
      />
    </van-dialog>

    <!-- 分组排序对话框 -->
    <van-dialog
      v-model:show="showSortGroupsDialog"
      title="排序分组"
      show-cancel-button
      confirm-button-text="保存"
      cancel-button-text="取消"
      @confirm="handleSaveGroupOrder"
      @cancel="onCancelSortMode"
    >
      <div class="sort-groups-container">
        <draggable
          v-model="sortableGroups"
          item-key="id"
          handle=".drag-handle"
          ghost-class="sort-ghost"
          drag-class="sort-drag"
        >
          <template #item="{ element }">
            <div
              class="sort-group-item"
              :class="{ 'is-uncategorized': element.name === '未分组' }"
            >
              <i class="fas fa-bars drag-handle" />
              <span class="group-name">{{ element.name }}</span>
              <span v-if="element.name === '未分组'" class="fixed-label">(固定)</span>
            </div>
          </template>
        </draggable>
      </div>
    </van-dialog>

    <!-- 重命名书籍对话框 -->
    <van-dialog
      v-model:show="showRenameBookDialog"
      title="重命名书籍"
      show-cancel-button
      @confirm="handleRenameBook"
    >
      <van-field
        v-model="renameBookName"
        placeholder="请输入新名称"
        label="书籍名称"
      />
    </van-dialog>

    <!-- 修改分组名称对话框 -->
    <van-dialog
      v-model:show="showRenameGroupDialog"
      title="修改分组名称"
      show-cancel-button
      @confirm="handleRenameGroup"
    >
      <van-field
        v-model="renameGroupName"
        placeholder="请输入分组名称"
        label="分组名称"
      />
    </van-dialog>

    <!-- 移动到分组对话框 -->
    <van-popup v-model:show="showMoveDialog" position="bottom" round>
      <div class="move-dialog">
        <div class="move-dialog-header">
          <span>移动到分组</span>
          <i class="fas fa-xmark" @click="showMoveDialog = false" />
        </div>
        <div class="move-dialog-content">
          <van-radio-group v-model="selectedMoveCategory">
            <van-cell-group>
              <van-cell
                v-for="cat in categoriesForMove"
                :key="cat.id"
                clickable
                @click="selectedMoveCategory = cat.id"
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
          <van-button size="small" type="primary" plain @click="showAddGroupInMove = true">
            创建新分组
          </van-button>
          <van-button size="small" type="primary" :loading="movingBooks" loading-text="移动中..." @click="confirmMoveBooks">
            确定
          </van-button>
        </div>
        <van-field
          v-if="showAddGroupInMove"
          v-model="newGroupInMove"
          placeholder="输入新分组名称"
          @keyup.enter="createGroupInMove"
        >
          <template #button>
            <van-button size="small" type="primary" @click="createGroupInMove">创建</van-button>
          </template>
        </van-field>
      </div>
    </van-popup>

    <!-- 封面对话框 -->
    <CoverSettingsDialog v-model:show="showCoverDialog" @saved="onCoverSaved" />

    <!-- 独立编辑对话框 -->
    <BookEditDialog
      ref="bookEditDialogRef"
      v-model="showEditDialog"
      :book-id="currentBookId"
      :title="currentBookTitle"
      :initial-content="editContent"
      @saved="onEditSavedHandler"
      @closed="onEditClosedHandler"
    />

    <!-- 书籍右键菜单 -->
    <BookContextMenu
      v-model:show="showContextMenuPopup"
      :book="contextMenuBook"
      :is-multi-select="isMultiSelect"
      :selected-count="selectedBooks.length"
      :is-admin="authStore.isAdmin"
      @toggle-read="toggleBookReadStatus"
      @rename="openRenameBookDialog"
      @enable-multi-select="enableMultiSelect"
      @export="exportSingleBook"
      @move="openMoveDialog"
      @change-cover="openCoverDialogHandler"
      @delete="confirmDeleteBook"
    />

    <!-- 分组右键菜单 -->
    <GroupContextMenu
      v-model:show="showGroupContextMenuPopup"
      :group="contextMenuGroup"
      :position="groupContextMenuPos"
      :hide-read-books-map="hideReadBooksMap"
      @toggle-hide-read="toggleHideReadBooks"
      @rename="openRenameGroupDialog"
      @delete="confirmDeleteGroup"
    />

    <!-- 音频检查修复弹窗 -->
    <AudioFixDialog
      v-model:show="showAudioErrorDialog"
      :fixed-list="audioFixedList"
      :error-list="audioErrorList"
      @edit-book="handleEditBookFromAudioFix"
    />

    <!-- 补充翻译+中文语音进度弹窗 -->
    <van-dialog
      v-model:show="showSupplementProgress"
      title="补充翻译+中文语音"
      :close-on-click-overlay="false"
      :show-cancel-button="supplementLoading"
      :show-confirm-button="!supplementLoading"
      confirm-button-text="关闭"
      cancel-button-text="取消"
      @cancel="handleCancelSupplement"
    >
      <div class="supplement-progress-content">
        <van-progress
          :percentage="supplementProgress"
          :stroke-width="8"
          :show-pivot="true"
        />
        <div class="progress-message">
          {{ supplementMessage }}
        </div>
      </div>
    </van-dialog>

    <!-- 预编译缓存进度弹窗 -->
    <van-dialog
      v-model:show="showPrecompileProgress"
      title="预编译缓存"
      :close-on-click-overlay="false"
      :show-cancel-button="false"
      :show-confirm-button="!precompileLoading"
      confirm-button-text="关闭"
    >
      <div class="supplement-progress-content">
        <van-progress
          :percentage="precompileProgress"
          :stroke-width="8"
          :show-pivot="true"
        />
        <div class="progress-message">
          {{ precompileMessage }}
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showNotify, showToast, showLoadingToast, closeToast } from 'vant'
import { useAuthStore, api } from '@/store/auth'
import BookEditDialog from '@/components/BookEditDialog.vue'
import AudioFixDialog from '@/components/AudioFixDialog.vue'
import draggable from 'vuedraggable'

// 子组件
import BookList from './Home/components/BookList.vue'
import BookContextMenu from './Home/components/BookContextMenu.vue'
import GroupContextMenu from './Home/components/GroupContextMenu.vue'
import ImportDialog from './Home/components/ImportDialog.vue'
import CoverSettingsDialog from './Home/components/CoverSettingsDialog.vue'
// Composables
import { useGroupManagement } from './Home/composables/useGroupManagement'
import { useImport } from './Home/composables/useImport'
import { useExport } from './Home/composables/useExport'
import { useCover } from './Home/composables/useCover'

// 类型
import type { Book, BookGroup, PopoverAction } from './Home/types'

// 定义组件名称
defineOptions({
  name: 'Home'
})

const router = useRouter()
const authStore = useAuthStore()

// ========== 分组管理 Composable ==========
const {
  showAddGroupDialog,
  newGroupName,
  handleAddGroup,
  showSortGroupsDialog,
  sortableGroups,
  onEnterSortMode,
  onSaveGroupOrder: saveGroupOrderFromComposable,
  onCancelSortMode,
  showGroupContextMenuPopup,
  groupContextMenuPos,
  contextMenuGroup,
  showGroupContextMenu,
  closeGroupContextMenu,
  showRenameGroupDialog,
  renameGroupName,
  openRenameGroupDialog,
  handleRenameGroup,
  confirmDeleteGroup,
} = useGroupManagement()

// 保存分组排序（带刷新）
const handleSaveGroupOrder = async () => {
  const success = await saveGroupOrderFromComposable()
  if (success) {
    await loadGroups()
  }
}

// ========== 导出 Composable ==========
const {
  showExportProgressDialog,
  exportProgress,
  exportStatus,
  exportCurrentBook,
  exportSingleBook: doExportSingleBook,
  exportSelectedBooks: doExportSelectedBooks,
  setOnExportComplete,
} = useExport()

// 设置导出完成后退出多选模式
setOnExportComplete(() => {
  if (isMultiSelect.value && selectedBooks.value.length > 0) {
    selectedBooks.value = []
    isMultiSelect.value = false
  }
})

// ========== 封面 Composable ==========
const {
  showCoverDialog,
  openCoverDialog,
} = useCover()

// ========== TTS设置 Composable (首页不需要，由设置对话框按需加载) ==========

// ========== 词典设置 Composable (首页不需要，由设置对话框按需加载) ==========

// ========== 基础状态 ==========
const bookGroups = ref<BookGroup[]>([])
const loading = ref(false)
const searchText = ref('')
const activeNames = ref<number>(0)

// 导航栏状态
const showBookPopover = ref(false)
const showUserPopover = ref(false)
const showExpandPopover = ref(false)

// 多选模式
const isMultiSelect = ref(false)
const selectedBooks = ref<string[]>([])
const currentGroupId = ref(0)

// 书籍右键菜单
const showContextMenuPopup = ref(false)
const contextMenuPos = ref({ x: 0, y: 0 })
const contextMenuBook = ref<Book | null>(null)
const contextMenuGroupId = ref(0)

// 隐藏已读书籍状态
const hideReadBooksMap = ref<Record<number, boolean>>({})

// swipe-cell 引用
const swipeCellRefs = ref<Record<string, any>>({})

// 重命名书籍
const showRenameBookDialog = ref(false)
const renameBookName = ref('')

// 移动到分组
const showMoveDialog = ref(false)
const selectedMoveCategory = ref(0)
const categoriesForMove = ref<{ id: number; name: string }[]>([])
const showAddGroupInMove = ref(false)
const newGroupInMove = ref('')
const movingBooks = ref(false)

// 编辑相关
const showEditDialog = ref(false)
const editContent = ref('')
const currentBookTitle = ref('')
const currentBookId = ref('')
const bookEditDialogRef = ref<{ closeImagePreview: () => void } | null>(null)

// 封面错误缓存
const coverErrorMap = ref<Record<string, boolean>>({})

// 横屏状态
const isLandscape = ref(false)

// 音频修复
const showAudioErrorDialog = ref(false)
const audioErrorList = ref<any[]>([])
const audioFixedList = ref<any[]>([])
const isEditingFromAudioFix = ref(false)

// 预编译
const showPrecompileProgress = ref(false)
const precompileProgress = ref(0)
const precompileMessage = ref('')
const precompileLoading = ref(false)

// 补充翻译
const showSupplementProgress = ref(false)
const supplementProgress = ref(0)
const supplementMessage = ref('')
const supplementLoading = ref(false)

// ========== 计算属性 ==========

// 拓展功能菜单
const expandActions = computed<PopoverAction[]>(() => {
  const actions: PopoverAction[] = []
  actions.push({ text: '听书模式', icon: 'fa-music', key: 'audiobook' })
  actions.push({ text: '生词本', icon: 'fa-book', key: 'vocabulary' })
  actions.push({ text: '词典', icon: 'fa-search', key: 'dictionary' })
  return actions
})

// 书籍管理菜单
const bookActions = [
  { text: '添加分组', icon: 'plus', key: 'addGroup' },
  { text: '排序分组', icon: 'exchange', key: 'sortGroups' },
  { text: '收起所有分组', icon: 'shrink', key: 'collapseAll' }
]

// 用户菜单
const userActions = computed<PopoverAction[]>(() => {
  const actions: PopoverAction[] = []
  if (authStore.isAdmin) {
    actions.push({ text: '用户管理', icon: 'friends-o', key: 'users' })
  } else {
    actions.push({ text: '个人信息', icon: 'user-o', key: 'users' })
  }
  actions.push({ text: '退出登录', icon: 'logout', key: 'logout' })
  return actions
})

// ========== 方法 ==========

// 加载分组书籍数据
const loadGroups = async () => {
  loading.value = true
  try {
    coverErrorMap.value = {}
    const res = await api.get<BookGroup[]>('/categories/books/grouped')
    bookGroups.value = res.data
    if (bookGroups.value.length > 0 && activeNames.value === 0) {
      activeNames.value = bookGroups.value[0].id
    }
  } catch (error) {
    console.error('加载分组失败:', error)
    showNotify({ type: 'danger', message: '加载分组失败' })
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {}

// 获取可见书籍
const getVisibleBooks = (group: BookGroup): Book[] => {
  if (hideReadBooksMap.value[group.id]) {
    return group.books.filter(book => !book.is_read)
  }
  return group.books
}

// 菜单处理
const handlePopoverShow = (show: boolean, current: string) => {
  if (show) {
    if (current !== 'book') showBookPopover.value = false
    if (current !== 'user') showUserPopover.value = false
    if (current !== 'expand') showExpandPopover.value = false
  }
}

const onUserSelect = (action: PopoverAction) => {
  if (action.key === 'users') {
    router.push('/users')
  } else if (action.key === 'logout') {
    showConfirmDialog({
      title: '确认退出',
      message: '确定要退出登录吗？'
    }).then(() => {
      authStore.logout()
      showToast('已退出登录')
      router.push('/login')
    }).catch(() => {})
  }
}

// 拓展功能菜单
const onExpandSelect = async (action: PopoverAction) => {
  if (action.key === 'audiobook') {
    router.push('/audiobook')
  } else if (action.key === 'vocabulary') {
    router.push('/vocabulary')
  } else if (action.key === 'dictionary') {
    router.push('/dictionary')
  }
}

// 书籍管理菜单
const onBookActionSelect = (action: PopoverAction) => {
  if (action.key === 'addGroup') {
    showAddGroupDialog.value = true
  } else if (action.key === 'sortGroups') {
    onEnterSortMode(bookGroups.value)
  } else if (action.key === 'collapseAll') {
    activeNames.value = -1
  }
}

// 导入
const importState = useImport()
const { openImportDialog } = importState

// 书籍操作
const handleBookClick = (bookId: string, _groupId: number) => {
  if (isMultiSelect.value) {
    toggleBookSelect(bookId)
  } else {
    router.push(`/book/${bookId}`)
  }
}

const toggleBookSelect = (bookId: string) => {
  const index = selectedBooks.value.indexOf(bookId)
  if (index === -1) {
    selectedBooks.value.push(bookId)
  } else {
    selectedBooks.value.splice(index, 1)
  }
}

const showContextMenu = (_event: MouseEvent, book: Book, groupId: number) => {
  contextMenuBook.value = book
  contextMenuGroupId.value = groupId
  const menuWidth = 150
  const menuHeight = 280
  const x = (window.innerWidth - menuWidth) / 2
  const y = (window.innerHeight - menuHeight) / 2
  contextMenuPos.value = { x, y }
  showContextMenuPopup.value = true
}

// 多选模式
const enableMultiSelect = () => {
  showContextMenuPopup.value = false
  isMultiSelect.value = true
  if (contextMenuBook.value) {
    selectedBooks.value = [contextMenuBook.value.id]
  }
}

const cancelMultiSelect = () => {
  isMultiSelect.value = false
  selectedBooks.value = []
  currentGroupId.value = 0
}

const selectAllBooks = () => {
  const allIds: string[] = []
  for (const group of bookGroups.value) {
    for (const book of getVisibleBooks(group)) {
      allIds.push(book.id)
    }
  }
  if (isAllSelected.value) {
    selectedBooks.value = []
  } else {
    selectedBooks.value = allIds
  }
}

const isAllSelected = computed(() => {
  const allIds: string[] = []
  for (const group of bookGroups.value) {
    for (const book of getVisibleBooks(group)) {
      allIds.push(book.id)
    }
  }
  return allIds.length > 0 && allIds.every(id => selectedBooks.value.includes(id))
})

const selectAllBooksInCurrentGroup = () => {
  let targetGroup = bookGroups.value.find(g => g.id === activeNames.value)
  if (!targetGroup) {
    targetGroup = bookGroups.value.find(g => getVisibleBooks(g).length > 0)
  }
  if (targetGroup) {
    const groupBookIds = getVisibleBooks(targetGroup).map(b => b.id)
    selectedBooks.value = [...new Set([...selectedBooks.value, ...groupBookIds])]
  }
}

// 标记已读
const markBookAsRead = async (bookId: string, isRead: number) => {
  try {
    await api.post(`/categories/books/${bookId}/read-status`, { is_read: isRead })
    for (const group of bookGroups.value) {
      const book = group.books.find(b => b.id === bookId)
      if (book) {
        book.is_read = isRead
        break
      }
    }
    const swipeCell = swipeCellRefs.value[bookId]
    if (swipeCell && swipeCell.close) {
      swipeCell.close()
    }
    showNotify({ type: 'success', message: `已标记为${isRead ? '已读' : '未读'}`, duration: 1000 })
  } catch (error) {
    showNotify({ type: 'danger', message: '标记失败' })
  }
}

const toggleBookReadStatus = async () => {
  if (!contextMenuBook.value) return
  const newStatus = contextMenuBook.value.is_read ? 0 : 1
  await markBookAsRead(contextMenuBook.value.id, newStatus)
  showContextMenuPopup.value = false
}

// 重命名书籍
const openRenameBookDialog = () => {
  showContextMenuPopup.value = false
  if (contextMenuBook.value) {
    renameBookName.value = contextMenuBook.value.title
    showRenameBookDialog.value = true
  }
}

const handleRenameBook = async () => {
  if (!contextMenuBook.value || !renameBookName.value.trim()) {
    showNotify({ type: 'warning', message: '请输入书籍名称' })
    return
  }
  try {
    await api.put(`/books/${contextMenuBook.value.id}/rename`, {
      new_title: renameBookName.value.trim()
    })
    showNotify({ type: 'success', message: '书籍重命名成功', duration: 1500 })
    showRenameBookDialog.value = false
    coverErrorMap.value = {}
    await loadGroups()
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '重命名失败' })
  }
}

// 移动书籍
const openMoveDialog = () => {
  showContextMenuPopup.value = false
  // 如果已有多选书籍，使用选中的书籍列表
  if (isMultiSelect.value && selectedBooks.value.length > 0) {
    // 保持 selectedBooks 不变
  } else if (contextMenuBook.value) {
    // 否则使用当前右键点击的书
    selectedBooks.value = [contextMenuBook.value.id]
  }
  currentGroupId.value = contextMenuGroupId.value
  loadCategoriesForMove()
}

const loadCategoriesForMove = async () => {
  try {
    const res = await api.get<{ id: number; name: string }[]>('/categories')
    categoriesForMove.value = res.data.filter(c => {
      if (currentGroupId.value === 0) return c.id !== 0
      return c.id !== 0 && c.id !== currentGroupId.value
    })
    selectedMoveCategory.value = categoriesForMove.value.length > 0 ? categoriesForMove.value[0].id : 0
    showAddGroupInMove.value = false
    newGroupInMove.value = ''
    showMoveDialog.value = true
  } catch (error) {
    console.error('加载分组失败:', error)
  }
}

const batchMoveBooks = () => {
  currentGroupId.value = activeNames.value || 0
  loadCategoriesForMove()
}

const confirmMoveBooks = async () => {
  movingBooks.value = true
  try {
    if (showAddGroupInMove.value && newGroupInMove.value.trim()) {
      const res = await api.post<{ id: number }>('/categories', { name: newGroupInMove.value.trim() })
      selectedMoveCategory.value = res.data.id
    }
    const moveCount = selectedBooks.value.length
    for (const bookId of selectedBooks.value) {
      await api.post('/categories/books', { book_id: bookId, category_id: selectedMoveCategory.value })
    }
    const moveMsg = moveCount > 1 ? `批量移动成功 (${moveCount} 本)` : '移动成功'
    showNotify({ type: 'success', message: moveMsg, duration: 1500 })
    showMoveDialog.value = false
    // 批量移动后不清除选择状态，让用户可以继续批量操作
    if (moveCount <= 1) {
      selectedBooks.value = []
      isMultiSelect.value = false
    }
    await loadGroups()
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '移动失败' })
  } finally {
    movingBooks.value = false
  }
}

const createGroupInMove = async () => {
  if (!newGroupInMove.value.trim()) {
    showNotify({ type: 'warning', message: '请输入分组名称' })
    return
  }
  try {
    const res = await api.post<{ id: number; name: string }>('/categories', { name: newGroupInMove.value.trim() })
    categoriesForMove.value.push(res.data)
    selectedMoveCategory.value = res.data.id
    showAddGroupInMove.value = false
    newGroupInMove.value = ''
    showNotify({ type: 'success', message: '分组创建成功', duration: 1500 })
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '创建分组失败' })
  }
}

// 封面
const openCoverDialogHandler = async () => {
  showContextMenuPopup.value = false
  if (contextMenuBook.value) {
    await openCoverDialog(contextMenuBook.value)
  }
}

const onCoverSaved = async () => {
  await loadGroups()
}

const exportSingleBook = () => {
  showContextMenuPopup.value = false
  // 如果已有多选书籍，导出所有选中的
  if (isMultiSelect.value && selectedBooks.value.length > 0) {
    doExportSelectedBooks(selectedBooks.value)
  } else if (contextMenuBook.value) {
    // 否则导出当前右键点击的书
    doExportSingleBook(contextMenuBook.value.id)
  }
}

const exportSelectedBooks = () => {
  doExportSelectedBooks(selectedBooks.value)
}

// 删除书籍
const confirmDeleteBook = async () => {
  showContextMenuPopup.value = false
  
  // 如果已有多选书籍，调用批量删除
  if (isMultiSelect.value && selectedBooks.value.length > 0) {
    await batchDeleteBooks()
    return
  }
  
  // 单本书删除
  if (!contextMenuBook.value) return
  const confirm = await showConfirmDialog({
    title: '确认删除',
    message: `确定要删除《${contextMenuBook.value.title}》吗？此操作不可恢复！`
  }).catch(() => null)
  if (!confirm) return
  try {
    bookGroups.value = bookGroups.value.map(group => ({
      ...group,
      books: group.books.filter(book => book.id !== contextMenuBook.value!.id)
    })).filter(group => group.books.length > 0)
    await api.delete(`/books/${contextMenuBook.value.id}`)
    showNotify({ type: 'success', message: '删除成功', duration: 1500 })
    await loadGroups()
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
    await loadGroups()
  }
}

const batchDeleteBooks = async () => {
  const confirm = await showConfirmDialog({
    title: '确认删除',
    message: `确定要删除选中的 ${selectedBooks.value.length} 本书籍吗？此操作不可恢复！`
  }).catch(() => null)
  if (!confirm) return
  try {
    const deletedBookIds = new Set(selectedBooks.value)
    bookGroups.value = bookGroups.value.map(group => ({
      ...group,
      books: group.books.filter(book => !deletedBookIds.has(book.id))
    })).filter(group => group.books.length > 0)
    for (const bookId of selectedBooks.value) {
      await api.delete(`/books/${bookId}`)
    }
    showNotify({ type: 'success', message: '删除成功', duration: 1500 })
    selectedBooks.value = []
    isMultiSelect.value = false
    await loadGroups()
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
    await loadGroups()
  }
}

// 分组右键菜单操作
const toggleHideReadBooks = async () => {
  if (contextMenuGroup.value) {
    const groupId = contextMenuGroup.value.id
    hideReadBooksMap.value[groupId] = !hideReadBooksMap.value[groupId]
    try {
      await api.put('/settings/ui', { hide_read_books_map: hideReadBooksMap.value })
    } catch (error) {
      showNotify({ type: 'danger', message: '保存设置失败', duration: 1500 })
    }
  }
  closeGroupContextMenu()
}

// 编辑相关
const handleEditBook = (bookId: string) => {
  currentBookId.value = bookId
  showLoadingToast({ message: '加载中...', forbidClick: true })
  api.get<{ title: string }>(`/books/${bookId}`).then(res => {
    currentBookTitle.value = res.data.title
    return api.get<{ content: string }>(`/books/${bookId}/content`)
  }).then(res => {
    editContent.value = res.data.content
    closeToast()
    showEditDialog.value = true
  }).catch(error => {
    console.error('加载书籍内容失败:', error)
    closeToast()
    showNotify({ type: 'danger', message: '加载书籍内容失败' })
  })
}

const handleEditBookFromAudioFix = async (bookId: string) => {
  isEditingFromAudioFix.value = true
  showAudioErrorDialog.value = false
  await handleEditBook(bookId)
}

const onEditSavedHandler = async () => {
  if (isEditingFromAudioFix.value) {
    await loadGroups()
  } else {
    onEditSaved()
  }
}

const onEditSaved = () => {
  loadGroups()
}

const onEditClosedHandler = async () => {
  if (isEditingFromAudioFix.value) {
    isEditingFromAudioFix.value = false
    await onEditSavedAndRefreshAudio()
  }
}

const onEditSavedAndRefreshAudio = async () => {
  await loadGroups()
  showLoadingToast({ message: '正在重新检查语音配置...', forbidClick: true, duration: 0 })
  try {
    const res = await api.post('/books/sync')
    closeToast()
    audioFixedList.value = res.data.audio_fixed || []
    audioErrorList.value = res.data.audio_errors || []
    if (audioFixedList.value.length > 0 || audioErrorList.value.length > 0) {
      showAudioErrorDialog.value = true
    }
  } catch (error) {
    closeToast()
    showNotify({ type: 'danger', message: '重新检查音频失败' })
  }
}

// 管理员功能已迁移到设置页面

// 保留取消补充翻译功能（供弹窗使用）
const handleCancelSupplement = async () => {
  try {
    await api.post('/books/admin/books/supplement-all/cancel')
    supplementMessage.value = '正在取消...'
  } catch (error) {}
}

// 屏幕方向检测
const checkOrientation = () => {
  isLandscape.value = window.innerWidth > window.innerHeight
}

const handleResize = () => {
  checkOrientation()
}

// 浏览器导航
const handleBrowserNavigation = () => {
  if (showEditDialog.value) {
    bookEditDialogRef.value?.closeImagePreview()
    showEditDialog.value = false
    onEditClosedHandler()
  }
}

const handleCloseNavMenus = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  const navActions = target.closest('.nav-actions')
  const inPopover = target.closest('.van-popover')
  if (!navActions && !inPopover) {
    showBookPopover.value = false
    showUserPopover.value = false
    showExpandPopover.value = false
  }
}

// 设置回调（已迁移到设置页面）

// 生命周期
onMounted(async () => {
  checkOrientation()
  window.addEventListener('resize', handleResize)
  window.addEventListener('click', handleCloseNavMenus)
  window.addEventListener('popstate', handleBrowserNavigation)
  // 首页只需加载书籍分组数据
  // TTS设置和词典设置延迟到用户打开设置对话框时按需加载
  await loadGroups()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('click', handleCloseNavMenus)
  window.removeEventListener('popstate', handleBrowserNavigation)
})

// 监听编辑弹窗状态管理浏览器历史
watch(showEditDialog, (newVal) => {
  if (newVal) {
    window.history.pushState({ openEditDialog: true, bookId: currentBookId.value }, '')
  } else {
    window.history.replaceState(null, '', window.location.pathname)
  }
})

// 监听导入完成，自动刷新书籍列表
watch(() => importState.importCompleted.value, async (completed) => {
  if (completed) {
    importState.importCompleted.value = false
    await loadGroups()
  }
})
</script>

<style scoped>
.home {
  min-height: 100vh;
  background: #f7f8fa;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
  -webkit-tap-highlight-color: transparent;
}

.nav-search {
  display: flex;
  align-items: center;
  background: #f7f8fa;
  border-radius: 20px;
  padding: 4px 12px;
  width: 140px;
}

@media (max-width: 375px) {
  .nav-search {
    width: 120px;
  }
}

.search-icon {
  color: #969799;
  margin-right: 6px;
  font-size: 16px;
}

.search-input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 14px;
  width: 100%;
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  font-size: 20px;
  color: #1989fa;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.nav-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}

.nav-actions {
  display: flex;
  align-items: center;
  -webkit-tap-highlight-color: transparent;
  gap: 8px;
}

@media (max-width: 375px) {
  .nav-actions {
    gap: 4px;
  }
}

.username-link {
  font-size: 14px;
  color: #333;
  margin: 0 8px;
  cursor: pointer;
}

.username-link:hover {
  color: #1989fa;
}

/* 设置菜单项图标样式 */
.settings-action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.settings-action-item .fas {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

.content {
  padding-bottom: 50px;
}

/* 导出进度 */
.export-progress-content {
  padding: 24px 20px;
  text-align: center;
}

.export-status {
  margin-top: 16px;
  font-size: 14px;
  color: #323233;
  font-weight: 500;
}

.export-current-book {
  margin-top: 8px;
  font-size: 12px;
  color: #969799;
  word-break: break-all;
}

/* 分组排序 */
.sort-groups-container {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
}

.sort-group-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: move;
}

.sort-group-item.is-uncategorized {
  background: #e8f0fe;
  cursor: not-allowed;
}

.sort-group-item .drag-handle {
  margin-right: 12px;
  color: #969799;
  font-size: 18px;
}

.sort-group-item.is-uncategorized .drag-handle {
  color: #1989fa;
}

.sort-group-item .group-name {
  flex: 1;
  font-size: 14px;
  color: #323233;
}

.sort-group-item .fixed-label {
  font-size: 12px;
  color: #969799;
}

.sort-ghost {
  opacity: 0.5;
  background: #c8c9cc;
}

.sort-drag {
  opacity: 0.8;
  background: #e8f0fe;
}

/* 移动对话框 */
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

/* 补充进度 */
.supplement-progress-content {
  padding: 24px 16px;
}

.progress-message {
  text-align: center;
  font-size: 14px;
  color: #646566;
  word-break: break-all;
  min-height: 20px;
}
</style>
