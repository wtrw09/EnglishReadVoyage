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
import { hilog } from '@kit.PerformanceAnalysisKit';
import { AVSessionMgr } from './AVSessionMgr';

const LOG_DOMAIN: number = 0xA045;
const LOG_TAG: string = 'HarmonyAudio';

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
  private currentLoadId_: number = 0;
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
        this.startTimer_();
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
        this.startTimer_();
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
      // 移除事件回调，避免内存泄漏
      try {
        this.player_.off('stateChange');
      } catch { /* ignore */ }
      try {
        this.player_.off('error');
      } catch { /* ignore */ }
      try {
        this.player_.release();
      } catch { /* ignore */ }
      this.player_ = null;
    }
  }

  private async loadTrack_(index: number, offsetMs: number): Promise<void> {
    if (index < 0 || index >= this.timeline_.length) return;
    // 递增 loadId，用于取消旧请求（快速切换音轨时避免竞争）
    const loadId: number = ++this.currentLoadId_;
    this.currentIndex_ = index;
    this.pendingSeekMs_ = offsetMs;
    this.releasePlayer();

    const track: TimelineTrack = this.timeline_[index];
    try {
      // 先创建播放器，成功后赋值给 this.player_
      const avPlayer: media.AVPlayer = await media.createAVPlayer();

      // 设置一个 Promise：等待 AVPlayer 状态变为 initialized（设置 url 后的合法状态）
      // 必须等待 initialized 后才能调用 prepare()，否则会报
      // "current state is not stopped or initialized, unsupport prepare operation"
      let resolveInit: () => void = () => {};
      let rejectInit: (err: Error) => void = (_err: Error): void => {};
      const waitInitialized: Promise<void> = new Promise<void>((resolve, reject) => {
        resolveInit = resolve;
        rejectInit = reject;
      });

      // 30 秒超时保护，防止 Promise 永不 resolve
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
          // AVPlayer 进入 error 状态，拒绝 Promise 避免死锁
          rejectInit(new Error('AVPlayer entered error state before initialized'));
          return;
        }
        this.onPlayerStateChange_(state);
      });
      avPlayer.on('error', (err: BusinessError) => {
        hilog.error(LOG_DOMAIN, LOG_TAG, 'avplayer error code=%{public}d msg=%{public}s', err.code, err.message);
        this.dispatchEvent_('error', this.buildErrorJson_('[code=' + err.code + '] ' + (err.message || 'avplayer error')));
      });

      // 设置 URL，等待状态变为 initialized
      hilog.info(LOG_DOMAIN, LOG_TAG, 'loadTrack: index=%{public}d url=%{public}s', index, track.url);
      avPlayer.url = track.url;

      // 竞速等待：initialized || error || 超时
      await Promise.race([waitInitialized, timeoutPromise]);
      clearTimeout(timeoutId);

      // 取消令牌检查：如果在此期间新的 loadTrack_ 已启动，放弃本次操作
      if (loadId !== this.currentLoadId_) {
        hilog.warn(LOG_DOMAIN, LOG_TAG, 'loadTrack cancelled: loadId=%{public}d current=%{public}d', loadId, this.currentLoadId_);
        try { avPlayer.off('stateChange'); } catch { /* ignore */ }
        try { avPlayer.off('error'); } catch { /* ignore */ }
        try { avPlayer.release(); } catch { /* ignore */ }
        return;
      }

      // 现在状态是 initialized，可以安全调用 prepare
      await avPlayer.prepare();
      hilog.info(LOG_DOMAIN, LOG_TAG, 'loadTrack: prepared index=%{public}d', index);

      // 再次取消检查
      if (loadId !== this.currentLoadId_) {
        hilog.warn(LOG_DOMAIN, LOG_TAG, 'loadTrack cancelled after prepare: loadId=%{public}d', loadId);
        try { avPlayer.off('stateChange'); } catch { /* ignore */ }
        try { avPlayer.off('error'); } catch { /* ignore */ }
        try { avPlayer.release(); } catch { /* ignore */ }
        return;
      }

      // seek 到指定位置
      if (this.pendingSeekMs_ > 0) {
        avPlayer.seek(this.pendingSeekMs_);
        this.pendingSeekMs_ = 0;
      }

      // 全部成功后赋值
      this.player_ = avPlayer;

      this.dispatchEvent_('trackchange', '{"trackIndex":' + index + '}');
      this.avSessionMgr_.setAudioDuration(this.totalMs_());
    } catch (e) {
      // 创建失败时 this.player_ 仍为 null，后续 play/pause 安全
      // ArkTS 严格模式下不支持 in 运算符（arkts-no-in），通过类型断言安全访问
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
        this.dispatchEvent_('ended', '{"completed":true}');
        this.stopTimer_();
        this.avSessionMgr_.setPlaybackState('paused');
      }
    } else if (state === 'error') {
      this.isPlaying_ = false;
      this.stopTimer_();
      this.releasePlayer();
      this.dispatchEvent_('error', '{"message":"avplayer state=error"}');
    }
  }

  private startTimer_(): void {
    this.stopTimer_();
    // 使用 setTimeout 递归调用避免累积误差
    // 注意：tick 始终调度下一次 setTimeout，避免音轨切换时 isPlaying_ 短暂变为 false
    // 导致定时器链断裂、后续再无 progress 事件的问题。
    // stopTimer_() 在 pause/stop 时由外部调用方主动停止计时器，因此这里无需依赖 isPlaying_ 做守卫。
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
      const json: string = '{"globalMs":' + globalMs + ',"localMs":' + localMs + ',"trackIndex":' + this.currentIndex_ + '}';
      this.dispatchEvent_('progress', json);
    } catch { /* ignore */ }
  }

  private buildErrorJson_(msg: string): string {
    const safe: string = msg
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\t/g, '\\t');
    return '{"message":"' + safe + '"}';
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
