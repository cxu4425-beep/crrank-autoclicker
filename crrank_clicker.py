# -*- coding: utf-8 -*-
"""CR Rank 自動收成器 - 單一 exe：電腦定點連點 + 手機（書籤/腳本 + 遙控）"""
import ctypes
import json
import os
import random
import re
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
APP_VERSION = "1.9"
REPO = "cxu4425-beep/crrank-autoclicker"
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
VK_F8, VK_F9, VK_F10 = 0x77, 0x78, 0x79
CLICK_LOCK = threading.Lock()  # 收成連點和自動購買不會同時點


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def click_at(x, y, restore=True):
    with CLICK_LOCK:
        old = get_cursor()
        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.03)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.04)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        if restore:
            time.sleep(0.03)
            user32.SetCursorPos(*old)


MOUSEEVENTF_WHEEL = 0x0800


def scroll_at(x, y, down=True, notches=3, restore=True):
    """把滑鼠移到 (x, y) 轉滾輪；down=True 往下捲。"""
    with CLICK_LOCK:
        old = get_cursor()
        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.05)
        delta = -120 if down else 120
        for _ in range(max(1, int(notches))):
            user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
            time.sleep(0.06)
        if restore:
            time.sleep(0.03)
            user32.SetCursorPos(*old)


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


SETTINGS_FILE = os.path.join(app_dir(), "crrank_clicker_settings.json")
DEFAULTS = {"x": 0, "y": 0, "interval": 60, "unit": "秒", "jitter": 0,
            "limit": 0, "restore": True, "click_now": True, "port": 8765,
            "buy_mode": "restock", "buy_every": 30, "buy_offset": 10, "buy_now": True,
            "buy_slot": 0, "buy_rotate": False, "auto_rate": True}
NUM_SLOTS = 3


def default_slots():
    return [{"name": f"存檔{i + 1}", "steps": []} for i in range(NUM_SLOTS)]


def step_action(st):
    """步驟在列表上顯示的動作文字"""
    if st.get("type") == "scroll":
        return f"滾動{'↓' if st.get('dir', 'down') == 'down' else '↑'}{st.get('amount', 3)}格"
    return "點擊"
UNIT_SEC = {"秒": 1, "分": 60, "時": 3600}
RESTOCK_SEC = 1800  # 商店每 30 分鐘（整點、半點）全服補貨

