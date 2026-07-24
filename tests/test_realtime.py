from backend.app.services.realtime_market import RealtimeMarketHub


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

