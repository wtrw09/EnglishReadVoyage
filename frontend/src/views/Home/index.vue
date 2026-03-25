<template>
  <div class="home">
    <!-- 顶部导航栏 -->
    <van-nav-bar fixed placeholder>
      <template #left>
        <div class="nav-left">
          <div class="nav-search">
            <van-icon name="search" class="search-icon" />
            <input
              v-model="bookGroupsState.searchText"
              type="text"
              placeholder="搜索书籍..."
              class="search-input"
            />
          </div>
          <van-icon
            v-if="authStore.isAdmin"
            name="plus"
            class="nav-icon"
            @click="bookImport.openImportDialog(0)"
          />
        </div>
      </template>
      <template #right>
        <div class="nav-actions">
          <NavPopover
            v-model:show="showBookPopover"
            :actions="bookActions"
            @select="onBookActionSelect"
          >
            <van-icon name="bars" class="nav-icon" />
          </NavPopover>
          <NavPopover
            v-model:show="showUserPopover"
            :actions="userActions"
            @select="onUserSelect"
          >
            <span class="username-link">{{ authStore.user?.username || '用户' }}</span>
          </NavPopover>
          <NavPopover
            v-model:show="showSettingsPopover"
            :actions="settingsActions"
            @select="onSettingsSelect"
          >
            <van-icon name="setting-o" class="nav-icon" />
          </NavPopover>
        </div>
      </template>
    </van-nav-bar>

    <!-- 内容区域 -->
    <div class="content">
      <van-collapse v-model="bookGroupsState.activeNames.value" accordion>
        <van-collapse-item
          v-for="group in bookGroupsState.filteredGroups.value"
          :key="group.id"
          :name="group.id"
          class="group-item"
          v-show="group.name !== '未分组' || group.books.length > 0"
        >
          <template #title>
            <GroupTitle
              :group="group"
              :is-multi-select="bookSelection.isMultiSelect.value"
              :is-selected="bookSelection.isGroupAllSelected(group)"
              @toggle-select="bookSelection.toggleGroupSelect(group)"
              @contextmenu="(e) => contextMenu.showGroupMenu(group, e)"
            />
          </template>
          <template #right-icon>
            <div class="group-actions" @click.stop>
              <van-button
                v-if="authStore.isAdmin"
                type="primary"
                size="small"
                icon="plus"
                class="group-import-btn"
                @click="bookImport.openImportDialog(group.id)"
              />
            </div>
          </template>

          <!-- 书籍列表 -->
          <BookList
            :books="bookGroupsState.getVisibleBooks(group)"
            :is-multi-select="bookSelection.isMultiSelect.value"
            :selected-books="bookSelection.selectedBooks.value"
            :group-id="group.id"
            @toggle-select="bookSelection.toggleBookSelect"
            @click="(book: Book) => handleBookClick(book, group.id)"
            @contextmenu="(book: Book, e: MouseEvent) => contextMenu.showBookMenu(book, group.id, e)"
            @swipe-read="(bookId: string) => bookGroupsState.markBookAsRead(bookId, 1)"
            @swipe-unread="(bookId: string) => bookGroupsState.markBookAsRead(bookId, 0)"
          />
        </van-collapse-item>
      </van-collapse>

      <!-- 批量操作栏 -->
      <BatchActionBar
        v-if="bookSelection.isMultiSelect.value"
        :selected-count="bookSelection.selectedCount.value"
        :is-all-selected="bookSelection.isAllSelected.value"
        :is-admin="authStore.isAdmin"
        @select-all="onSelectAll"
        @select-group="onSelectGroup"
        @export="onExportSelected"
        @move="onMoveBooks"
        @delete="onBatchDelete"
        @cancel="bookSelection.cancelMultiSelect()"
      />

      <!-- 空状态 -->
      <van-empty
        v-if="bookGroupsState.filteredGroups.value.length === 0 && !bookGroupsState.loading.value"
        description="暂无书籍"
      />
    </div>

    <!-- 导入对话框 -->
    <ImportDialog
      v-model:show="bookImport.showImportDialog.value"
      :is-importing="bookImport.importing.value"
      :import-completed="bookImport.importCompleted.value"
      :upload-progress="bookImport.uploadProgress.value"
      :import-progress="bookImport.importProgress.value"
      :upload-status="bookImport.uploadStatus.value"
      :import-status="bookImport.importStatus.value"
      :selected-file="bookImport.selectedFile.value"
      :selected-files="bookImport.selectedFiles.value"
      @file-select="bookImport.onFileSelected"
      @file-drop="bookImport.onFileDrop"
      @confirm="bookImport.handleImportConfirm"
      @closed="bookImport.resetState"
    />

    <!-- 重复书籍对话框 -->
    <DuplicateDialog
      v-model:show="bookImport.showDuplicateDialog.value"
      v-model:selected-books="bookImport.selectedDuplicateBooks.value"
      :result="bookImport.duplicateCheckResult.value"
      @overwrite-all="bookImport.handleImportWithOverwrite"
      @skip-all="bookImport.handleImportSkipDuplicates"
      @import-selected="bookImport.handleImportSelected"
      @cancel="bookImport.cancelImport"
    />

    <!-- 导出进度对话框 -->
    <van-dialog
      v-model:show="bookExport.showExportProgressDialog.value"
      title="导出书籍"
      :show-confirm-button="false"
      :show-cancel-button="false"
      :close-on-click-overlay="false"
    >
      <div class="export-progress-content">
        <van-progress
          :percentage="bookExport.exportProgress.value"
          :stroke-width="10"
          :show-pivot="true"
        />
        <p class="export-status">{{ bookExport.exportStatus.value }}</p>
        <p v-if="bookExport.exportCurrentBook.value" class="export-current-book">
          {{ bookExport.exportCurrentBook.value }}
        </p>
      </div>
    </van-dialog>

    <!-- 移动到分组对话框 -->
    <MoveDialog
      v-model:show="showMoveDialog"
      :categories="categoriesForMove"
      :is-moving="isMoving"
      @confirm="onConfirmMove"
      @create-group="onCreateGroupInMove"
    />

    <!-- 书籍右键菜单 -->
    <van-popup
      v-model:show="contextMenu.showBookContextMenu.value"
      :style="{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }"
      round
      class="context-menu"
    >
      <van-cell-group>
        <van-cell
          :title="contextMenu.contextMenuBook.value?.is_read ? '标记为未读' : '标记为已读'"
          clickable
          @click="onToggleBookReadStatus"
        />
        <van-cell title="重命名" clickable @click="showRenameBookDialog = true" />
        <van-cell
          title="选择更多"
          clickable
          @click="onEnableMultiSelect"
          v-if="!bookSelection.isMultiSelect.value"
        />
        <van-cell title="导出书籍" clickable @click="onExportSingleBook" />
        <van-cell title="移动到其他分组" clickable @click="onOpenMoveDialog" />
        <van-cell title="修改封面" clickable @click="onOpenCoverDialog" />
        <van-cell
          title="删除"
          clickable
          @click="onDeleteBook"
          v-if="authStore.isAdmin"
        />
      </van-cell-group>
    </van-popup>

    <!-- 分组右键菜单 -->
    <van-popup
      v-model:show="contextMenu.showGroupContextMenu.value"
      :style="{ top: contextMenu.groupContextMenuPos.value.y + 'px', left: contextMenu.groupContextMenuPos.value.x + 'px' }"
      round
      class="context-menu"
    >
      <van-cell-group>
        <van-cell
          :title="isHideReadBooks ? '显示已读书籍' : '隐藏已读书籍'"
          clickable
          @click="onToggleHideReadBooks"
        />
        <van-cell
          title="修改名称"
          clickable
          @click="showRenameGroupDialog = true"
          v-if="canRenameGroup"
        />
        <van-cell
          title="删除分组"
          clickable
          @click="onDeleteGroup"
          v-if="canDeleteGroup"
        />
      </van-cell-group>
    </van-popup>

    <!-- 添加分组对话框 -->
    <van-dialog
      v-model:show="showAddGroupDialog"
      title="添加分组"
      show-cancel-button
      @confirm="onAddGroup"
    >
      <van-field v-model="newGroupName" placeholder="请输入分组名称" label="分组名称" />
    </van-dialog>

    <!-- 重命名分组对话框 -->
    <van-dialog
      v-model:show="showRenameGroupDialog"
      title="修改分组名称"
      show-cancel-button
      @confirm="onRenameGroup"
    >
      <van-field v-model="renameGroupName" placeholder="请输入分组名称" label="分组名称" />
    </van-dialog>

    <!-- 重命名书籍对话框 -->
    <van-dialog
      v-model:show="showRenameBookDialog"
      title="重命名书籍"
      show-cancel-button
      @confirm="onRenameBook"
    >
      <van-field v-model="renameBookName" placeholder="请输入新名称" label="书籍名称" />
    </van-dialog>

    <!-- 修改封面对话框 -->
    <CoverDialog
      v-model:show="showCoverDialog"
      v-model:preview-image="previewCover"
      :images="mdImages"
      @upload="onCoverUpload"
      @confirm="onSaveCover"
    />

    <!-- TTS设置对话框 -->
    <TtsSettingsDialog
      v-model:show="ttsSettings.showTtsSettingsDialog.value"
      v-model:service-name="ttsSettings.ttsServiceName.value"
      v-model:voice="ttsSettings.ttsVoice.value"
      v-model:speed="ttsSettings.ttsSpeed.value"
      v-model:api-url="ttsSettings.ttsApiUrl.value"
      v-model:app-id="ttsSettings.ttsAppId.value"
      v-model:access-key="ttsSettings.ttsAccessKey.value"
      v-model:resource-id="ttsSettings.ttsResourceId.value"
      v-model:silicon-flow-api-key="ttsSettings.ttsSiliconFlowApiKey.value"
      v-model:silicon-flow-model="ttsSettings.ttsSiliconFlowModel.value"
      v-model:minimax-api-key="ttsSettings.ttsMinimaxApiKey.value"
      v-model:minimax-model="ttsSettings.ttsMinimaxModel.value"
      :available-voices="ttsSettings.availableVoices.value"
      :supports-speed="ttsSettings.supportsSpeed.value"
      :speed-range="ttsSettings.speedRange.value"
      :siliconflow-models="ttsSettings.siliconflowModels"
      :is-testing="ttsSettings.ttsTesting.value"
      :is-checking-usage="ttsSettings.minimaxUsageChecking.value"
      :test-text="ttsSettings.ttsTestText"
      @confirm="onSaveTtsSettings"
      @test="ttsSettings.testTts()"
      @check-usage="ttsSettings.checkMinimaxUsage()"
    />

    <!-- 词典设置对话框 -->
    <DictionarySettingsDialog
      v-model:show="showDictionarySettingsDialog"
      v-model:source="dictionarySource"
      :ecdict-available="ecdictAvailable"
      :is-admin="authStore.isAdmin"
      :translation-apis="translationApis"
      @save="onSaveDictionarySettings"
      @add-api="onAddTranslationApi"
      @delete-api="onDeleteTranslationApi"
    />

    <!-- 音标设置对话框 -->
    <PhoneticSettingsDialog
      v-model:show="showPhoneticSettingsDialog"
      v-model:accent="phoneticAccent"
      @save="onSavePhoneticSettings"
    />

    <!-- 音频修复对话框 -->
    <AudioFixDialog
      v-model:show="showAudioFixDialog"
      :fixed-list="audioFixedList"
      :error-list="audioErrorList"
      @edit-book="onEditBookFromAudioFix"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showNotify, showToast } from 'vant'
