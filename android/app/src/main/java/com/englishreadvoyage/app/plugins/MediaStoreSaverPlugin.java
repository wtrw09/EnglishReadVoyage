package com.englishreadvoyage.app.plugins;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

/**
 * 自定义 Capacitor 插件，使用 MediaStore API 将文件保存到系统 Downloads 目录。
 *
 * Android 10+（API 29+）：通过 MediaStore.Downloads 写入，无需存储权限
 * Android 9-（API < 29）：直接写入 /storage/emulated/0/Download/，需 WRITE_EXTERNAL_STORAGE
 */
@CapacitorPlugin(name = "MediaStoreSaver")
public class MediaStoreSaverPlugin extends Plugin {

    @PluginMethod
    public void saveToDownloads(PluginCall call) {
        String filename = call.getString("filename");
        String base64Data = call.getString("data");

        if (filename == null || filename.isEmpty()) {
            call.reject("Missing required parameter: filename");
            return;
        }
        if (base64Data == null || base64Data.isEmpty()) {
            call.reject("Missing required parameter: data");
            return;
        }

        try {
            byte[] decodedBytes = Base64.decode(base64Data, Base64.NO_WRAP);
            String mimeType = getMimeType(filename);
            Context context = getContext();

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                // Android 10+: 使用 MediaStore API 写入 Downloads
                ContentValues values = new ContentValues();
                values.put(MediaStore.Downloads.DISPLAY_NAME, filename);
                values.put(MediaStore.Downloads.MIME_TYPE, mimeType);
                values.put(MediaStore.Downloads.IS_PENDING, 0);
                // RELATIVE_PATH 让文件出现在 Downloads 目录下
                values.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);

                Uri uri = context.getContentResolver().insert(
                        MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (uri == null) {
                    call.reject("MediaStore: 创建 entry 失败");
                    return;
                }

                try (OutputStream os = context.getContentResolver().openOutputStream(uri)) {
                    if (os == null) {
                        call.reject("MediaStore: 打开输出流失败");
                        return;
                    }
                    os.write(decodedBytes);
                }

                JSObject result = new JSObject();
                result.put("success", true);
                result.put("uri", uri.toString());
                call.resolve(result);
            } else {
                // Android 9-: 直接写入公共 Downloads 目录
                File downloadsDir = Environment.getExternalStoragePublicDirectory(
                        Environment.DIRECTORY_DOWNLOADS);
                if (!downloadsDir.exists()) {
                    downloadsDir.mkdirs();
                }
                File file = new File(downloadsDir, filename);
                try (FileOutputStream fos = new FileOutputStream(file)) {
                    fos.write(decodedBytes);
                }

                JSObject result = new JSObject();
                result.put("success", true);
                result.put("uri", Uri.fromFile(file).toString());
                call.resolve(result);
            }
        } catch (Exception e) {
            call.reject("保存失败: " + e.getMessage());
        }
    }

    private String getMimeType(String filename) {
        if (filename == null) return "application/octet-stream";
        String lower = filename.toLowerCase();
        if (lower.endsWith(".apkg")) return "application/x-apkg";
        if (lower.endsWith(".docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        if (lower.endsWith(".zip")) return "application/zip";
        if (lower.endsWith(".txt")) return "text/plain";
        return "application/octet-stream";
    }
}
