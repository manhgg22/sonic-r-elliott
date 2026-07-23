"""Regime thị trường từ BTC D1, chỉ dùng dữ liệu đã đóng."""

import pandas as pd

from core import indicators as ind


def regime_btc_ma200(btc_d1: pd.DataFrame) -> pd.Series:
    """Bull khi BTC trên MA200 D1, ngược lại là bear."""
    ma200 = btc_d1["close"].rolling(200, min_periods=200).mean()
    regime = pd.Series("bear", index=btc_d1.index, dtype="object")
    regime[btc_d1["close"] > ma200] = "bull"
    return regime.where(ma200.notna()).shift(1).rename("regime")


def regime_btc_quarterly(btc_d1: pd.DataFrame) -> pd.Series:
    """Bull/bear/sideway theo return 90 ngày trước đó."""
    returns = btc_d1["close"].pct_change(90)
    regime = pd.Series("sideway", index=btc_d1.index, dtype="object")
    regime[returns > 0.20] = "bull"
    regime[returns < -0.20] = "bear"
    return regime.where(returns.notna()).shift(1).rename("regime")


def regime_adx_d1(btc_d1: pd.DataFrame) -> pd.Series:
    """Trending khi ADX(D1) > 25, còn lại là ranging."""
    adx = ind.adx(btc_d1, 14)
    regime = pd.Series("ranging", index=btc_d1.index, dtype="object")
    regime[adx > 25] = "trending"
    return regime.where(adx.notna()).shift(1).rename("regime")


def tag_trades_with_regime(
    trades: pd.DataFrame,
    regime_series: pd.Series,
) -> pd.DataFrame:
    """Gắn regime đã shift tại entry_time; thiếu nhãn là lỗi dữ liệu."""
    if not regime_series.index.is_monotonic_increasing:
        raise ValueError("regime_series phải được sắp xếp tăng dần")
    if regime_series.index.has_duplicates:
        raise ValueError("regime_series không được trùng timestamp")

    tagged = trades.copy()
    if tagged.empty:
        tagged["regime"] = pd.Series(dtype="object")
        return tagged

    entries = pd.DatetimeIndex(pd.to_datetime(tagged["entry_time"], utc=True))
    tagged["regime"] = regime_series.reindex(entries, method="ffill").to_numpy()
    if tagged["regime"].isna().any():
        raise ValueError("Không đủ dữ liệu warmup để gắn regime cho mọi trade")
    return tagged
