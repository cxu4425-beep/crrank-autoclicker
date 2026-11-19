package com.crrank.autoharvest;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.webkit.JavascriptInterface;

/** 讓網頁面板可以發 Android 系統通知（WebView 不支援網頁的 Notification）：window.CRAndroid.notify(title, text) */
public final class NotifyBridge {
    private static final String CHANNEL = "crrank_alerts";
    private static int nextId = 100;
    private final Context ctx;

    public NotifyBridge(Context c) {
        ctx = c.getApplicationContext();
    }

    @JavascriptInterface
    public void notify(String title, String text) {
        show(ctx, title, text);
    }

    public static void show(Context ctx, String title, String text) {
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            if (nm.getNotificationChannel(CHANNEL) == null) {
                NotificationChannel ch = new NotificationChannel(CHANNEL, "遊戲提醒", NotificationManager.IMPORTANCE_HIGH);
                ch.setDescription("能量快滿等提醒");
                nm.createNotificationChannel(ch);
            }
            b = new Notification.Builder(ctx, CHANNEL);
        } else {
            b = new Notification.Builder(ctx);
            b.setPriority(Notification.PRIORITY_HIGH);
            b.setDefaults(Notification.DEFAULT_ALL);
        }
        Intent open = new Intent(ctx, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent pi = PendingIntent.getActivity(ctx, 0, open,
                Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
        b.setSmallIcon(R.drawable.ic_launcher).setContentTitle(title).setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text)).setAutoCancel(true).setContentIntent(pi);
        try {
            nm.notify(nextId++, b.build());
        } catch (SecurityException ignored) { // 沒有通知權限
        }
    }
}
