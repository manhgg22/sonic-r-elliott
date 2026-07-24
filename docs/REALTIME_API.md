# Sonic R Realtime API

## Entry points

| Purpose | URL |
|---|---|
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| WebSocket console | `http://localhost:8000/api/v1/market/console` |
| OpenAPI JSON | `http://localhost:8000/openapi.json` |
| Realtime health | `GET /api/v1/market/realtime/status` |
| Initial snapshot | `GET /api/v1/market/realtime/snapshot` |
| Realtime deltas | `WS /api/v1/market/stream` |
| Terminal data | `GET /api/v1/terminal/snapshot` |

## Update policy

- Ticker, bid and ask are pushed whenever OKX publishes an update.
- The active M15 candle is pushed as it changes with `confirmed: false`.
- A closed M15 candle has `confirmed: true`.
- Strategy signals, paper entries and multi-timeframe calculations only use
  closed candles. The active candle is display-only.
- The Sonic backend maintains one pair of shared OKX connections and fans out
  updates to browser clients. Browser count therefore does not multiply OKX
  subscriptions.

## WebSocket messages

The first message is a complete snapshot:

```json
{
  "type": "snapshot",
  "sequence": 42,
  "server_time": "2026-07-24T04:30:00Z",
  "status": {
    "connected": true,
    "stale": false,
    "message_age_seconds": 0.1,
    "instruments": 50,
    "clients": 1,
    "reconnects": 0,
    "streams": {
      "tickers": {"connected": true, "last_error": null},
      "candles": {"connected": true, "last_error": null}
    }
  },
  "tickers": {},
  "candles": {}
}
```

Subsequent messages are deltas:

```json
{
  "type": "ticker",
  "sequence": 43,
  "instrument_id": "BTC-USDT-SWAP",
  "last": 64231.5,
  "bid": 64231.4,
  "ask": 64231.6,
  "open_24h": 63000,
  "exchange_ts": 1784870400123,
  "received_at": "2026-07-24T04:30:00.130Z"
}
```

```json
{
  "type": "candle",
  "sequence": 44,
  "instrument_id": "BTC-USDT-SWAP",
  "bar": "15m",
  "timestamp": 1784870400000,
  "open": 64190,
  "high": 64250,
  "low": 64170,
  "close": 64231.5,
  "volume": 128.4,
  "confirmed": false,
  "received_at": "2026-07-24T04:30:00.140Z"
}
```

Health and heartbeat messages may also be sent. Consumers should ignore
unknown message types to remain forward compatible.

## Browser example

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/market/stream");

ws.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  if (message.type === "snapshot") {
    initialiseMarket(message.tickers, message.candles);
  } else if (message.type === "ticker") {
    updateTicker(message.instrument_id, message);
  } else if (message.type === "candle") {
    updateCandle(message.instrument_id, message);
  }
};
```

## Python example

```python
import asyncio
import json
import websockets


async def watch():
    async with websockets.connect(
        "ws://localhost:8000/api/v1/market/stream"
    ) as socket:
        async for raw in socket:
            message = json.loads(raw)
            print(message["type"], message.get("instrument_id"))


asyncio.run(watch())
```

## Operational rules

- Treat `status.stale: true` as unavailable market data.
- Reconnect with exponential backoff after a socket close.
- Replace the current candle by `(instrument_id, bar, timestamp)`.
- Never generate a trading signal from a candle where `confirmed` is false.
- Use `sequence` to detect dropped deltas and reload the REST snapshot if a
  gap is detected.
