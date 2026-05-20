package com.englishreadvoyage.app.audio;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.media.PlaybackParams;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.util.Log;

import java.io.IOException;
import java.util.List;

/**
 * 音频播放引擎，封装 Android MediaPlayer，管理播放列表。
 *
 * 职责：
 * - 设置/切换播放列表
 * - 播放、暂停、恢复、停止
 * - 音轨跳转（按索引/按全局时间/按本地时间）
 * - 变速播放
 * - 通过 PlayerCallback 向外部报告进度、状态、错误
 */
public class PlaylistAudioPlayer {

    private static final String TAG = "PlaylistAudioPlayer";
    private static final long PROGRESS_INTERVAL_MS = 200;

    public interface PlayerCallback {
        void onProgress(long globalMs, long localMs, int trackIndex);
        void onTrackChange(int index);
        void onEnded(boolean completed);
        void onError(String message);
        void onStateChange(String state); // "playing" | "paused" | "stopped"
    }

    private MediaPlayer mediaPlayer;
    private List<TimelineTrack> timeline;
    private int currentIndex = -1;
    private boolean isPlaying = false;
    private float playbackRate = 1.0f;
    private PlayerCallback callback;
    private Context context;
    private final Handler progressHandler = new Handler(Looper.getMainLooper());
    private final Runnable progressRunnable = new Runnable() {
        @Override
        public void run() {
            fireProgress();
            if (isPlaying) {
                progressHandler.postDelayed(this, PROGRESS_INTERVAL_MS);
            }
        }
    };
    // 加载令牌：递增计数器，用于取消旧加载请求（快速切换音轨时防止竞争）
    private int loadIdCounter = 0;

    public void setCallback(PlayerCallback callback) {
        this.callback = callback;
    }

    public void setContext(Context ctx) {
        this.context = ctx;
    }

    // ---- 播放列表管理 ----

    /**
     * 设置播放列表。如果正在播放则停止。
     */
    public void setPlaylist(List<TimelineTrack> tracks) {
        stop();
        this.timeline = tracks;
        this.currentIndex = -1;
    }

    // ---- 播放控制 ----

    /**
     * 开始播放。如果当前没有选中音轨则从第 0 轨开始。
     */
    public void play() {
        if (timeline == null || timeline.isEmpty()) {
            fireError("playlist empty");
            return;
        }
        if (currentIndex < 0) {
            currentIndex = 0;
        }
        if (mediaPlayer == null) {
            loadTrack(currentIndex, 0, true);
        } else {
            mediaPlayer.start();
            isPlaying = true;
            fireState("playing");
            progressHandler.post(progressRunnable);
        }
    }

    /**
     * 暂停。
     */
    public void pause() {
        if (mediaPlayer != null && isPlaying) {
            mediaPlayer.pause();
            isPlaying = false;
            progressHandler.removeCallbacks(progressRunnable);
            fireState("paused");
        }
    }

    /**
     * 恢复。
     */
    public void resume() {
        if (mediaPlayer != null && !isPlaying && currentIndex >= 0) {
            mediaPlayer.start();
            isPlaying = true;
            fireState("playing");
            progressHandler.post(progressRunnable);
        } else if (currentIndex < 0 && timeline != null && !timeline.isEmpty()) {
            play();
        }
    }

    /**
     * 停止。释放播放器资源。
     */
    public void stop() {
        isPlaying = false;
        progressHandler.removeCallbacks(progressRunnable);
        releasePlayer();
        fireState("stopped");
    }

    // ---- 跳转 ----

    /**
     * 按全局时间跳转。在 timeline 中查找对应的音轨和偏移。
     */
    public void seekGlobal(long ms) {
        if (timeline == null || timeline.isEmpty() || currentIndex < 0) return;
        long clamped = Math.max(0, Math.min(getTotalMs(), ms));
        int idx = findTrackIndex(clamped);
        if (idx < 0) idx = timeline.size() - 1;
        long offset = clamped - timeline.get(idx).startMs;
        boolean wasPlaying = isPlaying;
        loadTrack(idx, (int) offset, wasPlaying);
    }

    /**
     * 在当前音轨内 seek（毫秒）。
     */
    public void seekLocal(int ms) {
        if (mediaPlayer == null || currentIndex < 0) return;
        try {
            mediaPlayer.seekTo(Math.max(0, ms));
        } catch (Exception e) {
            Log.e(TAG, "seekLocal failed", e);
        }
    }

    /**
     * 跳转到指定索引的音轨，可指定偏移。
     */
    public void seekToTrack(int index, int offsetMs) {
        if (timeline == null || index < 0 || index >= timeline.size()) return;
        boolean wasPlaying = isPlaying;
        loadTrack(index, Math.max(0, offsetMs), wasPlaying);
    }

    // ---- 设置 ----

    /**
     * 设置播放速率。
     */
    public void setRate(float rate) {
        playbackRate = Math.max(0.5f, Math.min(2.0f, rate));
        if (mediaPlayer != null) {
            applyPlaybackRate();
        }
    }

    /**
     * 获取当前播放索引。
     */
    public int getCurrentIndex() {
        return currentIndex;
    }

    /**
     * 获取当前播放状态。
     */
    public String getState() {
        if (currentIndex < 0) return "stopped";
        return isPlaying ? "playing" : "paused";
    }

