package com.crrank.autoharvest;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private Engine e;
    private EditText ex, ey, eiv, ejit, elim;
    private Spinner sun;
    private CheckBox cnow, cbub;
    private Button go;
    private TextView status, acc, urlTxt;
    private ImageView qr;
    private View accBox;
    private ScrollView[] tabs;
    private Button[] tabBtns;
    private String lastUrl = "", seenPos = "", seenIv = "", stepsSig = "";
    private final Runnable listener = this::refresh;
    private final Runnable ticker = new Runnable() {
        @Override
        public void run() {
            refresh();
            e.h.postDelayed(this, 500);
        }
    };

    private int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    // ---------- 外觀 ----------
    static final int C_BG = 0xFFF4F1EA, C_CARD = 0xFFFFFFFF, C_INK = 0xFF1E2230, C_MUTED = 0xFF6B7080, C_LINE = 0xFFE4DFD3,
            C_SOFT = 0xFFF1EDE3, C_YEL = 0xFFFFC93C, C_SKY = 0xFF8FD3FF, C_RED = 0xFFFF6B6B, C_HEAD = 0xFF1E2230;

    private GradientDrawable round(int color, float radiusDp, int stroke) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(dp(radiusDp));
        if (stroke != 0) g.setStroke(dp(1), stroke);
        return g;
    }

    /** 分隔用的標記：在 CardPage 裡代表「開始新的一張卡片」 */
    private static final class CardBreak extends View {
        CardBreak(android.content.Context c) {
            super(c);
        }
    }

    /** 自動把內容分成一張一張白色卡片的頁面 */
    private final class CardPage extends LinearLayout {
        private LinearLayout cur;
        private boolean internal;

        CardPage() {
            super(MainActivity.this);
            setOrientation(VERTICAL);
            setPadding(dp(14), dp(12), dp(14), dp(28));
        }

        private void newCard() {
            cur = new LinearLayout(getContext());
            cur.setOrientation(VERTICAL);
            cur.setPadding(dp(16), dp(12), dp(16), dp(14));
            cur.setBackground(round(C_CARD, 18, C_LINE));
            if (android.os.Build.VERSION.SDK_INT >= 21) cur.setElevation(dp(1.5f));
            LayoutParams lp = new LayoutParams(-1, -2);
            lp.setMargins(0, dp(6), 0, dp(6));
            internal = true;
            super.addView(cur, -1, lp);
            internal = false;
        }

        @Override
        public void addView(View child, int index, ViewGroup.LayoutParams params) {
            if (internal) {
                super.addView(child, index, params);
                return;
            }
            if (child instanceof CardBreak) {
                cur = null;
                return;
            }
            if (cur == null) newCard();
            cur.addView(child, params);
        }
    }

    private TextView label(String s, float size, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(size);
        t.setTextColor(C_INK);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        if (bold && size >= 16) t.setTextSize(17);
        t.setPadding(0, dp(4), 0, dp(4));
        t.setLineSpacing(0, 1.1f);
        return t;
    }

    private TextView hint(String s) {
        TextView t = label(s, 13, false);
        t.setTextColor(C_MUTED);
        return t;
    }

    private EditText num(boolean decimal) {
        EditText t = new EditText(this);
        t.setInputType(InputType.TYPE_CLASS_NUMBER | (decimal ? InputType.TYPE_NUMBER_FLAG_DECIMAL : 0));
        t.setSelectAllOnFocus(true);
        t.setMinWidth(dp(90));
        t.setTextColor(C_INK);
        t.setBackground(round(0xFFFFFFFF, 10, C_LINE));
        t.setPadding(dp(12), dp(8), dp(12), dp(8));
        return t;
    }

    private Button btn(String s, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setOnClickListener(l);
        b.setTextColor(C_INK);
        b.setTextSize(15);
        if (android.os.Build.VERSION.SDK_INT >= 21) b.setStateListAnimator(null);
        b.setMinHeight(dp(46));
        b.setPadding(dp(14), dp(8), dp(14), dp(8));
        paint(b, C_SOFT);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.setMargins(dp(2), dp(4), dp(2), dp(4));
        b.setLayoutParams(lp);
        return b;
    }

    /** 換按鈕顏色（保留按下去的波紋） */
    private void paint(Button b, int color) {
        b.setBackground(new android.graphics.drawable.RippleDrawable(
                android.content.res.ColorStateList.valueOf(0x33000000), round(color, 14, 0), null));
    }

    private Button primary(String s, int color, View.OnClickListener l) {
        Button b = btn(s, l);
        b.setTextSize(18);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setMinHeight(dp(58));
        paint(b, color);
        return b;
    }

    private CheckBox check(String text) {
        CheckBox c = new CheckBox(this);
        c.setText(text);
        c.setTextColor(C_INK);
        c.setTextSize(15);
        if (android.os.Build.VERSION.SDK_INT >= 21)
            c.setButtonTintList(android.content.res.ColorStateList.valueOf(0xFFE0A800));
        c.setPadding(dp(4), dp(6), 0, dp(6));
        return c;
    }

    private LinearLayout row(View... vs) {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        for (View v : vs) {
            if (v instanceof Button) v.setLayoutParams(new LinearLayout.LayoutParams(-2, -2));
            r.addView(v);
        }
        return r;
    }

    private LinearLayout row2(View a, View b) {
        LinearLayout r = row();
        LinearLayout.LayoutParams p1 = new LinearLayout.LayoutParams(0, -2, 1);
        p1.setMargins(0, dp(4), dp(4), dp(4));
        LinearLayout.LayoutParams p2 = new LinearLayout.LayoutParams(0, -2, 1);
        p2.setMargins(dp(4), dp(4), 0, dp(4));
        r.addView(a, p1);
        r.addView(b, p2);
        return r;
    }

    private LinearLayout page() {
        return new CardPage();
    }

    private View sep() {
        return new CardBreak(this);
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        e = Engine.get(this);
        e.startServer();

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(C_BG);
        if (android.os.Build.VERSION.SDK_INT >= 21) getWindow().setStatusBarColor(C_HEAD);

        // 頂部標題列
        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.VERTICAL);
        head.setBackgroundColor(C_HEAD);
        head.setPadding(dp(18), dp(14), dp(18), dp(12));
        TextView title = new TextView(this);
        title.setText("🌾 CR Rank 自動收成");
        title.setTextColor(Color.WHITE);
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        TextView sub = new TextView(this);
        sub.setText("v" + appVersion() + " · 知識領土小幫手");
        sub.setTextColor(0xFFA7ADBF);
        sub.setTextSize(12);
        head.addView(title);
        head.addView(sub);
        root.addView(head);

        // 膠囊式分頁列
        android.widget.HorizontalScrollView hs = new android.widget.HorizontalScrollView(this);
        hs.setHorizontalScrollBarEnabled(false);
        hs.setBackgroundColor(C_HEAD);
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setPadding(dp(12), 0, dp(12), dp(12));
        String[] names = {"🖱 定點連點", "🛒 自動購買", "📱 手機/遙控", "🎮 內建遊戲"};
        tabBtns = new Button[names.length];
        for (int i = 0; i < names.length; i++) {
            final int k = i;
            Button t = btn(names[i], v -> showTab(k));
            t.setTextSize(14);
            t.setMinHeight(dp(38));
            t.setMinimumHeight(dp(38));
            t.setPadding(dp(14), dp(4), dp(14), dp(4));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, dp(38));
            lp.setMargins(dp(3), 0, dp(3), 0);
            bar.addView(t, lp);
            tabBtns[i] = t;
        }
        hs.addView(bar);
        root.addView(hs);

        FrameLayout content = new FrameLayout(this);
        tabs = new ScrollView[]{new ScrollView(this), new ScrollView(this), new ScrollView(this), new ScrollView(this)};
        tabs[0].addView(buildClickTab());
        tabs[1].addView(buildBuyTab());
        tabs[2].addView(buildPhoneTab());
        tabs[3].addView(buildGameTab());
        for (ScrollView s : tabs) content.addView(s, new FrameLayout.LayoutParams(-1, -1));
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        int tab = e.prefs().getInt("tab", 0);
        showTab(tab >= 0 && tab < tabs.length ? tab : 0);
        if (android.os.Build.VERSION.SDK_INT >= 33
                && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != android.content.pm.PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 7);
        if (e.prefs().getBoolean("auto_update", true)) checkUpdate(false);
    }

    // ---------- ⑤ 自動更新：檢查 GitHub 最新版本 ----------
    private static final String REPO = "cxu4425-beep/crrank-autoclicker";

    private String appVersion() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception ex) {
            return "0";
        }
    }

    private static int[] ver(String v) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\d+").matcher(v == null ? "" : v);
        int[] r = new int[3];
        for (int i = 0; i < 3 && m.find(); i++) r[i] = Integer.parseInt(m.group());
        return r;
    }

    private static boolean newer(String a, String b) {
        int[] x = ver(a), y = ver(b);
        for (int i = 0; i < 3; i++) if (x[i] != y[i]) return x[i] > y[i];
        return false;
    }

    private void checkUpdate(final boolean manual) {
        new Thread(() -> {
            try {
                java.net.HttpURLConnection con = (java.net.HttpURLConnection)
                        new java.net.URL("https://api.github.com/repos/" + REPO + "/releases/latest").openConnection();
                con.setRequestProperty("User-Agent", "CRRank-AutoHarvest");
                con.setRequestProperty("Accept", "application/vnd.github+json");
                con.setConnectTimeout(10000);
                con.setReadTimeout(10000);
                java.io.InputStream in = con.getInputStream();
                java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
                in.close();
                org.json.JSONObject o = new org.json.JSONObject(new String(bo.toByteArray(), "UTF-8"));
                final String tag = o.optString("tag_name");
                final String body = o.optString("body");
                String apk = o.optString("html_url");
                org.json.JSONArray as = o.optJSONArray("assets");
                if (as != null) for (int i = 0; i < as.length(); i++)
                    if ("CRRank-AutoHarvest.apk".equals(as.getJSONObject(i).optString("name")))
                        apk = as.getJSONObject(i).optString("browser_download_url");
                final String url = apk;
                final String cur = appVersion();
                runOnUiThread(() -> {
                    if (isFinishing()) return;
                    if (!newer(tag, cur)) {
                        if (manual) Toast.makeText(this, "已經是最新版（v" + cur + "）", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    if (!manual && tag.equals(e.prefs().getString("skip_ver", ""))) return;
                    String notes = body.length() > 600 ? body.substring(0, 600) + "…" : body;
                    new AlertDialog.Builder(this).setTitle("有新版本 " + tag + "（目前 v" + cur + "）")
                            .setMessage(notes + "\n\n按「下載」後安裝新的 APK，會直接覆蓋舊版、設定會保留。")
                            .setPositiveButton("下載", (d, w) -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))))
                            .setNeutralButton("略過這版", (d, w) -> e.prefs().edit().putString("skip_ver", tag).apply())
                            .setNegativeButton("以後再說", null).show();
                });
            } catch (Exception ex) {
                if (manual) runOnUiThread(() -> Toast.makeText(this, "檢查更新失敗：" + ex.getMessage(), Toast.LENGTH_LONG).show());
            }
        }).start();
    }

    // ---------- ① 依產量算收成間隔 ----------
    private void calcInterval() {
        LinearLayout l = page();
        l.addView(hint("在遊戲裡點一下上方的金幣、建材，會看到「每小時產出 ___」。沒收成的產出最多累積金幣 2000、建材 1500，滿了就停產；這裡會算出快滿（90%）之前收一次的間隔。"));
        EditText g = num(true);
        EditText m = num(true);
        g.setText(e.prefs().getString("rate_gold", ""));
        m.setText(e.prefs().getString("rate_mat", ""));
        l.addView(row(label("金幣 每小時產出  ", 14, false), g));
        l.addView(row(label("建材 每小時產出  ", 14, false), m));
        new AlertDialog.Builder(this).setTitle("依產量算收成間隔").setView(l)
                .setPositiveButton("套用到間隔", (d, w) -> {
                    double gr = 0, mr = 0;
                    try {
                        gr = Double.parseDouble(g.getText().toString().trim());
                    } catch (Exception ignored) {
                    }
                    try {
                        mr = Double.parseDouble(m.getText().toString().trim());
                    } catch (Exception ignored) {
                    }
                    double hours = Double.MAX_VALUE;
                    if (gr > 0) hours = Math.min(hours, 2000 * 0.9 / gr);
                    if (mr > 0) hours = Math.min(hours, 1500 * 0.9 / mr);
                    if (hours == Double.MAX_VALUE) {
                        Toast.makeText(this, "至少要填一個大於 0 的產量", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    int mins = Math.max(1, (int) (hours * 60));
                    e.prefs().edit().putString("rate_gold", g.getText().toString().trim())
                            .putString("rate_mat", m.getText().toString().trim()).apply();
                    eiv.setText(String.valueOf(mins));
                    sun.setSelection(1); // 分
                    collect(true);
                    Toast.makeText(this, "已設定每 " + mins + " 分鐘收一次", Toast.LENGTH_LONG).show();
                }).setNegativeButton("取消", null).show();
    }

    // ---------- 分頁 2：自動購買（對應電腦版「自動購買」） ----------
    private LinearLayout stepsBox;
    private Spinner slotSp;
    private CheckBox cbrot;
    private TextView savedTxt;
    private long seenSaved;

    private void renderSlots() {
        String[] names = new String[e.slots.size()];
        for (int i = 0; i < names.length; i++)
            names[i] = e.slots.get(i).name + "（" + e.slots.get(i).steps.size() + " 步）";
        slotSp.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, names));
        slotSp.setSelection(e.slot);
    }

    private void renameSlot() {
        EditText n = new EditText(this);
        n.setText(e.curSlot().name);
        new AlertDialog.Builder(this).setTitle("存檔名稱").setView(n).setPositiveButton("儲存", (d, w) -> {
            String s = n.getText().toString().trim();
            if (!s.isEmpty()) {
                e.curSlot().name = s;
                e.saveBuy();
                renderSteps();
            }
        }).setNegativeButton("取消", null).show();
    }
    private EditText eboff, ebevery;
    private android.widget.RadioButton rbRestock, rbEvery;
    private CheckBox cbnow;
    private Button bgo;
    private TextView bstatus;

    private View buildBuyTab() {
        LinearLayout p = page();
        p.addView(label("自動購買（照順序模擬點擊）", 16, true));
        p.addView(hint("按「建立購買範本」→ 先打開遊戲的「物品 → 商店」確認位置 → 按「依序選全部」把每一步點在對應按鈕上。商品在下面看不到時，在「購買」前加一個「滾動步驟」。"));

        slotSp = new Spinner(this);
        slotSp.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> a, View v, int pos, long id) {
                if (pos != e.slot) {
                    e.switchSlot(pos);
                    e.saveBuy();
                    renderSteps();
                }
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> a) {
            }
        });
        LinearLayout sr = row(label("存檔 ", 15, true));
        sr.addView(slotSp, new LinearLayout.LayoutParams(0, -2, 1));
        sr.addView(btn("改名", v -> renameSlot()));
        sr.addView(btn("清空", v -> {
            if (e.steps.isEmpty()) return;
            new AlertDialog.Builder(this).setMessage("確定要清空「" + e.curSlot().name + "」的所有步驟嗎？")
                    .setPositiveButton("清空", (d, w) -> {
                        e.steps.clear();
                        e.saveBuy();
                        renderSteps();
                    }).setNegativeButton("取消", null).show();
        }));
        p.addView(sr);
        cbrot = new CheckBox(this);
        cbrot.setText("自動輪播（做完一個存檔接下一個）");
        cbrot.setOnCheckedChangeListener((v, on) -> {
            if (e.buyRotate != on) {
                e.buyRotate = on;
                e.saveBuy();
            }
        });
        p.addView(cbrot);
        savedTxt = hint("");
        savedTxt.setTextColor(0xFF2A8A2A);
        p.addView(savedTxt);
        stepsBox = new LinearLayout(this);
        stepsBox.setOrientation(LinearLayout.VERTICAL);
        p.addView(stepsBox);
        p.addView(row2(btn("📋 建立購買範本", v -> {
            if (e.steps.isEmpty()) makeTemplate();
            else new AlertDialog.Builder(this).setMessage("要用範本取代目前的步驟嗎？")
                    .setPositiveButton("取代", (d, w) -> makeTemplate()).setNegativeButton("取消", null).show();
        }), btn("➕ 點擊步驟", v -> {
            Engine.Step s = new Engine.Step();
            s.name = "點「購買」";
            s.times = 3;
            e.steps.add(s);
            e.saveBuy();
            renderSteps();
        })));
        p.addView(btn("➕ 滾動步驟（捲動商品清單）", v -> {
            Engine.Step s = new Engine.Step();
            s.name = "滾動商品清單";
            s.type = "scroll";
            s.wait = 0.8;
            e.steps.add(s);
            e.saveBuy();
            renderSteps();
            Toast.makeText(this, "已加在最後，可用 ↑ 移到「購買」前面；位置要選在商品清單上", Toast.LENGTH_LONG).show();
        }));
        p.addView(btn("🎯 依序選全部位置", v -> pickSteps(0, true)));
        p.addView(sep());

        android.widget.RadioGroup rg = new android.widget.RadioGroup(this);
        rbRestock = new android.widget.RadioButton(this);
        rbRestock.setText("每次補貨後（整點、半點）過");
        rbRestock.setId(View.generateViewId());
        rbEvery = new android.widget.RadioButton(this);
        rbEvery.setText("每 N 分鐘");
        rbEvery.setId(View.generateViewId());
        rg.addView(rbRestock);
        rg.addView(rbEvery);
        p.addView(rg);
        eboff = num(true);
        ebevery = num(true);
        p.addView(row(label("補貨後過  ", 15, false), eboff, label(" 秒", 15, false)));
        p.addView(row(label("每  ", 15, false), ebevery, label(" 分鐘", 15, false)));
        cbnow = new CheckBox(this);
        cbnow.setText("按開始時立刻先買一次");
        p.addView(cbnow);
        bgo = primary("▶  開始自動購買", C_SKY, v -> toggleBuy());
        p.addView(bgo);
        p.addView(btn("立即買一次（測試）", v -> {
            if (!collectBuy() || needService()) return;
            Toast.makeText(this, "1.5 秒後開始執行購買步驟", Toast.LENGTH_SHORT).show();
            moveTaskToBack(true);
            e.h.postDelayed(e::buyOnce, 1500);
        }));
        bstatus = label("已停止", 14, false);
        p.addView(bstatus);
        p.addView(hint("浮動控制鈕上的 🛒 也能開始／停止自動購買。開始前「物品」視窗要先關著，遊戲畫面要停在那裡、螢幕保持亮著。"));
        return p;
    }

    private void makeTemplate() {
        e.buyTemplate();
        renderSteps();
        new AlertDialog.Builder(this).setTitle("範本建立好了")
                .setMessage("請先打開遊戲，把「物品 → 商店」開到要買的商品那一頁，再回來按「依序選全部位置」。\n（第一步「打開物品」要點左邊欄的「物品」按鈕）")
                .setPositiveButton("好", null).show();
    }

    private void renderSteps() {
        if (stepsBox == null) return;
        renderSlots();
        stepsBox.removeAllViews();
        if (e.steps.isEmpty()) {
            stepsBox.addView(hint("還沒有步驟。"));
            return;
        }
        for (int i = 0; i < e.steps.size(); i++) {
            final int k = i;
            Engine.Step s = e.steps.get(i);
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setPadding(dp(10), dp(6), dp(10), dp(6));
            GradientDrawable g = new GradientDrawable();
            g.setColor(0xFFF3F4F8);
            g.setCornerRadius(dp(8));
            card.setBackground(g);
            LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1, -2);
            cp.setMargins(0, dp(3), 0, dp(3));
            String pos = s.x == null ? "（未選位置）" : "(" + s.x + ", " + s.y + ")";
            card.addView(label((i + 1) + ". " + s.name + "  " + pos + "\n" + s.action() + " × " + s.times
                    + " 次，做完等 " + Engine.fmt(s.wait) + " 秒", 14, false));
            LinearLayout r = row();
            Button pk = btn("🎯", v -> pickSteps(k, false));
            Button ed = btn("編輯", v -> editStep(k));
            Button up = btn("↑", v -> {
                if (k > 0) {
                    e.steps.add(k - 1, e.steps.remove(k));
                    e.saveBuy();
                    renderSteps();
                }
            });
            Button del = btn("刪除", v -> {
                e.steps.remove(k);
                e.saveBuy();
                renderSteps();
            });
            for (Button b : new Button[]{pk, ed, up, del}) r.addView(b, new LinearLayout.LayoutParams(0, -2, 1));
            card.addView(r);
            stepsBox.addView(card, cp);
        }
    }

    private void editStep(int k) {
        Engine.Step s = e.steps.get(k);
        LinearLayout l = page();
        EditText n = new EditText(this);
        n.setText(s.name);
        EditText t = num(false);
        t.setText(String.valueOf(s.times));
        EditText w = num(true);
        w.setText(Engine.fmt(s.wait));
        l.addView(label("名稱", 14, false));
        l.addView(n);
        Spinner ty = new Spinner(this);
        ty.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{"點擊", "滾動"}));
        ty.setSelection(s.isScroll() ? 1 : 0);
        Spinner dr = new Spinner(this);
        dr.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{"往下", "往上"}));
        dr.setSelection("up".equals(s.dir) ? 1 : 0);
        EditText am = num(false);
        am.setText(String.valueOf(s.amount));
        l.addView(row(label("動作  ", 14, false), ty));
        l.addView(row(label("重複幾次  ", 14, false), t));
        l.addView(row(label("做完等幾秒  ", 14, false), w));
        l.addView(row(label("滾動方向  ", 14, false), dr));
        l.addView(row(label("滾動格數  ", 14, false), am));
        new AlertDialog.Builder(this).setTitle("編輯第 " + (k + 1) + " 步").setView(l)
                .setPositiveButton("儲存", (d, x) -> {
                    try {
                        s.name = n.getText().toString().trim().isEmpty() ? s.name : n.getText().toString().trim();
                        s.times = Math.max(1, (int) Double.parseDouble(t.getText().toString()));
                        s.wait = Math.max(0.1, Double.parseDouble(w.getText().toString()));
                        s.type = ty.getSelectedItemPosition() == 1 ? "scroll" : "click";
                        s.dir = dr.getSelectedItemPosition() == 1 ? "up" : "down";
                        s.amount = Math.max(1, (int) Double.parseDouble(am.getText().toString()));
                    } catch (Exception ex) {
                        Toast.makeText(this, "次數和秒數要是數字", Toast.LENGTH_SHORT).show();
                    }
                    e.saveBuy();
                    renderSteps();
                }).setNegativeButton("取消", null).show();
    }

    /** 選第 k 步的位置；all=true 時選完自動接著選下一步 */
    private void pickSteps(int k, boolean all) {
        if (e.steps.isEmpty()) {
            Toast.makeText(this, "先按「建立購買範本」或「新增步驟」", Toast.LENGTH_SHORT).show();
            return;
        }
        if (needService()) return;
        moveTaskToBack(true);
        e.h.postDelayed(() -> pickNext(k, all), 700);
    }

    private void pickNext(int k, boolean all) {
        ClickService s = ClickService.inst;
        if (s == null || k >= e.steps.size()) {
            if (all && s != null) Toast.makeText(s, "全部位置都選好了！可以按「立即買一次」測試", Toast.LENGTH_LONG).show();
            return;
        }
        Engine.Step st = e.steps.get(k);
        String prompt = (all ? "第 " + (k + 1) + "/" + e.steps.size() + " 步：" : "") + "點「" + st.name + "」的位置";
        s.startPick(prompt, (x, y) -> {
            st.x = x;
            st.y = y;
            e.saveBuy();
            e.changed();
            if (all) e.h.postDelayed(() -> pickNext(k + 1, true), 400);
            else Toast.makeText(s, "第 " + (k + 1) + " 步位置 (" + x + ", " + y + ")", Toast.LENGTH_SHORT).show();
        });
    }

    private void loadBuyFields() {
        rbRestock.setChecked(!"interval".equals(e.buyMode));
        rbEvery.setChecked("interval".equals(e.buyMode));
        eboff.setText(Engine.fmt(e.buyOffset));
        ebevery.setText(Engine.fmt(e.buyEvery));
        cbnow.setChecked(e.buyNow);
        cbrot.setChecked(e.buyRotate);
        renderSteps();
    }

    private boolean collectBuy() {
        try {
            double off = Double.parseDouble(eboff.getText().toString().trim());
            double ev = Double.parseDouble(ebevery.getText().toString().trim());
            if (off < 0 || ev <= 0) throw new NumberFormatException();
            e.buyOffset = off;
            e.buyEvery = ev;
        } catch (Exception ex) {
            Toast.makeText(this, "請輸入正確的秒數／分鐘數", Toast.LENGTH_LONG).show();
            return false;
        }
        e.buyMode = rbEvery.isChecked() ? "interval" : "restock";
        e.buyNow = cbnow.isChecked();
        e.saveBuy();
        return true;
    }

    private void toggleBuy() {
        if (e.buyRunning) {
            e.buyStop();
            return;
        }
        if (!collectBuy() || needService()) return;
        if (!e.hasBuySteps()) {
            Toast.makeText(this, "還沒有設定步驟位置，先按「建立購買範本」", Toast.LENGTH_LONG).show();
            return;
        }
        Toast.makeText(this, "已開始自動購買，請切到遊戲畫面（浮動鈕 🛒 可停止）", Toast.LENGTH_LONG).show();
        moveTaskToBack(true);
        e.h.postDelayed(e::buyStart, 900);
    }

    private void showTab(int k) {
        for (int i = 0; i < tabs.length; i++) {
            tabs[i].setVisibility(i == k ? View.VISIBLE : View.GONE);
            tabBtns[i].setTypeface(i == k ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
            paint(tabBtns[i], i == k ? C_YEL : 0xFF2D3346);
            tabBtns[i].setTextColor(i == k ? C_INK : 0xFFC9CEDC);
        }
        e.prefs().edit().putInt("tab", k).apply();
    }

    // ---------- 分頁 1：定點連點（對應電腦版「電腦連點」） ----------
    private View buildClickTab() {
        LinearLayout p = page();

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(14), dp(10), dp(14), dp(10));
        box.setBackground(round(0xFFFFF4D6, 14, 0));
        acc = label("", 15, true);
        box.addView(acc);
        box.addView(hint("自動點擊需要開啟「無障礙」裡的「" + getString(R.string.service_name) + "」。\n"
                + "Android 13 以上若開關是灰色：到 設定 → 應用程式 → " + getString(R.string.app_name)
                + " → 右上角 ⋮ → 「允許受限制的設定」，再回來開啟。"));
        box.addView(btn("開啟無障礙權限設定", v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))));
        accBox = box;
        p.addView(box);
        p.addView(sep());

        p.addView(label("🎯 點擊位置", 16, true));
        p.addView(hint("遊戲上「收成」按鈕在螢幕上的座標"));
        ex = num(false);
        ey = num(false);
        p.addView(row(label("X  ", 15, false), ex, label("     Y  ", 15, false), ey));
        Button pk = btn("🎯 在螢幕上選位置", v -> pick());
        paint(pk, C_YEL);
        p.addView(row2(pk, btn("測試點一下", v -> testClick())));
        p.addView(hint("也可以在遊戲畫面上按浮動控制鈕的 🎯 選位置"));
        p.addView(sep());

        p.addView(label("🤖 自動判斷每小時產量", 16, true));
        p.addView(hint("每次點完收成會讀遊戲畫面上的「+產量/時」和「收成 +x/y」，算出金幣或建材快滿（90%）前再收。"
                + "產量變了也會跟著變，不用手動輸入。"));
        CheckBox ar = check("自動判斷收成時間");
        ar.setChecked(e.autoRate);
        ar.setOnCheckedChangeListener((v, on) -> {
            e.autoRate = on;
            e.save();
            refresh();
        });
        p.addView(ar);
        rateTxt = hint("");
        rateTxt.setTextColor(0xFF2A8A4A);
        p.addView(rateTxt);
        p.addView(hint("第一次使用（或更新後讀不到）：到無障礙設定把「" + getString(R.string.service_name)
                + "」關掉再打開一次，讓它可以讀取畫面文字。"));
        p.addView(sep());

        p.addView(label("⏱ 間隔與選項", 16, true));
        p.addView(hint("開著自動判斷時，這個間隔只在讀不到遊戲時使用。"));
        eiv = num(true);
        sun = new Spinner(this);
        ArrayAdapter<String> ad = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, Engine.UNITS);
        sun.setAdapter(ad);
        p.addView(row(label("每  ", 15, false), eiv, sun, label("  點一次", 15, false)));
        p.addView(btn("📊 依產量算間隔（快滿前才收）", v -> calcInterval()));
        ejit = num(true);
        p.addView(row(label("隨機誤差 ± 秒  ", 15, false), ejit));
        elim = num(false);
        p.addView(row(label("次數上限 (0=無限)  ", 15, false), elim));
        cnow = check("按開始時立刻先點一次");
        p.addView(cnow);
        cbub = check("顯示浮動控制鈕（▶ 開始停止、🎯 選位置、✕ 關掉）");
        cbub.setOnCheckedChangeListener((v, on) -> {
            e.showBubble = on;
            e.save();
            ClickService s = ClickService.inst;
            if (s != null) {
                if (on) s.showBubble();
                else s.hideBubble();
            }
        });
        p.addView(cbub);
        p.addView(sep());

        p.addView(label("▶ 自動收成", 16, true));
        go = primary("▶  開始自動收成", C_YEL, v -> toggle());
        p.addView(go);
        status = label("已停止", 14, true);
        status.setTextColor(0xFF2F6FDE);
        p.addView(status);
        p.addView(hint("按開始後 App 會退到背景。遊戲畫面要停在那個位置、不要被擋住。"));
        p.addView(btn("🌐 開啟知識領土網站", v -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(Engine.GAME_URL)))));
        p.addView(sep());

        p.addView(label("🌙 息屏也收成", 16, true));
        p.addView(hint("螢幕關掉時系統不讓 App 點螢幕，所以息屏期間改用「背景遊戲」直接點網頁上的收成按鈕；"
                + "解鎖後自動換回定點連點，並馬上補點過期的。需要先在「內建遊戲」分頁登入一次。"));
        CheckBox off = check("息屏時改用背景遊戲繼續收成");
        off.setChecked(e.offHarvest);
        off.setOnCheckedChangeListener((v, on) -> {
            e.offHarvest = on;
            e.save();
        });
        p.addView(off);
        batTxt = hint("");
        p.addView(batTxt);
        p.addView(btn("🔋 允許在背景不受省電限制", v -> askBattery()));
        p.addView(sep());

        p.addView(label("🔄 版本與更新", 16, true));
        CheckBox au = check("開啟時自動檢查更新");
        au.setChecked(e.prefs().getBoolean("auto_update", true));
        au.setOnCheckedChangeListener((v, on) -> e.prefs().edit().putBoolean("auto_update", on).apply());
        p.addView(row(label("目前版本 v" + appVersion() + "    ", 15, true), btn("檢查更新", v -> checkUpdate(true))));
        p.addView(au);
        return p;
    }

    private TextView batTxt, rateTxt;

    private boolean ignoringBattery() {
        try {
            android.os.PowerManager pm = (android.os.PowerManager) getSystemService(POWER_SERVICE);
            return android.os.Build.VERSION.SDK_INT < 23 || pm.isIgnoringBatteryOptimizations(getPackageName());
        } catch (Exception ex) {
            return false;
        }
    }

    /** 關掉電池最佳化：息屏久了手機會進入「打盹」斷網，不關掉的話背景遊戲可能收不到 */
    private void askBattery() {
        if (ignoringBattery()) {
            Toast.makeText(this, "已經允許了 ✅", Toast.LENGTH_SHORT).show();
            return;
        }
        try {
            startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + getPackageName())));
        } catch (Exception ex) {
            startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
        }
    }

    // ---------- 分頁 2：手機 / 遙控（對應電腦版「手機」分頁） ----------
    private ImageView rqr;
    private TextView remoteTxt;
    private String lastRemoteUrl = "";

    private View buildPhoneTab() {
        LinearLayout p = page();
        final Remote rm = Remote.get(e);
        p.addView(label("🖥 遙控電腦", 16, true));
        p.addView(hint("用這支手機遙控電腦（任何網路）。電腦只要加入一次就會記住，之後按下面的按鈕就自動連上，不用每次掃 QR Code。"));
        p.addView(primary("🖥 打開遙控電腦", C_YEL, v -> startActivity(new Intent(this, RemoteActivity.class))));
        p.addView(btn("📋 從剪貼簿加入電腦（貼上電腦版「🔗 複製連結」）", v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            CharSequence t = null;
            try {
                if (cm.hasPrimaryClip() && cm.getPrimaryClip().getItemCount() > 0)
                    t = cm.getPrimaryClip().getItemAt(0).coerceToText(this);
            } catch (Exception ignored) {
            }
            String s = t == null ? "" : t.toString().trim();
            if (!s.contains("remote.html#")) {
                Toast.makeText(this, "剪貼簿裡沒有遠端遙控連結。先在電腦版按「🔗 複製連結」，傳到手機後複製。", Toast.LENGTH_LONG).show();
                return;
            }
            startActivity(new Intent(this, RemoteActivity.class).putExtra("link", s));
        }));
        p.addView(hint("也可以用手機相機掃電腦上的 QR Code，選「用 CR Rank 自動收成開啟」，就會加進來。"));
        p.addView(sep());

        p.addView(label("🌍 遠端遙控這支手機（不用同一個 Wi-Fi）", 16, true));
        p.addView(hint("用另一支手機或電腦掃描，4G／5G 或別的 Wi-Fi 都能遙控，還看得到這支手機的實時畫面（紅圈＝會點的位置，需要 Android 11 以上）。"));
        rqr = new ImageView(this);
        rqr.setScaleType(ImageView.ScaleType.FIT_CENTER);
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(dp(240), dp(240));
        rp.gravity = Gravity.CENTER_HORIZONTAL;
        rp.setMargins(0, dp(8), 0, dp(8));
        p.addView(rqr, rp);
        CheckBox ron = check("允許遠端遙控");
        ron.setChecked(rm.enabled());
        ron.setOnCheckedChangeListener((v, on) -> {
            rm.setEnabled(on);
            lastRemoteUrl = "";
            refresh();
        });
        p.addView(ron);
        CheckBox rclick = check("允許從遠端點擊這支手機的畫面（對方開「👆 點擊模式」）");
        rclick.setChecked(e.prefs().getBoolean("remote_click", true));
        rclick.setOnCheckedChangeListener((v, on) -> e.prefs().edit().putBoolean("remote_click", on).apply());
        p.addView(rclick);
        remoteTxt = label("", 14, true);
        remoteTxt.setTextColor(0xFF2F6FDE);
        p.addView(remoteTxt);
        p.addView(row2(btn("🔗 複製連結", v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("遠端遙控", rm.url()));
            Toast.makeText(this, "已複製。這個連結等於遙控器，只傳給自己的裝置。", Toast.LENGTH_LONG).show();
        }), btn("🔄 換新連結", v -> new AlertDialog.Builder(this).setTitle("換新連結")
                .setMessage("換新連結後，舊的 QR Code／連結就不能用了，要重新掃描。確定嗎？")
                .setPositiveButton("換新", (d, w) -> {
                    rm.newKeys();
                    rm.restart();
                    lastRemoteUrl = "";
                    refresh();
                }).setNegativeButton("取消", null).show())));
        p.addView(hint("🔒 指令和畫面經公共中繼伺服器（broker.emqx.io）轉送，但全部用只存在這個 QR Code 裡的金鑰加密（AES-256），"
                + "伺服器看不到內容。畫面只在遙控頁面開著時才傳。第一次傳畫面前，要到無障礙設定把服務關掉再打開一次。"));
        p.addView(sep());

        p.addView(label("📶 同一個 Wi-Fi：書籤／使用者腳本", 16, true));
        p.addView(label("其他裝置（電腦或另一支手機）和這支手機連同一個 Wi-Fi，用相機掃描：", 15, true));
        qr = new ImageView(this);
        qr.setScaleType(ImageView.ScaleType.FIT_CENTER);
        LinearLayout.LayoutParams qp = new LinearLayout.LayoutParams(dp(240), dp(240));
        qp.gravity = Gravity.CENTER_HORIZONTAL;
        qp.setMargins(0, dp(8), 0, dp(8));
        p.addView(qr, qp);
        urlTxt = label("", 14, false);
        urlTxt.setTextIsSelectable(true);
        urlTxt.setGravity(Gravity.CENTER);
        p.addView(urlTxt);
        p.addView(hint("控制頁提供兩種用法：\n"
                + "① 書籤／使用者腳本：在瀏覽器的遊戲頁上直接自動點「收成」，可設間隔、可選自動找按鈕或自訂位置。\n"
                + "② 遙控：用那個裝置開始／停止這支手機的連點、改間隔。\n"
                + "iPhone 也能用：用 iPhone 掃描後，照頁面裡的「iPhone 教學」設定 Safari 書籤。"));
        p.addView(btn("📋 複製書籤碼（給這支手機的瀏覽器用）", v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("書籤碼", Res.bookmarklet(this)));
            Toast.makeText(this, "已複製！新增書籤時把網址貼上，名稱填「收成」", Toast.LENGTH_LONG).show();
        }));
        p.addView(btn("📁 匯出手機用檔案（腳本、書籤、說明）", v -> {
            try {
                String where = Res.export(this);
                new AlertDialog.Builder(this).setTitle("已匯出").setMessage("已存到：\n" + where
                        + "\n\ncrrank-auto-harvest.user.js\n書籤碼.txt\n手機使用說明.html").setPositiveButton("好", null).show();
            } catch (Exception ex) {
                Toast.makeText(this, "匯出失敗：" + ex.getMessage(), Toast.LENGTH_LONG).show();
            }
        }));
        p.addView(btn("在瀏覽器開啟控制頁", v -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(e.url())))));
        return p;
    }

    // ---------- 分頁 3：內建遊戲 ----------
    private View buildGameTab() {
        LinearLayout p = page();
        p.addView(label("內建遊戲模式（不需要無障礙權限）", 16, true));
        p.addView(hint("在 App 裡直接開啟知識領土，畫面上會自動出現「自動收成」面板："
                + "設定間隔秒數，選「自動找收成按鈕」（沒有可收成時會自動跳過）或「點自訂位置」，按開始。\n\n"
                + "第一次要在裡面用 Discord 登入。這個畫面會讓螢幕保持亮著；切到其他 App 時計時會暫停。"));
        Button b = btn("▶ 開啟知識領土（內建自動收成）", v -> startActivity(new Intent(this, GameActivity.class)));
        b.setTextSize(17);
        p.addView(b, new LinearLayout.LayoutParams(-1, dp(60)));
        p.addView(sep());
        p.addView(label("🌙 背景執行（遊戲不用放在前台）", 16, true));
        p.addView(hint("先用上面的按鈕打開遊戲、登入，在面板設定好收成和「🛒 自動購買」並按開始；再按下面的按鈕（或遊戲畫面右上角選單「切到背景執行」）。"
                + "遊戲會在看不見的視窗裡繼續跑，面板會自動接續剛剛的設定，你可以切去用別的 App。"
                + "浮動鈕 🌙 點一下可以顯示／隱藏，長按關閉。需要開啟無障礙權限；螢幕關掉時是否繼續跑，要看手機的省電設定。"));
        p.addView(btn("🌙 在背景執行遊戲", v -> {
            if (needService()) return;
            ClickService.inst.startBg();
            moveTaskToBack(true);
        }));
        p.addView(btn("關閉背景遊戲", v -> {
            ClickService s = ClickService.inst;
            if (s != null && s.bgRunning()) s.stopBg();
            else Toast.makeText(this, "背景遊戲沒有在執行", Toast.LENGTH_SHORT).show();
        }));
        return p;
    }

    // ---------- 動作 ----------
    private void loadFields() {
        ex.setText(String.valueOf(e.x));
        ey.setText(String.valueOf(e.y));
        eiv.setText(Engine.fmt(e.interval));
        for (int i = 0; i < Engine.UNITS.length; i++) if (Engine.UNITS[i].equals(e.unit)) sun.setSelection(i);
        ejit.setText(Engine.fmt(e.jitter));
        elim.setText(String.valueOf(e.limit));
        cnow.setChecked(e.clickNow);
        cbub.setChecked(e.showBubble);
        seenPos = e.x + "," + e.y;
        seenIv = Engine.fmt(e.interval) + e.unit;
    }

    private boolean collect(boolean showErr) {
        try {
            int x = Integer.parseInt(ex.getText().toString().trim());
            int y = Integer.parseInt(ey.getText().toString().trim());
            double iv = Double.parseDouble(eiv.getText().toString().trim());
            if (iv <= 0) throw new NumberFormatException();
            String js = ejit.getText().toString().trim();
            String ls = elim.getText().toString().trim();
            double jit = js.isEmpty() ? 0 : Double.parseDouble(js);
            int lim = ls.isEmpty() ? 0 : (int) Double.parseDouble(ls);
            e.x = x;
            e.y = y;
            e.interval = iv;
            e.unit = (String) sun.getSelectedItem();
            e.jitter = jit;
            e.limit = lim;
        } catch (Exception ex) {
            if (showErr) Toast.makeText(this, "請輸入正確的數字（間隔要大於 0）", Toast.LENGTH_LONG).show();
            return false;
        }
        e.clickNow = cnow.isChecked();
        e.save();
        return true;
    }

    private boolean needService() {
        if (e.serviceReady()) return false;
        new AlertDialog.Builder(this).setTitle("需要無障礙權限")
                .setMessage("要在其他 App（瀏覽器）上自動點擊，請先開啟「" + getString(R.string.service_name) + "」。\n\n"
                        + "或改用「內建遊戲」分頁，不需要這個權限。")
                .setPositiveButton("去開啟", (d, w) -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)))
                .setNegativeButton("取消", null).show();
        return true;
    }

    private void toggle() {
        if (e.running) {
            e.stop();
            return;
        }
        if (!collect(true) || needService()) return;
        Toast.makeText(this, "已開始，請切到遊戲畫面（可用浮動鈕 ■ 停止）", Toast.LENGTH_LONG).show();
        moveTaskToBack(true);
        e.h.postDelayed(e::start, 900);
    }

    private void testClick() {
        if (!collect(true) || needService()) return;
        Toast.makeText(this, "1.5 秒後在 (" + e.x + ", " + e.y + ") 點一下", Toast.LENGTH_SHORT).show();
        moveTaskToBack(true);
        e.h.postDelayed(e::once, 1500);
    }

    private void pick() {
        collect(false);
        if (needService()) return;
        moveTaskToBack(true);
        e.h.postDelayed(() -> {
            ClickService s = ClickService.inst;
            if (s != null) s.startPick();
        }, 700);
    }

    private void refresh() {
        if (go == null) return;
        status.setText(e.statusText());
        go.setText(e.running ? "■ 停止" : "▶ 開始");
        if (go.getTag() == null || (Boolean) go.getTag() != e.running) {
            go.setTag(e.running);
            paint(go, e.running ? C_RED : C_YEL);
        }
        boolean ok = e.serviceReady();
        acc.setText(ok ? "✅ 無障礙服務已開啟" : "⚠️ 尚未開啟無障礙服務");
        if (rateTxt != null) rateTxt.setText(e.rateText());
        if (batTxt != null)
            batTxt.setText(ignoringBattery() ? "✅ 已允許在背景執行（不受省電限制）" : "⚠️ 建議按下面的按鈕允許，不然息屏久了手機省電會讓背景遊戲斷線");
        ((GradientDrawable) accBox.getBackground()).setColor(ok ? 0xFFE3F7E3 : 0xFFFFF4D6);
        // 只有設定本身被改（浮動鈕選位置、遠端改間隔）時才更新欄位，不蓋掉使用者正在輸入的內容
        String pos = e.x + "," + e.y, ivs = Engine.fmt(e.interval) + e.unit;
        if (!pos.equals(seenPos)) {
            seenPos = pos;
            ex.setText(String.valueOf(e.x));
            ey.setText(String.valueOf(e.y));
        }
        if (!ivs.equals(seenIv)) {
            seenIv = ivs;
            eiv.setText(Engine.fmt(e.interval));
            for (int i = 0; i < Engine.UNITS.length; i++) if (Engine.UNITS[i].equals(e.unit)) sun.setSelection(i);
        }
        if (bgo != null) {
            bgo.setText(e.buyRunning ? "■ 停止自動購買" : "▶ 開始自動購買");
            if (bgo.getTag() == null || (Boolean) bgo.getTag() != e.buyRunning) {
                bgo.setTag(e.buyRunning);
                paint(bgo, e.buyRunning ? C_RED : C_SKY);
            }
            bstatus.setText(e.buyStatus());
            StringBuilder sig = new StringBuilder();
            sig.append(e.slot).append('|');
            for (Engine.Slot sl : e.slots) sig.append(sl.name).append(sl.steps.size()).append('|');
            for (Engine.Step s : e.steps) sig.append(s.name).append(s.x).append(',').append(s.y).append(s.times).append(s.wait)
                    .append(s.type).append(s.dir).append(s.amount).append(';');
            if (e.lastSaved != seenSaved) {
                seenSaved = e.lastSaved;
                savedTxt.setText("✔ 已自動存檔到「" + e.curSlot().name + "」 "
                        + new java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.US).format(new java.util.Date(e.lastSaved)));
            }
            if (!sig.toString().equals(stepsSig)) {
                stepsSig = sig.toString();
                renderSteps();
            }
        }
        String u = e.url();
        if (!u.equals(lastUrl)) {
            lastUrl = u;
            urlTxt.setText(u);
            drawQr(qr, u);
        }
        if (rqr != null) {
            Remote rm = Remote.get(e);
            String ru = rm.enabled() ? rm.url() : "";
            if (!ru.equals(lastRemoteUrl)) {
                lastRemoteUrl = ru;
                if (ru.isEmpty()) rqr.setImageDrawable(null);
                else drawQr(rqr, ru);
            }
            boolean watching = System.currentTimeMillis() < rm.watchUntil;
            remoteTxt.setText(rm.enabled() ? "● " + rm.state + (watching ? "　📺 有人正在看畫面" : "") : "遠端遙控已關閉");
        }
    }

    private void drawQr(ImageView qr, String text) {
        try {
            boolean[][] m = QrGen.encode(text);
            int n = m.length, border = 2, s = 8, size = (n + border * 2) * s;
            int[] px = new int[size * size];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++) {
                    int mx = x / s - border, my = y / s - border;
                    boolean dark = mx >= 0 && my >= 0 && mx < n && my < n && m[my][mx];
                    px[y * size + x] = dark ? Color.BLACK : Color.WHITE;
                }
            qr.setImageBitmap(Bitmap.createBitmap(px, size, size, Bitmap.Config.ARGB_8888));
        } catch (Exception ex) {
            qr.setImageDrawable(null);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadFields();
        loadBuyFields();
        e.addListener(listener);
        e.h.post(ticker);
    }

    @Override
    protected void onPause() {
        collect(false);
        e.removeListener(listener);
        e.h.removeCallbacks(ticker);
        super.onPause();
    }
}
