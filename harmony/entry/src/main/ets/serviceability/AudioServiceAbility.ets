/**
 * AudioServiceAbility - ServiceExtensionAbility
 *
 * 独立于 UIAbility 生命周期的音频服务，承载 HarmonyAudioService 中的
 * media.AVPlayer，实现长时间后台音频播放。
 *
 * 通信方式：
 * - 接收命令：UIAbility 通过 RPC（onRemoteRequest）发送 JSON 命令
 * - 推送事件：通过 UIAbility 预先注册的 UiEventStub RemoteObject 推送
 */
import { AppServiceExtensionAbility, Want } from '@kit.AbilityKit';
import { rpc } from '@kit.IPCKit';
import { backgroundTaskManager } from '@kit.BackgroundTasksKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { HarmonyAudioService } from '../bridge/HarmonyAudioService';

const LOG_DOMAIN: number = 0xA045;
const LOG_TAG: string = 'AudioSvcAbility';

// 与 AudioServiceProxy 中一致的消息码
const MSG_COMMAND: number = 1;
const MSG_REGISTER_CB: number = 2;
const MSG_EVENT: number = 3;

/** 服务端的 RemoteObject，处理 RPC 请求 */
class AudioServiceStub extends rpc.RemoteObject {
  private audioSvc_: HarmonyAudioService;
  private uiEventCbObj_: rpc.IRemoteObject | null = null;

  constructor(audioSvc: HarmonyAudioService) {
    super('AudioServiceStub');
    this.audioSvc_ = audioSvc;

    // 注册音频引擎的事件回调，推送到 UIAbility
    this.audioSvc_.setEventCallback((event: string, payload: string) => {
      this.sendEventToUI_(event, payload);
    });
  }

  onRemoteMessageRequest(
    code: number,
    data: rpc.MessageSequence,
    reply: rpc.MessageSequence,
    option: rpc.MessageOption
  ): boolean {
    try {
      switch (code) {
        case MSG_COMMAND:
          return this.handleCommand_(data, reply);
        case MSG_REGISTER_CB:
          return this.handleRegisterCb_(data, reply);
        default:
          reply.writeString('unknown code:' + code);
          return false;
      }
    } catch (e) {
      hilog.error(LOG_DOMAIN, LOG_TAG, 'onRemoteRequest error: %{public}s', String(e));
      reply.writeString('error:' + String(e));
      return true;
    }
  }

  /** 处理命令：解析 method + args，调用音频引擎相应方法 */
  private handleCommand_(data: rpc.MessageSequence, reply: rpc.MessageSequence): boolean {
    const method: string = data.readString();
    const argCount: number = data.readInt();
    const args: string[] = [];
    for (let i = 0; i < argCount; i++) {
      args.push(data.readString());
    }

    const svc: HarmonyAudioService = this.audioSvc_;

    switch (method) {
      case 'setPlaylist':
        svc.setPlaylist(args[0] || '[]');
        reply.writeString('ok');
        break;
      case 'play':
        svc.play();
        reply.writeString('ok');
        break;
      case 'pause':
        svc.pause();
        reply.writeString('ok');
        break;
      case 'resume':
        svc.resume();
        reply.writeString('ok');
        break;
      case 'stop':
        svc.stop();
        reply.writeString('ok');
        break;
      case 'seekGlobal':
        svc.seekGlobal(args.length > 0 ? JSON.stringify(Number(JSON.parse(args[0]))) : '0');
        reply.writeString('ok');
        break;
      case 'seekLocal':
        svc.seekLocal(args.length > 0 ? JSON.stringify(Number(JSON.parse(args[0]))) : '0');
        reply.writeString('ok');
        break;
      case 'seekToTrack': {
        const idx: string = args.length > 0 ? args[0] : '0';
        const offsetMs: string = args.length > 1 ? args[1] : '0';
        svc.seekToTrack(idx, offsetMs);
        reply.writeString('ok');
        break;
      }
      case 'setRate':
        svc.setRate(args.length > 0 ? JSON.stringify(Number(JSON.parse(args[0]))) : '1.0');
        reply.writeString('ok');
        break;
      case 'setMeta':
        // meta 解析后调用 setMeta
        try {
          const meta: Record<string, string> = JSON.parse(args[0] || '{}');
          svc.setMeta(meta.title || '', meta.artist || '');
        } catch { /* ignore */ }
        reply.writeString('ok');
        break;
      default:
        reply.writeString('unknown method:' + method);
    }
    return true;
  }

  /** 注册 UI 侧的 event 回调 RemoteObject */
  private handleRegisterCb_(data: rpc.MessageSequence, reply: rpc.MessageSequence): boolean {
    const obj: rpc.IRemoteObject | null = data.readRemoteObject();
    if (obj) {
      this.uiEventCbObj_ = obj;
      hilog.info(LOG_DOMAIN, LOG_TAG, 'UI event callback registered');
    }
    reply.writeString('ok');
    return true;
  }

  /** 通过 UI 侧注册的 RemoteObject 推送事件 */
  private async sendEventToUI_(event: string, payload: string): Promise<void> {
    if (!this.uiEventCbObj_) return;
    try {
      const data: rpc.MessageSequence = rpc.MessageSequence.create();
      const replyP: rpc.MessageSequence = rpc.MessageSequence.create();
      const option: rpc.MessageOption = new rpc.MessageOption();
      data.writeString(event);
      data.writeString(payload);
      await this.uiEventCbObj_.sendMessageRequest(MSG_EVENT, data, replyP, option);
      data.reclaim();
      replyP.reclaim();
    } catch (_e) { /* ignore */ }
  }
}

export default class AudioServiceAbility extends AppServiceExtensionAbility {
  private audioSvc_: HarmonyAudioService | null = null;
  private stub_: AudioServiceStub | null = null;

  onCreate(want: Want): void {
    hilog.info(LOG_DOMAIN, LOG_TAG, '%{public}s', 'AudioServiceAbility onCreate');
    const ctx = this.context;
    this.audioSvc_ = new HarmonyAudioService(ctx);
    this.stub_ = new AudioServiceStub(this.audioSvc_);
  }

  onDestroy(): void {
    hilog.info(LOG_DOMAIN, LOG_TAG, '%{public}s', 'AudioServiceAbility onDestroy');
    if (this.audioSvc_) {
      this.audioSvc_.destroy();
      this.audioSvc_ = null;
    }
    this.stub_ = null;
  }

  /** 返回 RemoteObject 供 UIAbility 通过 RPC 通信 */
  onConnect(want: Want): rpc.RemoteObject {
    hilog.info(LOG_DOMAIN, LOG_TAG, '%{public}s', 'AudioServiceAbility onConnect');
    return this.stub_!;
  }

  onDisconnect(want: Want): void {
    hilog.info(LOG_DOMAIN, LOG_TAG, '%{public}s', 'AudioServiceAbility onDisconnect');
  }

  onBackground(): void {
    hilog.info(LOG_DOMAIN, LOG_TAG, '%{public}s', 'AudioServiceAbility onBackground');
    try {
      const ctx = this.context;
      backgroundTaskManager.startBackgroundRunning(
        ctx,
        backgroundTaskManager.BackgroundMode.AUDIO_PLAYBACK,
        () => {
          hilog.info(LOG_DOMAIN, LOG_TAG, '%{public}s', 'Background running continuation');
        }
      );
    } catch (_e) {
      hilog.error(LOG_DOMAIN, LOG_TAG, 'startBackgroundRunning failed');
    }
  }

  onForeground(): void {
    hilog.info(LOG_DOMAIN, LOG_TAG, '%{public}s', 'AudioServiceAbility onForeground');
  }
}
