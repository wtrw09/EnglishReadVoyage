package com.englishreadvoyage.app.plugins;

import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

import com.englishreadvoyage.app.audio.AudioPlaybackService;
import com.englishreadvoyage.app.audio.PlaylistAudioPlayer;
import com.englishreadvoyage.app.audio.TimelineTrack;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import org.json.JSONException;

import java.util.List;

/**
 * 自定义 Capacitor 插件，提供原生音频播放能力。
 *
 * 与前端 nativeAudio.ts 中的 createAndroidPlaylistPlayer() 对接，
 * 通信方式：PluginMethod + notifyListeners。
 *
 * 事件回调（native → JS）：
 * - progress:   { globalMs, localMs, trackIndex }
 * - trackchange: { trackIndex }
 * - ended:       { completed }
 * - error:       { message }
 * - state:       "playing" | "paused" | "stopped"
 */
@CapacitorPlugin(name = "NativeAudio")
public class NativeAudioPlugin extends Plugin implements
        PlaylistAudioPlayer.PlayerCallback,
        AudioPlaybackService.NotificationActionListener {

    private static final String TAG = "NativeAudioPlugin";
    private static final String EVENT_PROGRESS = "progress";
    private static final String EVENT_TRACK_CHANGE = "trackchange";
    private static final String EVENT_ENDED = "ended";
    private static final String EVENT_ERROR = "error";
    private static final String EVENT_STATE = "state";

    private PlaylistAudioPlayer player;

    // 当前元数据（用于通知栏展示）
    private String currentTitle = "英语阅读之旅";
    private String currentArtist = "听书播放";

    @Override
    public void load() {
        super.load();
        player = new PlaylistAudioPlayer();
        player.setCallback(this);
        player.setContext(getContext());

        AudioPlaybackService.setActionListener(this);
    }

    // ===== PluginMethod: 由前端通过 Capacitor.Plugins.NativeAudio 调用 =====

    @PluginMethod
    public void setPlaylist(PluginCall call) {
        String timelineJson = call.getString("timelineJson");
        if (timelineJson == null || timelineJson.isEmpty()) {
            call.reject("Missing required parameter: timelineJson");
            return;
        }
        try {
            List<TimelineTrack> tracks = TimelineTrack.fromJsonArray(timelineJson);
            player.setPlaylist(tracks);
            call.resolve();
        } catch (JSONException e) {
            Log.e(TAG, "setPlaylist JSON parse error", e);
            call.reject("Invalid timelineJson: " + e.getMessage());
        }
    }

    @PluginMethod
    public void play(PluginCall call) {
        player.play();
        call.resolve();
    }

    @PluginMethod
    public void pause(PluginCall call) {
        player.pause();
        call.resolve();
    }

    @PluginMethod
    public void resume(PluginCall call) {
        player.resume();
        call.resolve();
    }

    @PluginMethod
    public void stop(PluginCall call) {
        player.stop();
        call.resolve();
    }

    @PluginMethod
    public void seekToTrack(PluginCall call) {
        Integer index = call.getInt("index");
        Integer offsetMs = call.getInt("offsetMs", 0);
        if (index == null) {
            call.reject("Missing required parameter: index");
            return;
        }
        player.seekToTrack(index, offsetMs);
        call.resolve();
    }

    @PluginMethod
    public void seekGlobal(PluginCall call) {
        // 前端传入 globalMs, native 侧自行查找对应的音轨和偏移
        Double ms = call.getDouble("ms");
        if (ms == null) {
            call.reject("Missing required parameter: ms");
            return;
        }
        player.seekGlobal(ms.longValue());
        call.resolve();
    }

    @PluginMethod
    public void seekLocal(PluginCall call) {
        Integer ms = call.getInt("ms");
        if (ms == null) {
            call.reject("Missing required parameter: ms");
            return;
        }
        player.seekLocal(ms);
        call.resolve();
    }

    @PluginMethod
    public void setRate(PluginCall call) {
        Double rate = call.getDouble("rate");
        if (rate == null) {
            call.reject("Missing required parameter: rate");
            return;
        }
        player.setRate(rate.floatValue());
        call.resolve();
    }

    @PluginMethod
    public void setMeta(PluginCall call) {
        String metaJson = call.getString("metaJson");
        if (metaJson == null) {
            call.reject("Missing required parameter: metaJson");
            return;
        }
        try {
            org.json.JSONObject meta = new org.json.JSONObject(metaJson);
            currentTitle = meta.optString("title", currentTitle);
            currentArtist = meta.optString("artist", currentArtist);
            updateServiceNotification();
            call.resolve();
        } catch (org.json.JSONException e) {
            call.reject("Invalid metaJson: " + e.getMessage());
        }
    }

    @PluginMethod
    public void destroy(PluginCall call) {
        player.release();
        call.resolve();
    }

    // ===== PlayerCallback: PlaylistAudioPlayer 事件回调 =====

    @Override
    public void onProgress(long globalMs, long localMs, int trackIndex) {
        JSObject data = new JSObject();
        data.put("globalMs", (double) globalMs);
        data.put("localMs", (double) localMs);
        data.put("trackIndex", trackIndex);
        notifyListeners(EVENT_PROGRESS, data);
    }

    @Override
    public void onTrackChange(int index) {
        JSObject data = new JSObject();
        data.put("trackIndex", index);
        notifyListeners(EVENT_TRACK_CHANGE, data);
    }

    @Override
    public void onEnded(boolean completed) {
        JSObject data = new JSObject();
        data.put("completed", completed);
        notifyListeners(EVENT_ENDED, data);
        stopPlaybackService();
    }

    @Override
    public void onError(String message) {
        JSObject data = new JSObject();
        String safe = message != null ? message : "unknown error";
        data.put("message", safe);
        notifyListeners(EVENT_ERROR, data);
    }

    @Override
    public void onStateChange(String state) {
        JSObject data = new JSObject();
        data.put("value", state);
        notifyListeners(EVENT_STATE, data);

        if ("playing".equals(state)) {
            startPlaybackService();
            updateServiceNotification();
        } else if ("stopped".equals(state)) {
            stopPlaybackService();
        } else if ("paused".equals(state)) {
            updateServiceNotification();
        }
    }

    // ===== NotificationActionListener: 通知栏按钮回调 =====

    @Override
    public void onPlayPause() {
        if ("playing".equals(player.getState())) {
            player.pause();
        } else {
            player.resume();
        }
    }

    @Override
    public void onPrev() {
        int current = player.getCurrentIndex();
        if (current > 0) {
            player.seekToTrack(current - 1, 0);
        }
    }

    @Override
    public void onNext() {
        int current = player.getCurrentIndex();
        // 如果没有下一轨，不操作
        player.seekToTrack(current + 1, 0);
    }

    @Override
    public void onStop() {
        player.stop();
    }

    // ===== 前台服务管理 =====

    private void startPlaybackService() {
        try {
            Context context = getContext();
            if (context == null) return;

            Intent intent = new Intent(context, AudioPlaybackService.class);
            intent.putExtra(AudioPlaybackService.EXTRA_TITLE, currentTitle);
            intent.putExtra(AudioPlaybackService.EXTRA_ARTIST, currentArtist);
            intent.putExtra(AudioPlaybackService.EXTRA_IS_PLAYING, true);

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent);
            } else {
                context.startService(intent);
            }
        } catch (Exception e) {
            Log.e(TAG, "startPlaybackService failed", e);
        }
    }

    private void updateServiceNotification() {
        try {
            boolean isPlaying = "playing".equals(player.getState());
            AudioPlaybackService.updateNotificationStatic(currentTitle, currentArtist, isPlaying);
        } catch (Exception e) {
            Log.e(TAG, "updateServiceNotification failed", e);
        }
    }

    private void stopPlaybackService() {
        try {
            Context context = getContext();
            if (context == null) return;
            Intent intent = new Intent(context, AudioPlaybackService.class);
            context.stopService(intent);
        } catch (Exception e) {
            Log.e(TAG, "stopPlaybackService failed", e);
        }
    }

    @Override
    protected void handleOnDestroy() {
        super.handleOnDestroy();
        player.release();
        stopPlaybackService();
        AudioPlaybackService.clearActionListener();
    }
}