# 購買範本：(步驟名稱, 點幾次, 點完等幾秒)
BUY_TEMPLATE = [("打開「物品」", 1, 1.2), ("點「商店」分頁", 1, 1.0), ("點商品分類（道具／地形）", 1, 1.0),
                ("點商品的「購買」", 3, 1.0), ("關閉商店 ×", 1, 0.5)]


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    # 存檔：舊版的 buy_steps 搬到「存檔1」
    slots = s.get("buy_slots")
    if not isinstance(slots, list) or not slots:
        slots = default_slots()
        if s.get("buy_steps"):
            slots[0]["steps"] = s["buy_steps"]
    while len(slots) < NUM_SLOTS:
        slots.append({"name": f"存檔{len(slots) + 1}", "steps": []})
    s["buy_slots"] = slots
    s.pop("buy_steps", None)
    if not (0 <= int(s.get("buy_slot", 0)) < len(slots)):
        s["buy_slot"] = 0
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
if(window.__crac){if(!window.__cracAuto)window.__crac.show();window.__cracAuto=0;return;}
window.__cracAuto=0;
var K='crac_cfg',c={iv:60,mode:'auto',x:50,y:50,px:10,py:90};
try{var o=JSON.parse(localStorage.getItem(K)||'{}');for(var k in o)c[k]=o[k];}catch(e){}
function save(){try{localStorage.setItem(K,JSON.stringify(c));}catch(e){}}
var t=null,tick=null,n=0,next=0,last='';
var p=document.createElement('div');
p.style.cssText='position:fixed;z-index:2147483647;background:#1e2230;color:#fff;font:14px sans-serif;padding:10px;border-radius:12px;box-shadow:0 4px 18px rgba(0,0,0,.45);width:220px;max-height:85vh;overflow:auto;touch-action:none;line-height:1.7';
p.innerHTML='<div data-h style="font-weight:bold;cursor:move;user-select:none;display:flex;align-items:center;gap:4px;min-height:34px">'+
'<span style="flex:1;white-space:nowrap">&#9776; 自動收成 <span data-ms style="font-size:12px"></span> <span data-vl style="font-weight:normal;font-size:11px;opacity:.6">v__VER__</span></span>'+
'<span data-hb data-mn title="收起（繼續執行）" style="cursor:pointer;font-size:18px;line-height:1;padding:10px 14px;border-radius:8px;background:#2d3346">&#8211;</span>'+
'<span data-hb data-x title="關閉（停止全部）" style="cursor:pointer;font-size:18px;line-height:1;padding:10px 14px;border-radius:8px;background:#3a2d36">&#10005;</span></div>'+
'<div data-body>'+
'<label>間隔(秒) <input data-iv type="number" min="1" style="width:80px;font-size:14px"></label><br>'+
'<label title="從資源列讀每小時產量，在金幣或建材快滿（90%）之前才收"><input type="checkbox" data-sm> 聰明間隔（快滿前才收）</label><br>'+
'<label><input type="radio" name="cracm" value="auto"> 自動找「收成」按鈕</label><br>'+
'<label><input type="radio" name="cracm" value="pos"> 點自訂位置</label> <button data-pk style="font-size:13px">選位置</button><br>'+
'<button data-go style="width:100%;margin-top:4px;padding:7px;font-size:15px;font-weight:bold;border:0;border-radius:8px;background:#ffc93c;color:#222">開始</button>'+
'<div data-s style="font-size:12px;opacity:.85;margin-top:4px">未開始</div>'+
'<div style="border-top:1px solid #3a4052;margin-top:6px;padding-top:4px"><div data-bt style="font-weight:bold;cursor:pointer;user-select:none">&#128722; 自動購買 <span data-ba>&#9662;</span></div>'+
'<div data-bb style="display:none"><div data-bl style="max-height:150px;overflow:auto;font-size:13px;margin:2px 0"></div>'+
'<button data-br style="font-size:13px">讀取商品</button> <button data-b1 style="font-size:13px">立即買一次</button><br>'+
'<label><input type="radio" name="cracb" value="restock"> 每次補貨後買</label><br>'+
'<label><input type="radio" name="cracb" value="min"> 每 <input data-bm type="number" min="1" style="width:52px;font-size:14px"> 分鐘檢查</label><br>'+
'<button data-bg style="width:100%;margin-top:4px;padding:6px;font-size:14px;font-weight:bold;border:0;border-radius:8px;background:#8fd3ff;color:#222">開始自動購買</button>'+
'<div data-bs style="font-size:12px;opacity:.85;margin-top:4px">勾選要買的商品後按開始</div></div></div>'+
'<div style="border-top:1px solid #3a4052;margin-top:6px;padding-top:4px"><div data-xt style="font-weight:bold;cursor:pointer;user-select:none">&#9881;&#65039; 領取與提醒 <span data-xa>&#9662;</span></div>'+
'<div data-xb style="display:none;font-size:13px">'+
'<label><input type="checkbox" data-cl> 自動領取任務／成就／補給</label><br>每 <input data-clm type="number" min="5" style="width:52px;font-size:14px"> 分鐘 <button data-cl1 style="font-size:13px">立即領取</button><br>'+
'<label><input type="checkbox" data-en> 能量快滿時提醒</label> 達 <input data-enp type="number" min="10" max="100" style="width:46px;font-size:14px">%<br>'+
'Discord Webhook（選填）<input data-wh placeholder="https://discord.com/api/webhooks/…" style="width:100%;font-size:12px;box-sizing:border-box">'+
'<button data-nt style="font-size:13px;margin-top:4px">測試通知</button>'+
'<div data-xs style="font-size:12px;opacity:.85;margin-top:4px"></div></div></div></div>';
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
if(c.mode=='auto'){var b=findBtn();if(b){var tx=b.textContent.trim();b.click();n++;last='已收成 '+tx;return true;}else{last='目前沒有可收成';}}
else{var x=c.x*innerWidth/100,y=c.y*innerHeight/100;p.style.visibility='hidden';var el=document.elementFromPoint(x,y);p.style.visibility='';if(el){fire(el,x,y);n++;last='已點位置';return true;}else last='位置沒有元素';}
return false;}
function num(s){s=String(s).replace(/,/g,'').trim();var k=1;if(/[kK]$/.test(s)){k=1e3;s=s.slice(0,-1);}else if(/[mM]$/.test(s)){k=1e6;s=s.slice(0,-1);}else if(/萬$/.test(s)){k=1e4;s=s.slice(0,-1);}return (parseFloat(s)||0)*k;}
function resInfo(kw){var el=document.querySelector('[title^="'+kw+'・每小時產出"]');if(!el)return null;var a=/每小時產出\s*([\d,.]+[kKmM萬]?)/.exec(el.title),b=/累積到\s*([\d,.]+[kKmM萬]?)/.exec(el.title);return a&&b?{rate:num(a[1]),cap:num(b[1])}:null;}
function pendingNow(){var b=findBtn();if(!b)return [0,0];var m=/\+\s*([\d,.]+[kKmM萬]?)\s*\/\s*([\d,.]+[kKmM萬]?)/.exec(b.textContent);return m?[num(m[1]),num(m[2])]:[0,0];}
var smartWho='';
function smartDelay(empty){var pd=empty?[0,0]:pendingNow(),best=null;[['金幣',0],['建材',1]].forEach(function(a){var r=resInfo(a[0]);if(!r||r.rate<=0||r.cap<=0)return;var h=(r.cap*0.9-pd[a[1]])/r.rate;if(best===null||h<best){best=h;smartWho=a[0];}});
if(best===null)return null;return Math.min(3*3600e3,Math.max(60e3,best*3600e3));}
function nextDelay(harvested){if(c.smart&&c.mode=='auto'){var d=smartDelay(harvested);if(d!==null)return d;}return c.iv*1000;}
function arm(harvested){clearTimeout(t);var d=nextDelay(harvested);next=Date.now()+d;t=setTimeout(function(){arm(doClick());},d);upd();}
function upd(){var s=Math.max(0,Math.ceil((next-Date.now())/1000)),mm=Math.floor(s/60)+':'+('0'+s%60).slice(-2);
q('data-s').textContent=(t?'執行中 · 下次 '+(s>=60?mm:s+' 秒')+(c.smart&&c.mode=='auto'&&smartWho?'（聰明間隔，'+smartWho+'先滿）':''):'已停止')+' · 共 '+n+' 次'+(last?' · '+last:'');}
function start(){if(t)return;c.run=true;save();var g=q('data-go');g.textContent='停止';g.style.background='#ff6b6b';t=-1;arm(doClick());tick=setInterval(upd,1000);upd();}
function stop(){c.run=false;save();clearTimeout(t);clearInterval(tick);t=null;var g=q('data-go');g.textContent='開始';g.style.background='#ffc93c';upd();}
q('data-go').onclick=function(){t?stop():start();};
q('data-x').onclick=function(){stop();c.closed=true;save();p.style.display='none';mk.style.display='none';};
function setMin(v){c.min=!!v;save();q('data-body').style.display=v?'none':'';p.style.width=v?'auto':'220px';
q('data-mn').innerHTML=v?'&#9634;':'&#8211;';q('data-mn').title=v?'展開':'收起（繼續執行）';q('data-vl').style.display=v?'none':'';}
q('data-mn').onclick=function(){setMin(!c.min);place();};
q('data-pk').onclick=function(){var ov=document.createElement('div');
ov.style.cssText='position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.35);color:#fff;font:bold 20px sans-serif;display:flex;align-items:center;justify-content:center;text-align:center;touch-action:none';
ov.textContent='點一下要自動點擊的位置';document.body.appendChild(ov);
ov.addEventListener('pointerdown',function(e){e.preventDefault();e.stopPropagation();c.x=e.clientX/innerWidth*100;c.y=e.clientY/innerHeight*100;c.mode='pos';
for(var j=0;j<rs.length;j++)rs[j].checked=rs[j].value=='pos';save();showMk();setTimeout(function(){ov.remove();},50);},{once:true});};
var hd=q('data-h'),dx=0,dy=0,dr=false;
hd.addEventListener('pointerdown',function(e){if(e.target.closest&&e.target.closest('[data-hb]'))return;dr=true;dx=e.clientX-c.px;dy=e.clientY-c.py;hd.setPointerCapture(e.pointerId);});
hd.addEventListener('pointermove',function(e){if(!dr)return;c.px=e.clientX-dx;c.py=e.clientY-dy;place();});
hd.addEventListener('pointerup',function(){dr=false;save();});
if(!c.buy)c.buy=[];if(!c.items)c.items=[];if(!c.bmode)c.bmode='restock';if(!c.bmin)c.bmin=10;
var B={on:false,t:null,busy:false,log:'',next:0,at:0};
function sleep(ms){return new Promise(function(r){setTimeout(r,ms);});}
function waitFor(fn,ms){return new Promise(function(res){try{if(fn()){res(true);return;}}catch(e){}var done=false,tm=null;
var ob=new MutationObserver(function(){try{if(!done&&fn()){done=true;ob.disconnect();clearTimeout(tm);res(true);}}catch(e){}});
ob.observe(document.body,{subtree:true,childList:true,attributes:true,characterData:true});
tm=setTimeout(function(){if(!done){done=true;ob.disconnect();var v=false;try{v=!!fn();}catch(e){}res(v);}},ms||8000);});}
function stockText(nm){var cd=findCard(nm);if(!cd)return 'gone';var li=cd.btn.closest('li');return (li?li.textContent:'')+'|'+cd.btn.disabled;}
function tabSel(t){return t&&t.getAttribute('aria-selected')=='true';}
function shopDlg(){var ds=document.querySelectorAll('[role=dialog]');for(var i=0;i<ds.length;i++){var h=ds[i].querySelector('h1,h2,h3');if(h&&h.textContent.trim()=='商店')return ds[i];}return null;}
function byText(sel,txt,root){var a=(root||document).querySelectorAll(sel);for(var i=0;i<a.length;i++){if(!p.contains(a[i])&&a[i].textContent.trim().indexOf(txt)==0)return a[i];}return null;}
async function openShop(){var d=shopDlg();if(d){await waitFor(shopReady,8000);return{opened:false};}var t0=byText('[role=tab]','商店');if(t0){t0.click();if(await waitFor(shopDlg,5000)){await waitFor(shopReady,8000);return{opened:false};}}var b=byText('button','物品');if(!b)return null;b.click();
await waitFor(function(){return shopDlg()||byText('[role=tab]','商店');},6000);if(!shopDlg()){var t=byText('[role=tab]','商店');if(t){t.click();await waitFor(shopDlg,6000);}}if(!shopDlg())return null;await waitFor(shopReady,8000);return{opened:true};}
function shopReady(){var d=shopDlg();return !!d&&(cards().length>0||/暫停營業|沒有商品/.test(d.textContent));}
function closeShop(){var d=shopDlg();if(!d)return;var x=d.querySelector('button[title^="關閉"],button[aria-label^="關閉"]');if(x)x.click();}
function cards(){var d=shopDlg(),out=[];if(!d)return out;var bs=d.querySelectorAll('button');for(var i=0;i<bs.length;i++){if(bs[i].textContent.trim()!='購買')continue;var li=bs[i].closest('li');var q=li&&li.querySelector('p');if(!q)continue;var nm='';for(var j=0;j<q.childNodes.length;j++){if(q.childNodes[j].nodeType==3)nm+=q.childNodes[j].textContent;}nm=nm.trim();var m=/庫存\s*[×x]\s*(\d+)/.exec(li.textContent);if(nm)out.push({name:nm,btn:bs[i],stock:m?+m[1]:1});}return out;}
function findCard(nm){var cs=cards();for(var i=0;i<cs.length;i++){if(cs[i].name==nm)return cs[i];}return null;}
async function eachCat(fn){var d=shopDlg();var tl=d&&(d.querySelector('[role=tablist][aria-label="商店分類"]')||d.querySelectorAll('[role=tablist]')[1]);var n=tl?tl.querySelectorAll('[role=tab]').length:0;if(!n){await fn();return;}
for(var i=0;i<n;i++){d=shopDlg();if(!d)return;tl=d.querySelector('[role=tablist][aria-label="商店分類"]')||d.querySelectorAll('[role=tablist]')[1];if(!tl)return;var tb=tl.querySelectorAll('[role=tab]')[i];var was=tabSel(tb);tb.click();
await waitFor(function(){var dd=shopDlg();var ll=dd&&(dd.querySelector('[role=tablist][aria-label="商店分類"]')||dd.querySelectorAll('[role=tablist]')[1]);var t2=ll&&ll.querySelectorAll('[role=tab]')[i];return !t2||tabSel(t2)||(was&&t2);},5000);
await waitFor(shopReady,6000);await fn();}}
function restockAt(){var d=shopDlg();var m=d&&/下次補貨\s*(\d+(?::\d+)+)/.exec(d.textContent);if(!m)return 0;var s=0,a=m[1].split(':');for(var i=0;i<a.length;i++)s=s*60+(+a[i]);return Date.now()+s*1000+5000;}
async function buyRun(){if(B.busy||(typeof X!='undefined'&&X.busy))return;B.busy=true;bupd();var got=[];try{var o=await openShop();if(!o){B.log='打不開商店（先關掉其他視窗）';return;}
await eachCat(async function(){var cs=cards();for(var i=0;i<cs.length;i++){var nm=cs[i].name;if(c.buy.indexOf(nm)<0)continue;var k=0,cap=Math.max(1,cs[i].stock);
while(k<cap){var cd=findCard(nm);if(!cd||cd.btn.disabled)break;var before=stockText(nm);cd.btn.click();k++;
await waitFor(function(){var s=stockText(nm);return s!=before&&!/\|true$/.test(s)||s=='gone'||(s!=before&&!/庫存/.test(s));},10000);}if(k)got.push(nm+' ×'+k);}});
B.next=restockAt();if(o.opened)closeShop();B.log=got.length?'買到 '+got.join('、'):'沒有可買的（缺貨或已買完）';}
catch(e){B.log='錯誤：'+e.message;}finally{B.busy=false;bupd();}}
async function scanItems(){if(B.busy)return;B.busy=true;B.log='讀取中…';bupd();try{var o=await openShop();if(!o){B.log='打不開商店';return;}var names=[];
await eachCat(async function(){var cs=cards();for(var i=0;i<cs.length;i++)if(names.indexOf(cs[i].name)<0)names.push(cs[i].name);});
B.next=restockAt();if(o.opened)closeShop();if(names.length){c.items=names;save();}B.log='讀到 '+names.length+' 樣商品';}catch(e){B.log='錯誤：'+e.message;}finally{B.busy=false;renderList();bupd();}}
function renderList(){var l=q('data-bl');l.innerHTML='';if(!c.items.length){l.textContent='按「讀取商品」載入商店清單';return;}
c.items.forEach(function(nm){var lb=document.createElement('label');lb.style.display='block';var cb=document.createElement('input');cb.type='checkbox';cb.checked=c.buy.indexOf(nm)>=0;
cb.onchange=function(){var i=c.buy.indexOf(nm);if(cb.checked&&i<0)c.buy.push(nm);if(!cb.checked&&i>=0)c.buy.splice(i,1);save();};lb.appendChild(cb);lb.appendChild(document.createTextNode(' '+nm));l.appendChild(lb);});}
function bsched(){clearTimeout(B.t);if(!B.on)return;var ms=(c.bmode=='restock'&&B.next>Date.now())?B.next-Date.now():c.bmin*60000;B.at=Date.now()+ms;
B.t=setTimeout(function(){buyRun().then(bsched);},ms);bupd();}
function bupd(){var g=q('data-bg');g.textContent=B.on?'停止自動購買':'開始自動購買';g.style.background=B.on?'#ff6b6b':'#8fd3ff';
var s=Math.max(0,Math.ceil((B.at-Date.now())/1000));q('data-bs').textContent=(B.busy?'購買中…':B.on?'執行中 · 下次 '+Math.floor(s/60)+':'+('0'+s%60).slice(-2):'已停止')+(B.log?' · '+B.log:'');}
q('data-bt').onclick=function(){var bb=q('data-bb'),o=bb.style.display=='none';bb.style.display=o?'':'none';q('data-ba').innerHTML=o?'&#9652;':'&#9662;';};
q('data-br').onclick=scanItems;q('data-b1').onclick=function(){buyRun();};
var bm=q('data-bm');bm.value=c.bmin;bm.onchange=function(){c.bmin=Math.max(1,parseFloat(bm.value)||10);bm.value=c.bmin;save();if(B.on)bsched();};
var brs=p.querySelectorAll('input[name=cracb]');for(var bi=0;bi<brs.length;bi++){(function(r){r.checked=r.value==c.bmode;r.onchange=function(){c.bmode=r.value;save();if(B.on)bsched();};})(brs[bi]);}
function bstop(){B.on=false;c.bon=false;save();clearTimeout(B.t);bupd();}
q('data-bg').onclick=function(){if(B.on){bstop();return;}if(!c.buy.length){B.log='先勾選要買的商品';bupd();return;}B.on=true;c.bon=true;save();buyRun().then(bsched);};
setInterval(function(){if(B.on||B.busy)bupd();},1000);renderList();bupd();
var oldX=q('data-x').onclick;q('data-x').onclick=function(){bstop();oldX();};
var sm=q('data-sm');sm.checked=!!c.smart;sm.onchange=function(){c.smart=sm.checked;save();if(t)arm(false);};
if(!c.clm)c.clm=30;if(!c.enp)c.enp=95;
var X={busy:false,t:null,log:'',enSent:false};
function xupd(){q('data-xs').textContent=X.busy?'領取中…':X.log;}
function dlgWithTab(name){var ds=document.querySelectorAll('[role=dialog]');for(var i=0;i<ds.length;i++){var ts=ds[i].querySelectorAll('[role=tab]');for(var j=0;j<ts.length;j++)if(ts[j].textContent.trim().indexOf(name)==0)return ds[i];}return null;}
function claimBtns(d){var out=[];if(!d)return out;var bs=d.querySelectorAll('button');for(var i=0;i<bs.length;i++){if(!bs[i].disabled&&bs[i].textContent.trim()=='領取'&&!p.contains(bs[i]))out.push(bs[i]);}return out;}
async function claimAll(){if(X.busy||B.busy)return;X.busy=true;xupd();var got=0;try{var opened=false;
if(!dlgWithTab('成就')){var b=byText('button','任務');if(!b){X.log='找不到「任務」按鈕';return;}b.click();opened=true;await waitFor(function(){return dlgWithTab('成就');},6000);}
var d=dlgWithTab('成就');if(!d){X.log='打不開任務視窗（先關掉其他視窗）';return;}
var tabs=['任務','成就'];for(var ti=0;ti<tabs.length;ti++){d=dlgWithTab('成就');if(!d)break;var tb=byText('[role=tab]',tabs[ti],d);if(tb&&!tabSel(tb)){tb.click();await waitFor(function(){var x=byText('[role=tab]',tabs[ti],dlgWithTab('成就'));return tabSel(x);},4000);}
await waitFor(function(){var dd=dlgWithTab('成就');return dd&&/領取|已完成|未完成|\d+\s*\/\s*\d+/.test(dd.textContent);},4000);
for(var k=0;k<40;k++){var bs=claimBtns(dlgWithTab('成就'));if(!bs.length)break;var btn=bs[0],before=btn.closest('li,div').textContent;btn.click();got++;
await waitFor(function(){return !document.contains(btn)||btn.textContent.trim()!='領取'||(!btn.disabled&&btn.closest('li,div').textContent!=before);},8000);}}
if(opened){var dd=dlgWithTab('成就');var x=dd&&dd.querySelector('button[title^="關閉"],button[aria-label^="關閉"]');if(x)x.click();}
X.log=new Date().toTimeString().slice(0,5)+' '+(got?'領取了 '+got+' 個獎勵':'沒有可以領的');}catch(e){X.log='錯誤：'+e.message;}finally{X.busy=false;xupd();}}
function clSched(){clearTimeout(X.t);if(!c.cl)return;var ms=Math.max(5,c.clm)*60000;X.at=Date.now()+ms;X.t=setTimeout(function(){claimAll().then(clSched);},ms);}
function energy(){var el=document.querySelector('[title^="能量"]');if(!el)return null;var m=/([\d,]+)\s*\/\s*([\d,]+)/.exec(el.textContent);return m?{cur:num(m[1]),max:num(m[2])}:null;}
function notify(tt,body){var ok=false;try{if(window.CRAndroid&&CRAndroid.notify){CRAndroid.notify(tt,body);ok=true;}else if('Notification' in window&&Notification.permission=='granted'){new Notification(tt,{body:body});ok=true;}}catch(e){}
if(c.wh&&/^https:\/\/(canary\.|ptb\.)?(discord|discordapp)\.com\/api\/webhooks\//.test(c.wh)){var fd=new FormData();fd.append('content','**'+tt+'** '+body);fetch(c.wh,{method:'POST',mode:'no-cors',body:fd}).catch(function(){});ok=true;}
X.log=new Date().toTimeString().slice(0,5)+(ok?' 已通知：'+tt:' 沒有可用的通知方式（允許瀏覽器通知或填 Webhook）');xupd();return ok;}
function askPerm(){try{if(!window.CRAndroid&&'Notification' in window&&Notification.permission=='default')Notification.requestPermission();}catch(e){}}
function checkEnergy(){if(!c.en)return;var e=energy();if(!e||!e.max)return;var pct=e.cur/e.max*100;if(pct>=c.enp){if(!X.enSent){X.enSent=true;notify('知識領土：能量快滿了','目前 '+e.cur+'/'+e.max+'，回來答題吧！');}}else if(pct<c.enp-5)X.enSent=false;}
setInterval(checkEnergy,30000);
q('data-xt').onclick=function(){var bb=q('data-xb'),o=bb.style.display=='none';bb.style.display=o?'':'none';q('data-xa').innerHTML=o?'&#9652;':'&#9662;';};
var cl=q('data-cl'),clm=q('data-clm'),en=q('data-en'),enp=q('data-enp'),wh=q('data-wh');
cl.checked=!!c.cl;clm.value=c.clm;en.checked=!!c.en;enp.value=c.enp;wh.value=c.wh||'';
cl.onchange=function(){c.cl=cl.checked;save();if(c.cl){claimAll().then(clSched);}else clearTimeout(X.t);};
clm.onchange=function(){c.clm=Math.max(5,parseFloat(clm.value)||30);clm.value=c.clm;save();clSched();};
en.onchange=function(){c.en=en.checked;save();X.enSent=false;if(c.en){askPerm();checkEnergy();}};
enp.onchange=function(){c.enp=Math.min(100,Math.max(10,parseFloat(enp.value)||95));enp.value=c.enp;save();X.enSent=false;};
wh.onchange=function(){c.wh=wh.value.trim();save();};
q('data-cl1').onclick=function(){claimAll();};
q('data-nt').onclick=function(){askPerm();setTimeout(function(){notify('測試通知','CR Rank 自動收成器的通知可以用了 ✅');},300);};
if(c.cl)setTimeout(function(){claimAll().then(clSched);},10000);
if(c.run)setTimeout(start,1500);
if(c.bon&&c.buy.length)setTimeout(function(){if(!B.on){B.on=true;B.log='自動接續';buyRun().then(bsched);}},4000);
/* 喚醒：擴充功能每 30 秒叫一次，把被背景節流拖延的工作補做 */
function wake(){var now=Date.now();p.setAttribute('data-last-tick',String(now));
if(t&&t!==-1&&next&&now>=next+1000)arm(doClick());
if(B.on&&!B.busy&&B.at&&now>=B.at+1000){clearTimeout(B.t);buyRun().then(bsched);}
if(c.cl&&!X.busy&&X.at&&now>=X.at+1000){clearTimeout(X.t);claimAll().then(clSched);}
checkEnergy();}
function mini(){var on=!!t||B.on||c.cl;q('data-ms').textContent=c.min?(on?'🟢':'⚪'):'';}
setInterval(mini,1000);
if(c.closed){c.closed=false;c.min=true;}  /* 關掉後重新載入：只顯示收起的小條，不擋畫面 */
setMin(!!c.min);mini();
window.__crac={show:function(){c.closed=false;p.style.display='';setMin(false);place();showMk();},tick:wake,
ensureHarvest:function(){if(t)return;c.mode='auto';for(var j=0;j<rs.length;j++)rs[j].checked=rs[j].value=='auto';start();},
stopHarvest:function(){if(t)stop();}};
})();
"""


MOBILE_JS = MOBILE_JS.replace("__VER__", APP_VERSION)


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
details{background:#262c3e;border-radius:10px;padding:8px 12px;margin:10px 0}
summary{font-weight:bold;font-size:16px;cursor:pointer;padding:4px 0}
.step{display:flex;gap:10px;margin:12px 0;align-items:flex-start}
.n{flex:none;width:26px;height:26px;border-radius:50%;background:#ffc93c;color:#222;font-weight:bold;text-align:center;line-height:26px}
.mock{background:#f2f2f7;color:#222;border-radius:12px;padding:8px 10px;margin-top:6px;font-size:13px}
.bar{display:flex;justify-content:space-around;align-items:center;background:#fff;border-radius:10px;padding:6px 0;margin-top:6px}
.bar svg{width:24px;height:24px;stroke:#007aff;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.hl{outline:3px solid #ff9f0a;outline-offset:3px;border-radius:6px}
.row{display:flex;justify-content:space-between;background:#fff;border-radius:8px;padding:7px 10px;margin-top:4px}
.blue{color:#007aff}.k{background:#ffc93c33;border-radius:4px;padding:0 4px;color:#ffd66b}
.mock .k{color:#b06d00;background:#ffc93c55}
</style></head><body>
<h1>CR Rank 自動收成 · 手機</h1>
<h2>方法一：在手機瀏覽器裡自動點（推薦）</h2>
<div class="card">
<p>先按這個按鈕複製書籤碼，再照你的手機選下面的教學：</p>
<button onclick="cp()">📋 複製書籤碼</button>
<textarea id="bm" readonly>__BM__</textarea>

<details id="ios"><summary>🍎 iPhone / iPad（Safari）教學</summary>
<div class="step"><div class="n">1</div><div>按上面的 <span class="k">📋 複製書籤碼</span>。如果跳出「請手動複製」，就長按文字框 → 全選 → 拷貝。</div></div>
<div class="step"><div class="n">2</div><div>在 Safari 開著這一頁，點下方的 <b>分享</b> 按鈕，選 <b>加入書籤</b> → 右上角 <b>儲存</b>。
<div class="mock">Safari 下方工具列
<div class="bar"><svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg><svg viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></svg>
<span class="hl"><svg viewBox="0 0 24 24"><path d="M12 3v12M8 7l4-4 4 4M5 11v9h14v-9"/></svg></span>
<svg viewBox="0 0 24 24"><path d="M3 5h7a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H3zM21 5h-7a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h7z"/></svg>
<svg viewBox="0 0 24 24"><rect x="4" y="4" width="12" height="12" rx="2"/><path d="M8 20h10a2 2 0 0 0 2-2V8"/></svg></div>
<div class="row"><span>加入書籤</span><span class="blue">📖</span></div></div></div></div>
<div class="step"><div class="n">3</div><div>點 <b>書籤</b> 按鈕（打開的書）→ 右下角 <b>編輯</b> → 點剛剛新增的那個書籤。
<div class="mock"><div class="bar"><svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg><svg viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></svg>
<svg viewBox="0 0 24 24"><path d="M12 3v12M8 7l4-4 4 4M5 11v9h14v-9"/></svg>
<span class="hl"><svg viewBox="0 0 24 24"><path d="M3 5h7a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H3zM21 5h-7a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h7z"/></svg></span>
<svg viewBox="0 0 24 24"><rect x="4" y="4" width="12" height="12" rx="2"/><path d="M8 20h10a2 2 0 0 0 2-2V8"/></svg></div>
<div class="row"><span>自動收成 · 手機</span><span class="blue">›</span></div>
<div style="text-align:right;margin-top:4px" class="blue"><span class="hl">編輯</span></div></div></div></div>
<div class="step"><div class="n">4</div><div>把<b>名稱</b>改成 <span class="k">收成</span>；把<b>網址</b>那一格<b>全部刪掉</b>，長按 → <b>貼上</b>剛剛複製的書籤碼（開頭是 <span class="k">javascript:</span>）→ 完成。
<div class="mock"><div class="row"><span>收成</span></div><div class="row" style="color:#888">javascript:(function(){if(window.__crac…</div></div></div></div>
<div class="step"><div class="n">5</div><div>打開 <a href="https://crrank.xpgs25.com/game" target="_blank">知識領土遊戲頁</a> 並登入 → 點 <b>書籤</b> 按鈕 → 點 <span class="k">收成</span>，畫面左上就會出現「自動收成」面板。設定間隔、選「自動找收成按鈕」或「點自訂位置」，按 <b>開始</b>。</div></div>
<div class="step"><div class="n">6</div><div><b>重要：</b>iPhone 鎖定畫面或切到別的 App 時，Safari 會暫停計時。請到 <b>設定 → 螢幕顯示與亮度 → 自動鎖定 → 永不</b>，並讓遊戲分頁停在畫面上（可以把亮度調低省電）。</div></div>
<p style="font-size:13px;opacity:.85"><b>想要每次進遊戲自動出現面板？</b>到 App Store 安裝免費的「<b>Userscripts</b>」→ 到 設定 → App → Safari → 延伸功能（舊版 iOS：設定 → Safari → 延伸功能）開啟 Userscripts，並允許所有網站 → 用 Safari 開
<a href="/crrank.user.js">使用者腳本</a> → 點網址列旁的 <b>ᴀA</b> / 拼圖按鈕 → Userscripts → <b>安裝</b>。</p>
</details>

<details id="android"><summary>🤖 Android（Chrome）教學</summary>
<div class="step"><div class="n">1</div><div>按上面的 <span class="k">📋 複製書籤碼</span>。</div></div>
<div class="step"><div class="n">2</div><div>點右上角 <b>⋮</b> → <b>☆</b> 把這頁加入書籤 → 點下方出現的 <b>編輯</b>，名稱改成 <span class="k">收成</span>，網址整個換成剛複製的內容。</div></div>
<div class="step"><div class="n">3</div><div>打開 <a href="https://crrank.xpgs25.com/game" target="_blank">知識領土遊戲頁</a> 並登入 → 在<b>網址列輸入「收成」</b>，點選下面出現的書籤那一項，面板就會出現。</div></div>
<p style="font-size:13px;opacity:.85">也可以安裝 Android App（GitHub Release 的 CRRank-AutoHarvest.apk），或在 Firefox／Kiwi／Edge 裝 Tampermonkey 後安裝
<a href="/crrank.user.js">使用者腳本</a>。手機請保持螢幕亮著、遊戲分頁在前景。</p>
</details>
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
(function(){var ua=navigator.userAgent,ios=/iPhone|iPad|iPod/.test(ua)||(/Macintosh/.test(ua)&&navigator.maxTouchPoints>1);
document.getElementById(ios?'ios':(/Android/.test(ua)?'android':'ios')).open=true;})();
function cp(){var t=document.getElementById('bm');t.removeAttribute('readonly');t.contentEditable=true;t.focus();
var r=document.createRange();r.selectNodeContents(t);var s=window.getSelection();s.removeAllRanges();s.addRange(r);
t.select();t.setSelectionRange(0,t.value.length);
var ok=false;try{ok=document.execCommand('copy');}catch(e){}
t.setAttribute('readonly','');t.contentEditable=false;t.blur();
if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t.value);ok=true;}
alert(ok?'已複製！請照下面的教學新增書籤並貼到網址欄。':'請長按文字框 → 全選 → 拷貝');}
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
        self.smart_fn = None

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
            self.next_at = time.time() + 5
            self.next_at = time.time() + self._wait(after_click=True)
            if self.stop_evt.wait(max(0, self.next_at - time.time())):
                return

    def _wait(self, after_click=False):
        j = float(self.s.get("jitter") or 0)
        base = None
        if self.s.get("auto_rate") and self.smart_fn:
            base = self.smart_fn(after_click)  # 自動判斷：讀遊戲畫面算出快滿前的時間
        if base is None:
            base = self.interval_sec()
        return max(0.1, base + (random.uniform(-j, j) if j else 0))

    def status(self):
        return {"running": self.running, "count": self.count, "x": self.s["x"], "y": self.s["y"],
                "interval": self.s["interval"], "unit": self.s["unit"],
                "next_in": max(0, int(round(self.next_at - time.time()))) if self.running else 0}


class BuyRunner:
    """自動購買：照順序點擊步驟（打開物品→商店→分類→購買→關閉），在每次補貨後或每 N 分鐘執行。"""

    def __init__(self, settings):
        self.s = settings
        self.running = False
        self.busy = False
        self.runs = 0
        self.next_at = 0.0
        self.log = ""
        self.stop_evt = threading.Event()
        self.thread = None
        self.on_change = lambda: None

    def next_time(self):
        now = time.time()
        if self.s.get("buy_mode") == "restock":
            base = (int(now) // RESTOCK_SEC + 1) * RESTOCK_SEC
            return base + float(self.s.get("buy_offset") or 0)
        return now + max(1.0, float(self.s.get("buy_every") or 30)) * 60

    def run_once(self, check_stop=False):
        if self.busy:
            return
        slots = self.s.get("buy_slots") or []

        def ready(sl):
            return [st for st in sl.get("steps", []) if st.get("x") is not None]

        if self.s.get("buy_rotate"):  # 自動輪播：存檔1 做完接存檔2、存檔3…
            order = [sl for sl in slots if ready(sl)]
        else:
            cur = slots[int(self.s.get("buy_slot", 0))] if slots else {"steps": []}
            order = [cur] if ready(cur) else []
        if not order:
            self.log = "沒有設定好位置的步驟"
            self.on_change()
            return
        self.busy = True
        self.on_change()
        restore = self.s.get("restore", True)
        try:
            done = []
            for sl in order:
                self.current = sl.get("name", "")
                self.on_change()
                for st in ready(sl):
                    times = max(1, int(st.get("times", 1)))
                    for i in range(times):
                        if check_stop and self.stop_evt.is_set():
                            self.log = "已中途停止"
                            return
                        if st.get("type") == "scroll":
                            scroll_at(st["x"], st["y"], st.get("dir", "down") == "down", st.get("amount", 3), restore)
                        else:
                            click_at(st["x"], st["y"], restore)
                        if i < times - 1:
                            time.sleep(1.0)
                    time.sleep(max(0.1, float(st.get("wait", 1.0))))
                done.append(sl.get("name", ""))
            self.runs += 1
            self.log = time.strftime("%H:%M:%S") + " 已執行 " + "→".join(done)
        finally:
            self.busy = False
            self.on_change()

    def start(self):
        if self.running:
            return
        self.running = True
        self.stop_evt.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.on_change()

    def stop(self):
        self.running = False
        self.stop_evt.set()
        self.on_change()

    def _loop(self):
        if self.s.get("buy_now", True):
            self.run_once(True)
        while not self.stop_evt.is_set():
            self.next_at = self.next_time()
            self.on_change()
            if self.stop_evt.wait(max(0, self.next_at - time.time())):
                return
            self.run_once(True)

    def status(self):
        if self.busy:
            return f"購買中…（{getattr(self, 'current', '')}）"
        if not self.running:
            return "已停止" + (f" · {self.log}" if self.log else "")
        s = max(0, int(self.next_at - time.time()))
        return f"執行中 · 下次 {time.strftime('%H:%M:%S', time.localtime(self.next_at))}（{s // 60}:{s % 60:02d} 後）" \
               + f" · 已買 {self.runs} 輪"


def ver_tuple(v):
    import re
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3])


def fetch_latest_release():
    import urllib.request
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                 headers={"User-Agent": "CRRank-AutoHarvest", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def finish_update_if_requested():
    """自我更新的後半段：新版 exe 從暫存資料夾啟動，等舊程式關掉後把自己複製過去再重新開啟。"""
    import shutil
    import subprocess
    argv = sys.argv
    if "--finish-update" in argv:
        i = argv.index("--finish-update")
        target, pid = argv[i + 1], int(argv[i + 2])
        h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if h:
            ctypes.windll.kernel32.WaitForSingleObject(h, 30000)
            ctypes.windll.kernel32.CloseHandle(h)
        for _ in range(20):
            try:
                shutil.copy2(sys.executable, target)
                break
            except OSError:
                time.sleep(0.5)
        subprocess.Popen([target, "--cleanup", sys.executable])
        sys.exit(0)
    if "--cleanup" in argv:
        path = argv[argv.index("--cleanup") + 1]

        def rm():
            for _ in range(15):
                time.sleep(1)
                try:
                    os.remove(path)
                    return
                except OSError:
                    pass
        threading.Thread(target=rm, daemon=True).start()


def smart_interval_minutes(gold_rate, mat_rate, gold_cap=2000, mat_cap=1500, ratio=0.9):
    """依每小時產量算出「快滿（90%）之前」的收成間隔（分鐘）。"""
    hours = [cap * ratio / rate for cap, rate in ((gold_cap, gold_rate), (mat_cap, mat_rate)) if rate > 0]
    return max(1, int(min(hours) * 60)) if hours else None



# ---------- 自動判斷每小時產量：直接讀你開著的遊戲分頁（Windows 輔助功能介面，不用登入、不用擴充功能） ----------
_IACC = None


def _iaccessible():
    global _IACC
    if _IACC is None:
        from ctypes import POINTER, c_int
        from comtypes import BSTR, COMMETHOD, GUID, HRESULT, dispid
        from comtypes.automation import IDispatch, VARIANT

        class IAccessible(IDispatch):
            _iid_ = GUID("{618736E0-3C3D-11CF-810C-00AA00389B71}")
            _methods_ = [
                COMMETHOD([dispid(-5000), "hidden", "propget"], HRESULT, "accParent",
                          (["out", "retval"], POINTER(POINTER(IDispatch)), "p")),
                COMMETHOD([dispid(-5001), "hidden", "propget"], HRESULT, "accChildCount",
                          (["out", "retval"], POINTER(c_int), "p")),
                COMMETHOD([dispid(-5002), "hidden", "propget"], HRESULT, "accChild",
                          (["in"], VARIANT, "v"), (["out", "retval"], POINTER(POINTER(IDispatch)), "p")),
                COMMETHOD([dispid(-5003), "hidden", "propget"], HRESULT, "accName",
                          (["in", "optional"], VARIANT, "v"), (["out", "retval"], POINTER(BSTR), "p")),
                COMMETHOD([dispid(-5004), "hidden", "propget"], HRESULT, "accValue",
                          (["in", "optional"], VARIANT, "v"), (["out", "retval"], POINTER(BSTR), "p")),
                COMMETHOD([dispid(-5005), "hidden", "propget"], HRESULT, "accDescription",
                          (["in", "optional"], VARIANT, "v"), (["out", "retval"], POINTER(BSTR), "p")),
            ]
        _IACC = IAccessible
    return _IACC


def game_num(t):
    t = str(t).replace(",", "").strip()
    mul = 1
    if t[-1:] in ("k", "K"):
        mul, t = 1e3, t[:-1]
    elif t[-1:] in ("m", "M"):
        mul, t = 1e6, t[:-1]
    elif t[-1:] == "萬":
        mul, t = 1e4, t[:-1]
    return float(t) * mul


_RE_RATE = re.compile(r"(金幣|建材)・每小時產出\s*([\d,.]+[kKmM萬]?)(?:.*?累積到\s*([\d,.]+[kKmM萬]?))?")
_RE_PEND = re.compile(r"收成\s*\+\s*([\d,.]+[kKmM萬]?)\s*/\s*([\d,.]+[kKmM萬]?)")


def parse_game_texts(texts):
    """從畫面文字找出每小時產量、上限和還沒收成的數量。"""
    st = {}
    for t in texts:
        m = _RE_RATE.search(t)
        if m:
            key = "gold" if m.group(1) == "金幣" else "mat"
            cap = game_num(m.group(3)) if m.group(3) else (2000 if key == "gold" else 1500)
            st.setdefault(key, {"rate": game_num(m.group(2)), "cap": cap})
            continue
        m = _RE_PEND.search(t)
        if m and "pending" not in st:
            st["pending"] = (game_num(m.group(1)), game_num(m.group(2)))
    return st if ("gold" in st or "mat" in st) else None


BROWSER_EXES = ("chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "vivaldi.exe")


def _chromium_pages():
    """找所有 Chrome／Edge 視窗（含安裝成 App 的網頁），名字像知識領土的排前面。"""
    import ctypes.wintypes as wt
    k32 = ctypes.windll.kernel32
    found = []

    def cls_of(h):
        b = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, b, 64)
        return b.value

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def top(h, l):
        if cls_of(h) != "Chrome_WidgetWin_1" or not user32.IsWindowVisible(h):
            return True
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(h, title, 512)
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        exe = ""
        hp = k32.OpenProcess(0x1000, 0, pid)
        if hp:
            buf, n = ctypes.create_unicode_buffer(300), wt.DWORD(300)
            if k32.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n)):
                exe = os.path.basename(buf.value).lower()
            k32.CloseHandle(hp)
        if exe not in BROWSER_EXES:
            return True
        t = title.value
        pri = 0 if ("知識領土" in t or "CR Rank" in t) else (2 if user32.IsIconic(h) else 1)
        found.append((pri, t, h))  # 直接讀整個視窗（Chrome 會自動打開網頁的輔助功能樹）
        return True

    user32.EnumWindows(top, 0)
    found.sort(key=lambda f: f[0])
    return found


def _acc_texts(hwnd, budget=4.0, limit=6000):
    from comtypes.automation import VARIANT
    IAcc = _iaccessible()
    oleacc = ctypes.oledll.oleacc
    p = ctypes.POINTER(IAcc)()
    oleacc.AccessibleObjectFromWindow(ctypes.c_void_p(hwnd), ctypes.c_long(-4), ctypes.byref(IAcc._iid_), ctypes.byref(p))
    out, end, stack = [], time.time() + budget, [p]
    me = VARIANT(0)
    while stack and len(out) < limit and time.time() < end:
        a = stack.pop()
        for get in ("accName", "accDescription"):
            try:
                v = getattr(a, get)(me)
                if v:
                    out.append(v)
            except Exception:
                pass
        try:
            n = a.accChildCount
        except Exception:
            n = 0
        if n:
            arr, got = (VARIANT * n)(), ctypes.c_long()
            try:
                oleacc.AccessibleChildren(a, 0, n, arr, ctypes.byref(got))
            except Exception:
                continue
            kids = []
            for i in range(got.value):
                v = arr[i].value
                if v is None or isinstance(v, int):
                    continue
                try:
                    kids.append(v.QueryInterface(IAcc))
                except Exception:
                    pass
            stack.extend(reversed(kids))  # 保持文件順序
        if any("每小時產出" in t for t in out) and any(_RE_PEND.search(t) for t in out):
            break
    return out


def read_game_state():
    """讀取開著的知識領土分頁：每小時產量、上限、還沒收成的數量。找不到回傳 None。"""
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        return None
    t_end = time.time() + 8
    for pri, title, hwnd in _chromium_pages():
        if time.time() > t_end:
            break
        try:
            st = parse_game_texts(_acc_texts(hwnd, budget=4.0 if pri == 0 else 1.5))
        except Exception:
            st = None
        if st:
            st["where"] = title
            st["at"] = time.time()
            return st
    return None


def smart_wait_seconds(st, ratio=0.9):
    """離「金幣或建材快滿（90%）」還有幾秒；最少 1 分鐘、最多 6 小時。"""
    if not st:
        return None
    pg, pm = st.get("pending") or (0, 0)
    hours = []
    for key, pend in (("gold", pg), ("mat", pm)):
        r = st.get(key)
        if r and r["rate"] > 0 and r["cap"] > 0:
            hours.append((r["cap"] * ratio - pend) / r["rate"])
    if not hours:
        return None
    return max(60.0, min(6 * 3600.0, min(hours) * 3600))


def describe_state(st):
    if not st:
        return ""
    parts = []
    for key, name in (("gold", "金幣"), ("mat", "建材")):
        r = st.get(key)
        if r:
            parts.append(f"{name} +{int(r['rate'])}/時")
    s = "、".join(parts)
    if st.get("pending"):
        s += f"，未收 {int(st['pending'][0])}/{int(st['pending'][1])}"
    return s


EXT_BACKGROUND_JS = r"""
// 每 30 秒喚醒知識領土分頁上的面板，並防止 Chrome 把分頁卸載（不需要重新登入，用你原本的 Chrome）
const GAME = 'https://crrank.xpgs25.com/*';
function ensureAlarm() {
  chrome.alarms.get('crac-tick', a => { if (!a) chrome.alarms.create('crac-tick', { periodInMinutes: 0.5 }); });
}
chrome.runtime.onInstalled.addListener(ensureAlarm);
chrome.runtime.onStartup.addListener(ensureAlarm);
ensureAlarm();
chrome.alarms.onAlarm.addListener(async a => {
  if (a.name !== 'crac-tick') return;
  const tabs = await chrome.tabs.query({ url: GAME });
  for (const t of tabs) {
    if (t.discarded) { chrome.tabs.reload(t.id).catch(() => {}); continue; }   // 被卸載了就重新載入（面板會自動接續）
    if (t.autoDiscardable) chrome.tabs.update(t.id, { autoDiscardable: false }).catch(() => {});
    chrome.tabs.sendMessage(t.id, { type: 'crac-tick' }).catch(() => {});
  }
});
"""

EXT_README = """CR Rank 自動收成 — Chrome／Edge 擴充功能

