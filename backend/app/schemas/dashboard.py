from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class RiskSummary(BaseModel):
    paper_equity_usd: float
    risk_per_trade_pct: float
    risk_per_trade_usd: float
    max_portfolio_risk_pct: float
    max_portfolio_risk_usd: float
    risk_guard_enabled: bool
    committed_risk_pct: float
    committed_risk_usd: float
    pending_orders: int
    open_positions: int
    pending_expiry_bars: int


class RiskGuardUpdate(BaseModel):
    enabled: bool


class SnapshotResponse(BaseModel):
    setups: list[dict[str, Any]]
    runs: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    events: list[dict[str, Any]]
    risk: RiskSummary


class LivePosition(BaseModel):
    id: int
    base: str
    side: str
    instrument_id: str
    last: float
    live_r: float
    live_pnl_usd: float
    risk_amount_usd: float
    position_size: float
    entry_notional_usd: float


class LivePositionsResponse(BaseModel):
    positions: list[LivePosition]


class CandleResponse(BaseModel):
    instrument_id: str
    bar: str
    candles: list[dict[str, Any]]


class ScanResponse(BaseModel):
    coins: int
    long_ready: int
    short_ready: int
    errors: int
    opened: int
    open_positions: int
    duration_seconds: float


class RealtimeStatusResponse(BaseModel):
    connected: bool
    stale: bool
    message_age_seconds: float | None = None
    instruments: int
    clients: int
    reconnects: int
    last_message_at: str | None = None
    last_error: str | None = None
    streams: dict[str, dict[str, Any]]


class RealtimeSnapshotResponse(BaseModel):
    type: str
    sequence: int
    server_time: str
    status: RealtimeStatusResponse
    tickers: dict[str, dict[str, Any]]
    candles: dict[str, dict[str, Any]]
