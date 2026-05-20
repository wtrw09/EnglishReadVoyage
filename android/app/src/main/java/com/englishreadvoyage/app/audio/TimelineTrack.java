package com.englishreadvoyage.app.audio;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONException;

import java.util.ArrayList;
import java.util.List;

/**
 * 播放列表中的单条音轨，与前端 nativeAudio.ts 中的 TimelineTrack 接口一一对应。
 */
public class TimelineTrack {
    public String id;
    public String url;
    public String lang;
    public long durationMs;
    public long startMs;
    public long endMs;
    public String sentenceId;
    public String bookId;
    public String title;

    /**
     * 从 JSON 数组解析音轨列表。
     * 期望格式：[{ id, url, lang?, durationMs, startMs, endMs, sentenceId?, bookId?, title? }, ...]
     */
    public static List<TimelineTrack> fromJsonArray(String json) throws JSONException {
        JSONArray arr = new JSONArray(json);
        List<TimelineTrack> tracks = new ArrayList<>(arr.length());
        for (int i = 0; i < arr.length(); i++) {
            tracks.add(fromJsonObject(arr.getJSONObject(i)));
        }
        return tracks;
    }

    private static TimelineTrack fromJsonObject(JSONObject obj) throws JSONException {
        TimelineTrack t = new TimelineTrack();
        t.id = obj.optString("id", "track_" + System.nanoTime());
        t.url = obj.optString("url", "");
        t.lang = obj.optString("lang", null);
        t.durationMs = obj.optLong("durationMs", 0);
        t.startMs = obj.optLong("startMs", 0);
        t.endMs = obj.optLong("endMs", 0);
        t.sentenceId = obj.optString("sentenceId", null);
        t.bookId = obj.optString("bookId", null);
        t.title = obj.optString("title", null);
        return t;
    }
}
