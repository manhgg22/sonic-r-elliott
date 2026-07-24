import { useEffect, useMemo, useState } from "react";
import { Button, Input, message, Progress, Segmented, Select, Tag } from "antd";
import {
  Activity, BarChart3, BookOpen, ChevronRight, CircleDollarSign,
  Code2, Crosshair, Database, Gauge, History, LayoutDashboard,
  Play, RefreshCw, Search, Server, ShieldAlert, Wifi
} from "lucide-react";
import { getTerminalSnapshot, runScanner } from "./api";
import { MarketChart } from "./MarketChart";
import { useMarketSocket } from "./useMarketSocket";
import type {
  MarketState, PaperEvent, Run, Setup, TerminalSnapshot, Trade
} from "./types";

type Page = "terminal" | "scanner" | "signal" | "portfolio" | "api";
const EMPTY: TerminalSnapshot = { setups: [], runs: [], trades: [], events: [] };
const GATES = [
  ["f_trend", "Xu hướng EMA"],
  ["f_breakout", "Breakout"],
  ["f_dow", "Cấu trúc Dow"],
  ["f_value_zone", "Vùng giá trị"],
  ["f_pa", "Price Action"]
] as const;

const num = (value: unknown, digits = 4) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", {
    maximumFractionDigits: Math.abs(n) >= 1000 ? 2 : digits
  });
};
const text = (value: unknown) => String(value ?? "—");
const truthy = (value: unknown) => value === true || value === 1 || value === "1";
const cls = (side: unknown) => text(side).toLowerCase() === "long" ? "positive" : "negative";

function Panel({ title, meta, children, className = "" }: {
  title: string; meta?: string; children: React.ReactNode; className?: string;
}) {
  return <section className={`panel ${className}`}>
    <header className="panel-heading"><h2>{title}</h2>{meta && <span>{meta}</span>}</header>
    {children}
  </section>;
}

function Kpi({ label, value, tone = "" }: { label: string; value: string; tone?: string }) {
  return <div className="kpi"><span>{label}</span><strong className={tone}>{value}</strong></div>;
}

function GateList({ setup }: { setup?: Setup }) {
  return <div className="gate-list">{GATES.map(([key, label], index) => {
    const pass = setup ? truthy(setup[key]) : false;
    return <div className="gate" key={key}>
      <span><i>{index + 1}</i>{label}</span>
      <b className={pass ? "positive" : "warning"}>{pass ? "PASS" : "WAIT"}</b>
    </div>;
  })}</div>;
}

function Level({ label, value, tone = "" }: { label: string; value: unknown; tone?: string }) {
  return <div className="level"><span>{label}</span><b className={tone}>{num(value)}</b></div>;
}

function Topbar({ page, market }: { page: Page; market: MarketState }) {
  const streams = market.status.streams ?? {};
  const tick = streams.tickers?.connected;
  const candle = streams.candles?.connected;
  const age = market.status.message_age_seconds;
  const now = new Date();
  const next = new Date(now);
  next.setMinutes(Math.floor(now.getMinutes() / 15) * 15 + 15, 5, 0);
  const seconds = Math.max(0, Math.floor((+next - +now) / 1000));
  return <header className="topbar">
    <div><span>SONIC R</span><b>{page.replace("-", " ").toUpperCase()}</b></div>
    <div className="health-strip">
      <small><i className={tick ? "dot live" : "dot down"} />OKX TICK {tick ? "LIVE" : "DOWN"}</small>
      <small><i className={candle ? "dot live" : "dot down"} />CANDLE {candle ? "LIVE" : "DOWN"}</small>
      <small>AGE <b>{age == null ? "—" : `${Number(age).toFixed(2)}s`}</b></small>
      <small>INSTRUMENTS <b>{market.status.instruments ?? 0}</b></small>
      <small>M15 CLOSE <b>{String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}</b></small>
    </div>
  </header>;
}

