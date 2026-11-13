# -*- coding: utf-8 -*-
"""CR Rank 自動收成器 - 單一 exe：電腦定點連點 + 手機（書籤/腳本 + 遙控）"""
import ctypes
import json
import os
import random
import secrets
import socket
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import filedialog, messagebox, ttk

APP_NAME = "CR Rank 自動收成器"
GAME_URL = "https://crrank.xpgs25.com/game"

# ---------- DPI：讓座標和實際螢幕像素一致 ----------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
VK_F8, VK_F9 = 0x77, 0x78


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def click_at(x, y, restore=True):
    old = get_cursor()
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.03)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    if restore:
        time.sleep(0.03)
        user32.SetCursorPos(*old)


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


SETTINGS_FILE = os.path.join(app_dir(), "crrank_clicker_settings.json")
DEFAULTS = {"x": 0, "y": 0, "interval": 60, "unit": "秒", "jitter": 0,
            "limit": 0, "restore": True, "click_now": True, "port": 8765}
UNIT_SEC = {"秒": 1, "分": 60, "時": 3600}


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------- 手機用的網頁腳本（在網頁裡直接點按鈕） ----------
MOBILE_JS = r"""
(function(){
if(window.__crac){window.__crac.show();return;}
var K='crac_cfg',c={iv:60,mode:'auto',x:50,y:50,px:10,py:90};
try{var o=JSON.parse(localStorage.getItem(K)||'{}');for(var k in o)c[k]=o[k];}catch(e){}
function save(){try{localStorage.setItem(K,JSON.stringify(c));}catch(e){}}
var t=null,tick=null,n=0,next=0,last='';
var p=document.createElement('div');
p.style.cssText='position:fixed;z-index:2147483647;background:#1e2230;color:#fff;font:14px sans-serif;padding:10px;border-radius:12px;box-shadow:0 4px 18px rgba(0,0,0,.45);width:210px;touch-action:none;line-height:1.7';
p.innerHTML='<div data-h style="font-weight:bold;cursor:move;user-select:none">&#9776; 自動收成<span data-x style="float:right;cursor:pointer;padding:0 4px">&#10005;</span></div>'+
'<label>間隔(秒) <input data-iv type="number" min="1" style="width:80px;font-size:14px"></label><br>'+
'<label><input type="radio" name="cracm" value="auto"> 自動找「收成」按鈕</label><br>'+
'<label><input type="radio" name="cracm" value="pos"> 點自訂位置</label> <button data-pk style="font-size:13px">選位置</button><br>'+
'<button data-go style="width:100%;margin-top:4px;padding:7px;font-size:15px;font-weight:bold;border:0;border-radius:8px;background:#ffc93c;color:#222">開始</button>'+
'<div data-s style="font-size:12px;opacity:.85;margin-top:4px">未開始</div>';
document.body.appendChild(p);
var mk=document.createElement('div');
mk.style.cssText='position:fixed;z-index:2147483646;width:22px;height:22px;margin:-11px 0 0 -11px;border:3px solid #ff3b5c;border-radius:50%;pointer-events:none;display:none';
document.body.appendChild(mk);
function q(s){return p.querySelector('['+s+']');}
function place(){var w=innerWidth,h=innerHeight;c.px=Math.min(Math.max(0,c.px),w-60);c.py=Math.min(Math.max(0,c.py),h-40);p.style.left=c.px+'px';p.style.top=c.py+'px';}
function showMk(){mk.style.left=(c.x*innerWidth/100)+'px';mk.style.top=(c.y*innerHeight/100)+'px';mk.style.display=c.mode=='pos'?'block':'none';}
place();showMk();addEventListener('resize',function(){place();showMk();});
var iv=q('data-iv');iv.value=c.iv;
iv.onchange=function(){c.iv=Math.max(1,parseFloat(iv.value)||60);iv.value=c.iv;save();if(t){stop();start();}};
var rs=p.querySelectorAll('input[name=cracm]');
for(var i=0;i<rs.length;i++){(function(r){r.checked=r.value==c.mode;r.onchange=function(){c.mode=r.value;save();showMk();};})(rs[i]);}
function findBtn(){var b=document.querySelector('button[title="領取領地產出"]');if(b)return b;var a=document.querySelectorAll('button');for(var j=0;j<a.length;j++){if(/^收成\s*\+/.test((a[j].textContent||'').trim()))return a[j];}return null;}
function fire(el,x,y){var o={bubbles:true,cancelable:true,view:window,clientX:x,clientY:y,button:0,pointerId:1,isPrimary:true,pointerType:'touch'};
try{el.dispatchEvent(new PointerEvent('pointerdown',o));}catch(e){}el.dispatchEvent(new MouseEvent('mousedown',o));
try{el.dispatchEvent(new PointerEvent('pointerup',o));}catch(e){}el.dispatchEvent(new MouseEvent('mouseup',o));
if(el.click)el.click();else el.dispatchEvent(new MouseEvent('click',o));}
function doClick(){
if(c.mode=='auto'){var b=findBtn();if(b){var tx=b.textContent.trim();b.click();n++;last='已收成 '+tx;}else{last='目前沒有可收成';}}
else{var x=c.x*innerWidth/100,y=c.y*innerHeight/100;p.style.visibility='hidden';var el=document.elementFromPoint(x,y);p.style.visibility='';if(el){fire(el,x,y);n++;last='已點位置';}else last='位置沒有元素';}
next=Date.now()+c.iv*1000;upd();}
function upd(){q('data-s').textContent=(t?'執行中 · 下次 '+Math.max(0,Math.ceil((next-Date.now())/1000))+' 秒':'已停止')+' · 共 '+n+' 次'+(last?' · '+last:'');}
function start(){if(t)return;doClick();t=setInterval(doClick,c.iv*1000);tick=setInterval(upd,1000);var g=q('data-go');g.textContent='停止';g.style.background='#ff6b6b';upd();}
function stop(){clearInterval(t);clearInterval(tick);t=null;var g=q('data-go');g.textContent='開始';g.style.background='#ffc93c';upd();}
q('data-go').onclick=function(){t?stop():start();};
q('data-x').onclick=function(){stop();p.style.display='none';mk.style.display='none';};
q('data-pk').onclick=function(){var ov=document.createElement('div');
ov.style.cssText='position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.35);color:#fff;font:bold 20px sans-serif;display:flex;align-items:center;justify-content:center;text-align:center;touch-action:none';
ov.textContent='點一下要自動點擊的位置';document.body.appendChild(ov);
ov.addEventListener('pointerdown',function(e){e.preventDefault();e.stopPropagation();c.x=e.clientX/innerWidth*100;c.y=e.clientY/innerHeight*100;c.mode='pos';
for(var j=0;j<rs.length;j++)rs[j].checked=rs[j].value=='pos';save();showMk();setTimeout(function(){ov.remove();},50);},{once:true});};
var hd=q('data-h'),dx=0,dy=0,dr=false;
hd.addEventListener('pointerdown',function(e){if(e.target.hasAttribute('data-x'))return;dr=true;dx=e.clientX-c.px;dy=e.clientY-c.py;hd.setPointerCapture(e.pointerId);});
hd.addEventListener('pointermove',function(e){if(!dr)return;c.px=e.clientX-dx;c.py=e.clientY-dy;place();});
hd.addEventListener('pointerup',function(){dr=false;save();});
window.__crac={show:function(){p.style.display='';showMk();}};
})();
"""


