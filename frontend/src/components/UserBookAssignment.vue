/**
 * UserBookAssignment.vue - 用户书籍分配管理
 *
 * 功能：管理员为用户分配书籍和管理分组
 * - 查看用户的书籍列表和分组
 * - 创建、编辑、删除分组
 * - 拖拽排序分组
 * - 单个或批量分配书籍到分组
 * - 批量删除用户书籍
 * - 长按/右键显示操作菜单
 */
<template>
  <div class="user-book-assignment">
    <van-nav-bar
      :title="`管理 ${userInfo?.username || ''} 的书籍`"
      left-text="返回"
      left-arrow
      fixed
      placeholder
      @click-left="goBack"
    />

    <div class="content">
      <!-- 加载状态 -->
      <van-loading v-if="loading" size="24px" class="loading-center">
        加载中...
      </van-loading>

      <!-- 分组列表 -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">分组管理</span>
          <div class="section-actions">
            <van-button type="primary" size="small" @click="showSortCategories" style="margin-right: 8px;">
              <i class="fas fa-sort"></i>
              排序
            </van-button>
            <van-button type="primary" size="small" @click="showCreateCategoryDialog">
              <i class="fas fa-plus"></i>
              新建分组
            </van-button>
          </div>
        </div>

        <van-collapse v-model="activeCategoryNames" accordion>
          <!-- 用户创建的分组 -->
          <van-collapse-item
            v-for="category in userCategories"
            :key="category.id"
            :name="category.id"
            class="category-item"
          >
            <template #title>
              <div
                class="category-title"
                @contextmenu.prevent.stop="showCategoryGroupContextMenu($event, category)"
              >
                <!-- 多选分组全选框（仅在"未添加书籍"区域显示） -->
                <span>{{ category.name }}</span>
                <span class="book-count">({{ getCategoryBookCount(category.id) }} 本)</span>
              </div>
            </template>

            <template #right-icon>
              <!-- "未分组"不显示编辑和删除按钮 -->
              <div v-if="category.name !== '未分组'" class="category-actions" @click.stop>
                <van-button
                  type="warning"
                  size="mini"
                  @click="showEditCategoryDialog(category)"
                >
                  <i class="fas fa-pencil"></i>
                </van-button>
                <van-button
                  type="danger"
                  size="mini"
                  @click="confirmDeleteCategory(category)"
                >
                  <i class="fas fa-trash"></i>
                </van-button>
              </div>
            </template>

            <!-- 分组内的书籍列表 -->
            <div class="book-list">
              <van-swipe-cell
                v-for="book in getCategoryBooks(category.id)"
                :key="book.id"
                :stop-propagation="true"
                :disabled="isMultiSelect"
              >
                <div
                  class="book-item"
                  :class="{ 'selected': selectedBooks.includes(book.id) }"
                  @click="handleBookClick(book.id, category.id)"
                  @contextmenu.prevent="showBookContextMenu($event, book, category.id)"
                  @touchstart="handleBookTouchStart($event, book, category.id)"
                  @touchend="handleBookTouchEnd"
                  @touchmove="handleBookTouchEnd"
                  @touchcancel="handleBookTouchEnd"
                >
                  <div class="book-cover" @click.stop="handleCoverClick(book)">
                    <img
                      v-if="book.cover_path"
                      :src="getCoverUrl(book.cover_path)"
                      :alt="book.title"
                      loading="lazy"
                    />
                    <i v-else class="fas fa-book" style="font-size: 24px; color: #dcdee0;" />
                  </div>
                  <div class="book-info">
                    <span class="book-title">{{ book.title }}</span>
                    <span class="book-meta">Level: {{ book.level }} | {{ book.page_count }} 页</span>
                  </div>
                </div>
                <template #right>
                  <van-button
                    type="danger"
                    square
                    text="移除"
                    @click="removeBookFromCategory(book.id, category.id)"
                  />
                </template>
              </van-swipe-cell>

              <van-empty
                v-if="getCategoryBooks(category.id).length === 0"
                description="该分组暂无书籍"
                :image-size="60"
              />
            </div>
          </van-collapse-item>

          <van-empty
            v-if="userCategories.length === 0"
            description="暂无分组"
            :image-size="60"
          />
        </van-collapse>
      </div>

      <!-- 未添加书籍（按分组显示） -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">未添加书籍</span>
          <span class="book-count">({{ unaddedBookGroups.reduce((sum, g) => sum + g.books.length, 0) }} 本)</span>
        </div>

        <van-collapse v-model="activeUnadded" accordion>
          <van-collapse-item
            v-for="group in unaddedBookGroups"
            :key="group.id"
            :name="group.id"
            class="category-item"

          >
            <template #title>
              <div
                class="category-title"
                @contextmenu.prevent.stop="showUnaddedGroupContextMenu($event, group)"
                @touchstart.stop="handleUnaddedGroupTouchStart($event, group)"
                @touchend.stop="handleUnaddedGroupTouchEnd"
                @touchmove.stop="handleUnaddedGroupTouchEnd"
                @touchcancel.stop="handleUnaddedGroupTouchEnd"
              >
                <!-- 多选分组全选框 -->
                <div v-if="isMultiSelect" class="group-checkbox" @click.stop>
                  <input
                    type="checkbox"
                    :checked="isUnaddedGroupAllSelected(group.id)"
                    @change.stop="toggleUnaddedGroupSelect(group.id)"
                  />
                </div>
                <span>{{ group.name }}</span>
                <span class="book-count">({{ group.books.length }} 本)</span>
              </div>
            </template>

            <div class="book-list">
              <van-swipe-cell
                v-for="book in group.books"
                :key="book.id"
                :stop-propagation="true"
                :disabled="isMultiSelect"
              >
                <div
                  class="book-item"
                  :class="{ 'selected': selectedBooks.includes(book.id) }"
                  @click="handleUnaddedBookClick(book.id)"
                  @contextmenu.prevent="showUnaddedBookContextMenu($event, book)"
                  @touchstart="handleUnaddedBookTouchStart($event, book)"
                  @touchend="handleBookTouchEnd"
                  @touchmove="handleBookTouchEnd"
                  @touchcancel="handleBookTouchEnd"
                >
                  <!-- 多选复选框 -->
                  <div v-if="isMultiSelect" class="book-checkbox" @click.stop>
                    <input
                      type="checkbox"
                      :checked="selectedBooks.includes(book.id)"
                      @change="toggleBookSelect(book.id)"
                    />
                  </div>
                  <div class="book-cover" @click.stop="handleCoverClick(book)">
                    <img
                      v-if="book.cover_path"
                      :src="getCoverUrl(book.cover_path)"
                      :alt="book.title"
                      loading="lazy"
                    />
                    <i v-else class="fas fa-book" style="font-size: 24px; color: #dcdee0;" />
                  </div>
                  <div class="book-info">
                    <span class="book-title">{{ book.title }}</span>
                    <span class="book-meta">Level: {{ book.level }} | {{ book.page_count }} 页</span>
                  </div>
                </div>
              </van-swipe-cell>

              <van-empty
                v-if="group.books.length === 0"
                :description="`${group.name}暂无书籍`"
                :image-size="60"
              />
            </div>
          </van-collapse-item>

          <van-empty
            v-if="unaddedBookGroups.length === 0 && !loading"
            description="所有书籍都已添加到用户"
            :image-size="60"
          />
        </van-collapse>
      </div>
    </div>

    <!-- 批量操作栏（根据当前展开的区域显示不同操作） -->
    <div v-if="isMultiSelect" class="batch-actions">
      <!-- 仅在未添加书籍区域显示批量操作栏 -->
      <van-button type="primary" size="small" plain @click="selectAllUnaddedBooks">
        {{ isAllUnaddedSelected ? '取消全选' : '全选' }}
      </van-button>
      <van-button type="primary" size="small" @click="batchAssignUnaddedBooks" :disabled="selectedBooks.length === 0">
        添加到分组 ({{ selectedBooks.length }})
      </van-button>
      <van-button size="small" @click="cancelMultiSelect">
        取消
      </van-button>
    </div>

    <!-- 新建分组对话框 -->
    <van-dialog
      v-model:show="createCategoryDialogVisible"
      title="新建分组"
      show-cancel-button
      @confirm="handleCreateCategory"
      @cancel="resetCategoryForm"
    >
      <van-form>
        <van-field
          v-model="categoryForm.name"
          label="分组名称"
          placeholder="请输入分组名称"
          :error-message="categoryNameError"
        />
      </van-form>
    </van-dialog>

    <!-- 编辑分组对话框 -->
    <van-dialog
      v-model:show="editCategoryDialogVisible"
      title="编辑分组"
      show-cancel-button
      @confirm="handleEditCategory"
      @cancel="resetCategoryForm"
    >
      <van-form>
        <van-field
          v-model="categoryForm.name"
          label="分组名称"
          placeholder="请输入分组名称"
          :error-message="categoryNameError"
        />
      </van-form>
    </van-dialog>

    <!-- 分组排序对话框 -->
    <van-dialog
      v-model:show="showSortCategoriesDialog"
      title="排序分组"
      show-cancel-button
      confirm-button-text="保存"
      cancel-button-text="取消"
      @confirm="handleSaveCategoryOrder"
      @cancel="handleCancelSortCategories"
    >
      <div class="sort-categories-container">
        <draggable
          v-model="sortableCategories"
          item-key="id"
          handle=".drag-handle"
          ghost-class="sort-ghost"
          drag-class="sort-drag"
        >
          <template #item="{ element }">
            <div
              class="sort-category-item"
              :class="{ 'is-uncategorized': element.name === '未分组' }"
            >
              <i class="fas fa-bars drag-handle" />
              <span class="category-name">{{ element.name }}</span>
              <span v-if="element.name === '未分组'" class="fixed-label">(固定)</span>
            </div>
          </template>
        </draggable>
      </div>
    </van-dialog>

    <!-- 书籍右键菜单（用户已有书籍） -->
    <van-popup
      v-model:show="showBookContextMenuPopup"
      :style="{ top: contextMenuPos.y + 'px', left: contextMenuPos.x + 'px' }"
      round
      class="book-context-menu"
    >
      <van-cell-group>
        <van-cell title="分配到分组" clickable @click="openAssignToCategory" />
        <van-cell title="选择更多" clickable @click="enableMultiSelect" v-if="!isMultiSelect" />
        <van-cell
          v-if="contextMenuBook && contextMenuBook.categoryId !== 0"
          title="从分组移除"
          clickable
          @click="removeBookFromCategoryMenu"
        />
        <van-cell title="删除" clickable @click="deleteBookFromMenu" />
      </van-cell-group>
    </van-popup>

    <!-- 未添加书籍右键菜单 -->
    <van-popup
      v-model:show="showUnaddedBookContextMenuPopup"
      :style="{ top: contextMenuPos.y + 'px', left: contextMenuPos.x + 'px' }"
      round
      class="book-context-menu"
    >
      <van-cell-group>
        <van-cell title="添加到分组" clickable @click="openAssignUnaddedToCategory" />
        <van-cell title="选择更多" clickable @click="enableMultiSelectForUnadded" v-if="!isMultiSelect" />
      </van-cell-group>
    </van-popup>

    <!-- 未添加书籍分组右键菜单（针对分组标题） -->
    <van-popup
      v-model:show="showUnaddedGroupContextMenuPopup"
      :style="{ top: contextMenuPos.y + 'px', left: contextMenuPos.x + 'px' }"
      round
      class="book-context-menu"
    >
      <van-cell-group>
        <van-cell
          title="添加分组所有书籍"
          clickable
          :is-link="false"
          @click="addAllBooksFromUnaddedGroup"
        />
      </van-cell-group>
    </van-popup>

    <!-- 用户分组右键菜单（针对分组标题） -->
    <van-popup
      v-model:show="showCategoryGroupContextMenuPopup"
      :style="{ top: contextMenuPos.y + 'px', left: contextMenuPos.x + 'px' }"
      round
      class="book-context-menu"
    >
      <van-cell-group>
        <van-cell title="选中分组内所有书籍" clickable @click="selectAllBooksInCategory" />
      </van-cell-group>
    </van-popup>

    <!-- 选择分组对话框（底部弹出） -->
    <van-popup v-model:show="showSelectCategoryPopup" position="bottom" round>
      <div class="select-category-dialog">
        <div class="select-category-header">
          <span>选择分组</span>
          <i class="fas fa-xmark" @click="showSelectCategoryPopup = false" style="cursor: pointer; color: #999; font-size: 18px;"></i>
        </div>
        <div class="select-category-content">
          <van-radio-group v-model="selectedCategoryForBook">
            <van-cell-group>
              <!-- 未分组选项 -->
              <van-cell
                clickable
                @click="selectedCategoryForBook = 0"
              >
                <template #title>
                  <span>未分组</span>
                </template>
                <template #right-icon>
                  <van-radio :name="0" />
                </template>
              </van-cell>
             <!-- 用户创建的分组（排除"未分组"，因为上面已有硬编码选项） -->
              <van-cell
                v-for="category in userCategories.filter(c => c.name !== '未分组')"
                :key="category.id"
                clickable
                @click="selectedCategoryForBook = category.id"
              >
                <template #title>
                  <span>{{ category.name }}</span>
                </template>
                <template #right-icon>
                  <van-radio :name="category.id" />
                </template>
              </van-cell>
            </van-cell-group>
          </van-radio-group>
        </div>
        <div class="select-category-footer">
          <van-button size="small" type="primary" plain @click="showCreateCategoryInSelect = true">
            创建新分组
          </van-button>
          <van-button
            size="small"
            type="primary"
            :loading="assigningBook"
            loading-text="分配中..."
            @click="confirmAssignToCategory"
          >
            确定
          </van-button>
        </div>
        <van-field
          v-if="showCreateCategoryInSelect"
          v-model="newCategoryInSelect"
          placeholder="输入新分组名称"
          @keyup.enter="createCategoryInSelect"
        >
          <template #button>
            <van-button size="small" type="primary" @click="createCategoryInSelect">创建</van-button>
          </template>
        </van-field>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showNotify, showConfirmDialog, showLoadingToast, closeToast } from 'vant'
