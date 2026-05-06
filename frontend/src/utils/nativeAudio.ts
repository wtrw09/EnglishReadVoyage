/**
 * 跨端音频播放包装
 *
 * - 浏览器/Capacitor WebView 均使用 HTMLAudioElement（WebView 对 HTML5 音频支持良好）。
 * - 通过 MediaSession API 暴露锁屏控制和通知栏控件（Android Capacitor 支持）。
 * - 如需后台保活（息屏继续播）可后续引入 `@capacitor-community/background-mode` 或前台服务插件。
 */

import { isCapacitorNative } from './apiBase'

export interface MediaMeta {
  title?: string
  artist?: string
  album?: string
  artwork?: string
}

export interface NativeAudioHandle {
  element: HTMLAudioElement
  play: () => Promise<void>
  pause: () => void
  seek: (sec: number) => void
  setRate: (rate: number) => void
  setMeta: (meta: MediaMeta) => void
  destroy: () => void
}

/**
 * 创建音频播放器。返回 element 供现有 AudiobookPlayer 继续通过 ref 使用；
 * 同时额外暴露 setMeta/seek/setRate 等方法供组件调用。
 */
export function createAudio(src?: string): NativeAudioHandle {
  const audio = new Audio()
  if (src) audio.src = src
  audio.preload = 'metadata'

  const canUseMediaSession = typeof navigator !== 'undefined' && 'mediaSession' in navigator

  const setMeta = (meta: MediaMeta) => {
    if (!canUseMediaSession) return
    try {
      const mediaSession = (navigator as any).mediaSession
      const MediaMetadataCtor = (window as any).MediaMetadata
      if (MediaMetadataCtor) {
        mediaSession.metadata = new MediaMetadataCtor({
          title: meta.title || '',
          artist: meta.artist || '',
          album: meta.album || '',
          artwork: meta.artwork
            ? [{ src: meta.artwork, sizes: '512x512', type: 'image/jpeg' }]
            : []
        })
      }

      mediaSession.setActionHandler('play', () => audio.play())
      mediaSession.setActionHandler('pause', () => audio.pause())
      mediaSession.setActionHandler('seekbackward', (e: any) => {
        audio.currentTime = Math.max(0, audio.currentTime - (e?.seekOffset || 10))
      })
      mediaSession.setActionHandler('seekforward', (e: any) => {
        audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + (e?.seekOffset || 10))
      })
    } catch (e) {
      // MediaSession 不支持时静默忽略
    }
  }

  return {
    element: audio,
    play: () => audio.play(),
    pause: () => audio.pause(),
    seek: (sec: number) => {
      audio.currentTime = sec
    },
    setRate: (rate: number) => {
      audio.playbackRate = rate
    },
    setMeta,
    destroy: () => {
      audio.pause()
      audio.src = ''
      audio.load()
    }
  }
}

/** 当前是否在原生壳内（便于外部决定是否启用特定能力） */
export { isCapacitorNative }

// ============================================================
// 播放列表抽象层（PlaylistPlayer）
//
// 设计目标：
//   1. 一套接口同时覆盖 Web / Capacitor / 鸿蒙 Web 壳三种运行时。
//   2. 对外暴露 "全局毫秒时间轴" 概念，拖动进度只需传 globalMs，
//      内部自动定位到对应 track + 句内偏移。
//   3. 鸿蒙壳通过 window.HarmonyAudio + window.__harmonyAudioEvent
//      桥实现后台/锁屏播放；桥不存在时自动回退到 HTMLAudioElement。
//   4. 保留 createAudio() 现有语义，AudiobookPlayer.vue 不受影响。
// ============================================================

/** 用户传入的原始播放项 */
export interface PlaylistTrack {
  id: string
  url: string
  lang?: 'en' | 'zh'
  /** 已知时长（毫秒）；未知传 0，Web 后端会在 loadedmetadata 后自动修正 */
  durationMs?: number
  sentenceId?: string
  bookId?: string
  title?: string
}