function Sidebar({ page, setPage }: { page: Page; setPage: (page: Page) => void }) {
  const items: Array<[Page, string, React.ReactNode]> = [
    ["terminal", "Terminal", <LayoutDashboard />],
    ["scanner", "Scanner", <Search />],
    ["signal", "Signal Detail", <BarChart3 />],
    ["portfolio", "Portfolio & Risk", <ShieldAlert />],
    ["api", "API / WebSocket", <Code2 />]
  ];
  return <aside className="sidebar">
    <div className="logo"><b>SR</b><span>SONIC R<small>ANALYTICAL TERMINAL</small></span></div>
    <nav>{items.map(([id, label, icon]) =>
      <button className={page === id ? "active" : ""} onClick={() => setPage(id)} key={id}>
        {icon}<span>{label}</span>
      </button>
    )}</nav>
    <div className="sidebar-foot"><Wifi size={13} /><span>Decision support<br />Paper execution only</span></div>
  </aside>;
}

function SetupPicker({ setups, selected, onSelect }: {
  setups: Setup[]; selected?: Setup; onSelect: (setup: Setup) => void;
}) {
  return <Select className="setup-select" value={text(selected?.symbol) + text(selected?.side)}
    options={setups.map((setup) => ({
      value: text(setup.symbol) + text(setup.side),
      label: `${text(setup.base)} · ${text(setup.side)} · ${text(setup.status)}`
    }))}
    onChange={(value) => {
      const setup = setups.find((s) => text(s.symbol) + text(s.side) === value);
      if (setup) onSelect(setup);
    }}
  />;
}

function Watchlist({ market }: { market: MarketState }) {
  const priority = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"];
  return <div>{priority.map((id) => {
    const ticker = market.tickers[id];
    const change = ticker?.open_24h ? (ticker.last / ticker.open_24h - 1) * 100 : 0;
    return <div className="watch-row" key={id}>
      <span>{id.split("-")[0]}<small>USDT PERP</small></span>
      <b>{num(ticker?.last)}<small className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</small></b>
    </div>;
  })}</div>;
}

function TerminalPage({ data, market, selected, setSelected }: {
  data: TerminalSnapshot; market: MarketState; selected?: Setup; setSelected: (s: Setup) => void;
}) {
  const ready = data.setups.filter((s) => s.status === "READY");
  const open = data.trades.filter((t) => t.status === "OPEN");
  const instrument = `${text(selected?.base === "—" ? "BTC" : selected?.base)}-USDT-SWAP`;
  return <div className="terminal-grid">
    <div className="stack">
      <Panel title="Watchlist" meta={`${Object.keys(market.tickers).length} MÃ`}><Watchlist market={market} /></Panel>
      <Panel title="5-gate status" meta={`${ready.length} READY`}>
        <SetupPicker setups={data.setups} selected={selected} onSelect={setSelected} />
        <GateList setup={selected} />
      </Panel>
    </div>
    <Panel title="Biểu đồ phân tích" meta="EMA34 · EMA89 · NẾN THẬT">
      <MarketChart instrumentId={instrument} live={market.candles[instrument]} setup={selected} />
    </Panel>
    <div className="stack">
      <Panel title="Luận điểm setup" meta="CANDLE-CLOSE">
        <div className={`side-title ${cls(selected?.side)}`}>{text(selected?.side)}</div>
        <Level label="Entry" value={selected?.entry} tone="live-text" />
        <Level label="Stop loss" value={selected?.sl} tone="negative" />
        <Level label="Take profit 1" value={selected?.tp1} tone="positive" />
        <Level label="Take profit 2" value={selected?.tp2} tone="positive" />
        <Level label="R:R TP2" value={selected?.tp2_rr} />
      </Panel>
      <Panel title="Paper positions" meta={`${open.length} MỞ`}>
        {open.slice(0, 4).map((trade) => <div className="mini-row" key={text(trade.id)}>
          <span>{text(trade.base)} · <i className={cls(trade.side)}>{text(trade.side)}</i></span><b>{num(trade.entry)}</b>
        </div>)}
        {!open.length && <div className="empty">Không có vị thế mở</div>}
      </Panel>
      <Panel title="Nhật ký hệ thống" meta="EVENTS">
        {data.events.slice(0, 5).map((event, i) => <div className="mini-row" key={i}>
          <span>{text(event.event)}</span><b>{num(event.price)}</b>
        </div>)}
      </Panel>
    </div>
  </div>;
}

