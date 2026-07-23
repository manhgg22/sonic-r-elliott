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


def latest_trade_setup(
    symbol: str,
    entry_df: pd.DataFrame,
    main_df: pd.DataFrame,
    now: pd.Timestamp | None = None,
) -> dict:
    """Trả về trạng thái mới nhất cùng Entry/SL/TP có thể thực thi thủ công."""
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

    sig = build_trade_setup_signals(entry, main)
    row = sig.iloc[-1]
    flags = {name: bool(row[name]) for name in FILTER_LABELS}

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
    risk = entry_price - sl
    risk_valid = np.isfinite(risk) and risk > 0
    if status == "READY" and not risk_valid:
        status = "ERROR"
    actionable = status == "READY"

    tp1 = float(row["tp_fib_1618"])
    tp2 = float(row["tp_fib_2618"])
    if not np.isfinite(tp1) or tp1 <= entry_price:
        tp1 = entry_price + 1.5 * risk
    if not np.isfinite(tp2) or tp2 <= tp1:
        tp2 = entry_price + 3.0 * risk

    bands = ind.sonic_r_bands(main)
    trail = align_htf_to_ltf(
        bands[["ema_fast_low"]], entry.index
    )["ema_fast_low"].iloc[-1]
    pa_type = (
        "engulfing" if row["pa_engulfing"]
        else "pinbar" if row["pa_pinbar"]
        else "-"
    )
    missing = [label for name, label in FILTER_LABELS.items() if not flags[name]]
    if not risk_valid:
        missing.append("SL không hợp lệ")

    return {
        "symbol": symbol,
        "status": status,
        "actionable": actionable,
        "signal_time": entry.index[-1] + BAR_DURATION["15m"],
        "entry": entry_price if actionable else np.nan,
        "sl": sl if actionable else np.nan,
        "tp1": tp1 if actionable else np.nan,
        "tp2": tp2 if actionable else np.nan,
        "tp1_rr": round((tp1 - entry_price) / risk, 2) if actionable else np.nan,
        "tp2_rr": round((tp2 - entry_price) / risk, 2) if actionable else np.nan,
        "trail_h1": float(trail) if actionable else np.nan,
        "pa": pa_type,
        "missing": ", ".join(missing) if missing else "-",
        **flags,
    }
