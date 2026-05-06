/**
 * HarmonyAudio 桥 - ArkTS 侧实现
 *
 * 通过 javaScriptProxy 注入到 WebView 的 window.HarmonyAudio，
 * 对接前端 nativeAudio.ts 中的 createHarmonyPlaylistPlayer。
 *
 * 前端调用：window.HarmonyAudio.setPlaylist(timeline) / play() / pause() 等
 * 回调前端：webviewController.runJavaScript('window.__harmonyAudioEvent(event, payload)')
 */
import { media } from '@kit.MediaKit';
import { type BusinessError } from '@kit.BasicServicesKit';
import { webview } from '@kit.ArkWeb';
import { AVSessionMgr } from './AVSessionMgr';

export interface TimelineTrack {
  startMs: number;
  endMs: number;
  durationMs: number;
  url: string;
  lang?: string;
}

interface MetaInfo {
  title: string;
  artist: string;
}

export class HarmonyAudio {
  private controller_: webview.WebviewController;
  private player_: media.AVPlayer | null = null;
  private timeline_: TimelineTrack[] = [];
  private currentIndex_: number = -1;
  private timerId_: number = -1;
  private isPlaying_: boolean = false;
  private pendingSeekMs_: number = 0;
  private avSessionMgr_: AVSessionMgr;

  constructor(controller: webview.WebviewController, avSessionMgr: AVSessionMgr) {
    this.controller_ = controller;
    this.avSessionMgr_ = avSessionMgr;
  }

  destroy(): void {
    this.releasePlayer();
    if (this.timerId_ >= 0) {
      clearTimeout(this.timerId_);
      this.timerId_ = -1;
    }
    this.avSessionMgr_.destroy();
  }

  // ---------- 桥方法（javaScriptProxy 注册） ----------

  setPlaylist(timelineJson: string): void {
    try {
      const raw: Object = JSON.parse(timelineJson) as Object;
      if (!this.isValidTimeline_(raw)) {
        this.timeline_ = [];
        return;
      }
      this.timeline_ = raw as TimelineTrack[];
    } catch {
      this.timeline_ = [];
    }
    this.currentIndex_ = -1;
    this.isPlaying_ = false;
    this.releasePlayer();
  }

  async play(): Promise<void> {
    if (this.timeline_.length === 0) {
      this.dispatchEvent_('error', '{"message":"playlist empty"}');
      return;
    }
    if (this.currentIndex_ < 0) {
      this.currentIndex_ = 0;
    }
    await this.loadTrack_(this.currentIndex_, 0);
    if (this.player_) {
      try {
        await this.player_.play();
        this.isPlaying_ = true;
        this.dispatchEvent_('state', '"playing"');
        this.startTimer_();
        this.avSessionMgr_.setPlaybackState('playing');
      } catch {
        this.dispatchEvent_('error', '{"message":"play() failed"}');
      }
    }
  }

  pause(): void {
    if (this.player_ && this.isPlaying_) {
      try {
        this.player_.pause();
        this.isPlaying_ = false;
        this.stopTimer_();
        this.dispatchEvent_('state', '"paused"');
        this.avSessionMgr_.setPlaybackState('paused');
      } catch { /* ignore */ }
    }
  }

  resume(): void {
    if (this.player_ && !this.isPlaying_ && this.currentIndex_ >= 0) {
      try {
        this.player_.play();
        this.isPlaying_ = true;
        this.startTimer_();
        this.dispatchEvent_('state', '"playing"');
        this.avSessionMgr_.setPlaybackState('playing');
      } catch { /* ignore */ }
    } else if (this.currentIndex_ < 0 && this.timeline_.length > 0) {
      this.play();
    }
  }

  stop(): void {
    this.releasePlayer();
    this.isPlaying_ = false;
    this.stopTimer_();
    this.dispatchEvent_('state', '"stopped"');
    this.avSessionMgr_.setPlaybackState('paused');
  }

  async seekGlobal(msJson: string): Promise<void> {
    const ms: number = JSON.parse(msJson);
    if (this.timeline_.length === 0) return;
    const clamped: number = Math.max(0, Math.min(this.totalMs_(), ms));
    let idx: number = this.timeline_.findIndex(t => clamped >= t.startMs && clamped < t.endMs);
    if (idx < 0) idx = this.timeline_.length - 1;
    const offset: number = clamped - this.timeline_[idx].startMs;
    const wasPlaying: boolean = this.isPlaying_;
    await this.loadTrack_(idx, offset);
    if (wasPlaying && this.player_) {
      try {
        await this.player_.play();
        this.isPlaying_ = true;
      } catch { /* ignore */ }
    }
  }

  async seekLocal(msJson: string): Promise<void> {
    const ms: number = JSON.parse(msJson);
    if (!this.player_ || this.currentIndex_ < 0) return;
    try {
      this.player_.seek(Math.max(0, ms));
    } catch { /* ignore */ }
  }

  async seekToTrack(indexJson: string, offsetMsJson?: string): Promise<void> {
    const index: number = JSON.parse(indexJson);
    const offsetMs: number = offsetMsJson !== undefined ? JSON.parse(offsetMsJson) : 0;
    if (index < 0 || index >= this.timeline_.length) return;
    const wasPlaying: boolean = this.isPlaying_;
    await this.loadTrack_(index, offsetMs);
    if (wasPlaying && this.player_) {
      try {
        await this.player_.play();
        this.isPlaying_ = true;
      } catch { /* ignore */ }
    }
  }