import { api } from '@/store/auth'
import { buildStaticUrl } from '@/utils/apiBase'
import draggable from 'vuedraggable'

interface Category {
  id: number
  name: string
  type: string
  user_id?: number
  sort_order: number
}

interface Book {
  id: string
  title: string
  level: string
  file_path: string
  page_count: number
  cover_path?: string
  is_read: number
}

interface BookGroup {
  id: number
  name: string
  type: string
  sort_order: number
  books: Book[]
}

// 注册draggable组件
const Draggable = draggable

const router = useRouter()
const route = useRoute()

const userId = computed(() => Number(route.params.userId))
const userInfo = ref<{ username: string } | null>(null)

// 数据
const categories = ref<Category[]>([])
const bookGroups = ref<BookGroup[]>([])
const unaddedBookGroups = ref<BookGroup[]>([])
const loading = ref(false)

// 折叠面板
const activeCategoryNames = ref<number | string | undefined>(undefined)
const activeUnadded = ref<number | string | undefined>(undefined)

// 未添加书籍右键菜单
const showUnaddedBookContextMenuPopup = ref(false)
// 未添加书籍分组右键菜单
const showUnaddedGroupContextMenuPopup = ref(false)
const contextMenuUnaddedGroup = ref<BookGroup | null>(null)
const addingGroupBooks = ref(false)
// 长按计时器
let unaddedGroupLongPressTimer: ReturnType<typeof setTimeout> | null = null
// 书籍长按计时器与标记
let bookLongPressTimer: ReturnType<typeof setTimeout> | null = null
let bookLongPressTriggered = false
const LONG_PRESS_DURATION = 500

