import { useEffect, useRef, useState } from "react";
import {
  ColorType,
  createChart,
  IChartApi,
  ISeriesApi,
  LineStyle,
  UTCTimestamp
} from "lightweight-charts";
import { getCandles } from "./api";
import type { Candle, CandleRow, Setup } from "./types";

type Props = {
  instrumentId: string;
  live?: Candle;
  setup?: Setup;
  height?: number;
};

export function MarketChart({ instrumentId, live, setup, height = 540 }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi>();
  const candleRef = useRef<ISeriesApi<"Candlestick">>();
  const ema34Ref = useRef<ISeriesApi<"Line">>();
  const ema89Ref = useRef<ISeriesApi<"Line">>();
  const volumeRef = useRef<ISeriesApi<"Histogram">>();
  const liveRef = useRef<Candle>();
  const [rows, setRows] = useState<CandleRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    liveRef.current = undefined;
    getCandles(instrumentId).then(setRows).catch((e: Error) => setError(e.message));
  }, [instrumentId]);

  // Khi nến M15 mới mở, chốt nến vừa đóng vào lịch sử để nó không bị mất
  // (rows chỉ fetch REST một lần; nếu không commit thì mỗi 15 phút thủng 1 nến).
  useEffect(() => {
    if (!live) return;
    const previous = liveRef.current;
    liveRef.current = live;
    if (!previous || previous.timestamp >= live.timestamp) return;
    setRows((current) => {
      if (!current.length) return current;
      const lastTime = +new Date(current[current.length - 1].timestamp);
      if (previous.timestamp <= lastTime) return current;
      const prevRow = current[current.length - 1];
      return [...current, {
        timestamp: new Date(previous.timestamp).toISOString(),
        open: previous.open, high: previous.high, low: previous.low,
        close: previous.close, volume: previous.volume, confirmed: true,
        ema34: prevRow?.ema34 ?? previous.close,
        ema89: prevRow?.ema89 ?? previous.close
      }];
    });
  }, [live]);

  useEffect(() => {
    if (!container.current) return;
    const chart = createChart(container.current, {
      height,
      width: container.current.clientWidth,
      layout: {
        background: { type: ColorType.Solid, color: "#0b161a" },
        textColor: "#71868e",
        fontFamily: "\"Be Vietnam Pro\", Arial, sans-serif",
        fontSize: 12
      },
      grid: {
        vertLines: { color: "#17262b" },
        horzLines: { color: "#17262b" }
      },
      rightPriceScale: { borderColor: "#223238" },
      timeScale: { borderColor: "#223238", timeVisible: true, secondsVisible: false },
      crosshair: {
        vertLine: { color: "#3f5961", labelBackgroundColor: "#102328" },
        horzLine: { color: "#3f5961", labelBackgroundColor: "#102328" }
      }
    });
    chartRef.current = chart;
    candleRef.current = chart.addCandlestickSeries({
      upColor: "#35e48c", downColor: "#ff6b76",
      wickUpColor: "#35e48c", wickDownColor: "#ff6b76",
      borderVisible: false
    });
    ema34Ref.current = chart.addLineSeries({
      color: "#28b8f7", lineWidth: 2, title: "EMA34", priceLineVisible: false
    });
    ema89Ref.current = chart.addLineSeries({
      color: "#ffbe3f", lineWidth: 2, title: "EMA89", priceLineVisible: false
    });
    volumeRef.current = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
      lastValueVisible: false,
      priceLineVisible: false
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 }
    });
    const resize = new ResizeObserver(() => {
      if (container.current) chart.applyOptions({ width: container.current.clientWidth });
    });
    resize.observe(container.current);
    return () => {
      resize.disconnect();
      chart.remove();
    };
  }, [height]);

  useEffect(() => {
    if (!rows.length || !candleRef.current) return;
    const merged = [...rows];
    if (live) {
      const iso = new Date(live.timestamp).toISOString();
      const found = merged.findIndex((row) => +new Date(row.timestamp) === live.timestamp);
      const previous = merged[Math.max(0, found >= 0 ? found - 1 : merged.length - 1)];
      const row: CandleRow = {
        timestamp: iso, open: live.open, high: live.high, low: live.low,
        close: live.close, volume: live.volume, confirmed: live.confirmed,
        ema34: previous?.ema34 ?? live.close, ema89: previous?.ema89 ?? live.close
      };
      if (found >= 0) merged[found] = row;
      else merged.push(row);
    }
    const time = (value: string) => Math.floor(+new Date(value) / 1000) as UTCTimestamp;
    candleRef.current.setData(merged.map((r) => ({
      time: time(r.timestamp), open: r.open, high: r.high, low: r.low, close: r.close
    })));
    ema34Ref.current?.setData(merged.map((r) => ({ time: time(r.timestamp), value: r.ema34 })));
    ema89Ref.current?.setData(merged.map((r) => ({ time: time(r.timestamp), value: r.ema89 })));
    volumeRef.current?.setData(merged.map((r) => ({
      time: time(r.timestamp), value: r.volume,
      color: r.close >= r.open ? "#35e48c55" : "#ff6b7655"
    })));
    chartRef.current?.timeScale().fitContent();
  }, [rows, live]);

  useEffect(() => {
    if (!candleRef.current || !setup) return;
    const lines = [
      ["entry", "ENTRY", "#19d9ec", LineStyle.Solid],
      ["sl", "SL", "#ff6b76", LineStyle.Dashed],
      ["tp1", "TP1", "#35e48c", LineStyle.Dotted],
      ["tp2", "TP2", "#35e48c", LineStyle.Dotted]
    ] as const;
    const handles = lines.flatMap(([key, title, color, lineStyle]) => {
      const raw = setup[key];
      if (raw === null || raw === undefined) return [];
      const price = Number(raw);
      return Number.isFinite(price)
        ? [candleRef.current!.createPriceLine({
            price, title, color, lineWidth: 1, lineStyle, axisLabelVisible: true
          })]
        : [];
    });
    return () => handles.forEach((line) => candleRef.current?.removePriceLine(line));
  }, [setup]);

  return (
    <div className="chart-shell">
      <div className="chart-meta">
        <span>{instrumentId}</span>
        <span className={live?.confirmed ? "positive" : "warning"}>
          {live?.confirmed ? "CLOSED · ĐÃ XÁC NHẬN" : "LIVE · CHƯA XÁC NHẬN"}
        </span>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div ref={container} />
    </div>
  );
}
