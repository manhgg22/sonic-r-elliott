"""
Data loader — tải OHLCV từ OKX qua ccxt.

Lưu ý về survivorship bias:
Danh sách TOP10 dưới đây là top market cap tại thời điểm viết code.
Backtest 3 năm bằng danh sách hôm nay = survivorship bias
(ta đang chọn những coin ĐÃ SỐNG SÓT và thành công).
Kết quả sẽ đẹp hơn thực tế. Đây là hạn chế đã biết, phải ghi rõ trong báo cáo.
"""

import time
from pathlib import Path
import pandas as pd

try:
    import ccxt
except ImportError:
    ccxt = None


CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Top market cap có trên OKX (cập nhật thủ công)
TOP10 = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
]

TIMEFRAMES = ["15m", "1H", "4H", "1D"]

# ccxt dùng chữ thường cho OKX
TF_MAP = {"15m": "15m", "1H": "1h", "4H": "4h", "1D": "1d"}


def _cache_path(symbol: str, timeframe: str, since_days: int) -> Path:
    safe = symbol.replace("/", "_")
    return CACHE_DIR / f"{safe}_{timeframe}_{since_days}d.parquet"


def fetch_ohlcv(
    symbol: str,
    timeframe: str = "15m",
    since_days: int = 1095,
    exchange_id: str = "okx",
    use_cache: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Tải OHLCV, phân trang tự động, cache ra parquet.

    Args:
        since_days: số ngày lịch sử. 1095 = 3 năm.
    """
    path = _cache_path(symbol, timeframe, since_days)
    if (
        use_cache
        and path.exists()
        and time.time() - path.stat().st_mtime < 3600
    ):
        df = pd.read_parquet(path)
        if verbose:
            print(f"  [cache] {symbol} {timeframe}: {len(df)} nến")
        return df

    if ccxt is None:
        raise ImportError("Cần cài ccxt: pip install ccxt")

    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    tf = TF_MAP.get(timeframe, timeframe)

    since = ex.milliseconds() - since_days * 24 * 60 * 60 * 1000
    all_rows = []
    limit = 300  # OKX giới hạn

    while True:
        try:
            batch = ex.fetch_ohlcv(symbol, tf, since=since, limit=limit)
        except Exception as e:
            print(f"  [lỗi] {symbol} {timeframe}: {e}")
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


def load_all_timeframes(symbol: str, since_days: int = 1095,
                        verbose: bool = True) -> dict:
    """Tải cả 4 khung cho 1 symbol."""
    return {
        tf: fetch_ohlcv(symbol, tf, since_days, verbose=verbose)
        for tf in TIMEFRAMES
    }


def load_universe(symbols=None, since_days: int = 1095) -> dict:
    """Tải toàn bộ universe. Trả về {symbol: {tf: df}}."""
    symbols = symbols or TOP10
    data = {}
    for sym in symbols:
        print(f"\n{sym}")
        try:
            data[sym] = load_all_timeframes(sym, since_days)
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
