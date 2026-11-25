package com.crrank.autoharvest;

import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 自動判斷每小時產量：讀畫面上知識領土的文字（「+5014/時」「收成 +86/60」），算出快滿前什麼時候收。 */
public final class GameReader {
    public static final class Rates {
        public double goldRate = -1, matRate = -1, goldCap = 2000, matCap = 1500, pendGold, pendMat;
        public boolean hasPending;
        public long at = System.currentTimeMillis();

        /** 離「金幣或建材快滿（90%）」還有幾秒；最少 1 分鐘、最多 6 小時。 */
        public double smartSec() {
            double best = Double.MAX_VALUE;
            if (goldRate > 0) best = Math.min(best, (goldCap * 0.9 - pendGold) / goldRate);
            if (matRate > 0) best = Math.min(best, (matCap * 0.9 - pendMat) / matRate);
            if (best == Double.MAX_VALUE) return -1;
            return Math.max(60, Math.min(6 * 3600, best * 3600));
        }

        public String describe() {
            StringBuilder sb = new StringBuilder();
            if (goldRate >= 0) sb.append("金幣 +").append((long) goldRate).append("/時");
            if (matRate >= 0) sb.append(sb.length() > 0 ? "、" : "").append("建材 +").append((long) matRate).append("/時");
            if (hasPending) sb.append("，未收 ").append((long) pendGold).append("/").append((long) pendMat);
            return sb.toString();
        }
    }

    private static final String N = "([\\d,.]+[kKmM萬]?)";
    private static final Pattern RATE_TITLE = Pattern.compile("(金幣|建材)・每小時產出\\s*" + N + "(?:.*?累積到\\s*" + N + ")?");
    private static final Pattern RATE_TEXT = Pattern.compile("\\+\\s*" + N + "\\s*/\\s*時");
    private static final Pattern PENDING = Pattern.compile("收成\\s*\\+\\s*" + N + "\\s*/\\s*" + N);

    static double num(String t) {
        t = t.replace(",", "").trim();
        double mul = 1;
        if (t.endsWith("k") || t.endsWith("K")) mul = 1e3;
        else if (t.endsWith("m") || t.endsWith("M")) mul = 1e6;
        else if (t.endsWith("萬")) mul = 1e4;
        if (mul != 1) t = t.substring(0, t.length() - 1);
        try {
            return Double.parseDouble(t) * mul;
        } catch (Exception ex) {
            return -1;
        }
    }

    /** 從畫面文字（照畫面順序）找出產量、上限、還沒收成的數量；找不到回傳 null。 */
    public static Rates parse(List<String> texts) {
        Rates r = new Rates();
        StringBuilder all = new StringBuilder();
        for (String t : texts) {
            all.append(t).append('\n');
            Matcher m = RATE_TITLE.matcher(t);
            if (m.find()) {
                boolean gold = "金幣".equals(m.group(1));
                double rate = num(m.group(2));
                if (gold && r.goldRate < 0) {
                    r.goldRate = rate;
                    if (m.group(3) != null) r.goldCap = num(m.group(3));
                } else if (!gold && r.matRate < 0) {
                    r.matRate = rate;
                    if (m.group(3) != null) r.matCap = num(m.group(3));
                }
            }
        }
        String s = all.toString();
        if (r.goldRate < 0 && r.matRate < 0) {
            // 沒有提示文字時，用資源列上的「+5014/時」（第一個是金幣、第二個是建材）
            Matcher m = RATE_TEXT.matcher(s);
            List<Double> v = new ArrayList<>();
            while (m.find() && v.size() < 2) v.add(num(m.group(1)));
            if (v.size() >= 1) r.goldRate = v.get(0);
            if (v.size() >= 2) r.matRate = v.get(1);
        }
        if (r.goldRate < 0 && r.matRate < 0) return null;
        Matcher p = PENDING.matcher(s);
        if (p.find()) {
            r.pendGold = Math.max(0, num(p.group(1)));
            r.pendMat = Math.max(0, num(p.group(2)));
            r.hasPending = true;
        }
        return r;
    }

    /** 讀目前畫面上所有視窗的文字（需要無障礙服務的「讀取視窗內容」）。 */
    public static Rates read(android.accessibilityservice.AccessibilityService s) {
        List<AccessibilityNodeInfo> roots = new ArrayList<>();
        try {
            for (AccessibilityWindowInfo w : s.getWindows()) {
                if (w.getType() != AccessibilityWindowInfo.TYPE_APPLICATION) continue;
                AccessibilityNodeInfo n = w.getRoot();
                if (n != null) roots.add(n);
            }
        } catch (Exception ignored) {
        }
        if (roots.isEmpty()) {
            AccessibilityNodeInfo n = s.getRootInActiveWindow();
            if (n != null) roots.add(n);
        }
        for (AccessibilityNodeInfo root : roots) {
            List<String> texts = new ArrayList<>();
            ArrayDeque<AccessibilityNodeInfo> stack = new ArrayDeque<>();
            stack.push(root);
            int seen = 0;
            while (!stack.isEmpty() && seen < 5000) {
                AccessibilityNodeInfo n = stack.pop();
                seen++;
                add(texts, n.getText());
                add(texts, n.getContentDescription());
                if (android.os.Build.VERSION.SDK_INT >= 26) add(texts, n.getHintText());
                if (android.os.Build.VERSION.SDK_INT >= 28) add(texts, n.getTooltipText());
                for (int i = n.getChildCount() - 1; i >= 0; i--) {  // 反著推進去，取出時就是畫面順序
                    AccessibilityNodeInfo c = n.getChild(i);
                    if (c != null) stack.push(c);
                }
            }
            Rates r = parse(texts);
            if (r != null) return r;
        }
        return null;
    }

    private static void add(List<String> out, CharSequence cs) {
        if (cs != null && cs.length() > 0) out.add(cs.toString());
    }

    public static String minutes(double sec) {
        return String.format(Locale.US, "%d", Math.max(1, Math.round(sec / 60)));
    }
}