import { useAuthStore } from '@/store/auth'
import { api } from '@/store/auth'
import type { Book, PopoverAction, AudioErrorItem, AudioFixedItem } from '@/types'

// Composables
import { useBookImport } from './composables/useBookImport'
import { useBookExport } from './composables/useBookExport'
import { useBookSelection } from './composables/useBookSelection'
import { useBookGroups } from './composables/useBookGroups'
import { useTtsSettings } from './composables/useTtsSettings'
import { useContextMenu } from './composables/useContextMenu'

// Components
import NavPopover from './components/NavPopover.vue'
import GroupTitle from './components/GroupTitle.vue'
import BookList from './components/BookList.vue'
import BatchActionBar from './components/BatchActionBar.vue'
import ImportDialog from './components/dialogs/ImportDialog.vue'
import DuplicateDialog from './components/dialogs/DuplicateDialog.vue'
import MoveDialog from './components/dialogs/MoveDialog.vue'
import CoverDialog from './components/dialogs/CoverDialog.vue'
import TtsSettingsDialog from './components/dialogs/settings/TtsSettingsDialog.vue'
import DictionarySettingsDialog from './components/dialogs/settings/DictionarySettingsDialog.vue'
import PhoneticSettingsDialog from './components/dialogs/settings/PhoneticSettingsDialog.vue'
import AudioFixDialog from '@/components/AudioFixDialog.vue'

