/**
 * HarmonyFileSaver 桥 - ArkTS 侧实现
 *
 * 通过 javaScriptProxy 注入到 WebView 的 window.HarmonyFileSaver，
 * 对接前端 nativeDownload.ts 中的 harmonyFileSaver。
 *
 * 前端调用：window.HarmonyFileSaver.saveFile(filename, base64Data)
 *
 * 实现方式：
 * - 通过 getContext() 获取应用沙箱文件目录（filesDir）
 * - 使用 @ohos.file.fs 将 Base64 数据写入文件
 * - 写入到沙箱 files/Downloads/ 子目录中
 */
import { fileIo as fs } from '@kit.CoreFileKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { common } from '@kit.AbilityKit';

const LOG_DOMAIN: number = 0xA046;
const LOG_TAG: string = 'HarmonyFileSaver';

export class HarmonyFileSaver {
  private context_: common.UIAbilityContext | null = null;

  constructor() {
    try {
      this.context_ = getContext(this) as common.UIAbilityContext;
    } catch (e) {
      hilog.error(LOG_DOMAIN, LOG_TAG, '无法获取 UIAbilityContext: %{public}s', String(e));
    }
  }

  /**
   * 保存文件
   * @param filename 文件名（不含路径）
   * @param base64Data Base64 编码的文件内容（不含 data:xxx;base64, 前缀）
   * @returns 'success' 表示成功，其他表示失败原因
   */
  saveFile(filename: string, base64Data: string): string {
    hilog.info(LOG_DOMAIN, LOG_TAG, 'saveFile 被调用: %{public}s', filename);

    if (!this.context_) {
      hilog.error(LOG_DOMAIN, LOG_TAG, 'UIAbilityContext 为空，无法保存文件');
      return 'error: no context';
    }

    if (!filename || filename.length === 0) {
      return 'error: invalid filename';
    }

    if (!base64Data || base64Data.length === 0) {
      return 'error: empty data';
    }

    try {
      // 解码 Base64 为字节数组
      const dataArray: Uint8Array | null = this.base64ToBytes_(base64Data);
      if (!dataArray || dataArray.length === 0) {
        return 'error: decode failed';
      }

      // 使用 context 的 filesDir 获取应用沙箱目录，避免硬编码路径
      const downloadDir: string = this.context_.filesDir + '/Downloads/';
      this.ensureDir_(downloadDir);

      const filePath: string = downloadDir + filename;
      const file: fs.File = fs.openSync(filePath, fs.OpenMode.CREATE | fs.OpenMode.WRITE | fs.OpenMode.TRUNC);
      fs.writeSync(file.fd, dataArray);
      fs.closeSync(file.fd);

      hilog.info(LOG_DOMAIN, LOG_TAG, '文件已保存到: %{public}s', filePath);
      return 'success';
    } catch (e) {
      hilog.error(LOG_DOMAIN, LOG_TAG, 'saveFile 异常: %{public}s', String(e));
      return 'error: ' + String(e);
    }
  }

  /**
   * 将 Base64 字符串解码为字节数组
   * 仅支持标准 Base64 字符集
   */
  private base64ToBytes_(base64: string): Uint8Array | null {
    try {
      const cleanBase64: string = base64.replace(/[\s\r\n]/g, '');
      const chars: string = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
      const lookup: Uint8Array = new Uint8Array(128);
      for (let i = 0; i < chars.length; i++) {
        lookup[chars.charCodeAt(i)] = i;
      }

      const len: number = cleanBase64.length;
      if (len % 4 !== 0) return null;

      let padding: number = 0;
      if (cleanBase64.charAt(len - 1) === '=') padding++;
      if (cleanBase64.charAt(len - 2) === '=') padding++;

      const bufferLength: number = (len * 3) / 4 - padding;
      const buffer: Uint8Array = new Uint8Array(bufferLength);
      let outputIndex: number = 0;
      let i: number = 0;

      while (i < len) {
        const a: number = lookup[cleanBase64.charCodeAt(i++)];
        const b: number = lookup[cleanBase64.charCodeAt(i++)];
        const c: number = lookup[cleanBase64.charCodeAt(i++)];
        const d: number = lookup[cleanBase64.charCodeAt(i++)];

        if (a === undefined || b === undefined) return null;

        const triple: number = ((a << 18) + (b << 12) + (c << 6) + d) & 0xffffff;

        buffer[outputIndex++] = (triple >> 16) & 0xff;
        if (c !== 128) buffer[outputIndex++] = (triple >> 8) & 0xff;
        if (d !== 128) buffer[outputIndex++] = triple & 0xff;
      }

      return buffer;
    } catch (e) {
      hilog.error(LOG_DOMAIN, LOG_TAG, 'Base64 解码失败: %{public}s', String(e));
      return null;
    }
  }

  /**
   * 确保目录存在，不存在则创建
   */
  private ensureDir_(dirPath: string): void {
    try {
      if (!fs.accessSync(dirPath)) {
        fs.mkdirSync(dirPath, true);
      }
    } catch (e) {
      hilog.warn(LOG_DOMAIN, LOG_TAG, '创建目录失败: %{public}s', String(e));
    }
  }
}