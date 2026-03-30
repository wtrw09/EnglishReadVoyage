<template>
  <div class="user-management">
    <van-nav-bar
      :title="isAdmin ? '用户管理' : '个人信息'"
      left-text="返回"
      left-arrow
      fixed
      placeholder
      @click-left="goBack"
    />

    <div class="content">
      <!-- 管理员界面：创建用户按钮 -->
      <div v-if="isAdmin" class="action-bar">
        <van-button type="primary" size="small" @click="showCreateDialog">
          <i class="fas fa-plus" style="margin-right: 4px;"></i>
          新建用户
        </van-button>
      </div>

      <!-- 管理员界面：用户列表 -->
      <template v-if="isAdmin">
        <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
          <van-list
            v-model:loading="loading"
            :finished="finished"
            finished-text="没有更多了"
            @load="onLoad"
          >
            <van-swipe-cell v-for="user in users" :key="user.id">
              <van-cell
                :title="user.username"
                :label="`创建时间: ${formatDate(user.created_at)}`"
                @contextmenu.prevent="handleContextMenu($event, user)"
              >
                <template #icon>
                  <i :class="['fas', user.role === 'admin' ? 'fa-user-gear' : 'fa-user', 'user-icon', { admin: user.role === 'admin' }]" />
                </template>
                <template #value>
                  <div class="user-tags">
                    <van-tag :type="user.role === 'admin' ? 'danger' : 'primary'">
                      {{ user.role === 'admin' ? '管理员' : '用户' }}
                    </van-tag>
                    <van-tag :type="user.is_active ? 'success' : 'warning'">
                      {{ user.is_active ? '已激活' : '未激活' }}
                    </van-tag>
                  </div>
                </template>
              </van-cell>

              <template #right>
                <div class="slide-actions">
                  <van-button
                    v-if="user.username !== 'admin'"
                    square
                    type="primary"
                    text="编辑"
                    class="slide-btn"
                    @click="showEditDialog(user)"
                  />
                  <van-button
                    v-if="user.username !== 'admin' && user.is_active"
                    square
                    type="success"
                    text="管理书籍"
                    class="slide-btn"
                    @click="goToUserBookAssignment(user)"
                  />
                  <!-- 已激活用户显示重置密码，未激活用户显示获取邀请码 -->
                  <van-button
                    v-if="user.is_active"
                    square
                    type="warning"
                    text="重置密码"
                    class="slide-btn"
                    @click="showResetPasswordDialog(user)"
                  />
                  <van-button
                    v-else-if="user.username !== 'admin'"
                    square
                    type="success"
                    text="获取邀请码"
                    class="slide-btn"
                    @click="handleGetInvitationCode(user)"
                  />
                  <van-button
                    v-if="user.username !== 'admin'"
                    square
                    type="danger"
                    text="删除"
                    class="slide-btn"
                    @click="confirmDelete(user)"
                  />
                </div>
              </template>
            </van-swipe-cell>
          </van-list>
        </van-pull-refresh>
      </template>

      <!-- 普通用户界面：个人信息卡片 -->
      <template v-else>
        <div class="profile-card">
          <van-cell-group>
            <van-cell title="用户名" :value="authStore.user?.username" />
            <van-cell title="角色">
              <template #value>
                <van-tag :type="authStore.user?.role === 'admin' ? 'danger' : 'primary'">
                  {{ authStore.user?.role === 'admin' ? '管理员' : '用户' }}
                </van-tag>
              </template>
            </van-cell>
            <van-cell title="状态">
              <template #value>
                <van-tag :type="authStore.user?.is_active ? 'success' : 'warning'">
                  {{ authStore.user?.is_active ? '已激活' : '未激活' }}
                </van-tag>
              </template>
            </van-cell>
            <van-cell title="创建时间" :value="formatDate(authStore.user?.created_at || '')" />
          </van-cell-group>

          <div class="action-buttons">
            <van-button type="primary" block @click="showChangePasswordDialog">
              <i class="fas fa-lock" style="margin-right: 4px;"></i>
              修改密码
            </van-button>
          </div>
        </div>
      </template>
    </div>

    <!-- 创建用户对话框 -->
    <van-dialog
      v-model:show="createDialogVisible"
      title="创建新用户"
      show-cancel-button
      :before-close="onCreateBeforeClose"
      @cancel="resetCreateForm"
    >
      <van-form>
        <van-field
          v-model="createForm.username"
          label="用户名"
          placeholder="请输入用户名"
          :error-message="createUsernameError"
        />
      </van-form>
    </van-dialog>

    <!-- 编辑用户对话框 -->
    <van-dialog
      v-model:show="editDialogVisible"
      title="编辑用户"
      show-cancel-button
      @confirm="handleEdit"
      @cancel="resetEditForm"
    >
      <van-form>
        <van-field
          v-model="editForm.username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="[{ required: true, message: '请填写用户名' }]"
        />
        <van-field
          :model-value="roleDisplayText"
          label="角色"
          readonly
          clickable
          placeholder="选择角色"
          @click="showRolePicker = true"
        />
      </van-form>
    </van-dialog>

    <!-- 角色选择器 -->
    <van-popup v-model:show="showRolePicker" position="bottom">
      <van-picker
        :columns="roleColumns"
        @confirm="onRoleConfirm"
        @cancel="showRolePicker = false"
      />
    </van-popup>

    <!-- 重置密码对话框(管理员) -->
    <van-dialog
      v-model:show="resetPasswordVisible"
      title="重置密码"
      show-cancel-button
      @confirm="handleResetPassword"
    >
      <van-field
        v-model="newPassword"
        type="password"
        label="新密码"
        placeholder="请输入新密码"
      />
    </van-dialog>

    <!-- 修改密码对话框(普通用户) -->
    <van-dialog
      v-model:show="changePasswordVisible"
      title="修改密码"
      show-cancel-button
      :before-close="onChangePasswordBeforeClose"
      @cancel="resetChangePasswordForm"
    >
      <van-form>
        <van-field
          v-model="oldPassword"
          type="password"
          label="旧密码"
          placeholder="请输入旧密码"
          :error-message="oldPasswordError"
        />
        <van-field
          v-model="newUserPassword"
          type="password"
          label="新密码"
          placeholder="请输入新密码"
          :error-message="newPasswordError"
        />
      </van-form>
    </van-dialog>

    <!-- 用户右键菜单 -->
    <van-popup
      v-model:show="showContextMenuPopup"
      :style="{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }"
      round
      class="user-context-menu"
    >
      <div class="context-menu-list">
        <div class="context-menu-item" @click="handleMenuEdit">
          <i class="fas fa-pencil" />
          <span>编辑</span>
        </div>
        <div
          v-if="contextMenuUser?.is_active"
          class="context-menu-item"
          @click="handleMenuManageBooks"
        >
          <i class="fas fa-layer-group"></i>
          <span>管理书籍</span>
        </div>
        <div
          v-if="contextMenuUser?.is_active"
          class="context-menu-item"
          @click="handleMenuResetPassword"
        >
          <i class="fas fa-lock" />
          <span>重置密码</span>
        </div>
        <div
          v-else-if="contextMenuUser?.username !== 'admin'"
          class="context-menu-item"
          @click="handleMenuGetInvitationCode"
        >
          <i class="fas fa-ticket" />
          <span>获取邀请码</span>
        </div>
        <div
          v-if="contextMenuUser?.username !== 'admin'"
          class="context-menu-item danger"
          @click="handleMenuDelete"
        >
          <i class="fas fa-trash" />
          <span>删除</span>
        </div>
      </div>
    </van-popup>

    <!-- 邀请码展示对话框 -->
    <van-dialog
      v-model:show="invitationVisible"
      title="用户创建成功"
      :show-confirm-button="false"
      :show-cancel-button="false"
      close-on-click-overlay
    >
      <div class="invitation-info">
        <div class="info-item">
          <span class="label">用户名</span>
          <span class="value">{{ createdUser?.username }}</span>
        </div>
        <div class="info-item code-item">
          <span class="label">邀请码</span>
          <div class="code-wrapper">
            <span class="code">{{ createdUser?.invitation_code }}</span>
            <van-button
              type="primary"
              size="small"
              @click="copyInvitationCode"
            >
              <i class="fas fa-copy" style="margin-right: 4px;"></i>
              复制
            </van-button>
          </div>
        </div>
        <div class="info-item expiry-item">
          <span class="label">有效期至</span>
          <span class="value">{{ formatDate(createdUser?.invitation_expires || '') }}</span>
        </div>
        <van-divider />
        <p class="hint">请复制邀请码发送给用户，用户可使用邀请码激活账户并设置密码。</p>
        <van-button type="default" block round @click="invitationVisible = false">
          关闭
        </van-button>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { 
  showNotify, 
  showConfirmDialog,
} from 'vant'
import { useAuthStore, type UserDetail } from '@/store/auth'

