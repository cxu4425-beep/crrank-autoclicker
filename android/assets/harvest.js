(function(){
if(window.__crac){window.__crac.show();return;}
var K='crac_cfg',c={iv:60,mode:'auto',x:50,y:50,px:10,py:90};
try{var o=JSON.parse(localStorage.getItem(K)||'{}');for(var k in o)c[k]=o[k];}catch(e){}
function save(){try{localStorage.setItem(K,JSON.stringify(c));}catch(e){}}
var t=null,tick=null,n=0,next=0,last='';
var p=document.createElement('div');
p.style.cssText='position:fixed;z-index:2147483647;background:#1e2230;color:#fff;font:14px sans-serif;padding:10px;border-radius:12px;box-shadow:0 4px 18px rgba(0,0,0,.45);width:220px;max-height:85vh;overflow:auto;touch-action:none;line-height:1.7';
p.innerHTML='<div data-h style="font-weight:bold;cursor:move;user-select:none">&#9776; 自動收成 <span style="font-weight:normal;font-size:11px;opacity:.6">v1.5</span><span data-x style="float:right;cursor:pointer;padding:0 4px">&#10005;</span></div>'+
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
'<div data-xs style="font-size:12px;opacity:.85;margin-top:4px"></div></div></div>';
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
function clSched(){clearTimeout(X.t);if(!c.cl)return;X.t=setTimeout(function(){claimAll().then(clSched);},Math.max(5,c.clm)*60000);}
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
window.__crac={show:function(){p.style.display='';showMk();}};
})();