用你原本的 Chrome（已經登入的那個），不用重新登入 Discord。
安裝一次就好：
1. Chrome 網址列輸入 chrome://extensions （Edge：edge://extensions）
2. 打開右上角（Edge 在左下）的「開發人員模式」
3. 按「載入未封裝項目」，選這個資料夾
4. 打開或重新整理知識領土，面板會自動出現

之後就算遊戲分頁在背景、被其他視窗蓋住，面板也會繼續收成、購買、領取；
擴充功能每 30 秒會喚醒面板一次，並防止 Chrome 把遊戲分頁卸載。
更新電腦版程式後，到 chrome://extensions 按這個擴充功能的「重新載入」(↻) 就會換成新版面板。
"""


def extension_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", app_dir()), "CRRankAutoHarvest", "chrome-extension")


def write_extension(path=None):
    """產生 Chrome／Edge 擴充功能（MV3）：自動放入面板＋定時喚醒＋防止分頁卸載。"""
    path = path or extension_dir()
    os.makedirs(path, exist_ok=True)
    manifest = {
        "manifest_version": 3,
        "name": "CR Rank 自動收成",
        "version": APP_VERSION,
        "description": "在知識領土頁面自動放入自動收成面板，背景分頁也會繼續運作（非官方玩家工具）。",
        "permissions": ["alarms"],
        "host_permissions": ["https://crrank.xpgs25.com/*"],
        "background": {"service_worker": "background.js"},
        "content_scripts": [{"matches": ["https://crrank.xpgs25.com/*"], "js": ["panel.js"], "run_at": "document_idle"}],
    }
    panel = MOBILE_JS.strip() + "\nchrome.runtime.onMessage.addListener(function(m){if(m&&m.type==='crac-tick'&&window.__crac&&window.__crac.tick)window.__crac.tick();});\n"
    files = {"manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2), "background.js": EXT_BACKGROUND_JS.strip() + "\n",
             "panel.js": panel, "安裝說明.txt": EXT_README}
    for name, text in files.items():
        with open(os.path.join(path, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return path


class BgBrowser:
    """背景模式：開一個專用的 Chrome／Edge 視窗（關掉背景節流），自動把面板放進遊戲頁。
    視窗可以縮小或被蓋住，面板照樣運作；用模擬點擊（點網頁上的按鈕），不需要遊戲畫面在前台。"""

    FLAGS = ["--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows",
             "--disable-renderer-backgrounding",
             "--disable-features=CalculateNativeWinOcclusion,IntensiveWakeUpThrottling",
             "--no-first-run", "--no-default-browser-check"]

    def __init__(self):
        self.proc = None
        self.port = 0
        self.injected = 0
        self.state = "未開啟"
        self.stop_evt = threading.Event()

    @staticmethod
    def find_browser():
        pf = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        cands = [os.path.join(b, r) for b in pf if b for r in (
            r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe")]
        for c in cands:
            if os.path.isfile(c):
                return c
        return None

    @staticmethod
    def profile_dir():
        d = os.path.join(os.environ.get("LOCALAPPDATA", app_dir()), "CRRankAutoHarvest", "browser")
        os.makedirs(d, exist_ok=True)
        return d

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        import subprocess
        if self.running():
            return True
        exe = self.find_browser()
        if not exe:
            self.state = "找不到 Chrome 或 Edge"
            return False
        for p in range(9333, 9353):
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", p)) != 0:
                    self.port = p
                    break
        args = [exe, f"--user-data-dir={self.profile_dir()}", f"--remote-debugging-port={self.port}",
                "--remote-allow-origins=http://127.0.0.1", *self.FLAGS, "--new-window", GAME_URL]
        self.proc = subprocess.Popen(args)
        self.stop_evt.clear()
        self.injected = 0
        self.state = "啟動中…"
        threading.Thread(target=self._watch, daemon=True).start()
        # 背景模式期間不要讓電腦進入睡眠
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        return True

    def stop(self):
        self.stop_evt.set()
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        if self.running():
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None
        self.state = "未開啟"

    def _watch(self):
        import urllib.request
        wrapper = ("(function(){if(window.__crac)return 'skip';var run=function(){" + minify_js(MOBILE_JS) +
                   "};if(document.body)run();else document.addEventListener('DOMContentLoaded',run);return 'ok';})()")
        while not self.stop_evt.wait(3):
            if not self.running():
                self.state = "視窗已關閉"
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
                return
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=3) as r:
                    targets = json.loads(r.read().decode("utf-8"))
            except Exception:
                continue
            pages = [t for t in targets if t.get("type") == "page" and "crrank.xpgs25.com" in t.get("url", "")]
            if not pages:
                self.state = "執行中（請在視窗裡打開知識領土）"
                continue
            for t in pages:
                try:
                    res = cdp_call(t["webSocketDebuggerUrl"], "Runtime.evaluate", {"expression": wrapper})
                    if res.get("result", {}).get("result", {}).get("value") == "ok":
                        self.injected += 1
                except Exception:
                    pass
            self.state = f"執行中 · 面板已放進遊戲頁（{len(pages)} 個分頁）"


def cdp_call(ws_url, method, params, timeout=5):
    """最小的 WebSocket 用戶端：送一個 DevTools 指令並等回覆。"""
    import base64
    import struct
    u = urllib.parse.urlparse(ws_url)
    s = socket.create_connection((u.hostname, u.port), timeout=timeout)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                raise ConnectionError("handshake failed")
            buf += chunk
        head, buf = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError(head.split(b"\r\n")[0].decode(errors="replace"))
        payload = json.dumps({"id": 1, "method": method, "params": params}).encode()
        n = len(payload)
        hdr = bytearray([0x81])
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        s.sendall(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

        def need(k):
            nonlocal buf
            while len(buf) < k:
                chunk = s.recv(65536)
                if not chunk:
                    raise ConnectionError("closed")
                buf += chunk
            out, buf = buf[:k], buf[k:]
            return out

        msg = b""
        while True:
            b0, b1 = need(2)
            ln = b1 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", need(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", need(8))[0]
            data = need(ln)
            op = b0 & 0x0F
            if op in (0x1, 0x0):
                msg += data
                if b0 & 0x80:
                    obj = json.loads(msg.decode("utf-8"))
                    msg = b""
                    if obj.get("id") == 1:
                        return obj
            elif op == 0x8:
                raise ConnectionError("closed")
    finally:
        s.close()


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


# ---------- 介面外觀 ----------
PAL = dict(bg="#F4F1EA", card="#FFFFFF", ink="#1E2230", muted="#6B7080", line="#E4DFD3", soft="#F1EDE3",
           accent="#FFC93C", accent_h="#F2B622", sky="#8FD3FF", sky_h="#6FC3F7", red="#FF6B6B", red_h="#F25252",
           head="#1E2230", green="#2A8A4A", blue="#2F6FDE", sel="#FFE8A6")
FONT = "Microsoft JhengHei UI"
UI_K = 1.0  # 螢幕縮放比例（高 DPI 時大於 1）


def WRAP(px=430):
    return int(px * UI_K)


def _hex(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _indicator_img(n, radio, on, bg):
    """畫手機版風格的勾選框／圓點（3x3 超取樣去鋸齒）。"""
    import math
    P = PAL
    img = tk.PhotoImage(width=n + int(7 * UI_K), height=n)  # 右邊留透明空白當間距
    cbg, cline, cfill, cmark = _hex(bg), _hex(P["line"] if not on else P["accent_h"]), _hex("#FFFFFF" if not on else P["accent"]), _hex(P["ink"])
    rad = n * 0.22
    bw = max(1.2, n / 14)

    def inside_shape(x, y, inset):
        if radio:
            return math.hypot(x - n / 2, y - n / 2) <= n / 2 - 0.5 - inset
        lo, hi = 0.5 + inset, n - 0.5 - inset
        r = max(0.1, rad - inset)
        cx, cy = min(max(x, lo + r), hi - r), min(max(y, lo + r), hi - r)
        return lo <= x <= hi and lo <= y <= hi and math.hypot(x - cx, y - cy) <= r

    def seg(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)

    rows = []
    for yy in range(n):
        row = []
        for xx in range(n):
            acc = [0.0, 0.0, 0.0]
            for sy in (0.17, 0.5, 0.83):
                for sx in (0.17, 0.5, 0.83):
                    x, y = xx + sx, yy + sy
                    col = cbg
                    if inside_shape(x, y, 0):
                        col = cline
                        if inside_shape(x, y, bw):
                            col = cfill
                            if on and radio and math.hypot(x - n / 2, y - n / 2) <= n * 0.2:
                                col = cmark
                            if on and not radio and min(seg(x, y, n * .24, n * .52, n * .43, n * .71),
                                                        seg(x, y, n * .43, n * .71, n * .77, n * .31)) <= n * .075:
                                col = cmark
                    for i in range(3):
                        acc[i] += col[i]
            row.append("#%02x%02x%02x" % tuple(int(v / 9) for v in acc))
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows), to=(0, 0))
    return img


def _indicators(root, st):
    n = int(17 * UI_K)
    imgs = {}
    for radio in (False, True):
        for on in (False, True):
            imgs[(radio, on)] = _indicator_img(n, radio, on, PAL["card"])
    root._crac_imgs = imgs  # 保留參照，不然圖片會被回收
    for w, radio in (("Checkbutton", False), ("Radiobutton", True)):
        el = f"Crac.{w}.indicator"
        st.element_create(el, "image", imgs[(radio, False)], ("selected", imgs[(radio, True)]), sticky="w")
        st.layout("T" + w, [(f"{w}.padding", {"sticky": "nswe", "children": [
            (el, {"side": "left", "sticky": ""}),
            (f"{w}.label", {"side": "left", "sticky": "nswe"})]})])


def setup_theme(root):
    st = ttk.Style(root)
    st.theme_use("clam")
    P = PAL
    root.configure(bg=P["bg"])
    st.configure(".", background=P["bg"], foreground=P["ink"], font=(FONT, 10), bordercolor=P["line"],
                 lightcolor=P["card"], darkcolor=P["line"], troughcolor=P["soft"], focuscolor=P["accent"],
                 selectbackground=P["sel"], selectforeground=P["ink"], insertcolor=P["ink"])
    st.configure("TFrame", background=P["bg"])
    st.configure("Card.TFrame", background=P["card"], relief="solid", borderwidth=1, bordercolor=P["line"])
    st.configure("Row.TFrame", background=P["card"])
    for name, extra in (("Card.TLabel", {}), ("Muted.TLabel", dict(foreground=P["muted"], font=(FONT, 9))),
                        ("Title.TLabel", dict(font=(FONT, 13, "bold"))), ("Bold.TLabel", dict(font=(FONT, 10, "bold"))),
                        ("Ok.TLabel", dict(foreground=P["green"], font=(FONT, 9))),
                        ("Info.TLabel", dict(foreground=P["blue"], font=(FONT, 10, "bold")))):
        st.configure(name, background=P["card"], **extra)
    st.configure("TButton", padding=(12, 6), background=P["soft"], bordercolor=P["line"], relief="flat", font=(FONT, 10))
    st.map("TButton", background=[("pressed", P["line"]), ("active", "#ECE6D8")])
    st.configure("Accent.TButton", background=P["accent"], bordercolor=P["accent_h"], font=(FONT, 10, "bold"))
    st.map("Accent.TButton", background=[("pressed", P["accent_h"]), ("active", P["accent_h"])])
    st.configure("TEntry", fieldbackground="#FFFFFF", bordercolor=P["line"], lightcolor="#FFFFFF", darkcolor=P["line"], padding=(8, 5))
    st.map("TEntry", bordercolor=[("focus", P["blue"])], lightcolor=[("focus", P["blue"])])
    st.configure("TCombobox", fieldbackground="#FFFFFF", background=P["soft"], bordercolor=P["line"], padding=(6, 3), arrowsize=14)
    st.map("TCombobox", fieldbackground=[("readonly", "#FFFFFF")], bordercolor=[("focus", P["blue"])])
    for w in ("TCheckbutton", "TRadiobutton"):
        st.configure(w, background=P["card"], indicatorbackground="#FFFFFF", indicatorforeground=P["ink"], padding=(0, 4),
                     indicatorsize=int(15 * UI_K), indicatormargin=(0, 0, int(6 * UI_K), 0), upperbordercolor=P["line"],
                     lowerbordercolor=P["line"])
        st.map(w, background=[("active", P["card"])], indicatorbackground=[("selected", P["accent"])])
    _indicators(root, st)
    st.configure("TNotebook", background=P["bg"], borderwidth=0, tabmargins=(10, 8, 10, 0))
    st.configure("TNotebook.Tab", padding=(18, 8), background="#E7E1D3", foreground=P["muted"], font=(FONT, 10, "bold"), borderwidth=0)
    st.map("TNotebook.Tab", background=[("selected", P["card"])], foreground=[("selected", P["ink"])],
           expand=[("selected", (0, 2, 0, 0))])
    st.configure("Treeview", background=P["card"], fieldbackground=P["card"], bordercolor=P["line"], rowheight=int(26 * UI_K), font=(FONT, 10))
    st.configure("Treeview.Heading", background=P["soft"], font=(FONT, 9, "bold"), relief="flat", padding=(4, 4))
    st.map("Treeview", background=[("selected", P["sel"])], foreground=[("selected", P["ink"])])
    st.configure("TSeparator", background=P["line"])
    st.layout("Slim.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    st.configure("Slim.Vertical.TScrollbar", background="#D6D0C2", troughcolor=P["bg"], bordercolor=P["bg"],
                 lightcolor="#D6D0C2", darkcolor="#D6D0C2", gripcount=0, arrowsize=int(8 * UI_K))
    st.map("Slim.Vertical.TScrollbar", background=[("active", "#BDB6A6")])
    return st


def _bg_of(w):
    """取得父元件的底色（tk 或 ttk 都可以）。"""
    try:
        return w.cget("background")
    except Exception:
        pass
    try:
        return ttk.Style().lookup(w.cget("style") or w.winfo_class(), "background") or PAL["bg"]
    except Exception:
        return PAL["bg"]


def rrect(cv, x1, y1, x2, y2, r, **kw):
    """在 Canvas 上畫圓角矩形。"""
    r = max(1, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class RoundBtn(tk.Canvas):
    """手機版風格的圓角按鈕（也可當不能按的膠囊標籤）。"""

    KINDS = None

    def __init__(self, parent, text="", command=None, kind="soft", big=False, style=None, small=False):
        import tkinter.font as tkfont
        P = PAL
        kinds = {"soft": (P["soft"], "#E9E3D5", P["ink"]), "accent": (P["accent"], P["accent_h"], P["ink"]),
                 "sky": (P["sky"], P["sky_h"], P["ink"]), "red": (P["red"], P["red_h"], P["ink"]),
                 "tab": ("#2D3346", "#3A4158", "#C9CEDC"), "chip": ("#2D3346", "#2D3346", "#C9CEDC"),
                 "white": ("#FFFFFF", "#FFF4D6", P["ink"])}
        if style == "Accent.TButton":
            kind = "accent"
        self._bg, self._hover, self._fg = kinds.get(kind, kinds["soft"])
        size = 13 if big else (9 if small else 10)
        bold = big or small or kind in ("accent", "sky", "red", "tab")
        self._font = tkfont.Font(family=FONT, size=size, weight="bold" if bold else "normal")
        self._h = int((54 if big else (26 if small else 38)) * UI_K)
        self._padx = int((12 if small else 16) * UI_K)
        self._r = int((16 if big else (13 if small else 12)) * UI_K)
        self._text, self._cmd, self._hot, self._down = text, command, False, False
        super().__init__(parent, height=self._h, width=self._need(), bg=_bg_of(parent), highlightthickness=0, bd=0,
                         cursor="hand2" if command else "arrow")
        self.bind("<Configure>", lambda e: self.draw())
        if command:
            self.bind("<Enter>", lambda e: self._set(hot=True))
            self.bind("<Leave>", lambda e: self._set(hot=False, down=False))
            self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
            self.bind("<ButtonRelease-1>", self._release)

    def _need(self):
        return self._font.measure(self._text) + self._padx * 2

    def _set(self, hot=None, down=None):
        if hot is not None:
            self._hot = hot
        if down is not None:
            self._down = down
        self.draw()

    def _release(self, e):
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        self._set(down=False)
        if inside and self._cmd:
            self._cmd()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = self._need(), self._h
        fill = self._hover if (self._hot or self._down) else self._bg
        o = 1 if self._down else 0
        rrect(self, 0, 0, w - 1, h - 1, self._r, fill=fill, outline=fill)
        self.create_text(w / 2, h / 2 + o, text=self._text, font=self._font, fill=self._fg)

    def set_colors(self, bg, hover, fg=None):
        if (bg, hover, fg or self._fg) != (self._bg, self._hover, self._fg):
            self._bg, self._hover = bg, hover
            if fg:
                self._fg = fg
            self.draw()

    def config(self, cnf=None, **kw):
        changed = False
        if "text" in kw:
            t = kw.pop("text")
            if t != self._text:
                self._text = t
                super().configure(width=self._need())
                changed = True
        if "bg" in kw or "fg" in kw:  # 膠囊標籤：bg/fg 代表填色和字色
            bg, fg = kw.pop("bg", self._bg), kw.pop("fg", self._fg)
            if (bg, fg) != (self._bg, self._fg):
                self._bg = self._hover = bg
                self._fg = fg
                changed = True
        if cnf or kw:
            super().configure(cnf, **kw)
        if changed:
            self.draw()

    configure = config


class RoundBox(tk.Canvas):
    """圓角底框，內容放在 .inner；高度跟著內容自動變。"""

    def __init__(self, parent, fill, outline=None, radius=18, pad=(16, 12, 16, 14)):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0, height=20)
        self._fill, self._outline, self._r = fill, outline or fill, int(radius * UI_K)
        self._pad = [int(p * UI_K) for p in pad]
        self.inner = tk.Frame(self, bg=fill)
        self._win = self.create_window(self._pad[0], self._pad[1], window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._fit)
        self.bind("<Configure>", lambda e: self._redraw())

    def _fit(self, e):
        h = e.height + self._pad[1] + self._pad[3]
        if int(self.cget("height")) != h:
            self.configure(height=h)

    def _redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        self.itemconfigure(self._win, width=max(10, w - self._pad[0] - self._pad[2]))
        self.delete("bg")
        rrect(self, 1, 1, w - 2, h - 2, self._r, fill=self._fill, outline=self._outline, tags="bg")
        self.tag_lower("bg")


class ScrollFrame(ttk.Frame):
    """可以用滑鼠滾輪捲動的分頁內容。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=PAL["bg"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="Slim.Vertical.TScrollbar")
        self.inner = ttk.Frame(self.canvas, padding=(14, 8, 10, 24))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if w is self:
                if self.inner.winfo_height() > self.canvas.winfo_height():
                    self.canvas.yview_scroll(int(-e.delta / 120), "units")
                return
            w = w.master


