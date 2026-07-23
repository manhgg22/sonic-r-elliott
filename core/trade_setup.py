"""Setup BUY kỷ luật: Sonic R + breakout + Dow + Value Zone + PA."""

import numpy as np
import pandas as pd

from . import indicators as ind
from .mtf import align_htf_to_ltf
from .pure_sonic import PureSonicConfig, build_pure_signals
from .signals import Config, dow_and_fib_state


BAR_DURATION = {"15m": pd.Timedelta("15min"), "1H": pd.Timedelta("1h")}
FILTER_LABELS = {
    "f_trend": "EMA34 > EMA89",
    "f_breakout": "phá vùng tích lũy",
    "f_dow": "Dow HH/HL",
    "f_value_zone": "hồi Value Zone",
    "f_pa": "engulfing/pinbar",
}
SHORT_FILTER_LABELS = {
    "f_trend": "EMA34 < EMA89",
    "f_breakout": "phá đáy vùng tích lũy",
    "f_dow": "Dow LL/LH",
    "f_value_zone": "hồi Value Zone",
    "f_pa": "bearish engulfing/pinbar",
}


def closed_bars(
    df: pd.DataFrame,
    timeframe: str,
    now: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Loại nến đang chạy; index OHLCV là thời gian mở nến."""
    if timeframe not in BAR_DURATION:
        raise ValueError(f"Khung không hỗ trợ: {timeframe}")
    if df.empty:
        return df
    if now is None:
        now = pd.Timestamp.now(tz="UTC")
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    return df.loc[df.index + BAR_DURATION[timeframe] <= now]


def build_trade_setup_signals(
    entry_df: pd.DataFrame,
    main_df: pd.DataFrame,
) -> pd.DataFrame:
    """Năm điều kiện đúng quan điểm: trend, breakout, Dow, VZ và PA."""
    sig = build_pure_signals(entry_df, main_df, PureSonicConfig())
    dow = dow_and_fib_state(
        main_df,
        Config(zz_left=5, zz_right=5, swing_max_age=100),
    )[["dow"]]
    dow_aligned = align_htf_to_ltf(dow, entry_df.index)
    sig.insert(6, "f_dow", dow_aligned["dow"].eq("uptrend"))
    sig["entry_signal"] &= sig["f_dow"]
    sig.attrs["active_filters"] = list(FILTER_LABELS)
    return sig


def build_short_trade_setup_signals(
    entry_df: pd.DataFrame,
    main_df: pd.DataFrame,
) -> pd.DataFrame:
    """Setup SHORT đối xứng với setup BUY, không thêm indicator."""
    cfg = PureSonicConfig()
    bands = ind.sonic_r_bands(main_df, cfg.ema_fast, cfg.ema_slow)
    high20 = main_df["high"].rolling(cfg.breakout_lookback).max()
    low20 = main_df["low"].rolling(cfg.breakout_lookback).min()
    breakdown = main_df["close"] < low20.shift(1)
    dow = dow_and_fib_state(
        main_df,
        Config(zz_left=5, zz_right=5, swing_max_age=100),
    )[["dow"]]

    main_state = pd.DataFrame(index=main_df.index)
    main_state["trend"] = bands["ema_fast_close"] < bands["ema_slow"]
    main_state["breakout"] = (
        breakdown.rolling(cfg.breakout_valid_bars, min_periods=1)
        .max()
        .fillna(False)
        .astype(bool)
    )
    main_state["dow"] = dow["dow"]
    main_state["vz_fast"] = bands["ema_fast_low"]
    main_state["vz_slow"] = bands["ema_slow"]
    main_state["ext"] = high20 - low20
    main_aligned = align_htf_to_ltf(main_state, entry_df.index)

    o, h, l, c = (
        entry_df["open"], entry_df["high"], entry_df["low"], entry_df["close"]
    )
    body = (c - o).abs()
    upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
    lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l
    engulfing = (
        (c < o) & (c.shift(1) > o.shift(1))
        & (c < o.shift(1)) & (o > c.shift(1))
    )
    pinbar = (upper_wick > 2 * body) & (upper_wick > lower_wick) & (body > 0)
    atr_entry = ind.atr(entry_df, 14)

    sig = pd.DataFrame(index=entry_df.index)
    sig["close"] = c
    sig["high"] = h
    sig["low"] = l
    sig["f_trend"] = main_aligned["trend"].eq(True)
    sig["f_breakout"] = main_aligned["breakout"].eq(True)
    sig["f_dow"] = main_aligned["dow"].eq("downtrend")
    sig["f_value_zone"] = (
        (h >= main_aligned["vz_fast"]) & (c < main_aligned["vz_slow"])
    ).fillna(False)
    sig["f_pa"] = engulfing | pinbar
    sig["entry_signal"] = sig[list(SHORT_FILTER_LABELS)].all(axis=1)
    sig["pa_engulfing"] = engulfing.fillna(False)
    sig["pa_pinbar"] = pinbar.fillna(False)

    entry_high = h.rolling(cfg.sl_lookback).max()
    sl_raw = pd.concat([entry_high, main_aligned["vz_slow"]], axis=1).max(axis=1)
    sig["sl"] = sl_raw + cfg.sl_buffer_atr * atr_entry
    sig["risk"] = sig["sl"] - sig["close"]
    sig["tp_2r"] = sig["close"] - cfg.tp_r_multiple * sig["risk"]
    sig["tp_fib_1618"] = sig["high"] - cfg.tp_fib_1 * main_aligned["ext"]
    sig["tp_fib_2618"] = sig["high"] - cfg.tp_fib_2 * main_aligned["ext"]
    sig.attrs["active_filters"] = list(SHORT_FILTER_LABELS)
    return sig


def latest_trade_setup(
    symbol: str,
    entry_df: pd.DataFrame,
    main_df: pd.DataFrame,
    now: pd.Timestamp | None = None,
    side: str = "LONG",
) -> dict:
    """Trả về trạng thái mới nhất cùng Entry/SL/TP có thể thực thi thủ công."""
    side = side.upper()
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side phải là LONG hoặc SHORT")
    labels = FILTER_LABELS if side == "LONG" else SHORT_FILTER_LABELS
    entry = closed_bars(entry_df, "15m", now)
    if len(entry) < 100:
        raise ValueError(f"{symbol}: chưa đủ dữ liệu để tính setup")
    # Giữ nến H1 cùng giờ làm placeholder; align_htf_to_ltf() shift một nến
    # nên tín hiệu chỉ nhận giá trị của H1 đã đóng liền trước.
    main_cutoff = entry.index[-1].floor("1h")
    main = main_df.loc[main_df.index <= main_cutoff]
    if len(main) < 100:
        raise ValueError(f"{symbol}: chưa đủ dữ liệu để tính setup")
    if main.index[-1] != main_cutoff:
        raise ValueError(f"{symbol}: thiếu nến H1 tại {main_cutoff}")

    sig = (
        build_trade_setup_signals(entry, main)
        if side == "LONG"
        else build_short_trade_setup_signals(entry, main)
    )
    row = sig.iloc[-1]
    flags = {name: bool(row[name]) for name in labels}

    context_ready = flags["f_trend"] and flags["f_breakout"] and flags["f_dow"]
    if all(flags.values()):
        status = "READY"
    elif context_ready and flags["f_value_zone"]:
        status = "WAIT_PA"
    elif context_ready:
        status = "WAIT_PULLBACK"
    else:
        status = "NO_SETUP"

    entry_price = float(row["close"])
    sl = float(row["sl"])
    risk = entry_price - sl if side == "LONG" else sl - entry_price
    risk_valid = np.isfinite(risk) and risk > 0
    if status == "READY" and not risk_valid:
        status = "ERROR"
    actionable = status == "READY"

    tp1 = float(row["tp_fib_1618"])
    tp2 = float(row["tp_fib_2618"])
    if side == "LONG":
        if not np.isfinite(tp1) or tp1 <= entry_price:
            tp1 = entry_price + 1.5 * risk
        if not np.isfinite(tp2) or tp2 <= tp1:
            tp2 = entry_price + 3.0 * risk
        trail_column = "ema_fast_low"
    else:
        if not np.isfinite(tp1) or tp1 >= entry_price:
            tp1 = entry_price - 1.5 * risk
        if not np.isfinite(tp2) or tp2 >= tp1:
            tp2 = entry_price - 3.0 * risk
        trail_column = "ema_fast_high"

    bands = ind.sonic_r_bands(main)
    trail = align_htf_to_ltf(
        bands[[trail_column]], entry.index
    )[trail_column].iloc[-1]
    pa_type = (
        "engulfing" if row["pa_engulfing"]
        else "pinbar" if row["pa_pinbar"]
        else "-"
    )
    missing = [label for name, label in labels.items() if not flags[name]]
    if not risk_valid:
        missing.append("SL không hợp lệ")

    return {
        "symbol": symbol,
        "side": side,
        "status": status,
        "actionable": actionable,
        "signal_time": entry.index[-1] + BAR_DURATION["15m"],
        "bar_open": float(entry["open"].iloc[-1]),
        "bar_high": float(entry["high"].iloc[-1]),
        "bar_low": float(entry["low"].iloc[-1]),
        "bar_close": entry_price,
        "entry": entry_price if actionable else np.nan,
        "sl": sl if actionable else np.nan,
        "tp1": tp1 if actionable else np.nan,
        "tp2": tp2 if actionable else np.nan,
        "tp1_rr": round(abs(tp1 - entry_price) / risk, 2) if actionable else np.nan,
        "tp2_rr": round(abs(tp2 - entry_price) / risk, 2) if actionable else np.nan,
        "trail_h1": float(trail),
        "pa": pa_type,
        "missing": ", ".join(missing) if missing else "-",
        **flags,
    }
