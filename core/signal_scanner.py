"""Scanner OKX dùng chung cho monitor và dashboard."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import local

import ccxt
import pandas as pd

from .trade_setup import latest_trade_setup
from data.loader import data_quality_check, fetch_ohlcv, okx_usdt_swap_universe


_THREAD_STATE = local()


def _exchange():
    if not hasattr(_THREAD_STATE, "exchange"):
        _THREAD_STATE.exchange = ccxt.okx({"enableRateLimit": True})
        _THREAD_STATE.exchange.load_markets()
    return _THREAD_STATE.exchange


def scan_one(meta: dict) -> list[dict]:
    """Quét hai hướng của một coin, lỗi coin nào không làm dừng cả lượt."""
    try:
        exchange = _exchange()
        entry = fetch_ohlcv(
            meta["symbol"], "15m", 3, exchange_id="okx",
            exchange=exchange, cache_max_age=300, verbose=False,
        )
        main = fetch_ohlcv(
            meta["symbol"], "1H", 12, exchange_id="okx",
            exchange=exchange, cache_max_age=300, verbose=False,
        )
        for frame, timeframe in ((entry, "15m"), (main, "1H")):
            if not data_quality_check(frame, timeframe)["ok"]:
                raise RuntimeError(f"dữ liệu {timeframe} lỗi")
        return [
            {**meta, **latest_trade_setup(meta["symbol"], entry, main, side=side)}
            for side in ("LONG", "SHORT")
        ]
    except Exception as exc:
        return [
            {
                **meta,
                "side": side,
                "status": "ERROR",
                "actionable": False,
                "missing": str(exc),
            }
            for side in ("LONG", "SHORT")
        ]


def scan_market(universe=None, progress=None, workers=4) -> pd.DataFrame:
    """Quét universe song song; progress(done, total) là callback tùy chọn."""
    universe = universe or okx_usdt_swap_universe()
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(scan_one, meta) for meta in universe]
        for done, future in enumerate(as_completed(futures), 1):
            rows.extend(future.result())
            if progress:
                progress(done, len(futures))
    return pd.DataFrame(rows)
