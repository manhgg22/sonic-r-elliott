import {
  BarChart3, Code2, History, LayoutDashboard, ScanLine, ShieldCheck,
  SlidersHorizontal, X
} from "lucide-react";
import type { Page } from "../../shared/constants";

export function Sidebar({ page, setPage, open, onClose }: {
  page: Page;
  setPage: (page: Page) => void;
  open: boolean;
  onClose: () => void;
}) {
  const items: Array<[Page, string, string, React.ReactNode]> = [
    ["terminal", "Tổng quan", "Thị trường & tín hiệu", <LayoutDashboard />],
    ["scanner", "Bộ quét", "Tìm cơ hội mới", <ScanLine />],
    ["signal", "Thiết lập", "Luận điểm chi tiết", <BarChart3 />],
    ["portfolio", "Danh mục", "Hiệu suất & rủi ro", <ShieldCheck />],
    ["history", "Lịch sử lệnh", "Khớp & thoát lệnh", <History />],
    ["api", "Hệ thống", "API & luồng dữ liệu", <Code2 />]
  ];

  const navigate = (id: Page) => {
    setPage(id);
    onClose();
  };

  return (
    <>
      <button className={`sidebar-scrim ${open ? "open" : ""}`} onClick={onClose} aria-label="Đóng menu" />
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="logo">
          <b><span /><span /><span /></b>
          <span>SONIC R<small>MARKET INTELLIGENCE</small></span>
          <button className="sidebar-close" onClick={onClose} aria-label="Đóng menu"><X /></button>
        </div>
        <div className="nav-label">Không gian làm việc</div>
        <nav>
          {items.map(([id, label, note, icon]) => (
            <button className={page === id ? "active" : ""} onClick={() => navigate(id)} key={id}>
              <span className="nav-icon">{icon}</span>
              <span className="nav-copy"><b>{label}</b><small>{note}</small></span>
              {page === id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-card">
          <span className="paper-icon"><ShieldCheck /></span>
          <div><b>Paper mode</b><small>Không gửi lệnh thật</small></div>
          <span className="online-dot" />
        </div>
        <div className="sidebar-foot">
          <div className="avatar">SR</div>
          <span><b>Sonic Operator</b><small>Decision support</small></span>
          <SlidersHorizontal />
        </div>
      </aside>
    </>
  );
}
