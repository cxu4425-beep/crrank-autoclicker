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
            "buy_slot": 0, "buy_rotate": False}
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
if(window.__crac){window.__crac.show();return;}
var K='crac_cfg',c={iv:60,mode:'auto',x:50,y:50,px:10,py:90};
try{var o=JSON.parse(localStorage.getItem(K)||'{}');for(var k in o)c[k]=o[k];}catch(e){}
function save(){try{localStorage.setItem(K,JSON.stringify(c));}catch(e){}}
var t=null,tick=null,n=0,next=0,last='';
var p=document.createElement('div');
p.style.cssText='position:fixed;z-index:2147483647;background:#1e2230;color:#fff;font:14px sans-serif;padding:10px;border-radius:12px;box-shadow:0 4px 18px rgba(0,0,0,.45);width:220px;max-height:85vh;overflow:auto;touch-action:none;line-height:1.7';
p.innerHTML='<div data-h style="font-weight:bold;cursor:move;user-select:none">&#9776; 自動收成<span data-x style="float:right;cursor:pointer;padding:0 4px">&#10005;</span></div>'+
'<label>間隔(秒) <input data-iv type="number" min="1" style="width:80px;font-size:14px"></label><br>'+
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
'<div data-bs style="font-size:12px;opacity:.85;margin-top:4px">勾選要買的商品後按開始</div></div></div>';
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
function start(){if(t)return;c.run=true;save();doClick();t=setInterval(doClick,c.iv*1000);tick=setInterval(upd,1000);var g=q('data-go');g.textContent='停止';g.style.background='#ff6b6b';upd();}
function stop(){c.run=false;save();clearInterval(t);clearInterval(tick);t=null;var g=q('data-go');g.textContent='開始';g.style.background='#ffc93c';upd();}
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
async function buyRun(){if(B.busy)return;B.busy=true;bupd();var got=[];try{var o=await openShop();if(!o){B.log='打不開商店（先關掉其他視窗）';return;}
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
if(c.run)setTimeout(start,1500);
if(c.bon&&c.buy.length)setTimeout(function(){if(!B.on){B.on=true;B.log='自動接續';buyRun().then(bsched);}},4000);
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
        self.buyer = BuyRunner(self.s)
        self.buyer.on_change = lambda: self.root.after(0, self.refresh_buy)
        self.bg = BgBrowser()
        self.server = None
        self.url = ""
        self.build_ui()
        self.start_server()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(200, self.poll)
        self._keys = {VK_F8: False, VK_F9: False, VK_F10: False}

    def toggle_bg(self):
        if self.bg.running():
            self.bg.stop()
        elif not self.bg.start():
            messagebox.showerror(APP_NAME, "找不到 Chrome 或 Edge，背景模式需要其中一個。")

    # ----- UI -----
    def build_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.nb = nb
        pc = ttk.Frame(nb, padding=10)
        buy = ttk.Frame(nb, padding=10)
        ph = ttk.Frame(nb, padding=10)
        nb.add(pc, text=" 電腦連點 ")
        nb.add(buy, text=" 自動購買 ")
        nb.add(ph, text=" 手機 ")
        self.buy_tab = buy
        self.build_buy_tab(buy)

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
        r += 1
        ttk.Separator(pc).grid(row=r, column=0, columnspan=4, sticky="we", pady=6)
        r += 1
        ttk.Label(pc, text="🌙 背景模式（遊戲不用放在前台）", font=("Microsoft JhengHei UI", 10, "bold")).grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        self.bgbtn = ttk.Button(pc, text="開啟背景遊戲視窗", command=self.toggle_bg)
        self.bgbtn.grid(row=r, column=0, columnspan=4, sticky="we")
        r += 1
        self.bglbl = ttk.Label(pc, text="未開啟", foreground="#2a6db0", wraplength=380)
        self.bglbl.grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        ttk.Label(pc, foreground="#666", wraplength=380, justify="left", text=(
            "會開一個專用的 Chrome／Edge 視窗，第一次要在裡面用 Discord 登入。遊戲頁會自動出現面板，"
            "在面板設定收成和「🛒 自動購買」後按開始，之後視窗可以縮小或被其他視窗蓋住，照樣會繼續點。"
            "背景模式期間電腦不會自動睡眠。")).grid(row=r, column=0, columnspan=4, sticky="w")

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
            "iPhone 也能用：掃描後照頁面裡的「iPhone 教學」設定。\n"
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
        f.columnconfigure(1, weight=1)
        head = ttk.Frame(f)
        head.grid(row=0, column=0, columnspan=4, sticky="we")
        ttk.Label(head, text="自動購買（照順序模擬點擊）", font=("Microsoft JhengHei UI", 10, "bold")).pack(side="left")
        self.saved_lbl = ttk.Label(head, text="", foreground="#2a8a2a")
        self.saved_lbl.pack(side="right")
        sr = ttk.Frame(f)
        sr.grid(row=1, column=0, columnspan=4, sticky="we", pady=(2, 0))
        ttk.Label(sr, text="存檔").pack(side="left")
        self.vslot = tk.StringVar()
        self.slot_cb = ttk.Combobox(sr, textvariable=self.vslot, state="readonly", width=12)
        self.slot_cb.pack(side="left", padx=4)
        self.slot_cb.bind("<<ComboboxSelected>>", lambda e: self.switch_slot(self.slot_cb.current()))
        ttk.Button(sr, text="改名", width=5, command=self.rename_slot).pack(side="left")
        ttk.Button(sr, text="清空", width=5, command=self.clear_slot).pack(side="left", padx=2)
        self.vrot = tk.BooleanVar(value=self.s.get("buy_rotate", False))
        ttk.Checkbutton(sr, text="自動輪播（做完一個存檔接下一個）", variable=self.vrot,
                        command=self.set_rotate).pack(side="left", padx=(6, 0))

        cols = ("n", "name", "act", "x", "y", "times", "wait")
        tv = ttk.Treeview(f, columns=cols, show="headings", height=6, selectmode="browse")
        for c, t, w in zip(cols, ("#", "步驟", "動作", "X", "Y", "次數", "等待秒"), (28, 160, 70, 50, 50, 40, 50)):
            tv.heading(c, text=t)
            tv.column(c, width=w, anchor="w" if c == "name" else "center", stretch=(c == "name"))
        tv.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(4, 4))
        tv.bind("<<TreeviewSelect>>", lambda e: self.load_step())
        self.tv = tv

        ed = ttk.Frame(f)
        ed.grid(row=3, column=0, columnspan=4, sticky="we")
        self.st_name = tk.StringVar()
        self.st_times = tk.StringVar(value="1")
        self.st_wait = tk.StringVar(value="1")
        self.st_type = tk.StringVar(value="點擊")
        self.st_dir = tk.StringVar(value="往下")
        self.st_amount = tk.StringVar(value="3")
        ttk.Label(ed, text="名稱").pack(side="left")
        e1 = ttk.Entry(ed, textvariable=self.st_name, width=14)
        e1.pack(side="left", padx=(2, 6))
        ttk.Label(ed, text="重複").pack(side="left")
        e2 = ttk.Entry(ed, textvariable=self.st_times, width=3)
        e2.pack(side="left")
        ttk.Label(ed, text="次 做完等").pack(side="left")
        e3 = ttk.Entry(ed, textvariable=self.st_wait, width=4)
        e3.pack(side="left")
        ttk.Label(ed, text="秒").pack(side="left")
        ed2 = ttk.Frame(f)
        ed2.grid(row=4, column=0, columnspan=4, sticky="we", pady=(2, 0))
        ttk.Label(ed2, text="動作").pack(side="left")
        c1 = ttk.Combobox(ed2, textvariable=self.st_type, values=("點擊", "滾動"), state="readonly", width=5)
        c1.pack(side="left", padx=(2, 6))
        ttk.Label(ed2, text="滾動方向").pack(side="left")
        c2 = ttk.Combobox(ed2, textvariable=self.st_dir, values=("往下", "往上"), state="readonly", width=5)
        c2.pack(side="left", padx=2)
        e4 = ttk.Entry(ed2, textvariable=self.st_amount, width=3)
        e4.pack(side="left")
        ttk.Label(ed2, text="格").pack(side="left")
        ttk.Button(ed2, text="套用", width=5, command=self.apply_step).pack(side="left", padx=6)
        for w in (e1, e2, e3, e4):  # 改完自動套用＋自動存檔
            w.bind("<Return>", lambda e: self.apply_step())
            w.bind("<FocusOut>", lambda e: self.apply_step(quiet=True))
        for w in (c1, c2):
            w.bind("<<ComboboxSelected>>", lambda e: self.apply_step())

        b1 = ttk.Frame(f)
        b1.grid(row=5, column=0, columnspan=4, sticky="we", pady=(4, 0))
        for i, (t, cmd) in enumerate((("📋 建立購買範本", self.buy_template), ("➕ 點擊步驟", self.add_step),
                                      ("➕ 滾動步驟", self.add_scroll), ("🗑 刪除", self.del_step))):
            ttk.Button(b1, text=t, command=cmd).grid(row=0, column=i, sticky="we", padx=1)
            b1.columnconfigure(i, weight=1)
        b2 = ttk.Frame(f)
        b2.grid(row=6, column=0, columnspan=4, sticky="we")
        for i, (t, cmd) in enumerate((("🎯 選位置", self.pick_step), ("🎯 依序選全部", self.pick_all),
                                      ("↑", lambda: self.move_step(-1)), ("↓", lambda: self.move_step(1)))):
            ttk.Button(b2, text=t, command=cmd).grid(row=0, column=i, sticky="we", padx=1)
            b2.columnconfigure(i, weight=1 if i < 2 else 0)
        ttk.Label(f, text="選中步驟後，把滑鼠移到目標上按 F8 也能記錄位置；滾動步驟的位置＝要捲的清單上",
                  foreground="#666", wraplength=420).grid(row=7, column=0, columnspan=4, sticky="w")

        ttk.Separator(f).grid(row=8, column=0, columnspan=4, sticky="we", pady=6)
        self.vbmode = tk.StringVar(value=self.s.get("buy_mode", "restock"))
        self.vboff = tk.StringVar(value=str(self.s.get("buy_offset", 10)))
        self.vbevery = tk.StringVar(value=str(self.s.get("buy_every", 30)))
        r1 = ttk.Frame(f)
        r1.grid(row=9, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(r1, text="每次補貨後（整點、半點）過", variable=self.vbmode, value="restock").pack(side="left")
        ttk.Entry(r1, textvariable=self.vboff, width=4).pack(side="left")
        ttk.Label(r1, text="秒").pack(side="left")
        r2 = ttk.Frame(f)
        r2.grid(row=10, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(r2, text="每", variable=self.vbmode, value="interval").pack(side="left")
        ttk.Entry(r2, textvariable=self.vbevery, width=5).pack(side="left")
        ttk.Label(r2, text="分鐘").pack(side="left")
        self.vbnow = tk.BooleanVar(value=self.s.get("buy_now", True))
        ttk.Checkbutton(f, text="按開始時立刻先買一次", variable=self.vbnow).grid(row=11, column=0, columnspan=4, sticky="w")
        self.bbtn = tk.Button(f, text="▶ 開始自動購買 (F10)", font=("Microsoft JhengHei UI", 12, "bold"), bg="#8fd3ff",
                              relief="flat", command=self.toggle_buy)
        self.bbtn.grid(row=12, column=0, columnspan=4, sticky="we", pady=(8, 2))
        ttk.Button(f, text="立即買一次（測試）", command=self.buy_once).grid(row=13, column=0, columnspan=4, sticky="we")
        self.bstatus = ttk.Label(f, text="已停止", wraplength=420)
        self.bstatus.grid(row=14, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Label(f, foreground="#666", wraplength=420, justify="left", text=(
            "用法：按「建立購買範本」→ 先在瀏覽器打開商店確認位置，再按「依序選全部」把每一步點在對應按鈕上。"
            "商品在下面看不到時，在「購買」前加一個「滾動步驟」。開始前「物品」視窗要先關著，遊戲畫面不要被擋住。"
            "步驟會自動存到目前的存檔。")).grid(row=15, column=0, columnspan=4, sticky="w", pady=(4, 0))
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
            self.bbtn.config(text="■ 停止自動購買 (F10)", bg="#ff6b6b")
        else:
            self.bbtn.config(text="▶ 開始自動購買 (F10)", bg="#8fd3ff")

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
        self.bstatus.config(text=self.buyer.status())
        self.bglbl.config(text=self.bg.state if self.bg.running() or self.bg.state != "啟動中…" else "未開啟")
        self.bgbtn.config(text="關閉背景遊戲視窗" if self.bg.running() else "開啟背景遊戲視窗")
        on_buy_tab = self.nb.select() == str(self.buy_tab)
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

    def quit(self):
        self.clicker.stop()
        self.buyer.stop()
        if self.bg.running() and messagebox.askyesno(APP_NAME, "要一起關掉背景遊戲視窗嗎？\n（選「否」視窗會留著，面板繼續跑，但重新整理後就不會自動放回面板）"):
            self.bg.stop()
        self.bg.stop_evt.set()
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
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
