package com.englishreadvoyage.app;

import android.os.Bundle;
import android.webkit.WebView;

import com.englishreadvoyage.app.plugins.MediaStoreSaverPlugin;
import com.englishreadvoyage.app.plugins.NativeAudioPlugin;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(MediaStoreSaverPlugin.class);
        registerPlugin(NativeAudioPlugin.class);
        super.onCreate(savedInstanceState);

        // 禁用 WebView 缩放（双指缩放 + 滚轮缩放）
        WebView webView = getBridge().getWebView();
        if (webView != null) {
            webView.getSettings().setBuiltInZoomControls(false);
            webView.getSettings().setDisplayZoomControls(false);
            webView.getSettings().setSupportZoom(false);
        }
    }
}