    /**
     * 获取 timeline 总时长。
     */
    public long getTotalMs() {
        if (timeline == null || timeline.isEmpty()) return 0;
        return timeline.get(timeline.size() - 1).endMs;
    }

    /**
     * 获取当前播放位置（全局毫秒）。
     */
    public long getCurrentGlobalMs() {
        if (mediaPlayer == null || currentIndex < 0 || timeline == null) return 0;
        try {
            long localMs = mediaPlayer.getCurrentPosition();
            return timeline.get(currentIndex).startMs + localMs;
        } catch (Exception e) {
            return 0;
        }
    }

    /**
     * 释放所有资源。
     */
    public void release() {
        stop();
        timeline = null;
        callback = null;
    }

    // ---- 内部方法 ----

    private void loadTrack(int index, int offsetMs, boolean autoPlay) {
        if (timeline == null || index < 0 || index >= timeline.size()) return;

        final int loadId = ++loadIdCounter;
        currentIndex = index;

        releasePlayer();

        TimelineTrack track = timeline.get(index);
        if (track.url == null || track.url.isEmpty()) {
            fireError("track url is empty at index " + index);
            return;
        }

        MediaPlayer mp = null;
        try {
            mp = new MediaPlayer();

            // 设置音频属性（允许后台播放、使用媒体通道）
            mp.setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build());

            // 预准备完成回调
            mp.setOnPreparedListener(player -> {
                if (loadId != loadIdCounter) {
                    player.release();
                    return;
                }
                mediaPlayer = player;

                // 设置 WakeLock 防止 CPU 休眠
                if (context != null) {
                    try {
                        player.setWakeMode(context, PowerManager.PARTIAL_WAKE_LOCK);
                    } catch (Exception ignored) {}
                }

                applyPlaybackRate();

                // seek 到指定位置
                if (offsetMs > 0) {
                    try {
                        player.seekTo(offsetMs);
                    } catch (Exception ignored) {}
                }

                // 自动播放
                if (autoPlay) {
                    player.start();
                    isPlaying = true;
                    progressHandler.post(progressRunnable);
                    fireState("playing");
                }

                fireTrackChange(index);
            });

            // 播放完成回调：自动切到下一轨
            mp.setOnCompletionListener(player -> {
                if (loadId != loadIdCounter) return;
                int next = currentIndex + 1;
                if (next < timeline.size()) {
                    currentIndex = next;
                    loadTrack(next, 0, true);
                } else {
                    // 所有音轨播放完毕
                    isPlaying = false;
                    progressHandler.removeCallbacks(progressRunnable);
                    fireEnded(true);
                    releasePlayer();
                    fireState("stopped");
                }
            });

            // 错误回调
            mp.setOnErrorListener((player, what, extra) -> {
                Log.e(TAG, "MediaPlayer error: what=" + what + " extra=" + extra);
                fireError("MEDIA_ERROR what=" + what + " extra=" + extra);
                isPlaying = false;
                progressHandler.removeCallbacks(progressRunnable);
                releasePlayer();
                fireState("stopped");
                return true; // 已处理
            });

            // 设置数据源并异步准备
            mp.setDataSource(track.url);
            mp.prepareAsync();

        } catch (IOException | IllegalStateException e) {
            if (mp != null) {
                try { mp.release(); } catch (Exception ignored) {}
            }
            Log.e(TAG, "loadTrack failed: index=" + index + " url=" + track.url, e);
            fireError("loadTrack: " + e.getMessage());
        }
    }

    private void releasePlayer() {
        if (mediaPlayer != null) {
            try {
                mediaPlayer.stop();
            } catch (Exception ignored) {}
            try {
                mediaPlayer.reset();
            } catch (Exception ignored) {}
            try {
                mediaPlayer.release();
            } catch (Exception ignored) {}
            mediaPlayer = null;
        }
    }

    private void applyPlaybackRate() {
        if (mediaPlayer == null) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                PlaybackParams params = new PlaybackParams();
                params.setSpeed(playbackRate);
                mediaPlayer.setPlaybackParams(params);
            } catch (Exception e) {
                Log.w(TAG, "setPlaybackParams failed", e);
            }
        }
    }

    private int findTrackIndex(long globalMs) {
        if (timeline == null) return -1;
        for (int i = 0; i < timeline.size(); i++) {
            TimelineTrack t = timeline.get(i);
            if (globalMs >= t.startMs && globalMs < t.endMs) {
                return i;
            }
        }
        return -1;
    }

    private void fireProgress() {
        if (callback == null || mediaPlayer == null || currentIndex < 0 || timeline == null) return;
        try {
            long localMs = mediaPlayer.getCurrentPosition();
            long globalMs = timeline.get(currentIndex).startMs + localMs;
            callback.onProgress(globalMs, localMs, currentIndex);
        } catch (Exception ignored) {}
    }

    private void fireTrackChange(int index) {
        if (callback != null) {
            callback.onTrackChange(index);
        }
    }

    private void fireEnded(boolean completed) {
        if (callback != null) {
            callback.onEnded(completed);
        }
    }

    private void fireError(String message) {
        Log.e(TAG, "Error: " + message);
        if (callback != null) {
            callback.onError(message);
        }
    }

    private void fireState(String state) {
        if (callback != null) {
            callback.onStateChange(state);
        }
    }
}