defineOptions({ name: 'Home' })

const router = useRouter()
const authStore = useAuthStore()

// 使用composables
const bookImport = useBookImport()
const bookExport = useBookExport()
const bookGroupsState = useBookGroups()
const bookSelection = useBookSelection({
  getVisibleBooks: bookGroupsState.getVisibleBooks
})
const ttsSettings = useTtsSettings()
const contextMenu = useContextMenu()

// 导航栏菜单状态
const showBookPopover = ref(false)
const showUserPopover = ref(false)
const showSettingsPopover = ref(false)

// 对话框状态
const showMoveDialog = ref(false)
const showAddGroupDialog = ref(false)
const showRenameGroupDialog = ref(false)
const showRenameBookDialog = ref(false)
const showCoverDialog = ref(false)
const showDictionarySettingsDialog = ref(false)
const showPhoneticSettingsDialog = ref(false)
const showAudioFixDialog = ref(false)

// 表单数据
const newGroupName = ref('')
const renameGroupName = ref('')
const renameBookName = ref('')
const previewCover = ref('')
const mdImages = ref<string[]>([])
const isMoving = ref(false)
const categoriesForMove = ref<{ id: number; name: string }[]>([])

// 词典设置
const dictionarySource = ref<'api' | 'local'>('local')
const ecdictAvailable = ref(false)
const translationApis = ref<{ id: number; app_id: string; is_active: boolean }[]>([])

