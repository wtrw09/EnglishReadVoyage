package com.englishreadvoyage.app.audio;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.core.app.NotificationCompat;

/**
 * 前台服务，用于在 Android 后台播放音频时保持进程存活。
 *
 * 生命周期：
 * - startForeground() 在 play() 被调用时启动
 * - stopForeground() + stopSelf() 在 stop() 时停止
 *
 * 注意：实际的音频播放逻辑在 PlaylistAudioPlayer 中，
 * 此 Service 仅负责通知栏展示和前台保活。
 */
public class AudioPlaybackService extends Service {

    private static final String TAG = "AudioPlaybackService";
    private static final String CHANNEL_ID = "media_playback";
    private static final int NOTIFICATION_ID = 1001;

    // Intent actions from notification controls
    public static final String ACTION_PLAY_PAUSE = "com.englishreadvoyage.action.PLAY_PAUSE";
    public static final String ACTION_PREV = "com.englishreadvoyage.action.PREV";
    public static final String ACTION_NEXT = "com.englishreadvoyage.action.NEXT";
    public static final String ACTION_STOP = "com.englishreadvoyage.action.STOP";

    // Extra keys
    public static final String EXTRA_TITLE = "title";
    public static final String EXTRA_ARTIST = "artist";
    public static final String EXTRA_IS_PLAYING = "is_playing";

    // 静态实例引用，用于 NativeAudioPlugin 更新通知
    private static AudioPlaybackService instance;

    // 静态回调，由 NativeAudioPlugin 设置
    private static NotificationActionListener actionListener;

    public interface NotificationActionListener {
        void onPlayPause();
        void onPrev();
        void onNext();
        void onStop();
    }

    public static void setActionListener(NotificationActionListener listener) {
        actionListener = listener;
    }

    public static void clearActionListener() {
        actionListener = null;
    }

    /**
     * 更新通知（由 NativeAudioPlugin 通过静态方法调用）。
     */
    public static void updateNotificationStatic(String title, String artist, boolean isPlaying) {
        AudioPlaybackService svc = instance;
        if (svc != null) {
            svc.postNotification(title, artist, isPlaying);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null) {
            String action = intent.getAction();
            if (action != null) {
                handleAction(action);
            } else {
                // 首次启动：从 Intent extras 读取元数据并显示通知
                String title = intent.getStringExtra(EXTRA_TITLE);
                String artist = intent.getStringExtra(EXTRA_ARTIST);
                boolean isPlaying = intent.getBooleanExtra(EXTRA_IS_PLAYING, true);
                showForeground(title, artist, isPlaying);
            }
        }
        // 如果服务被杀，自动重建
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
    }

    /**
     * 启动前台服务并显示通知。
     */
    private void showForeground(String title, String artist, boolean isPlaying) {
        Notification notification = buildNotification(title, artist, isPlaying);
        startForeground(NOTIFICATION_ID, notification);
    }

    /**
     * 更新通知（内部调用）。
     */
    private void postNotification(String title, String artist, boolean isPlaying) {
        Notification notification = buildNotification(title, artist, isPlaying);
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify(NOTIFICATION_ID, notification);
        }
    }

    // ---- 私有方法 ----

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "音乐播放",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("后台播放音频时的通知");
            channel.setShowBadge(false);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    private Notification buildNotification(String title, String artist, boolean isPlaying) {
        // PendingIntent flags for Android 12+ (FLAG_IMMUTABLE)
        int pendingFlags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            pendingFlags |= PendingIntent.FLAG_IMMUTABLE;
        }

        // Play/pause action
        Intent playPauseIntent = new Intent(this, AudioPlaybackService.class);
        playPauseIntent.setAction(ACTION_PLAY_PAUSE);
        PendingIntent playPausePending = PendingIntent.getService(this, 0, playPauseIntent, pendingFlags);

        // Previous track action
        Intent prevIntent = new Intent(this, AudioPlaybackService.class);
        prevIntent.setAction(ACTION_PREV);
        PendingIntent prevPending = PendingIntent.getService(this, 1, prevIntent, pendingFlags);

        // Next track action
        Intent nextIntent = new Intent(this, AudioPlaybackService.class);
        nextIntent.setAction(ACTION_NEXT);
        PendingIntent nextPending = PendingIntent.getService(this, 2, nextIntent, pendingFlags);

        // Stop action
        Intent stopIntent = new Intent(this, AudioPlaybackService.class);
        stopIntent.setAction(ACTION_STOP);
        PendingIntent stopPending = PendingIntent.getService(this, 3, stopIntent, pendingFlags);

        int playPauseIcon = isPlaying
                ? android.R.drawable.ic_media_pause
                : android.R.drawable.ic_media_play;

        String playPauseText = isPlaying ? "暂停" : "播放";

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(title != null ? title : "英语阅读之旅")
                .setContentText(artist != null ? artist : "听书播放")
                .setSmallIcon(android.R.drawable.ic_media_play)
                .setOngoing(true)
                .setShowWhen(false)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .addAction(android.R.drawable.ic_media_previous, "上一首", prevPending)
                .addAction(playPauseIcon, playPauseText, playPausePending)
                .addAction(android.R.drawable.ic_media_next, "下一首", nextPending)
                .addAction(android.R.drawable.ic_menu_close_clear_cancel, "关闭", stopPending)
                .setStyle(new androidx.media.app.NotificationCompat.MediaStyle()
                        .setShowActionsInCompactView(0, 1, 2) // 紧凑视图显示 prev, play/pause, next
                        .setShowCancelButton(true)
                        .setCancelButtonIntent(stopPending))
                .build();
    }

    private void handleAction(String action) {
        if (actionListener == null) return;
        switch (action) {
            case ACTION_PLAY_PAUSE:
                actionListener.onPlayPause();
                break;
            case ACTION_PREV:
                actionListener.onPrev();
                break;
            case ACTION_NEXT:
                actionListener.onNext();
                break;
            case ACTION_STOP:
                actionListener.onStop();
                break;
        }
    }
}