// 分组表单
const createCategoryDialogVisible = ref(false)
const editCategoryDialogVisible = ref(false)
const categoryForm = reactive({
  id: 0,
  name: ''
})
const categoryNameError = ref('')

// 右键菜单相关
const showBookContextMenuPopup = ref(false)
const contextMenuPos = ref({ x: 0, y: 0 })
const contextMenuBook = ref<{ id: string; categoryId: number } | null>(null)

// 分组右键菜单
const showCategoryGroupContextMenuPopup = ref(false)
const contextMenuCategory = ref<Category | null>(null)

// 选择分组对话框
const showSelectCategoryPopup = ref(false)
const selectedCategoryForBook = ref<number>(0)
const assigningBook = ref(false)
const showCreateCategoryInSelect = ref(false)
const newCategoryInSelect = ref('')

// 批量选择相关
const isMultiSelect = ref(false)
const selectedBooks = ref<string[]>([])

// 分组排序相关
const showSortCategoriesDialog = ref(false)
const sortableCategories = ref<Category[]>([])

// 计算属性
// 用户创建的分类（不包含默认的未分组）
const userCategories = computed(() => {
  return categories.value.filter(c => c.type !== 'default')
})

// 获取未添加书籍分组的书籍
const getUnaddedGroupBooks = (groupId: number | string): Book[] => {
  const group = unaddedBookGroups.value.find(g => g.id === groupId)
  return group?.books || []
}

