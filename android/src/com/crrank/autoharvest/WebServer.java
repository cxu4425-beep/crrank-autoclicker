package com.crrank.autoharvest;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/** 和電腦版相同的區網伺服器：/、/crrank.user.js、/api/status|start|stop|once|set */
public final class WebServer extends Thread {
    private final Engine e;
    private ServerSocket ss;
    public int port;

    WebServer(Engine e) {
        this.e = e;
        setDaemon(true);
        for (int p = 8765; p < 8785; p++) {
            try {
                ss = new ServerSocket(p);
                port = p;
                break;
            } catch (Exception ignored) {
            }
        }
    }

    @Override
    public void run() {
        if (ss == null) return;
        while (true) {
            try {
                final Socket s = ss.accept();
                new Thread(() -> handle(s)).start();
            } catch (Exception ex) {
                return;
            }
        }
    }

    private void handle(Socket so) {
        try (Socket s = so) {
            s.setSoTimeout(8000);
            BufferedReader r = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
            String line = r.readLine();
            if (line == null) return;
            String l;
            while ((l = r.readLine()) != null && !l.isEmpty()) { /* 略過標頭 */ }
            String[] parts = line.split(" ");
            String target = parts.length > 1 ? parts[1] : "/";
            String path = target, query = "";
            int qi = target.indexOf('?');
            if (qi >= 0) {
                path = target.substring(0, qi);
                query = target.substring(qi + 1);
            }
            Map<String, String> qs = parseQuery(query);
            OutputStream out = s.getOutputStream();

            if (path.equals("/crrank.user.js")) {
                send(out, 200, "application/javascript; charset=utf-8", Res.userscript(e.ctx));
                return;
            }
            if (!e.token.equals(qs.get("t"))) {
                send(out, 403, "text/plain; charset=utf-8", "需要正確的連結（請重新掃描手機 App 上的 QR Code）");
                return;
            }
            if (path.equals("/")) {
                send(out, 200, "text/html; charset=utf-8", Res.phoneHtml(e.ctx, e.token, true));
                return;
            }
            if (path.startsWith("/api/")) {
                String cmd = path.substring(5);
                switch (cmd) {
                    case "start": e.h.post(e::start); break;
                    case "stop": e.h.post(e::stop); break;
                    case "once": e.h.post(e::once); break;
                    case "set":
                        try {
                            final double v = Double.parseDouble(qs.get("interval"));
                            final String u = qs.containsKey("unit") ? qs.get("unit") : "秒";
                            if (v > 0) e.h.post(() -> e.setInterval(v, u));
                        } catch (Exception ignored) {
                        }
                        break;
                    default: break;
                }
                Thread.sleep(150);
                send(out, 200, "application/json", e.statusJson());
                return;
            }
            send(out, 404, "text/plain", "not found");
        } catch (Exception ignored) {
        }
    }

    private static Map<String, String> parseQuery(String q) {
        Map<String, String> m = new HashMap<>();
        if (q.isEmpty()) return m;
        for (String kv : q.split("&")) {
            int i = kv.indexOf('=');
            try {
                String k = URLDecoder.decode(i >= 0 ? kv.substring(0, i) : kv, "UTF-8");
                String v = i >= 0 ? URLDecoder.decode(kv.substring(i + 1), "UTF-8") : "";
                m.put(k, v);
            } catch (Exception ignored) {
            }
        }
        return m;
    }

    private static void send(OutputStream out, int code, String type, String body) throws Exception {
        byte[] b = body.getBytes(StandardCharsets.UTF_8);
        String head = "HTTP/1.1 " + code + (code == 200 ? " OK" : code == 403 ? " Forbidden" : " Not Found") + "\r\n"
                + "Content-Type: " + type + "\r\nContent-Length: " + b.length
                + "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
        out.write(head.getBytes(StandardCharsets.UTF_8));
        out.write(b);
        out.flush();
    }
}
