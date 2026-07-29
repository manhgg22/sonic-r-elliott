import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, CircleDollarSign, History, ShieldCheck } from "lucide-react";
import { message, Progress, Switch } from "antd";
import { Kpi, Panel } from "../../components/ui/Panel";
import { TablePager } from "../../components/ui/TablePager";
import { setPortfolioRiskGuard } from "../../services/api";
import { PAGE_META } from "../../shared/constants";
import {
  displayText, formatUsd, formatUsdPrice, sideTone
} from "../../shared/format";
import type { MarketState, TerminalSnapshot, Trade } from "../../shared/types";

function liveR(trade: Trade, market: MarketState) {
  const ticker = market.tickers[`${displayText(trade.base)}-USDT-SWAP`];
  if (!ticker) return Number(trade.realized_r ?? 0);
  const direction = trade.side === "LONG" ? 1 : -1;
  return Number(trade.realized_r ?? 0) + Number(trade.remaining ?? 0) *
    (ticker.last - Number(trade.entry)) * direction / Number(trade.risk);
}

function livePnlUsd(trade: Trade, market: MarketState) {
  return liveR(trade, market) * Number(trade.risk_amount_usd ?? 0);
}

function unrealizedPnlUsd(trade: Trade, market: MarketState) {
  return (
    liveR(trade, market) - Number(trade.realized_r ?? 0)
  ) * Number(trade.risk_amount_usd ?? 0);
}

