"""Sonic R thuần: trend, breakout, Value Zone và Price Action."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind
from .mtf import align_htf_to_ltf


@dataclass
class PureSonicConfig:
    ema_fast: int = 34
    ema_slow: int = 89
    breakout_lookback: int = 20
    breakout_valid_bars: int = 30
    tf_main: str = "1H"
    tf_entry: str = "15m"
    sl_lookback: int = 5
    sl_buffer_atr: float = 0.5
    tp_r_multiple: float = 2.0
    tp_fib_1: float = 1.618
    tp_fib_2: float = 2.618
    use_breakout: bool = True
    use_pa: bool = True


def build_pure_signals(
    entry_df: pd.DataFrame,
    main_df: pd.DataFrame,
    cfg: PureSonicConfig,
) -> pd.DataFrame:
    """Sinh tín hiệu engine-compatible với đúng bốn điều kiện Sonic R."""
    bands = ind.sonic_r_bands(main_df, cfg.ema_fast, cfg.ema_slow)
    high20 = main_df["high"].rolling(cfg.breakout_lookback).max()
    low20 = main_df["low"].rolling(cfg.breakout_lookback).min()
    breakout = main_df["close"] > high20.shift(1)

    main_state = pd.DataFrame(index=main_df.index)
    main_state["trend"] = bands["ema_fast_close"] > bands["ema_slow"]
    main_state["breakout"] = (
        breakout.rolling(cfg.breakout_valid_bars, min_periods=1)
        .max()
        .fillna(False)
        .astype(bool)
    )
    main_state["vz_top"] = bands["ema_fast_high"]
    main_state["vz_bot"] = bands["ema_slow"]
    main_state["swing_low"] = low20
    main_state["swing_high"] = high20
    main_state["ext"] = high20 - low20
    main_aligned = align_htf_to_ltf(main_state, entry_df.index)

    pa = ind.pa_signals(entry_df)
    atr_entry = ind.atr(entry_df, 14)
    sig = pd.DataFrame(index=entry_df.index)
    sig["close"] = entry_df["close"]
    sig["high"] = entry_df["high"]
    sig["low"] = entry_df["low"]
    sig["atr_m15"] = atr_entry

    sig["f_trend"] = main_aligned["trend"].eq(True)
    sig["f_breakout"] = main_aligned["breakout"].eq(True)
    sig["f_value_zone"] = (
        (entry_df["low"] <= main_aligned["vz_top"])
        & (entry_df["close"] > main_aligned["vz_bot"])
    ).fillna(False)
    sig["f_pa"] = pa[["engulfing", "pinbar"]].any(axis=1)

    conditions = [sig["f_trend"], sig["f_value_zone"]]
    if cfg.use_breakout:
        conditions.append(sig["f_breakout"])
    if cfg.use_pa:
        conditions.append(sig["f_pa"])
    sig["entry_signal"] = pd.concat(conditions, axis=1).all(axis=1)

    sig["vz_top"] = main_aligned["vz_top"]
    sig["vz_bot"] = main_aligned["vz_bot"]
    sig["swing_low"] = main_aligned["swing_low"]
    sig["swing_high"] = main_aligned["swing_high"]
    sig["adx"] = np.nan
    sig["retrace_pct"] = np.nan
    sig["pa_engulfing"] = pa["engulfing"].fillna(False)
    sig["pa_pinbar"] = pa["pinbar"].fillna(False)
    sig["pa_bos"] = pa["bos"].fillna(False)

    entry_low = entry_df["low"].rolling(cfg.sl_lookback).min()
    sl_raw = pd.concat([entry_low, main_aligned["vz_bot"]], axis=1).min(axis=1)
    sig["sl"] = sl_raw - cfg.sl_buffer_atr * atr_entry
    sig["risk"] = sig["close"] - sig["sl"]
    sig["tp_2r"] = sig["close"] + cfg.tp_r_multiple * sig["risk"]
    sig["tp_fib_1618"] = sig["low"] + cfg.tp_fib_1 * main_aligned["ext"]
    sig["tp_fib_2618"] = sig["low"] + cfg.tp_fib_2 * main_aligned["ext"]
    return sig
