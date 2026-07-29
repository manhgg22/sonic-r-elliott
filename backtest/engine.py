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

from core.indicators import find_resistance, find_support


@dataclass
class Costs:
    """Chi phí giao dịch thực tế trên OKX."""
    taker_fee: float = 0.0005      # 0.05%
    slippage: float = 0.0002       # 0.02%
    funding_rate_8h: float = 0.0001
    funding_series: dict[str, pd.Series] | None = None

    @property
    def round_trip(self) -> float:
        return 2 * (self.taker_fee + self.slippage)


@dataclass
class Trade:
    symbol: str
    side: str
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
    tp: float = np.nan
    tp_source: str = ""
    funding_paid: float = 0.0
    funding_pnl: float = 0.0
    funding_periods: int = 0
    funding_source: str = "none"
    funding_mark_source: str = "m15_close_proxy"


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
    pending_expiry_bars: int = 4,
) -> pd.DataFrame:
    """
    Chạy backtest, trả về DataFrame trade log.

    max_concurrent = 1: mỗi lúc chỉ 1 lệnh (kỷ luật, không nhồi lệnh).
    """
    costs = costs or Costs()
    if len(sig) != len(m15) or not sig.index.equals(m15.index):
        raise ValueError("sig và m15 phải có cùng index và số dòng")
    if (
        not isinstance(m15.index, pd.DatetimeIndex)
        or m15.index.tz is None
        or str(m15.index.tz) != "UTC"
    ):
        raise ValueError("OHLCV index phải timezone-aware UTC")
    if not m15.index.is_monotonic_increasing or m15.index.has_duplicates:
        raise ValueError("OHLCV index phải tăng dần và không trùng")
    trades: List[Trade] = []
    balance = initial_balance

    open_trade: Optional[Trade] = None
    open_idx = -1
    remaining_size = 0.0
    partials = []
    pending_idx: Optional[int] = None

    high_series = m15["high"]
    low_series = m15["low"]
    highs = high_series.to_numpy()
    lows = m15["low"].to_numpy()
    closes = m15["close"].to_numpy()
    entries = sig["entry_signal"].to_numpy(dtype=bool)
    sides = (
        sig["side"].astype(str).str.upper().to_numpy()
        if "side" in sig.columns
        else np.full(len(sig), "LONG", dtype=object)
    )
    invalid_sides = set(sides).difference({"LONG", "SHORT"})
    if invalid_sides:
        raise ValueError(f"side không hợp lệ: {sorted(invalid_sides)}")
    stops = sig["sl"].to_numpy()
    triggers = (
        sig["entry_trigger"].to_numpy()
        if "entry_trigger" in sig.columns
        else np.full(len(sig), np.nan)
    )
    adx_values = (
        sig["adx"].to_numpy() if "adx" in sig.columns else np.full(len(sig), np.nan)
    )
    retrace_values = (
        sig["retrace_pct"].to_numpy()
        if "retrace_pct" in sig.columns
        else np.full(len(sig), np.nan)
    )
    pa_engulfing = (
        sig["pa_engulfing"].to_numpy(dtype=bool)
        if "pa_engulfing" in sig.columns else np.zeros(len(sig), dtype=bool)
    )
    pa_pinbar = (
        sig["pa_pinbar"].to_numpy(dtype=bool)
        if "pa_pinbar" in sig.columns else np.zeros(len(sig), dtype=bool)
    )
    pa_bos = (
        sig["pa_bos"].to_numpy(dtype=bool)
        if "pa_bos" in sig.columns else np.zeros(len(sig), dtype=bool)
    )
    trail_values = trail_ema.to_numpy() if trail_ema is not None else None
    tp1_values = (
        sig["tp_fib_1618"].to_numpy() if tp_mode == "fib_extension" else None
    )
    tp2_values = (
        sig["tp_fib_2618"].to_numpy() if tp_mode == "fib_extension" else None
    )
    signal_tp = (
        sig["tp"].to_numpy(dtype=float)
        if "tp" in sig.columns else np.full(len(sig), np.nan)
    )
    signal_tp_source = (
        sig["tp_source"].fillna("").astype(str).to_numpy()
        if "tp_source" in sig.columns else np.full(len(sig), "", dtype=object)
    )
    adr_values = (
        sig["adr"].to_numpy(dtype=float)
        if "adr" in sig.columns else np.full(len(sig), np.nan)
    )
    tp_r_values = (
        sig["tp_r"].to_numpy(dtype=float)
        if "tp_r" in sig.columns else np.ones(len(sig))
    )

    def direction(side: str) -> float:
        return 1.0 if side == "LONG" else -1.0

    def funding_for(
        trade: Trade,
        exit_time: pd.Timestamp,
        exits: list,
    ) -> tuple[float, int, str]:
        """Trả ``(funding_pnl, periods, source)`` cho khoảng (entry, exit]."""
        start = pd.Timestamp(trade.entry_time)
        end = pd.Timestamp(exit_time)
        if end <= start:
            return 0.0, 0, "none"
        actual = None
        if costs.funding_series and symbol in costs.funding_series:
            actual = costs.funding_series[symbol].copy()
            if (
                not isinstance(actual.index, pd.DatetimeIndex)
                or actual.index.tz is None
                or str(actual.index.tz) != "UTC"
            ):
                raise ValueError("funding series index phải timezone-aware UTC")
            if (
                not actual.index.is_monotonic_increasing
                or actual.index.has_duplicates
                or actual.isna().any()
            ):
                raise ValueError("funding series phải đầy đủ, tăng dần và không trùng")
            expected_through = end.floor("8h")
            if actual.index.max() < expected_through:
                raise ValueError(
                    f"funding series {symbol} thiếu timestamp đến "
                    f"{expected_through}"
                )
            diffs = actual.index.to_series().diff().dropna()
            if len(diffs) >= 2:
                normal_interval = diffs.median()
                if (diffs > 1.5 * normal_interval).any():
                    raise ValueError(
                        f"funding series {symbol} có khoảng trống timestamp"
                    )
            periods = actual.index[(actual.index > start) & (actual.index <= end)]
        else:
            first = start.floor("8h")
            if first <= start:
                first += pd.Timedelta("8h")
            periods = pd.date_range(first, end, freq="8h")
        if len(periods) == 0:
            return 0.0, 0, "none"
        funding_pnl = 0.0
        for funding_time in periods:
            rate = (
                float(actual.loc[funding_time])
                if actual is not None
                else costs.funding_rate_8h
            )

            size_at_time = trade.size
            for partial in exits:
                if pd.Timestamp(partial[1]) < funding_time:
                    if partial[0] == "TP1_1.618":
                        size_at_time -= 0.5 * trade.size
                    elif partial[0] == "TP2_2.618":
                        size_at_time -= 0.3 * trade.size
            if size_at_time <= 0:
                continue
            # Proxy mark dùng close cuối cùng có timestamp nghiêm ngặt < kỳ funding.
            price_pos = m15.index.searchsorted(funding_time, side="left") - 1
            mark = (
                float(closes[price_pos])
                if price_pos >= 0
                else trade.entry_price
            )
            funding_pnl += (
                -direction(trade.side) * rate * mark * size_at_time
            )
        return (
            funding_pnl,
            len(periods),
            "real" if actual is not None else "fallback_8h",
        )

    def make_trade(signal_idx: int, entry_idx: int, entry: float):
        sl = stops[signal_idx]
        side = sides[signal_idx]
        trade_direction = direction(side)
        if np.isnan(sl) or trade_direction * (entry - sl) <= 0:
            return None
        risk_per_unit = trade_direction * (entry - sl)
        if costs.round_trip > 0 and risk_per_unit < entry * 0.001:
            return None
        risk_amount = balance * risk_pct / 100
        size = risk_amount / risk_per_unit
        trade = Trade(
            symbol=symbol,
            side=side,
            entry_time=sig.index[entry_idx],
            entry_price=entry,
            sl=sl,
            tp_mode=tp_mode,
            size=size,
            risk_amount=risk_amount,
            adx=adx_values[signal_idx],
            retrace_pct=retrace_values[signal_idx],
            pa_type=(
                "engulfing" if pa_engulfing[signal_idx]
                else "pinbar" if pa_pinbar[signal_idx]
                else "bos" if pa_bos[signal_idx]
                else "none"
            ),
        )
        trade._initial_risk = risk_per_unit
        if tp_mode == "sr_level":
            if np.isfinite(signal_tp[signal_idx]):
                trade._tp_sr = signal_tp[signal_idx]
                trade.tp_source = signal_tp_source[signal_idx]
            else:
                level = (
                    find_resistance(high_series, signal_idx, entry)
                    if side == "LONG"
                    else find_support(low_series, signal_idx, entry)
                )
                trade._tp_sr = (
                    level if level is not None
                    else entry + trade_direction * 2 * risk_per_unit
                )
                trade.tp_source = "sr_level" if level is not None else "fallback"
            trade.tp = trade._tp_sr
        elif tp_mode == "rdh_rdl":
            entry_time = m15.index[entry_idx]
            day_start = entry_time.normalize()
            history = m15.loc[
                (m15.index >= day_start) & (m15.index < entry_time)
            ]
            adr_value = adr_values[signal_idx]
            level = np.nan
            if not history.empty and np.isfinite(adr_value):
                level = (
                    float(history["low"].min()) + adr_value
                    if side == "LONG"
                    else float(history["high"].max()) - adr_value
                )
            if np.isfinite(level) and trade_direction * (level - entry) > 0:
                trade._tp_signal = level
                trade.tp_source = "rdh" if side == "LONG" else "rdl"
            else:
                trade._tp_signal = (
                    entry + trade_direction * tp_r_values[signal_idx] * risk_per_unit
                )
                trade.tp_source = "fallback_invalid_rdh_rdl"
            trade.tp = trade._tp_signal
        elif tp_mode in {"fixed_r", "signal"}:
            if not np.isfinite(signal_tp[signal_idx]):
                return None
            trade._tp_signal = signal_tp[signal_idx]
            trade.tp = trade._tp_signal
            trade.tp_source = signal_tp_source[signal_idx] or tp_mode
        elif tp_mode == "fib_extension":
            trade._tp1 = tp1_values[signal_idx]
            trade._tp2 = tp2_values[signal_idx]
            if np.isnan(trade._tp1) or trade._tp1 <= entry:
                trade._tp1 = entry + 1.5 * risk_per_unit
            if np.isnan(trade._tp2) or trade._tp2 <= trade._tp1:
                trade._tp2 = entry + 3.0 * risk_per_unit
        return trade

    for i in range(len(sig)):
        ts = sig.index[i]
        bar_high = highs[i]
        bar_low = lows[i]
        bar_close = closes[i]
        filled_pending_this_bar = False

        # ---------------- Quản lý lệnh đang mở ----------------
        if open_trade is not None:
            t = open_trade
            trade_direction = direction(t.side)
            bars = i - open_idx
            risk_per_unit = max(
                trade_direction * (t.entry_price - t.sl), 1e-9
            )

            # MFE/MAE luôn tính theo RISK GỐC lúc vào lệnh.
            # Không dùng risk hiện tại vì SL có thể đã dời về hoà vốn -> chia 0.
            init_risk = t._initial_risk

            fav = (
                (bar_high - t.entry_price) / init_risk
                if t.side == "LONG"
                else (t.entry_price - bar_low) / init_risk
            )
            adv = (
                (bar_low - t.entry_price) / init_risk
                if t.side == "LONG"
                else (t.entry_price - bar_high) / init_risk
            )
            t.mfe_r = max(t.mfe_r, fav)
            t.mae_r = min(t.mae_r, adv)

            exit_price = None
            reason = ""

            # 1. Stop loss luôn kiểm tra trước (giả định bi quan)
            if (
                (t.side == "LONG" and bar_low <= t.sl)
                or (t.side == "SHORT" and bar_high >= t.sl)
            ):
                exit_price = t.sl
                reason = "SL"

            # 2. Take profit theo từng chế độ
            elif tp_mode == "fixed_2r":
                tp = t.entry_price + trade_direction * 2.0 * risk_per_unit
                if (
                    (t.side == "LONG" and bar_high >= tp)
                    or (t.side == "SHORT" and bar_low <= tp)
                ):
                    exit_price = tp
                    reason = "TP_2R"

            elif tp_mode == "sr_level":
                tp = getattr(t, "_tp_sr", None)
                if tp and (
                    (t.side == "LONG" and bar_high >= tp)
                    or (t.side == "SHORT" and bar_low <= tp)
                ):
                    exit_price = tp
                    reason = "TP_SR"

            elif tp_mode in {"fixed_r", "rdh_rdl", "signal"}:
                tp = getattr(t, "_tp_signal", None)
                if tp and (
                    (t.side == "LONG" and bar_high >= tp)
                    or (t.side == "SHORT" and bar_low <= tp)
                ):
                    exit_price = tp
                    reason = f"TP_{t.tp_source.upper()}"

            elif tp_mode == "fib_extension":
                tp1 = getattr(t, "_tp1", None)
                tp2 = getattr(t, "_tp2", None)
                # Chốt từng phần
                hit_tp1 = (
                    (t.side == "LONG" and bar_high >= tp1)
                    or (t.side == "SHORT" and bar_low <= tp1)
                ) if tp1 else False
                if hit_tp1 and remaining_size > 0.5 * t.size:
                    pnl_p = trade_direction * (tp1 - t.entry_price) * (0.5 * t.size)
                    pnl_p -= tp1 * (0.5 * t.size) * costs.round_trip
                    balance += pnl_p
                    partials.append(("TP1_1.618", ts, tp1, pnl_p))
                    remaining_size = 0.5 * t.size
                    t.sl = t.entry_price  # dời SL về hoà vốn

                hit_tp2 = (
                    (t.side == "LONG" and bar_high >= tp2)
                    or (t.side == "SHORT" and bar_low <= tp2)
                ) if tp2 else False
                if hit_tp2 and 0.2 * t.size < remaining_size <= 0.5 * t.size:
                    pnl_p = trade_direction * (tp2 - t.entry_price) * (0.3 * t.size)
                    pnl_p -= tp2 * (0.3 * t.size) * costs.round_trip
                    balance += pnl_p
                    partials.append(("TP2_2.618", ts, tp2, pnl_p))
                    remaining_size = 0.2 * t.size

                # Runner: trailing theo EMA34_low H1
                if trail_values is not None and remaining_size <= 0.2 * t.size:
                    trail = trail_values[i]
                    if not np.isnan(trail) and (
                        (t.side == "LONG" and bar_close < trail)
                        or (t.side == "SHORT" and bar_close > trail)
                    ):
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
                gross = trade_direction * (exit_price - t.entry_price) * size_out
                fee = (t.entry_price + exit_price) * size_out * costs.round_trip / 2
                funding_pnl, funding_periods, funding_source = funding_for(
                    t, ts, partials
                )
                net = gross - fee + funding_pnl
                balance += net

                total_pnl = net + sum(p[3] for p in partials)
                t.exit_time = ts
                t.exit_price = exit_price
                t.exit_reason = reason
                t.pnl = total_pnl
                t.r_multiple = total_pnl / t.risk_amount if t.risk_amount else 0
                t.bars_held = bars
                t.partial_exits = partials.copy()
                t.funding_paid = -funding_pnl
                t.funding_pnl = funding_pnl
                t.funding_periods = funding_periods
                t.funding_source = funding_source

                trades.append(t)
                open_trade = None
                partials = []
                remaining_size = 0.0

        # Stop-entry chỉ có hiệu lực từ nến kế tiếp. Nếu OHLC cùng nến fill
        # cũng chạm SL, ghi nhận SL trước để giữ giả định bảo thủ.
        if pending_idx is not None and open_trade is None:
            if i > pending_idx + pending_expiry_bars:
                pending_idx = None
            elif i > pending_idx and (
                (sides[pending_idx] == "LONG" and bar_high >= triggers[pending_idx])
                or (sides[pending_idx] == "SHORT" and bar_low <= triggers[pending_idx])
            ):
                signal_idx = pending_idx
                pending_idx = None
                filled_pending_this_bar = True
                trade = make_trade(
                    signal_idx, i, float(triggers[signal_idx])
                )
                if trade is not None:
                    open_trade = trade
                    open_idx = i
                    remaining_size = trade.size
                    init_risk = trade._initial_risk
                    trade.mfe_r = max(
                        trade.mfe_r,
                        (
                            (bar_high - trade.entry_price) / init_risk
                            if trade.side == "LONG"
                            else (trade.entry_price - bar_low) / init_risk
                        ),
                    )
                    trade.mae_r = min(
                        trade.mae_r,
                        (
                            (bar_low - trade.entry_price) / init_risk
                            if trade.side == "LONG"
                            else (trade.entry_price - bar_high) / init_risk
                        ),
                    )
                    if (
                        (trade.side == "LONG" and bar_low <= trade.sl)
                        or (trade.side == "SHORT" and bar_high >= trade.sl)
                    ):
                        trade_direction = direction(trade.side)
                        gross = trade_direction * (
                            trade.sl - trade.entry_price
                        ) * trade.size
                        fee = (
                            (trade.entry_price + trade.sl)
                            * trade.size * costs.round_trip / 2
                        )
                        (
                            funding_pnl,
                            funding_periods,
                            funding_source,
                        ) = funding_for(trade, ts, [])
                        net = gross - fee + funding_pnl
                        balance += net
                        trade.exit_time = ts
                        trade.exit_price = trade.sl
                        trade.exit_reason = "SL_SAME_BAR"
                        trade.pnl = net
                        trade.r_multiple = (
                            net / trade.risk_amount
                            if trade.risk_amount else 0
                        )
                        trade.bars_held = 0
                        trade.partial_exits = []
                        trade.funding_paid = -funding_pnl
                        trade.funding_pnl = funding_pnl
                        trade.funding_periods = funding_periods
                        trade.funding_source = funding_source
                        trades.append(trade)
                        open_trade = None
                        remaining_size = 0.0
                    elif i == len(sig) - 1:
                        trade_direction = direction(trade.side)
                        gross = trade_direction * (
                            bar_close - trade.entry_price
                        ) * trade.size
                        fee = (
                            (trade.entry_price + bar_close)
                            * trade.size * costs.round_trip / 2
                        )
                        (
                            funding_pnl,
                            funding_periods,
                            funding_source,
                        ) = funding_for(trade, ts, [])
                        net = gross - fee + funding_pnl
                        balance += net
                        trade.exit_time = ts
                        trade.exit_price = bar_close
                        trade.exit_reason = "END_OF_DATA"
                        trade.pnl = net
                        trade.r_multiple = (
                            net / trade.risk_amount
                            if trade.risk_amount else 0
                        )
                        trade.bars_held = 0
                        trade.partial_exits = []
                        trade.funding_paid = -funding_pnl
                        trade.funding_pnl = funding_pnl
                        trade.funding_periods = funding_periods
                        trade.funding_source = funding_source
                        trades.append(trade)
                        open_trade = None
                        remaining_size = 0.0

        # ---------------- Mở lệnh mới ----------------
        if (
            i < len(sig) - 1
            and open_trade is None
            and entries[i]
            and not filled_pending_this_bar
        ):
            if np.isfinite(triggers[i]):
                if pending_idx is None:
                    pending_idx = i
            else:
                trade = make_trade(i, i, bar_close)
                if trade is not None:
                    open_trade = trade
                    open_idx = i
                    remaining_size = trade.size

    # Chuyển sang DataFrame
    if not trades:
        return pd.DataFrame()

    rows = []
    for t in trades:
        rows.append({
            "symbol": t.symbol,
            "side": t.side,
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "sl": t.sl,
            "tp": t.tp,
            "tp_source": t.tp_source,
            "tp_mode": t.tp_mode,
            "exit_reason": t.exit_reason,
            "pnl": t.pnl,
            "r_multiple": t.r_multiple,
            "risk_amount": t.risk_amount,
            "mfe_r": t.mfe_r,
            "mae_r": t.mae_r,
            "bars_held": t.bars_held,
            "funding_paid": t.funding_paid,
            "funding_pnl": t.funding_pnl,
            "funding_periods": t.funding_periods,
            "funding_source": t.funding_source,
            "funding_mark_source": t.funding_mark_source,
            "adx": t.adx,
            "retrace_pct": t.retrace_pct,
            "pa_type": t.pa_type,
        })
    return pd.DataFrame(rows)
