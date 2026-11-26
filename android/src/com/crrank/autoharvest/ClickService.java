package com.crrank.autoharvest;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/** 無障礙服務：在螢幕座標點擊、顯示浮動控制鈕（等同電腦版 F9）、全螢幕選位置（等同 F8 / 選位置）。 */
public class ClickService extends AccessibilityService {
    public static volatile ClickService inst;

    private WindowManager wm;
    private Engine e;
    private final Handler h = new Handler(Looper.getMainLooper());
    private LinearLayout bubble;
    private TextView bubbleTxt, bubbleGo, bubbleBuy, bubbleBg;
    private WindowManager.LayoutParams blp;
    private View pickView;

    private final Runnable listener = this::updateBubble;
    private final Runnable ticker = new Runnable() {
        @Override
        public void run() {
            updateBubble();
            h.postDelayed(this, 500);
        }
    };

    @Override
    protected void onServiceConnected() {
        inst = this;
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        e = Engine.get(this);
        e.startServer();
        e.addListener(listener);
        if (e.showBubble) showBubble();
        h.post(ticker);
        android.content.IntentFilter f = new android.content.IntentFilter();
        f.addAction(Intent.ACTION_SCREEN_OFF);
        f.addAction(Intent.ACTION_SCREEN_ON);
        f.addAction(Intent.ACTION_USER_PRESENT);
        registerReceiver(screenRx, f);
        e.changed();
    }

    // ---------- 息屏也收成 ----------
    private boolean autoBg;   // 背景遊戲是不是因為息屏而自動開的

    private final android.content.BroadcastReceiver screenRx = new android.content.BroadcastReceiver() {
        @Override
        public void onReceive(android.content.Context c, Intent i) {
            String a = i.getAction();
            if (Intent.ACTION_SCREEN_OFF.equals(a)) {
                // 息屏後點擊會被系統擋下 → 改用背景遊戲（網頁面板直接點「收成」按鈕）繼續收成
                if (e.offHarvest && e.running && !bgRunning()) {
                    autoBg = true;
                    startBg(true);
                }
            } else if (Intent.ACTION_USER_PRESENT.equals(a)
                    || (Intent.ACTION_SCREEN_ON.equals(a) && Engine.screenUsable(ClickService.this))) {
                e.catchUp();  // 解鎖後馬上補點過期的
                if (autoBg) {
                    autoBg = false;
                    if (bgWeb != null) bgWeb.evaluateJavascript("window.__crac&&window.__crac.stopHarvest&&window.__crac.stopHarvest();", null);
                    h.postDelayed(ClickService.this::stopBg, 600);
                }
            }
        }
    };

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(Intent intent) {
        cleanup();
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        cleanup();
        super.onDestroy();
    }

    private void cleanup() {
        if (inst == this) inst = null;
        try {
            unregisterReceiver(screenRx);
        } catch (Exception ignored) {
        }
        h.removeCallbacksAndMessages(null);
        if (e != null) {
            e.stop();
            e.buyStop();
            e.removeListener(listener);
        }
        hideBubble();
        removePick();
        stopBg();
    }

    private int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    public void tap(int x, int y) {
        Path p = new Path();
        p.moveTo(Math.max(0, x), Math.max(0, y));
        GestureDescription.StrokeDescription sd = new GestureDescription.StrokeDescription(p, 0, 60);
        dispatchGesture(new GestureDescription.Builder().addStroke(sd).build(), null, null);
    }

    // ---------- 🌍 遠端遙控的實時畫面（Android 11 以上） ----------
    public interface JpegCallback {
        void done(byte[] jpg);
    }

