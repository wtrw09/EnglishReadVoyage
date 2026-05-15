/**
 * 跨平台文件保存抽象层
 *
 * 目标：统一 Web / Android (Capacitor) / HarmonyOS 三种运行时的文件下载行为。
 *
 * 设计原则：
 * - Web 环境：保留现有的 createObjectURL + <a>.click() 方式（桌面浏览器正常工作）
 * - Android (Capacitor)：使用 @capacitor/filesystem 插件写入 Downloads 目录
 * - HarmonyOS：调用原生桥接 window.HarmonyFileSaver
 *
 * 使用方式：
 *   import { saveFile } from '@/utils/nativeDownload'
 *   await saveFile(blob, 'books.zip')
 */


// ============================================================
// 接口定义
// ============================================================

export interface NativeFileSaver {
  /**
   * 将 Blob 保存为文件
   * @param blob 要保存的二进制数据
   * @param filename 文件名（不含路径）
   * @returns 是否保存成功
   */
  save(blob: Blob, filename: string): Promise<boolean>
}

// ============================================================
// Web 环境（桌面浏览器）
// ============================================================

const webFileSaver: NativeFileSaver = {
  async save(blob: Blob, filename: string): Promise<boolean> {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    // 延迟释放 Blob URL，避免浏览器提前回收
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    return true
  }
}

// ============================================================
// Android (Capacitor) 环境
// ============================================================

/**
 * 当前是否有 Capacitor Filesystem 插件可用
 */
function hasCapacitorFilesystem(): boolean {
  const cap = (window as any).Capacitor
  if (!cap) return false
  const plugin = cap.Plugins?.Filesystem
  return !!plugin
}

/**
 * 将 Blob 转换为 Base64 字符串
 */
function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      const base64 = (reader.result as string).split(',')[1]
      resolve(base64 || '')
    }
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

const capacitorFileSaver: NativeFileSaver = {
  async save(blob: Blob, filename: string): Promise<boolean> {
    try {
      const cap = (window as any).Capacitor
      const { Filesystem, Directory, Encoding } = cap.Plugins

      // 将 blob 转为 base64
      const base64Data = await blobToBase64(blob)

      // 写入 Downloads 目录
      await Filesystem.writeFile({
        path: filename,
        data: base64Data,
        directory: Directory.Downloads,
        encoding: Encoding.Base64
      })

      console.log('[nativeDownload] Capacitor: 文件已保存到 Downloads:', filename)
      return true
    } catch (e) {
      console.error('[nativeDownload] Capacitor: 文件保存失败', e)
      return false
    }
  }
}

// ============================================================
// HarmonyOS 环境
// ============================================================

/**
 * 当前是否有鸿蒙原生桥接可用
 */
function hasHarmonyFileSaver(): boolean {
  return typeof window !== 'undefined' && !!(window as any).HarmonyFileSaver
}

const harmonyFileSaver: NativeFileSaver = {
  async save(blob: Blob, filename: string): Promise<boolean> {
    try {
      const base64Data = await blobToBase64(blob)
      const H = (window as any).HarmonyFileSaver

      if (H && typeof H.saveFile === 'function') {
        const result = H.saveFile(filename, base64Data)
        if (result === true || result === 'success') {
          console.log('[nativeDownload] HarmonyOS: 文件已保存:', filename)
          return true
        } else {
          console.error('[nativeDownload] HarmonyOS: 保存返回失败:', result)
          return false
        }
      } else {
        console.error('[nativeDownload] HarmonyOS: HarmonyFileSaver.saveFile 不可用')
        return false
      }
    } catch (e) {
      console.error('[nativeDownload] HarmonyOS: 文件保存失败', e)
      return false
    }
  }
}

// ============================================================
// 平台选择
// ============================================================

let cachedSaver: NativeFileSaver | null = null

/**
 * 获取当前平台对应的文件保存器
 * 会在首次调用时缓存，后续直接返回缓存值
 */
export function getFileSaver(): NativeFileSaver {
  if (cachedSaver) return cachedSaver

  // 优先级：HarmonyOS > Capacitor > Web
  if (hasHarmonyFileSaver()) {
    cachedSaver = harmonyFileSaver
  } else if (hasCapacitorFilesystem()) {
    cachedSaver = capacitorFileSaver
  } else {
    cachedSaver = webFileSaver
  }

  return cachedSaver
}

// ============================================================
// 便捷 API
// ============================================================

/**
 * 保存文件到本地（跨平台统一入口）
 *
 * @param blob 要保存的二进制数据
 * @param filename 文件名（不含路径）
 * @returns 是否保存成功
 *
 * @example
 * import { saveFile } from '@/utils/nativeDownload'
 *
 * // 从 API 获取文件 blob
 * const response = await fetch('/api/export')
 * const blob = await response.blob()
 *
 * // 保存到本地
 * const success = await saveFile(blob, 'books.zip')
 * if (success) {
 *   showToast('文件已保存')
 * }
 */
export async function saveFile(blob: Blob, filename: string): Promise<boolean> {
  const saver = getFileSaver()
  return saver.save(blob, filename)
}

/**
 * 检测当前环境是否支持原生文件保存
 * （用于 UI 层面决定是否显示下载相关功能）
 */
export function supportsNativeDownload(): boolean {
  return hasHarmonyFileSaver() || hasCapacitorFilesystem()
}

/**
 * 获取当前平台的描述
 */
export function getPlatformName(): 'web' | 'android' | 'harmony' {
  if (hasHarmonyFileSaver()) return 'harmony'
  if (hasCapacitorFilesystem()) return 'android'
  return 'web'
}
