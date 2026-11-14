package com.crrank.autoharvest;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Random;

/** 連點核心：設定、計時、狀態。和電腦版 Clicker 對應。 */
public final class Engine {
    public static final String GAME_URL = "https://crrank.xpgs25.com/game";
    public static final String[] UNITS = {"秒", "分", "時"};

    private static Engine inst;

    public static synchronized Engine get(Context c) {
        if (inst == null) inst = new Engine(c.getApplicationContext());
        return inst;
    }

    public final Context ctx;
    private final SharedPreferences sp;
    public final Handler h = new Handler(Looper.getMainLooper());
    private final Random rnd = new Random();
    private final List<Runnable> listeners = new ArrayList<>();
    public final String token;

    public int x, y, limit;
    public double interval, jitter;
    public String unit;
    public boolean clickNow, showBubble;

    public volatile boolean running;
    public volatile int count;
    public volatile long nextAt;
    private int done;
    private WebServer server;

    private Engine(Context c) {
        ctx = c;
        sp = c.getSharedPreferences("settings", Context.MODE_PRIVATE);
        x = sp.getInt("x", 0);
        y = sp.getInt("y", 0);
        interval = parse(sp.getString("interval", "60"), 60);
        unit = sp.getString("unit", "秒");
        jitter = parse(sp.getString("jitter", "0"), 0);
        limit = sp.getInt("limit", 0);
        clickNow = sp.getBoolean("click_now", true);
        showBubble = sp.getBoolean("bubble", true);
        String a = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
        SecureRandom r = new SecureRandom();
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 11; i++) sb.append(a.charAt(r.nextInt(a.length())));
        token = sb.toString();
    }

    private static double parse(String s, double d) {
        try {
            return Double.parseDouble(s);
        } catch (Exception e) {
            return d;
        }
    }

    public void save() {
        sp.edit().putInt("x", x).putInt("y", y).putString("interval", fmt(interval)).putString("unit", unit)
                .putString("jitter", fmt(jitter)).putInt("limit", limit).putBoolean("click_now", clickNow)
                .putBoolean("bubble", showBubble).apply();
    }

    public SharedPreferences prefs() {
        return sp;
    }

    public static String fmt(double v) {
        return v == Math.rint(v) ? String.valueOf((long) v) : String.valueOf(v);
    }

    public static double unitSec(String u) {
        return "分".equals(u) ? 60 : "時".equals(u) ? 3600 : 1;
    }

    public double intervalSec() {
        return Math.max(0.1, interval * unitSec(unit));
    }

    private double waitSec() {
        double w = intervalSec();
        if (jitter > 0) w += (rnd.nextDouble() * 2 - 1) * jitter;
        return Math.max(0.1, w);
    }

    // ---------- 監聽 ----------
    public void addListener(Runnable r) {
        if (!listeners.contains(r)) listeners.add(r);
    }

    public void removeListener(Runnable r) {
        listeners.remove(r);
    }

    public void changed() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            h.post(this::changed);
            return;
        }
        for (Runnable r : new ArrayList<>(listeners)) r.run();
    }

    // ---------- 連點 ----------
    public boolean serviceReady() {
        return ClickService.inst != null;
    }

    public void start() {
        if (running) return;
        count = 0;
        begin();
    }

    private void begin() {
        running = true;
        done = 0;
        h.removeCallbacks(tick);
        if (clickNow) h.post(tick);
        else schedule();
        changed();
    }

    public void stop() {
        running = false;
        h.removeCallbacks(tick);
        changed();
    }

    public void toggle() {
        if (running) stop();
        else start();
    }

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            if (!running) return;
            tap();
            done++;
            if (limit > 0 && done >= limit) {
                running = false;
                changed();
                return;
            }
            schedule();
        }
    };

    private void schedule() {
        double w = waitSec();
        nextAt = System.currentTimeMillis() + (long) (w * 1000);
        h.postDelayed(tick, (long) (w * 1000));
        changed();
    }

    public void once() {
        tap();
        changed();
    }

    private void tap() {
        ClickService s = ClickService.inst;
        if (s != null) {
            s.tap(x, y);
            count++;
        }
    }

    /** 遙控改間隔：執行中就以新間隔重新開始（不歸零次數） */
    public void setInterval(double v, String u) {
        if (v <= 0) return;
        interval = v;
        for (String k : UNITS) if (k.equals(u)) unit = u;
        save();
        if (running) {
            h.removeCallbacks(tick);
            begin();
        } else changed();
    }

    public int nextIn() {
        return running ? (int) Math.max(0, Math.round((nextAt - System.currentTimeMillis()) / 1000.0)) : 0;
    }

    public String statusJson() {
        return String.format(Locale.US,
                "{\"running\": %s, \"count\": %d, \"x\": %d, \"y\": %d, \"interval\": %s, \"unit\": \"%s\", \"next_in\": %d, \"service\": %s}",
                running, count, x, y, fmt(interval), unit, nextIn(), serviceReady());
    }

    public String statusText() {
        String s = running ? "執行中 · 下次 " + nextIn() + " 秒" : "已停止";
        return s + " · 已點 " + count + " 次";
    }

    // ---------- 區網伺服器 ----------
    public synchronized void startServer() {
        if (server != null) return;
        server = new WebServer(this);
        server.start();
    }

    public String url() {
        if (server == null || server.port == 0) return "（伺服器啟動失敗）";
        return "http://" + lanIp() + ":" + server.port + "/?t=" + token;
    }

    public static String lanIp() {
        String fallback = null;
        try {
            for (NetworkInterface ni : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InetAddress a : Collections.list(ni.getInetAddresses())) {
                    if (!(a instanceof Inet4Address) || !a.isSiteLocalAddress()) continue;
                    String n = ni.getName();
                    if (n.startsWith("wlan") || n.startsWith("ap") || n.startsWith("swlan")) return a.getHostAddress();
                    if (fallback == null) fallback = a.getHostAddress();
                }
            }
        } catch (Exception ignored) {
        }
        return fallback != null ? fallback : "127.0.0.1";
    }
}
