from backend.app.services.realtime_market import RealtimeMarketHub
from backend.app.services.okx_market_service import OkxMarketService


def test_okx_ticker_message_is_normalized():
    message = RealtimeMarketHub.parse_message({
        "arg": {"channel": "tickers", "instId": "BTC-USDT-SWAP"},
        "data": [{
            "instId": "BTC-USDT-SWAP",
            "last": "64231.5",
            "bidPx": "64231.4",
            "askPx": "64231.6",
            "open24h": "63000",
            "ts": "1784870400123",
        }],
    })
    assert message["type"] == "ticker"
    assert message["instrument_id"] == "BTC-USDT-SWAP"
    assert message["last"] == 64231.5
    assert message["exchange_ts"] == 1784870400123


def test_okx_live_candle_keeps_confirm_flag():
    message = RealtimeMarketHub.parse_message({
        "arg": {"channel": "candle15m", "instId": "ETH-USDT-SWAP"},
        "data": [[
            "1784870400000", "3500", "3512", "3498", "3508",
            "120.5", "0", "0", "0",
        ]],
    })
    assert message["type"] == "candle"
    assert message["bar"] == "15m"
    assert message["close"] == 3508.0
    assert message["confirmed"] is False


def test_rest_candles_include_complete_dragon_band(monkeypatch):
    service = OkxMarketService("https://www.okx.com", 1)
    rows = [
        ["2000", "102", "106", "101", "105", "12", "0", "0", "1"],
        ["1000", "100", "104", "99", "103", "10", "0", "0", "1"],
    ]
    monkeypatch.setattr(service, "_get", lambda _path, _params: rows)
    candles = service.candles("BTC-USDT-SWAP", limit=50)
    assert len(candles) == 2
    assert {
        "ema34", "ema34_high", "ema34_low", "ema89"
    }.issubset(candles[-1])
    assert candles[-1]["ema34_high"] > candles[-1]["ema34_low"]