/** 累计时间轴后的播放项（对外只读） */
export interface TimelineTrack {
  id: string
  url: string
  lang?: 'en' | 'zh'
  durationMs: number
  startMs: number
  endMs: number
  sentenceId?: string
  bookId?: string
  title?: string
}

export interface PlaylistProgress {
  /** 整个 playlist 的全局毫秒（供 slider 使用） */
  globalMs: number
  /** 当前 track 内的毫秒 */
  localMs: number
  trackIndex: number
  track: TimelineTrack
}

export type PlaylistPlayState = 'playing' | 'paused' | 'stopped'

export interface PlaylistEndedPayload {
  completed: boolean
}

export interface PlaylistPlayerEventMap {
  progress: PlaylistProgress
  trackchange: { index: number; track: TimelineTrack }
  ended: PlaylistEndedPayload
  error: { message: string }
  state: PlaylistPlayState
  /** 时间轴被探测或修正（Web 后端 loadedmetadata 后会触发） */
  timelineupdate: { timeline: TimelineTrack[]; totalMs: number }
}

export interface PlaylistPlayer {
  setTracks(tracks: PlaylistTrack[]): void
  play(): Promise<void>
  pause(): void
  resume(): Promise<void>
  stop(): void
  /** 按全局时间轴 ms 跳转（推荐 Slider 使用） */
  seekGlobal(ms: number): Promise<void>
  /** 在当前 track 内 seek（ms） */
  seekLocal(ms: number): Promise<void>
  /** 跳到指定 index 的 track，可选句内偏移 */
  seekToTrack(index: number, offsetMs?: number): Promise<void>
  setRate(rate: number): void
  setMeta(meta: MediaMeta): void
  on<K extends keyof PlaylistPlayerEventMap>(
    event: K,
    cb: (e: PlaylistPlayerEventMap[K]) => void
  ): () => void
  getTimeline(): TimelineTrack[]
  getTotalDurationMs(): number
  getCurrentIndex(): number
  getState(): PlaylistPlayState
  destroy(): void
}

// ---------- 构建辅助 ----------

/** 将原始 tracks 累计成带 startMs/endMs 的时间轴 */
export function buildTimeline(tracks: PlaylistTrack[]): TimelineTrack[] {
  let acc = 0
  return tracks.map((t, i) => {
    const durationMs = Math.max(0, Math.round(t.durationMs || 0))
    const startMs = acc
    acc += durationMs
    return {
      id: t.id || `track_${i}`,
      url: t.url,
      lang: t.lang,
      durationMs,
      startMs,
      endMs: startMs + durationMs,
      sentenceId: t.sentenceId,
      bookId: t.bookId,
      title: t.title
    }
  })
}

/** 对齐项目现有 AudioInfo 的最小字段集 */
export interface BilingualAudioItem {
  audio_url: string
  audio_url_zh?: string
  /** 秒 */
  duration?: number
  /** 秒 */
  duration_zh?: number
  sentenceId?: string
  text_hash?: string
  bookId?: string
}

/** 对齐项目 userReadConfig.segments 的类型 */
export interface BilingualSegmentConfig {
  segments: Array<{ lang: 'en' | 'zh'; count: number }>
}

/**
 * 将双语 AudioInfo 列表展平为 "英中交替/重复" 的串行 playlist。
 * 契合记忆中 "双语音频切换需重置currentTime" / "播放列表切换逻辑判断标准"：
 * 每个片段都是独立 track，切换时内部会 reset 音源，避免 currentTime 残留。
 */