function SignalPage({ data, market, selected, setSelected }: {
  data: TerminalSnapshot; market: MarketState; selected?: Setup; setSelected: (s: Setup) => void;
}) {
  const instrument = `${text(selected?.base === "—" ? "BTC" : selected?.base)}-USDT-SWAP`;
  return <div className="detail-grid">
    <Panel title={`${text(selected?.base)}/USDT · ${text(selected?.side)}`} meta="M15 · CANDLE-CLOSE">
      <SetupPicker setups={data.setups} selected={selected} onSelect={setSelected} />
      <MarketChart instrumentId={instrument} live={market.candles[instrument]} setup={selected} height={640} />
    </Panel>
    <Panel title="Luận điểm setup" meta={text(selected?.status)}>
      <GateList setup={selected} />
      <div className="score">{GATES.filter(([key]) => selected && truthy(selected[key])).length}<small>/5 GATES</small></div>
      <Level label="Entry" value={selected?.entry} tone="live-text" />
      <Level label="Stop loss" value={selected?.sl} tone="negative" />
      <Level label="Take profit 1" value={selected?.tp1} tone="positive" />
      <Level label="Take profit 2" value={selected?.tp2} tone="positive" />
      <Level label="Trailing EMA34 H1" value={selected?.trail_h1} tone="warning" />
      <div className="thesis"><b>Price Action</b><p>{text(selected?.pa)}</p>
        <b>Xác nhận lúc</b><p>{text(selected?.signal_time)}</p>
        <span>Chỉ theo dõi paper. Không gửi lệnh thật.</span></div>
    </Panel>
  </div>;
}

function ScannerPage({ data, selected, setSelected, refresh }: {
  data: TerminalSnapshot; selected?: Setup; setSelected: (s: Setup) => void; refresh: () => void;
}) {
  const [query, setQuery] = useState("");
  const [side, setSide] = useState("ALL");
  const [running, setRunning] = useState(false);
  const rows = data.setups.filter((s) =>
    (side === "ALL" || s.side === side) &&
    text(s.base).toLowerCase().includes(query.toLowerCase())
  );
  const last = data.runs.at(-1);
  return <div className="scanner-layout">
    <Panel title="Bảng quét tín hiệu" meta="CONFIRMED CANDLES ONLY">
      <div className="toolbar">
        <Segmented
          value={side}
          options={["ALL", "LONG", "SHORT"]}
          onChange={(value) => setSide(String(value))}
          size="small"
        />
        <Input
          className="scanner-search"
          prefix={<Search size={14} />}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Tìm mã..."
          allowClear
        />
        <Button className="action" loading={running} icon={<RefreshCw size={13} />} onClick={async () => {
          setRunning(true);
          try { await runScanner(); refresh(); }
          catch (e) { message.error((e as Error).message); }
          finally { setRunning(false); }
        }}>QUÉT TOÀN BỘ</Button>
      </div>
      <div className="table-wrap"><table><thead><tr>
        {["Mã", "Side", "Status", "Close", "Entry", "SL", "TP1", "TP2", "R:R", "EMA", "Break", "Dow", "Zone", "PA"].map((h) => <th key={h}>{h}</th>)}
      </tr></thead><tbody>{rows.map((s) => <tr className={selected === s ? "selected" : ""} onClick={() => setSelected(s)} key={text(s.symbol) + text(s.side)}>
        <td><b>{text(s.base)}</b></td><td className={cls(s.side)}>{text(s.side)}</td><td><Tag className={`status ${text(s.status).toLowerCase()}`}>{text(s.status)}</Tag></td>
        {[s.bar_close, s.entry, s.sl, s.tp1, s.tp2, s.tp2_rr].map((v, i) => <td key={i}>{num(v)}</td>)}
        {GATES.map(([key]) => <td className={truthy(s[key]) ? "positive" : "muted"} key={key}>{truthy(s[key]) ? "●" : "○"}</td>)}
      </tr>)}</tbody></table></div>
      <footer className="table-foot">Scan cuối {text(last?.scanned_at)} · {num(last?.success_count, 0)}/{num(last?.universe_count, 0)} thành công · {num(last?.duration_seconds, 1)}s</footer>
    </Panel>
    <Panel title="Chi tiết scan" meta={text(selected?.status)}>
      <div className="instrument-title">{text(selected?.base)}/USDT <span className={cls(selected?.side)}>{text(selected?.side)}</span></div>
      <GateList setup={selected} />
      <Button type="primary" className="primary wide" icon={<ChevronRight size={14} />}>TẠO CẢNH BÁO</Button>
    </Panel>
  </div>;
}

