package com.crrank.autoharvest;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/** 共用資源：網頁腳本、書籤碼、使用者腳本、手機頁、匯出檔案（與電腦版相同內容） */
public final class Res {
    private static final String SAFE = "()';,/=+:!*.-_~[]{}?&<>|@$^`\"";
    private static String jsCache, htmlCache;

    public static synchronized String asset(Context c, String name) {
        try (InputStream in = c.getAssets().open(name)) {
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            return new String(bo.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return "";
        }
    }

    public static String js(Context c) {
        if (jsCache == null) jsCache = asset(c, "harvest.js");
        return jsCache;
    }

    public static String minify(String js) {
        StringBuilder sb = new StringBuilder();
        for (String line : js.trim().split("\n")) sb.append(line.trim());
        return sb.toString();
    }

    public static String bookmarklet(Context c) {
        byte[] b = minify(js(c)).getBytes(StandardCharsets.UTF_8);
        StringBuilder sb = new StringBuilder("javascript:");
        for (byte x : b) {
            int v = x & 0xFF;
            char ch = (char) v;
            if (v < 128 && (Character.isLetterOrDigit(ch) || SAFE.indexOf(ch) >= 0)) sb.append(ch);
            else sb.append('%').append(String.format("%02X", v));
        }
        return sb.toString();
    }

    public static String userscript(Context c) {
        return "// ==UserScript==\n// @name         CR Rank 自動收成\n// @namespace    crrank-auto-harvest\n"
                + "// @version      1.0\n// @description  定時點擊知識領土的「收成」按鈕，可自訂間隔與位置\n"
                + "// @match        https://crrank.xpgs25.com/*\n// @grant        none\n// @run-at       document-idle\n"
                + "// ==/UserScript==\n" + js(c).trim() + "\n";
    }

    public static String phoneHtml(Context c, String token, boolean served) {
        if (htmlCache == null) htmlCache = asset(c, "phone.html");
        String bm = bookmarklet(c).replace("&", "&amp;").replace("<", "&lt;");
        String h = htmlCache.replace("__BM__", bm).replace("__TOKEN__", token);
        if (!served) h = h.replace("href=\"/crrank.user.js\"", "href=\"crrank-auto-harvest.user.js\"");
        return h;
    }

    /** 匯出到「下載/crrank_手機檔案」，回傳顯示用路徑 */
    public static String export(Context c) throws Exception {
        String dir = "crrank_手機檔案";
        String where = write(c, dir, "crrank-auto-harvest.user.js", "application/octet-stream", userscript(c));
        write(c, dir, "書籤碼.txt", "text/plain", bookmarklet(c));
        write(c, dir, "手機使用說明.html", "text/html", phoneHtml(c, "", false));
        return where;
    }

    private static String write(Context c, String dir, String name, String mime, String text) throws Exception {
        byte[] data = text.getBytes(StandardCharsets.UTF_8);
        if (Build.VERSION.SDK_INT >= 29) {
            ContentResolver cr = c.getContentResolver();
            String rel = Environment.DIRECTORY_DOWNLOADS + "/" + dir;
            // 先刪掉同名舊檔，避免變成「(1)」
            try {
                cr.delete(MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                        MediaStore.MediaColumns.DISPLAY_NAME + "=? AND " + MediaStore.MediaColumns.RELATIVE_PATH + "=?",
                        new String[]{name, rel + "/"});
            } catch (Exception ignored) {
            }
            ContentValues cv = new ContentValues();
            cv.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
            cv.put(MediaStore.MediaColumns.MIME_TYPE, mime);
            cv.put(MediaStore.MediaColumns.RELATIVE_PATH, rel);
            Uri uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
            if (uri == null) throw new Exception("無法建立檔案");
            try (OutputStream os = cr.openOutputStream(uri)) {
                os.write(data);
            }
            return "下載/" + dir;
        }
        File d = new File(c.getExternalFilesDir(null), dir);
        d.mkdirs();
        try (FileOutputStream fo = new FileOutputStream(new File(d, name))) {
            fo.write(data);
        }
        return d.getAbsolutePath();
    }
}