  setRate(rateJson: string): void {
    const rate: number = JSON.parse(rateJson);
    // 有效播放速度范围 [0.5, 2.0]
    const clamped: number = Math.max(0.5, Math.min(2.0, rate));
    if (this.player_) {
      try {
        this.player_.setSpeed(clamped);
      } catch { /* ignore */ }
    }
  }

  setMeta(metaJson: string): void {
    try {
      const meta: MetaInfo = JSON.parse(metaJson) as MetaInfo;
      this.avSessionMgr_.setMeta(
        meta.title || '',
        meta.artist || '',
        this.totalMs_()
      );
    } catch { /* ignore */ }
  }

  // ---------- 内部方法 ----------

  private totalMs_(): number {
    return this.timeline_.length > 0
      ? this.timeline_[this.timeline_.length - 1].endMs
      : 0;
  }

  private isValidTimeline_(data: Object): boolean {
    if (!Array.isArray(data)) return false;
    const arr: TimelineTrack[] = data as TimelineTrack[];
    if (arr.length === 0) return true;
    return arr.every((t: Object) =>
      typeof t === 'object' && t !== null &&
      typeof (t as Record<string, Object>).startMs === 'number' &&
      typeof (t as Record<string, Object>).endMs === 'number' &&
      typeof (t as Record<string, Object>).durationMs === 'number' &&
      typeof (t as Record<string, Object>).url === 'string'
    );
  }

  private releasePlayer(): void {
    if (this.player_) {
      try {
        this.player_.stop();
      } catch { /* ignore */ }
      try {
        this.player_.release();
      } catch { /* ignore */ }
      this.player_ = null;
    }
  }

  private async loadTrack_(index: number, offsetMs: number): Promise<void> {
    if (index < 0 || index >= this.timeline_.length) return;
    this.currentIndex_ = index;
    this.pendingSeekMs_ = offsetMs;
    this.releasePlayer();

    const track: TimelineTrack = this.timeline_[index];
    try {
      // 先创建播放器，成功后赋值给 this.player_
      const avPlayer: media.AVPlayer = await media.createAVPlayer();
      avPlayer.on('stateChange', (state: media.AVPlayerState, _reason: media.StateChangeReason) => {
        this.onPlayerStateChange_(state);
      });
      avPlayer.on('error', (err: BusinessError) => {
        this.dispatchEvent_('error', this.buildErrorJson_(err.message || 'avplayer error'));
      });

      // 配置并准备
      avPlayer.url = track.url;
      await avPlayer.prepare();

      // seek 到指定位置
      if (this.pendingSeekMs_ > 0) {
        avPlayer.seek(this.pendingSeekMs_);
        this.pendingSeekMs_ = 0;
      }

      // 全部成功后赋值
      this.player_ = avPlayer;

      this.dispatchEvent_('trackchange', '{"trackIndex":' + index + '}');
      this.avSessionMgr_.setAudioDuration(this.totalMs_());
    } catch {
      // 创建失败时 this.player_ 仍为 null，后续 play/pause 安全
      this.dispatchEvent_('error', '{"message":"loadTrack failed for index ' + index + '"}');
    }
  }

  private onPlayerStateChange_(state: media.AVPlayerState): void {
    if (state === 'completed') {
      this.isPlaying_ = false;
      const next = this.currentIndex_ + 1;
      if (next < this.timeline_.length) {
        this.currentIndex_ = next;
        this.loadTrack_(next, 0).then(() => {
          if (this.player_) {
            this.player_.play().then(() => {
              this.isPlaying_ = true;
              this.avSessionMgr_.setPlaybackState('playing');
            }).catch(() => { /* ignore */ });
          }
        }).catch(() => { /* ignore */ });
      } else {
        this.dispatchEvent_('ended', '{"completed":true}');
        this.stopTimer_();
        this.avSessionMgr_.setPlaybackState('paused');
      }
    } else if (state === 'error') {
      this.dispatchEvent_('error', '{"message":"avplayer state=error"}');
    }
  }

  private startTimer_(): void {
    this.stopTimer_();
    // 使用 setTimeout 递归调用避免累积误差
    const tick = (): void => {
      if (!this.isPlaying_) return;
      this.fireProgress_();
      this.timerId_ = setTimeout(tick, 200);
    };
    this.timerId_ = setTimeout(tick, 200);
  }

  private stopTimer_(): void {
    if (this.timerId_ >= 0) {
      clearTimeout(this.timerId_);
      this.timerId_ = -1;
    }
  }

  private fireProgress_(): void {
    if (!this.player_ || this.currentIndex_ < 0) return;
    const track: TimelineTrack = this.timeline_[this.currentIndex_];
    if (!track) return;
    try {
      const localMs: number = this.player_.currentTime;
      const globalMs: number = track.startMs + localMs;
      const json: string = '{"globalMs":' + globalMs + ',"localMs":' + localMs + ',"trackIndex":' + this.currentIndex_ + '}';
      this.dispatchEvent_('progress', json);
    } catch { /* ignore */ }
  }

  private buildErrorJson_(msg: string): string {
    return '{"message":"' + msg.replace(/"/g, '\\"') + '"}';
  }

  private dispatchEvent_(event: string, payload: string): void {
    try {
      // 转义单引号和反斜杠，防止 XSS 注入
      const safeEvent: string = event.replace(/[\\']/g, '\\$&');
      this.controller_.runJavaScript(
        "window.__harmonyAudioEvent('" + safeEvent + "'," + payload + ")"
      );
    } catch { /* ignore */ }
  }
}
