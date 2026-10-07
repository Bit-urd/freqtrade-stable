"""Standalone comparison viewer; no external assets or network requests."""
import csv,json
from pathlib import Path
D=Path(__file__).resolve().parent/'representative_assets'
plan=json.loads((D/'plan.json').read_text());rows=list(csv.DictReader((D/'summary.csv').open()))
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>代表性标的策略对比</title>
<style>body{font:15px system-ui;margin:30px;background:#f7f8fa;color:#1c2534}h1{font-size:24px}select{padding:8px;margin:8px}table{border-collapse:collapse;width:100%;background:white}th,td{padding:12px;border-bottom:1px solid #e3e7ec;text-align:right}th:first-child,td:first-child{text-align:left}.good{background:#e5f6eb}.bad{background:#ffe7e7}.mixed{background:#fff3d6}small{color:#627087}svg{background:white;max-width:900px;width:100%;border:1px solid #dde3eb}#legend{display:flex;gap:15px;flex-wrap:wrap;margin:12px 0}p{max-width:1000px;line-height:1.6}</style>
<h1>不同标的、不同周期：策略与持有</h1><p>每组独立 1000 USDT、单币单槽位、单边手续费 0.1%。每格：收益率 / 最大回撤。绿：收益和回撤同时好于原 Portfolio；红：两者同时变差；黄：有得有失。缺少上市前历史的组不测试。各时间窗口重叠，不能把收益相加。</p>
<label>周期 <select id="window"></select></label><label>查看单币收益与回撤 <select id="coin"></select></label><div id="legend"></div><svg id="plot" viewBox="0 0 880 390"></svg><p id="dates"></p><table id="table"></table><p><small>回撤采用每日收盘总权益，未计额外滑点或盘中回撤。单币账户结果不能直接等同多币组合风控；现存上市币池存在幸存者偏差。正式版本实盘重启持久化尚未实现，运行服务未切换。</small></p>
<script>const plan=PLAN_DATA,rows=ROWS_DATA,names=[...plan.strategies,'BuyAndHold'];const short=['新正式版','原 Portfolio','分阶段','快速退出','全天个币保护','持有'],colors=['#15803d','#64748b','#7c3aed','#ea580c','#0891b2','#be123c'];
const win=document.querySelector('#window'),coin=document.querySelector('#coin');
for(const w of plan.windows){let o=document.createElement('option');o.value=w.label;o.textContent=w.label.replace('ref_','')+' '+w.timerange;win.append(o)}win.value='ref_requested_long';
for(let i=0;i<names.length;i++){let x=document.createElement('span');x.textContent='● '+short[i];x.style.color=colors[i];document.querySelector('#legend').append(x)}
function draw(){const selected=rows.filter(r=>r.window===win.value),pairs=plan.pairs.filter(p=>selected.some(r=>r.pair===p));const old=coin.value;coin.replaceChildren();for(const p of pairs){let o=document.createElement('option');o.value=p;o.textContent=p;coin.append(o)}if(pairs.includes(old))coin.value=old;
let t=document.querySelector('#table');t.replaceChildren();let head=t.insertRow();for(const text of ['标的 / 性质',...short]){let th=document.createElement('th');th.textContent=text;head.append(th)}
for(const p of pairs){let tr=t.insertRow(),label=tr.insertCell();label.textContent=p+' · '+plan.asset_types[p];let base=selected.find(r=>r.pair===p&&r.strategy===names[1]);for(const n of names){let r=selected.find(r=>r.pair===p&&r.strategy===n),td=tr.insertCell();let ret=+r.return_pct,dd=+r.wallet_drawdown_pct;td.textContent=(ret>=0?'+':'')+ret.toFixed(2)+'% / '+dd.toFixed(2)+'%';if(n!==names[1]&&n!=='BuyAndHold'){let a=ret-(+base.return_pct),b=dd-(+base.wallet_drawdown_pct);td.className=a>1e-6&&b<-1e-6?'good':a<-1e-6&&b>1e-6?'bad':'mixed'}if(n===names[0])td.style.fontWeight='bold'}}
let r=selected[0];document.querySelector('#dates').textContent=r?'实际日期：'+r.start+' ～ '+r.end+'；共 '+pairs.length+' 个标的':'';plot()}
function plot(){let rs=rows.filter(r=>r.window===win.value&&r.pair===coin.value),svg=document.querySelector('#plot');svg.replaceChildren();let ymin=Math.min(0,...rs.map(r=>+r.return_pct)),ymax=Math.max(20,...rs.map(r=>+r.return_pct));let pad=(ymax-ymin)*.12;ymin-=pad;ymax+=pad;let x=v=>65+v/100*750,y=v=>335-(v-ymin)/(ymax-ymin)*280;
function add(tag,attrs,text){let e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(let k in attrs)e.setAttribute(k,attrs[k]);if(text)e.textContent=text;svg.append(e);return e}
for(let dd=0;dd<=100;dd+=20){add('line',{x1:x(dd),x2:x(dd),y1:50,y2:335,stroke:'#e2e8f0'});add('text',{x:x(dd),y:355,'text-anchor':'middle',fill:'#64748b'},dd+'%')}
for(let i=0;i<=4;i++){let v=ymin+(ymax-ymin)*i/4;add('line',{x1:65,x2:815,y1:y(v),y2:y(v),stroke:'#e2e8f0'});add('text',{x:60,y:y(v)+5,'text-anchor':'end',fill:'#64748b'},v.toFixed(0)+'%')}
add('text',{x:440,y:383,'text-anchor':'middle'},'最大回撤 →（越小越好）');add('text',{x:65,y:24},coin.value+'：收益 ↑（越高越好）');for(let i=0;i<names.length;i++){let r=rs.find(r=>r.strategy===names[i]);if(!r)continue;let c=add('circle',{cx:x(+r.wallet_drawdown_pct),cy:y(+r.return_pct),r:i===0?9:6,fill:colors[i],opacity:.8});let title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=short[i]+' '+(+r.return_pct).toFixed(2)+'% / '+(+r.wallet_drawdown_pct).toFixed(2)+'%';c.append(title)}}
win.onchange=draw;coin.onchange=plot;draw();</script></html>'''
html=html.replace('PLAN_DATA',json.dumps(plan,ensure_ascii=False)).replace('ROWS_DATA',json.dumps(rows,ensure_ascii=False));(D/'comparison.html').write_text(html)
print('Generated standalone comparison.html')
