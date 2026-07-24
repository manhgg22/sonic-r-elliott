export type StreamState = {
  connected?: boolean;
  last_error?: string | null;
  updated_at?: string;
};

export type RealtimeStatus = {
  connected?: boolean;
  stale?: boolean;
  message_age_seconds?: number | null;
  instruments?: number;
  clients?: number;
  reconnects?: number;
  streams?: Record<string, StreamState>;
};

export type Ticker = {
  type?: "ticker";
  instrument_id?: string;
  last: number;
  bid?: number | null;
  ask?: number | null;
  open_24h?: number | null;
  exchange_ts?: number;
  received_at?: string;
  sequence?: number;
};

export type Candle = {
  type?: "candle";
  instrument_id?: string;
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  confirmed: boolean;
  sequence?: number;
};

export type MarketState = {
  connected: boolean;
  status: RealtimeStatus;
  tickers: Record<string, Ticker>;
  candles: Record<string, Candle>;
  events: Array<Record<string, unknown>>;
  sequence: number;
};

export type Setup = Record<string, string | number | boolean | null>;
export type Trade = Record<string, string | number | boolean | null>;
export type Run = Record<string, string | number | boolean | null>;
export type PaperEvent = Record<string, string | number | boolean | null>;

export type TerminalSnapshot = {
  setups: Setup[];
  runs: Run[];
  trades: Trade[];
  events: PaperEvent[];
};

export type CandleRow = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema34: number;
  ema89: number;
  confirmed: boolean;
};
