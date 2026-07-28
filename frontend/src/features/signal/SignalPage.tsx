import { BarChart3, ShieldCheck } from "lucide-react";
import { MarketChart } from "../../components/trading/MarketChart";
import { GateList, SetupPicker } from "../../components/trading/SignalControls";
import { Level, Panel } from "../../components/ui/Panel";
import { PAGE_META, SIGNAL_GATES } from "../../shared/constants";
import { displayText, isTruthyFlag } from "../../shared/format";
import type { MarketState, Setup, TerminalSnapshot } from "../../shared/types";

export function SignalPage({ data, market, selected, setSelected }: {
  data: TerminalSnapshot;
  market: MarketState;
  selected?: Setup;
  setSelected: (setup: Setup) => void;
}) {
  const base = selected?.base && selected.base !== "—"
    ? displayText(selected.base)
    : "BTC";
  const instrument = `${base}-USDT-SWAP`;
  const score = SIGNAL_GATES.filter(([key]) =>
    selected && isTruthyFlag(selected[key])
  ).length;
  const scorePercent = score / SIGNAL_GATES.length * 100;

  return (
    <>
      <div className="page-intro simple">
        <div><p>{PAGE_META.signal.description}</p><span><i /> Chỉ sử dụng nến đã đóng</span></div>
      </div>
      <div className="detail-grid">
        <Panel title={`${base}/USDT · ${displayText(selected?.side)}`} meta="M15 · CANDLE-CLOSE" icon={<BarChart3 />}>
          <div className="inline-picker">
            <SetupPicker setups={data.setups} selected={selected} onSelect={setSelected} />
          </div>
          <MarketChart instrumentId={instrument} live={market.candles[instrument]} setup={selected} height={620} />
        </Panel>
        <Panel title="Kiểm chứng luận điểm" meta={displayText(selected?.status)} icon={<ShieldCheck />}>
          <div className="score-ring" style={{ "--score": `${scorePercent}%` } as React.CSSProperties}>
            <div><b>{score}</b><small>/ {SIGNAL_GATES.length}</small><span>GATE ĐẠT</span></div>
          </div>
          <GateList setup={selected} />
          <div className="level-group">
            <Level label="Vùng vào lệnh" value={selected?.entry} tone="live-text" />
            <Level label="Dừng lỗ" value={selected?.sl} tone="negative" />
            <Level label="Chốt lời 1" value={selected?.tp1} tone="positive" />
            <Level label="Chốt lời 2" value={selected?.tp2} tone="positive" />
            <Level label="Trailing EMA34 H1" value={selected?.trail_h1} tone="warning" />
          </div>
          <div className="thesis">
            <b>Price Action</b><p>{displayText(selected?.pa)}</p>
            <b>PVSRA volume</b>
            <p>{displayText(selected?.pva_state)} · {Number(selected?.pva_ratio ?? 0).toFixed(2)}× trung bình</p>
            <b>Bối cảnh</b>
            <p>
              {displayText(selected?.session)} · ADX {Number(selected?.adx ?? 0).toFixed(1)}
              {" · "}EMA200 {selected?.ema200_aligned ? "đồng thuận" : "chưa đồng thuận"}
            </p>
            <b>Thời điểm xác nhận</b><p>{displayText(selected?.signal_time)}</p>
            <span><ShieldCheck /> Chỉ theo dõi paper, không gửi lệnh thật.</span>
          </div>
        </Panel>
      </div>
    </>
  );
}
