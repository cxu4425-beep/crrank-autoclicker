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
    /** 息屏時改用背景遊戲（網頁面板點按鈕）繼續收成 */
    public boolean offHarvest;
    /** 自動判斷每小時產量：點完收成後讀遊戲畫面，算出快滿前什麼時候再收 */
    public boolean autoRate;
    public volatile GameReader.Rates lastRates;
    public volatile long lastReadAt;
    public volatile boolean lastReadOk, smartUsed;
    private long lastPeriodicRead;

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
        offHarvest = sp.getBoolean("off_harvest", true);
        autoRate = sp.getBoolean("auto_rate", true);
        String a = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
        SecureRandom r = new SecureRandom();
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 11; i++) sb.append(a.charAt(r.nextInt(a.length())));
        token = sb.toString();
        loadBuy();
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
                .putBoolean("bubble", showBubble).putBoolean("off_harvest", offHarvest)
                .putBoolean("auto_rate", autoRate).apply();
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
        smartUsed = false;
        nextAt = clickNow ? 0 : System.currentTimeMillis() + (long) (waitSec() * 1000);
        ensureWatch();
        changed();
    }

    public void stop() {
        running = false;
        changed();
    }

    public void toggle() {
        if (running) stop();
        else start();
    }

    /** 螢幕亮著而且已解鎖才點得到（息屏或鎖屏時點擊會被系統擋下）。 */
    public static boolean screenUsable(Context c) {
        try {
            android.os.PowerManager pm = (android.os.PowerManager) c.getSystemService(Context.POWER_SERVICE);
            android.app.KeyguardManager km = (android.app.KeyguardManager) c.getSystemService(Context.KEYGUARD_SERVICE);
            return pm.isInteractive() && (km == null || !km.isKeyguardLocked());
        } catch (Exception ex) {
            return true;
        }
    }

    public volatile boolean waitingScreen;

    /** 每秒用「真實時間」檢查一次：手機睡眠時 postDelayed 會停住，醒來後這裡會馬上補點，不會卡在 0。 */
    private final Runnable watch = new Runnable() {
        @Override
        public void run() {
            if (!running && !buyRunning) return;
            long now = System.currentTimeMillis();
            boolean usable = screenUsable(ctx);
            boolean due = running && now >= nextAt;
            waitingScreen = (due || (buyRunning && !buyBusy && now >= buyNextAt)) && !usable;
            if (due && usable) {
                tap();
                done++;
                if (limit > 0 && done >= limit) running = false;
                else {
                    nextAt = now + (long) (waitSec() * 1000);
                    if (autoRate) h.postDelayed(() -> readGame(true), 2500);  // 等遊戲畫面更新再讀
                }
                changed();
            } else if (running && autoRate && usable && now - lastPeriodicRead > 60000) {
                lastPeriodicRead = now;
                readGame(false);
            }
            if (buyRunning && !buyBusy && buyNextAt > 0 && now >= buyNextAt && usable) {
                buyNextAt = 0;
                runSequence(() -> buySchedule());
            }
            h.postDelayed(this, 1000);
        }
    };

    private void ensureWatch() {
        h.removeCallbacks(watch);
        h.post(watch);
    }

    /**
     * 讀畫面上的遊戲數字。afterTap＝剛點完收成（還沒收的當作 0）；
     * 定時讀取只有在讀得到「收成 +x/y」時才調整下次時間。
     */
    public void readGame(boolean afterTap) {
        ClickService s = ClickService.inst;
        if (s == null) return;
        GameReader.Rates r = null;
        try {
            r = GameReader.read(s);
        } catch (Exception ignored) {
        }
        lastReadAt = System.currentTimeMillis();
        lastReadOk = r != null;
        if (r != null) {
            lastRates = r;
            double sec = r.smartSec();
            if (running && sec > 0 && (afterTap || r.hasPending)) {
                if (jitter > 0) sec += (rnd.nextDouble() * 2 - 1) * jitter;
                nextAt = lastReadAt + (long) (Math.max(30, sec) * 1000);
                smartUsed = true;
            }
        }
        changed();
    }

    public String rateText() {
        if (!autoRate) return "已關閉：用下面的固定間隔。";
        if (lastReadAt == 0) return "開始收成後，每次點完會讀遊戲畫面上的產量（遊戲要在畫面上）。";
        String when = new java.text.SimpleDateFormat("HH:mm:ss", Locale.US).format(new java.util.Date(lastReadAt));
        GameReader.Rates r = lastRates;
        if (lastReadOk && r != null) {
            double sec = r.smartSec();
            return "✔ " + r.describe() + "\n→ 約 " + GameReader.minutes(sec) + " 分鐘後快滿，到時自動收成（" + when + " 讀取）";
        }
        return "這次沒讀到遊戲（" + when + "）：遊戲要停在畫面上。讀不到時用下面的間隔。"
                + (r != null ? "\n上次讀到：" + r.describe() : "");
    }

    /** 螢幕打開／解鎖時呼叫：立刻檢查有沒有過期沒點的。 */
    public void catchUp() {
        if (running || buyRunning) ensureWatch();
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
        if (running) begin();
        else changed();
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
        int n = nextIn();
        String nx = n >= 120 ? (n / 60) + " 分 " + (n % 60) + " 秒" : n + " 秒";
        String s = running ? (waitingScreen ? "執行中 · 等螢幕解鎖後補點" : "執行中 · 下次 " + nx + (autoRate && smartUsed ? " · 🤖 自動判斷" : "")) : "已停止";
        return s + " · 已點 " + count + " 次";
    }

    // ---------- 自動購買（照順序點擊步驟，和電腦版 BuyRunner 相同） ----------
    public static final long RESTOCK_MS = 30 * 60 * 1000L;
    public static final Object[][] BUY_TEMPLATE = {
            {"打開「物品」", 1, 1.2}, {"點「商店」分頁", 1, 1.0}, {"點商品分類（道具／地形）", 1, 1.0},
            {"點商品的「購買」", 3, 1.0}, {"關閉商店 ×", 1, 0.5}};

    public static final class Step {
        public String name;
        public Integer x, y;
        public int times = 1;
        public double wait = 1.0;
        public String type = "click"; // click / scroll
        public String dir = "down";   // 滾動方向 down / up
        public int amount = 3;        // 滾動格數

        public boolean isScroll() {
            return "scroll".equals(type);
        }

        public String action() {
            return isScroll() ? "滾動" + ("up".equals(dir) ? "↑" : "↓") + amount + "格" : "點擊";
        }
    }

    public static final class Slot {
        public String name;
        public final List<Step> steps = new ArrayList<>();
    }

    public static final int NUM_SLOTS = 3;
    public final List<Slot> slots = new ArrayList<>();
    public int slot = 0;
    public boolean buyRotate = false;
    /** 目前存檔的步驟（切換存檔時會換成別的清單） */
    public List<Step> steps = new ArrayList<>();
    private String curSlotName = "";
    public String buyMode = "restock";
    public double buyOffset = 10, buyEvery = 30;
    public boolean buyNow = true;
    public volatile boolean buyRunning, buyBusy;
    public int buyRuns;
    public long buyNextAt;
    public String buyLog = "";
    private int seqGen;

    void loadBuy() {
        buyMode = sp.getString("buy_mode", "restock");
        buyOffset = parse(sp.getString("buy_offset", "10"), 10);
        buyEvery = parse(sp.getString("buy_every", "30"), 30);
        buyNow = sp.getBoolean("buy_now", true);
        buyRotate = sp.getBoolean("buy_rotate", false);
        slots.clear();
        try {
            org.json.JSONArray a = new org.json.JSONArray(sp.getString("buy_slots", "[]"));
            for (int i = 0; i < a.length(); i++) {
                org.json.JSONObject o = a.getJSONObject(i);
                Slot sl = new Slot();
                sl.name = o.optString("name", "存檔" + (i + 1));
                readSteps(o.optJSONArray("steps"), sl.steps);
                slots.add(sl);
            }
        } catch (Exception ignored) {
        }
        if (slots.isEmpty()) { // 舊版只有一組步驟 → 搬到「存檔1」
            Slot first = new Slot();
            first.name = "存檔1";
            try {
                readSteps(new org.json.JSONArray(sp.getString("buy_steps", "[]")), first.steps);
            } catch (Exception ignored) {
            }
            slots.add(first);
        }
        while (slots.size() < NUM_SLOTS) {
            Slot sl = new Slot();
            sl.name = "存檔" + (slots.size() + 1);
            slots.add(sl);
        }
        int k = sp.getInt("buy_slot", 0);
        switchSlot(k >= 0 && k < slots.size() ? k : 0);
    }

    private static void readSteps(org.json.JSONArray a, List<Step> out) throws org.json.JSONException {
        if (a == null) return;
        for (int i = 0; i < a.length(); i++) {
            org.json.JSONObject o = a.getJSONObject(i);
            Step s = new Step();
            s.name = o.optString("name", "步驟");
            s.x = o.isNull("x") ? null : o.getInt("x");
            s.y = o.isNull("y") ? null : o.getInt("y");
            s.times = Math.max(1, o.optInt("times", 1));
            s.wait = Math.max(0.1, o.optDouble("wait", 1));
            s.type = o.optString("type", "click");
            s.dir = o.optString("dir", "down");
            s.amount = Math.max(1, o.optInt("amount", 3));
            out.add(s);
        }
    }

    public void switchSlot(int i) {
        slot = i;
        steps = slots.get(i).steps;
    }

    public Slot curSlot() {
        return slots.get(slot);
    }

    public long lastSaved;

    /** 自動存檔：步驟有任何變動就呼叫 */
    public void saveBuy() {
        org.json.JSONArray all = new org.json.JSONArray();
        try {
            for (Slot sl : slots) {
                org.json.JSONArray a = new org.json.JSONArray();
                for (Step s : sl.steps) {
                    org.json.JSONObject o = new org.json.JSONObject();
                    o.put("name", s.name);
                    o.put("x", s.x == null ? org.json.JSONObject.NULL : s.x);
                    o.put("y", s.y == null ? org.json.JSONObject.NULL : s.y);
                    o.put("times", s.times);
                    o.put("wait", s.wait);
                    o.put("type", s.type);
                    o.put("dir", s.dir);
                    o.put("amount", s.amount);
                    a.put(o);
                }
                org.json.JSONObject so = new org.json.JSONObject();
                so.put("name", sl.name);
                so.put("steps", a);
                all.put(so);
            }
        } catch (Exception ignored) {
        }
        sp.edit().putString("buy_slots", all.toString()).remove("buy_steps").putInt("buy_slot", slot)
                .putBoolean("buy_rotate", buyRotate).putString("buy_mode", buyMode)
                .putString("buy_offset", fmt(buyOffset)).putString("buy_every", fmt(buyEvery))
                .putBoolean("buy_now", buyNow).apply();
        lastSaved = System.currentTimeMillis();
    }

    public void buyTemplate() {
        steps.clear();
        for (Object[] t : BUY_TEMPLATE) {
            Step s = new Step();
            s.name = (String) t[0];
            s.times = (Integer) t[1];
            s.wait = (Double) t[2];
            steps.add(s);
        }
        saveBuy();
        changed();
    }

    public boolean hasBuySteps() {
        for (Slot sl : buyRotate ? slots : java.util.Collections.singletonList(curSlot()))
            for (Step s : sl.steps) if (s.x != null) return true;
        return false;
    }

    private long buyNextTime() {
        long now = System.currentTimeMillis();
        if ("restock".equals(buyMode)) return (now / RESTOCK_MS + 1) * RESTOCK_MS + (long) (buyOffset * 1000);
        return now + (long) (Math.max(1, buyEvery) * 60000);
    }

    private void buySchedule() {
        if (!buyRunning) return;
        buyNextAt = buyNextTime();
        ensureWatch();
        changed();
    }

    /** 開始自動購買；沒有設定好位置的步驟就回傳 false */
    public boolean buyStart() {
        if (buyRunning) return true;
        if (!hasBuySteps()) return false;
        buyRunning = true;
        buyNextAt = buyNow ? 1 : buyNextTime();   // 1 = 馬上（由看門狗執行）
        ensureWatch();
        changed();
        return true;
    }

    public void buyStop() {
        buyRunning = false;
        if (buyBusy) {
            seqGen++;
            buyBusy = false;
            buyLog = "已中途停止";
        }
        changed();
    }

    public void buyOnce() {
        runSequence(null);
    }

    /** 依序點每個步驟：每步點 times 次（間隔 1 秒），點完等 wait 秒 */
    private void runSequence(final Runnable done) {
        if (buyBusy) return;
        // 自動輪播：存檔1 做完接存檔2、存檔3…；否則只做目前存檔
        final List<Step> list = new ArrayList<>();
        final List<String> owner = new ArrayList<>();
        final List<String> doneNames = new ArrayList<>();
        for (Slot sl : buyRotate ? slots : java.util.Collections.singletonList(curSlot())) {
            boolean any = false;
            for (Step s : sl.steps)
                if (s.x != null) {
                    list.add(s);
                    owner.add(sl.name);
                    any = true;
                }
            if (any) doneNames.add(sl.name);
        }
        if (list.isEmpty()) {
            buyLog = "沒有設定好位置的步驟";
            changed();
            if (done != null) done.run();
            return;
        }
        if (ClickService.inst == null) {
            buyLog = "無障礙服務未開啟";
            changed();
            if (done != null) done.run();
            return;
        }
        buyBusy = true;
        final int gen = ++seqGen;
        changed();
        new Runnable() {
            int si = 0, ti = 0;

            @Override
            public void run() {
                if (gen != seqGen) return;
                if (si >= list.size()) {
                    buyBusy = false;
                    buyRuns++;
                    buyLog = new java.text.SimpleDateFormat("HH:mm:ss", Locale.US).format(new java.util.Date())
                            + " 已執行 " + android.text.TextUtils.join("→", doneNames);
                    changed();
                    if (done != null) done.run();
                    return;
                }
                Step s = list.get(si);
                if (!owner.get(si).equals(curSlotName)) {
                    curSlotName = owner.get(si);
                    changed();
                }
                ClickService cs = ClickService.inst;
                if (cs != null) {
                    if (s.isScroll()) cs.scroll(s.x, s.y, !"up".equals(s.dir), s.amount);
                    else cs.tap(s.x, s.y);
                }
                ti++;
                long delay;
                if (ti < s.times) delay = 1000;
                else {
                    delay = (long) (s.wait * 1000);
                    si++;
                    ti = 0;
                }
                h.postDelayed(this, delay);
            }
        }.run();
    }

    public String buyStatus() {
        if (buyBusy) return "購買中…（" + curSlotName + "）";
        if (!buyRunning) return "已停止" + (buyLog.isEmpty() ? "" : " · " + buyLog);
        long s = Math.max(0, (buyNextAt - System.currentTimeMillis()) / 1000);
        String at = new java.text.SimpleDateFormat("HH:mm:ss", Locale.US).format(new java.util.Date(buyNextAt));
        return "執行中 · 下次 " + at + "（" + (s / 60) + ":" + String.format(Locale.US, "%02d", s % 60) + " 後）· 已買 " + buyRuns + " 輪";
    }

    // ---------- 區網伺服器 ----------
    public synchronized void startServer() {
        Remote.get(this).start();  // 🌍 遠端遙控（不用同一個 Wi-Fi）
        if (server != null) return;
        server = new WebServer(this);
        server.start();
    }

    public String appVersion() {
        try {
            return ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName;
        } catch (Exception ex) {
            return "?";
        }
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
