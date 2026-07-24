import asyncio
import json
import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

import websockets


LOGGER = logging.getLogger(__name__)
DEFAULT_INSTRUMENTS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RealtimeMarketHub:
    """One shared OKX connection fan-outs market updates to all API clients."""

    def __init__(
        self,
        ws_url: str,
        candle_ws_url: str | None = None,
        instrument_provider: Callable[[], Iterable[str]] | None = None,
        max_instruments: int = 50,
        stale_seconds: float = 10,
        broadcast_interval: float = 0.25,
    ):
        self.ws_url = ws_url
        self.candle_ws_url = candle_ws_url or ws_url.replace(
            "/public", "/business"
        )
        self.instrument_provider = instrument_provider
        self.max_instruments = max(1, max_instruments)
        self.stale_seconds = stale_seconds
        self.broadcast_interval = max(0.05, broadcast_interval)
        self.tickers: dict[str, dict[str, Any]] = {}
        self.candles: dict[str, dict[str, Any]] = {}
        self.status: dict[str, Any] = {
            "connected": False,
            "last_message_at": None,
            "last_error": None,
            "reconnects": 0,
            "streams": {
                "tickers": {"connected": False, "last_error": None},
                "candles": {"connected": False, "last_error": None},
            },
        }
        self._subscribers: set[asyncio.Queue] = set()
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._sequence = 0
        self._pending_tickers: dict[str, dict[str, Any]] = {}
        self._pending_candles: dict[str, dict[str, Any]] = {}

    def instruments(self) -> list[str]:
        values = list(DEFAULT_INSTRUMENTS)
        if self.instrument_provider:
            try:
                values.extend(self.instrument_provider())
            except Exception:
                LOGGER.exception("Could not refresh realtime instruments")
        normalized = []
        for value in values:
            instrument_id = str(value).strip().upper()
            if not instrument_id:
                continue
            if not instrument_id.endswith("-SWAP"):
                base = instrument_id.split("/")[0].split("-")[0]
                instrument_id = f"{base}-USDT-SWAP"
            if instrument_id not in normalized:
                normalized.append(instrument_id)
        return normalized[: self.max_instruments]

    async def start(self):
        if any(not task.done() for task in self._tasks):
            return
        self._stop.clear()
        self._tasks = [
            asyncio.create_task(
                self._run_stream(self.ws_url, "tickers"),
                name="okx-realtime-tickers",
            ),
            asyncio.create_task(
                self._run_stream(self.candle_ws_url, "candles"),
                name="okx-realtime-candles",
            ),
            asyncio.create_task(
                self._flush_loop(),
                name="okx-realtime-flush",
            ),
        ]

    async def stop(self):
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    def subscribe(self) -> asyncio.Queue:
        """Queue of pre-serialized JSON text, ready for websocket.send_text."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers.discard(queue)

    def snapshot(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "sequence": self._sequence,
            "server_time": utc_now(),
            "status": self.health(),
            "tickers": self.tickers,
            "candles": self.candles,
        }

    def health(self) -> dict[str, Any]:
        result = dict(self.status)
        last_at = result.get("last_message_at")
        if last_at:
            age = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(last_at)
            ).total_seconds()
        else:
            age = None
        result["message_age_seconds"] = age
        result["stale"] = age is None or age > self.stale_seconds
        result["instruments"] = len(self.instruments())
        result["clients"] = len(self._subscribers)
        return result

    async def _broadcast(self, message: dict[str, Any]):
        if not self._subscribers:
            return
        self._sequence += 1
        message["sequence"] = self._sequence
        # Serialize once per broadcast instead of once per connected client.
        text = json.dumps(message)
        dead = []
        for queue in self._subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(text)
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            self._subscribers.discard(queue)

    async def _flush_loop(self):
        """Coalesce ticker/candle updates and broadcast them at a fixed
        cadence instead of once per exchange message, so N fast ticks
        across M instruments become a single batched frame per client."""
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.broadcast_interval
                )
            except asyncio.TimeoutError:
                pass
            await self._flush()

    async def _flush(self):
        if not self._pending_tickers and not self._pending_candles:
            return
        tickers, self._pending_tickers = self._pending_tickers, {}
        candles, self._pending_candles = self._pending_candles, {}
        await self._broadcast({
            "type": "batch",
            "tickers": tickers,
            "candles": candles,
        })

    def _subscription_args(self, stream: str) -> list[dict[str, str]]:
        args = []
        for instrument_id in self.instruments():
            channel = "tickers" if stream == "tickers" else "candle15m"
            args.append({"channel": channel, "instId": instrument_id})
        return args

    def _set_stream_status(
        self, stream: str, connected: bool, error: str | None = None
    ):
        self.status["streams"][stream] = {
            "connected": connected,
            "last_error": error,
            "updated_at": utc_now(),
        }
        states = self.status["streams"].values()
        self.status["connected"] = all(item["connected"] for item in states)
        errors = [
            item.get("last_error") for item in states
            if item.get("last_error")
        ]
        self.status["last_error"] = "; ".join(errors) if errors else None

    async def _run_stream(self, ws_url: str, stream: str):
        delay = 1
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    ws_url,
                    ping_interval=None,
                    open_timeout=10,
                    close_timeout=5,
                    max_size=2**20,
                ) as socket:
                    self._set_stream_status(stream, True)
                    self.status["connected_at"] = utc_now()
                    await socket.send(json.dumps({
                        "id": f"sonic{stream}",
                        "op": "subscribe",
                        "args": self._subscription_args(stream),
                    }))
                    await self._broadcast({
                        "type": "health", "status": self.health()
                    })
                    delay = 1
                    await self._receive(socket)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.status.update(
                    disconnected_at=utc_now(),
                    reconnects=self.status["reconnects"] + 1,
                )
                self._set_stream_status(stream, False, str(exc))
                LOGGER.warning("OKX %s websocket disconnected: %s", stream, exc)
                await self._broadcast({
                    "type": "health", "status": self.health()
                })
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2, 30)

    async def _receive(self, socket):
        while not self._stop.is_set():
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=20)
            except asyncio.TimeoutError:
                await socket.send("ping")
                raw = await asyncio.wait_for(socket.recv(), timeout=10)
            if raw == "pong":
                self.status["last_message_at"] = utc_now()
                continue
            payload = json.loads(raw)
            if payload.get("event") == "error":
                raise RuntimeError(
                    f"OKX {payload.get('code')}: {payload.get('msg')}"
                )
            message = self.parse_message(payload)
            if not message:
                continue
            self.status["last_message_at"] = utc_now()
            if message["type"] == "ticker":
                self.tickers[message["instrument_id"]] = message
                self._pending_tickers[message["instrument_id"]] = message
            elif message["type"] == "candle":
                self.candles[message["instrument_id"]] = message
                self._pending_candles[message["instrument_id"]] = message

    @staticmethod
    def parse_message(payload: dict[str, Any]) -> dict[str, Any] | None:
        arg = payload.get("arg") or {}
        data = payload.get("data") or []
        if not data:
            return None
        channel = arg.get("channel", "")
        instrument_id = arg.get("instId")
        received_at = utc_now()
        if channel == "tickers":
            row = data[0]
            return {
                "type": "ticker",
                "instrument_id": instrument_id or row.get("instId"),
                "last": float(row["last"]),
                "bid": float(row["bidPx"]) if row.get("bidPx") else None,
                "ask": float(row["askPx"]) if row.get("askPx") else None,
                "open_24h": (
                    float(row["open24h"]) if row.get("open24h") else None
                ),
                "exchange_ts": int(row["ts"]),
                "received_at": received_at,
            }
        if channel.startswith("candle"):
            row = data[0]
            return {
                "type": "candle",
                "instrument_id": instrument_id,
                "bar": channel.removeprefix("candle"),
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "confirmed": row[8] == "1",
                "received_at": received_at,
            }
        return None
