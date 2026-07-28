import {
  Activity, BarChart3, CircleDollarSign, Gauge, History,
  ScanLine, ShieldCheck, SlidersHorizontal
} from "lucide-react";
import { Tag } from "antd";
import { MarketChart } from "../../components/trading/MarketChart";
import { GateList, SetupPicker } from "../../components/trading/SignalControls";
import { Level, Panel } from "../../components/ui/Panel";
import { PAGE_META } from "../../shared/constants";
import { displayText, formatNumber, sideTone } from "../../shared/format";
import type { MarketState, Setup, TerminalSnapshot } from "../../shared/types";

function Watchlist({ market }: { market: MarketState }) {
  const priority = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"];

  return (
    <div className="watchlist">
      {priority.map((id) => {
        const ticker = market.tickers[id];
        const change = ticker?.open_24h
          ? (ticker.last / ticker.open_24h - 1) * 100
          : 0;
        return (
          <div className="watch-row" key={id}>
            <div className="asset-name">
              <i>{id.slice(0, 1)}</i>
              <span>{id.split("-")[0]}<small>USDT PERP</small></span>
            </div>
            <b>
              {formatNumber(ticker?.last)}
              <small className={change >= 0 ? "positive" : "negative"}>
                {change >= 0 ? "+" : ""}{change.toFixed(2)}%
              </small>
            </b>
          </div>
        );
      })}
    </div>
  );
}

function MarketSummary({ data, market }: {
  data: TerminalSnapshot;
  market: MarketState;
}) {
  const ready = data.setups.filter((setup) => setup.status === "READY").length;
  const open = data.trades.filter((trade) => trade.status === "OPEN").length;
  const pending = data.trades.filter((trade) => trade.status === "PENDING").length;

  return (
    <div className="market-summary">
      <div>
        <span className="summary-icon cyan"><ScanLine /></span>
        <p><small>Tín hiệu sẵn sàng</small><b>{ready.toString().padStart(2, "0")}</b></p>
        <em>7-gate confirmed</em>
      </div>
      <div>
        <span className="summary-icon violet"><Gauge /></span>
        <p><small>Mã đang theo dõi</small><b>{market.status.instruments ?? Object.keys(market.tickers).length}</b></p>
        <em>OKX perpetual</em>
      </div>
      <div>
        <span className="summary-icon green"><CircleDollarSign /></span>
        <p><small>Open / Pending</small><b>{open.toString().padStart(2, "0")} / {pending}</b></p>
        <em>Risk {data.risk.risk_per_trade_pct.toFixed(2)}% / lệnh</em>
      </div>
    </div>
  );
}

export function TerminalPage({ data, market, selected, setSelected }: {
  data: TerminalSnapshot;
  market: MarketState;
  selected?: Setup;
  setSelected: (setup: Setup) => void;
}) {
  const ready = data.setups.filter((setup) => setup.status === "READY");
  const active = data.trades.filter(
    (trade) => trade.status === "OPEN" || trade.status === "PENDING"
  );
  const base = selected?.base && selected.base !== "—"
    ? displayText(selected.base)
    : "BTC";
  const instrument = `${base}-USDT-SWAP`;

  return (
    <>
      <div className="page-intro">
        <div>
          <p>{PAGE_META.terminal.description}</p>
          <span><i /> Dữ liệu trực tiếp từ OKX</span>
        </div>
        <MarketSummary data={data} market={market} />
      </div>
      <div className="terminal-grid">
        <div className="stack">
          <Panel title="Danh sách theo dõi" meta={`${Object.keys(market.tickers).length} MÃ`} icon={<History />}>
            <Watchlist market={market} />
          </Panel>
          <Panel title="Bộ lọc 7-gate" meta={`${ready.length} SẴN SÀNG`} icon={<SlidersHorizontal />}>
            <SetupPicker setups={data.setups} selected={selected} onSelect={setSelected} />
            <GateList setup={selected} />
          </Panel>
        </div>
        <Panel title="Biểu đồ phân tích" meta="M15 · EMA34 · EMA89" icon={<BarChart3 />} className="chart-panel">
          <MarketChart instrumentId={instrument} live={market.candles[instrument]} setup={selected} />
        </Panel>
        <div className="stack">
          <Panel title="Thiết lập giao dịch" meta="NẾN ĐÓNG" icon={<Gauge />}>
            <div className="setup-hero">
              <div><small>{base}/USDT</small><b className={sideTone(selected?.side)}>{displayText(selected?.side)}</b></div>
              <Tag className={`status ${displayText(selected?.status).toLowerCase()}`}>{displayText(selected?.status)}</Tag>
            </div>
            <Level label="Vùng vào lệnh" value={selected?.entry} tone="live-text" />
            <Level label="Dừng lỗ" value={selected?.sl} tone="negative" />
            <Level label="Chốt lời 1" value={selected?.tp1} tone="positive" />
            <Level label="Chốt lời 2" value={selected?.tp2} tone="positive" />
            <Level label="Tỷ lệ R:R" value={selected?.tp2_rr} />
            <Level label="PVSRA volume" value={selected?.pva_ratio} tone={selected?.pva_climax ? "warning" : ""} />
          </Panel>
          <Panel title="Lệnh đang hoạt động" meta={`${active.length} OPEN / PENDING`} icon={<CircleDollarSign />}>
            {active.slice(0, 4).map((trade) => (
              <div className="mini-row" key={displayText(trade.id)}>
                <span>
                  {displayText(trade.base)} · <i className={sideTone(trade.side)}>{displayText(trade.side)}</i>
                  {" · "}{displayText(trade.status)}
                </span>
                <b>{formatNumber(trade.entry)}</b>
              </div>
            ))}
            {!active.length && <div className="empty"><ShieldCheck />Chưa có lệnh paper hoạt động</div>}
          </Panel>
          <Panel title="Hoạt động gần đây" meta="EVENTS" icon={<Activity />}>
            {data.events.slice(0, 4).map((event, index) => (
              <div className="mini-row" key={index}>
                <span>{displayText(event.event)}</span><b>{formatNumber(event.price)}</b>
              </div>
            ))}
            {!data.events.length && <div className="empty compact">Đang chờ sự kiện mới</div>}
          </Panel>
        </div>
      </div>
    </>
  );
}
