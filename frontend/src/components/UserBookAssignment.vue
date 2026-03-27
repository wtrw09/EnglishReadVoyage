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
            <van-button type="primary" size="small" icon="exchange" @click="showSortCategories" style="margin-right: 8px;">
              排序
            </van-button>
            <van-button type="primary" size="small" icon="plus" @click="showCreateCategoryDialog">
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
              <div class="category-title">
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
                  icon="edit"
                  @click="showEditCategoryDialog(category)"
                />
                <van-button
                  type="danger"
                  size="mini"
                  icon="delete"
                  @click="confirmDeleteCategory(category)"
                />
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
                  @longpress="showBookContextMenu($event, book, category.id)"
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
                    <van-icon v-else name="book" size="24" color="#dcdee0" />
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
              <div class="category-title">
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
                  @longpress="showUnaddedBookContextMenu($event, book)"
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
                    <van-icon v-else name="book" size="24" color="#dcdee0" />
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
      <template v-if="activeUnadded !== undefined && activeCategoryNames === undefined">
        <!-- 未添加书籍区域 -->
        <van-button type="primary" size="small" plain @click="selectAllUnaddedBooks">
          {{ isAllUnaddedSelected ? '取消全选' : '全选' }}
        </van-button>
        <van-button type="primary" size="small" @click="batchAssignUnaddedBooks" :disabled="selectedBooks.length === 0">
          添加到分组 ({{ selectedBooks.length }})
        </van-button>
      </template>
      <template v-else>
        <!-- 用户书籍区域 -->
        <van-button type="primary" size="small" plain @click="selectAllBooks">
          {{ isAllSelected ? '取消全选' : '全选' }}
        </van-button>
        <van-button type="primary" size="small" @click="batchAssignBooks" :disabled="selectedBooks.length === 0">
          分配到分组 ({{ selectedBooks.length }})
        </van-button>
        <van-button type="danger" size="small" @click="batchDeleteBooks" :disabled="selectedBooks.length === 0">
          删除 ({{ selectedBooks.length }})
        </van-button>
      </template>
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
              <van-icon name="bars" class="drag-handle" />
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

    <!-- 选择分组对话框（底部弹出） -->
    <van-popup v-model:show="showSelectCategoryPopup" position="bottom" round>
      <div class="select-category-dialog">
        <div class="select-category-header">
          <span>选择分组</span>
          <van-icon name="cross" @click="showSelectCategoryPopup = false" />
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
              <!-- 用户创建的分组 -->
              <van-cell
                v-for="category in userCategories"
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
import { showNotify, showConfirmDialog } from 'vant'
import { api } from '@/store/auth'
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
  if (coverPath.startsWith('http')) return coverPath
  // 直接使用 cover_path，后端已挂载 /books 静态目录
  return coverPath
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
  if (isMultiSelect.value) {
    toggleBookSelect(bookId)
  } else {
    handleCoverClick({ id: bookId } as Book)
  }
}

// 显示未添加书籍右键菜单
const showUnaddedBookContextMenu = (event: MouseEvent, book: Book) => {
  contextMenuBook.value = { id: book.id, categoryId: -1 } // -1 表示未添加
  // 计算菜单位置
  const menuWidth = 150
  const menuHeight = 80
  let x = Math.min(event.clientX, window.innerWidth - menuWidth - 20)
  let y = Math.min(event.clientY, window.innerHeight - menuHeight - 20)
  x = Math.max(x, 10)
  y = Math.max(y, 10)
  contextMenuPos.value = { x, y }
  showUnaddedBookContextMenuPopup.value = true
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

// 显示书籍右键菜单
const showBookContextMenu = (event: MouseEvent, book: Book, categoryId: number) => {
  contextMenuBook.value = { id: book.id, categoryId }
  // 计算菜单位置，确保不超出屏幕
  const menuWidth = 150
  const menuHeight = 100
  let x = Math.min(event.clientX, window.innerWidth - menuWidth - 20)
  let y = Math.min(event.clientY, window.innerHeight - menuHeight - 20)
  // 确保菜单位置不小于0
  x = Math.max(x, 10)
  y = Math.max(y, 10)
  contextMenuPos.value = { x, y }
  showBookContextMenuPopup.value = true
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
  padding: 12px;
  padding-bottom: 70px;
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
</style>
