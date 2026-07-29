import {
  lazy, Suspense, useCallback, useEffect, useMemo, useState
} from "react";
import { Wifi } from "lucide-react";
import { Sidebar } from "../components/layout/Sidebar";
import { Topbar } from "../components/layout/Topbar";
import { LoginPage } from "../features/auth/LoginPage";
import { useMarketSocket } from "../hooks/useMarketSocket";
import {
  ApiError, getAuthSession, getTerminalSnapshot, logout,
  type AuthSession
} from "../services/api";
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
  const [session, setSession] = useState<AuthSession | null>();
  const handleUnauthorized = useCallback(() => setSession(null), []);
  const market = useMarketSocket(Boolean(session), handleUnauthorized);

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
    .catch((loadError: Error) => {
      if (loadError instanceof ApiError && loadError.status === 401) {
        setSession(null);
        return;
      }
      setError(loadError.message);
    });

  useEffect(() => {
    getAuthSession()
      .then(setSession)
      .catch(() => setSession(null));
  }, []);

  useEffect(() => {
    if (!session) return;
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [session]);

  useEffect(() => {
    location.hash = page;
    document.title = `${PAGE_META[page].title} · Sonic R`;
  }, [page]);

  if (session === undefined) {
    return (
      <main className="auth-loading">
        <span className="login-mark"><i /><i /><i /></span>
        <b>SONIC R</b>
        <small>Đang xác minh phiên đăng nhập…</small>
      </main>
    );
  }

  if (session === null) {
    return <LoginPage onAuthenticated={setSession} />;
  }

  const signOut = async () => {
    try {
      await logout();
    } finally {
      setData(EMPTY_SNAPSHOT);
      setSession(null);
    }
  };

  return (
    <div className="app">
      <Sidebar
        page={page}
        setPage={setPage}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        username={session.username}
        onLogout={signOut}
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
            {page === "portfolio" && <PortfolioPage data={data} market={market} refresh={load} />}
            {page === "history" && <HistoryPage data={data} />}
            {page === "api" && <ApiPage market={market} />}
          </Suspense>
        </div>
      </main>
    </div>
  );
}