interface CreateForm {
  username: string
}

interface EditForm {
  id: number
  username: string
  role: string
}

interface CreatedUserInfo {
  username: string
  invitation_code: string
  invitation_expires: string
}

const router = useRouter()
const authStore = useAuthStore()

// 计算属性
const isAdmin = computed(() => authStore.isAdmin)

// 角色显示文本（英文值转中文）
const roleMap: Record<string, string> = {
  'user': '用户',
  'admin': '管理员'
}
const roleDisplayText = computed(() => roleMap[editForm.role] || '选择角色')

// 列表数据
const users = ref<UserDetail[]>([])
const loading = ref(false)
const finished = ref(true)
const refreshing = ref(false)

// 创建用户
const createDialogVisible = ref(false)
const createForm = reactive<CreateForm>({
  username: ''
})
const createUsernameError = ref('')

// 编辑用户
const editDialogVisible = ref(false)
const editForm = reactive<EditForm>({
  id: 0,
  username: '',
  role: 'user'
})
const showRolePicker = ref(false)
const roleColumns = [
  { text: '用户', value: 'user' },
  { text: '管理员', value: 'admin' }
]

// 重置密码(管理员)
const resetPasswordVisible = ref(false)
const selectedUser = ref<UserDetail | null>(null)
const newPassword = ref('')

