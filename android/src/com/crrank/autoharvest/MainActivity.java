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
        String[] names = {"定點連點", "自動購買", "手機/遙控", "內建遊戲"};
        tabBtns = new Button[names.length];
        for (int i = 0; i < names.length; i++) {
            final int k = i;
            tabBtns[i] = btn(names[i], v -> showTab(k));
            bar.addView(tabBtns[i], new LinearLayout.LayoutParams(0, -2, 1));
        }
        root.addView(bar);

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
        bgo = btn("▶ 開始自動購買", v -> toggleBuy());
        bgo.setTextSize(18);
        bgo.setTypeface(Typeface.DEFAULT_BOLD);
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(-1, dp(56));
        gp.setMargins(0, dp(10), 0, dp(4));
        p.addView(bgo, gp);
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
        if (bgo != null) {
            bgo.setText(e.buyRunning ? "■ 停止自動購買" : "▶ 開始自動購買");
            bgo.getBackground().setTint(e.buyRunning ? 0xFFFF6B6B : 0xFF8FD3FF);
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
