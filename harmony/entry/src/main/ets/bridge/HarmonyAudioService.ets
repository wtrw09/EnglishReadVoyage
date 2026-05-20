/**
 * HarmonyAudioService - ServiceExtensionAbility 侧音频引擎
 *
 * 从原 HarmonyAudio.ets 提取纯音频播放逻辑，去除 WebView 依赖，
 * 通过 event callback 向上层推送播放事件。
 */
import { media } from '@kit.MediaKit';
import { type BusinessError } from '@kit.BasicServicesKit';
import { common } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { AVSessionMgr } from './AVSessionMgr';

const LOG_DOMAIN: number = 0xA045;
const LOG_TAG: string = 'AudioSvc';

export interface TimelineTrack {
  startMs: number;
  endMs: number;
  durationMs: number;
  url: string;
  lang?: string;
}

export type ServiceEventCallback = (event: string, payload: string) => void;

export class HarmonyAudioService {
  private player_: media.AVPlayer | null = null;
  private timeline_: TimelineTrack[] = [];
  private currentIndex_: number = -1;
  private timerId_: number = -1;
  private isPlaying_: boolean = false;
  private pendingSeekMs_: number = 0;
  private currentLoadId_: number = 0;
  private avSessionMgr_: AVSessionMgr;
  private eventCb_: ServiceEventCallback | null = null;

  constructor(context: common.Context) {
    this.avSessionMgr_ = new AVSessionMgr();
    this.avSessionMgr_.create(context, this);
  }

  setEventCallback(cb: ServiceEventCallback): void {
    this.eventCb_ = cb;
  }

  destroy(): void {
    this.releasePlayer();
    if (this.timerId_ >= 0) {
      clearTimeout(this.timerId_);
      this.timerId_ = -1;
    }
    this.avSessionMgr_.destroy();
  }

  // ---------- 公开方法 ----------

  setPlaylist(timelineJson: string): void {
    try {
      const raw: Object = JSON.parse(timelineJson) as Object;
      if (!this.isValidTimeline_(raw)) {
        this.timeline_ = [];
        return;
      }
      this.timeline_ = raw as TimelineTrack[];
    } catch (_e) {
      this.timeline_ = [];
    }
    this.currentIndex_ = -1;
    this.isPlaying_ = false;
    this.releasePlayer();
  }