export function buildBilingualPlaylist(
  items: BilingualAudioItem[],
  config?: BilingualSegmentConfig
): PlaylistTrack[] {
  const segs = (config && config.segments && config.segments.length > 0)
    ? config.segments
    : [{ lang: 'en' as const, count: 1 }]

  const out: PlaylistTrack[] = []
  items.forEach((it, i) => {
    const sid = it.sentenceId || it.text_hash || `s_${i}`
    segs.forEach((seg, sIdx) => {
      // count <= 0 时跳过该段（用于“本书无中文时将中文段 count 置 0 以保持英文重复次数”的场景）
      const repeat = Math.max(0, seg.count | 0)
      if (repeat === 0) return
      const url = seg.lang === 'en' ? it.audio_url : (it.audio_url_zh || '')
      const durSec = seg.lang === 'en' ? (it.duration || 0) : (it.duration_zh || 0)
      if (!url) return
      for (let r = 0; r < repeat; r++) {
        out.push({
          id: `${sid}_${seg.lang}_${sIdx}_${r}`,
          url,
          lang: seg.lang,
          durationMs: Math.round(durSec * 1000),
          sentenceId: sid,
          bookId: it.bookId
        })
      }
    })
  })
  return out
}

// ---------- 后端选择 ----------

/** 当前是否处于鸿蒙 Web 壳（通过约定的 HarmonyAudio 全局桥判断） */
export function hasHarmonyAudioBridge(): boolean {
  return typeof window !== 'undefined' && !!(window as any).HarmonyAudio
}

export interface PlaylistPlayerOptions {
  /** 是否由 player 自动接管 navigator.mediaSession（锁屏/通知栈控件）。
   *  外层自己管理跨专辑/跨书籍的 prev/next 时，应传 false。默认 true。 */
  manageMediaSession?: boolean
}

/** 创建跨端 playlist 播放器；鸿蒙壳下走原生桥，否则走 HTMLAudioElement */
export function createPlaylistPlayer(options: PlaylistPlayerOptions = {}): PlaylistPlayer {
  if (hasHarmonyAudioBridge()) return createHarmonyPlaylistPlayer()
  return createWebPlaylistPlayer(options)
}

// ---------- 共用：监听器工具 ----------

type ListenerBag = {
  [K in keyof PlaylistPlayerEventMap]?: Array<(e: PlaylistPlayerEventMap[K]) => void>
}

function createEmitter() {
  const bag: ListenerBag = {}
  function on<K extends keyof PlaylistPlayerEventMap>(
    ev: K,
    cb: (e: PlaylistPlayerEventMap[K]) => void
  ): () => void {
    const arr = (bag[ev] || (bag[ev] = [])) as Array<(e: PlaylistPlayerEventMap[K]) => void>
    arr.push(cb)
    return () => {
      const list = bag[ev] as Array<(e: PlaylistPlayerEventMap[K]) => void> | undefined
      if (!list) return
      const i = list.indexOf(cb)
      if (i >= 0) list.splice(i, 1)
    }
  }
  function emit<K extends keyof PlaylistPlayerEventMap>(ev: K, payload: PlaylistPlayerEventMap[K]) {
    const list = bag[ev] as Array<(e: PlaylistPlayerEventMap[K]) => void> | undefined
    if (!list) return
    list.slice().forEach(cb => {
      try { cb(payload) } catch { /* ignore listener errors */ }
    })
  }
  function clear() {
    for (const k of Object.keys(bag)) delete (bag as any)[k]
  }
  return { on, emit, clear }
}

// ---------- Web 后端 ----------

