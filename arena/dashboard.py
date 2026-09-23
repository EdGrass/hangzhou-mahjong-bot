"""arena —— 本地数据工厂 + 训练/跑分面板（FastAPI）。

面板（M3.5 初版，localhost:8088）只读监控：
  GET /                 总览 + 趋势 + 最近对局（自动刷新）
  GET /api/metrics      汇总快照（arena/metrics.json）
  GET /api/history      批次历史（趋势图数据）
  GET /api/games?n=100  最近 n 局
数据由 arena.runner 进程独立写入 var/arena/，面板进程只读（进程解耦）。
运行：python -m uvicorn arena.dashboard:app --host 127.0.0.1 --port 8088
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "var", "arena")

app = FastAPI(title="杭麻 Arena 面板")
STATE = {"data_dir": DEFAULT_DIR}


def _load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _tail(path, n):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[-n:] if l.strip()]


@app.get("/api/metrics")
def api_metrics():
    return _load(os.path.join(STATE["data_dir"], "metrics.json")) or {}


@app.get("/api/history")
def api_history(combo: str = ""):
    rows = _tail(os.path.join(STATE["data_dir"], "history.jsonl"), 500)
    return [r for r in rows if not combo or r.get("combo") == combo]


@app.get("/api/games")
def api_games(n: int = 100):
    return _tail(os.path.join(STATE["data_dir"], "games.jsonl"), n)


PAGE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>杭麻 Arena 训练面板</title>
<style>
 body{font-family:system-ui;background:#14161c;color:#e6e8ee;margin:0;padding:16px}
 h1{font-size:18px} h2{font-size:14px;color:#9aa3b2;margin:24px 0 8px}
 table{border-collapse:collapse;font-size:13px;width:100%}
 th,td{border:1px solid #2a2e3a;padding:6px 10px;text-align:center}
 th{background:#1d2029} td.num{font-variant-numeric:tabular-nums}
 .pos{color:#7ee08a}.neg{color:#ff8282}
 canvas{background:#0d0f14;border:1px solid #2a2e3a}
 #status{color:#9aa3b2;font-size:12px;margin:8px 0}
</style></head><body>
<h1>杭麻 Arena · 训练/评估面板</h1>
<div id="status">加载中…</div>
<h2>总览（按组合×策略身份聚合）</h2>
<table id="ov"><tr><th>组合</th><th>局数</th>
<th>身份明细（均分 / 胡率）</th><th>流局率</th><th>累计耗时</th></tr></table>
<h2>趋势（各策略身份胡率 vs 批次）</h2>
<canvas id="cv" width="960" height="260"></canvas>
<h2>最近对局</h2>
<table id="g"><tr><th>时间</th><th>组合</th><th>结果总分</th>
<th>胡/吃/碰/杠</th><th>流局</th><th>违规</th></tr></table>
<script>
const FMT=new Intl.DateTimeFormat('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
async function j(p){const r=await fetch(p);return r.json();}
function td(s,cls){const e=document.createElement('td');e.textContent=s;
 if(cls)e.className=cls;return e;}
async function refresh(){
 const [m,h,g]=await Promise.all([j('/api/metrics'),j('/api/history'),
   j('/api/games?n=60')]);
 document.getElementById('status').textContent=
  '更新于 '+FMT.format(new Date((m.updated_at||0)*1000))+
  ' · 总批次 '+m.total_batches+' · 最近局数 '+g.length;
 const ov=document.getElementById('ov');
 while(ov.rows.length>1)ov.deleteRow(1);
 const combos=Object.entries(m.combos||{});
 for(const [name,c] of combos){
  const r=ov.insertRow();
  r.appendChild(td(name));
  r.appendChild(td(c.games+''));
  const parts=(c.identities||[]).map(v=>
    v.name+': '+(v.avg_tot>=0?'+':'')+v.avg_tot+' / '+(v.hu_rate*100).toFixed(1)+'%');
  r.appendChild(td(parts.join(' ｜ ')));
  r.appendChild(td(c.draw_rate.toFixed(3)));
  r.appendChild(td(c.secs+'s'));
 }
 // 趋势：按 身份名 折线（胡率/局）
 const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
 ctx.clearRect(0,0,cv.width,cv.height);
 const W=cv.width,H=cv.height,padL=46,padB=24,padT=24;
 ctx.strokeStyle='#333';ctx.fillStyle='#9aa3b2';ctx.font='11px system-ui';
 for(let gv of [0,0.05,0.1,0.15,0.2]){const Y=H-padB-gv/0.25*(H-padB-padT);
  ctx.beginPath();ctx.moveTo(padL,Y);ctx.lineTo(W-8,Y);ctx.stroke();
  ctx.fillText(gv.toFixed(2),4,Y+4);}
 ctx.fillText('胡率/局',6,padT-8);
 const series={};
 for(const b of h)for(const id of (b.identities||[]))
  (series[id.name]=series[id.name]||[]).push({i:series[id.name]?series[id.name].length:0,v:id.hu_rate});
 const cols=['#7ee08a','#6cb2ff','#ffb86c','#ff8282','#c792ea'];
 let ci=0;
 for(const [nm,pts] of Object.entries(series)){
  ctx.strokeStyle=cols[ci%cols.length];ctx.beginPath();
  pts.forEach((p,idx)=>{const X=padL+(pts.length===1?0.5:idx/(pts.length-1))*(W-padL-8);
   const Y=H-padB-p.v/0.25*(H-padB-padT);
   idx?ctx.lineTo(X,Y):ctx.moveTo(X,Y);});
  ctx.stroke();
  ctx.fillStyle=cols[ci%cols.length];
  ctx.fillText(nm+' ('+pts[pts.length-1].v.toFixed(3)+')',padL+6,padT-8+ci*14);
  ci++;
 }
 const gt=document.getElementById('g');
 while(gt.rows.length>1)gt.deleteRow(1);
 for(const x of g){
  const r=gt.insertRow();const st=x.stats||{};
  r.appendChild(td(FMT.format(new Date(x.ts*1000))));
  r.appendChild(td(x.combo));
  r.appendChild(td('['+(x.totals||[]).join(', ')+']',
    (x.totals||[]).reduce((a,b)=>a+b,0)>=0?'pos':'neg'));
  r.appendChild(td([st.hu_count,st.chi,st.peng,st.gang]
    .map(a=>(a||[]).reduce((s,v)=>s+v,0)).join(' / ')));
  r.appendChild(td((st.draw_count||0)+''));
  r.appendChild(td((st.violations||0)+''));
 }
}
setInterval(refresh,3000);refresh();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE
