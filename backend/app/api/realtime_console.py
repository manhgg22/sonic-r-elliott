REALTIME_CONSOLE_HTML = r"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sonic R · WebSocket Console</title>
  <style>
    :root{color-scheme:dark;--bg:#071014;--panel:#0c171b;--line:#223238;
      --text:#d9e5e7;--muted:#789097;--cyan:#19d9ec;--green:#35e48c;
      --red:#ff6b76;--amber:#ffbe3f}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);
      font:13px Inter,system-ui,sans-serif} header{height:54px;display:flex;
      align-items:center;justify-content:space-between;padding:0 18px;border-bottom:
      1px solid var(--line);background:#081216;position:sticky;top:0;z-index:2}
    h1{font-size:15px;letter-spacing:.04em;margin:0}.brand{color:var(--cyan)}
    .links a{color:var(--muted);text-decoration:none;margin-left:16px}
    .links a:hover{color:var(--cyan)} main{padding:12px;max-width:1600px;margin:auto}
    .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
    .card,.panel{border:1px solid var(--line);background:var(--panel);padding:12px}
    .card span,.label{color:var(--muted);font-size:10px;text-transform:uppercase;
      letter-spacing:.09em}.card strong{display:block;margin-top:7px;font:600 19px
      ui-monospace,SFMono-Regular,monospace}.ok{color:var(--green)}.bad{color:var(--red)}
    .layout{display:grid;grid-template-columns:1.5fr 1fr;gap:8px;margin-top:8px}
    .panel h2{font-size:12px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.08em}
    table{width:100%;border-collapse:collapse;font:12px ui-monospace,monospace}
    th,td{text-align:right;border-bottom:1px solid #18272c;padding:7px 6px}
    th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-size:10px}
    .up{color:var(--green)}.down{color:var(--red)}#events{height:510px;overflow:auto;
      white-space:pre-wrap;font:11px/1.55 ui-monospace,monospace;color:#9cb0b5}
    .event{border-bottom:1px solid #17252a;padding:5px 0}.candle{color:var(--amber)}
    .ticker{color:var(--cyan)}.controls{display:flex;gap:6px}
    button{background:#102328;color:var(--text);border:1px solid var(--line);
      padding:7px 10px;cursor:pointer}button:hover{border-color:var(--cyan)}
    @media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}
      .layout{grid-template-columns:1fr}}
  </style>
</head>
<body>
<header>
  <h1><span class="brand">SONIC R</span> · WEBSOCKET CONSOLE</h1>
  <div class="links"><a href="/docs">Swagger</a><a href="/redoc">ReDoc</a>
    <a href="/openapi.json">OpenAPI JSON</a></div>
</header>
<main>
  <section class="grid">
    <div class="card"><span>Kết nối Sonic</span><strong id="connection">CONNECTING</strong></div>
    <div class="card"><span>OKX streams</span><strong id="streams">—</strong></div>
    <div class="card"><span>Mã realtime</span><strong id="instruments">0</strong></div>
    <div class="card"><span>Độ trễ tin cuối</span><strong id="age">—</strong></div>
  </section>
  <section class="layout">
    <div class="panel">
      <h2>Live market snapshot</h2>
      <table><thead><tr><th>Instrument</th><th>Last</th><th>Bid</th><th>Ask</th>
        <th>24h</th><th>Nến M15</th><th>Confirm</th></tr></thead>
        <tbody id="market"></tbody></table>
    </div>
    <div class="panel">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h2>Event stream</h2><div class="controls"><button id="pause">Pause</button>
        <button id="clear">Clear</button></div>
      </div>
      <div id="events"></div>
    </div>
  </section>
</main>
<script>
const state={tickers:{},candles:{},paused:false,status:{}};
const $=id=>document.getElementById(id);
function n(v){return v==null?'—':Number(v).toLocaleString('en-US',{maximumFractionDigits:8})}
function log(m){
  if(state.paused)return;
  const d=document.createElement('div');d.className='event '+(m.type||'');
  d.textContent=`${new Date().toLocaleTimeString()}  ${JSON.stringify(m)}`;
  $('events').prepend(d);while($('events').children.length>150)$('events').lastChild.remove();
}
function render(){
  const s=state.status||{}, streams=s.streams||{};
  $('streams').textContent=`TICK ${streams.tickers?.connected?'LIVE':'DOWN'} · CANDLE ${streams.candles?.connected?'LIVE':'DOWN'}`;
  $('streams').className=s.connected?'ok':'bad';
  $('instruments').textContent=s.instruments||Object.keys(state.tickers).length;
  $('age').textContent=s.message_age_seconds==null?'—':`${Number(s.message_age_seconds).toFixed(2)}s`;
  const ids=Object.keys(state.tickers).sort().slice(0,50);
  $('market').innerHTML=ids.map(id=>{
    const t=state.tickers[id]||{},c=state.candles[id]||{};
    const change=t.open_24h?((t.last/t.open_24h-1)*100):0;
    return `<tr><td>${id}</td><td>${n(t.last)}</td><td>${n(t.bid)}</td><td>${n(t.ask)}</td>
      <td class="${change>=0?'up':'down'}">${change.toFixed(2)}%</td><td>${n(c.close)}</td>
      <td class="${c.confirmed?'ok':'candle'}">${c.confirmed?'CLOSED':'LIVE'}</td></tr>`}).join('');
}
function connect(){
  const scheme=location.protocol==='https:'?'wss':'ws';
  const ws=new WebSocket(`${scheme}://${location.host}/api/v1/market/stream`);
  ws.onopen=()=>{$('connection').textContent='LIVE';$('connection').className='ok'};
  ws.onclose=()=>{$('connection').textContent='RECONNECTING';$('connection').className='bad';setTimeout(connect,1500)};
  ws.onerror=()=>ws.close();
  ws.onmessage=e=>{const m=JSON.parse(e.data);
    if(m.type==='snapshot'){state.tickers=m.tickers||{};state.candles=m.candles||{};state.status=m.status||{}}
    else if(m.type==='batch'){Object.assign(state.tickers,m.tickers||{});Object.assign(state.candles,m.candles||{})}
    else if(m.type==='ticker')state.tickers[m.instrument_id]=m;
    else if(m.type==='candle')state.candles[m.instrument_id]=m;
    else if(m.status)state.status=m.status;
    log(m);render();
  };
}
$('pause').onclick=()=>{state.paused=!state.paused;$('pause').textContent=state.paused?'Resume':'Pause'};
$('clear').onclick=()=>$('events').innerHTML='';
connect();setInterval(render,1000);
</script>
</body></html>"""
