"""
Bộ chỉ báo nền tảng cho hệ thống Sonic R + Elliott.

Nguyên tắc quan trọng: MỌI hàm ở đây chỉ được dùng dữ liệu quá khứ.
Không có look-ahead. ZigZag là chỗ dễ sai nhất -> xem hàm zigzag_confirmed.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- EMA / Dragon

def ema(series: pd.Series, period: int) -> pd.Series:
    """EMA chuẩn, khớp với TradingView (adjust=False)."""
    return series.ewm(span=period, adjust=False).mean()


def sonic_r_bands(df: pd.DataFrame, fast: int = 34, slow: int = 89) -> pd.DataFrame:
    """
    Bộ Sonic R gốc:
      - Dragon Band = EMA34 áp lên High / Close / Low
      - Trend line  = EMA89 áp lên Close
    Trả về DataFrame các cột chỉ báo (không sửa df gốc).
    """
    out = pd.DataFrame(index=df.index)
    out["ema_fast_high"] = ema(df["high"], fast)
    out["ema_fast_close"] = ema(df["close"], fast)
    out["ema_fast_low"] = ema(df["low"], fast)
    out["ema_slow"] = ema(df["close"], slow)
    out["ema_200"] = ema(df["close"], 200)
    return out


# ---------------------------------------------------------------- Volatility

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing)."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    ADX — bộ lọc sideway chính của hệ thống.
    Đây là thứ trả lời trực tiếp vấn đề "đoạn sideway anh em cực kì dễ toang".
    """
    high, low = df["high"], df["low"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr_val = atr(df, period)
    alpha = 1 / period

    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=alpha, adjust=False
    ).mean() / atr_val
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=alpha, adjust=False
    ).mean() / atr_val

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=alpha, adjust=False).mean()


def slope(series: pd.Series, lookback: int = 10) -> pd.Series:
    """Độ dốc chuẩn hoá: thay đổi trên mỗi nến, chia cho giá trị hiện tại."""
    return (series - series.shift(lookback)) / (lookback * series.abs())


# ---------------------------------------------------------------- PVSRA

def pva_signals(df: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
    """
    Phân loại volume theo định nghĩa PVA của TAH/qFish.

    - Rising: volume >= 150% trung bình ``lookback`` nến trước.
    - Climax: volume >= 200% trung bình trước, hoặc spread*volume đạt
      mức cao nhất so với ``lookback`` nến trước.

    Đây là dữ liệu bối cảnh PVSRA, không phải điều kiện entry độc lập.
    Trung bình và cực trị đều shift(1) để không tự so nến hiện tại với chính nó.
    """
    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"PVA thiếu cột OHLCV: {sorted(missing)}")
    if lookback < 2:
        raise ValueError("PVA lookback phải >= 2")

    volume = pd.to_numeric(df["volume"], errors="coerce")
    spread = (df["high"] - df["low"]).abs()
    activity = spread * volume
    average_volume = volume.rolling(lookback, min_periods=lookback).mean().shift(1)
    previous_peak = activity.rolling(lookback, min_periods=lookback).max().shift(1)
    volume_ratio = volume / average_volume.replace(0, np.nan)

    out = pd.DataFrame(index=df.index)
    out["volume_ratio"] = volume_ratio
    out["rising"] = (volume_ratio >= 1.5).fillna(False)
    out["climax"] = (
        (volume_ratio >= 2.0) | (activity >= previous_peak)
    ).fillna(False)
    out["direction"] = np.where(
        df["close"] > df["open"],
        "bull",
        np.where(df["close"] < df["open"], "bear", "neutral"),
    )
    out["state"] = "normal"
    out.loc[out["rising"], "state"] = (
        out.loc[out["rising"], "direction"] + "_rising"
    )
    out.loc[out["climax"], "state"] = (
        out.loc[out["climax"], "direction"] + "_climax"
    )
    return out


# ---------------------------------------------------------------- ZigZag / Swing

def zigzag_confirmed(
    df: pd.DataFrame, left: int = 5, right: int = 5
) -> pd.DataFrame:
    """
    Tìm swing high/low bằng fractal, CÓ ĐỘ TRỄ ĐÚNG.

    CỰC KỲ QUAN TRỌNG:
    Một swing high tại nến i chỉ được XÁC NHẬN sau `right` nến nữa.
    Cột `confirmed_at` ghi lại thời điểm ta thực sự BIẾT được swing này.
    Backtest bắt buộc dùng confirmed_at, không được dùng index của swing.
    Đây là lỗi look-ahead phổ biến nhất khi backtest Elliott/ZigZag.

    Trả về DataFrame: [idx, price, kind, confirmed_at]
    """
    high, low = df["high"].values, df["low"].values
    n = len(df)
    pivots = []

    for i in range(left, n - right):
        window_h = high[i - left : i + right + 1]
        window_l = low[i - left : i + right + 1]

        if high[i] == window_h.max() and (window_h == high[i]).sum() == 1:
            pivots.append((i, high[i], "high", i + right))
        elif low[i] == window_l.min() and (window_l == low[i]).sum() == 1:
            pivots.append((i, low[i], "low", i + right))

    if not pivots:
        return pd.DataFrame(columns=["idx", "price", "kind", "confirmed_at"])

    piv = pd.DataFrame(pivots, columns=["idx", "price", "kind", "confirmed_at"])

    # Lọc pivot liên tiếp cùng loại: giữ cái cực đoan hơn
    cleaned = []
    for _, row in piv.iterrows():
        if cleaned and cleaned[-1]["kind"] == row["kind"]:
            prev = cleaned[-1]
            better = (row["kind"] == "high" and row["price"] > prev["price"]) or (
                row["kind"] == "low" and row["price"] < prev["price"]
            )
            if better:
                cleaned[-1] = row.to_dict()
        else:
            cleaned.append(row.to_dict())

    return pd.DataFrame(cleaned)


