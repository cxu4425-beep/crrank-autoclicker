package com.crrank.autoharvest;

import android.content.SharedPreferences;
import android.util.Base64;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/**
 * 🌍 遠端遙控（不用同一個 Wi-Fi）：經公共 MQTT 中繼伺服器轉送，全程 AES-256-GCM 加密。
 * 和電腦版 RemoteLink 用同一套格式，手機頁面在 GitHub Pages（remote.html）。
 */
public final class Remote {
    public static final String PAGE = "https://cxu4425-beep.github.io/crrank-autoclicker/remote.html";
    private static final String[][] BROKERS = {{"broker.emqx.io", "8883"}, {"test.mosquitto.org", "8886"}};
    private static Remote inst;

    private final Engine e;
    private final SharedPreferences sp;
    private final SecureRandom rnd = new SecureRandom();
    private final Object wlock = new Object();
    private final Map<String, Long> seen = new HashMap<>();
    public volatile String state = "未啟動";
    public volatile boolean ok;
    public volatile long watchUntil;
    private volatile boolean stopFlag;
    private volatile SSLSocket sock;
    private OutputStream out;
    private Thread th;
    private volatile byte[] pendingFrame;
    private volatile boolean capturing;

    public static synchronized Remote get(Engine e) {
        if (inst == null) inst = new Remote(e);
        return inst;
    }

    private Remote(Engine e) {
        this.e = e;
        sp = e.prefs();
        if (sp.getString("remote_id", "").isEmpty() || sp.getString("remote_key", "").isEmpty()) newKeys();
    }

    public boolean enabled() {
        return sp.getBoolean("remote_on", true);
    }

    public void setEnabled(boolean on) {
        sp.edit().putBoolean("remote_on", on).apply();
        if (on) start();
        else stop();
    }

    public void newKeys() {
        byte[] id = new byte[10], key = new byte[32];
        rnd.nextBytes(id);
        rnd.nextBytes(key);
        StringBuilder h = new StringBuilder();
        for (byte b : id) h.append(String.format("%02x", b & 255));
        sp.edit().putString("remote_id", h.toString())
                .putString("remote_key", Base64.encodeToString(key, Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP)).apply();
    }

    public String url() {
        return PAGE + "#" + sp.getString("remote_id", "") + "." + sp.getString("remote_key", "") + "." + broker();
    }

    private int broker() {
        return Math.abs(sp.getInt("remote_broker", 0)) % BROKERS.length;
    }

    private String topic(String d) {
        return "crrank/v1/" + sp.getString("remote_id", "") + "/" + d;
    }

    // ---------- 加密 ----------
    private byte[] keyBytes() {
        return Base64.decode(sp.getString("remote_key", ""), Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
    }

    private byte[] seal(char kind, byte[] data) throws Exception {
        byte[] n = new byte[12];
        rnd.nextBytes(n);
        Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(keyBytes(), "AES"), new GCMParameterSpec(128, n));
        c.updateAAD("crrank-v1|up".getBytes(StandardCharsets.UTF_8));
        byte[] plain = new byte[data.length + 1];
        plain[0] = (byte) kind;
        System.arraycopy(data, 0, plain, 1, data.length);
        byte[] ct = c.doFinal(plain);
        byte[] r = new byte[12 + ct.length];
        System.arraycopy(n, 0, r, 0, 12);
        System.arraycopy(ct, 0, r, 12, ct.length);
        return r;
    }