  async play(): Promise<void> {
    if (this.timeline_.length === 0) {
      this.dispatch_('error', '{"message":"playlist empty"}');
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
        this.dispatch_('state', '"playing"');
        this.startTimer_();
        this.avSessionMgr_.setPlaybackState('playing');
      } catch {
        this.dispatch_('error', '{"message":"play() failed"}');
      }
    }
  }

  pause(): void {
    if (this.player_ && this.isPlaying_) {
      try {
        this.player_.pause();
        this.isPlaying_ = false;
        this.stopTimer_();
        this.dispatch_('state', '"paused"');
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
        this.dispatch_('state', '"playing"');
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
    this.dispatch_('state', '"stopped"');
    this.avSessionMgr_.setPlaybackState('paused');
  }

  async seekGlobal(msJson: string): Promise<void> {
    if (this.timeline_.length === 0) return;
    const ms: number = JSON.parse(msJson);
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
        this.startTimer_();
      } catch { /* ignore */ }
    }
  }

  async seekLocal(msJson: string): Promise<void> {
    const ms: number = Number(JSON.parse(msJson));
    if (!this.player_ || this.currentIndex_ < 0) return;
    try {
      this.player_.seek(Math.max(0, ms));
    } catch { /* ignore */ }
  }

  async seekToTrack(indexJson: string, offsetMsJson: string = '0'): Promise<void> {
    if (this.timeline_.length === 0) return;
    const index: number = Number(JSON.parse(indexJson));
    const offsetMs: number = Number(JSON.parse(offsetMsJson));
    if (index < 0 || index >= this.timeline_.length) return;
    const wasPlaying: boolean = this.isPlaying_;
    await this.loadTrack_(index, offsetMs);
    if (wasPlaying && this.player_) {
      try {
        await this.player_.play();
        this.isPlaying_ = true;
        this.startTimer_();
      } catch { /* ignore */ }
    }
  }

  setRate(rateJson: string): void {
    const rate: number = Number(JSON.parse(rateJson));
    const clamped: number = Math.max(0.5, Math.min(2.0, rate));
    if (this.player_) {
      try {
        this.player_.setSpeed(clamped);
      } catch { /* ignore */ }
    }
  }

  setMeta(title: string, artist: string): void {
    this.avSessionMgr_.setMeta(title, artist, this.totalMs_());
  }

  /** 用于 IPC 查询当前状态 */
  getState(): string {
    if (this.isPlaying_) return 'playing';
    if (this.currentIndex_ >= 0) return 'paused';
    return 'stopped';
  }

  /** 用于 IPC 查询当前进度 */
  getProgressJson(): string {
    if (!this.player_ || this.currentIndex_ < 0) return '{}';
    const track: TimelineTrack = this.timeline_[this.currentIndex_];
    if (!track) return '{}';
    try {
      const localMs: number = this.player_.currentTime;
      const globalMs: number = track.startMs + localMs;
      return JSON.stringify({
        globalMs, localMs,
        trackIndex: this.currentIndex_
      });
    } catch { return '{}'; }
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
      try { this.player_.stop(); } catch { /* ignore */ }
      try { this.player_.off('stateChange'); } catch { /* ignore */ }
      try { this.player_.off('error'); } catch { /* ignore */ }
      try { this.player_.release(); } catch { /* ignore */ }
      this.player_ = null;
    }
  }

  private async loadTrack_(index: number, offsetMs: number): Promise<void> {
    if (index < 0 || index >= this.timeline_.length) return;
    const loadId: number = ++this.currentLoadId_;
    this.currentIndex_ = index;
    this.pendingSeekMs_ = offsetMs;
    this.releasePlayer();

    const track: TimelineTrack = this.timeline_[index];
    try {
      const avPlayer: media.AVPlayer = await media.createAVPlayer();

      let resolveInit: () => void = () => {};
      let rejectInit: (err: Error) => void = (_err: Error): void => {};
      const waitInitialized: Promise<void> = new Promise<void>((resolve, reject) => {
        resolveInit = resolve;
        rejectInit = reject;
      });

      const timeoutMs: number = 30000;
      let timeoutId: number = -1;
      const timeoutPromise: Promise<void> = new Promise<void>((_resolve, reject) => {
        timeoutId = setTimeout(() => {
          reject(new Error('loadTrack timeout after ' + timeoutMs + 'ms'));
        }, timeoutMs);
      });

      avPlayer.on('stateChange', (state: media.AVPlayerState, _reason: media.StateChangeReason) => {
        hilog.info(LOG_DOMAIN, LOG_TAG, 'stateChange: %{public}s', state);
        if (state === 'initialized') {
          resolveInit();
          return;
        } else if (state === 'error') {
          rejectInit(new Error('AVPlayer entered error state before initialized'));
          return;
        }
        this.onPlayerStateChange_(state);
      });
      avPlayer.on('error', (err: BusinessError) => {
        hilog.error(LOG_DOMAIN, LOG_TAG, 'avplayer error code=%{public}d msg=%{public}s', err.code, err.message);
        this.dispatch_('error', '{"message":"[code=' + err.code + '] ' + (err.message || 'avplayer error') + '"}');
      });

      hilog.info(LOG_DOMAIN, LOG_TAG, 'loadTrack: index=%{public}d url=%{public}s', index, track.url);
      avPlayer.url = track.url;

      await Promise.race([waitInitialized, timeoutPromise]);
      clearTimeout(timeoutId);

      if (loadId !== this.currentLoadId_) {
        hilog.warn(LOG_DOMAIN, LOG_TAG, 'loadTrack cancelled');
        try { avPlayer.off('stateChange'); } catch { /* ignore */ }
        try { avPlayer.off('error'); } catch { /* ignore */ }
        try { avPlayer.release(); } catch { /* ignore */ }
        return;
      }

      await avPlayer.prepare();
      hilog.info(LOG_DOMAIN, LOG_TAG, 'loadTrack: prepared index=%{public}d', index);

      if (loadId !== this.currentLoadId_) {
        hilog.warn(LOG_DOMAIN, LOG_TAG, 'loadTrack cancelled after prepare');
        try { avPlayer.off('stateChange'); } catch { /* ignore */ }
        try { avPlayer.off('error'); } catch { /* ignore */ }
        try { avPlayer.release(); } catch { /* ignore */ }
        return;
      }

      if (this.pendingSeekMs_ > 0) {
        avPlayer.seek(this.pendingSeekMs_);
        this.pendingSeekMs_ = 0;
      }

      this.player_ = avPlayer;
      this.dispatch_('trackchange', '{"trackIndex":' + index + '}');
      this.avSessionMgr_.setAudioDuration(this.totalMs_());
    } catch (e) {
      const errMsg: string = (e && typeof e === 'object')
        ? String((e as Record<string, Object>).message || '')
        : String(e || '');
      const urlStr: string = track.url || '';
      hilog.error(LOG_DOMAIN, LOG_TAG, 'loadTrack catch: index=%{public}d url=%{public}s err=%{public}s', index, urlStr, errMsg);
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
        this.dispatch_('ended', '{"completed":true}');
        this.stopTimer_();
        this.avSessionMgr_.setPlaybackState('paused');
      }
    } else if (state === 'error') {
      this.isPlaying_ = false;
      this.stopTimer_();
      this.releasePlayer();
      this.dispatch_('error', '{"message":"avplayer state=error"}');
    }
  }

  private startTimer_(): void {
    this.stopTimer_();
    const tick = (): void => {
      if (this.isPlaying_) {
        this.fireProgress_();
      }
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
      const json: string = JSON.stringify({
        globalMs, localMs,
        trackIndex: this.currentIndex_
      });
      this.dispatch_('progress', json);
    } catch { /* ignore */ }
  }

  private dispatch_(event: string, payload: string): void {
    if (this.eventCb_) {
      try {
        this.eventCb_(event, payload);
      } catch { /* ignore */ }
    }
  }
}
