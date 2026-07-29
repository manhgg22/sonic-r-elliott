import { ArrowUpRight, BookOpen, Code2, Database, Radio, Server } from "lucide-react";
import { Tag } from "antd";
import { Kpi, Panel } from "../../components/ui/Panel";
import { PAGE_META } from "../../shared/constants";
import { displayText, formatUsdPrice } from "../../shared/format";
import type { MarketState } from "../../shared/types";

export function ApiPage({ market }: { market: MarketState }) {
  const streams = market.status.streams ?? {};
  const tickerRows = Object.entries(market.tickers).sort().slice(0, 50);
  const latest = market.events.at(-1) ?? { status: "waiting" };

  return (
    <>
      <div className="page-intro simple">
        <div><p>{PAGE_META.api.description}</p><span><i /> Sequence #{market.sequence}</span></div>
      </div>
      <div className="kpi-grid">
        <Kpi label="Sonic API" value="HEALTHY" tone="positive" note="dịch vụ sẵn sàng" />
        <Kpi label="Tick stream" value={streams.tickers?.connected ? "LIVE" : "DOWN"} tone={streams.tickers?.connected ? "positive" : "negative"} note="OKX realtime" />
        <Kpi label="Candle stream" value={streams.candles?.connected ? "LIVE" : "DOWN"} tone={streams.candles?.connected ? "positive" : "negative"} note="khung M15" />
        <Kpi label="Instruments" value={String(market.status.instruments ?? 0)} note="đang theo dõi" />
        <Kpi label="Clients" value={String(market.status.clients ?? 0)} note="đang kết nối" />
        <Kpi label="Sequence" value={String(market.sequence)} note="event gần nhất" />
      </div>
      <div className="api-grid">
        <Panel title="Trạng thái thị trường" meta={`${tickerRows.length} TICKERS`} icon={<Database />}>
          <div className="table-wrap">
            <table>
              <thead><tr>{["Instrument", "Last", "Bid", "Ask", "24h", "M15", "Xác nhận"].map((heading) => <th key={heading}>{heading}</th>)}</tr></thead>
              <tbody>
                {tickerRows.map(([id, ticker]) => {
                  const candle = market.candles[id];
                  const change = ticker.open_24h
                    ? (ticker.last / ticker.open_24h - 1) * 100
                    : 0;
                  return (
                    <tr key={id}>
                      <td><b>{id}</b></td>
                      <td>{formatUsdPrice(ticker.last)}</td>
                      <td>{formatUsdPrice(ticker.bid)}</td>
                      <td>{formatUsdPrice(ticker.ask)}</td>
                      <td className={change >= 0 ? "positive" : "negative"}>{change.toFixed(2)}%</td>
                      <td>{formatUsdPrice(candle?.close)}</td>
                      <td><Tag className={candle?.confirmed ? "status closed" : "status live-status"}>{candle?.confirmed ? "CLOSED" : "LIVE"}</Tag></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel title="Event stream" meta={`${market.events.length} BUFFERED`} icon={<Radio />}>
          <div className="event-console">
            {[...market.events].reverse().slice(0, 80).map((event, index) => (
              <div key={index}>
                <time>{new Date().toLocaleTimeString("vi-VN")}</time>
                <b>[{displayText(event.type).toUpperCase()}]</b>
                <span>{displayText(event.instrument_id)} · seq {displayText(event.sequence)}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <div className="api-bottom">
        <Panel title="API Explorer" meta="DOCUMENTATION" icon={<BookOpen />}>
          <div className="api-links">
            <a href="/docs" target="_blank" rel="noreferrer"><BookOpen /><span><b>Swagger UI</b><small>Khám phá endpoint</small></span><ArrowUpRight /></a>
            <a href="/redoc" target="_blank" rel="noreferrer"><Database /><span><b>ReDoc</b><small>Tài liệu tham chiếu</small></span><ArrowUpRight /></a>
            <a href="/openapi.json" target="_blank" rel="noreferrer"><Code2 /><span><b>OpenAPI JSON</b><small>Machine readable</small></span><ArrowUpRight /></a>
            <a href="/api/v1/market/console" target="_blank" rel="noreferrer"><Server /><span><b>WS Console</b><small>Luồng WebSocket</small></span><ArrowUpRight /></a>
          </div>
        </Panel>
        <Panel title="Payload inspector" meta="LATEST EVENT" icon={<Code2 />}>
          <pre>{JSON.stringify(latest, null, 2)}</pre>
        </Panel>
      </div>
    </>
  );
}