export function PortfolioPage({ data, market, refresh }: {
  data: TerminalSnapshot;
  market: MarketState;
  refresh: () => Promise<void>;
}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [changingGuard, setChangingGuard] = useState(false);
  const open = data.trades.filter((trade) => trade.status === "OPEN");
  const pending = data.trades.filter((trade) => trade.status === "PENDING");
  const active = [...pending, ...open];
  const pageRows = active.slice((page - 1) * pageSize, page * pageSize);
  const closed = data.trades.filter((trade) => trade.status === "CLOSED");
  const realized = data.trades.reduce(
    (sum, trade) => sum + Number(trade.realized_pnl_usd ?? 0), 0
  );
  const unrealized = open.reduce(
    (sum, trade) => sum + unrealizedPnlUsd(trade, market), 0
  );
  const currentEquity = data.risk.paper_equity_usd + realized + unrealized;
  const closedPnl = closed.slice(-30).map(
    (trade) => Number(trade.total_pnl_usd ?? 0)
  );
  const chartMax = Math.max(1, ...closedPnl.map(Math.abs));
  const riskBreached =
    data.risk.committed_risk_pct > data.risk.max_portfolio_risk_pct;

  const changeRiskGuard = async (enabled: boolean) => {
    setChangingGuard(true);
    try {
      await setPortfolioRiskGuard(enabled);
      await refresh();
      message.success(
        enabled
          ? "Đã bật giới hạn rủi ro danh mục 2%."
          : "Đã tắt giới hạn 2% cho paper test."
      );
    } catch (changeError) {
      message.error(
        changeError instanceof Error
          ? changeError.message
          : "Không thể cập nhật giới hạn rủi ro."
      );
    } finally {
      setChangingGuard(false);
    }
  };

  useEffect(() => {
    const lastPage = Math.max(1, Math.ceil(active.length / pageSize));
    if (page > lastPage) setPage(lastPage);
  }, [active.length, page, pageSize]);

  return (
    <>
      <div className="page-intro simple">
        <div><p>{PAGE_META.portfolio.description}</p><span><i /> Paper execution only</span></div>
      </div>
      <div className="kpi-grid">
        <Kpi label="Vị thế mở" value={String(open.length)} note="đang hoạt động" />
        <Kpi label="Lệnh chờ" value={String(pending.length)} note={`hết hạn sau ${data.risk.pending_expiry_bars} nến`} />
        <Kpi label="Lãi/lỗ đã chốt" value={formatUsd(realized, true)} tone={realized >= 0 ? "positive" : "negative"} note="USD đã ghi nhận" />
        <Kpi label="Lãi/lỗ tạm tính" value={formatUsd(unrealized, true)} tone={unrealized >= 0 ? "positive" : "negative"} note="USD theo giá live" />
        <Kpi label="Vốn tạm tính" value={formatUsd(currentEquity)} tone={currentEquity >= data.risk.paper_equity_usd ? "positive" : "negative"} note={`vốn gốc ${formatUsd(data.risk.paper_equity_usd)}`} />
        <Kpi label="Risk / lệnh" value={formatUsd(data.risk.risk_per_trade_usd)} note={`${data.risk.risk_per_trade_pct.toFixed(2)}% vốn paper`} />
      </div>
      <div className="portfolio-grid">
        <Panel title="Lệnh đang hoạt động" meta="OPEN + PENDING" icon={<CircleDollarSign />}>
          <div className="table-wrap desktop-table">
            <table>
              <thead><tr>{["Mã", "Side", "Trạng thái", "Entry", "Live", "SL", "TP1", "TP2", "Giá trị vị thế", "Risk USD", "Còn lại", "P&L live"].map((heading) => <th key={heading}>{heading}</th>)}</tr></thead>
              <tbody>
                {pageRows.map((trade) => {
                  const isOpen = trade.status === "OPEN";
                  const valueUsd = isOpen ? livePnlUsd(trade, market) : 0;
                  return (
                    <tr key={displayText(trade.id)}>
                      <td><b>{displayText(trade.base)}</b></td>
                      <td className={sideTone(trade.side)}>{displayText(trade.side)}</td>
                      <td>{displayText(trade.status)}</td>
                      <td>{formatUsdPrice(trade.entry)}</td>
                      <td>{isOpen ? formatUsdPrice(market.tickers[`${displayText(trade.base)}-USDT-SWAP`]?.last) : "—"}</td>
                      <td>{formatUsdPrice(trade.current_sl)}</td>
                      <td>{formatUsdPrice(trade.tp1)}</td>
                      <td>{formatUsdPrice(trade.tp2)}</td>
                      <td>{formatUsd(trade.entry_notional_usd)}</td>
                      <td>{formatUsd(trade.risk_amount_usd)}</td>
                      <td>{(Number(trade.remaining) * 100).toFixed(0)}%</td>
                      <td className={isOpen ? (valueUsd >= 0 ? "positive" : "negative") : "muted"}>
                        {isOpen ? formatUsd(valueUsd, true) : "CHỜ KHỚP"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mobile-list">
            {pageRows.map((trade) => {
              const isOpen = trade.status === "OPEN";
              const valueUsd = isOpen ? livePnlUsd(trade, market) : 0;
              return (
                <article className="mobile-data-card" key={displayText(trade.id)}>
                  <header>
                    <span>
                      <b>{displayText(trade.base)}</b>
                      <small>{displayText(trade.status)}</small>
                    </span>
                    <i className={sideTone(trade.side)}>{displayText(trade.side)}</i>
                  </header>
                  <div className="mobile-metrics">
                    <span>Entry<b>{formatUsdPrice(trade.entry)}</b></span>
                    <span>Live<b>{isOpen
                      ? formatUsdPrice(market.tickers[`${displayText(trade.base)}-USDT-SWAP`]?.last)
                      : "CHỜ KHỚP"}</b></span>
                    <span>Current SL<b className="negative">{formatUsdPrice(trade.current_sl)}</b></span>
                    <span>Giá trị vị thế<b>{formatUsd(trade.entry_notional_usd)}</b></span>
                    <span>Risk<b className="negative">{formatUsd(trade.risk_amount_usd)}</b></span>
                    <span>P&amp;L live<b className={valueUsd >= 0 ? "positive" : "negative"}>
                      {isOpen ? formatUsd(valueUsd, true) : "—"}
                    </b></span>
                  </div>
                  <footer>TP1 {formatUsdPrice(trade.tp1)} · TP2 {formatUsdPrice(trade.tp2)}</footer>
                </article>
              );
            })}
          </div>
          <TablePager page={page} pageSize={pageSize} total={active.length}
            onChange={(nextPage, nextSize) => {
              setPageSize(nextSize);
              setPage(nextSize !== pageSize ? 1 : nextPage);
            }} />
          {!active.length && <div className="empty table-empty"><ShieldCheck />Chưa có lệnh đang hoạt động</div>}
        </Panel>
        <Panel title="Quản trị rủi ro" meta="RISK PANEL" icon={<ShieldCheck />}>
          <div className="risk-guard-toggle">
            <span>
              <b>Giới hạn danh mục 2%</b>
              <small>
                {data.risk.risk_guard_enabled
                  ? "Đang bảo vệ paper portfolio"
                  : "Paper test · không áp dụng trần 2%"}
              </small>
            </span>
            <Switch
              checked={data.risk.risk_guard_enabled}
              loading={changingGuard}
              onChange={changeRiskGuard}
              aria-label="Bật hoặc tắt giới hạn rủi ro danh mục 2%"
            />
          </div>
          <div className="risk-total"><span>Risk đang cam kết</span><strong className={riskBreached ? "negative" : ""}>{formatUsd(data.risk.committed_risk_usd)}</strong></div>
          <Progress className="risk-progress" percent={Math.min(
              data.risk.committed_risk_pct / data.risk.max_portfolio_risk_pct * 100,
              100
            )}
            strokeColor={riskBreached ? "#ff7185" : "#f5b942"}
            trailColor="#202a42" showInfo={false} size="small" />
          <div className="risk-scale"><span>An toàn</span><span>Cảnh báo</span><span>Giới hạn</span></div>
          <div className="alert warning-box"><Activity /><span><b>Rủi ro tương quan</b>Kiểm tra các vị thế cùng chiều trước khi mở mới.</span></div>
          <div className={`alert ${!data.risk.risk_guard_enabled || riskBreached ? "danger-box" : "ok-box"}`}><ShieldCheck /><span>
            <b>{!data.risk.risk_guard_enabled
              ? "Chế độ paper test"
              : riskBreached ? "Đã vượt trần risk" : "Guardrail hoạt động"}</b>
            {!data.risk.risk_guard_enabled
              ? `Trần ${formatUsd(data.risk.max_portfolio_risk_usd)} đang tắt. Không gửi lệnh thật; mỗi lệnh vẫn risk ${formatUsd(data.risk.risk_per_trade_usd)} và giới hạn tuần vẫn áp dụng.`
              : riskBreached
              ? `Các vị thế lịch sử đang vượt ${formatUsd(data.risk.max_portfolio_risk_usd)}. Engine đã chặn lệnh mới; không tự động đóng dữ liệu cũ.`
              : `Vốn paper ${formatUsd(data.risk.paper_equity_usd)} · ${formatUsd(data.risk.risk_per_trade_usd)} mỗi lệnh · tối đa ${formatUsd(data.risk.max_portfolio_risk_usd)} danh mục.`}
          </span></div>
        </Panel>
      </div>
      <div className="bottom-grid">
        <Panel title="Lãi/lỗ theo USD" meta={`${closed.length} CLOSED TRADES`} icon={<ArrowUpRight />}>
          <div className="equity-chart">
            <div className="chart-y"><span>{formatUsd(chartMax)}</span><span>{formatUsd(chartMax * 0.66)}</span><span>{formatUsd(chartMax * 0.33)}</span><span>$0</span></div>
            <div className="equity-bars">
              {closedPnl.map((pnl, index) => (
                <i key={index} className={pnl >= 0 ? "win" : "loss"}
                  title={formatUsd(pnl, true)}
                  style={{ height: `${Math.min(95, 18 + Math.abs(pnl) / chartMax * 77)}%` }} />
              ))}
              {!closed.length && <div className="equity-empty">Dữ liệu hiệu suất sẽ xuất hiện sau khi đóng lệnh.</div>}
            </div>
          </div>
        </Panel>
        <Panel title="Lifecycle events" meta="PAPER ENGINE" icon={<History />}>
          {data.events.slice(0, 7).map((event, index) => (
            <div className="mini-row timeline-row" key={index}>
              <span>{displayText(event.event_at)}</span>
              <b>{displayText(event.event)} · {formatUsd(event.delta_usd, true)}</b>
            </div>
          ))}
          {!data.events.length && <div className="empty">Đang chờ sự kiện từ paper engine</div>}
        </Panel>
      </div>
    </>
  );
}