function createWebPlaylistPlayer(options: PlaylistPlayerOptions = {}): PlaylistPlayer {
  const manageMediaSession = options.manageMediaSession !== false
  const audio = new Audio()
  audio.preload = 'metadata'

  const { on, emit, clear } = createEmitter()

  let timeline: TimelineTrack[] = []
  let currentIndex = -1
  let state: PlaylistPlayState = 'stopped'
  let pendingSeekLocalMs = 0
  let meta: MediaMeta = {}
  let currentRate = 1

  function totalMs(): number {
    return timeline.length ? timeline[timeline.length - 1].endMs : 0
  }

  function setState(s: PlaylistPlayState) {
    if (state === s) return
    state = s
    emit('state', s)
  }

  function rebuildTimelineFrom(index: number, newDurationMs: number) {
    if (index < 0 || index >= timeline.length) return
    const old = timeline[index]
    if (Math.abs(old.durationMs - newDurationMs) < 50) return
    const delta = newDurationMs - old.durationMs
    timeline[index] = { ...old, durationMs: newDurationMs, endMs: old.startMs + newDurationMs }
    for (let i = index + 1; i < timeline.length; i++) {
      const t = timeline[i]
      timeline[i] = { ...t, startMs: t.startMs + delta, endMs: t.endMs + delta }
    }
    emit('timelineupdate', { timeline: timeline.slice(), totalMs: totalMs() })
  }

  async function loadIndex(index: number, offsetMs: number) {
    if (index < 0 || index >= timeline.length) return
    currentIndex = index
    const track = timeline[index]
    pendingSeekLocalMs = Math.max(0, offsetMs)
    audio.src = track.url
    audio.playbackRate = currentRate
    emit('trackchange', { index, track })
  }

  audio.addEventListener('loadedmetadata', () => {
    if (currentIndex < 0) return
    const realMs = Math.round((audio.duration || 0) * 1000)
    if (realMs > 0) rebuildTimelineFrom(currentIndex, realMs)
    if (pendingSeekLocalMs > 0) {
      try { audio.currentTime = pendingSeekLocalMs / 1000 } catch { /* ignore */ }
      pendingSeekLocalMs = 0
    }
  })

  audio.addEventListener('timeupdate', () => {
    if (currentIndex < 0) return
    const track = timeline[currentIndex]
    if (!track) return
    const localMs = Math.round((audio.currentTime || 0) * 1000)
    emit('progress', {
      globalMs: track.startMs + localMs,
      localMs,
      trackIndex: currentIndex,
      track
    })
  })

  audio.addEventListener('ended', async () => {
    const next = currentIndex + 1
    if (next < timeline.length) {
      await loadIndex(next, 0)
      try { await audio.play() } catch { /* ignore autoplay reject */ }
    } else {
      setState('stopped')
      emit('ended', { completed: true })
    }
  })

  audio.addEventListener('play', () => setState('playing'))
  audio.addEventListener('pause', () => {
    // 停止态下 pause 也会触发，保持 stopped
    if (state !== 'stopped') setState('paused')
  })
  audio.addEventListener('error', () => {
    emit('error', { message: audio.error ? String(audio.error.message || audio.error.code) : 'audio error' })
  })

  function applyMediaSession() {
    if (!manageMediaSession) return
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return
    try {
      const ms: any = (navigator as any).mediaSession
      const MM = (window as any).MediaMetadata
      if (MM) {
        ms.metadata = new MM({
          title: meta.title || '',
          artist: meta.artist || '',
          album: meta.album || '',
          artwork: meta.artwork ? [{ src: meta.artwork, sizes: '512x512', type: 'image/jpeg' }] : []
        })
      }
      ms.setActionHandler('play', () => { audio.play().catch(() => { /* ignore */ }) })
      ms.setActionHandler('pause', () => audio.pause())
      ms.setActionHandler('previoustrack', () => {
        if (currentIndex > 0) seekToTrack(currentIndex - 1, 0)
      })
      ms.setActionHandler('nexttrack', () => {
        if (currentIndex >= 0 && currentIndex < timeline.length - 1) seekToTrack(currentIndex + 1, 0)
      })
      ms.setActionHandler('seekto', (e: any) => {
        if (e && typeof e.seekTime === 'number') seekLocal(e.seekTime * 1000)
      })
    } catch { /* ignore */ }
  }

  function setTracks(tracks: PlaylistTrack[]) {
    timeline = buildTimeline(tracks)
    currentIndex = -1
    pendingSeekLocalMs = 0
    audio.pause()
    audio.removeAttribute('src')
    audio.load()
    setState('stopped')
    emit('timelineupdate', { timeline: timeline.slice(), totalMs: totalMs() })
  }

  async function play(): Promise<void> {
    if (!timeline.length) return
    if (currentIndex < 0) await loadIndex(0, 0)
    applyMediaSession()
    try { await audio.play() } catch { /* ignore */ }
  }

  function pause(): void { audio.pause() }

  async function resume(): Promise<void> {
    if (!timeline.length) return
    if (currentIndex < 0) await loadIndex(0, 0)
    try { await audio.play() } catch { /* ignore */ }
  }

  function stop(): void {
    audio.pause()
    try { audio.currentTime = 0 } catch { /* ignore */ }
    setState('stopped')
  }

  async function seekGlobal(ms: number): Promise<void> {
    if (!timeline.length) return
    const clamped = Math.max(0, Math.min(totalMs(), ms))
    let idx = timeline.findIndex(t => clamped >= t.startMs && clamped < t.endMs)
    if (idx < 0) idx = timeline.length - 1
    const offset = clamped - timeline[idx].startMs
    if (idx !== currentIndex) {
      const wasPlaying = !audio.paused
      await loadIndex(idx, offset)
      if (wasPlaying) { try { await audio.play() } catch { /* ignore */ } }
    } else {
      try { audio.currentTime = offset / 1000 } catch { /* ignore */ }
    }
  }

  async function seekLocal(ms: number): Promise<void> {
    if (currentIndex < 0) return
    try { audio.currentTime = Math.max(0, ms) / 1000 } catch { /* ignore */ }
  }

  async function seekToTrack(index: number, offsetMs: number = 0): Promise<void> {
    if (index < 0 || index >= timeline.length) return
    const wasPlaying = !audio.paused
    await loadIndex(index, offsetMs)
    if (wasPlaying) { try { await audio.play() } catch { /* ignore */ } }
  }

  function setRate(rate: number): void {
    currentRate = rate
    audio.playbackRate = rate
  }

  function setMeta(m: MediaMeta): void {
    meta = { ...meta, ...m }
    applyMediaSession()
  }

  function destroy(): void {
    audio.pause()
    audio.removeAttribute('src')
    audio.load()
    timeline = []
    currentIndex = -1
    clear()
  }

  return {
    setTracks,
    play,
    pause,
    resume,
    stop,
    seekGlobal,
    seekLocal,
    seekToTrack,
    setRate,
    setMeta,
    on,
    getTimeline: () => timeline.slice(),
    getTotalDurationMs: totalMs,
    getCurrentIndex: () => currentIndex,
    getState: () => state,
    destroy
  }
}