    public void captureJpeg(final int cx, final int cy, final int maxW, final int quality, final JpegCallback cb) {
        if (android.os.Build.VERSION.SDK_INT < 30) {
            cb.done(null);
            return;
        }
        try {
            takeScreenshot(android.view.Display.DEFAULT_DISPLAY, getMainExecutor(), new TakeScreenshotCallback() {
                @Override
                public void onSuccess(ScreenshotResult r) {
                    new Thread(() -> {
                        byte[] out = null;
                        try {
                            android.hardware.HardwareBuffer hb = r.getHardwareBuffer();
                            android.graphics.Bitmap hw = android.graphics.Bitmap.wrapHardwareBuffer(hb, r.getColorSpace());
                            android.graphics.Bitmap bm = hw.copy(android.graphics.Bitmap.Config.ARGB_8888, true);
                            hw.recycle();
                            hb.close();
                            android.graphics.Canvas c = new android.graphics.Canvas(bm);
                            android.graphics.Paint p = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
                            p.setColor(0xFFFF3C3C);
                            p.setStyle(android.graphics.Paint.Style.STROKE);
                            p.setStrokeWidth(Math.max(4, bm.getWidth() / 150f));
                            float rr = Math.max(18, bm.getWidth() / 25f);
                            c.drawCircle(cx, cy, rr, p);
                            c.drawLine(cx - rr * 1.8f, cy, cx + rr * 1.8f, cy, p);
                            c.drawLine(cx, cy - rr * 1.8f, cx, cy + rr * 1.8f, p);
                            int w = Math.min(maxW, bm.getWidth());
                            android.graphics.Bitmap sm = android.graphics.Bitmap.createScaledBitmap(bm, w, bm.getHeight() * w / bm.getWidth(), true);
                            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                            sm.compress(android.graphics.Bitmap.CompressFormat.JPEG, quality, bo);
                            out = bo.toByteArray();
                            if (sm != bm) sm.recycle();
                            bm.recycle();
                        } catch (Throwable ignored) {
                        }
                        cb.done(out);
                    }).start();
                }

                @Override
                public void onFailure(int code) {
                    cb.done(null);  // 息屏或太頻繁時會失敗，下次再試
                }
            });
        } catch (Throwable t) {
            cb.done(null);
        }
    }

    // ---------- 背景遊戲：隱藏的遊戲視窗（透明、點不到），切去用別的 App 也會繼續跑 ----------
    private FrameLayout bgBox;
    private android.webkit.WebView bgWeb;
    private WindowManager.LayoutParams bgLp;
    private boolean bgShown;
    private android.os.PowerManager.WakeLock wakeLock;

    public boolean bgRunning() {
        return bgBox != null;
    }

    public boolean bgShown() {
        return bgShown;
    }

    public void startBg() {
        startBg(false);
    }

    /** 每 30 秒從 Java 叫醒網頁面板（息屏時網頁計時器會被拖慢，這裡用 wake lock 保證會跑） */
    private final Runnable bgTick = new Runnable() {
        @Override
        public void run() {
            if (bgWeb == null) return;
            bgWeb.resumeTimers();
            bgWeb.evaluateJavascript("window.__crac&&window.__crac.tick&&window.__crac.tick();"
                    + (autoBg ? "window.__crac&&window.__crac.ensureHarvest&&window.__crac.ensureHarvest();" : ""), null);
            h.postDelayed(this, 30000);
        }
    };

    @android.annotation.SuppressLint("SetJavaScriptEnabled")
    public void startBg(final boolean quiet) {
        if (bgBox != null || wm == null) return;
        bgWeb = new android.webkit.WebView(this);
        android.webkit.WebSettings s = bgWeb.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        android.webkit.CookieManager.getInstance().setAcceptCookie(true);
        android.webkit.CookieManager.getInstance().setAcceptThirdPartyCookies(bgWeb, true);
        final String js = Res.js(this);
        bgWeb.addJavascriptInterface(new NotifyBridge(this), "CRAndroid");
        bgWeb.setWebViewClient(new android.webkit.WebViewClient() {
            @Override
            public void onPageFinished(android.webkit.WebView v, String url) {
                if (url != null && url.contains("crrank.xpgs25.com")) {
                    v.evaluateJavascript("window.__cracAuto=1;" + js, null);
                    if (autoBg) h.postDelayed(() -> {
                        if (bgWeb != null) bgWeb.evaluateJavascript("window.__crac&&window.__crac.ensureHarvest&&window.__crac.ensureHarvest();", null);
                    }, 2000);
                }
            }
        });
        bgBox = new FrameLayout(this);
        bgBox.setBackgroundColor(Color.WHITE);
        bgBox.addView(bgWeb, new FrameLayout.LayoutParams(-1, -1));
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.END);
        bar.setPadding(dp(6), dp(30), dp(6), dp(6));
        TextView hide = pill("🌙 隱藏到背景", C_SKY);
        TextView close = pill("✕ 關閉背景遊戲", C_RED);
        LinearLayout.LayoutParams g = new LinearLayout.LayoutParams(-2, -2);
        g.setMargins(dp(6), 0, 0, 0);
        bar.addView(hide);
        bar.addView(close, g);
        bgBox.addView(bar, new FrameLayout.LayoutParams(-1, -2, Gravity.TOP));
        hide.setOnClickListener(v -> showBg(false));
        close.setOnClickListener(v -> stopBg());

