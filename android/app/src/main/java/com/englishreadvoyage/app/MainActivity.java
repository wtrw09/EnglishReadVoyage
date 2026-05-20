package com.englishreadvoyage.app;

import android.os.Bundle;

import com.englishreadvoyage.app.plugins.MediaStoreSaverPlugin;
import com.englishreadvoyage.app.plugins.NativeAudioPlugin;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(MediaStoreSaverPlugin.class);
        registerPlugin(NativeAudioPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
