import { useEffect, useRef, useState } from "react";
import type { Candle, MarketState, Ticker } from "../shared/types";

const initial: MarketState = {
  connected: false, status: {}, tickers: {}, candles: {}, events: [], sequence: 0
};

export function useMarketSocket(): MarketState {
  const [state, setState] = useState<MarketState>(initial);
  const retry = useRef(0);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer = 0;
    let stopped = false;

    const connect = () => {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${location.host}/api/v1/market/stream`);
      socket.onopen = () => {
        retry.current = 0;
        setState((current) => ({ ...current, connected: true }));
      };
      socket.onmessage = ({ data }) => {
        const message = JSON.parse(data) as Record<string, unknown>;
        setState((current) => {
          const next = {
            ...current,
            events: [...current.events.slice(-199), message],
            sequence: Number(message.sequence ?? current.sequence)
          };
          if (message.type === "snapshot") {
            next.tickers = (message.tickers ?? {}) as Record<string, Ticker>;
            next.candles = (message.candles ?? {}) as Record<string, Candle>;
            next.status = message.status ?? {};
          } else if (message.type === "batch") {
            // Server coalesces rapid ticks into one batch per interval;
            // only spread when something actually changed.
            const tickers = message.tickers as Record<string, Ticker> | undefined;
            const candles = message.candles as Record<string, Candle> | undefined;
            if (tickers && Object.keys(tickers).length) {
              next.tickers = { ...current.tickers, ...tickers };
            }
            if (candles && Object.keys(candles).length) {
              next.candles = { ...current.candles, ...candles };
            }
          } else if (message.type === "ticker") {
            const ticker = message as unknown as Ticker;
            next.tickers = { ...current.tickers, [ticker.instrument_id!]: ticker };
          } else if (message.type === "candle") {
            const candle = message as unknown as Candle;
            next.candles = { ...current.candles, [candle.instrument_id!]: candle };
          } else if (message.status) {
            next.status = message.status as MarketState["status"];
          }
          return next;
        });
      };
      socket.onclose = () => {
        setState((current) => ({ ...current, connected: false }));
        if (!stopped) {
          const delay = Math.min(1000 * 2 ** retry.current++, 15000);
          timer = window.setTimeout(connect, delay);
        }
      };
      socket.onerror = () => socket?.close();
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, []);
  return state;
}
