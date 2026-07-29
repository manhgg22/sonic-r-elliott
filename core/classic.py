"""Sonic Classic cho crypto perpetual, tách biệt với strategy hiện có."""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import indicators as ind
from .mtf import align_htf_to_ltf, resample_ohlcv
from .wave import detect_waves


NEW_YORK = ZoneInfo("America/New_York")


@dataclass
class SonicClassicConfig:
    # Indicator — hằng số Sonic gốc.
    ema_fast: int = 34
    ema_slow: int = 89

    # Khung.
    tf_entry: str = "15m"
    tf_main: str = "1H"
    tf_adr: str = "1D"

    # Volatility.
    atr_period: int = 14
    adr_period: int = 14

    # Wave.
    pivot_left: int = 3
    pivot_right: int = 3
    require_leg1_cross: bool = False

    # Entry.
    entry_buffer_atr: float = 0.05
    pending_expiry_bars: int = 4

    # SL.
    sl_buffer_atr: float = 0.5
    sl_max_adr: float | None = 1.0
    sl_min_adr: float = 0.25
    min_risk_price_pct: float = 0.001

    # TP.
    tp_mode: str = "sr_level"
    tp_r: float = 1.0
    sr_lookback_bars: int = 200
    sr_min_distance_pct: float = 0.005

    # PVSRA — chỉ quan sát.
    pva_lookback: int = 10
    pva_rising_mult: float = 1.5
    pva_climax_mult: float = 2.0

    # Phiên.
    session_filter: str = "none"

    # Slope.
    slope_lookback: int = 5

    def __post_init__(self) -> None:
        if self.tp_mode not in {"sr_level", "rdh_rdl", "fixed_r"}:
            raise ValueError("tp_mode phải là sr_level, rdh_rdl hoặc fixed_r")
        if self.session_filter not in {"none", "sonic_ny"}:
            raise ValueError("session_filter phải là none hoặc sonic_ny")
        periods = {
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
            "atr_period": self.atr_period,
            "adr_period": self.adr_period,
            "pivot_left": self.pivot_left,
            "pivot_right": self.pivot_right,
            "pending_expiry_bars": self.pending_expiry_bars,
            "pva_lookback": self.pva_lookback,
            "slope_lookback": self.slope_lookback,
            "sr_lookback_bars": self.sr_lookback_bars,
        }
        if any(value < 1 for value in periods.values()):
            raise ValueError(f"period/count phải >= 1: {periods}")
        nonnegative = {
            "entry_buffer_atr": self.entry_buffer_atr,
            "sl_buffer_atr": self.sl_buffer_atr,
            "sl_min_adr": self.sl_min_adr,
            "min_risk_price_pct": self.min_risk_price_pct,
            "sr_min_distance_pct": self.sr_min_distance_pct,
        }
        if any(value < 0 for value in nonnegative.values()):
            raise ValueError(f"buffer/ngưỡng không được âm: {nonnegative}")
        if self.sl_max_adr is not None and self.sl_max_adr <= self.sl_min_adr:
            raise ValueError("sl_max_adr phải > sl_min_adr hoặc là None")
        if self.tp_r <= 0 or self.pva_rising_mult <= 0 or self.pva_climax_mult <= 0:
            raise ValueError("TP/PVA multiplier phải > 0")


def _sonic_session(index: pd.DatetimeIndex) -> pd.Series:
    localized = index.tz_localize("UTC") if index.tz is None else index
    local = localized.tz_convert(NEW_YORK)
    weekday = local.weekday < 5
    hour = local.hour
    return pd.Series(
        weekday & (((hour >= 1) & (hour < 4)) | ((hour >= 7) & (hour < 11))),
        index=index,
    )


