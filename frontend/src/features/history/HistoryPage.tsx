import { useEffect, useMemo, useState } from "react";
import { Clock3, History, Search, TrendingUp } from "lucide-react";
import { Input, Segmented, Select, Tag } from "antd";
import { Kpi, Panel } from "../../components/ui/Panel";
import { TablePager } from "../../components/ui/TablePager";
import { PAGE_META } from "../../shared/constants";
import {
  displayText, formatDateTime, formatNumber, sideTone
} from "../../shared/format";
import type { TerminalSnapshot, Trade } from "../../shared/types";

const STATUSES = ["ALL", "OPEN", "PENDING", "CLOSED", "EXPIRED"];

function numeric(value: unknown) {
  const result = Number(value);
  return Number.isFinite(result) ? result : 0;
}

function lifecycleStatus(trade: Trade) {
  if (trade.status === "OPEN" && !trade.filled_at) return "OPEN · LEGACY";
  return displayText(trade.status);
}

export function HistoryPage({ data }: { data: TerminalSnapshot }) {
  const [status, setStatus] = useState("ALL");
  const [side, setSide] = useState("ALL");
  const [resultFilter, setResultFilter] = useState("ALL");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const rows = useMemo(() => data.trades.filter((trade) => {
    const matchStatus = status === "ALL" || trade.status === status;
    const matchSide = side === "ALL" || trade.side === side;
    const matchQuery = displayText(trade.base)
      .toLowerCase()
      .includes(query.trim().toLowerCase());
    const totalR = numeric(trade.total_r);
    const matchResult =
      resultFilter === "ALL" ||
      (resultFilter === "WIN" && trade.status === "CLOSED" && totalR > 0) ||
      (resultFilter === "LOSS" && trade.status === "CLOSED" && totalR < 0) ||
      (resultFilter === "FLAT" && trade.status === "CLOSED" && totalR === 0);
    return matchStatus && matchSide && matchQuery && matchResult;
  }).sort((left, right) => numeric(right.id) - numeric(left.id)),
  [data.trades, query, resultFilter, side, status]);
  const pageRows = rows.slice((page - 1) * pageSize, page * pageSize);

  useEffect(
    () => setPage(1),
    [query, resultFilter, side, status]
  );
  useEffect(() => {
    const lastPage = Math.max(1, Math.ceil(rows.length / pageSize));
    if (page > lastPage) setPage(lastPage);
  }, [page, pageSize, rows.length]);

  const closed = data.trades.filter((trade) => trade.status === "CLOSED");
  const expired = data.trades.filter((trade) => trade.status === "EXPIRED");
  const filled = data.trades.filter((trade) => trade.filled_at);
  const result = closed.reduce((sum, trade) => sum + numeric(trade.total_r), 0);
  const average = closed.length ? result / closed.length : 0;
  const grossProfit = closed.reduce(
    (sum, trade) => sum + Math.max(0, numeric(trade.total_r)), 0
  );
  const grossLoss = Math.abs(closed.reduce(
    (sum, trade) => sum + Math.min(0, numeric(trade.total_r)), 0
  ));
  const profitFactor = grossLoss ? grossProfit / grossLoss : 0;

  return (
    <>
      <div className="page-intro simple">
        <div>
          <p>{PAGE_META.history.description}</p>
          <span><i /> Múi giờ hiển thị: ICT (UTC+7)</span>
        </div>
      </div>
      <div className="kpi-grid history-kpis">
        <Kpi label="Tổng setup" value={String(data.trades.length)} note="toàn bộ database" />
        <Kpi label="Đã khớp" value={String(filled.length)} note="có thời điểm fill" />
        <Kpi label="Đã đóng" value={String(closed.length)} note="có kết quả cuối" />
        <Kpi label="Hết hạn" value={String(expired.length)} note="không chạm trigger" />
        <Kpi label="R trung bình" value={`${average >= 0 ? "+" : ""}${average.toFixed(2)}R`}
          tone={average >= 0 ? "positive" : "negative"} note="trên lệnh đã đóng" />
        <Kpi label="Profit factor" value={profitFactor.toFixed(2)}
          tone={profitFactor >= 1 ? "positive" : "negative"} note={`${result >= 0 ? "+" : ""}${result.toFixed(2)}R tổng`} />
      </div>
      <div className="history-layout">
        <Panel title="Sổ lệnh paper" meta={`${rows.length} BẢN GHI`} icon={<History />}>
          <div className="toolbar history-toolbar">
            <Select className="filter-select" value={status} onChange={setStatus}
              options={STATUSES.map((value) => ({
                value,
                label: value === "ALL" ? "Mọi trạng thái" : value
              }))} />
            <Segmented value={side} options={["ALL", "LONG", "SHORT"]}
              onChange={(value) => setSide(String(value))} />
            <Select className="filter-select result-filter" value={resultFilter}
              onChange={setResultFilter}
              options={[
                { value: "ALL", label: "Mọi kết quả" },
                { value: "WIN", label: "Lệnh thắng" },
                { value: "LOSS", label: "Lệnh thua" },
                { value: "FLAT", label: "Hòa vốn" }
              ]} />
            <Input className="scanner-search" prefix={<Search />} value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm mã..." allowClear />
          </div>
          <div className="table-wrap history-table desktop-table">
            <table>
              <thead>
                <tr>
                  {[
                    "ID", "Mã", "Side", "Trạng thái", "Armed", "Filled",
                    "Closed", "Entry", "Exit", "Initial SL", "Lý do",
                    "Kết quả", "MFE", "MAE"
                  ].map((heading) => <th key={heading}>{heading}</th>)}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((trade) => {
                  const totalR = numeric(trade.total_r);
                  return (
                    <tr key={displayText(trade.id)}>
                      <td>#{displayText(trade.id)}</td>
                      <td><b>{displayText(trade.base)}</b></td>
                      <td className={sideTone(trade.side)}>{displayText(trade.side)}</td>
                      <td>
                        <Tag className={`status ${displayText(trade.status).toLowerCase()}`}>
                          {lifecycleStatus(trade)}
                        </Tag>
                      </td>
                      <td>{formatDateTime(trade.opened_at)}</td>
                      <td>{formatDateTime(trade.filled_at)}</td>
                      <td>{formatDateTime(trade.closed_at)}</td>
                      <td>{formatNumber(trade.entry)}</td>
                      <td>{formatNumber(trade.exit_price)}</td>
                      <td>{formatNumber(trade.initial_sl)}</td>
                      <td>{displayText(trade.exit_reason)}</td>
                      <td className={totalR >= 0 ? "positive" : "negative"}>
                        {trade.total_r == null
                          ? "—"
                          : `${totalR >= 0 ? "+" : ""}${totalR.toFixed(2)}R`}
                      </td>
                      <td>{numeric(trade.mfe_r).toFixed(2)}R</td>
                      <td>{numeric(trade.mae_r).toFixed(2)}R</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mobile-list">
            {pageRows.map((trade) => {
              const totalR = numeric(trade.total_r);
              return (
                <article className="mobile-data-card" key={displayText(trade.id)}>
                  <header>
                    <span>
                      <b>{displayText(trade.base)}</b>
                      <small>#{displayText(trade.id)}</small>
                    </span>
                    <i className={sideTone(trade.side)}>{displayText(trade.side)}</i>
                    <Tag className={`status ${displayText(trade.status).toLowerCase()}`}>
                      {lifecycleStatus(trade)}
                    </Tag>
                  </header>
                  <div className="mobile-metrics">
                    <span>Entry<b>{formatNumber(trade.entry)}</b></span>
                    <span>Exit<b>{formatNumber(trade.exit_price)}</b></span>
                    <span>Kết quả<b className={totalR >= 0 ? "positive" : "negative"}>
                      {trade.total_r == null ? "—" : `${totalR >= 0 ? "+" : ""}${totalR.toFixed(2)}R`}
                    </b></span>
                  </div>
                  <div className="mobile-timeline">
                    <span>Armed <b>{formatDateTime(trade.opened_at)}</b></span>
                    <span>Filled <b>{formatDateTime(trade.filled_at)}</b></span>
                    <span>Closed <b>{formatDateTime(trade.closed_at)}</b></span>
                  </div>
                  <footer>{displayText(trade.exit_reason)}</footer>
                </article>
              );
            })}
          </div>
          <TablePager page={page} pageSize={pageSize} total={rows.length}
            onChange={(nextPage, nextSize) => {
              setPageSize(nextSize);
              setPage(nextSize !== pageSize ? 1 : nextPage);
            }} />
          {!rows.length && (
            <div className="empty">
              <Search />Không có bản ghi phù hợp bộ lọc
            </div>
          )}
        </Panel>
        <Panel title="Lifecycle gần nhất" meta="500 EVENTS" icon={<Clock3 />}>
          <div className="history-events">
            {data.events.slice(0, 30).map((event) => (
              <div className="history-event" key={displayText(event.id)}>
                <span className={`event-dot ${displayText(event.event).toLowerCase()}`} />
                <div>
                  <b>
                    {displayText(event.base)} · <i className={sideTone(event.side)}>
                      {displayText(event.side)}
                    </i>
                  </b>
                  <small>{displayText(event.event)} · {formatDateTime(event.event_at)}</small>
                </div>
                <strong className={numeric(event.delta_r) >= 0 ? "positive" : "negative"}>
                  {formatNumber(event.price)}
                  <small>{numeric(event.delta_r) >= 0 ? "+" : ""}{numeric(event.delta_r).toFixed(2)}R</small>
                </strong>
              </div>
            ))}
            {!data.events.length && (
              <div className="empty"><TrendingUp />Chưa có lifecycle event</div>
            )}
          </div>
        </Panel>
      </div>
    </>
  );
}