// 音标设置
const phoneticAccent = ref<'uk' | 'us'>('uk')

// 音频修复
const audioFixedList = ref<AudioFixedItem[]>([])
const audioErrorList = ref<AudioErrorItem[]>([])
const isEditingFromAudioFix = ref(false)

// 计算属性
const bookActions: PopoverAction[] = [
  { text: '添加分组', icon: 'plus', key: 'addGroup' },
  { text: '收起所有分组', icon: 'shrink', key: 'collapseAll' }
]

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

const settingsActions = computed<PopoverAction[]>(() => {
  const actions: PopoverAction[] = [
    { text: '听书模式', icon: 'music-o', key: 'audiobook' },
    { text: '生词本', icon: 'records-o', key: 'vocabulary' },
    { text: '词典设置', icon: 'bookmark-o', key: 'dictionarySettings' }
  ]

  if (authStore.isAdmin) {
    actions.push(
      { text: '朗读设置', icon: 'volume-o', key: 'ttsSettings' },
      { text: '音标设置', icon: 'font-o', key: 'phoneticSettings' },
      { text: '修复书籍数据', icon: 'replay', key: 'syncBooks' },
      { text: '压缩书籍图片', icon: 'photo-o', key: 'compressImages' }
    )
  }

  return actions
})

const isHideReadBooks = computed(() => {
  const group = contextMenu.contextMenuGroup.value
  return group ? bookGroupsState.hideReadBooksMap.value[group.id] : false
})

const canRenameGroup = computed(() => {
  const group = contextMenu.contextMenuGroup.value
  return group && group.id !== 0 && group.name !== '未分组'
})

const canDeleteGroup = computed(() => {
  const group = contextMenu.contextMenuGroup.value
  return group && group.id !== 0 && group.name !== '未分组'
})

// 方法
const handleBookClick = (book: Book, _groupId: number) => {
  if (bookSelection.isMultiSelect.value) {
    bookSelection.toggleBookSelect(book.id)
  } else {
    router.push(`/book/${book.id}`)
  }
}

const onSelectAll = () => {
  const allIds = bookGroupsState.filteredGroups.value.flatMap(g =>
    bookGroupsState.getVisibleBooks(g).map(b => b.id)
  )
  bookSelection.selectAllBooks(allIds)
}

const onSelectGroup = () => {
  const activeGroup = bookGroupsState.filteredGroups.value.find(
    g => g.id === bookGroupsState.activeNames.value
  )
  if (activeGroup) {
    bookSelection.selectAllBooksInGroup(activeGroup)
  }
}

