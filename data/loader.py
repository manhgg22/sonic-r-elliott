"""Data loader ccxt.

Universe theo volume hoặc vốn hóa được lấy tại thời điểm chạy. Dùng danh sách
hôm nay để backtest quá khứ có survivorship bias và thường làm kết quả đẹp hơn
thực tế.
"""

import json
import time
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

try:
    import ccxt
except ImportError:
    ccxt = None


CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Universe cũ, giữ để dashboard và các lệnh lịch sử không đổi đột ngột.
TOP10 = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
]

TIMEFRAMES = ["15m", "1H", "4H", "1D"]

# ccxt dùng chữ thường cho tên timeframe.
TF_MAP = {"15m": "15m", "1H": "1h", "4H": "4h", "1D": "1d"}
STABLE_BASES = {
    "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "USDE", "USDS",
    "USD1", "RLUSD", "PYUSD", "USDD", "FRAX", "USDG", "GUSD", "EUR", "AEUR",
    "EURI",
}
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
_REQUEST_LOCK = Lock()
_LAST_REQUEST = {}


def _throttle(exchange_id: str) -> None:
    """Giữ tổng OKX dưới public limit 20 request/2 giây."""
    interval = 0.14 if exchange_id == "okx" else 0
    if not interval:
        return
    with _REQUEST_LOCK:
        now = time.monotonic()
        wait = interval - (now - _LAST_REQUEST.get(exchange_id, 0))
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST[exchange_id] = time.monotonic()


def _cache_path(
    symbol: str,
    timeframe: str,
    since_days: int,
    exchange_id: str = "binance",
) -> Path:
    safe = symbol.replace("/", "_").replace(":", "_")
    directory = CACHE_DIR / exchange_id
    directory.mkdir(exist_ok=True, parents=True)
    return directory / f"{safe}_{timeframe}_{since_days}d.parquet"


def top_usdt_symbols(exchange_id: str = "binance", limit: int = 50) -> list[str]:
    """Top USDT spot theo quote volume 24h hiện tại — có survivorship bias."""
    if ccxt is None:
        raise ImportError("Cần cài ccxt: pip install ccxt")

    tickers = getattr(ccxt, exchange_id)({"enableRateLimit": True}).fetch_tickers()
    ranked = []
    for symbol, ticker in tickers.items():
        if not symbol.endswith("/USDT") or ":" in symbol:
            continue
        base = symbol.removesuffix("/USDT")
        if base in STABLE_BASES or base.endswith(LEVERAGED_SUFFIXES):
            continue
        volume = ticker.get("quoteVolume")
        if volume is not None:
            ranked.append((float(volume), symbol))

    symbols = [symbol for _, symbol in sorted(ranked, reverse=True)[:limit]]
    if len(symbols) < limit:
        raise RuntimeError(f"{exchange_id} chỉ trả về {len(symbols)}/{limit} cặp hợp lệ")
    return symbols


def _select_market_cap_universe(
    coins: list[dict],
    markets: dict,
    limit: int,
) -> list[dict]:
    """Chọn coin vốn hóa lớn nhất có spot USDT hoạt động trên sàn."""
    spot_by_base = {}
    for market in markets.values():
        if (
            market.get("spot")
            and market.get("quote") == "USDT"
            and market.get("active") is not False
            and ":" not in market.get("symbol", "")
        ):
            spot_by_base.setdefault(market.get("base"), market["symbol"])

    selected = []
    ranked = sorted(
        coins,
        key=lambda coin: coin.get("market_cap") or 0,
        reverse=True,
    )
    for coin in ranked:
        base = str(coin.get("symbol", "")).upper()
        symbol = spot_by_base.get(base)
        if not symbol or base in STABLE_BASES or base.endswith(LEVERAGED_SUFFIXES):
            continue
        selected.append({
            "rank": len(selected) + 1,
            "market_cap_rank": coin.get("market_cap_rank"),
            "name": coin.get("name", base),
            "base": base,
            "symbol": symbol,
            "market_cap_usd": coin.get("market_cap"),
            "price_usd": coin.get("current_price"),
            "change_24h_pct": coin.get("price_change_percentage_24h"),
        })
        if len(selected) == limit:
            break

    if len(selected) < limit:
        raise RuntimeError(
            f"Chỉ ghép được {len(selected)}/{limit} coin vốn hóa với spot USDT"
        )
    return selected


