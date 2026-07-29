import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, CircleDollarSign, History, ShieldCheck } from "lucide-react";
import { message, Progress, Switch } from "antd";
import { Kpi, Panel } from "../../components/ui/Panel";
import { TablePager } from "../../components/ui/TablePager";
import { setPortfolioRiskGuard } from "../../services/api";
import { PAGE_META } from "../../shared/constants";
import { displayText, formatNumber, sideTone } from "../../shared/format";
import type { MarketState, TerminalSnapshot, Trade } from "../../shared/types";

function liveR(trade: Trade, market: MarketState) {
  const ticker = market.tickers[`${displayText(trade.base)}-USDT-SWAP`];
  if (!ticker) return Number(trade.realized_r ?? 0);
  const direction = trade.side === "LONG" ? 1 : -1;
  return Number(trade.realized_r ?? 0) + Number(trade.remaining ?? 0) *
    (ticker.last - Number(trade.entry)) * direction / Number(trade.risk);
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
  const realized = closed.reduce((sum, trade) => sum + Number(trade.total_r ?? 0), 0);
  const unrealized = open.reduce((sum, trade) => sum + liveR(trade, market), 0);
  const wins = closed.filter((trade) => Number(trade.total_r ?? 0) > 0).length;
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
        <Kpi label="Realized R" value={`${realized >= 0 ? "+" : ""}${realized.toFixed(2)}R`} tone={realized >= 0 ? "positive" : "negative"} note="đã ghi nhận" />
        <Kpi label="Unrealized R" value={`${unrealized >= 0 ? "+" : ""}${unrealized.toFixed(2)}R`} tone={unrealized >= 0 ? "positive" : "negative"} note="theo giá live" />
        <Kpi label="Win rate" value={`${closed.length ? (wins / closed.length * 100).toFixed(1) : "0.0"}%`} note={`${closed.length} lệnh đã đóng`} />
        <Kpi label="Risk / lệnh" value={`${data.risk.risk_per_trade_pct.toFixed(2)}%`} note="guardrail từ engine" />
      </div>
      <div className="portfolio-grid">
        <Panel title="Lệnh đang hoạt động" meta="OPEN + PENDING" icon={<CircleDollarSign />}>
          <div className="table-wrap desktop-table">
            <table>
              <thead><tr>{["Mã", "Side", "Trạng thái", "Entry", "Live", "SL", "TP1", "TP2", "Còn lại", "Live R"].map((heading) => <th key={heading}>{heading}</th>)}</tr></thead>
              <tbody>
                {pageRows.map((trade) => {
                  const isOpen = trade.status === "OPEN";
                  const valueR = isOpen ? liveR(trade, market) : 0;
                  return (
                    <tr key={displayText(trade.id)}>
                      <td><b>{displayText(trade.base)}</b></td>
                      <td className={sideTone(trade.side)}>{displayText(trade.side)}</td>
                      <td>{displayText(trade.status)}</td>
                      <td>{formatNumber(trade.entry)}</td>
                      <td>{isOpen ? formatNumber(market.tickers[`${displayText(trade.base)}-USDT-SWAP`]?.last) : "—"}</td>
                      <td>{formatNumber(trade.current_sl)}</td>
                      <td>{formatNumber(trade.tp1)}</td>
                      <td>{formatNumber(trade.tp2)}</td>
                      <td>{(Number(trade.remaining) * 100).toFixed(0)}%</td>
                      <td className={isOpen ? (valueR >= 0 ? "positive" : "negative") : "muted"}>
                        {isOpen ? `${valueR >= 0 ? "+" : ""}${valueR.toFixed(2)}R` : "CHỜ KHỚP"}
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
              const valueR = isOpen ? liveR(trade, market) : 0;
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
                    <span>Entry<b>{formatNumber(trade.entry)}</b></span>
                    <span>Live<b>{isOpen
                      ? formatNumber(market.tickers[`${displayText(trade.base)}-USDT-SWAP`]?.last)
                      : "CHỜ KHỚP"}</b></span>
                    <span>Current SL<b className="negative">{formatNumber(trade.current_sl)}</b></span>
                    <span>Live R<b className={valueR >= 0 ? "positive" : "negative"}>
                      {isOpen ? `${valueR >= 0 ? "+" : ""}${valueR.toFixed(2)}R` : "—"}
                    </b></span>
                  </div>
                  <footer>TP1 {formatNumber(trade.tp1)} · TP2 {formatNumber(trade.tp2)}</footer>
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
          <div className="risk-total"><span>Risk đang cam kết</span><strong className={riskBreached ? "negative" : ""}>{data.risk.committed_risk_pct.toFixed(2)}%</strong></div>
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
              ? `Trần ${data.risk.max_portfolio_risk_pct.toFixed(2)}% đang tắt. Không gửi lệnh thật; mỗi lệnh vẫn ${data.risk.risk_per_trade_pct.toFixed(2)}% và giới hạn tuần vẫn áp dụng.`
              : riskBreached
              ? `Các vị thế lịch sử đang vượt ${data.risk.max_portfolio_risk_pct.toFixed(2)}%. Engine đã chặn lệnh mới; không tự động đóng dữ liệu cũ.`
              : `Paper-only · ${data.risk.risk_per_trade_pct.toFixed(2)}% mỗi lệnh · tối đa ${data.risk.max_portfolio_risk_pct.toFixed(2)}% danh mục.`}
          </span></div>
        </Panel>
      </div>
      <div className="bottom-grid">
        <Panel title="Hiệu suất theo R" meta={`${closed.length} CLOSED TRADES`} icon={<ArrowUpRight />}>
          <div className="equity-chart">
            <div className="chart-y"><span>+3R</span><span>+2R</span><span>+1R</span><span>0R</span></div>
            <div className="equity-bars">
              {closed.slice(-30).map((trade, index) => (
                <i key={index} className={Number(trade.total_r) >= 0 ? "win" : "loss"}
                  style={{ height: `${Math.min(95, 18 + Math.abs(Number(trade.total_r)) * 35)}%` }} />
              ))}
              {!closed.length && <div className="equity-empty">Dữ liệu hiệu suất sẽ xuất hiện sau khi đóng lệnh.</div>}
            </div>
          </div>
        </Panel>
        <Panel title="Lifecycle events" meta="PAPER ENGINE" icon={<History />}>
          {data.events.slice(0, 7).map((event, index) => (
            <div className="mini-row timeline-row" key={index}>
              <span>{displayText(event.event_at)}</span>
              <b>{displayText(event.event)} · {formatNumber(event.price)}</b>
            </div>
          ))}
          {!data.events.length && <div className="empty">Đang chờ sự kiện từ paper engine</div>}
        </Panel>
      </div>
    </>
  );
}
