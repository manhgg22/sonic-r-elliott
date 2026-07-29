import type { TerminalSnapshot } from "./types";

export type Page =
  "terminal" | "scanner" | "signal" | "portfolio" | "history" | "api";

export const EMPTY_SNAPSHOT: TerminalSnapshot = {
  setups: [],
  runs: [],
  trades: [],
  events: [],
  risk: {
    risk_per_trade_pct: 0.5,
    max_portfolio_risk_pct: 2,
    risk_guard_enabled: true,
    committed_risk_pct: 0,
    pending_orders: 0,
    open_positions: 0,
    pending_expiry_bars: 4
  }
};

export const SIGNAL_GATES = [
  ["f_trend", "Xu hướng EMA"],
  ["f_regime", "Thị trường có xu hướng"],
  ["f_session", "Phiên Âu / Mỹ"],
  ["f_breakout", "Breakout"],
  ["f_dow", "Cấu trúc Dow"],
  ["f_value_zone", "Vùng giá trị"],
  ["f_pa", "Price Action"]
] as const;

export const PAGE_META: Record<Page, {
  eyebrow: string;
  title: string;
  description: string;
}> = {
  terminal: {
    eyebrow: "Không gian phân tích",
    title: "Tổng quan thị trường",
    description: "Theo dõi tín hiệu, cấu trúc giá và vị thế paper trong một màn hình."
  },
  scanner: {
    eyebrow: "Signal engine",
    title: "Bộ quét tín hiệu",
    description: "Lọc cơ hội theo mô hình 7-gate trên nến đã xác nhận."
  },
  signal: {
    eyebrow: "Phân tích chuyên sâu",
    title: "Chi tiết thiết lập",
    description: "Kiểm chứng luận điểm, vùng vào lệnh và cấu trúc rủi ro."
  },
  portfolio: {
    eyebrow: "Paper portfolio",
    title: "Danh mục & rủi ro",
    description: "Đo hiệu suất theo R và kiểm soát mức phơi nhiễm."
  },
  history: {
    eyebrow: "Execution audit",
    title: "Lịch sử lệnh",
    description: "Đối chiếu toàn bộ vòng đời ARMED, FILL và kết quả thoát lệnh."
  },
  api: {
    eyebrow: "Hạ tầng realtime",
    title: "API & WebSocket",
    description: "Quan sát luồng dữ liệu, độ trễ và trạng thái dịch vụ."
  }
};
