package com.crrank.autoharvest;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * 🖥 遙控電腦：App 裡直接開遠端遙控頁面。掃過（或貼上）的電腦會記在 App 裡，
 * 之後打開就自動連上，不用每次掃 QR Code。
 */
public class RemoteActivity extends Activity {
    private WebView web;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (android.os.Build.VERSION.SDK_INT >= 21) getWindow().setStatusBarColor(0xFF1E2230);
        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(0xF4, 0xF1, 0xEA));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);  // 記住的電腦存在這裡（只在這支手機）
        web.setWebChromeClient(new WebChromeClient());  // 讓「改名」「刪除」的對話框可以跳出來
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, String url) {
                if (url.startsWith(Remote.PAGE)) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                } catch (Exception ignored) {
                }
                return true;
            }
        });
        setContentView(web);
        load(getIntent());
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        load(i);
    }

    /** 從連結打開（掃 QR Code 選「用這個 App 開啟」或貼上連結）就加入那台電腦；否則打開上次用的。 */
    private void load(Intent i) {
        String url = Remote.PAGE;
        Uri d = i != null ? i.getData() : null;
        String extra = i != null ? i.getStringExtra("link") : null;
        if (d != null && d.toString().startsWith(Remote.PAGE)) url = d.toString();
        else if (extra != null && extra.contains("#")) url = Remote.PAGE + extra.substring(extra.indexOf('#'));
        web.loadUrl(url);
    }

    @Override
    public void onBackPressed() {
        finish();
    }

    @Override
    protected void onDestroy() {
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
