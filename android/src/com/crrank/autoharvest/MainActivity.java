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
    private String lastUrl = "", seenPos = "", seenIv = "";
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

    // ---------- 小工具 ----------
    private TextView label(String s, float size, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(size);
        t.setTextColor(0xFF222222);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, dp(4), 0, dp(4));
        return t;
    }

    private TextView hint(String s) {
        TextView t = label(s, 13, false);
        t.setTextColor(0xFF666666);
        return t;
    }

    private EditText num(boolean decimal) {
        EditText t = new EditText(this);
        t.setInputType(InputType.TYPE_CLASS_NUMBER | (decimal ? InputType.TYPE_NUMBER_FLAG_DECIMAL : 0));
        t.setSelectAllOnFocus(true);
        t.setMinWidth(dp(90));
        return t;
    }

    private Button btn(String s, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setOnClickListener(l);
        return b;
    }

    private LinearLayout row(View... vs) {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        for (View v : vs) r.addView(v);
        return r;
    }

    private LinearLayout row2(View a, View b) {
        LinearLayout r = row();
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, -2, 1);
        r.addView(a, p);
        r.addView(b, new LinearLayout.LayoutParams(0, -2, 1));
        return r;
    }

    private LinearLayout page() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setPadding(dp(16), dp(10), dp(16), dp(24));
        return l;
    }

    private View sep() {
        View v = new View(this);
        v.setBackgroundColor(0xFFDDDDDD);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, dp(1));
        p.setMargins(0, dp(10), 0, dp(10));
        v.setLayoutParams(p);
        return v;
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        e = Engine.get(this);
        e.startServer();

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        String[] names = {"定點連點", "手機 / 遙控", "內建遊戲"};
        tabBtns = new Button[3];
        for (int i = 0; i < 3; i++) {
            final int k = i;
            tabBtns[i] = btn(names[i], v -> showTab(k));
            bar.addView(tabBtns[i], new LinearLayout.LayoutParams(0, -2, 1));
        }
        root.addView(bar);

        FrameLayout content = new FrameLayout(this);
        tabs = new ScrollView[]{new ScrollView(this), new ScrollView(this), new ScrollView(this)};
        tabs[0].addView(buildClickTab());
        tabs[1].addView(buildPhoneTab());
        tabs[2].addView(buildGameTab());
        for (ScrollView s : tabs) content.addView(s, new FrameLayout.LayoutParams(-1, -1));
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        showTab(e.prefs().getInt("tab", 0));
    }

    private void showTab(int k) {
        for (int i = 0; i < tabs.length; i++) {
            tabs[i].setVisibility(i == k ? View.VISIBLE : View.GONE);
            tabBtns[i].setTypeface(i == k ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
            tabBtns[i].setAlpha(i == k ? 1f : 0.6f);
        }
        e.prefs().edit().putInt("tab", k).apply();
    }

    // ---------- 分頁 1：定點連點（對應電腦版「電腦連點」） ----------
    private View buildClickTab() {
        LinearLayout p = page();

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(12), dp(8), dp(12), dp(8));
        GradientDrawable g = new GradientDrawable();
        g.setColor(0xFFFFF4D6);
        g.setCornerRadius(dp(10));
        box.setBackground(g);
        acc = label("", 14, true);
        box.addView(acc);
        box.addView(hint("自動點擊需要開啟「無障礙」裡的「" + getString(R.string.service_name) + "」。\n"
                + "Android 13 以上若開關是灰色：到 設定 → 應用程式 → " + getString(R.string.app_name)
                + " → 右上角 ⋮ → 「允許受限制的設定」，再回來開啟。"));
        box.addView(btn("開啟無障礙權限設定", v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))));
        accBox = box;
        p.addView(box);

        p.addView(label("點擊位置（螢幕座標）", 16, true));
        ex = num(false);
        ey = num(false);
        p.addView(row(label("X ", 15, false), ex, label("   Y ", 15, false), ey));
        p.addView(row2(btn("🎯 在螢幕上選位置", v -> pick()), btn("測試點一下", v -> testClick())));
        p.addView(hint("或在遊戲畫面上按浮動控制鈕的 🎯 選位置（等同電腦版 F8）"));
        p.addView(sep());

        eiv = num(true);
        sun = new Spinner(this);
        ArrayAdapter<String> ad = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, Engine.UNITS);
        sun.setAdapter(ad);
        p.addView(row(label("間隔  ", 15, false), eiv, sun));
        ejit = num(true);
        p.addView(row(label("隨機誤差 ± 秒  ", 15, false), ejit));
        elim = num(false);
        p.addView(row(label("次數上限 (0=無限)  ", 15, false), elim));
        cnow = new CheckBox(this);
        cnow.setText("按開始時立刻先點一次");
        p.addView(cnow);
        cbub = new CheckBox(this);
        cbub.setText("顯示浮動控制鈕（▶/■ 開始停止、🎯 選位置）");
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

        go = btn("▶ 開始", v -> toggle());
        go.setTextSize(18);
        go.setTypeface(Typeface.DEFAULT_BOLD);
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(-1, dp(56));
        gp.setMargins(0, dp(10), 0, dp(4));
        p.addView(go, gp);
        status = label("已停止", 14, false);
        p.addView(status);
        p.addView(btn("開啟知識領土網站", v -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(Engine.GAME_URL)))));
        p.addView(hint("提示：按開始後 App 會退到背景，遊戲畫面要停在那個位置、不要被擋住，螢幕要保持亮著。"));
        return p;
    }

    // ---------- 分頁 2：手機 / 遙控（對應電腦版「手機」分頁） ----------
    private View buildPhoneTab() {
        LinearLayout p = page();
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
        go.getBackground().setTint(e.running ? 0xFFFF6B6B : 0xFFFFC93C);
        boolean ok = e.serviceReady();
        acc.setText(ok ? "✅ 無障礙服務已開啟" : "⚠️ 尚未開啟無障礙服務");
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
        String u = e.url();
        if (!u.equals(lastUrl)) {
            lastUrl = u;
            urlTxt.setText(u);
            drawQr(u);
        }
    }

    private void drawQr(String text) {
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
