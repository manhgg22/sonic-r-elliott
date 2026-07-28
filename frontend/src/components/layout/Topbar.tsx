import { Activity, Bell, Clock3, Menu, Radio } from "lucide-react";
import { PAGE_META, type Page } from "../../shared/constants";
import type { MarketState } from "../../shared/types";

export function Topbar({ page, market, onMenu }: {
  page: Page;
  market: MarketState;
  onMenu: () => void;
}) {
  const streams = market.status.streams ?? {};
  const tick = streams.tickers?.connected;
  const candle = streams.candles?.connected;
  const age = market.status.message_age_seconds;
  const now = new Date();
  const next = new Date(now);
  next.setMinutes(Math.floor(now.getMinutes() / 15) * 15 + 15, 5, 0);
  const seconds = Math.max(0, Math.floor((+next - +now) / 1000));

  return (
    <header className="topbar">
      <div className="topbar-title">
        <button className="mobile-menu" onClick={onMenu} aria-label="Mở menu"><Menu /></button>
        <span>{PAGE_META[page].eyebrow}</span>
        <b>{PAGE_META[page].title}</b>
      </div>
      <div className="health-strip">
        <small className={market.connected ? "health-pill live" : "health-pill down"}>
          <i className={market.connected ? "dot live" : "dot down"} />
          {market.connected ? "Realtime" : "Mất kết nối"}
        </small>
        <small className="health-detail"><Radio /> Ticker <b>{tick ? "Live" : "Down"}</b></small>
        <small className="health-detail"><Activity /> Candle <b>{candle ? "Live" : "Down"}</b></small>
        <small className="health-detail"><Clock3 /> Độ trễ <b>{age == null ? "—" : `${Number(age).toFixed(2)}s`}</b></small>
        <small className="countdown">
          M15 <b>{String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}</b>
        </small>
        <button className="icon-button" aria-label="Thông báo"><Bell /></button>
      </div>
    </header>
  );
}