    private byte[] open(byte[] p) throws Exception {
        Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.DECRYPT_MODE, new SecretKeySpec(keyBytes(), "AES"), new GCMParameterSpec(128, p, 0, 12));
        c.updateAAD("crrank-v1|down".getBytes(StandardCharsets.UTF_8));
        return c.doFinal(p, 12, p.length - 12);
    }

    // ---------- MQTT（最小、QoS 0） ----------
    private static byte[] str(String s) {
        byte[] b = s.getBytes(StandardCharsets.UTF_8);
        byte[] r = new byte[b.length + 2];
        r[0] = (byte) (b.length >> 8);
        r[1] = (byte) b.length;
        System.arraycopy(b, 0, r, 2, b.length);
        return r;
    }

    private void packet(int h, byte[]... parts) throws Exception {
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        for (byte[] p : parts) body.write(p);
        ByteArrayOutputStream pk = new ByteArrayOutputStream();
        pk.write(h);
        int n = body.size();
        do {
            int b = n % 128;
            n /= 128;
            pk.write(n > 0 ? b | 128 : b);
        } while (n > 0);
        body.writeTo(pk);
        synchronized (wlock) {
            out.write(pk.toByteArray());
            out.flush();
        }
    }

    private void publish(String topic, byte[] payload) throws Exception {
        packet(0x30, str(topic), payload);
    }

    private static byte[] readN(InputStream in, int n) throws Exception {
        byte[] b = new byte[n];
        int off = 0;
        while (off < n) {
            int r = in.read(b, off, n - off);
            if (r < 0) throw new java.io.EOFException();
            off += r;
        }
        return b;
    }

    // ---------- 執行 ----------
    public synchronized void start() {
        if (!enabled() || (th != null && th.isAlive())) return;
        stopFlag = false;
        th = new Thread(this::run, "crrank-remote");
        th.setDaemon(true);
        th.start();
    }

    public synchronized void stop() {
        stopFlag = true;
        ok = false;
        state = "已關閉";
        closeSock();
    }

    public void restart() {
        stop();
        new Thread(() -> {
            try {
                if (th != null) th.join(3000);
            } catch (InterruptedException ignored) {
            }
            start();
        }).start();
    }

    private void closeSock() {
        try {
            if (sock != null) sock.close();
        } catch (Exception ignored) {
        }
    }

    private void run() {
        long wait = 3000;
        while (!stopFlag) {
            String host = BROKERS[broker()][0];
            int port = Integer.parseInt(BROKERS[broker()][1]);
            state = "連線到 " + host + " 中…";
            ok = false;
            try {
                SSLSocket s = (SSLSocket) SSLSocketFactory.getDefault().createSocket(host, port);
                s.setSoTimeout(15000);
                s.startHandshake();
                sock = s;
                out = s.getOutputStream();
                final InputStream in = s.getInputStream();
                byte[] cid = new byte[6];
                rnd.nextBytes(cid);
                packet(0x10, str("MQTT"), new byte[]{4, 2, 0, 30}, str("crrank-and-" + Base64.encodeToString(cid, Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP)));
                int h = in.read();
                byte[] ack = readN(in, in.read());
                if (h >> 4 != 2 || ack.length < 2 || ack[1] != 0) throw new Exception("中繼伺服器拒絕連線");
                s.setSoTimeout(60000);
                packet(0x82, new byte[]{0, 1}, str(topic("down")), new byte[]{0});
                ok = true;
                state = "已連線（" + host + "）";
                wait = 3000;
                Thread reader = new Thread(() -> readLoop(in), "crrank-remote-rx");
                reader.setDaemon(true);
                reader.start();
                sendLoop();
            } catch (Exception ex) {
                state = "連線失敗，" + (wait / 1000) + " 秒後重試（" + ex.getClass().getSimpleName() + "）";
            }
            ok = false;
            closeSock();
            e.changed();
            if (stopFlag) break;
            try {
                Thread.sleep(wait);
            } catch (InterruptedException ignored) {
            }
            wait = Math.min(60000, wait * 2);
        }
    }

    private void readLoop(InputStream in) {
        try {
            while (!stopFlag) {
                int h = in.read();
                if (h < 0) break;
                int mul = 1, n = 0, b;
                do {
                    b = in.read();
                    if (b < 0) throw new java.io.EOFException();
                    n += (b & 127) * mul;
                    mul *= 128;
                } while ((b & 128) != 0);
                byte[] body = readN(in, n);
                if (h >> 4 == 3) {
                    int tl = ((body[0] & 255) << 8) | (body[1] & 255);
                    int off = 2 + tl + (((h >> 1) & 3) != 0 ? 2 : 0);
                    byte[] payload = new byte[body.length - off];
                    System.arraycopy(body, off, payload, 0, payload.length);
                    onMessage(payload);
                }
            }
        } catch (Exception ignored) {
        }
        closeSock();
    }

    private void sendLoop() throws Exception {
        long lastStatus = 0, lastFrame = 0, lastPing = System.currentTimeMillis();
        while (!stopFlag && sock != null && !sock.isClosed()) {
            long now = System.currentTimeMillis();
            boolean watching = now < watchUntil;
            if (now - lastStatus >= (watching ? 1000 : 20000)) {
                lastStatus = now;
                publish(topic("up"), seal('S', statusJson().getBytes(StandardCharsets.UTF_8)));
            }
            byte[] f = pendingFrame;
            if (f != null) {
                pendingFrame = null;
                publish(topic("up"), seal('F', f));
            }
            if (watching && !capturing && now - lastFrame >= 2000) {
                lastFrame = now;
                requestFrame();
            }
            if (now - lastPing > 18000) {
                lastPing = now;
                synchronized (wlock) {
                    out.write(new byte[]{(byte) 0xC0, 0});
                    out.flush();
                }
            }
            Thread.sleep(250);
        }
    }

    /** 用無障礙服務截圖（Android 11 以上），畫上紅圈＝會點的位置 */
    private void requestFrame() {
        ClickService s = ClickService.inst;
        if (s == null || android.os.Build.VERSION.SDK_INT < 30) return;
        capturing = true;
        e.h.post(() -> s.captureJpeg(e.x, e.y, jpg -> {
            capturing = false;
            if (jpg != null) pendingFrame = jpg;
        }));
    }

    private String statusJson() {
        try {
            JSONObject o = new JSONObject();
            o.put("running", e.running).put("count", e.count).put("next_in", e.nextIn())
                    .put("interval", Engine.fmt(e.interval)).put("unit", e.unit).put("x", e.x).put("y", e.y)
                    .put("ver", e.appVersion()).put("auto_rate", e.autoRate).put("smart", e.smartUsed)
                    .put("buy", e.buyRunning).put("buy_text", e.buyStatus()).put("ts", System.currentTimeMillis())
                    .put("android", true).put("name", android.os.Build.MODEL);
            GameReader.Rates r = e.lastRates;
            String rate;
            if (!e.autoRate) rate = "自動判斷已關閉";
            else if (r != null && e.lastReadOk)
                rate = r.describe() + " → 約 " + GameReader.minutes(r.smartSec()) + " 分鐘後快滿";
            else rate = "還沒讀到遊戲（遊戲要在手機畫面上）";
            o.put("rate", rate);
            if (android.os.Build.VERSION.SDK_INT < 30) o.put("no_frame", "Android 11 以上才能傳畫面");
            return o.toString();
        } catch (Exception ex) {
            return "{}";
        }
    }

    private void onMessage(byte[] payload) {
        if (payload.length < 29) return;
        JSONObject c;
        try {
            byte[] d = open(payload);
            if (d.length < 2 || d[0] != 'C') return;
            c = new JSONObject(new String(d, 1, d.length - 1, StandardCharsets.UTF_8));
        } catch (Exception ex) {
            return;  // 不是用這把金鑰加密的 → 忽略
        }
        long now = System.currentTimeMillis();
        String nonce = c.optString("n", "");
        long ts = c.optLong("ts", 0);
        synchronized (seen) {
            if (nonce.isEmpty() || Math.abs(now - ts) > 300000 || seen.containsKey(nonce)) return;  // 擋掉重播的舊指令
            for (Iterator<Map.Entry<String, Long>> it = seen.entrySet().iterator(); it.hasNext(); )
                if (now - it.next().getValue() > 600000) it.remove();
            seen.put(nonce, now);
        }
        final String cmd = c.optString("cmd", "");
        final JSONObject cc = c;
        if ("watch".equals(cmd)) {
            watchUntil = now + 20000;
            return;
        }
        e.h.post(() -> {
            switch (cmd) {
                case "start":
                    e.start();
                    break;
                case "stop":
                    e.stop();
                    break;
                case "once":
                    e.once();
                    break;
                case "set":
                    double v = cc.optDouble("interval", -1);
                    if (v > 0) e.setInterval(v, cc.optString("unit", "秒"));
                    break;
                case "auto_rate":
                    e.autoRate = cc.optBoolean("on", true);
                    e.save();
                    e.changed();
                    break;
                case "read":
                    e.readGame(false);
                    break;
                case "buy":
                    if (e.buyRunning) e.buyStop();
                    else e.buyStart();
                    break;
            }
        });
    }
}
