/**
 * 分组管理 Composable
 * 集中管理所有分组相关的状态和方法
 */
import { ref } from 'vue'
import { showNotify, showConfirmDialog } from 'vant'
import { api } from '@/store/auth'
import type { BookGroup } from '../types'

export const useGroupManagement = () => {
  // ========== 添加分组相关 ==========

  // 添加分组对话框显示状态
  const showAddGroupDialog = ref(false)

  // 新分组名称
  const newGroupName = ref('')

  // ========== 分组排序相关 ==========

  // 分组排序对话框显示状态
  const showSortGroupsDialog = ref(false)

  // 可排序的分组列表
  const sortableGroups = ref<BookGroup[]>([])

  // ========== 分组右键菜单相关 ==========

  // 分组右键菜单显示状态
  const showGroupContextMenuPopup = ref(false)

  // 分组右键菜单位置
  const groupContextMenuPos = ref({ x: 0, y: 0 })

  // 当前操作的分组
  const contextMenuGroup = ref<BookGroup | null>(null)

  // ========== 重命名分组相关 ==========

  // 重命名分组对话框显示状态
  const showRenameGroupDialog = ref(false)

  // 重命名分组名称
  const renameGroupName = ref('')

  // ========== 方法 ==========

  /**
   * 添加分组
   */
  const handleAddGroup = async () => {
    if (!newGroupName.value.trim()) {
      showNotify({ type: 'warning', message: '请输入分组名称' })
      return
    }

    try {
      await api.post('/categories', { name: newGroupName.value.trim() })
      showNotify({ type: 'success', message: '分组创建成功', duration: 1500 })
      newGroupName.value = ''
      showAddGroupDialog.value = false
    } catch (error: any) {
      console.error('创建分组失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '创建分组失败' })
    }
  }

  /**
   * 进入分组排序模式
   */
  const onEnterSortMode = (groups: BookGroup[]) => {
    // 复制当前分组列表（排除未分组）
    sortableGroups.value = groups.filter(g => g.name !== '未分组')
    showSortGroupsDialog.value = true
  }

  /**
   * 保存分组排序
   */
  const onSaveGroupOrder = async (): Promise<boolean> => {
    const orderedIds = sortableGroups.value.map(g => g.id)
    try {
      await api.put('/categories/reorder', { category_ids: orderedIds })
      showNotify({ type: 'success', message: '分组排序已保存', duration: 1500 })
      showSortGroupsDialog.value = false
      return true
    } catch (error: any) {
      console.error('保存分组排序失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
      return false
    }
  }

  /**
   * 取消分组排序
   */
  const onCancelSortMode = () => {
    sortableGroups.value = []
    showSortGroupsDialog.value = false
  }

  /**
   * 显示分组右键菜单
   */
  const showGroupContextMenu = (event: MouseEvent, group: BookGroup) => {
    contextMenuGroup.value = group
    // 计算菜单位置，确保不超出屏幕
    const x = Math.min(event.clientX, window.innerWidth - 150)
    const y = Math.min(event.clientY, window.innerHeight - 120)
    groupContextMenuPos.value = { x, y }
    showGroupContextMenuPopup.value = true
  }

  /**
   * 关闭分组右键菜单
   */
  const closeGroupContextMenu = () => {
    showGroupContextMenuPopup.value = false
  }

  /**
   * 打开修改分组名称对话框
   */
  const openRenameGroupDialog = () => {
    closeGroupContextMenu()
    if (contextMenuGroup.value) {
      renameGroupName.value = contextMenuGroup.value.name
      showRenameGroupDialog.value = true
    }
  }

  /**
   * 处理修改分组名称
   */
  const handleRenameGroup = async () => {
    if (!contextMenuGroup.value) return
    if (!renameGroupName.value.trim()) {
      showNotify({ type: 'warning', message: '请输入分组名称' })
      return
    }

    try {
      await api.put(`/categories/${contextMenuGroup.value.id}`, {
        name: renameGroupName.value.trim()
      })
      showNotify({ type: 'success', message: '分组名称修改成功', duration: 1500 })
      showRenameGroupDialog.value = false
    } catch (error: any) {
      console.error('修改分组名称失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '修改失败' })
    }
  }

  /**
   * 确认删除分组
   */
  const confirmDeleteGroup = async () => {
    closeGroupContextMenu()
    if (!contextMenuGroup.value) return

    const confirm = await showConfirmDialog({
      title: '确认删除',
      message: `确定要删除分组"${contextMenuGroup.value.name}"吗？分组内的书籍将自动移动到未分组。`
    }).catch(() => null)

    if (!confirm) return

    try {
      await api.delete(`/categories/${contextMenuGroup.value.id}`)
      showNotify({ type: 'success', message: '分组删除成功，书籍已移至未分组', duration: 1500 })
    } catch (error: any) {
      console.error('删除分组失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
    }
  }

  return {
    // 添加分组
    showAddGroupDialog,
    newGroupName,
    handleAddGroup,

    // 分组排序
    showSortGroupsDialog,
    sortableGroups,
    onEnterSortMode,
    onSaveGroupOrder,
    onCancelSortMode,

    // 分组右键菜单
    showGroupContextMenuPopup,
    groupContextMenuPos,
    contextMenuGroup,
    showGroupContextMenu,
    closeGroupContextMenu,

    // 重命名分组
    showRenameGroupDialog,
    renameGroupName,
    openRenameGroupDialog,
    handleRenameGroup,

    // 删除分组
    confirmDeleteGroup,
  }
}