def card(parent, title, subtitle=None):
    """白色卡片＋標題，回傳放內容的框。"""
    box = RoundBox(parent, PAL["card"], PAL["line"], 18)
    box.pack(fill="x", pady=6)
    outer = box.inner
    ttk.Label(outer, text=title, style="Title.TLabel").pack(anchor="w")
    if subtitle:
        ttk.Label(outer, text=subtitle, style="Muted.TLabel", wraplength=WRAP(), justify="left").pack(anchor="w", pady=(0, 4))
    body = ttk.Frame(outer, style="Row.TFrame")
    body.pack(fill="x", pady=(6, 0))
    return body


def row(parent, pady=3):
    r = ttk.Frame(parent, style="Row.TFrame")
    r.pack(fill="x", pady=pady)
    return r


def lbl(parent, text, style="Card.TLabel", **kw):
    return ttk.Label(parent, text=text, style=style, **kw)


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
        global UI_K
        try:
            UI_K = max(1.0, (user32.GetDpiForWindow(self.root.winfo_id()) or 96) / 96.0)
        except Exception:
            UI_K = 1.0
        setup_theme(self.root)
        self.root.geometry(f"{int(560 * UI_K)}x{min(int(800 * UI_K), self.root.winfo_screenheight() - 90)}")
        self.root.minsize(int(520 * UI_K), int(520 * UI_K))
        self.clicker.on_change = lambda: self.root.after(0, self.refresh_btn)
        self.clicker.smart_fn = self.smart_wait
        self.rate_state, self.rate_ok, self.rate_checked, self.smart_used = None, None, 0, False
        self.buyer = BuyRunner(self.s)
        self.buyer.on_change = lambda: self.root.after(0, self.refresh_buy)
        self.bg = BgBrowser()
        self.server = None
        self.url = ""
        self.build_ui()
        self.refresh_rate_lbl()
        threading.Thread(target=self.rate_watch, daemon=True).start()
        t = self.s.get("tab", 0)
        self.show_tab(t if t in (0, 1, 2) else 0)
        self.start_server()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(200, self.poll)
        self._keys = {VK_F8: False, VK_F9: False, VK_F10: False}
        if self.s.get("auto_update", True):
            self.root.after(3000, self.check_update)
        if os.path.isdir(extension_dir()):  # 已經裝過擴充功能 → 把檔案更新成這一版的面板
            try:
                write_extension()
            except Exception:
                pass

    # ----- ① 依產量算收成間隔 -----
    def calc_interval(self):
        w = tk.Toplevel(self.root)
        w.title("依產量算收成間隔")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        f = ttk.Frame(w, padding=12)
        f.pack()
        ttk.Label(f, justify="left", wraplength=320, text=(
            "把滑鼠移到遊戲上方的金幣、建材上，會看到「每小時產出 ___」。\n"
            "沒收成的產出最多累積金幣 2000、建材 1500，滿了就停產；這裡會算出快滿（90%）之前收一次的間隔。")).grid(row=0, column=0, columnspan=2, sticky="w")
        rs = self.rate_state or {}
        vg = tk.StringVar(value=str(int(rs["gold"]["rate"]) if rs.get("gold") else self.s.get("rate_gold", "")))
        vm = tk.StringVar(value=str(int(rs["mat"]["rate"]) if rs.get("mat") else self.s.get("rate_mat", "")))
        ttk.Label(f, text="金幣 每小時產出").grid(row=1, column=0, sticky="e", pady=(8, 0))
        ttk.Entry(f, textvariable=vg, width=10).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(f, text="建材 每小時產出").grid(row=2, column=0, sticky="e")
        ttk.Entry(f, textvariable=vm, width=10).grid(row=2, column=1, sticky="w")
        res = ttk.Label(f, text="", foreground="#2a6db0")
        res.grid(row=3, column=0, columnspan=2, sticky="w", pady=6)

        def compute(apply=False):
            try:
                g = float(vg.get() or 0)
                m = float(vm.get() or 0)
            except ValueError:
                res.config(text="請輸入數字")
                return
            mins = smart_interval_minutes(g, m)
            if not mins:
                res.config(text="至少要填一個大於 0 的產量")
                return
            res.config(text=f"建議每 {mins} 分鐘收一次")
            if apply:
                self.s.update(rate_gold=g, rate_mat=m)
                self.viv.set(str(mins))
                self.vun.set("分")
                self.collect()
                w.destroy()

        b = ttk.Frame(f)
        b.grid(row=4, column=0, columnspan=2, sticky="we")
        RoundBtn(b, text="計算", command=compute).pack(side="left")
        RoundBtn(b, text="套用到間隔", command=lambda: compute(True)).pack(side="left", padx=6)

    # ----- ⑤ 自動更新 -----
    def check_update(self, manual=False):
        def work():
            try:
                data = fetch_latest_release()
            except Exception as ex:
                if manual:
                    self.root.after(0, lambda: messagebox.showerror(APP_NAME, f"檢查更新失敗：{ex}"))
                return
            tag = data.get("tag_name", "")
            if ver_tuple(tag) <= ver_tuple(APP_VERSION):
                if manual:
                    self.root.after(0, lambda: messagebox.showinfo(APP_NAME, f"已經是最新版（v{APP_VERSION}）"))
                return
            if not manual and self.s.get("skip_ver") == tag:
                return
            self.root.after(0, lambda: self.offer_update(data))
        threading.Thread(target=work, daemon=True).start()

    def offer_update(self, data):
        tag = data.get("tag_name", "")
        notes = (data.get("body") or "").strip()
        if len(notes) > 500:
            notes = notes[:500] + "…"
        ans = messagebox.askyesnocancel(APP_NAME, f"有新版本 {tag}（目前 v{APP_VERSION}）\n\n{notes}\n\n"
                                                  "「是」立即更新　「否」以後再說　「取消」略過這個版本")
        if ans is None:
            self.s["skip_ver"] = tag
            save_settings(self.s)
            return
        if not ans:
            return
        asset = next((a for a in data.get("assets", []) if a.get("name") == "CRRank.exe"), None)
        if not getattr(sys, "frozen", False) or not asset:
            webbrowser.open(data.get("html_url", f"https://github.com/{REPO}/releases/latest"))
            return
        self.root.title(f"{APP_NAME} — 下載 {tag} 中…")
        threading.Thread(target=self._download_update, args=(asset["browser_download_url"], tag), daemon=True).start()

    def _download_update(self, url, tag):
        import subprocess
        import tempfile
        import urllib.request
        tmp = os.path.join(tempfile.gettempdir(), f"CRRank_update_{tag}.exe")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CRRank-AutoHarvest"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        pct = got * 100 // total
                        self.root.after(0, lambda p=pct: self.root.title(f"{APP_NAME} — 下載 {tag} {p}%"))
            if total and got != total:
                raise IOError("下載不完整")
        except Exception as ex:
            self.root.after(0, lambda: (self.root.title(APP_NAME), messagebox.showerror(APP_NAME, f"下載更新失敗：{ex}")))
            return
        subprocess.Popen([tmp, "--finish-update", sys.executable, str(os.getpid())])
        self.root.after(0, lambda: self.quit(silent=True))

    # ----- 🧩 Chrome 擴充功能（用原本的 Chrome，不用重新登入） -----
    def install_extension(self):
        import subprocess
        path = write_extension()
        try:
            os.startfile(path)
        except Exception:
            pass
        exe = BgBrowser.find_browser()
        page = "edge://extensions" if exe and exe.lower().endswith("msedge.exe") else "chrome://extensions"
        if exe:
            try:
                subprocess.Popen([exe, page])  # 在你原本的瀏覽器（同一個設定檔）打開擴充功能頁
            except Exception:
                pass
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
        except Exception:
            pass
        messagebox.showinfo(APP_NAME, (
            "擴充功能檔案已經準備好（資料夾路徑也複製到剪貼簿了）：\n" + path + "\n\n"
            f"在剛打開的 {page} 頁面：\n"
            "1. 打開「開發人員模式」\n"
            "2. 按「載入未封裝項目」，選上面這個資料夾（可以直接貼上路徑）\n"
            "3. 打開或重新整理知識領土，面板就會自動出現\n\n"
            "只要裝一次。以後更新程式，到擴充功能頁按它的「重新載入」(↻) 就會換成新版面板。"))

    def toggle_bg(self):
        if self.bg.running():
            self.bg.stop()
        elif not self.bg.start():
            messagebox.showerror(APP_NAME, "找不到 Chrome 或 Edge，背景模式需要其中一個。")

    # ----- UI -----
    def build_ui(self):
        P = PAL
        # ---- 頂部標題列（和手機版一樣：深色標題＋膠囊分頁） ----
        head = tk.Frame(self.root, bg=P["head"])
        head.pack(fill="x")
        top = tk.Frame(head, bg=P["head"])
        top.pack(fill="x", padx=int(18 * UI_K), pady=(int(14 * UI_K), int(10 * UI_K)))
        tt = tk.Frame(top, bg=P["head"])
        tt.pack(side="left")
        tk.Label(tt, text="🌾 CR Rank 自動收成", bg=P["head"], fg="#FFFFFF", font=(FONT, 15, "bold")).pack(anchor="w")
        tk.Label(tt, text=f"v{APP_VERSION} · 知識領土小幫手", bg=P["head"], fg="#A7ADBF", font=(FONT, 9)).pack(anchor="w")
        chips = tk.Frame(top, bg=P["head"])
        chips.pack(side="right")
        self.chip_h = RoundBtn(chips, "收成 ● 停止", kind="chip", small=True)
        self.chip_h.pack(anchor="e", pady=(0, 4))
        self.chip_b = RoundBtn(chips, "購買 ● 停止", kind="chip", small=True)
        self.chip_b.pack(anchor="e")
        bar = tk.Frame(head, bg=P["head"])
        bar.pack(fill="x", padx=int(12 * UI_K), pady=(0, int(12 * UI_K)))
        content = tk.Frame(self.root, bg=P["bg"])
        content.pack(fill="both", expand=True)
        pcs, buys, phs = ScrollFrame(content), ScrollFrame(content), ScrollFrame(content)
        self.pages = [pcs, buys, phs]
        self.tab_btns = []
        for i, name in enumerate(("🖱 電腦連點", "🛒 自動購買", "📱 手機")):
            t = RoundBtn(bar, name, command=lambda k=i: self.show_tab(k), kind="tab")
            t.pack(side="left", padx=int(3 * UI_K))
            self.tab_btns.append(t)
        self.cur_tab = 0
        self.build_buy_tab(buys.inner)
        pc, ph = pcs.inner, phs.inner

        # ---- 點擊位置 ----
        c = card(pc, "🎯 點擊位置", "遊戲上「收成」按鈕在螢幕上的座標。")
        r = row(c)
        self.vx = tk.IntVar(value=self.s["x"])
        self.vy = tk.IntVar(value=self.s["y"])
        lbl(r, "X").pack(side="left")
        ttk.Entry(r, textvariable=self.vx, width=8).pack(side="left", padx=(6, 16))
        lbl(r, "Y").pack(side="left")
        ttk.Entry(r, textvariable=self.vy, width=8).pack(side="left", padx=6)
        r = row(c, 6)
        RoundBtn(r, text="🎯 在螢幕上選位置", style="Accent.TButton", command=self.pick).pack(side="left", fill="x", expand=True)
        RoundBtn(r, text="測試點一下", command=self.test_click).pack(side="left", fill="x", expand=True, padx=(8, 0))
        lbl(c, "或把滑鼠移到「收成」按鈕上按 F8 記錄", "Muted.TLabel").pack(anchor="w")

        # ---- 自動判斷產量 ----
        c = card(pc, "🤖 自動判斷每小時產量",
                 "直接讀你開著的知識領土分頁，算出金幣或建材快滿（90%）前收成。產量變了會跟著變，不用手動輸入。")
        self.vauto_rate = tk.BooleanVar(value=self.s.get("auto_rate", True))
        r = row(c)
        ttk.Checkbutton(r, text="自動判斷收成時間", variable=self.vauto_rate, command=self.set_auto_rate).pack(side="left")
        RoundBtn(r, text="🔍 立即讀取", command=lambda: threading.Thread(target=self.read_rates, daemon=True).start()).pack(side="right")
        self.rate_lbl = lbl(c, "讀取中…", "Muted.TLabel", wraplength=WRAP(), justify="left")
        self.rate_lbl.pack(anchor="w", pady=(4, 0))

        # ---- 間隔 ----
        c = card(pc, "⏱ 間隔與選項", "開著自動判斷時，這個間隔只在讀不到遊戲時使用。")
        r = row(c)
        lbl(r, "每").pack(side="left")
        self.viv = tk.StringVar(value=str(self.s["interval"]))
        ttk.Entry(r, textvariable=self.viv, width=8).pack(side="left", padx=6)
        self.vun = tk.StringVar(value=self.s["unit"])
        ttk.Combobox(r, textvariable=self.vun, values=list(UNIT_SEC), width=4, state="readonly").pack(side="left")
        lbl(r, "點一次").pack(side="left", padx=6)
        RoundBtn(r, text="📊 依產量算", command=self.calc_interval).pack(side="right")
        r = row(c)
        lbl(r, "隨機誤差 ±").pack(side="left")
        self.vjit = tk.StringVar(value=str(self.s["jitter"]))
        ttk.Entry(r, textvariable=self.vjit, width=6).pack(side="left", padx=6)
        lbl(r, "秒").pack(side="left")
        lbl(r, "次數上限").pack(side="left", padx=(20, 0))
        self.vlim = tk.StringVar(value=str(self.s["limit"]))
        ttk.Entry(r, textvariable=self.vlim, width=6).pack(side="left", padx=6)
        lbl(r, "（0＝無限）", "Muted.TLabel").pack(side="left")
        self.vres = tk.BooleanVar(value=self.s["restore"])
        ttk.Checkbutton(c, text="點完把滑鼠移回原位", variable=self.vres).pack(anchor="w", pady=(4, 0))
        self.vnow = tk.BooleanVar(value=self.s["click_now"])
        ttk.Checkbutton(c, text="按開始時立刻先點一次", variable=self.vnow).pack(anchor="w")

        # ---- 開始 ----
        c = card(pc, "▶ 自動收成")
        self.btn = RoundBtn(c, "▶  開始自動收成  (F9)", self.toggle, kind="accent", big=True)
        self.btn.pack(fill="x")
        self.status = lbl(c, "已停止", "Info.TLabel")
        self.status.pack(anchor="w", pady=(8, 0))
        lbl(c, "提示：這個模式會移動真的滑鼠，遊戲畫面要停在原位、不要被擋住。", "Muted.TLabel",
            wraplength=WRAP(), justify="left").pack(anchor="w")
        RoundBtn(c, text="🌐 開啟知識領土網站", command=lambda: webbrowser.open(GAME_URL)).pack(fill="x", pady=(8, 0))

        # ---- 背景模式 ----
        c = card(pc, "🌙 背景模式", "遊戲不用放在前台：用面板直接點網頁上的按鈕，分頁放背景、被蓋住都會繼續跑。")
        RoundBtn(c, text="🧩 用原本的 Chrome（安裝擴充功能，不用重新登入）", style="Accent.TButton",
                   command=self.install_extension).pack(fill="x")
        lbl(c, "推薦。只要裝一次，之後在平常的 Chrome 打開知識領土就會自動出現面板，Chrome 也不會把遊戲分頁卸載。",
            "Muted.TLabel", wraplength=WRAP(), justify="left").pack(anchor="w", pady=(4, 8))
        self.bgbtn = RoundBtn(c, text="開啟專用背景視窗（要另外登入）", command=self.toggle_bg)
        self.bgbtn.pack(fill="x")
        self.bglbl = lbl(c, "未開啟", "Muted.TLabel", wraplength=WRAP())
        self.bglbl.pack(anchor="w", pady=(4, 0))

        # ---- 版本 ----
        c = card(pc, "🔄 版本與更新")
        r = row(c)
        lbl(r, f"目前版本 v{APP_VERSION}", "Bold.TLabel").pack(side="left")
        RoundBtn(r, text="檢查更新", command=lambda: self.check_update(manual=True)).pack(side="right")
        self.vauto_up = tk.BooleanVar(value=self.s.get("auto_update", True))
        ttk.Checkbutton(c, text="開啟時自動檢查更新", variable=self.vauto_up,
                        command=lambda: (self.s.__setitem__("auto_update", self.vauto_up.get()), save_settings(self.s))).pack(anchor="w")

        # ---- 手機分頁 ----
        c = card(ph, "📱 用手機掃描", "手機和電腦連同一個 Wi-Fi，用手機相機掃描下面的 QR Code。")
        qbox = tk.Frame(c, bg="#FFFFFF", highlightbackground=P["line"], highlightthickness=1, padx=8, pady=8)
        qbox.pack(pady=6)  # QR Code 保持方形白底，手機比較好掃
        self.qr = tk.Canvas(qbox, width=220, height=220, bg="white", highlightthickness=0)
        self.qr.pack()
        self.url_lbl = ttk.Entry(c, width=44)
        self.url_lbl.pack(fill="x", pady=(4, 0))
        c = card(ph, "📖 手機頁面能做什麼")
        for t in ("•書籤／使用者腳本：在手機瀏覽器的遊戲頁上自動點「收成」，可設間隔、自動找按鈕或自訂位置。",
                  "•遙控：用手機開始／停止電腦這邊的連點、改間隔。",
                  "•iPhone 也能用：掃描後照頁面裡的「iPhone 教學」設定。",
                  "第一次啟動時 Windows 防火牆若跳出詢問，請按「允許」。"):
            lbl(c, t, wraplength=WRAP(), justify="left").pack(anchor="w", pady=2)
        c = card(ph, "📁 檔案")
        RoundBtn(c, text="📁 匯出手機用檔案（腳本、書籤、說明）", command=self.export).pack(fill="x")
        RoundBtn(c, text="在電腦瀏覽器開啟手機頁", command=lambda: webbrowser.open(self.url)).pack(fill="x", pady=(6, 0))

    # ----- 🤖 自動判斷每小時產量 -----
    def set_auto_rate(self):
        self.s["auto_rate"] = bool(self.vauto_rate.get())
        save_settings(self.s)
        self.refresh_rate_lbl()
        if self.s["auto_rate"]:
            threading.Thread(target=self.read_rates, daemon=True).start()

    def read_rates(self):
        try:
            st = read_game_state()
        except Exception:
            st = None
        if st:
            self.rate_state = st
        self.rate_ok = bool(st)
        self.rate_checked = time.time()
        try:
            self.root.after(0, self.refresh_rate_lbl)
        except Exception:
            pass
        return st

    def smart_wait(self, after_click):
        """連點每次點完呼叫：等遊戲畫面更新後讀數字，回傳到快滿還有幾秒（讀不到回傳 None）。"""
        if after_click and self.clicker.stop_evt.wait(2.5):
            return None
        sec = smart_wait_seconds(self.read_rates())
        self.smart_used = sec is not None
        return sec

    def rate_watch(self):
        while True:
            if self.s.get("auto_rate") and not self.clicker.running:
                self.read_rates()
            time.sleep(60)

    def refresh_rate_lbl(self):
        if not self.s.get("auto_rate"):
            self.rate_lbl.config(text="已關閉：用下面的固定間隔。", style="Muted.TLabel")
            return
        if self.rate_ok is None:
            self.rate_lbl.config(text="讀取中…", style="Muted.TLabel")
            return
        st = self.rate_state
        when = time.strftime("%H:%M:%S", time.localtime(self.rate_checked))
        if self.rate_ok and st:
            sec = smart_wait_seconds(st)
            mins = max(1, int(round(sec / 60))) if sec else 0
            self.rate_lbl.config(style="Ok.TLabel", text=(
                f"✔ {describe_state(st)}\n→ 約 {mins} 分鐘後快滿，到時自動收成（{when} 讀取）"))
        else:
            self.rate_lbl.config(style="Muted.TLabel", text=(
                f"找不到遊戲（{when}）：在 Chrome／Edge 打開知識領土並停在那個分頁，視窗不要縮到最小。"
                "讀不到時會用下面的間隔。"))

    def show_tab(self, k):
        self.cur_tab = k
        for i, (pg, b) in enumerate(zip(self.pages, self.tab_btns)):
            if i == k:
                pg.pack(fill="both", expand=True)
                b.set_colors(PAL["accent"], PAL["accent_h"], PAL["ink"])
            else:
                pg.pack_forget()
                b.set_colors("#2D3346", "#3A4158", "#C9CEDC")
        if self.s.get("tab") != k:
            self.s["tab"] = k
            save_settings(self.s)

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
        def done(x, y):
            self.vx.set(x)
            self.vy.set(y)
            self.collect()
        self.pick_point("點一下「收成」按鈕的位置（Esc 取消）", done)

    def pick_point(self, prompt, on_pick, on_cancel=None):
        vx = user32.GetSystemMetrics(76)
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)
        vh = user32.GetSystemMetrics(79)
        self.root.withdraw()  # 把主視窗藏起來，才不會擋住要選的按鈕
        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.geometry(f"{vw}x{vh}+{vx}+{vy}")
        ov.attributes("-alpha", 0.3)
        ov.attributes("-topmost", True)
        ov.configure(bg="black", cursor="crosshair")
        tk.Label(ov, text=prompt, fg="white", bg="black",
                 font=("Microsoft JhengHei UI", 20, "bold")).place(relx=0.5, rely=0.08, anchor="n")

        def done(e):
            x, y = get_cursor()
            ov.destroy()
            self.root.deiconify()
            on_pick(x, y)

        def cancel(e):
            ov.destroy()
            self.root.deiconify()
            if on_cancel:
                on_cancel()

        ov.bind("<Button-1>", done)
        ov.bind("<Escape>", cancel)
        ov.focus_force()

    # ----- 自動購買分頁 -----
    def build_buy_tab(self, f):
        P = PAL
        # ---- 存檔 ----
        c = card(f, "💾 存檔", "步驟有任何變動都會自動存到目前的存檔。")
        r = row(c)
        self.vslot = tk.StringVar()
        self.slot_cb = ttk.Combobox(r, textvariable=self.vslot, state="readonly", width=16)
        self.slot_cb.pack(side="left")
        self.slot_cb.bind("<<ComboboxSelected>>", lambda e: self.switch_slot(self.slot_cb.current()))
        RoundBtn(r, text="改名", command=self.rename_slot).pack(side="left", padx=(8, 0))
        RoundBtn(r, text="清空", command=self.clear_slot).pack(side="left", padx=(6, 0))
        self.vrot = tk.BooleanVar(value=self.s.get("buy_rotate", False))
        ttk.Checkbutton(c, text="自動輪播（做完一個存檔接下一個）", variable=self.vrot, command=self.set_rotate).pack(anchor="w", pady=(4, 0))
        self.saved_lbl = lbl(c, "", "Ok.TLabel")
        self.saved_lbl.pack(anchor="w")

        # ---- 步驟 ----
        c = card(f, "📋 購買步驟", "照順序模擬點擊：打開物品 → 商店 → 分類 → 購買 → 關閉商店。")
        cols = ("n", "name", "act", "x", "y", "times", "wait")
        tv = ttk.Treeview(c, columns=cols, show="headings", height=6, selectmode="browse")
        for col, t, w in zip(cols, ("#", "步驟", "動作", "X", "Y", "次數", "等待秒"), (30, 150, 76, 50, 50, 42, 54)):
            tv.heading(col, text=t)
            tv.column(col, width=int(w * UI_K), anchor="w" if col == "name" else "center", stretch=(col == "name"))
        tv.pack(fill="x")
        tv.bind("<<TreeviewSelect>>", lambda e: self.load_step())
        self.tv = tv

        edbox = RoundBox(c, P["soft"], None, 14, (12, 10, 12, 10))
        edbox.pack(fill="x", pady=(8, 0))
        ed = edbox.inner
        self.st_name = tk.StringVar()
        self.st_times = tk.StringVar(value="1")
        self.st_wait = tk.StringVar(value="1")
        self.st_type = tk.StringVar(value="點擊")
        self.st_dir = tk.StringVar(value="往下")
        self.st_amount = tk.StringVar(value="3")

        def L(parent, text):
            return tk.Label(parent, text=text, bg=P["soft"], fg=P["ink"], font=(FONT, 10))

        r1 = tk.Frame(ed, bg=P["soft"])
        r1.pack(fill="x")
        L(r1, "選中的步驟：名稱").pack(side="left")
        e1 = ttk.Entry(r1, textvariable=self.st_name, width=14)
        e1.pack(side="left", padx=(4, 8))
        L(r1, "重複").pack(side="left")
        e2 = ttk.Entry(r1, textvariable=self.st_times, width=3)
        e2.pack(side="left", padx=4)
        L(r1, "次，做完等").pack(side="left")
        e3 = ttk.Entry(r1, textvariable=self.st_wait, width=4)
        e3.pack(side="left", padx=4)
        L(r1, "秒").pack(side="left")
        r2 = tk.Frame(ed, bg=P["soft"])
        r2.pack(fill="x", pady=(6, 0))
        L(r2, "動作").pack(side="left")
        c1 = ttk.Combobox(r2, textvariable=self.st_type, values=("點擊", "滾動"), state="readonly", width=5)
        c1.pack(side="left", padx=(4, 10))
        L(r2, "滾動").pack(side="left")
        c2 = ttk.Combobox(r2, textvariable=self.st_dir, values=("往下", "往上"), state="readonly", width=5)
        c2.pack(side="left", padx=4)
        e4 = ttk.Entry(r2, textvariable=self.st_amount, width=3)
        e4.pack(side="left")
        L(r2, "格").pack(side="left", padx=(4, 0))
        RoundBtn(r2, text="套用", command=self.apply_step, kind="white").pack(side="right")
        for w in (e1, e2, e3, e4):  # 改完自動套用＋自動存檔
            w.bind("<Return>", lambda e: self.apply_step())
            w.bind("<FocusOut>", lambda e: self.apply_step(quiet=True))
        for w in (c1, c2):
            w.bind("<<ComboboxSelected>>", lambda e: self.apply_step())

        b1 = row(c, (8, 2))
        for i, (t, cmd) in enumerate((("📋 建立購買範本", self.buy_template), ("➕ 點擊步驟", self.add_step),
                                      ("➕ 滾動步驟", self.add_scroll), ("🗑 刪除", self.del_step))):
            RoundBtn(b1, text=t, command=cmd, style="Accent.TButton" if i == 0 else None).grid(row=0, column=i, sticky="we", padx=2)
            b1.columnconfigure(i, weight=1)
        b2 = row(c, 2)
        for i, (t, cmd) in enumerate((("🎯 選位置", self.pick_step), ("🎯 依序選全部", self.pick_all),
                                      ("↑ 上移", lambda: self.move_step(-1)), ("↓ 下移", lambda: self.move_step(1)))):
            RoundBtn(b2, text=t, command=cmd).grid(row=0, column=i, sticky="we", padx=2)
            b2.columnconfigure(i, weight=1)
        lbl(c, "選中步驟後，把滑鼠移到目標上按 F8 也能記錄位置；滾動步驟的位置＝要捲的清單上。", "Muted.TLabel",
            wraplength=WRAP(), justify="left").pack(anchor="w", pady=(6, 0))

        # ---- 執行 ----
        c = card(f, "⏰ 什麼時候買")
        self.vbmode = tk.StringVar(value=self.s.get("buy_mode", "restock"))
        self.vboff = tk.StringVar(value=str(self.s.get("buy_offset", 10)))
        self.vbevery = tk.StringVar(value=str(self.s.get("buy_every", 30)))
        r = row(c)
        ttk.Radiobutton(r, text="每次補貨後（整點、半點）過", variable=self.vbmode, value="restock").pack(side="left")
        ttk.Entry(r, textvariable=self.vboff, width=5).pack(side="left", padx=4)
        lbl(r, "秒").pack(side="left")
        r = row(c)
        ttk.Radiobutton(r, text="每", variable=self.vbmode, value="interval").pack(side="left")
        ttk.Entry(r, textvariable=self.vbevery, width=6).pack(side="left", padx=4)
        lbl(r, "分鐘").pack(side="left")
        self.vbnow = tk.BooleanVar(value=self.s.get("buy_now", True))
        ttk.Checkbutton(c, text="按開始時立刻先買一次", variable=self.vbnow).pack(anchor="w", pady=(2, 8))
        self.bbtn = RoundBtn(c, "▶  開始自動購買  (F10)", self.toggle_buy, kind="sky", big=True)
        self.bbtn.pack(fill="x")
        RoundBtn(c, text="立即買一次（測試）", command=self.buy_once).pack(fill="x", pady=(8, 0))
        self.bstatus = lbl(c, "已停止", "Info.TLabel", wraplength=WRAP())
        self.bstatus.pack(anchor="w", pady=(8, 0))
        lbl(c, "開始前「物品」視窗要先關著，遊戲畫面不要被擋住。", "Muted.TLabel").pack(anchor="w")
        self.refresh_slots()
        self.refresh_steps()

    # ----- 存檔 -----
    def slots(self):
        return self.s["buy_slots"]

    def cur_slot(self):
        return self.slots()[int(self.s.get("buy_slot", 0))]

    def autosave(self):
        save_settings(self.s)
        if hasattr(self, "saved_lbl"):
            self.saved_lbl.config(text=f"✔ 已自動存檔到「{self.cur_slot()['name']}」 {time.strftime('%H:%M:%S')}")

    def refresh_slots(self):
        names = [f"{sl['name']}（{len(sl.get('steps', []))} 步）" for sl in self.slots()]
        self.slot_cb.config(values=names)
        self.slot_cb.current(int(self.s.get("buy_slot", 0)))

    def switch_slot(self, i):
        if i < 0:
            return
        self.s["buy_slot"] = i
        self.autosave()
        self.refresh_slots()
        self.refresh_steps(0 if self.steps() else None)

    def rename_slot(self):
        from tkinter import simpledialog
        sl = self.cur_slot()
        n = simpledialog.askstring(APP_NAME, "存檔名稱：", initialvalue=sl["name"], parent=self.root)
        if n and n.strip():
            sl["name"] = n.strip()
            self.autosave()
            self.refresh_slots()

    def clear_slot(self):
        sl = self.cur_slot()
        if sl.get("steps") and messagebox.askyesno(APP_NAME, f"確定要清空「{sl['name']}」的所有步驟嗎？"):
            sl["steps"] = []
            self.autosave()
            self.refresh_slots()
            self.refresh_steps()

    def set_rotate(self):
        self.s["buy_rotate"] = bool(self.vrot.get())
        self.autosave()

    def steps(self):
        return self.cur_slot().setdefault("steps", [])

    def refresh_steps(self, select=None):
        self.tv.delete(*self.tv.get_children())
        for i, st in enumerate(self.steps()):
            x = "—" if st.get("x") is None else st["x"]
            y = "—" if st.get("y") is None else st["y"]
            self.tv.insert("", "end", iid=str(i), values=(i + 1, st["name"], step_action(st), x, y,
                                                          st.get("times", 1), st.get("wait", 1)))
        if select is not None and 0 <= select < len(self.steps()):
            self.tv.selection_set(str(select))
            self.tv.see(str(select))
        if hasattr(self, "slot_cb"):
            self.refresh_slots()

    def sel_index(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def load_step(self):
        i = self.sel_index()
        if i is None:
            return
        st = self.steps()[i]
        self.st_name.set(st["name"])
        self.st_times.set(str(st.get("times", 1)))
        self.st_wait.set(str(st.get("wait", 1)))
        self.st_type.set("滾動" if st.get("type") == "scroll" else "點擊")
        self.st_dir.set("往上" if st.get("dir") == "up" else "往下")
        self.st_amount.set(str(st.get("amount", 3)))

    def apply_step(self, quiet=False):
        i = self.sel_index()
        if i is None:
            return
        try:
            times = max(1, int(float(self.st_times.get())))
            wait = max(0.1, float(self.st_wait.get()))
            amount = max(1, int(float(self.st_amount.get() or 3)))
        except ValueError:
            if not quiet:
                messagebox.showerror(APP_NAME, "次數、秒數、格數要是數字")
            return
        st = self.steps()[i]
        new = dict(name=self.st_name.get().strip() or st["name"], times=times, wait=wait,
                   type="scroll" if self.st_type.get() == "滾動" else "click",
                   dir="up" if self.st_dir.get() == "往上" else "down", amount=amount)
        if all(st.get(k) == v for k, v in new.items()):
            return
        st.update(new)
        self.autosave()
        self.refresh_steps(i)

    def add_step(self):
        self.steps().append({"name": "點「購買」", "type": "click", "x": None, "y": None, "times": 3, "wait": 1.0})
        self.autosave()
        self.refresh_steps(len(self.steps()) - 1)

    def add_scroll(self):
        i = self.sel_index()
        st = {"name": "滾動商品清單", "type": "scroll", "dir": "down", "amount": 3,
              "x": None, "y": None, "times": 1, "wait": 0.8}
        pos = len(self.steps()) if i is None else i + 1  # 插在選中步驟後面
        self.steps().insert(pos, st)
        self.autosave()
        self.refresh_steps(pos)

    def del_step(self):
        i = self.sel_index()
        if i is None:
            return
        del self.steps()[i]
        self.autosave()
        self.refresh_steps(min(i, len(self.steps()) - 1))

    def move_step(self, d):
        i = self.sel_index()
        st = self.steps()
        if i is None or not (0 <= i + d < len(st)):
            return
        st[i], st[i + d] = st[i + d], st[i]
        self.autosave()
        self.refresh_steps(i + d)

    def buy_template(self):
        if self.steps() and not messagebox.askyesno(APP_NAME, f"要用範本取代「{self.cur_slot()['name']}」目前的步驟嗎？"):
            return
        self.cur_slot()["steps"] = [{"name": n, "type": "click", "x": None, "y": None, "times": t, "wait": w}
                                    for n, t, w in BUY_TEMPLATE]
        self.autosave()
        self.refresh_steps(0)
        if messagebox.askyesno(APP_NAME, "範本建立好了。\n\n請先在瀏覽器打開遊戲，把「物品 → 商店」打開到要買的商品那一頁，"
                                         "然後按「是」開始依序選位置。\n（第一步「打開物品」請點左邊欄的「物品」按鈕）"):
            self.pick_all()

    def set_step_pos(self, i, x, y):
        st = self.steps()[i]
        st["x"], st["y"] = int(x), int(y)
        self.autosave()
        self.refresh_steps(i)

    def pick_step(self):
        i = self.sel_index()
        if i is None:
            messagebox.showinfo(APP_NAME, "先在列表選一個步驟")
            return
        self.pick_point(f"第 {i + 1} 步：點一下「{self.steps()[i]['name']}」的位置（Esc 取消）",
                        lambda x, y: self.set_step_pos(i, x, y))

    def pick_all(self, i=0):
        if i >= len(self.steps()):
            messagebox.showinfo(APP_NAME, "全部位置都選好了！可以按「立即買一次」測試。")
            return
        self.refresh_steps(i)
        self.pick_point(f"第 {i + 1}/{len(self.steps())} 步：點「{self.steps()[i]['name']}」的位置（Esc 結束）",
                        lambda x, y: (self.set_step_pos(i, x, y), self.root.after(250, lambda: self.pick_all(i + 1))))

    def collect_buy(self):
        try:
            off = float(self.vboff.get() or 0)
            every = float(self.vbevery.get() or 30)
            if every <= 0 or off < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_NAME, "請輸入正確的秒數／分鐘數")
            return False
        self.s.update(buy_mode=self.vbmode.get(), buy_offset=off, buy_every=every, buy_now=self.vbnow.get())
        save_settings(self.s)
        return True

    def toggle_buy(self):
        if self.buyer.running:
            self.buyer.stop()
            return
        if not self.collect_buy():
            return
        pool = [st for sl in self.slots() for st in sl.get("steps", [])] if self.s.get("buy_rotate") else self.steps()
        if not any(st.get("x") is not None for st in pool):
            messagebox.showinfo(APP_NAME, "還沒有設定步驟位置。先按「建立購買範本」。")
            return
        self.buyer.start()

    def buy_once(self):
        if self.collect_buy():
            threading.Thread(target=self.buyer.run_once, daemon=True).start()

    def refresh_buy(self):
        if self.buyer.running:
            self.bbtn.config(text="■  停止自動購買  (F10)")
            self.bbtn.set_colors(PAL["red"], PAL["red_h"])
        else:
            self.bbtn.config(text="▶  開始自動購買  (F10)")
            self.bbtn.set_colors(PAL["sky"], PAL["sky_h"])

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
            self.btn.config(text="■  停止自動收成  (F9)")
            self.btn.set_colors(PAL["red"], PAL["red_h"])
        else:
            self.btn.config(text="▶  開始自動收成  (F9)")
            self.btn.set_colors(PAL["accent"], PAL["accent_h"])

    def poll(self):
        st = self.clicker.status()
        nxt = st["next_in"]
        nxt_s = f"{nxt // 60} 分 {nxt % 60:02d} 秒" if nxt >= 120 else f"{nxt} 秒"
        auto = " · 🤖 自動判斷" if (self.s.get("auto_rate") and self.smart_used) else ""
        self.status.config(text=(f"執行中 · 下次 {nxt_s}{auto}" if st["running"] else "已停止") + f" · 已點 {st['count']} 次")
        self.bstatus.config(text=self.buyer.status())
        for chip, name, on in ((self.chip_h, "收成", st["running"]), (self.chip_b, "購買", self.buyer.running)):
            chip.config(text=f"{name} ● {'執行中' if on else '停止'}", bg="#1F5134" if on else "#2D3346",
                        fg="#7CF0A6" if on else "#C9CEDC")
        self.bglbl.config(text=self.bg.state if self.bg.running() or self.bg.state != "啟動中…" else "未開啟")
        self.bgbtn.config(text="關閉專用背景視窗" if self.bg.running() else "開啟專用背景視窗（要另外登入）")
        on_buy_tab = self.cur_tab == 1
        for vk in (VK_F8, VK_F9, VK_F10):
            down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            if down and not self._keys[vk]:
                if vk == VK_F8:
                    x, y = get_cursor()
                    if on_buy_tab:
                        i = self.sel_index()
                        if i is not None:
                            self.set_step_pos(i, x, y)
                    else:
                        self.vx.set(x)
                        self.vy.set(y)
                        self.collect()
                elif vk == VK_F9:
                    self.toggle()
                else:
                    self.toggle_buy()
            self._keys[vk] = down
        self.root.after(100, self.poll)

    def quit(self, silent=False):
        self.clicker.stop()
        self.buyer.stop()
        if not silent and self.bg.running() and messagebox.askyesno(APP_NAME, "要一起關掉背景遊戲視窗嗎？\n（選「否」視窗會留著，面板繼續跑，但重新整理後就不會自動放回面板）"):
            self.bg.stop()
        self.bg.stop_evt.set()
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        if silent:
            save_settings(self.s)
        else:
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
    finish_update_if_requested()
    if len(sys.argv) >= 3 and sys.argv[1] == "--read-game":  # 自我檢查：把讀到的遊戲數字寫到檔案
        _st = read_game_state()
        with open(sys.argv[2], "w", encoding="utf-8") as _f:
            json.dump({"state": _st, "text": describe_state(_st), "wait": smart_wait_seconds(_st)}, _f, ensure_ascii=False)
        sys.exit(0)
    App().run()
