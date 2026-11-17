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
    private TextView bubbleTxt, bubbleGo, bubbleBuy;
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
        e.changed();
    }

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
        h.removeCallbacksAndMessages(null);
        if (e != null) {
            e.stop();
            e.buyStop();
            e.removeListener(listener);
        }
        hideBubble();
        removePick();
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

    private WindowManager.LayoutParams overlayParams(int w, int hgt, int extraFlags) {
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(w, hgt,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | extraFlags, PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        return lp;
    }

    // ---------- 浮動控制鈕 ----------
    private TextView chip(String text, int bg) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextColor(bg == 0 ? Color.WHITE : 0xFF222222);
        t.setTextSize(18);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(10), dp(4), dp(10), dp(4));
        if (bg != 0) {
            GradientDrawable g = new GradientDrawable();
            g.setColor(bg);
            g.setCornerRadius(dp(8));
            t.setBackground(g);
        }
        return t;
    }

    public void showBubble() {
        if (bubble != null || wm == null) return;
        bubble = new LinearLayout(this);
        bubble.setOrientation(LinearLayout.HORIZONTAL);
        bubble.setGravity(Gravity.CENTER_VERTICAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xEE1E2230);
        bg.setCornerRadius(dp(14));
        bubble.setBackground(bg);
        bubble.setPadding(dp(4), dp(4), dp(6), dp(4));

        TextView handle = chip("☰", 0);
        bubbleTxt = new TextView(this);
        bubbleTxt.setTextColor(Color.WHITE);
        bubbleTxt.setTextSize(11);
        bubbleTxt.setPadding(0, 0, dp(6), 0);
        bubbleGo = chip("▶", 0xFFFFC93C);
        TextView pick = chip("🎯", 0xFF8FD3FF);
        bubbleBuy = chip("🛒", 0xFFDDDDDD);
        LinearLayout.LayoutParams gap = new LinearLayout.LayoutParams(-2, -2);
        gap.setMargins(dp(4), 0, 0, 0);
        LinearLayout.LayoutParams gap2 = new LinearLayout.LayoutParams(-2, -2);
        gap2.setMargins(dp(4), 0, 0, 0);
        bubble.addView(handle);
        bubble.addView(bubbleTxt);
        bubble.addView(bubbleGo);
        bubble.addView(pick, gap);
        bubble.addView(bubbleBuy, gap2);
        bubbleBuy.setOnClickListener(v -> {
            if (e.buyRunning) e.buyStop();
            else if (!e.buyStart()) Toast.makeText(this, "先在 App 的「自動購買」分頁設定步驟位置", Toast.LENGTH_LONG).show();
        });

        bubbleGo.setOnClickListener(v -> {
            if (e.running) e.stop();
            else e.start();
        });
        pick.setOnClickListener(v -> startPick());

        blp = overlayParams(-2, -2, 0);
        blp.x = e.prefs().getInt("bx", dp(8));
        blp.y = e.prefs().getInt("by", dp(160));
        handle.setOnTouchListener(new View.OnTouchListener() {
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
        });
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
        ((GradientDrawable) bubbleGo.getBackground()).setColor(e.running ? 0xFFFF6B6B : 0xFFFFC93C);
        bubbleTxt.setText(e.running ? "下次 " + e.nextIn() + "s\n已點 " + e.count : "已停止\n已點 " + e.count);
        ((GradientDrawable) bubbleBuy.getBackground()).setColor(e.buyBusy ? 0xFFFFC93C : e.buyRunning ? 0xFF8FD3FF : 0xFFDDDDDD);
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