// 修改密码(普通用户)
const changePasswordVisible = ref(false)
const oldPassword = ref('')
const newUserPassword = ref('')
const oldPasswordError = ref('')
const newPasswordError = ref('')

// 邀请码展示
const invitationVisible = ref(false)
const createdUser = ref<CreatedUserInfo | null>(null)

// 右键菜单
const showContextMenuPopup = ref(false)
const contextMenuUser = ref<UserDetail | null>(null)

// 显示右键菜单
const handleContextMenu = (_event: MouseEvent, user: UserDetail) => {
  contextMenuUser.value = user
  showContextMenuPopup.value = true
}

// 关闭右键菜单
const closeContextMenu = () => {
  showContextMenuPopup.value = false
}

// 菜单操作
const handleMenuEdit = () => {
  closeContextMenu()
  if (contextMenuUser.value) {
    showEditDialog(contextMenuUser.value)
  }
}

const handleMenuResetPassword = () => {
  closeContextMenu()
  if (contextMenuUser.value) {
    showResetPasswordDialog(contextMenuUser.value)
  }
}

const handleMenuGetInvitationCode = () => {
  closeContextMenu()
  if (contextMenuUser.value) {
    handleGetInvitationCode(contextMenuUser.value)
  }
}

const handleMenuManageBooks = () => {
  closeContextMenu()
  if (contextMenuUser.value) {
    goToUserBookAssignment(contextMenuUser.value)
  }
}

const handleMenuDelete = () => {
  closeContextMenu()
  if (contextMenuUser.value) {
    confirmDelete(contextMenuUser.value)
  }
}

const goBack = () => {
  router.back()
}

const goToUserBookAssignment = (user: UserDetail) => {
  router.push({
    name: 'UserBookAssignment',
    params: { userId: user.id }
  })
}

const formatDate = (dateStr: string): string => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const loadUsers = async () => {
  const result = await authStore.fetchUsers()
  if (result.success && result.data) {
    users.value = result.data
  } else if (!result.success) {
    showNotify({ type: 'danger', message: result.message })
  }
}

const onLoad = async () => {
  loading.value = true
  await loadUsers()
  loading.value = false
  finished.value = true
}

const onRefresh = async () => {
  await loadUsers()
  refreshing.value = false
  showNotify({ type: 'success', message: '刷新成功', duration: 1500 })
}

// 创建用户
const showCreateDialog = () => {
  createForm.username = ''
  createUsernameError.value = ''
  createDialogVisible.value = true
}

const resetCreateForm = () => {
  createForm.username = ''
  createUsernameError.value = ''
}

const onCreateBeforeClose = async (action: 'confirm' | 'cancel') => {
  if (action === 'confirm') {
    const success = await handleCreate()
    return success
  }
  return true
}