def top_market_cap_universe(
    exchange_id: str = "okx",
    limit: int = 20,
) -> list[dict]:
    """Top coin theo vốn hóa hiện tại có spot USDT trên sàn.

    CoinGecko cung cấp thứ hạng vốn hóa; ccxt xác nhận cặp spot đang hoạt động.
    Stablecoin bị loại. Đây là universe hiện tại nên có survivorship bias nếu
    dùng để backtest quá khứ.
    """
    if ccxt is None:
        raise ImportError("Cần cài ccxt: pip install ccxt")
    if limit < 1:
        raise ValueError("limit phải lớn hơn 0")

    exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    markets = exchange.load_markets()
    params = urlencode({
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": min(250, max(100, limit * 4)),
        "page": 1,
        "sparkline": "false",
    })
    request = Request(
        f"{COINGECKO_MARKETS_URL}?{params}",
        headers={"User-Agent": "sonic-r-signal-center/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            coins = json.load(response)
    except Exception as exc:
        raise RuntimeError(f"Không tải được vốn hóa CoinGecko: {exc}") from exc

    return _select_market_cap_universe(coins, markets, limit)


def _select_usdt_crypto_swaps(markets: dict) -> list[dict]:
    """Toàn bộ perpetual USDT crypto active, loại stock/commodity tokenized."""
    selected = []
    for market in markets.values():
        if not (
            market.get("swap")
            and market.get("linear")
            and market.get("settle") == "USDT"
            and market.get("active") is not False
            and market.get("info", {}).get("instCategory") == "1"
        ):
            continue
        selected.append({
            "name": market["base"],
            "base": market["base"],
            "symbol": market["symbol"],
            "contract_size": market.get("contractSize") or 1.0,
            "amount_step": market.get("precision", {}).get("amount") or 1.0,
            "min_contracts": (
                market.get("limits", {}).get("amount", {}).get("min")
                or market.get("precision", {}).get("amount")
                or 1.0
            ),
        })

    selected.sort(key=lambda row: row["base"])
    for rank, row in enumerate(selected, 1):
        row["rank"] = rank
    return selected


def okx_usdt_swap_universe() -> list[dict]:
    """Tất cả perpetual USDT crypto đang active trên OKX."""
    if ccxt is None:
        raise ImportError("Cần cài ccxt: pip install ccxt")
    markets = ccxt.okx({"enableRateLimit": True}).load_markets()
    universe = _select_usdt_crypto_swaps(markets)
    if not universe:
        raise RuntimeError("OKX không trả về perpetual USDT crypto nào")
    return universe


def fetch_ohlcv(
    symbol: str,
    timeframe: str = "15m",
    since_days: int = 1095,
    exchange_id: str = "binance",
    exchange=None,
    use_cache: bool = True,
    verbose: bool = True,
    cache_max_age: float | None = 3600,
) -> pd.DataFrame:
    """
    Tải OHLCV, phân trang tự động, cache ra parquet.

    Args:
        since_days: số ngày lịch sử. 1095 = 3 năm.
        cache_max_age: tuổi cache tối đa theo giây; ``None`` dùng snapshot hiện có.
    """
    path = _cache_path(symbol, timeframe, since_days, exchange_id)
    if (
        use_cache
        and path.exists()
        and (
            cache_max_age is None
            or time.time() - path.stat().st_mtime < cache_max_age
        )
    ):
        df = pd.read_parquet(path)
        if verbose:
            print(f"  [cache] {symbol} {timeframe}: {len(df)} nến")
        return df

    if ccxt is None:
        raise ImportError("Cần cài ccxt: pip install ccxt")

    ex = exchange or getattr(ccxt, exchange_id)({"enableRateLimit": True})
    tf = TF_MAP.get(timeframe, timeframe)

    since = ex.milliseconds() - since_days * 24 * 60 * 60 * 1000
    all_rows = []
    fetch_error = None
    limit = 1000 if exchange_id == "binance" else 300

    while True:
        for attempt in range(3):
            try:
                _throttle(exchange_id)
                batch = ex.fetch_ohlcv(symbol, tf, since=since, limit=limit)
                break
            except Exception as e:
                transient = any(
                    marker in str(e).lower()
                    for marker in ("rate limit", "too many", "429", "50011", "timeout")
                )
                if transient and attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                print(f"  [lỗi] {symbol} {timeframe}: {e}")
                fetch_error = e
                batch = []
                break
        if fetch_error is not None:
            break

        if not batch:
            break

        all_rows.extend(batch)
        since = batch[-1][0] + 1

        if len(batch) < limit:
            break
        if since > ex.milliseconds():
            break

        time.sleep(ex.rateLimit / 1000)

    if fetch_error is not None:
        if use_cache and path.exists():
            print(f"  [cache cũ] {symbol} {timeframe}: giữ dữ liệu trước lỗi tải")
            return pd.read_parquet(path)
        return pd.DataFrame()

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    df.to_parquet(path)
    if verbose:
        print(f"  [tải] {symbol} {timeframe}: {len(df)} nến "
              f"({df.index[0].date()} -> {df.index[-1].date()})")
    return df


def load_all_timeframes(
    symbol: str,
    since_days: int = 1095,
    verbose: bool = True,
    exchange_id: str = "binance",
) -> dict:
    """Tải cả 4 khung cho 1 symbol."""
    return {
        tf: fetch_ohlcv(
            symbol, tf, since_days, exchange_id=exchange_id, verbose=verbose
        )
        for tf in TIMEFRAMES
    }


def load_universe(
    symbols=None,
    since_days: int = 1095,
    exchange_id: str = "binance",
) -> dict:
    """Tải toàn bộ universe. Trả về {symbol: {tf: df}}."""
    symbols = symbols or top_usdt_symbols(exchange_id)
    data = {}
    for sym in symbols:
        print(f"\n{sym}")
        try:
            data[sym] = load_all_timeframes(
                sym, since_days, exchange_id=exchange_id
            )
        except Exception as e:
            print(f"  [bỏ qua] {e}")
    return data


def data_quality_check(df: pd.DataFrame, timeframe: str) -> dict:
    """Kiểm tra chất lượng dữ liệu trước khi backtest."""
    if df.empty:
        return {"ok": False, "reason": "rỗng"}

    expected_delta = {
        "15m": pd.Timedelta("15min"),
        "1H": pd.Timedelta("1h"),
        "4H": pd.Timedelta("4h"),
        "1D": pd.Timedelta("1D"),
    }[timeframe]

    gaps = df.index.to_series().diff()
    n_gaps = int((gaps > expected_delta * 1.5).sum())

    invalid = int(
        ((df["high"] < df["low"]) |
         (df["close"] > df["high"]) |
         (df["close"] < df["low"]) |
         (df["open"] > df["high"]) |
         (df["open"] < df["low"])).sum()
    )

    return {
        "ok": invalid == 0,
        "n_bars": len(df),
        "start": str(df.index[0].date()),
        "end": str(df.index[-1].date()),
        "gaps": n_gaps,
        "invalid_bars": invalid,
        "zero_volume_pct": round(100 * (df["volume"] == 0).mean(), 2),
    }


if __name__ == "__main__":
    print("Test tải dữ liệu BTC/USDT...")
    df = fetch_ohlcv("BTC/USDT", "1H", since_days=30)
    if not df.empty:
        print(df.tail())
        print(data_quality_check(df, "1H"))
