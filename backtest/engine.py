"""
Backtest engine — mô phỏng bar-by-bar.

Ba chế độ thoát lệnh, đúng theo phương pháp:
  fixed_2r      : TP = 2R                          ("TP mặc định 2R")
  sr_level      : TP = kháng cự cũ gần nhất        ("hoặc hỗ trợ kháng cự cũ")
  fib_extension : TP1 1.618 / TP2 2.618 + trailing ("ăn sóng thì dùng fibo gồng dài")

Engine chạy cả ba trên cùng bộ tín hiệu -> so sánh trực tiếp,
trả lời câu hỏi: gồng dài có thật sự tốt hơn chốt 2R không?
"""

from dataclasses import dataclass
from typing import Optional, List
import numpy as np
import pandas as pd


@dataclass
class Costs:
    """Chi phí giao dịch thực tế trên OKX."""
    taker_fee: float = 0.0005      # 0.05%
    slippage: float = 0.0002       # 0.02%

    @property
    def round_trip(self) -> float:
        return 2 * (self.taker_fee + self.slippage)


@dataclass
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    entry_price: float
    sl: float
    tp_mode: str
    size: float
    risk_amount: float
    # kết quả
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    pnl: float = 0.0
    r_multiple: float = 0.0
    mfe_r: float = 0.0             # max favorable excursion
    mae_r: float = 0.0             # max adverse excursion
    bars_held: int = 0
    # bối cảnh khi vào lệnh
    adx: float = np.nan
    retrace_pct: float = np.nan
    pa_type: str = ""
    partial_exits: List = None


def find_resistance(highs: pd.Series, current_idx: int, entry: float,
                    lookback: int = 200) -> Optional[float]:
    """
    Tìm kháng cự cũ gần nhất phía trên giá vào lệnh.
    Dùng cho chế độ TP 'sr_level'.
    """
    start = max(0, current_idx - lookback)
    window = highs.iloc[start:current_idx]
    above = window[window > entry * 1.005]
    if above.empty:
        return None
    return float(above.min())