def dow_structure(pivots: pd.DataFrame, as_of_idx: int) -> str:
    """
    Xác định cấu trúc Dow tại thời điểm as_of_idx.
    CHỈ dùng các pivot đã được xác nhận trước hoặc tại as_of_idx.

    Trả về: 'uptrend' (HH+HL) | 'downtrend' (LL+LH) | 'unclear'
    """
    visible = pivots[pivots["confirmed_at"] <= as_of_idx]
    if len(visible) < 4:
        return "unclear"

    highs = visible[visible["kind"] == "high"]["price"].values
    lows = visible[visible["kind"] == "low"]["price"].values

    if len(highs) < 2 or len(lows) < 2:
        return "unclear"

    hh = highs[-1] > highs[-2]
    hl = lows[-1] > lows[-2]
    ll = lows[-1] < lows[-2]
    lh = highs[-1] < highs[-2]

    if hh and hl:
        return "uptrend"
    if ll and lh:
        return "downtrend"
    return "unclear"


# ---------------------------------------------------------------- Fibonacci

def fib_retracement(swing_low: float, swing_high: float) -> dict:
    """Các mức hồi Fibo cho một sóng đẩy tăng."""
    rng = swing_high - swing_low
    return {
        "0.0": swing_high,
        "0.236": swing_high - 0.236 * rng,
        "0.382": swing_high - 0.382 * rng,
        "0.5": swing_high - 0.5 * rng,
        "0.618": swing_high - 0.618 * rng,
        "0.786": swing_high - 0.786 * rng,
        "1.0": swing_low,
    }


def fib_extension(swing_low: float, swing_high: float, retrace_low: float) -> dict:
    """
    Fibo extension — dùng cho chế độ TP "ăn sóng dài".
    Đo từ đáy sóng đẩy -> đỉnh -> đáy hồi, chiếu lên phía trước.
    """
    rng = swing_high - swing_low
    return {
        "1.0": retrace_low + rng,
        "1.272": retrace_low + 1.272 * rng,
        "1.618": retrace_low + 1.618 * rng,
        "2.0": retrace_low + 2.0 * rng,
        "2.618": retrace_low + 2.618 * rng,
    }


def in_golden_pocket(
    price: float, swing_low: float, swing_high: float,
    lo: float = 0.382, hi: float = 0.618,
) -> bool:
    """
    Kiểm tra giá có nằm trong vùng hồi hợp lệ của sóng đẩy không.
    Đây là proxy Tầng 1 cho Elliott: pullback nông (<38.2%) hoặc
    quá sâu (>61.8%) đều không phải sóng hồi đẹp của wave 2/4.
    """
    rng = swing_high - swing_low
    if rng <= 0:
        return False
    retrace = (swing_high - price) / rng
    return lo <= retrace <= hi


# ---------------------------------------------------------------- Price Action

def bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    o, c = df["open"], df["close"]
    prev_o, prev_c = o.shift(1), c.shift(1)
    return (c > o) & (prev_c < prev_o) & (c > prev_o) & (o < prev_c)


def bullish_pinbar(df: pd.DataFrame, wick_ratio: float = 2.0) -> pd.Series:
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body = (c - o).abs()
    lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l
    upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
    return (lower_wick > wick_ratio * body) & (lower_wick > upper_wick) & (body > 0)


def break_of_structure(df: pd.DataFrame, lookback: int = 3) -> pd.Series:
    """Đóng cửa vượt đỉnh của N nến trước đó."""
    return df["close"] > df["high"].rolling(lookback).max().shift(1)


def pa_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Gộp tất cả tín hiệu Price Action, mỗi loại một cột riêng để phân tích."""
    out = pd.DataFrame(index=df.index)
    out["engulfing"] = bullish_engulfing(df)
    out["pinbar"] = bullish_pinbar(df)
    out["bos"] = break_of_structure(df)
    out["any_pa"] = out[["engulfing", "pinbar", "bos"]].any(axis=1)
    return out