def minify_js(js):
    return "".join(line.strip() for line in js.strip().splitlines())


def bookmarklet():
    return "javascript:" + urllib.parse.quote(minify_js(MOBILE_JS), safe="()';,/=+:!*.-_~[]{}?&<>|@$^`\"")


def userscript():
    return ("// ==UserScript==\n// @name         CR Rank 自動收成\n// @namespace    crrank-auto-harvest\n"
            "// @version      1.0\n// @description  定時點擊知識領土的「收成」按鈕，可自訂間隔與位置\n"
            "// @match        https://crrank.xpgs25.com/*\n// @grant        none\n// @run-at       document-idle\n"
            "// ==/UserScript==\n" + MOBILE_JS.strip() + "\n")


# ---------- 手機網頁 ----------
PHONE_HTML = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>自動收成 · 手機</title>
<style>
body{font-family:sans-serif;background:#141722;color:#eee;margin:0;padding:16px;line-height:1.6}
h1{font-size:20px;margin:0 0 12px}h2{font-size:17px;margin:22px 0 8px;color:#ffc93c}
.card{background:#1f2433;border-radius:12px;padding:14px;margin-bottom:12px}
button{font-size:16px;padding:10px 14px;border:0;border-radius:8px;background:#ffc93c;color:#222;font-weight:bold;margin:4px 4px 4px 0}
button.red{background:#ff6b6b}textarea{width:100%;height:90px;font-size:11px;box-sizing:border-box}
input,select{font-size:16px;padding:6px;width:90px}ol{padding-left:20px}a{color:#7cc4ff}
#st{font-size:14px;opacity:.9}
</style></head><body>
<h1>CR Rank 自動收成 · 手機</h1>
<h2>方法一：在手機瀏覽器裡自動點（推薦）</h2>
<div class="card">
<p>1. 按「複製書籤碼」，在瀏覽器新增一個書籤，名稱填 <b>收成</b>，網址貼上剛複製的內容。</p>
<p>2. 打開 <a href="https://crrank.xpgs25.com/game" target="_blank">知識領土遊戲頁</a> 並登入。</p>
<p>3. <b>Chrome (Android)</b>：在網址列輸入「收成」，點選書籤那一項。<b>Safari (iPhone)</b>：從書籤列表點「收成」。</p>
<p>4. 畫面上會出現控制面板：設定間隔秒數、選「自動找收成按鈕」或「點自訂位置」，按開始。</p>
<button onclick="cp()">複製書籤碼</button>
<textarea id="bm" readonly>__BM__</textarea>
<p style="font-size:13px;opacity:.8">有裝 Tampermonkey／Violentmonkey（如 Firefox、Kiwi、Edge 手機版）也可以直接安裝
<a href="/crrank.user.js">使用者腳本</a>，進遊戲頁就會自動出現面板。<br>
注意：手機請保持螢幕亮著、遊戲分頁在前景，否則瀏覽器會暫停計時。</p>
</div>
<h2>方法二：用手機遙控電腦連點</h2>
<div class="card">
<div id="st">讀取中…</div>
<p>間隔 <input id="iv" type="number" min="1"> <select id="un"><option>秒</option><option>分</option><option>時</option></select>
<button onclick="api('set?interval='+iv.value+'&unit='+encodeURIComponent(un.value))">套用</button></p>
<button onclick="api('start')">開始</button><button class="red" onclick="api('stop')">停止</button>
<button onclick="api('once')">立即點一次</button>
</div>
<script>
var T='__TOKEN__';
function cp(){var t=document.getElementById('bm');t.focus();t.select();t.setSelectionRange(0,99999);
var ok=false;try{ok=document.execCommand('copy');}catch(e){}
if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t.value);ok=true;}
alert(ok?'已複製！請新增書籤並貼到網址欄。':'請長按文字框全選後手動複製');}
var first=true;
function show(s){document.getElementById('st').innerHTML=(s.running?'<b style="color:#7f7">執行中</b>':'<b>已停止</b>')+
' · 位置 ('+s.x+', '+s.y+') · 已點 '+s.count+' 次'+(s.running?' · 下次 '+s.next_in+' 秒':'');
if(first){iv.value=s.interval;un.value=s.unit;first=false;}}
function api(p){fetch('/api/'+p+(p.indexOf('?')<0?'?':'&')+'t='+T).then(function(r){return r.json()}).then(show).catch(function(){
document.getElementById('st').textContent='連不到電腦（確認電腦程式開著、在同一個 Wi-Fi）';});}
api('status');setInterval(function(){api('status')},2000);
</script></body></html>"""


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class Clicker:
    def __init__(self, settings):
        self.s = settings
        self.running = False
        self.count = 0
        self.next_at = 0.0
        self.stop_evt = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.on_change = lambda: None

    def interval_sec(self):
        return max(0.1, float(self.s["interval"]) * UNIT_SEC.get(self.s["unit"], 1))

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            self.stop_evt.clear()
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
        self.on_change()

    def stop(self):
        with self.lock:
            self.running = False
            self.stop_evt.set()
        self.on_change()

    def once(self):
        click_at(self.s["x"], self.s["y"], self.s["restore"])
        self.count += 1

    def _loop(self):
        done = 0
        if not self.s.get("click_now", True):
            self.next_at = time.time() + self._wait()
            if self.stop_evt.wait(self.next_at - time.time()):
                return
        while not self.stop_evt.is_set():
            self.once()
            done += 1
            lim = int(self.s.get("limit") or 0)
            if lim and done >= lim:
                self.running = False
                self.on_change()
                return
            self.next_at = time.time() + self._wait()
            if self.stop_evt.wait(max(0, self.next_at - time.time())):
                return

    def _wait(self):
        j = float(self.s.get("jitter") or 0)
        return max(0.1, self.interval_sec() + (random.uniform(-j, j) if j else 0))

    def status(self):
        return {"running": self.running, "count": self.count, "x": self.s["x"], "y": self.s["y"],
                "interval": self.s["interval"], "unit": self.s["unit"],
                "next_in": max(0, int(round(self.next_at - time.time()))) if self.running else 0}


def make_handler(app):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            qs = dict(urllib.parse.parse_qsl(u.query))
            if u.path == "/crrank.user.js":
                return self._send(200, userscript(), "application/javascript; charset=utf-8")
            if qs.get("t") != app.token:
                return self._send(403, "需要正確的連結（請重新掃描電腦上的 QR Code）", "text/plain; charset=utf-8")
            if u.path == "/":
                html = PHONE_HTML.replace("__BM__", bookmarklet().replace("&", "&amp;").replace("<", "&lt;")) \
                                 .replace("__TOKEN__", app.token)
                return self._send(200, html, "text/html; charset=utf-8")
            if u.path.startswith("/api/"):
                cmd = u.path[5:]
                if cmd == "start":
                    app.root.after(0, app.start)
                elif cmd == "stop":
                    app.root.after(0, app.stop)
                elif cmd == "once":
                    threading.Thread(target=app.clicker.once, daemon=True).start()
                elif cmd == "set":
                    try:
                        v = float(qs.get("interval", ""))
                        if v > 0:
                            app.root.after(0, lambda: app.set_interval(v, qs.get("unit", "秒")))
                    except ValueError:
                        pass
                time.sleep(0.15)
                return self._send(200, json.dumps(app.clicker.status()), "application/json")
            self._send(404, "not found", "text/plain")
    return H


class App:
    def __init__(self):
        self.s = load_settings()
        self.token = secrets.token_urlsafe(8)
        self.clicker = Clicker(self.s)
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        try:
            dpi = user32.GetDpiForWindow(self.root.winfo_id()) or 96
            self.root.tk.call("tk", "scaling", dpi / 72.0)
        except Exception:
            pass
        self.root.attributes("-topmost", True)
        self.clicker.on_change = lambda: self.root.after(0, self.refresh_btn)
        self.server = None
        self.url = ""
        self.build_ui()
        self.start_server()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(200, self.poll)
        self._keys = {VK_F8: False, VK_F9: False}

    # ----- UI -----
    def build_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        pc = ttk.Frame(nb, padding=10)
        ph = ttk.Frame(nb, padding=10)
        nb.add(pc, text=" 電腦連點 ")
        nb.add(ph, text=" 手機 ")

        r = 0
        ttk.Label(pc, text="點擊位置（螢幕座標）", font=("Microsoft JhengHei UI", 10, "bold")).grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        self.vx = tk.IntVar(value=self.s["x"])
        self.vy = tk.IntVar(value=self.s["y"])
        ttk.Label(pc, text="X").grid(row=r, column=0, sticky="e")
        ttk.Entry(pc, textvariable=self.vx, width=7).grid(row=r, column=1, sticky="w")
        ttk.Label(pc, text="Y").grid(row=r, column=2, sticky="e")
        ttk.Entry(pc, textvariable=self.vy, width=7).grid(row=r, column=3, sticky="w")
        r += 1
        ttk.Button(pc, text="🎯 在螢幕上選位置", command=self.pick).grid(row=r, column=0, columnspan=2, sticky="we", pady=4)
        ttk.Button(pc, text="測試點一下", command=self.test_click).grid(row=r, column=2, columnspan=2, sticky="we", pady=4)
        r += 1
        ttk.Label(pc, text="或把滑鼠移到「收成」按鈕上按 F8 記錄", foreground="#666").grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        ttk.Separator(pc).grid(row=r, column=0, columnspan=4, sticky="we", pady=6)
        r += 1
        ttk.Label(pc, text="間隔").grid(row=r, column=0, sticky="e")
        self.viv = tk.StringVar(value=str(self.s["interval"]))
        ttk.Entry(pc, textvariable=self.viv, width=7).grid(row=r, column=1, sticky="w")
        self.vun = tk.StringVar(value=self.s["unit"])
        ttk.Combobox(pc, textvariable=self.vun, values=list(UNIT_SEC), width=4, state="readonly").grid(row=r, column=2, sticky="w")
        r += 1
        ttk.Label(pc, text="隨機誤差 ± 秒").grid(row=r, column=0, columnspan=2, sticky="e")
        self.vjit = tk.StringVar(value=str(self.s["jitter"]))
        ttk.Entry(pc, textvariable=self.vjit, width=7).grid(row=r, column=2, sticky="w")
        r += 1
        ttk.Label(pc, text="次數上限 (0=無限)").grid(row=r, column=0, columnspan=2, sticky="e")
        self.vlim = tk.StringVar(value=str(self.s["limit"]))
        ttk.Entry(pc, textvariable=self.vlim, width=7).grid(row=r, column=2, sticky="w")
        r += 1
        self.vres = tk.BooleanVar(value=self.s["restore"])
        ttk.Checkbutton(pc, text="點完把滑鼠移回原位", variable=self.vres).grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        self.vnow = tk.BooleanVar(value=self.s["click_now"])
        ttk.Checkbutton(pc, text="按開始時立刻先點一次", variable=self.vnow).grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        self.btn = tk.Button(pc, text="▶ 開始 (F9)", font=("Microsoft JhengHei UI", 12, "bold"), bg="#ffc93c",
                             relief="flat", command=self.toggle)
        self.btn.grid(row=r, column=0, columnspan=4, sticky="we", pady=(8, 4))
        r += 1
        self.status = ttk.Label(pc, text="已停止")
        self.status.grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        ttk.Button(pc, text="開啟知識領土網站", command=lambda: webbrowser.open(GAME_URL)).grid(row=r, column=0, columnspan=4, sticky="we", pady=(6, 0))
        r += 1
        ttk.Label(pc, text="提示：瀏覽器視窗要保持在那個位置、不要被擋住。", foreground="#666").grid(row=r, column=0, columnspan=4, sticky="w")

        ttk.Label(ph, text="手機和電腦連同一個 Wi-Fi，用手機相機掃描：", font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
        self.qr = tk.Canvas(ph, width=220, height=220, bg="white", highlightthickness=0)
        self.qr.pack(pady=6)
        self.url_lbl = ttk.Entry(ph, width=44)
        self.url_lbl.pack(fill="x")
        ttk.Label(ph, justify="left", foreground="#444", text=(
            "手機頁面提供兩種用法：\n"
            "① 書籤／使用者腳本：在手機瀏覽器的遊戲頁上直接自動\n"
            "   點「收成」，可設間隔、可選自動找按鈕或自訂位置。\n"
            "② 遙控：用手機開始／停止電腦這邊的連點。\n"
            "第一次啟動時 Windows 防火牆若跳出詢問，請按「允許」。")).pack(anchor="w", pady=6)
        ttk.Button(ph, text="📁 匯出手機用檔案（腳本、書籤、說明）", command=self.export).pack(fill="x")
        ttk.Button(ph, text="在電腦瀏覽器開啟手機頁", command=lambda: webbrowser.open(self.url)).pack(fill="x", pady=4)

    def draw_qr(self, text):
        self.qr.delete("all")
        try:
            import qrcode
            q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            q.add_data(text)
            q.make(fit=True)
            m = q.get_matrix()
            n = len(m)
            size = max(2, 220 // n)
            off = (220 - size * n) // 2
            for y, row in enumerate(m):
                for x, v in enumerate(row):
                    if v:
                        self.qr.create_rectangle(off + x * size, off + y * size, off + (x + 1) * size,
                                                 off + (y + 1) * size, fill="black", outline="black")
        except Exception as e:
            self.qr.create_text(110, 110, text=f"QR 失敗\n{e}")

    # ----- 動作 -----
    def collect(self):
        try:
            self.s["x"], self.s["y"] = int(self.vx.get()), int(self.vy.get())
            self.s["interval"] = float(self.viv.get())
            if self.s["interval"] <= 0:
                raise ValueError
            self.s["unit"] = self.vun.get()
            self.s["jitter"] = float(self.vjit.get() or 0)
            self.s["limit"] = int(float(self.vlim.get() or 0))
        except (ValueError, tk.TclError):
            messagebox.showerror(APP_NAME, "請輸入正確的數字（間隔要大於 0）")
            return False
        self.s["restore"] = self.vres.get()
        self.s["click_now"] = self.vnow.get()
        if self.s["interval"] == int(self.s["interval"]):
            self.s["interval"] = int(self.s["interval"])
        save_settings(self.s)
        return True

    def start(self):
        if self.collect():
            self.clicker.count = 0
            self.clicker.start()

    def stop(self):
        self.clicker.stop()

    def toggle(self):
        self.stop() if self.clicker.running else self.start()

    def set_interval(self, v, unit):
        self.viv.set(str(int(v) if v == int(v) else v))
        if unit in UNIT_SEC:
            self.vun.set(unit)
        was = self.clicker.running
        if was:
            self.clicker.stop()
            if self.clicker.thread:
                self.clicker.thread.join(1)
        if self.collect() and was:
            self.clicker.start()

    def test_click(self):
        if self.collect():
            self.root.after(300, lambda: click_at(self.s["x"], self.s["y"], self.s["restore"]))

    def pick(self):
        vx = user32.GetSystemMetrics(76)
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)
        vh = user32.GetSystemMetrics(79)
        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.geometry(f"{vw}x{vh}+{vx}+{vy}")
        ov.attributes("-alpha", 0.3)
        ov.attributes("-topmost", True)
        ov.configure(bg="black", cursor="crosshair")
        tk.Label(ov, text="點一下「收成」按鈕的位置（Esc 取消）", fg="white", bg="black",
                 font=("Microsoft JhengHei UI", 20, "bold")).place(relx=0.5, rely=0.08, anchor="n")

        def done(e):
            x, y = get_cursor()
            self.vx.set(x)
            self.vy.set(y)
            ov.destroy()
            self.collect()

        ov.bind("<Button-1>", done)
        ov.bind("<Escape>", lambda e: ov.destroy())
        ov.focus_force()

    def export(self):
        d = filedialog.askdirectory(title="選擇匯出資料夾", initialdir=app_dir())
        if not d:
            return
        out = os.path.join(d, "crrank_手機檔案")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "crrank-auto-harvest.user.js"), "w", encoding="utf-8") as f:
            f.write(userscript())
        with open(os.path.join(out, "書籤碼.txt"), "w", encoding="utf-8") as f:
            f.write(bookmarklet())
        html = PHONE_HTML.replace("__BM__", bookmarklet().replace("&", "&amp;").replace("<", "&lt;")).replace("__TOKEN__", "")
        html = html.replace('href="/crrank.user.js"', 'href="crrank-auto-harvest.user.js"')
        with open(os.path.join(out, "手機使用說明.html"), "w", encoding="utf-8") as f:
            f.write(html)
        messagebox.showinfo(APP_NAME, f"已匯出到：\n{out}\n\n可把這個資料夾傳到手機使用（遙控功能需連到電腦程式）。")
        os.startfile(out)

    def start_server(self):
        port = int(self.s.get("port", 8765))
        for p in range(port, port + 20):
            try:
                self.server = ThreadingHTTPServer(("0.0.0.0", p), make_handler(self))
                break
            except OSError:
                continue
        if not self.server:
            self.url = "（伺服器啟動失敗）"
        else:
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            self.url = f"http://{lan_ip()}:{self.server.server_address[1]}/?t={self.token}"
        self.url_lbl.insert(0, self.url)
        self.draw_qr(self.url)

    def refresh_btn(self):
        if self.clicker.running:
            self.btn.config(text="■ 停止 (F9)", bg="#ff6b6b")
        else:
            self.btn.config(text="▶ 開始 (F9)", bg="#ffc93c")

    def poll(self):
        st = self.clicker.status()
        self.status.config(text=(f"執行中 · 下次 {st['next_in']} 秒" if st["running"] else "已停止") + f" · 已點 {st['count']} 次")
        for vk in (VK_F8, VK_F9):
            down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            if down and not self._keys[vk]:
                if vk == VK_F8:
                    x, y = get_cursor()
                    self.vx.set(x)
                    self.vy.set(y)
                    self.collect()
                else:
                    self.toggle()
            self._keys[vk] = down
        self.root.after(100, self.poll)

    def quit(self):
        self.clicker.stop()
        try:
            self.collect()
        except Exception:
            pass
        if self.server:
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