def run_backtest(
    sig: pd.DataFrame,
    m15: pd.DataFrame,
    symbol: str = "TEST",
    tp_mode: str = "fixed_2r",
    initial_balance: float = 10000.0,
    risk_pct: float = 1.0,
    costs: Costs = None,
    max_bars: int = 500,
    max_concurrent: int = 1,
    trail_ema: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Chạy backtest, trả về DataFrame trade log.

    max_concurrent = 1: mỗi lúc chỉ 1 lệnh (kỷ luật, không nhồi lệnh).
    """
    costs = costs or Costs()
    trades: List[Trade] = []
    balance = initial_balance

    open_trade: Optional[Trade] = None
    open_idx = -1
    remaining_size = 0.0
    partials = []

    high_series = m15["high"]
    highs = high_series.to_numpy()
    lows = m15["low"].to_numpy()
    closes = m15["close"].to_numpy()
    entries = sig["entry_signal"].to_numpy(dtype=bool)
    stops = sig["sl"].to_numpy()
    adx_values = (
        sig["adx"].to_numpy() if "adx" in sig.columns else np.full(len(sig), np.nan)
    )
    retrace_values = (
        sig["retrace_pct"].to_numpy()
        if "retrace_pct" in sig.columns
        else np.full(len(sig), np.nan)
    )
    pa_engulfing = sig["pa_engulfing"].to_numpy()
    pa_pinbar = sig["pa_pinbar"].to_numpy()
    pa_bos = sig["pa_bos"].to_numpy()
    trail_values = trail_ema.to_numpy() if trail_ema is not None else None
    tp1_values = (
        sig["tp_fib_1618"].to_numpy() if tp_mode == "fib_extension" else None
    )
    tp2_values = (
        sig["tp_fib_2618"].to_numpy() if tp_mode == "fib_extension" else None
    )

    for i in range(len(sig)):
        ts = sig.index[i]
        bar_high = highs[i]
        bar_low = lows[i]
        bar_close = closes[i]

        # ---------------- Quản lý lệnh đang mở ----------------
        if open_trade is not None:
            t = open_trade
            bars = i - open_idx
            risk_per_unit = max(t.entry_price - t.sl, 1e-9)

            # MFE/MAE luôn tính theo RISK GỐC lúc vào lệnh.
            # Không dùng risk hiện tại vì SL có thể đã dời về hoà vốn -> chia 0.
            init_risk = t._initial_risk

            fav = (bar_high - t.entry_price) / init_risk
            adv = (bar_low - t.entry_price) / init_risk
            t.mfe_r = max(t.mfe_r, fav)
            t.mae_r = min(t.mae_r, adv)

            exit_price = None
            reason = ""

            # 1. Stop loss luôn kiểm tra trước (giả định bi quan)
            if bar_low <= t.sl:
                exit_price = t.sl
                reason = "SL"

            # 2. Take profit theo từng chế độ
            elif tp_mode == "fixed_2r":
                tp = t.entry_price + 2.0 * risk_per_unit
                if bar_high >= tp:
                    exit_price = tp
                    reason = "TP_2R"

            elif tp_mode == "sr_level":
                tp = getattr(t, "_tp_sr", None)
                if tp and bar_high >= tp:
                    exit_price = tp
                    reason = "TP_SR"

            elif tp_mode == "fib_extension":
                tp1 = getattr(t, "_tp1", None)
                tp2 = getattr(t, "_tp2", None)
                # Chốt từng phần
                if tp1 and bar_high >= tp1 and remaining_size > 0.5 * t.size:
                    pnl_p = (tp1 - t.entry_price) * (0.5 * t.size)
                    pnl_p -= tp1 * (0.5 * t.size) * costs.round_trip
                    balance += pnl_p
                    partials.append(("TP1_1.618", ts, tp1, pnl_p))
                    remaining_size = 0.5 * t.size
                    t.sl = t.entry_price  # dời SL về hoà vốn

                if tp2 and bar_high >= tp2 and 0.2 * t.size < remaining_size <= 0.5 * t.size:
                    pnl_p = (tp2 - t.entry_price) * (0.3 * t.size)
                    pnl_p -= tp2 * (0.3 * t.size) * costs.round_trip
                    balance += pnl_p
                    partials.append(("TP2_2.618", ts, tp2, pnl_p))
                    remaining_size = 0.2 * t.size

                # Runner: trailing theo EMA34_low H1
                if trail_values is not None and remaining_size <= 0.2 * t.size:
                    trail = trail_values[i]
                    if not np.isnan(trail) and bar_close < trail:
                        exit_price = bar_close
                        reason = "TRAIL_EMA"

            # 3. Hết thời gian tối đa
            if exit_price is None and bars >= max_bars:
                exit_price = bar_close
                reason = "TIMEOUT"
            elif exit_price is None and i == len(sig) - 1:
                exit_price = bar_close
                reason = "END_OF_DATA"

            # ---- Đóng lệnh
            if exit_price is not None:
                size_out = remaining_size if remaining_size > 0 else t.size
                gross = (exit_price - t.entry_price) * size_out
                fee = (t.entry_price + exit_price) * size_out * costs.round_trip / 2
                net = gross - fee
                balance += net

                total_pnl = net + sum(p[3] for p in partials)
                t.exit_time = ts
                t.exit_price = exit_price
                t.exit_reason = reason
                t.pnl = total_pnl
                t.r_multiple = total_pnl / t.risk_amount if t.risk_amount else 0
                t.bars_held = bars
                t.partial_exits = partials.copy()

                trades.append(t)
                open_trade = None
                partials = []
                remaining_size = 0.0

        # ---------------- Mở lệnh mới ----------------
        if (
            i < len(sig) - 1
            and open_trade is None
            and entries[i]
        ):
            entry = bar_close
            sl = stops[i]

            if np.isnan(sl) or sl >= entry:
                continue

            risk_per_unit = entry - sl
            # Chỉ áp dụng sàn khoảng SL khi backtest có phí.
            if costs.round_trip > 0 and risk_per_unit < entry * 0.001:
                continue
            risk_amount = balance * risk_pct / 100
            size = risk_amount / risk_per_unit

            t = Trade(
                symbol=symbol,
                entry_time=ts,
                entry_price=entry,
                sl=sl,
                tp_mode=tp_mode,
                size=size,
                risk_amount=risk_amount,
                adx=adx_values[i],
                retrace_pct=retrace_values[i],
                pa_type=(
                    "engulfing" if pa_engulfing[i]
                    else "pinbar" if pa_pinbar[i]
                    else "bos" if pa_bos[i]
                    else "none"
                ),
            )

            # Lưu risk gốc — dùng cho MFE/MAE, không đổi dù SL có dời
            t._initial_risk = risk_per_unit

            # Thiết lập TP theo chế độ
            if tp_mode == "sr_level":
                res = find_resistance(high_series, i, entry)
                # Nếu không có kháng cự rõ ràng -> dùng 2R
                t._tp_sr = res if res else entry + 2 * risk_per_unit
            elif tp_mode == "fib_extension":
                t._tp1 = tp1_values[i]
                t._tp2 = tp2_values[i]
                # Fallback nếu Fibo không hợp lệ
                if np.isnan(t._tp1) or t._tp1 <= entry:
                    t._tp1 = entry + 1.5 * risk_per_unit
                if np.isnan(t._tp2) or t._tp2 <= t._tp1:
                    t._tp2 = entry + 3.0 * risk_per_unit

            open_trade = t
            open_idx = i
            remaining_size = size

    # Chuyển sang DataFrame
    if not trades:
        return pd.DataFrame()

    rows = []
    for t in trades:
        rows.append({
            "symbol": t.symbol,
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "sl": t.sl,
            "tp_mode": t.tp_mode,
            "exit_reason": t.exit_reason,
            "pnl": t.pnl,
            "r_multiple": t.r_multiple,
            "mfe_r": t.mfe_r,
            "mae_r": t.mae_r,
            "bars_held": t.bars_held,
            "adx": t.adx,
            "retrace_pct": t.retrace_pct,
            "pa_type": t.pa_type,
        })
    return pd.DataFrame(rows)