const onExportSelected = async () => {
  if (bookSelection.selectedBooks.value.length === 0) {
    showNotify({ type: 'warning', message: '请先选择要导出的书籍' })
    return
  }
  await bookExport.exportBooks(bookSelection.selectedBooks.value)
  bookSelection.cancelMultiSelect()
}

const onExportSingleBook = async () => {
  const book = contextMenu.contextMenuBook.value
  if (book) {
    contextMenu.closeBookMenu()
    await bookExport.exportBooks([book.id])
  }
}

const onMoveBooks = async () => {
  if (bookSelection.selectedBooks.value.length === 0) return

  try {
    const res = await api.get<{ id: number; name: string }[]>('/categories')
    const currentGroupId = bookSelection.currentGroupId.value
    categoriesForMove.value = res.data.filter(c => c.id !== 0 && c.id !== currentGroupId)
    showMoveDialog.value = true
  } catch (error) {
    console.error('加载分组失败:', error)
  }
}

const onOpenMoveDialog = async () => {
  const book = contextMenu.contextMenuBook.value
  if (book) {
    bookSelection.selectedBooks.value = [book.id]
    bookSelection.currentGroupId.value = contextMenu.contextMenuGroupId.value
    contextMenu.closeBookMenu()
    await onMoveBooks()
  }
}

const onConfirmMove = async (categoryId: number) => {
  isMoving.value = true
  try {
    const success = await bookGroupsState.moveBooksToCategory(
      bookSelection.selectedBooks.value,
      categoryId
    )
    if (success) {
      showMoveDialog.value = false
      bookSelection.cancelMultiSelect()
    }
  } finally {
    isMoving.value = false
  }
}

const onCreateGroupInMove = async (name: string) => {
  const success = await bookGroupsState.addGroup(name)
  if (success) {
    const res = await api.get<{ id: number; name: string }[]>('/categories')
    const currentGroupId = bookSelection.currentGroupId.value
    categoriesForMove.value = res.data.filter(c => c.id !== 0 && c.id !== currentGroupId)
  }
}

const onBatchDelete = async () => {
  const success = await bookGroupsState.batchDeleteBooks(bookSelection.selectedBooks.value)
  if (success) {
    bookSelection.cancelMultiSelect()
  }
}

const onDeleteBook = async () => {
  const book = contextMenu.contextMenuBook.value
  if (book) {
    contextMenu.closeBookMenu()
    await bookGroupsState.deleteBook(book.id, book.title)
  }
}

const onToggleBookReadStatus = async () => {
  const book = contextMenu.contextMenuBook.value
  if (book) {
    const newStatus = book.is_read ? 0 : 1
    await bookGroupsState.markBookAsRead(book.id, newStatus)
    contextMenu.closeBookMenu()
  }
}

const onEnableMultiSelect = () => {
  const book = contextMenu.contextMenuBook.value
  if (book) {
    bookSelection.enableMultiSelect(book.id, contextMenu.contextMenuGroupId.value)
    contextMenu.closeBookMenu()
  }
}

const onToggleHideReadBooks = async () => {
  const group = contextMenu.contextMenuGroup.value
  if (group) {
    await bookGroupsState.toggleHideReadBooks(group.id)
    contextMenu.closeGroupMenu()
  }
}

const onAddGroup = async () => {
  await bookGroupsState.addGroup(newGroupName.value)
  newGroupName.value = ''
}

const onRenameGroup = async () => {
  const group = contextMenu.contextMenuGroup.value
  if (group) {
    await bookGroupsState.renameGroup(group.id, renameGroupName.value)
    renameGroupName.value = ''
  }
}

const onDeleteGroup = async () => {
  const group = contextMenu.contextMenuGroup.value
  if (group) {
    contextMenu.closeGroupMenu()
    await bookGroupsState.deleteGroup(group.id, group.name)
  }
}

const onRenameBook = async () => {
  const book = contextMenu.contextMenuBook.value
  if (book) {
    await bookGroupsState.renameBook(book.id, renameBookName.value, book.title)
    renameBookName.value = ''
    contextMenu.closeBookMenu()
  }
}

