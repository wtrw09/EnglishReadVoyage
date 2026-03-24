import { showConfirmDialog } from 'vant'

/**
 * 显示错误消息对话框
 * 使用 Vant Dialog 替代 Notify，确保用户点击确定按钮后关闭
 * 适合移动端操作，比 Notify 的 X 按钮更易点击
 * @param message 错误消息内容
 */
export function showErrorDialog(message: string): void {
  showConfirmDialog({
    title: '提示',
    message: message,
    confirmButtonText: '确定',
    cancelButtonText: '',
    showCancelButton: false,
  })
}

/**
 * 显示警告消息对话框
 * @param message 警告消息内容
 */
export function showWarningDialog(message: string): void {
  showConfirmDialog({
    title: '警告',
    message: message,
    confirmButtonText: '确定',
    cancelButtonText: '',
    showCancelButton: false,
  })
}

/**
 * 显示成功消息对话框
 * @param message 成功消息内容
 */
export function showSuccessDialog(message: string): void {
  showConfirmDialog({
    title: '成功',
    message: message,
    confirmButtonText: '确定',
    cancelButtonText: '',
    showCancelButton: false,
  })
}