const handleCreate = async (): Promise<boolean> => {
  // 清空之前的错误
  createUsernameError.value = ''

  if (!createForm.username.trim()) {
    createUsernameError.value = '请填写用户名'
    return false
  }

  const result = await authStore.createUser(createForm.username.trim())
  if (result.success && result.data) {
    showNotify({
      type: 'success',
      message: '创建成功',
      duration: 1000
    })
    createdUser.value = {
      username: result.data.user.username,
      invitation_code: result.data.invitation_code,
      invitation_expires: result.data.invitation_expires
    }
    createDialogVisible.value = false
    invitationVisible.value = true
    await loadUsers()
    return true
  } else if (!result.success) {
    // 确保错误消息是字符串类型
    const errorMsg = typeof result.message === 'string' ? result.message : '创建用户失败'
    createUsernameError.value = errorMsg
    return false
  }
  return false
}

// 编辑用户
const showEditDialog = (user: UserDetail) => {
  editForm.id = user.id
  editForm.username = user.username
  editForm.role = user.role
  editDialogVisible.value = true
}

const resetEditForm = () => {
  editForm.id = 0
  editForm.username = ''
  editForm.role = 'user'
}

const onRoleConfirm = ({ selectedOptions }: { selectedOptions: { value: string }[] }) => {
  editForm.role = selectedOptions[0].value
  showRolePicker.value = false
}

const handleEdit = async () => {
  if (!editForm.username.trim()) {
    showNotify({ type: 'danger', message: '请填写用户名' })
    return
  }

  const result = await authStore.updateUser(editForm.id, {
    username: editForm.username.trim(),
    role: editForm.role
  })

  if (result.success) {
    showNotify({ type: 'success', message: '更新成功', duration: 1500 })
    await loadUsers()
  } else {
    showNotify({ type: 'danger', message: result.message })
  }
}

// 重置密码(管理员)
const showResetPasswordDialog = (user: UserDetail) => {
  selectedUser.value = user
  newPassword.value = ''
  resetPasswordVisible.value = true
}

const handleResetPassword = async () => {
  if (!newPassword.value.trim()) {
    showNotify({ type: 'danger', message: '请填写新密码' })
    return
  }

  if (!selectedUser.value) return

  const result = await authStore.resetPassword(selectedUser.value.id, newPassword.value.trim())
  if (result.success) {
    showNotify({ type: 'success', message: '密码重置成功', duration: 1500 })
  } else {
    showNotify({ type: 'danger', message: result.message })
  }
}

// 获取用户邀请码
const handleGetInvitationCode = async (user: UserDetail) => {
  const result = await authStore.getUserInvitationCode(user.id)
  if (result.success && result.data) {
    createdUser.value = {
      username: result.data.username,
      invitation_code: result.data.invitation_code || '',
      invitation_expires: result.data.invitation_expires || ''
    }
    invitationVisible.value = true
  } else {
    const errorMsg = (result as { message?: string }).message || '获取邀请码失败'
    showNotify({ type: 'danger', message: errorMsg })
  }
}

// 修改密码(普通用户)
const showChangePasswordDialog = () => {
  oldPassword.value = ''
  newUserPassword.value = ''
  oldPasswordError.value = ''
  newPasswordError.value = ''
  changePasswordVisible.value = true
}

const resetChangePasswordForm = () => {
  oldPassword.value = ''
  newUserPassword.value = ''
  oldPasswordError.value = ''
  newPasswordError.value = ''
}

const handleChangePassword = async () => {
  // 清空之前的错误
  oldPasswordError.value = ''
  newPasswordError.value = ''

  // 验证空值（同时检查两个字段）
  let hasError = false
  if (!oldPassword.value.trim()) {
    oldPasswordError.value = '请填写旧密码'
    hasError = true
  }

  if (!newUserPassword.value.trim()) {
    newPasswordError.value = '请填写新密码'
    hasError = true
  }

  if (hasError) {
    return false
  }

  // 调用后端API
  const result = await authStore.changePassword(
    oldPassword.value.trim(),
    newUserPassword.value.trim()
  )

  if (result.success) {
    resetChangePasswordForm()
    showNotify({
      type: 'success',
      message: '密码修改成功',
      duration: 1000
    })
    return true
  } else {
    // 同时处理前端和后端的错误
    const errorMsg = result.message || '密码修改失败'
    console.log('后端返回错误:', errorMsg)

    // 先根据后端错误类型在对应字段显示错误
    if (errorMsg.indexOf('无法验证凭证') !== -1 || errorMsg.indexOf('旧密码') !== -1 || errorMsg.indexOf('原密码') !== -1) {
      oldPasswordError.value = '旧密码不正确'
    } else if (errorMsg.indexOf('相同') !== -1) {
      newPasswordError.value = errorMsg
    }

    // 再检查新密码长度（前端验证），不覆盖后端错误
    if (newUserPassword.value.trim().length < 6) {
      if (!newPasswordError.value) {
        newPasswordError.value = '新密码长度不能少于6位'
      }
    }

    return false
  }
}