function liveR(trade: Trade, market: MarketState) {
  const ticker = market.tickers[`${text(trade.base)}-USDT-SWAP`];
  if (!ticker) return Number(trade.realized_r ?? 0);
  const direction = trade.side === "LONG" ? 1 : -1;
  return Number(trade.realized_r ?? 0) + Number(trade.remaining ?? 0) *
    (ticker.last - Number(trade.entry)) * direction / Number(trade.risk);
}

function PortfolioPage({ data, market }: { data: TerminalSnapshot; market: MarketState }) {
  const open = data.trades.filter((t) => t.status === "OPEN");
  const closed = data.trades.filter((t) => t.status === "CLOSED");
  const realized = closed.reduce((sum, t) => sum + Number(t.total_r ?? 0), 0);
  const unrealized = open.reduce((sum, t) => sum + liveR(t, market), 0);
  const wins = closed.filter((t) => Number(t.total_r ?? 0) > 0).length;
  return <>
    <div className="kpi-grid">
      <Kpi label="Vị thế mở" value={String(open.length)} />
      <Kpi label="Realized R" value={`${realized >= 0 ? "+" : ""}${realized.toFixed(2)}R`} tone={realized >= 0 ? "positive" : "negative"} />
      <Kpi label="Unrealized R" value={`${unrealized >= 0 ? "+" : ""}${unrealized.toFixed(2)}R`} tone={unrealized >= 0 ? "positive" : "negative"} />
      <Kpi label="Win rate" value={`${closed.length ? (wins / closed.length * 100).toFixed(1) : "0.0"}%`} />
      <Kpi label="Risk / trade" value="0.50%" />
      <Kpi label="Execution" value="PAPER" />
    </div>
    <div className="portfolio-grid">
      <Panel title="Vị thế mở" meta="LIVE PRICE · WEBSOCKET">
        <div className="table-wrap"><table><thead><tr>{["Mã", "Side", "Entry", "Live", "SL", "TP1", "TP2", "Còn lại", "Live R"].map((x) => <th key={x}>{x}</th>)}</tr></thead>
          <tbody>{open.map((t) => { const r = liveR(t, market); return <tr key={text(t.id)}>
            <td><b>{text(t.base)}</b></td><td className={cls(t.side)}>{text(t.side)}</td><td>{num(t.entry)}</td>
            <td>{num(market.tickers[`${text(t.base)}-USDT-SWAP`]?.last)}</td><td>{num(t.current_sl)}</td><td>{num(t.tp1)}</td><td>{num(t.tp2)}</td>
            <td>{(Number(t.remaining) * 100).toFixed(0)}%</td><td className={r >= 0 ? "positive" : "negative"}>{r >= 0 ? "+" : ""}{r.toFixed(2)}R</td>
          </tr>; })}</tbody></table></div>
      </Panel>
      <Panel title="Quản trị rủi ro" meta="RISK PANEL">
        <div className="risk-total"><span>Tổng risk danh mục</span><strong>{(open.length * .5).toFixed(2)}%</strong></div>
        <Progress
          className="risk-progress"
          percent={Math.min(open.length * 10, 100)}
          strokeColor="#ffbe3f"
          trailColor="#17262b"
          showInfo={false}
          size="small"
        />
        <div className="alert warning-box"><ShieldAlert /><span><b>Rủi ro tương quan</b>Kiểm tra các vị thế cùng chiều trước khi mở mới.</span></div>
        <div className="alert ok-box"><Activity /><span><b>Guardrail</b>Paper-only và giới hạn 0.5% mỗi lệnh.</span></div>
      </Panel>
    </div>
    <div className="bottom-grid">
      <Panel title="Equity theo R" meta={`${closed.length} CLOSED TRADES`}>
        <div className="equity-bars">{closed.slice(-30).map((t, i) => <i key={i} className={Number(t.total_r) >= 0 ? "win" : "loss"} style={{ height: `${Math.min(95, 18 + Math.abs(Number(t.total_r)) * 35)}%` }} />)}</div>
      </Panel>
      <Panel title="Lifecycle events" meta="PAPER ENGINE">
        {data.events.slice(0, 7).map((e, i) => <div className="mini-row" key={i}><span>{text(e.event_at)}</span><b>{text(e.event)} · {num(e.price)}</b></div>)}
      </Panel>
    </div>
  </>;
}

