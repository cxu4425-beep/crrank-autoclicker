package com.crrank.autoharvest;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** 內建瀏覽器開啟知識領土，並自動注入「自動收成」面板（和書籤／使用者腳本相同）。 */
public class GameActivity extends Activity {
    private WebView w;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        w = new WebView(this);
        WebSettings s = w.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(w, true);
        final String js = Res.js(this);
        w.addJavascriptInterface(new NotifyBridge(this), "CRAndroid");
        w.setWebChromeClient(new WebChromeClient());
        w.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                String sc = u.getScheme();
                if ("http".equals(sc) || "https".equals(sc)) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (Exception ignored) {
                }
                return true;
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                if (url != null && url.contains("crrank.xpgs25.com")) v.evaluateJavascript(js, null);
            }
        });
        setContentView(w);
        if (b != null) w.restoreState(b);
        else w.loadUrl(Engine.GAME_URL);
    }

    @Override
    public boolean onCreateOptionsMenu(android.view.Menu menu) {
        menu.add(0, 1, 0, "🌙 切到背景執行").setShowAsAction(android.view.MenuItem.SHOW_AS_ACTION_ALWAYS);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(android.view.MenuItem item) {
        if (item.getItemId() != 1) return super.onOptionsItemSelected(item);
        ClickService s = ClickService.inst;
        if (s == null) {
            android.widget.Toast.makeText(this, "要先開啟無障礙權限才能背景執行（App 主畫面「定點連點」分頁）",
                    android.widget.Toast.LENGTH_LONG).show();
            return true;
        }
        CookieManager.getInstance().flush();
        finish();                 // 關掉前台的遊戲頁，換成背景視窗接手
        s.startBg();
        return true;
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        w.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (w.canGoBack()) w.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        CookieManager.getInstance().flush();
        w.destroy();
        super.onDestroy();
    }
}
