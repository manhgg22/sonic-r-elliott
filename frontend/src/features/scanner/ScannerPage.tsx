import { useEffect, useMemo, useState } from "react";
import { Bell, ChevronRight, Gauge, RefreshCw, ScanLine, Search } from "lucide-react";
import { Button, Input, message, Segmented, Select, Tag } from "antd";
import { GateList } from "../../components/trading/SignalControls";
import { Level, Panel } from "../../components/ui/Panel";
import { TablePager } from "../../components/ui/TablePager";
import { runScanner } from "../../services/api";
import { PAGE_META, SIGNAL_GATES } from "../../shared/constants";
import {
  displayText, formatNumber, isTruthyFlag, sideTone
} from "../../shared/format";
import type { Setup, TerminalSnapshot } from "../../shared/types";

export function ScannerPage({ data, selected, setSelected, refresh }: {
  data: TerminalSnapshot;
  selected?: Setup;
  setSelected: (setup: Setup) => void;
  refresh: () => void;
}) {
  const [query, setQuery] = useState("");
  const [side, setSide] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [running, setRunning] = useState(false);
  const rows = useMemo(() => data.setups.filter((setup) => {
    const setupStatus = displayText(setup.status);
    const matchStatus =
      status === "ALL" ||
      setupStatus === status ||
      (status === "WAITING" && setupStatus.startsWith("WAIT_"));
    return matchStatus &&
      (side === "ALL" || setup.side === side) &&
      displayText(setup.base).toLowerCase().includes(query.toLowerCase());
  }).sort((left, right) => {
    const priority: Record<string, number> = {
      READY: 0, WAIT_PA: 1, WAIT_PULLBACK: 2, NO_SETUP: 3, ERROR: 4
    };
    return (priority[displayText(left.status)] ?? 9) -
      (priority[displayText(right.status)] ?? 9) ||
      Number(left.rank ?? 9999) - Number(right.rank ?? 9999);
  }), [data.setups, query, side, status]);
  const pageRows = rows.slice((page - 1) * pageSize, page * pageSize);
  const last = data.runs[0];

  useEffect(() => setPage(1), [query, side, status]);
  useEffect(() => {
    const lastPage = Math.max(1, Math.ceil(rows.length / pageSize));
    if (page > lastPage) setPage(lastPage);
  }, [page, pageSize, rows.length]);

  const scan = async () => {
    setRunning(true);
    try {
      await runScanner();
      refresh();
      message.success("Đã cập nhật kết quả quét");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <div className="page-intro simple">
        <div><p>{PAGE_META.scanner.description}</p><span><i /> {rows.length} kết quả phù hợp</span></div>
      </div>
      <div className="scanner-layout">
        <Panel title="Kết quả quét" meta="CONFIRMED CANDLES ONLY" icon={<ScanLine />}>
          <div className="toolbar scanner-toolbar">
            <Segmented value={side} options={["ALL", "LONG", "SHORT"]} onChange={(value) => setSide(String(value))} />
            <Select className="filter-select" value={status} onChange={setStatus}
              options={[
                { value: "ALL", label: "Mọi trạng thái" },
                { value: "READY", label: "Sẵn sàng" },
                { value: "WAITING", label: "Đang chờ" },
                { value: "NO_SETUP", label: "Chưa có setup" },
                { value: "ERROR", label: "Lỗi dữ liệu" }
              ]} />
            <Input className="scanner-search" prefix={<Search />} value={query}
              onChange={(event) => setQuery(event.target.value)} placeholder="Tìm mã..." allowClear />
            <Button className="action" loading={running} icon={<RefreshCw />} onClick={scan}>QUÉT TOÀN BỘ</Button>
          </div>
          <div className="table-wrap desktop-table">
            <table>
              <thead><tr>
                {["Mã", "Side", "Trạng thái", "Close", "Entry", "SL", "TP1", "TP2", "R:R", "Dragon", "Regime", "Session", "Break", "Dow", "Zone", "PA"].map((heading) => <th key={heading}>{heading}</th>)}
              </tr></thead>
              <tbody>
                {pageRows.map((setup) => (
                  <tr className={selected === setup ? "selected" : ""} onClick={() => setSelected(setup)}
                    key={displayText(setup.symbol) + displayText(setup.side)}>
                    <td><b>{displayText(setup.base)}</b></td>
                    <td className={sideTone(setup.side)}>{displayText(setup.side)}</td>
                    <td><Tag className={`status ${displayText(setup.status).toLowerCase()}`}>{displayText(setup.status)}</Tag></td>
                    {[setup.bar_close, setup.entry, setup.sl, setup.tp1, setup.tp2, setup.tp2_rr].map((value, index) => <td key={index}>{formatNumber(value)}</td>)}
                    {SIGNAL_GATES.map(([key]) => (
                      <td key={key}>
                        <span className={isTruthyFlag(setup[key]) ? "gate-check passed" : "gate-check"}>
                          {isTruthyFlag(setup[key]) ? "✓" : "—"}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mobile-list">
            {pageRows.map((setup) => {
              const passed = SIGNAL_GATES.filter(([key]) =>
                isTruthyFlag(setup[key])
              ).length;
              return (
                <button className={`mobile-data-card ${selected === setup ? "selected" : ""}`}
                  onClick={() => setSelected(setup)}
                  key={displayText(setup.symbol) + displayText(setup.side)}>
                  <header>
                    <span><b>{displayText(setup.base)}</b><small>USDT PERP</small></span>
                    <i className={sideTone(setup.side)}>{displayText(setup.side)}</i>
                    <Tag className={`status ${displayText(setup.status).toLowerCase()}`}>
                      {displayText(setup.status)}
                    </Tag>
                  </header>
                  <div className="mobile-metrics">
                    <span>Entry<b>{formatNumber(setup.entry)}</b></span>
                    <span>SL<b className="negative">{formatNumber(setup.sl)}</b></span>
                    <span>TP2<b className="positive">{formatNumber(setup.tp2)}</b></span>
                    <span>Gate<b>{passed}/{SIGNAL_GATES.length}</b></span>
                  </div>
                  <footer>{displayText(setup.missing)}</footer>
                </button>
              );
            })}
          </div>
          <TablePager page={page} pageSize={pageSize} total={rows.length}
            onChange={(nextPage, nextSize) => {
              setPageSize(nextSize);
              setPage(nextSize !== pageSize ? 1 : nextPage);
            }} />
          <footer className="table-foot">
            Lần quét cuối: {displayText(last?.scanned_at)} · {formatNumber(last?.success_count, 0)}/{formatNumber(last?.universe_count, 0)} thành công · {formatNumber(last?.duration_seconds, 1)}s
          </footer>
        </Panel>
        <Panel title="Chi tiết tín hiệu" meta={displayText(selected?.status)} icon={<Gauge />}>
          <div className="instrument-title">
            <div><small>PERPETUAL</small>{displayText(selected?.base)}/USDT</div>
            <span className={sideTone(selected?.side)}>{displayText(selected?.side)}</span>
          </div>
          <GateList setup={selected} />
          <div className="scan-levels">
            <Level label="Entry" value={selected?.entry} tone="live-text" />
            <Level label="R:R TP2" value={selected?.tp2_rr} />
          </div>
          <Button type="primary" className="primary wide" icon={<Bell />}>TẠO CẢNH BÁO <ChevronRight /></Button>
        </Panel>
      </div>
    </>
  );
}