function ApiPage({ market }: { market: MarketState }) {
  const streams = market.status.streams ?? {};
  const tickerRows = Object.entries(market.tickers).sort().slice(0, 50);
  const latest = market.events.at(-1) ?? { status: "waiting" };
  return <>
    <div className="kpi-grid">
      <Kpi label="Sonic API" value="HEALTHY" tone="positive" />
      <Kpi label="Tick stream" value={streams.tickers?.connected ? "LIVE" : "DOWN"} tone={streams.tickers?.connected ? "positive" : "negative"} />
      <Kpi label="Candle stream" value={streams.candles?.connected ? "LIVE" : "DOWN"} tone={streams.candles?.connected ? "positive" : "negative"} />
      <Kpi label="Instruments" value={String(market.status.instruments ?? 0)} />
      <Kpi label="Clients" value={String(market.status.clients ?? 0)} />
      <Kpi label="Sequence" value={String(market.sequence)} />
    </div>
    <div className="api-grid">
      <Panel title="Live market state" meta={`${tickerRows.length} TICKERS`}>
        <div className="table-wrap"><table><thead><tr>{["Instrument", "Last", "Bid", "Ask", "24h", "M15", "Confirm"].map((x) => <th key={x}>{x}</th>)}</tr></thead>
          <tbody>{tickerRows.map(([id, t]) => { const c = market.candles[id]; const ch = t.open_24h ? (t.last / t.open_24h - 1) * 100 : 0; return <tr key={id}>
            <td><b>{id}</b></td><td>{num(t.last)}</td><td>{num(t.bid)}</td><td>{num(t.ask)}</td><td className={ch >= 0 ? "positive" : "negative"}>{ch.toFixed(2)}%</td>
            <td>{num(c?.close)}</td><td><Tag className={c?.confirmed ? "status closed" : "status live-status"}>{c?.confirmed ? "CLOSED" : "LIVE"}</Tag></td>
          </tr>; })}</tbody></table></div>
      </Panel>
      <Panel title="Event stream" meta={`${market.events.length} BUFFERED`}>
        <div className="event-console">{[...market.events].reverse().slice(0, 80).map((event, i) =>
          <div key={i}><time>{new Date().toLocaleTimeString()}</time><b>[{text(event.type).toUpperCase()}]</b><span>{text(event.instrument_id)} · seq {text(event.sequence)}</span></div>
        )}</div>
      </Panel>
    </div>
    <div className="api-bottom">
      <Panel title="API Explorer" meta="DOCUMENTATION">
        <div className="api-links">
          <a href="/docs" target="_blank"><BookOpen />Swagger UI</a>
          <a href="/redoc" target="_blank"><Database />ReDoc</a>
          <a href="/openapi.json" target="_blank"><Code2 />OpenAPI JSON</a>
          <a href="/api/v1/market/console" target="_blank"><Server />WebSocket Console</a>
        </div>
      </Panel>
      <Panel title="Payload inspector" meta="LATEST EVENT">
        <pre>{JSON.stringify(latest, null, 2)}</pre>
      </Panel>
    </div>
  </>;
}

export default function App() {
  const [page, setPage] = useState<Page>(() => (location.hash.slice(1) as Page) || "terminal");
  const [data, setData] = useState<TerminalSnapshot>(EMPTY);
  const [selected, setSelected] = useState<Setup>();
  const [error, setError] = useState("");
  const market = useMarketSocket();
  const load = () => getTerminalSnapshot().then((snapshot) => {
    setData(snapshot);
    setSelected((current) => current
      ?? snapshot.setups.find((s) => s.status === "READY")
      ?? snapshot.setups.find((s) => s.entry != null)
      ?? snapshot.setups[0]);
    setError("");
  }).catch((e: Error) => setError(e.message));

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => { location.hash = page; }, [page]);

  return <div className="app">
    <Sidebar page={page} setPage={setPage} />
    <main>
      <Topbar page={page} market={market} />
      {error && <div className="error-banner">Không kết nối được API: {error}</div>}
      <div className="content">
        {page === "terminal" && <TerminalPage data={data} market={market} selected={selected} setSelected={setSelected} />}
        {page === "scanner" && <ScannerPage data={data} selected={selected} setSelected={setSelected} refresh={load} />}
        {page === "signal" && <SignalPage data={data} market={market} selected={selected} setSelected={setSelected} />}
        {page === "portfolio" && <PortfolioPage data={data} market={market} />}
        {page === "api" && <ApiPage market={market} />}
      </div>
    </main>
  </div>;
}
