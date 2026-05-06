import web_webview from '@ohos.web.webview';
import { common } from '@kit.AbilityKit';
import { HarmonyAudio } from '../bridge/HarmonyAudio';
import { AVSessionMgr } from '../bridge/AVSessionMgr';

// 模拟 HTTP 基地址（用于绕过 resource:// 协议 CORS 限制）
const MOCK_BASE: string = 'http://harmony.local/';

/** 根据文件扩展名返回对应的 MIME Type */
function mimeTypeOf(path: string): string {
  if (path.endsWith('.html')) return 'text/html';
  if (path.endsWith('.css')) return 'text/css';
  if (path.endsWith('.js')) return 'text/javascript';
  if (path.endsWith('.svg')) return 'image/svg+xml';
  if (path.endsWith('.png')) return 'image/png';
  if (path.endsWith('.jpg') || path.endsWith('.jpeg')) return 'image/jpeg';
  if (path.endsWith('.gif')) return 'image/gif';
  if (path.endsWith('.woff2')) return 'font/woff2';
  if (path.endsWith('.woff')) return 'font/woff';
  if (path.endsWith('.ttf') || path.endsWith('.otf')) return 'font/ttf';
  if (path.endsWith('.ico')) return 'image/x-icon';
  if (path.endsWith('.json')) return 'application/json';
  if (path.endsWith('.pdf')) return 'application/pdf';
  return 'text/plain';
}

@Entry
@Component
struct Index {
  private controller: web_webview.WebviewController = new web_webview.WebviewController();
  private avSessionMgr: AVSessionMgr = new AVSessionMgr();
  private harmonyAudio: HarmonyAudio = new HarmonyAudio(this.controller, this.avSessionMgr);

  aboutToAppear(): void {
    const ctx: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;
    this.avSessionMgr.create(ctx, this.harmonyAudio);
  }

  build() {
    Column() {
      // 使用模拟 HTTP URL 代替 $rawfile，配合 onInterceptRequest 绕过 CORS 限制
      Web({ src: MOCK_BASE + 'dist/index.html', controller: this.controller })
        .javaScriptProxy({
          controller: this.controller,
          object: this.harmonyAudio,
          name: 'HarmonyAudio',
          methodList: [
            'setPlaylist', 'play', 'pause', 'resume', 'stop',
            'seekGlobal', 'seekLocal', 'seekToTrack', 'setRate', 'setMeta'
          ]
        })
        .javaScriptAccess(true)
        .fileAccess(true)
        .domStorageAccess(true)
        .onInterceptRequest((event) => {
          if (!event) {
            return null;
          }
          const requestUrl: string = event.request.getRequestUrl();
          if (!requestUrl.startsWith(MOCK_BASE)) {
            return null;
          }
          // 提取相对路径（如 dist/index.html、dist/assets/app.js）
          const relativePath: string = requestUrl.substring(MOCK_BASE.length);
          if (!relativePath) {
            return null;
          }
          // 通过 $rawfile 加载资源，并返回正确的 MIME Type
          const response: WebResourceResponse = new WebResourceResponse();
          response.setResponseData($rawfile(relativePath));
          response.setResponseEncoding('utf-8');
          response.setResponseMimeType(mimeTypeOf(relativePath));
          response.setResponseCode(200);
          response.setReasonMessage('OK');
          return response;
        })
        .width('100%')
        .height('100%')
        .backgroundColor(Color.White)
    }
    .width('100%')
    .height('100%')
  }
}