import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Wifi } from "lucide-react";
import { Sidebar } from "../components/layout/Sidebar";
import { Topbar } from "../components/layout/Topbar";
import { useMarketSocket } from "../hooks/useMarketSocket";
import { getTerminalSnapshot } from "../services/api";
import {
  EMPTY_SNAPSHOT, PAGE_META, type Page
} from "../shared/constants";
import { displayText } from "../shared/format";
import type { Setup, TerminalSnapshot } from "../shared/types";

const TerminalPage = lazy(() => import(
  "../features/terminal/TerminalPage"
).then((module) => ({ default: module.TerminalPage })));
const ScannerPage = lazy(() => import(
  "../features/scanner/ScannerPage"
).then((module) => ({ default: module.ScannerPage })));
const SignalPage = lazy(() => import(
  "../features/signal/SignalPage"
).then((module) => ({ default: module.SignalPage })));
const PortfolioPage = lazy(() => import(
  "../features/portfolio/PortfolioPage"
).then((module) => ({ default: module.PortfolioPage })));
const HistoryPage = lazy(() => import(
  "../features/history/HistoryPage"
).then((module) => ({ default: module.HistoryPage })));
const ApiPage = lazy(() => import(
  "../features/system/ApiPage"
).then((module) => ({ default: module.ApiPage })));

export default function App() {
  const initialPage = location.hash.slice(1) as Page;
  const [page, setPage] = useState<Page>(
    PAGE_META[initialPage] ? initialPage : "terminal"
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [data, setData] = useState<TerminalSnapshot>(EMPTY_SNAPSHOT);
  const [selectedKey, setSelectedKey] = useState<string>();
  const [error, setError] = useState("");
  const market = useMarketSocket();

  const selected = useMemo(() =>
    data.setups.find((setup) =>
      displayText(setup.symbol) + displayText(setup.side) === selectedKey
    ) ??
    data.setups.find((setup) => setup.status === "READY") ??
    data.setups.find((setup) => setup.entry != null) ??
    data.setups[0],
  [data.setups, selectedKey]);

  const setSelected = (setup: Setup) =>
    setSelectedKey(displayText(setup.symbol) + displayText(setup.side));

  const load = () => getTerminalSnapshot()
    .then((snapshot) => {
      setData(snapshot);
      setError("");
    })
    .catch((loadError: Error) => setError(loadError.message));

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    location.hash = page;
    document.title = `${PAGE_META[page].title} · Sonic R`;
  }, [page]);

  return (
    <div className="app">
      <Sidebar
        page={page}
        setPage={setPage}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <main>
        <Topbar page={page} market={market} onMenu={() => setSidebarOpen(true)} />
        {error && (
          <div className="error-banner">
            <Wifi /> Không kết nối được API: {error}
          </div>
        )}
        <div className="content">
          <Suspense fallback={<div className="page-loading">Đang tải màn hình…</div>}>
            {page === "terminal" && <TerminalPage data={data} market={market} selected={selected} setSelected={setSelected} />}
            {page === "scanner" && <ScannerPage data={data} selected={selected} setSelected={setSelected} refresh={load} />}
            {page === "signal" && <SignalPage data={data} market={market} selected={selected} setSelected={setSelected} />}
            {page === "portfolio" && <PortfolioPage data={data} market={market} />}
            {page === "history" && <HistoryPage data={data} />}
            {page === "api" && <ApiPage market={market} />}
          </Suspense>
        </div>
      </main>
    </div>
  );
}
