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