// 未添加书籍是否全选（根据当前展开的分组）
const isAllUnaddedSelected = computed(() => {
  if (activeUnadded.value === undefined) return false
  const books = getUnaddedGroupBooks(activeUnadded.value)
  return books.length > 0 && books.every((b: Book) => selectedBooks.value.includes(b.id))
})

// 方法
const goBack = () => {
  router.back()
}

const getCategoryBookCount = (categoryId: number): number => {
  const group = bookGroups.value.find(g => g.id === categoryId)
  return group?.books.length || 0
}

const getCategoryBooks = (categoryId: number): Book[] => {
  const group = bookGroups.value.find(g => g.id === categoryId)
  return group?.books || []
}

const getCoverUrl = (coverPath: string): string => {
  if (!coverPath) return ''
  return buildStaticUrl(coverPath)
}

const handleCoverClick = (_book: Book) => {
  // 可以在此添加预览功能
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    // 加载用户信息
    const userRes = await api.get(`/auth/users/${userId.value}`)
    if (userRes.data) {
      userInfo.value = userRes.data
    }

    // 加载分组
    const categoriesRes = await api.get(`/admin/users/${userId.value}/categories`)
    categories.value = categoriesRes.data

    // 加载分组书籍
    const groupedRes = await api.get(`/admin/users/${userId.value}/categories/grouped`)
    bookGroups.value = groupedRes.data

    // 加载未添加书籍的分组
    const unaddedGroupedRes = await api.get(`/admin/users/${userId.value}/books/grouped`)
    unaddedBookGroups.value = unaddedGroupedRes.data
  } catch (error: any) {
    showNotify({
      type: 'danger',
      message: error.response?.data?.detail || '加载数据失败'
    })
  } finally {
    loading.value = false
  }
}

// 分组管理
const showCreateCategoryDialog = () => {
  categoryForm.name = ''
  categoryNameError.value = ''
  createCategoryDialogVisible.value = true
}

const showEditCategoryDialog = (category: Category) => {
  categoryForm.id = category.id
  categoryForm.name = category.name
  categoryNameError.value = ''
  editCategoryDialogVisible.value = true
}

const resetCategoryForm = () => {
  categoryForm.id = 0
  categoryForm.name = ''
  categoryNameError.value = ''
}

const handleCreateCategory = async () => {
  if (!categoryForm.name.trim()) {
    categoryNameError.value = '请输入分组名称'
    return
  }

  try {
    await api.post(`/admin/users/${userId.value}/categories`, {
      name: categoryForm.name.trim()
    })
    showNotify({ type: 'success', message: '分组创建成功' })
    createCategoryDialogVisible.value = false
    await loadData()
  } catch (error: any) {
    categoryNameError.value = error.response?.data?.detail || '创建失败'
  }
}

const handleEditCategory = async () => {
  if (!categoryForm.name.trim()) {
    categoryNameError.value = '请输入分组名称'
    return
  }

  try {
    await api.put(`/admin/users/${userId.value}/categories/${categoryForm.id}`, {
      name: categoryForm.name.trim()
    })
    showNotify({ type: 'success', message: '分组更新成功' })
    editCategoryDialogVisible.value = false
    await loadData()
  } catch (error: any) {
    categoryNameError.value = error.response?.data?.detail || '更新失败'
  }
}

const confirmDeleteCategory = (category: Category) => {
  showConfirmDialog({
    title: '确认删除',
    message: `确定要删除分组 "${category.name}" 吗？分组内的书籍将变为未分组状态。`,
    confirmButtonText: '删除',
    confirmButtonColor: '#ee0a24'
  }).then(async () => {
    try {
      await api.delete(`/admin/users/${userId.value}/categories/${category.id}`)
      showNotify({ type: 'success', message: '分组已删除' })
      await loadData()
    } catch (error: any) {
      showNotify({
        type: 'danger',
        message: error.response?.data?.detail || '删除失败'
      })
    }
  }).catch(() => {})
}