// ---------- 鸿蒙桥后端 ----------
//
// 约定：鸿蒙 ArkTS 侧通过 javaScriptProxy 注入对象 `HarmonyAudio`，方法：
//   setPlaylist(timeline: TimelineTrack[]): void
//   play() / pause() / resume() / stop(): Promise<void> | void
//   seekGlobal(ms: number): Promise<void>
//   seekLocal(ms: number): Promise<void>
//   seekToTrack(index: number, offsetMs: number): Promise<void>
//   setRate(rate: number): void
//   setMeta(meta: MediaMeta): void
// 事件：原生侧调用 `window.__harmonyAudioEvent(event, payload)` 回传
//   event='progress'  payload={ globalMs, localMs?, trackIndex? }
//   event='trackchange' payload={ trackIndex }
//   event='ended'     payload={ completed }
//   event='state'     payload='playing'|'paused'|'stopped'
//   event='error'     payload={ message }

type HarmonyEventHandler = (event: string, payload: any) => void

function ensureHarmonyDispatcher(): Set<HarmonyEventHandler> {
  const g: any = window as any
  if (!g.__harmonyAudioDispatch) {
    const subs: Set<HarmonyEventHandler> = new Set()
    g.__harmonyAudioDispatch = subs
    g.__harmonyAudioEvent = (event: string, payload: any) => {
      subs.forEach(fn => { try { fn(event, payload) } catch { /* ignore */ } })
    }
  }
  return g.__harmonyAudioDispatch as Set<HarmonyEventHandler>
}

