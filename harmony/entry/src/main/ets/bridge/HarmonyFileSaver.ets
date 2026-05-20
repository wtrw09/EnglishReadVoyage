/**
 * HarmonyFileSaver 桥 - ArkTS 侧实现
 *
 * 通过 javaScriptProxy 注入到 WebView 的 window.HarmonyFileSaver，
 * 对接前端 nativeDownload.ts 中的 harmonyFileSaver。
 *
 * 前端调用：window.HarmonyFileSaver.saveFile(filename, base64Data)
 *
 * 实现方式：
 * 1. 同步阶段：将 Base64 数据写入沙箱 filesDir/Downloads/（始终可靠）
 * 2. 异步阶段：弹出 DocumentViewPicker 系统保存对话框，让用户选择公开保存位置
 *    - 若用户取消或出错，沙箱内的文件仍可作为兜底
 */
import { fileIo as fs } from '@kit.CoreFileKit';
import { picker } from '@kit.CoreFileKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { common } from '@kit.AbilityKit';

const LOG_DOMAIN: number = 0xA046;
const LOG_TAG: string = 'HarmonyFileSaver';

export class HarmonyFileSaver {
  private context_: common.UIAbilityContext | null = null;

  constructor(ctx: common.UIAbilityContext) {
    this.context_ = ctx;
  }

  /**
   * 保存文件（同步 + 异步双阶段）
   *
   * 阶段1 - 同步：写入沙箱 filesDir/Downloads/（应用私有目录，始终可靠）
   * 阶段2 - 异步：弹出 DocumentViewPicker，让用户选择公开保存位置
   *
   * @param filename 文件名（不含路径）
   * @param base64Data Base64 编码的文件内容（不含 data:xxx;base64, 前缀）
   * @returns 'success' 表示同步阶段成功，其他表示失败原因
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

      // === 阶段1（同步）：写入沙箱目录（始终可靠） ===
      const sandboxDir: string = this.context_.filesDir + '/Downloads/';
      this.ensureDir_(sandboxDir);

      const sandboxPath: string = sandboxDir + filename;
      const file: fs.File = fs.openSync(sandboxPath, fs.OpenMode.READ_WRITE);
      fs.writeSync(file.fd, dataArray);
      fs.closeSync(file.fd);

      hilog.info(LOG_DOMAIN, LOG_TAG, '阶段1（沙箱）完成: %{public}s', sandboxPath);

      // === 阶段2（异步）：弹出系统保存对话框 ===
      // 用户可以在系统文件管理器中自由选择保存位置（如 Documents、Downloads）
      // 此阶段失败不影响导出结果（沙箱内已有文件）
      this.tryPublicSaveAsync_(sandboxPath, filename);

      return 'success';
    } catch (e) {
      hilog.error(LOG_DOMAIN, LOG_TAG, 'saveFile 异常: %{public}s', String(e));
      return 'error: ' + String(e);
    }
  }

  /**
   * 阶段2（异步）：通过 DocumentViewPicker 弹出系统保存对话框
   * 将沙箱中的文件复制到用户选择的公开位置
   */
  private tryPublicSaveAsync_(sourcePath: string, filename: string): void {
    try {
      if (!this.context_) {
        hilog.warn(LOG_DOMAIN, LOG_TAG, 'tryPublicSaveAsync_: context 为空，跳过');
        return;
      }

      const pickerInstance = new picker.DocumentViewPicker(this.context_);

      const options = new picker.DocumentSaveOptions();
      options.newFileNames = [filename];
      pickerInstance.save(options).then((uris: string[]) => {
        if (uris && uris.length > 0) {
          // 将沙箱文件复制到用户选择的公开位置
          try {
            const srcFd: number = fs.openSync(sourcePath, fs.OpenMode.READ_ONLY).fd;
            const stat = fs.statSync(sourcePath);
            const buf: ArrayBuffer = new ArrayBuffer(stat.size);
            fs.readSync(srcFd, buf);
            fs.closeSync(srcFd);
            const destFd: number = fs.openSync(uris[0], fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE).fd;
            fs.writeSync(destFd, buf);
            fs.closeSync(destFd);
            hilog.info(LOG_DOMAIN, LOG_TAG, '阶段2（公开）完成: %{public}s', uris[0]);
          } catch (copyErr) {
            hilog.warn(LOG_DOMAIN, LOG_TAG, '复制到公开目录失败: %{public}s', String(copyErr));
          }
        } else {
          hilog.warn(LOG_DOMAIN, LOG_TAG, '阶段2完成，但未返回 URI');
        }
      }).catch((err: Error) => {
        // 用户取消或系统错误：不视为导出失败
        hilog.warn(LOG_DOMAIN, LOG_TAG, '阶段2取消/失败: %{public}s', String(err));
      });
    } catch (e) {
      // DocumentViewPicker 不可用（如 API 版本过低）时静默忽略
      hilog.warn(LOG_DOMAIN, LOG_TAG, '阶段2（公开）不可用: %{public}s', String(e));
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