// 分组排序
const showSortCategories = () => {
  // 复制当前分类列表（排除未分组）
  sortableCategories.value = categories.value.filter(c => c.name !== '未分组')
  showSortCategoriesDialog.value = true
}

const handleSaveCategoryOrder = async () => {
  try {
    const orderedIds = sortableCategories.value.map(c => c.id)
    await api.put(`/admin/users/${userId.value}/categories/reorder`, {
      category_ids: orderedIds
    })
    showNotify({ type: 'success', message: '排序已保存' })
    showSortCategoriesDialog.value = false
    await loadData()
  } catch (error: any) {
    showNotify({
      type: 'danger',
      message: error.response?.data?.detail || '保存排序失败'
    })
  }
}

const handleCancelSortCategories = () => {
  sortableCategories.value = []
  showSortCategoriesDialog.value = false
}

// 书籍分配
// 打开单个书籍分配对话框（底部弹出）
// 启用多选模式
const enableMultiSelect = () => {
  showBookContextMenuPopup.value = false
  if (contextMenuBook.value) {
    selectedBooks.value = [contextMenuBook.value.id]
  }
  isMultiSelect.value = true
}

// 切换书籍选择状态
const toggleBookSelect = (bookId: string) => {
  const index = selectedBooks.value.indexOf(bookId)
  if (index === -1) {
    selectedBooks.value.push(bookId)
  } else {
    selectedBooks.value.splice(index, 1)
  }
}

// 处理书籍点击（支持多选模式）
const handleBookClick = (bookId: string, _categoryId: number) => {
  if (bookLongPressTriggered) {
    bookLongPressTriggered = false
    return
  }
  if (isMultiSelect.value) {
    toggleBookSelect(bookId)
  } else {
    handleCoverClick({ id: bookId } as Book)
  }
}

// 全选/取消全选（当前展开的用户分组）
const selectAllBooks = () => {
  if (isAllSelected.value) {
    selectedBooks.value = []
  } else {
    // 获取当前展开的分组的书籍
    let books: Book[] = []
    if (activeCategoryNames.value !== undefined) {
      const catId = activeCategoryNames.value
      if (typeof catId === 'number') {
        books = getCategoryBooks(catId)
      }
    }
    selectedBooks.value = books.map(b => b.id)
  }
}

// 判断未添加分组是否已全选
const isUnaddedGroupAllSelected = (groupId: number | string): boolean => {
  const group = unaddedBookGroups.value.find(g => g.id === groupId)
  if (!group || group.books.length === 0) return false
  return group.books.every((b: Book) => selectedBooks.value.includes(b.id))
}

// 切换未添加分组全选/取消
const toggleUnaddedGroupSelect = (groupId: number | string) => {
  const group = unaddedBookGroups.value.find(g => g.id === groupId)
  if (!group) return
  const groupBookIds = group.books.map((b: Book) => b.id)
  const isAllSelected = groupBookIds.every(id => selectedBooks.value.includes(id))
  if (isAllSelected) {
    selectedBooks.value = selectedBooks.value.filter(id => !groupBookIds.includes(id))
  } else {
    selectedBooks.value = [...new Set([...selectedBooks.value, ...groupBookIds])]
  }
}

// 判断用户分组是否已全选
const isUserCategoryAllSelected = (categoryId: number): boolean => {
  const books = getCategoryBooks(categoryId)
  if (books.length === 0) return false
  return books.every((b: Book) => selectedBooks.value.includes(b.id))
}

// 切换用户分组全选/取消
const toggleUserCategorySelect = (categoryId: number) => {
  const books = getCategoryBooks(categoryId)
  const groupBookIds = books.map((b: Book) => b.id)
  const isAllSelected = groupBookIds.every(id => selectedBooks.value.includes(id))
  if (isAllSelected) {
    selectedBooks.value = selectedBooks.value.filter(id => !groupBookIds.includes(id))
  } else {
    selectedBooks.value = [...new Set([...selectedBooks.value, ...groupBookIds])]
  }
}

// 是否全选（用户已有书籍分组）
const isAllSelected = computed(() => {
  let books: Book[] = []
  if (activeCategoryNames.value !== undefined) {
    const catId = activeCategoryNames.value
    if (typeof catId === 'number') {
      books = getCategoryBooks(catId)
    }
  }
  return books.length > 0 && books.every((b: Book) => selectedBooks.value.includes(b.id))
})

// 未添加书籍全选/取消全选
const selectAllUnaddedBooks = () => {
  if (activeUnadded.value === undefined) return
  if (isAllUnaddedSelected.value) {
    // 取消当前分组的全选
    const books = getUnaddedGroupBooks(activeUnadded.value)
    selectedBooks.value = selectedBooks.value.filter(id => !books.some((b: Book) => b.id === id))
  } else {
    // 全选当前分组
    const books = getUnaddedGroupBooks(activeUnadded.value)
    const bookIds = books.map((b: Book) => b.id)
    selectedBooks.value = [...new Set([...selectedBooks.value, ...bookIds])]
  }
}