const onOpenCoverDialog = async () => {
  const book = contextMenu.contextMenuBook.value
  if (!book) return

  contextMenu.closeBookMenu()
  previewCover.value = bookGroupsState.getBookCover(book) || ''
  mdImages.value = []
  showCoverDialog.value = true

  // 加载书籍图片
  try {
    const bookRes = await api.get<{ book_path: string }>(`/books/${book.id}`)
    const contentRes = await api.get<{ content: string }>(`/books/${book.id}/content-file`)
    const content = contentRes.data.content

    // 提取markdown中的图片
    const matches = content.match(/!\[[^\]]*\]\(([^)]+)\)/g) || []
    const images: string[] = []

    for (const match of matches) {
      const urlMatch = match.match(/!\[[^\]]*\]\(([^)]+)\)/)
      if (urlMatch) {
        const url = urlMatch[1]
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
          let resultUrl = url
          if (url.startsWith('./assets/')) {
            resultUrl = `/books/${bookRes.data.book_path}/assets/${url.replace('./assets/', '')}`
          } else if (url.startsWith('assets/')) {
            resultUrl = `/books/${bookRes.data.book_path}/assets/${url.replace('assets/', '')}`
          } else {
            resultUrl = `/books/${bookRes.data.book_path}/assets/${url}`
          }
          images.push(resultUrl)
        }
      }
    }
    mdImages.value = images
  } catch (error) {
    console.error('加载书籍图片失败:', error)
  }
}

const onCoverUpload = (file: File) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    previewCover.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
}

