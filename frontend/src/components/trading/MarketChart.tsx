import { useEffect, useRef, useState } from "react";
import {
  ColorType,
  createChart,
  IChartApi,
  ISeriesApi,
  LineStyle,
  UTCTimestamp
} from "lightweight-charts";
import { getCandles } from "../../services/api";
import type { Candle, CandleRow, Setup } from "../../shared/types";

type Props = {
  instrumentId: string;
  live?: Candle;
  setup?: Setup;
  height?: number;
};

const nextEma = (value: number, previous: number, period: number) => {
  const alpha = 2 / (period + 1);
  return value * alpha + previous * (1 - alpha);
};

export function MarketChart({ instrumentId, live, setup, height = 540 }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi>();
  const candleRef = useRef<ISeriesApi<"Candlestick">>();
  const ema34Ref = useRef<ISeriesApi<"Line">>();
  const ema34HighRef = useRef<ISeriesApi<"Line">>();
  const ema34LowRef = useRef<ISeriesApi<"Line">>();
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
      const previousIndex = current.findIndex(
        (row) => +new Date(row.timestamp) === previous.timestamp
      );
      const baseRow = previousIndex > 0
        ? current[previousIndex - 1]
        : current[current.length - 1];
      const committed: CandleRow = {
        timestamp: new Date(previous.timestamp).toISOString(),
        open: previous.open, high: previous.high, low: previous.low,
        close: previous.close, volume: previous.volume, confirmed: true,
        ema34: nextEma(previous.close, baseRow?.ema34 ?? previous.close, 34),
        ema34_high: nextEma(
          previous.high, baseRow?.ema34_high ?? previous.high, 34
        ),
        ema34_low: nextEma(
          previous.low, baseRow?.ema34_low ?? previous.low, 34
        ),
        ema89: nextEma(previous.close, baseRow?.ema89 ?? previous.close, 89)
      };
      if (previousIndex >= 0) {
        const updated = [...current];
        updated[previousIndex] = committed;
        return updated;
      }
      return [...current, committed].slice(-300);
    });
  }, [live]);

  useEffect(() => {
    if (!container.current) return;
    const chart = createChart(container.current, {
      height,
      width: container.current.clientWidth,
      layout: {
        background: { type: ColorType.Solid, color: "#0f1422" },
        textColor: "#6f7b94",
        fontFamily: "\"Be Vietnam Pro\", Arial, sans-serif",
        fontSize: 12
      },
      grid: {
        vertLines: { color: "#1a2235" },
        horzLines: { color: "#1a2235" }
      },
      rightPriceScale: { borderColor: "#232b42" },
      timeScale: { borderColor: "#232b42", timeVisible: true, secondsVisible: false },
      crosshair: {
        vertLine: { color: "#46536d", labelBackgroundColor: "#202a42" },
        horzLine: { color: "#46536d", labelBackgroundColor: "#202a42" }
      }
    });
    chartRef.current = chart;
    candleRef.current = chart.addCandlestickSeries({
      upColor: "#43d99b", downColor: "#ff7185",
      wickUpColor: "#43d99b", wickDownColor: "#ff7185",
      borderVisible: false
    });
    ema34Ref.current = chart.addLineSeries({
      color: "#49d8ed", lineWidth: 2, title: "Dragon C", priceLineVisible: false
    });
    ema34HighRef.current = chart.addLineSeries({
      color: "#49d8ed88", lineWidth: 1, title: "Dragon H",
      priceLineVisible: false, lastValueVisible: false
    });
    ema34LowRef.current = chart.addLineSeries({
      color: "#49d8ed88", lineWidth: 1, title: "Dragon L",
      priceLineVisible: false, lastValueVisible: false
    });
    ema89Ref.current = chart.addLineSeries({
      color: "#f5b942", lineWidth: 2, title: "EMA89", priceLineVisible: false
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
        ema34: nextEma(live.close, previous?.ema34 ?? live.close, 34),
        ema34_high: nextEma(
          live.high, previous?.ema34_high ?? live.high, 34
        ),
        ema34_low: nextEma(
          live.low, previous?.ema34_low ?? live.low, 34
        ),
        ema89: nextEma(live.close, previous?.ema89 ?? live.close, 89)
      };
      if (found >= 0) merged[found] = row;
      else merged.push(row);
    }
    const time = (value: string) => Math.floor(+new Date(value) / 1000) as UTCTimestamp;
    candleRef.current.setData(merged.map((r) => ({
      time: time(r.timestamp), open: r.open, high: r.high, low: r.low, close: r.close
    })));
    ema34Ref.current?.setData(merged.map((r) => ({ time: time(r.timestamp), value: r.ema34 })));
    ema34HighRef.current?.setData(merged.map((r) => ({
      time: time(r.timestamp), value: r.ema34_high
    })));
    ema34LowRef.current?.setData(merged.map((r) => ({
      time: time(r.timestamp), value: r.ema34_low
    })));
    ema89Ref.current?.setData(merged.map((r) => ({ time: time(r.timestamp), value: r.ema89 })));
    volumeRef.current?.setData(merged.map((r) => ({
      time: time(r.timestamp), value: r.volume,
      color: r.close >= r.open ? "#43d99b55" : "#ff718555"
    })));
    chartRef.current?.timeScale().fitContent();
  }, [rows, live]);

  useEffect(() => {
    if (!candleRef.current || !setup) return;
    const lines = [
      ["entry", "ENTRY", "#49d8ed", LineStyle.Solid],
      ["sl", "SL", "#ff7185", LineStyle.Dashed],
      ["tp1", "TP1", "#43d99b", LineStyle.Dotted],
      ["tp2", "TP2", "#43d99b", LineStyle.Dotted]
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
          {live?.confirmed ? "ĐÃ ĐÓNG · ĐÃ XÁC NHẬN" : "ĐANG CHẠY · CHƯA XÁC NHẬN"}
        </span>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div ref={container} />
    </div>
  );
}