// 处理未添加书籍点击
const handleUnaddedBookClick = (bookId: string) => {
  if (bookLongPressTriggered) {
    bookLongPressTriggered = false
    return
  }
  if (isMultiSelect.value) {
    toggleBookSelect(bookId)
  } else {
    handleCoverClick({ id: bookId } as Book)
  }
}

// 显示未添加书籍分组右键菜单（针对分组标题）
const showUnaddedGroupContextMenu = (event: MouseEvent | { clientX: number; clientY: number }, group: BookGroup) => {
  contextMenuUnaddedGroup.value = group
  const menuWidth = 180
  const menuHeight = 120
  let x = Math.min(event.clientX, window.innerWidth - menuWidth - 20)
  let y = Math.min(event.clientY, window.innerHeight - menuHeight - 20)
  x = Math.max(x, 10)
  y = Math.max(y, 10)
  contextMenuPos.value = { x, y }
  showUnaddedGroupContextMenuPopup.value = true
}

// 长按启动（移动端触摸事件）
const handleUnaddedGroupTouchStart = (event: TouchEvent, group: BookGroup) => {
  const touch = event.touches[0]
  if (!touch) return
  const touchPoint = { clientX: touch.clientX, clientY: touch.clientY }
  if (unaddedGroupLongPressTimer) clearTimeout(unaddedGroupLongPressTimer)
  unaddedGroupLongPressTimer = setTimeout(() => {
    showUnaddedGroupContextMenu(touchPoint, group)
    unaddedGroupLongPressTimer = null
  }, LONG_PRESS_DURATION)
}
// 取消长按
const handleUnaddedGroupTouchEnd = () => {
  if (unaddedGroupLongPressTimer) {
    clearTimeout(unaddedGroupLongPressTimer)
    unaddedGroupLongPressTimer = null
  }
}

// 添加未添加书籍分组下的所有书籍到普通用户的同名分组
// 若用户不存在同名分组，则先创建再添加
const addAllBooksFromUnaddedGroup = async () => {
  if (addingGroupBooks.value) return
  const group = contextMenuUnaddedGroup.value
  showUnaddedGroupContextMenuPopup.value = false
  if (!group) return

  if (!group.books || group.books.length === 0) {
    showNotify({ type: 'warning', message: '该分组暂无可添加的书籍' })
    return
  }

  addingGroupBooks.value = true
  // 显示加载提示
  showLoadingToast({
    message: '正在添加书籍，请勿关闭...',
    duration: 0,
    forbidClick: true,
    overlay: true
  })
  try {
    // 查找用户已有同名分组
    let targetCategoryId: number | null = null
    const existing = categories.value.find(c => c.name === group.name)
    if (existing) {
      targetCategoryId = existing.id
    } else {
      // 创建同名分组
      const createRes = await api.post(`/admin/users/${userId.value}/categories`, {
        name: group.name
      })
      targetCategoryId = createRes.data?.id ?? null
    }

    if (targetCategoryId === null) {
      closeToast()
      throw new Error('目标分组ID获取失败')
    }

    const total = group.books.length
    // 批量将书籍分配到目标分组
    let successCount = 0
    const failedBooks: string[] = []
    for (let i = 0; i < total; i++) {
      const book = group.books[i]
      // 更新进度提示
      showLoadingToast({
        message: `正在添加书籍 (${i + 1}/${total})，请勿关闭...`,
        duration: 0,
        forbidClick: true,
        overlay: true
      })
      try {
        await api.post(`/admin/users/${userId.value}/categories/books`, {
          book_id: book.id,
          category_id: targetCategoryId
        })
        successCount++
      } catch (e) {
        failedBooks.push(book.title)
      }
    }

    closeToast()

    if (failedBooks.length === 0) {
      showNotify({ type: 'success', message: `成功添加 ${successCount} 本书籍到分组「${group.name}」` })
    } else {
      showNotify({
        type: 'warning',
        message: `成功 ${successCount} 本，失败 ${failedBooks.length} 本`
      })
    }
    await loadData()
  } catch (error: any) {
    closeToast()
    showNotify({
      type: 'danger',
      message: error.response?.data?.detail || error.message || '添加分组所有书籍失败'
    })
  } finally {
    addingGroupBooks.value = false
    contextMenuUnaddedGroup.value = null
  }
}

// 显示未添加书籍右键菜单
const showUnaddedBookContextMenu = (event: MouseEvent | { clientX: number; clientY: number }, book: Book) => {
  contextMenuBook.value = { id: book.id, categoryId: -1 } // -1 表示未添加
  // 计算菜单位置
  const menuWidth = 150
  const menuHeight = 120
  let x = Math.min(event.clientX, window.innerWidth - menuWidth - 20)
  let y = Math.min(event.clientY, window.innerHeight - menuHeight - 20)
  x = Math.max(x, 10)
  y = Math.max(y, 10)
  contextMenuPos.value = { x, y }
  showUnaddedBookContextMenuPopup.value = true
}

// 显示书籍右键菜单
const showBookContextMenu = (event: MouseEvent | { clientX: number; clientY: number }, book: Book, categoryId: number) => {
  contextMenuBook.value = { id: book.id, categoryId }
  // 计算菜单位置，确保不超出屏幕
  const menuWidth = 150
  const menuHeight = 120
  let x = Math.min(event.clientX, window.innerWidth - menuWidth - 20)
  let y = Math.min(event.clientY, window.innerHeight - menuHeight - 20)
  // 确保菜单位置不小于0
  x = Math.max(x, 10)
  y = Math.max(y, 10)
  contextMenuPos.value = { x, y }
  showBookContextMenuPopup.value = true
}