function createHarmonyPlaylistPlayer(): PlaylistPlayer {
  const H: any = (window as any).HarmonyAudio
  const { on, emit, clear } = createEmitter()

  let timeline: TimelineTrack[] = []
  let state: PlaylistPlayState = 'stopped'
  let currentIndex = -1

  const dispatcher = ensureHarmonyDispatcher()

  const handler: HarmonyEventHandler = (event, payload) => {
    if (event === 'progress' && payload) {
      let idx = typeof payload.trackIndex === 'number' ? payload.trackIndex : -1
      if (idx < 0 && typeof payload.globalMs === 'number') {
        idx = timeline.findIndex(t => payload.globalMs >= t.startMs && payload.globalMs < t.endMs)
      }
      if (idx < 0 || idx >= timeline.length) return
      const track = timeline[idx]
      const globalMs = typeof payload.globalMs === 'number' ? payload.globalMs : track.startMs
      const localMs = typeof payload.localMs === 'number' ? payload.localMs : Math.max(0, globalMs - track.startMs)
      currentIndex = idx
      emit('progress', { globalMs, localMs, trackIndex: idx, track })
    } else if (event === 'trackchange' && payload) {
      const idx = typeof payload.trackIndex === 'number' ? payload.trackIndex : -1
      if (idx >= 0 && idx < timeline.length) {
        currentIndex = idx
        emit('trackchange', { index: idx, track: timeline[idx] })
      }
    } else if (event === 'ended') {
      state = 'stopped'
      emit('state', state)
      emit('ended', { completed: !!(payload && payload.completed) })
    } else if (event === 'state') {
      if (payload === 'playing' || payload === 'paused' || payload === 'stopped') {
        state = payload
        emit('state', state)
      }
    } else if (event === 'error') {
      emit('error', { message: (payload && payload.message) || 'native audio error' })
    }
  }
  dispatcher.add(handler)

  function totalMs(): number {
    return timeline.length ? timeline[timeline.length - 1].endMs : 0
  }

  function setTracks(tracks: PlaylistTrack[]): void {
    timeline = buildTimeline(tracks)
    currentIndex = -1
    try { H.setPlaylist && H.setPlaylist(timeline) } catch { /* ignore */ }
    emit('timelineupdate', { timeline: timeline.slice(), totalMs: totalMs() })
  }

  async function call(method: string, ...args: any[]): Promise<void> {
    try {
      const fn = H && H[method]
      if (typeof fn === 'function') {
        const r = fn.apply(H, args)
        if (r && typeof r.then === 'function') await r
      }
    } catch (e: any) {
      emit('error', { message: e?.message || `harmony ${method} failed` })
    }
  }

  return {
    setTracks,
    play: () => call('play'),
    pause: () => { call('pause') },
    resume: () => call('resume'),
    stop: () => { call('stop') },
    seekGlobal: (ms: number) => call('seekGlobal', Math.max(0, Math.round(ms))),
    seekLocal: (ms: number) => call('seekLocal', Math.max(0, Math.round(ms))),
    seekToTrack: (index: number, offsetMs: number = 0) =>
      call('seekToTrack', index, Math.max(0, Math.round(offsetMs))),
    setRate: (rate: number) => { try { H.setRate && H.setRate(rate) } catch { /* ignore */ } },
    setMeta: (meta: MediaMeta) => { try { H.setMeta && H.setMeta(meta) } catch { /* ignore */ } },
    on,
    getTimeline: () => timeline.slice(),
    getTotalDurationMs: totalMs,
    getCurrentIndex: () => currentIndex,
    getState: () => state,
    destroy: () => {
      call('stop')
      dispatcher.delete(handler)
      timeline = []
      currentIndex = -1
      clear()
    }
  }
}