const onSaveCover = async () => {
  const book = contextMenu.contextMenuBook.value
  if (!book) return

  try {
    let coverPath = previewCover.value

    if (coverPath.startsWith('data:')) {
      const res = await fetch(coverPath)
      const blob = await res.blob()
      const formData = new FormData()
      formData.append('file', blob, 'cover.webp')

      const uploadRes = await fetch(`/api/v1/books/upload-cover?book_id=${book.id}`, {
        method: 'POST',
        body: formData,
        headers: { 'Authorization': `Bearer ${authStore.token}` }
      })
      const uploadData = await uploadRes.json()
      coverPath = uploadData.path
    }

    await api.put(`/books/${book.id}/cover`, { cover_path: coverPath })
    showNotify({ type: 'success', message: '封面保存成功', duration: 1500 })
    showCoverDialog.value = false
    await bookGroupsState.loadGroups()
  } catch (error: any) {
    console.error('保存封面失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '保存封面失败' })
  }
}

const onSaveTtsSettings = async () => {
  const success = await ttsSettings.saveTtsSettings()
  if (success) {
    ttsSettings.showTtsSettingsDialog.value = false
  }
}

const onSaveDictionarySettings = async () => {
  try {
    await api.put('/settings/dictionary', { dictionary_source: dictionarySource.value })
    showNotify({ type: 'success', message: '词典设置已保存', duration: 1500 })
    showDictionarySettingsDialog.value = false
  } catch (error: any) {
    console.error('保存词典设置失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
  }
}

const onSavePhoneticSettings = async () => {
  try {
    await api.put('/settings/phonetic', { accent: phoneticAccent.value })
    showNotify({ type: 'success', message: '音标设置已保存', duration: 1500 })
    showPhoneticSettingsDialog.value = false
  } catch (error: any) {
    console.error('保存音标设置失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
  }
}

const onAddTranslationApi = async (appId: string, appKey: string) => {
  try {
    await api.post('/translation/apis', {
      name: '百度翻译',
      app_id: appId,
      app_key: appKey,
      is_active: true
    })
    showNotify({ type: 'success', message: '百度翻译API已添加', duration: 1500 })
    await loadTranslationSettings()
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '添加失败' })
  }
}

const onDeleteTranslationApi = async (apiId: number) => {
  try {
    await api.delete(`/translation/apis/${apiId}`)
    showNotify({ type: 'success', message: '翻译API已删除', duration: 1500 })
    await loadTranslationSettings()
  } catch (error: any) {
    showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
  }
}

const loadTranslationSettings = async () => {
  try {
    const res = await api.get('/translation/settings')
    translationApis.value = res.data.apis || []
  } catch (error) {
    console.error('加载翻译设置失败:', error)
  }
}

// 导航菜单处理
const onBookActionSelect = (action: PopoverAction) => {
  if (action.key === 'addGroup') {
    showAddGroupDialog.value = true
  } else if (action.key === 'collapseAll') {
    bookGroupsState.activeNames.value = -1
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

const onSettingsSelect = async (action: PopoverAction) => {
  switch (action.key) {
    case 'audiobook':
      router.push('/audiobook')
      break
    case 'vocabulary':
      router.push('/vocabulary')
      break
    case 'ttsSettings':
      await ttsSettings.openTtsSettings()
      break
    case 'dictionarySettings':
      await loadTranslationSettings()
      showDictionarySettingsDialog.value = true
      break
    case 'phoneticSettings':
      showPhoneticSettingsDialog.value = true
      break
    case 'syncBooks':
      await handleSyncBooks()
      break
    case 'compressImages':
      await handleCompressImages()
      break
  }
}

const handleSyncBooks = async () => {
  showConfirmDialog({
    title: '修复书籍数据',
    message: '将扫描 Books 目录并同步数据库记录，同时检查语音配置文件完整性，是否继续？'
  }).then(async () => {
    try {
      showToast({ message: '正在同步书籍...', forbidClick: true, duration: 0 })
      const res = await api.post('/books/sync')
      const result = res.data

      const messages: string[] = []
      if (result.fixed?.length > 0) messages.push(`修复 ${result.fixed.length} 本`)
      if (result.added?.length > 0) messages.push(`新增 ${result.added.length} 本`)
      if (result.removed?.length > 0) messages.push(`删除无效书籍 ${result.removed.length} 本`)
      if (result.audio_fixed?.length > 0) messages.push(`自动修复语音配置 ${result.audio_fixed.length} 本`)

      if (messages.length === 0) {
        showNotify({ type: 'success', message: '无需修复，数据已同步' })
      } else {
        showNotify({ type: 'success', message: messages.join('，') })
        await bookGroupsState.loadGroups()
      }

      if (result.audio_fixed?.length > 0 || result.audio_errors?.length > 0) {
        audioFixedList.value = result.audio_fixed || []
        audioErrorList.value = result.audio_errors || []
        showAudioFixDialog.value = true
      }
    } catch (error: any) {
      showNotify({ type: 'danger', message: error.response?.data?.detail || '同步失败' })
    }
  }).catch(() => {})
}

const handleCompressImages = async () => {
  showConfirmDialog({
    title: '压缩书籍图片',
    message: '将扫描所有书籍，将jpg/jpeg/png/bmp格式图片压缩并转换为WebP格式，是否继续？'
  }).then(async () => {
    try {
      showToast({ message: '正在压缩图片...', forbidClick: true, duration: 0 })
      const res = await api.post('/books/compress-images')
      const result = res.data

      const messages: string[] = []
      if (result.processed_books > 0) messages.push(`处理 ${result.processed_books} 本书籍`)
      if (result.converted_images > 0) messages.push(`转换 ${result.converted_images} 张图片`)
      if (result.skipped_images > 0) messages.push(`跳过 ${result.skipped_images} 张`)

      if (messages.length === 0) {
        showNotify({ type: 'success', message: '所有图片已是WebP格式，无需转换' })
      } else {
        showNotify({ type: 'success', message: messages.join('，') })
      }
    } catch (error: any) {
      showNotify({ type: 'danger', message: error.response?.data?.detail || '压缩失败' })
    }
  }).catch(() => {})
}

const onEditBookFromAudioFix = (bookId: string) => {
  isEditingFromAudioFix.value = true
  showAudioFixDialog.value = false
  router.push(`/book/${bookId}`)
}

// 生命周期
onMounted(async () => {
  bookGroupsState.loadGroups()
  await ttsSettings.loadUserSettings()

  // 加载词典状态
  try {
    const res = await api.get('/dictionary/status')
    ecdictAvailable.value = res.data.ecdict_available
  } catch (error) {
    console.error('加载词典状态失败:', error)
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
  font-size: 20px;
  color: #1989fa;
  cursor: pointer;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.username-link {
  font-size: 14px;
  color: #333;
  margin: 0 8px;
  cursor: pointer;
}

.content {
  padding-bottom: 50px;
}

.group-item {
  margin-bottom: 8px;
  background: #fff;
}

.group-actions {
  display: flex;
  align-items: center;
}

.group-import-btn {
  min-width: 28px;
  height: 24px;
}

.context-menu {
  position: fixed !important;
  width: 150px;
  top: 50% !important;
  left: 50% !important;
  transform: translate(-50%, -50%) !important;
}

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
</style>
