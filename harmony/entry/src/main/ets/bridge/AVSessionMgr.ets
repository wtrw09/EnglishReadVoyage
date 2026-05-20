/**
 * AVSessionMgr - 锁屏/通知栏播放控件
 *
 * 通过 @ohos.multimedia.avsession 创建 AVSession，
 * 将锁屏用户操作（play/pause/prev/next/seek）桥接到音频引擎。
 *
 * IAudioController 接口使此类同时适用于 UIAbility 和 ServiceExtensionAbility 场景。
 */
import { avSession } from '@kit.AVSessionKit';
import { common } from '@kit.AbilityKit';

/** 音频控制器接口，HarmonyAudio 和 HarmonyAudioService 均实现此接口 */
export interface IAudioController {
  play(): Promise<void>;
  pause(): void;
  stop(): void;
  /** @param msJson JSON字符串，内部解析为毫秒数 */
  seekGlobal(msJson: string): Promise<void>;
}

export class AVSessionMgr {
  private session_: avSession.AVSession | null = null;
  private audioCtrl_: IAudioController | null = null;
  private currentTitle_: string = '';
  private currentArtist_: string = '';

  async create(context: common.Context, audioCtrl: IAudioController): Promise<void> {
    this.audioCtrl_ = audioCtrl;
    try {
      this.session_ = await avSession.createAVSession(context, 'EnglishReadVoyage', 'audio');
      this.registerCallbacks_();
    } catch {
      // AVSession not available or not supported
    }
  }

  destroy(): void {
    if (this.session_) {
      try {
        this.session_.destroy();
      } catch { /* ignore */ }
      this.session_ = null;
    }
  }

  setMeta(title: string, artist: string, duration: number): void {
    this.currentTitle_ = title;
    this.currentArtist_ = artist;
    if (!this.session_) return;
    try {
      this.session_.setAVMetadata({
        assetId: 'default',
        title: title,
        artist: artist,
        duration: duration
      });
    } catch { /* ignore */ }
  }

  setAudioDuration(durationMs: number): void {
    if (!this.session_) return;
    try {
      this.session_.setAVMetadata({
        assetId: 'default',
        title: this.currentTitle_,
        artist: this.currentArtist_,
        duration: durationMs
      });
    } catch { /* ignore */ }
  }

  setPlaybackState(state: string): void {
    if (!this.session_) return;
    try {
      const stateValue = state === 'playing'
        ? avSession.PlaybackState.PLAYBACK_STATE_PLAY
        : avSession.PlaybackState.PLAYBACK_STATE_PAUSE;
      this.session_.setAVPlaybackState({
        state: stateValue,
        position: { elapsedTime: 0, updateTime: Date.now() }
      });
    } catch (_e) { /* ignore */ }
  }

  private registerCallbacks_(): void {
    if (!this.session_) return;
    const ctrl: IAudioController | null = this.audioCtrl_;

    this.session_.on('play', () => {
      try {
        ctrl?.play().catch(() => {});
      } catch (_e) { /* ignore */ }
    });

    this.session_.on('pause', () => {
      try {
        ctrl?.pause();
      } catch (_e) { /* ignore */ }
    });

    this.session_.on('stop', () => {
      try {
        ctrl?.stop();
      } catch (_e) { /* ignore */ }
    });

    this.session_.on('seek', (time: number) => {
      // AVSession 回调的 time 单位为秒，转换为毫秒后传给音频引擎
      try {
        ctrl?.seekGlobal(JSON.stringify(time * 1000)).catch(() => {});
      } catch (_e) { /* ignore */ }
    });
  }
}