const onChangePasswordBeforeClose = async (action: 'confirm' | 'cancel') => {
  if (action === 'confirm') {
    const success = await handleChangePassword()
    return success
  }
  return true
}

// 删除用户
const confirmDelete = (user: UserDetail) => {
  showConfirmDialog({
    title: '确认删除',
    message: `确定要删除用户 "${user.username}" 吗？此操作不可恢复。`,
    confirmButtonText: '删除',
    confirmButtonColor: '#ee0a24'
  }).then(async () => {
    const result = await authStore.deleteUser(user.id)
    if (result.success) {
      showNotify({ type: 'success', message: '删除成功', duration: 1500 })
      await loadUsers()
    } else {
      showNotify({ type: 'danger', message: result.message })
    }
  }).catch(() => {
    // 取消删除
  })
}

// 复制邀请码
const copyInvitationCode = () => {
  if (!createdUser.value || !createdUser.value.invitation_code) return

  const text = `用户名: ${createdUser.value.username}\n邀请码: ${createdUser.value.invitation_code}`

  // 兼容性复制：优先使用 Clipboard API，降级使用 execCommand
  const doCopy = (): boolean => {
    // 尝试使用 Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        showNotify({
          type: 'success',
          message: '邀请码已复制',
          duration: 1500
        })
      }).catch(() => {
        // Clipboard API 失败，尝试降级方案
        if (!fallbackCopy()) {
          showNotify({
            type: 'warning',
            message: '复制失败，请手动复制',
            duration: 2000
          })
        }
      })
      return true
    }
    // 使用降级方案
    return fallbackCopy()
  }

  // 降级复制方案（兼容 HTTP 环境）
  const fallbackCopy = (): boolean => {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    try {
      const successful = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (successful) {
        showNotify({
          type: 'success',
          message: '邀请码已复制',
          duration: 1500
        })
      }
      return successful
    } catch (err) {
      document.body.removeChild(textarea)
      return false
    }
  }

  if (!doCopy()) {
    showNotify({
      type: 'warning',
      message: '复制失败，请手动复制',
      duration: 2000
    })
  }
}

onMounted(() => {
  if (isAdmin.value) {
    loadUsers()
  }
})
</script>

<style scoped lang="less">
.user-management {
  min-height: 100vh;
  background: #f7f8fa;
}

.content {
  padding: 12px;
}

.action-bar {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}

.user-icon {
  font-size: 24px;
  margin-right: 12px;
  color: #1989fa;
  align-self: center;

  &.admin {
    color: #ee0a24;
  }
}

.user-tags {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
}

.slide-actions {
  display: flex;
  height: 100%;
}

.slide-btn {
  height: 100%;
  min-width: 60px;
}

.invitation-info {
  padding: 20px;

  .info-item {
    display: flex;
    flex-direction: column;
    margin-bottom: 16px;

    .label {
      font-size: 12px;
      color: #969799;
      margin-bottom: 4px;
    }

    .value {
      font-size: 14px;
      color: #323233;
    }

    &.code-item {
      .code-wrapper {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 4px;

        .code {
          font-size: 18px;
          font-weight: bold;
          color: #1989fa;
          font-family: monospace;
          letter-spacing: 1px;
          flex: 1;
          min-width: 0;
          word-break: break-all;
        }
      }
    }

    &.expiry-item {
      .value {
        color: #ff976a;
      }
    }
  }

  .hint {
    color: #969799;
    font-size: 12px;
    line-height: 1.5;
    margin: 12px 0;
  }
}

.profile-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;

  .action-buttons {
    padding: 16px;
    margin-top: 12px;
  }
}

/* 用户右键菜单 */
.user-context-menu {
  position: fixed !important;
  width: 150px;
  top: 50% !important;
  left: 50% !important;
  transform: translate(-50%, -50%) !important;
}

.context-menu-list {
  padding: 8px 0;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  font-size: 14px;
  color: #323233;

  &:hover {
    background-color: #f5f5f5;
  }

  &:active {
    background-color: #e8e8e8;
  }

  &.danger {
    color: #ee0a24;

    i {
      color: #ee0a24;
    }
  }

  i {
    font-size: 18px;
    color: #969799;
  }
}
</style>
