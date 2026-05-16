package com.englishreadvoyage.app;

import android.os.Bundle;

import com.englishreadvoyage.app.plugins.MediaStoreSaverPlugin;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(MediaStoreSaverPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
