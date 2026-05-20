/**
 * AudioServiceProxy - UIAbility 侧的 IPC 代理
 *
 * 通过 javaScriptProxy 注入到 WebView 的 window.HarmonyAudio，
 * 将前端命令通过 RPC 转发到 ServiceExtensionAbility 中的音频引擎。
 *
 * 事件回调：service 通过 UI 回调 RemoteObject 推送事件，
 * 此对象将事件转发给 WebView（runJavaScript）。
 */
import { webview } from '@kit.ArkWeb';
import { rpc } from '@kit.IPCKit';
import { hilog } from '@kit.PerformanceAnalysisKit';

const LOG_DOMAIN: number = 0xA045;
const LOG_TAG: string = 'AudioProxy';

// ---- 模块级远程引用 ----

let g_remote: rpc.IRemoteObject | null = null;
let g_proxy: AudioServiceProxy | null = null;

/** 由 EntryAbility 在连接建立后调用，设置 service 的 remote */
export function setServiceRemote(remote: rpc.IRemoteObject): void {
  g_remote = remote;
  // 如果 proxy 已创建但还未注册回调，立即注册
  if (g_proxy) {
    g_proxy.registerEventCb_();
  }
}

// ---- UI 回调 RemoteObject（接收 service 推送的事件） ----

class UiEventStub extends rpc.RemoteObject {
  private proxy_: AudioServiceProxy;

  constructor(proxy: AudioServiceProxy) {
    super('UiEventStub');
    this.proxy_ = proxy;
  }

  onRemoteMessageRequest(
    code: number,
    data: rpc.MessageSequence,
    reply: rpc.MessageSequence,
    _option: rpc.MessageOption
  ): boolean {
    if (code === MSG_EVENT) {
      const event: string = data.readString();
      const payload: string = data.readString();
      this.proxy_.dispatchEvent(event, payload);
      reply.writeString('ok');
      return true;
    }
    reply.writeString('unknown code:' + code);
    return false;
  }
}

// ---- 协议常量 ----

const MSG_COMMAND: number = 1;  // UI -> Service: 命令
const MSG_REGISTER_CB: number = 2; // UI -> Service: 注册事件回调
const MSG_EVENT: number = 3;    // Service -> UI: 事件推送

// ---- Proxy 类 ----

export class AudioServiceProxy {
  private controller_: webview.WebviewController;
  private eventStub_: UiEventStub;

  constructor(controller: webview.WebviewController) {
    this.controller_ = controller;
    this.eventStub_ = new UiEventStub(this);
    g_proxy = this;
    this.registerEventCb_();
  }

  /** 发送命令到 service（fire-and-forget，返回空串表示当前不可用） */
  private async sendCmd_(method: string, ...args: string[]): Promise<string> {
    const remote: rpc.IRemoteObject | null = g_remote;
    if (!remote) return '';
    try {
      const data: rpc.MessageSequence = rpc.MessageSequence.create();
      const reply: rpc.MessageSequence = rpc.MessageSequence.create();
      const option: rpc.MessageOption = new rpc.MessageOption();
      data.writeString(method);
      data.writeInt(args.length);
      for (const a of args) {
        data.writeString(a);
      }
      const requestResult: rpc.RequestResult = await remote.sendMessageRequest(MSG_COMMAND, data, reply, option);
      const result: string = requestResult.reply.readString() || '';
      data.reclaim();
      reply.reclaim();
      return result;
    } catch (_e) { /* ignore */ }
    return '';
  }

  /** 向 service 注册 UI 侧的 event callback RemoteObject */
  async registerEventCb_(): Promise<void> {
    const remote: rpc.IRemoteObject | null = g_remote;
    if (!remote) return;
    try {
      const data: rpc.MessageSequence = rpc.MessageSequence.create();
      const reply: rpc.MessageSequence = rpc.MessageSequence.create();
      const option: rpc.MessageOption = new rpc.MessageOption();
      data.writeRemoteObject(this.eventStub_);
      await remote.sendMessageRequest(MSG_REGISTER_CB, data, reply, option);
      data.reclaim();
      reply.reclaim();
    } catch (_e) { /* ignore */ }
  }

  // ---------- javaScriptProxy 注入的方法 ----------

  async setPlaylist(timelineJson: string): Promise<void> {
    await this.sendCmd_('setPlaylist', timelineJson);
  }

  async play(): Promise<void> {
    await this.sendCmd_('play');
  }

  async pause(): Promise<void> {
    await this.sendCmd_('pause');
  }

  async resume(): Promise<void> {
    await this.sendCmd_('resume');
  }

  async stop(): Promise<void> {
    await this.sendCmd_('stop');
  }

  async seekGlobal(msJson: string): Promise<void> {
    await this.sendCmd_('seekGlobal', msJson);
  }

  async seekLocal(msJson: string): Promise<void> {
    await this.sendCmd_('seekLocal', msJson);
  }

  async seekToTrack(indexJson: string, offsetMsJson?: string): Promise<void> {
    if (offsetMsJson !== undefined) {
      await this.sendCmd_('seekToTrack', indexJson, offsetMsJson);
    } else {
      await this.sendCmd_('seekToTrack', indexJson);
    }
  }

  async setRate(rateJson: string): Promise<void> {
    await this.sendCmd_('setRate', rateJson);
  }

  async setMeta(metaJson: string): Promise<void> {
    await this.sendCmd_('setMeta', metaJson);
  }

  /** 由 UiEventStub 回调，转发事件到 WebView JS 侧 */
  async dispatchEvent(event: string, payload: string): Promise<void> {
    try {
      const safeEvent: string = event.replace(/[\\']/g, '\\$&');
      await this.controller_.runJavaScript(
        "window.__harmonyAudioEvent('" + safeEvent + "'," + payload + ")"
      );
    } catch (_e) { /* ignore */ }
  }
}