// 书籍长按（用户已有分组）
const handleBookTouchStart = (event: TouchEvent, book: Book, categoryId: number) => {
  const touch = event.touches[0]
  if (!touch) return
  bookLongPressTriggered = false
  const touchPoint = { clientX: touch.clientX, clientY: touch.clientY }
  if (bookLongPressTimer) clearTimeout(bookLongPressTimer)
  bookLongPressTimer = setTimeout(() => {
    bookLongPressTriggered = true
    showBookContextMenu(touchPoint, book, categoryId)
    bookLongPressTimer = null
  }, LONG_PRESS_DURATION)
}

// 未添加书籍长按
const handleUnaddedBookTouchStart = (event: TouchEvent, book: Book) => {
  const touch = event.touches[0]
  if (!touch) return
  bookLongPressTriggered = false
  const touchPoint = { clientX: touch.clientX, clientY: touch.clientY }
  if (bookLongPressTimer) clearTimeout(bookLongPressTimer)
  bookLongPressTimer = setTimeout(() => {
    bookLongPressTriggered = true
    showUnaddedBookContextMenu(touchPoint, book)
    bookLongPressTimer = null
  }, LONG_PRESS_DURATION)
}

// 取消书籍长按（移动 / 抬起 / 取消）
const handleBookTouchEnd = () => {
  if (bookLongPressTimer) {
    clearTimeout(bookLongPressTimer)
    bookLongPressTimer = null
  }
}

// 为未添加书籍启用多选
const enableMultiSelectForUnadded = () => {
  showUnaddedBookContextMenuPopup.value = false
  if (contextMenuBook.value) {
    selectedBooks.value = [contextMenuBook.value.id]
  }
  isMultiSelect.value = true
}

// 打开未添加书籍的分配对话框
const openAssignUnaddedToCategory = () => {
  showUnaddedBookContextMenuPopup.value = false
  selectedCategoryForBook.value = categories.value[0]?.id || 0
  showSelectCategoryPopup.value = true
}

// 批量分配未添加书籍到分组
const batchAssignUnaddedBooks = () => {
  if (selectedBooks.value.length === 0) return
  selectedCategoryForBook.value = categories.value[0]?.id || 0
  showSelectCategoryPopup.value = true
}

// 取消多选
const cancelMultiSelect = () => {
  isMultiSelect.value = false
  selectedBooks.value = []
}

// 显示分类分组右键菜单
const showCategoryGroupContextMenu = (event: MouseEvent, category: Category) => {
  contextMenuCategory.value = category
  const menuWidth = 150
  const menuHeight = 60
  let x = Math.min(event.clientX, window.innerWidth - menuWidth - 20)
  let y = Math.min(event.clientY, window.innerHeight - menuHeight - 20)
  x = Math.max(x, 10)
  y = Math.max(y, 10)
  contextMenuPos.value = { x, y }
  showCategoryGroupContextMenuPopup.value = true
}

// 选中分组内所有书籍
const selectAllBooksInCategory = () => {
  showCategoryGroupContextMenuPopup.value = false
  if (!contextMenuCategory.value) return

  const books = getCategoryBooks(contextMenuCategory.value.id)
  isMultiSelect.value = true
  selectedBooks.value = books.map((b: Book) => b.id)
  contextMenuCategory.value = null
}

// 批量分配书籍到分组
const batchAssignBooks = () => {
  if (selectedBooks.value.length === 0) return
  selectedCategoryForBook.value = userCategories.value[0]?.id || 0
  showSelectCategoryPopup.value = true
}

const removeBookFromCategory = async (bookId: string, categoryId: number) => {
  try {
    await api.delete(`/admin/users/${userId.value}/categories/${categoryId}/books/${bookId}`)
    showNotify({ type: 'success', message: '书籍已从分组移除' })
    await loadData()
  } catch (error: any) {
    showNotify({
      type: 'danger',
      message: error.response?.data?.detail || '移除失败'
    })
  }
}

// 打开分配到分组对话框
const openAssignToCategory = () => {
  showBookContextMenuPopup.value = false
  if (isMultiSelect.value) {
    // 批量分配模式
    selectedCategoryForBook.value = userCategories.value[0]?.id || 0
  } else if (contextMenuBook.value) {
    // 单个分配模式
    selectedCategoryForBook.value = contextMenuBook.value.categoryId || userCategories.value[0]?.id || 0
  }
  showSelectCategoryPopup.value = true
}

// 确认分配到分组
const confirmAssignToCategory = async () => {
  // 确定要分配的书籍列表（支持批量和单个）
  const booksToAssign = isMultiSelect.value ? selectedBooks.value : (contextMenuBook.value ? [contextMenuBook.value.id] : [])
  if (booksToAssign.length === 0) return

  assigningBook.value = true
  try {
    for (const bookId of booksToAssign) {
      await api.post(`/admin/users/${userId.value}/categories/books`, {
        book_id: bookId,
        category_id: selectedCategoryForBook.value
      })
    }
    showNotify({ type: 'success', message: `成功分配 ${booksToAssign.length} 本书籍` })
    showSelectCategoryPopup.value = false
    // 清除多选状态
    isMultiSelect.value = false
    selectedBooks.value = []
    await loadData()
  } catch (error: any) {
    showNotify({
      type: 'danger',
      message: error.response?.data?.detail || '分配失败'
    })
  } finally {
    assigningBook.value = false
  }
}

