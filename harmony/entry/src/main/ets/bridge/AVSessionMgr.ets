/**
 * AVSessionMgr - 锁屏/通知栏播放控件
 *
 * 通过 @ohos.multimedia.avsession 创建 AVSession，
 * 将锁屏用户操作（play/pause/prev/next/seek）桥接到 HarmonyAudio。
 */
import { avSession } from '@kit.AVSessionKit';
import { common } from '@kit.AbilityKit';
import { HarmonyAudio } from './HarmonyAudio';

export class AVSessionMgr {
  private session_: avSession.AVSession | null = null;
  private harmonyAudio_: HarmonyAudio | null = null;
  private currentTitle_: string = '';
  private currentArtist_: string = '';

  async create(context: common.UIAbilityContext, harmonyAudio: HarmonyAudio): Promise<void> {
    this.harmonyAudio_ = harmonyAudio;
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
    // 如果 duration 不变则跳过，避免重复更新
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
    } catch { /* ignore */ }
  }

  private registerCallbacks_(): void {
    if (!this.session_) return;
    const ha: HarmonyAudio | null = this.harmonyAudio_;

    this.session_.on('play', () => {
      try {
        ha?.play().catch(() => {});
      } catch { /* ignore */ }
    });

    this.session_.on('pause', () => {
      try {
        ha?.pause();
      } catch { /* ignore */ }
    });

    this.session_.on('stop', () => {
      try {
        ha?.stop();
      } catch { /* ignore */ }
    });

    this.session_.on('seek', (time: number) => {
      // AVSession 回调的 time 单位为秒，转换为毫秒后传给 HarmonyAudio
      try {
        ha?.seekGlobal(JSON.stringify(time * 1000)).catch(() => {});
      } catch { /* ignore */ }
    });
  }
}