        bgLp = overlayParams(-1, -1, WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE);
        bgLp.alpha = 0f;
        bgShown = false;
        try {
            wm.addView(bgBox, bgLp);
        } catch (Exception ex) {
            bgBox = null;
            bgWeb = null;
            return;
        }
        bgWeb.loadUrl(Engine.GAME_URL);
        bgWeb.onResume();
        bgWeb.resumeTimers();
        if (bubble != null) { // 讓浮動鈕保持在最上層
            hideBubble();
            showBubble();
        }
        try {
            android.os.PowerManager pm = (android.os.PowerManager) getSystemService(POWER_SERVICE);
            wakeLock = pm.newWakeLock(android.os.PowerManager.PARTIAL_WAKE_LOCK, "crrank:bg");
            wakeLock.acquire(12 * 60 * 60 * 1000L);
        } catch (Exception ignored) {
        }
        if (!quiet) Toast.makeText(this, "背景遊戲已開始：可以切去用別的 App，浮動鈕 🌙 可以顯示／隱藏", Toast.LENGTH_LONG).show();
        h.removeCallbacks(bgTick);
        h.postDelayed(bgTick, 30000);
        updateBubble();
    }

    public void showBg(boolean show) {
        if (bgBox == null) return;
        bgShown = show;
        bgLp.alpha = show ? 1f : 0f;
        if (show) bgLp.flags &= ~WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
        else bgLp.flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
        try {
            wm.updateViewLayout(bgBox, bgLp);
        } catch (Exception ignored) {
        }
        updateBubble();
    }

    public void stopBg() {
        h.removeCallbacks(bgTick);
        if (bgBox != null) {
            try {
                wm.removeView(bgBox);
            } catch (Exception ignored) {
            }
            try {
                bgWeb.destroy();
            } catch (Exception ignored) {
            }
            bgBox = null;
            bgWeb = null;
            bgShown = false;
        }
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        wakeLock = null;
        updateBubble();
    }

    /** 在 (x, y) 用手指滑動來捲動；down=true 代表內容往下捲（手指往上滑） */
    public void scroll(int x, int y, boolean down, int notches) {
        int hgt = getResources().getDisplayMetrics().heightPixels;
        int dist = Math.min(dp(90) * Math.max(1, notches), hgt / 2);
        int y2 = down ? y - dist : y + dist;
        y2 = Math.max(1, Math.min(hgt - 1, y2));
        Path p = new Path();
        p.moveTo(Math.max(0, x), Math.max(0, y));
        p.lineTo(Math.max(0, x), y2);
        GestureDescription.StrokeDescription sd = new GestureDescription.StrokeDescription(p, 0, 400);
        dispatchGesture(new GestureDescription.Builder().addStroke(sd).build(), null, null);
    }

    private WindowManager.LayoutParams overlayParams(int w, int hgt, int extraFlags) {
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(w, hgt,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | extraFlags, PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        return lp;
    }

    // ---------- 浮動控制鈕 ----------
    private static final int C_DARK = 0xF21E2230, C_IDLE = 0xFF3A4157, C_YEL = 0xFFFFC93C, C_RED = 0xFFFF6B6B,
            C_SKY = 0xFF8FD3FF, C_PUR = 0xFFB79CFF, C_CLOSE = 0xFF6B3442;

    private TextView pill(String text, int bg) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextColor(0xFF1E2230);
        t.setTextSize(14);
        t.setPadding(dp(14), dp(8), dp(14), dp(8));
        GradientDrawable g = new GradientDrawable();
        g.setColor(bg);
        g.setCornerRadius(dp(20));
        t.setBackground(g);
        return t;
    }

    /** 圓形小按鈕 */
    private TextView chip(String text, int bg) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextColor(bg == C_IDLE || bg == C_CLOSE ? Color.WHITE : 0xFF1E2230);
        t.setTextSize(16);
        t.setGravity(Gravity.CENTER);
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.OVAL);
        g.setColor(bg);
        t.setBackground(g);
        t.setLayoutParams(chipLp());
        return t;
    }

    private LinearLayout.LayoutParams chipLp() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(38), dp(38));
        lp.setMargins(dp(3), 0, dp(3), 0);
        return lp;
    }

    private void setChip(TextView t, int bg) {
        ((GradientDrawable) t.getBackground()).setColor(bg);
        t.setTextColor(bg == C_IDLE || bg == C_CLOSE ? Color.WHITE : 0xFF1E2230);
    }

    public void showBubble() {
        if (bubble != null || wm == null) return;
        bubble = new LinearLayout(this);
        bubble.setOrientation(LinearLayout.HORIZONTAL);
        bubble.setGravity(Gravity.CENTER_VERTICAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(C_DARK);
        bg.setCornerRadius(dp(26));
        bg.setStroke(dp(1), 0x33FFFFFF);
        bubble.setBackground(bg);
        bubble.setPadding(dp(4), dp(5), dp(5), dp(5));
        if (android.os.Build.VERSION.SDK_INT >= 21) bubble.setElevation(dp(6));

        TextView handle = new TextView(this);   // 拖曳把手
        handle.setText("⋮⋮");
        handle.setTextColor(0x99FFFFFF);
        handle.setTextSize(16);
        handle.setGravity(Gravity.CENTER);
        handle.setLayoutParams(new LinearLayout.LayoutParams(dp(26), dp(38)));

        bubbleTxt = new TextView(this);
        bubbleTxt.setTextColor(Color.WHITE);
        bubbleTxt.setTextSize(11);
        bubbleTxt.setLineSpacing(0, 1.05f);
        bubbleTxt.setPadding(dp(2), 0, dp(6), 0);
        bubbleTxt.setMinWidth(dp(58));

        bubbleGo = chip("▶", C_YEL);
        TextView pick = chip("🎯", C_IDLE);
        bubbleBuy = chip("🛒", C_IDLE);
        bubbleBg = chip("🌙", C_IDLE);
        TextView bx = chip("✕", C_CLOSE);
        bubble.addView(handle);
        bubble.addView(bubbleTxt);
        bubble.addView(bubbleGo);
        bubble.addView(pick);
        bubble.addView(bubbleBuy);
        bubble.addView(bubbleBg);
        bubble.addView(bx);

        bubbleGo.setOnClickListener(v -> {
            if (e.running) e.stop();
            else e.start();
        });
        pick.setOnClickListener(v -> startPick());
        bubbleBuy.setOnClickListener(v -> {
            if (e.buyRunning) e.buyStop();
            else if (!e.buyStart()) Toast.makeText(this, "先在 App 的「自動購買」分頁設定步驟位置", Toast.LENGTH_LONG).show();
        });
        bubbleBg.setOnClickListener(v -> {
            if (!bgRunning()) startBg();
            else showBg(!bgShown);
        });
        bubbleBg.setOnLongClickListener(v -> {
            if (bgRunning()) {
                stopBg();
                Toast.makeText(this, "已關閉背景遊戲", Toast.LENGTH_SHORT).show();
            }
            return true;
        });
        bx.setOnClickListener(v -> {   // 關掉浮動控制鈕（連點照常繼續）
            e.showBubble = false;
            e.save();
            hideBubble();
            e.changed();
            Toast.makeText(this, "已關掉浮動控制鈕（連點仍會繼續）。要再打開：App「定點連點」分頁勾「顯示浮動控制鈕」", Toast.LENGTH_LONG).show();
        });

        blp = overlayParams(-2, -2, 0);
        blp.x = e.prefs().getInt("bx", dp(8));
        blp.y = e.prefs().getInt("by", dp(160));
        View.OnTouchListener drag = new View.OnTouchListener() {
            float sx, sy;
            int ox, oy;

            @Override
            public boolean onTouch(View v, MotionEvent ev) {
                switch (ev.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        sx = ev.getRawX();
                        sy = ev.getRawY();
                        ox = blp.x;
                        oy = blp.y;
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        blp.x = ox + (int) (ev.getRawX() - sx);
                        blp.y = oy + (int) (ev.getRawY() - sy);
                        if (bubble != null) wm.updateViewLayout(bubble, blp);
                        return true;
                    case MotionEvent.ACTION_UP:
                        e.prefs().edit().putInt("bx", blp.x).putInt("by", blp.y).apply();
                        return true;
                }
                return false;
            }
        };
        handle.setOnTouchListener(drag);
        bubbleTxt.setOnTouchListener(drag);
        try {
            wm.addView(bubble, blp);
        } catch (Exception ex) {
            bubble = null;
            return;
        }
        updateBubble();
    }

    public void hideBubble() {
        if (bubble != null) {
            try {
                wm.removeView(bubble);
            } catch (Exception ignored) {
            }
            bubble = null;
        }
    }

    private void updateBubble() {
        if (bubble == null || e == null) return;
        bubbleGo.setText(e.running ? "■" : "▶");
        setChip(bubbleGo, e.running ? C_RED : C_YEL);
        String top = e.running ? (e.waitingScreen ? "等解鎖" : "收成中") : "已停止";
        String bottom = e.running && !e.waitingScreen ? e.nextIn() + "s · " + e.count + "次" : "已點 " + e.count;
        bubbleTxt.setText(top + "\n" + bottom);
        setChip(bubbleBuy, e.buyBusy ? C_YEL : e.buyRunning ? C_SKY : C_IDLE);
        setChip(bubbleBg, bgShown ? C_YEL : bgRunning() ? C_PUR : C_IDLE);
    }

    // ---------- 全螢幕選位置 ----------
    public interface PickCallback {
        void onPick(int x, int y);
    }

    public void startPick() {
        startPick("點一下「收成」按鈕的位置", (x, y) -> {
            e.x = x;
            e.y = y;
            e.save();
            Toast.makeText(this, "已設定位置 (" + x + ", " + y + ")", Toast.LENGTH_SHORT).show();
            e.changed();
        });
    }

    public void startPick(String prompt, PickCallback onPick) {
        if (pickView != null || wm == null) return;
        FrameLayout fl = new FrameLayout(this);
        fl.setBackgroundColor(0x66000000);
        TextView tip = new TextView(this);
        tip.setText(prompt);
        tip.setTextColor(Color.WHITE);
        tip.setTextSize(20);
        tip.setGravity(Gravity.CENTER);
        tip.setShadowLayer(4, 0, 0, Color.BLACK);
        FrameLayout.LayoutParams tlp = new FrameLayout.LayoutParams(-1, -2, Gravity.TOP);
        tlp.topMargin = dp(90);
        fl.addView(tip, tlp);
        TextView cancel = new TextView(this);
        cancel.setText("取消");
        cancel.setTextColor(0xFF222222);
        cancel.setTextSize(16);
        cancel.setPadding(dp(22), dp(10), dp(22), dp(10));
        GradientDrawable cb = new GradientDrawable();
        cb.setColor(Color.WHITE);
        cb.setCornerRadius(dp(20));
        cancel.setBackground(cb);
        FrameLayout.LayoutParams clp = new FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        clp.bottomMargin = dp(80);
        fl.addView(cancel, clp);
        cancel.setOnClickListener(v -> removePick());

        fl.setOnTouchListener((v, ev) -> {
            if (ev.getActionMasked() == MotionEvent.ACTION_DOWN) {
                int px = Math.round(ev.getRawX()), py = Math.round(ev.getRawY());
                removePick();
                onPick.onPick(px, py);
            }
            return true;
        });
        WindowManager.LayoutParams lp = overlayParams(-1, -1,
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS);
        try {
            wm.addView(fl, lp);
            pickView = fl;
        } catch (Exception ignored) {
        }
    }

    private void removePick() {
        if (pickView != null) {
            try {
                wm.removeView(pickView);
            } catch (Exception ignored) {
            }
            pickView = null;
        }
    }
}