// 从右键菜单移除书籍
const removeBookFromCategoryMenu = () => {
  showBookContextMenuPopup.value = false
  if (contextMenuBook.value && contextMenuBook.value.categoryId !== 0) {
    removeBookFromCategory(contextMenuBook.value.id, contextMenuBook.value.categoryId)
  }
}

// 批量删除用户书籍
const batchDeleteBooks = async () => {
  if (selectedBooks.value.length === 0) return

  try {
    await showConfirmDialog({
      title: '确认删除',
      message: `确定要删除选中的 ${selectedBooks.value.length} 本书籍吗？删除后这些书籍将回到"未添加书籍"列表。`,
      confirmButtonText: '删除',
      confirmButtonColor: '#ee0a24'
    })

    const deletingBookIds = [...selectedBooks.value]
    for (const bookId of deletingBookIds) {
      await api.delete(`/admin/users/${userId.value}/books/${bookId}`)
    }
    showNotify({ type: 'success', message: `成功删除 ${deletingBookIds.length} 本书籍` })
    // 清除多选状态
    isMultiSelect.value = false
    selectedBooks.value = []
    await loadData()
  } catch (error: any) {
    if (error !== 'cancel') {
      showNotify({
        type: 'danger',
        message: error.response?.data?.detail || '删除失败'
      })
    }
  }
}

// 从右键菜单删除书籍
const deleteBookFromMenu = () => {
  showBookContextMenuPopup.value = false
  if (contextMenuBook.value) {
    selectedBooks.value = [contextMenuBook.value.id]
    batchDeleteBooks()
  }
}

// 在选择分组对话框中创建新分组
const createCategoryInSelect = async () => {
  if (!newCategoryInSelect.value.trim()) {
    showNotify({ type: 'warning', message: '请输入分组名称' })
    return
  }

  try {
    const res = await api.post(`/admin/users/${userId.value}/categories`, {
      name: newCategoryInSelect.value.trim()
    })
    showNotify({ type: 'success', message: '分组创建成功' })
    // 选择新创建的分组
    selectedCategoryForBook.value = res.data.id
    newCategoryInSelect.value = ''
    showCreateCategoryInSelect.value = false
    await loadData()
  } catch (error: any) {
    showNotify({
      type: 'danger',
      message: error.response?.data?.detail || '创建失败'
    })
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="less">
.user-book-assignment {
  min-height: 100vh;
  background: #f7f8fa;
}

.content {
  padding: 0 12px 70px;
}

.loading-center {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px 0;
}

.section {
  margin-bottom: 16px;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #323233;
}

.book-count {
  font-size: 14px;
  color: #969799;
}

.category-item {
  :deep(.van-collapse-item__content) {
    padding: 0;
  }
}

.category-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.category-actions {
  display: flex;
  gap: 4px;
}

.book-list {
  padding: 8px 16px;
}

.book-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;

  &:last-child {
    border-bottom: none;
  }
}

.book-cover {
  width: 50px;
  height: 70px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  flex-shrink: 0;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.book-info {
  flex: 1;
  min-width: 0;
}

.book-title {
  display: block;
  font-size: 14px;
  color: #323233;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.book-meta {
  display: block;
  font-size: 12px;
  color: #969799;
  margin-top: 4px;
}

.assign-dialog-content {
  max-height: 60vh;
  overflow-y: auto;
}

.book-select-list {
  max-height: 300px;
  overflow-y: auto;
}

.book-select-item {
  display: flex;
  align-items: center;
  gap: 8px;

  .book-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #f5f5f5;
}

.book-context-menu {
  max-width: 150px;
}

.select-category-dialog {
  max-height: 60vh;
  display: flex;
  flex-direction: column;
}

.select-category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid #f5f5f5;
}

.select-category-content {
  flex: 1;
  overflow-y: auto;
  max-height: 300px;
}

.select-category-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #f5f5f5;
}

/* 批量操作栏 */
.batch-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: #fff;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
  z-index: 100;
}

/* 书籍复选框 */
.book-checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;

  input {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }
}

/* 选中状态 */
.book-item.selected {
  background: #e6f7ff;
}

/* 分组排序样式 */
.sort-categories-container {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
}

.sort-category-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: move;

  &.is-uncategorized {
    background: #e8f0fe;
    cursor: not-allowed;
  }

  .drag-handle {
    margin-right: 12px;
    color: #969799;
    font-size: 18px;
  }

  &.is-uncategorized .drag-handle {
    color: #1989fa;
  }

  .category-name {
    flex: 1;
    font-size: 14px;
    color: #323233;
  }

  .fixed-label {
    font-size: 12px;
    color: #969799;
  }
}

.sort-ghost {
  opacity: 0.5;
  background: #c8c9cc;
}

.sort-drag {
  opacity: 0.8;
  background: #e8f0fe;
}

/* 分组多选全选框 */
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
</style>