def _utc_day(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    localized = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    return localized.normalize()


def _pva_location_counts(
    entry_df: pd.DataFrame,
    climax: pd.Series,
    window: int = 20,
) -> tuple[pd.Series, pd.Series]:
    """Đếm climax có close ở 1/3 trên/dưới range của cửa sổ hiện tại."""
    highs = entry_df["high"].to_numpy(dtype=float)
    lows = entry_df["low"].to_numpy(dtype=float)
    typical = (
        (entry_df["high"] + entry_df["low"] + entry_df["close"]) / 3
    ).to_numpy(dtype=float)
    flags = climax.to_numpy(dtype=bool)
    at_highs = np.full(len(entry_df), np.nan)
    at_lows = np.full(len(entry_df), np.nan)

    for i in range(len(entry_df)):
        if i + 1 < window:
            continue
        start = i - window + 1
        ceiling = np.nanmax(highs[start:i + 1])
        floor = np.nanmin(lows[start:i + 1])
        width = ceiling - floor
        if not np.isfinite(width) or width <= 0:
            continue
        upper = floor + 2 * width / 3
        lower = floor + width / 3
        window_flags = flags[start:i + 1]
        at_highs[i] = int((window_flags & (typical[start:i + 1] >= upper)).sum())
        at_lows[i] = int((window_flags & (typical[start:i + 1] <= lower)).sum())

    return (
        pd.Series(at_highs, index=entry_df.index),
        pd.Series(at_lows, index=entry_df.index),
    )


def _trigger_events(
    entry_df: pd.DataFrame,
    bands: pd.DataFrame,
    waves: pd.DataFrame,
    side: str,
) -> pd.Series:
    """Chọn đúng một breakout causal cho mỗi WAVE đã xác nhận."""
    events = pd.Series(False, index=entry_df.index)
    used: set[tuple[int, int, int]] = set()

    for i in range(1, len(entry_df)):
        if (
            not bool(waves["wave_valid"].iloc[i])
            or bool(waves["missed_preconfirmation"].iloc[i])
        ):
            continue
        ready = waves["leg3_ready_at"].iloc[i]
        if pd.isna(ready) or i < int(ready):
            continue
        identity = (
            int(waves["wave_start_idx"].iloc[i]),
            int(waves["pivot_2_idx"].iloc[i]),
            int(waves["pivot_3_idx"].iloc[i]),
        )
        if identity in used:
            continue

        if side == "LONG":
            outside = entry_df["close"].iloc[i] > bands["ema_fast_high"].iloc[i]
            was_outside = (
                entry_df["close"].iloc[i - 1] > bands["ema_fast_high"].iloc[i - 1]
            )
        else:
            outside = entry_df["close"].iloc[i] < bands["ema_fast_low"].iloc[i]
            was_outside = (
                entry_df["close"].iloc[i - 1] < bands["ema_fast_low"].iloc[i - 1]
            )
        # Mỗi wave chỉ arm đúng cross-out đầu tiên sau khi được xác nhận.
        if outside and not was_outside:
            events.iloc[i] = True
            used.add(identity)

    return events


def build_classic_signals(
    entry_df: pd.DataFrame,
    main_df: pd.DataFrame,
    daily_df: pd.DataFrame | None = None,
    cfg: SonicClassicConfig | None = None,
    side: str = "LONG",
) -> pd.DataFrame:
    """Ghép context H1, WAVE/trigger M15 và ADR D1 thành signal cho engine."""
    cfg = cfg or SonicClassicConfig()
    side = side.upper()
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side phải là LONG hoặc SHORT")
    if not isinstance(entry_df.index, pd.DatetimeIndex):
        raise ValueError("entry_df phải có DatetimeIndex")
    for name, frame in {
        "entry_df": entry_df,
        "main_df": main_df,
        "daily_df": daily_df,
    }.items():
        if frame is None:
            continue
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise ValueError(f"{name} phải có DatetimeIndex")
        if frame.index.tz is None or str(frame.index.tz) != "UTC":
            raise ValueError(f"{name} index phải timezone-aware UTC")
        if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
            raise ValueError(f"{name} index phải tăng dần và không trùng")
    if daily_df is None:
        daily_df = resample_ohlcv(entry_df, "1D")

    entry_bands = ind.sonic_r_bands(entry_df, cfg.ema_fast, cfg.ema_slow)
    main_bands = ind.sonic_r_bands(main_df, cfg.ema_fast, cfg.ema_slow)
    waves = detect_waves(
        entry_df,
        entry_bands,
        side,
        left=cfg.pivot_left,
        right=cfg.pivot_right,
    )

    main_state = pd.DataFrame(index=main_df.index)
    main_state["dragon_slope"] = ind.slope(
        main_bands["ema_fast_close"], cfg.slope_lookback
    )
    if side == "LONG":
        main_state["f_dragon_slope"] = main_state["dragon_slope"] > 0
        main_state["f_price_above_dragon"] = (
            main_df["close"] > main_bands["ema_fast_high"]
        )
        main_state["f_trend"] = main_df["close"] > main_bands["ema_slow"]
    else:
        main_state["f_dragon_slope"] = main_state["dragon_slope"] < 0
        main_state["f_price_above_dragon"] = (
            main_df["close"] < main_bands["ema_fast_low"]
        )
        main_state["f_trend"] = main_df["close"] < main_bands["ema_slow"]
    main_aligned = align_htf_to_ltf(main_state, entry_df.index)

    daily_state = pd.DataFrame(
        {"adr": ind.adr(daily_df, cfg.adr_period)},
        index=daily_df.index,
    )
    adr_aligned = align_htf_to_ltf(daily_state, entry_df.index)["adr"]
    atr_entry = ind.atr(entry_df, cfg.atr_period)
    pva = ind.pva_signals(
        entry_df,
        cfg.pva_lookback,
        cfg.pva_rising_mult,
        cfg.pva_climax_mult,
    )
    pva_highs, pva_lows = _pva_location_counts(entry_df, pva["climax"])
    trigger_event = _trigger_events(entry_df, entry_bands, waves, side)

    sig = pd.DataFrame(index=entry_df.index)
    sig["side"] = side
    sig["close"] = entry_df["close"]
    sig["high"] = entry_df["high"]
    sig["low"] = entry_df["low"]
    sig["atr_m15"] = atr_entry
    sig["adr"] = adr_aligned
    sig["dragon_slope"] = main_aligned["dragon_slope"]
    sig["f_dragon_slope"] = main_aligned["f_dragon_slope"].eq(True)
    sig["f_price_above_dragon"] = main_aligned["f_price_above_dragon"].eq(True)
    sig["f_trend"] = main_aligned["f_trend"].eq(True)
    sig["f_session"] = (
        True
        if cfg.session_filter == "none"
        else _sonic_session(entry_df.index)
    )
    for column in waves.columns:
        sig[column] = waves[column]
    sig["trigger_event"] = trigger_event
    sig["wave_id"] = waves["wave_id"]
    sig["signal_time"] = pd.Series(
        sig.index.where(trigger_event, pd.NaT),
        index=sig.index,
    )

    direction = 1.0 if side == "LONG" else -1.0
    sig["entry_trigger"] = np.nan
    sig.loc[trigger_event, "entry_trigger"] = (
        entry_df.loc[trigger_event, "high"] + cfg.entry_buffer_atr * atr_entry[trigger_event]
        if side == "LONG"
        else entry_df.loc[trigger_event, "low"] - cfg.entry_buffer_atr * atr_entry[trigger_event]
    )

    pivot_price = pd.Series(np.nan, index=entry_df.index)
    for i in np.flatnonzero(trigger_event.to_numpy()):
        pivot_idx = int(waves["pivot_3_idx"].iloc[i])
        pivot_price.iloc[i] = (
            entry_df["low"].iloc[pivot_idx]
            if side == "LONG"
            else entry_df["high"].iloc[pivot_idx]
        )
    sig["sl_raw"] = pivot_price
    sig["sl"] = np.nan
    sig.loc[trigger_event, "sl"] = (
        pivot_price[trigger_event] - direction * cfg.sl_buffer_atr * atr_entry[trigger_event]
    )
    sig["risk"] = direction * (sig["entry_trigger"] - sig["sl"])

    hard_context = (
        sig["f_dragon_slope"]
        & sig["f_price_above_dragon"]
        & sig["f_trend"]
        & sig["f_session"]
    )
    leg1_ok = (
        sig["leg1_crossed_dragon"]
        if cfg.require_leg1_cross
        else pd.Series(True, index=sig.index)
    )
    candidates = trigger_event & hard_context & leg1_ok
    sig["risk_candidate"] = candidates
    sig["rejected_reason"] = ""
    invalid_risk = candidates & (
        ~np.isfinite(sig["entry_trigger"])
        | ~np.isfinite(sig["sl"])
        | ~np.isfinite(sig["risk"])
        | (sig["risk"] <= 0)
    )
    missing_adr = candidates & ~invalid_risk & (
        ~np.isfinite(sig["adr"]) | (sig["adr"] <= 0)
    )
    too_wide = (
        candidates
        & ~invalid_risk
        & ~missing_adr
        & (
            False
            if cfg.sl_max_adr is None
            else sig["risk"] > cfg.sl_max_adr * sig["adr"]
        )
    )
    too_tight = (
        candidates
        & ~invalid_risk
        & ~missing_adr
        & ~too_wide
        & (sig["risk"] < cfg.sl_min_adr * sig["adr"])
    )
    below_engine_min = (
        candidates
        & ~invalid_risk
        & ~missing_adr
        & ~too_wide
        & ~too_tight
        & (sig["risk"] < sig["entry_trigger"].abs() * cfg.min_risk_price_pct)
    )
    sig.loc[invalid_risk, "rejected_reason"] = "INVALID_LEVELS"
    sig.loc[missing_adr, "rejected_reason"] = "ADR_UNAVAILABLE"
    sig.loc[too_wide, "rejected_reason"] = "SL_TOO_WIDE"
    sig.loc[too_tight, "rejected_reason"] = "SL_TOO_TIGHT"
    sig.loc[below_engine_min, "rejected_reason"] = "SL_BELOW_ENGINE_MIN"

    sig["tp"] = np.nan
    sig["tp_source"] = ""
    utc_days = _utc_day(entry_df.index)
    session_low = entry_df["low"].groupby(utc_days).cummin()
    session_high = entry_df["high"].groupby(utc_days).cummax()
    for i in np.flatnonzero(trigger_event.to_numpy()):
        entry = float(sig["entry_trigger"].iloc[i])
        risk = float(sig["risk"].iloc[i])
        if not np.isfinite(risk) or risk <= 0:
            continue
        fallback = entry + direction * cfg.tp_r * risk
        target = fallback
        source = "fixed_r" if cfg.tp_mode == "fixed_r" else "fallback"
        if cfg.tp_mode == "sr_level":
            level = (
                ind.find_resistance(
                    entry_df["high"],
                    i,
                    entry,
                    cfg.sr_lookback_bars,
                    cfg.sr_min_distance_pct,
                )
                if side == "LONG"
                else ind.find_support(
                    entry_df["low"],
                    i,
                    entry,
                    cfg.sr_lookback_bars,
                    cfg.sr_min_distance_pct,
                )
            )
            if level is not None and direction * (level - entry) > 0:
                target, source = level, "sr_level"
            else:
                source = "fallback_no_sr"
        elif cfg.tp_mode == "rdh_rdl":
            # RDH/RDL phải được chụp tại fill bằng session extrema đã đóng.
            target, source = np.nan, ""
        sig.iat[i, sig.columns.get_loc("tp")] = target
        sig.iat[i, sig.columns.get_loc("tp_source")] = source

    sig["entry_signal"] = (
        candidates
        & sig["rejected_reason"].eq("")
        & (
            True
            if cfg.tp_mode == "rdh_rdl"
            else np.isfinite(sig["tp"])
        )
    )
    sig["tp_r"] = cfg.tp_r

    sig["pva_state"] = pva["state"]
    sig["pva_ratio"] = pva["volume_ratio"]
    sig["pva_rising"] = pva["rising"]
    sig["pva_climax"] = pva["climax"]
    sig["pva_climax_count_20"] = pva["climax"].rolling(
        20, min_periods=20
    ).sum()
    sig["pva_climax_at_highs_20"] = pva_highs
    sig["pva_climax_at_lows_20"] = pva_lows

    # Contract tương thích engine cũ; Classic không dùng PA làm cổng.
    sig["pa_engulfing"] = False
    sig["pa_pinbar"] = False
    sig["pa_bos"] = False
    sig["retrace_pct"] = np.nan
    sig["adx"] = np.nan
    return sig
