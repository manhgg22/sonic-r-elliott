"""
Signal Engine — dịch phương pháp Sonic R + Dow + PA thành điều kiện số học.

  Tầng 1  "H4 giá nằm trên 34-89"        -> nền xu hướng (D1 tham khảo)
  Tầng 2  "H1 EMA34 trên EMA89"          -> sóng chính
          "sideway cực kì dễ toang"      -> ADX + separation filter
          "dùng Dow"                     -> HH + HL bắt buộc
  Tầng 3  "hồi về vùng giá trị"          -> M15 chạm Value Zone
          "PA đẹp"                       -> engulfing / pinbar / BOS
  TP      Fibo extension                 -> "ăn sóng dài"

Mỗi filter được bật/tắt độc lập để chạy ablation test.
"""

from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

from . import indicators as ind
from .mtf import align_htf_to_ltf


@dataclass
class Config:
    """Toàn bộ tham số hệ thống. Chỉnh được từ dashboard."""

    # EMA
    ema_fast: int = 34
    ema_slow: int = 89

    # Tầng 2 — sóng chính H1
    cross_mode: str = "state"        # 'state' | 'event'
    cross_valid_bars: int = 50       # cú cắt còn hiệu lực bao lâu
    adx_period: int = 14
    adx_min: float = 18.0            # chống sideway
    separation_min: float = 0.35     # |EMA34-EMA89| / ATR
    slope_lookback: int = 10

    # Vùng hồi Fibo tùy chọn cho entry
    fib_lo: float = 0.30
    fib_hi: float = 0.75

    # ZigZag
    zz_left: int = 5
    zz_right: int = 5
    swing_max_age: int = 200        # nến H1

    # Tầng 3 — vào lệnh M15
    value_zone_source: str = "h1"    # 'h1' hoặc 'm15'
    require_pa: bool = True
    pa_patterns: tuple[str, ...] = ("engulfing", "pinbar", "bos")

    # Risk
    atr_period: int = 14
    sl_lookback: int = 5
    sl_buffer_atr: float = 0.5
    risk_pct: float = 1.0

    # TP
    tp_mode: str = "fixed_2r"        # 'fixed_2r' | 'sr_level' | 'fib_extension'
    tp_r_multiple: float = 2.0
    tp_fib_1: float = 1.618
    tp_fib_2: float = 2.618

    # Entry chuẩn: H4 + H1 + Dow + Value Zone + PA. D1/Fibo chỉ để ablation.
    use_d1_filter: bool = False
    use_h4_filter: bool = True
    use_cross_filter: bool = True
    use_adx_filter: bool = True
    use_separation_filter: bool = True
    use_dow_filter: bool = True
    use_fib_filter: bool = False

    @classmethod
    def baseline_sampling(cls) -> "Config":
        """Preset lỏng chỉ để lấy mẫu khi debug, không phải phương pháp thật."""
        return cls(
            use_d1_filter=False,
            use_h4_filter=False,
            use_separation_filter=False,
            use_dow_filter=False,
            use_fib_filter=False,
        )

    def to_dict(self):
        return asdict(self)


# ------------------------------------------------------------------ Tầng 1

def base_trend_ok(df_htf: pd.DataFrame, cfg: Config) -> pd.Series:
    """
    "D1/H4 giá nằm trên 34-89"

    Điều kiện:
      - close > EMA34_low   (giá nằm trên Dragon Band)
      - EMA34_low > EMA89   (Dragon nằm trên trend line)
    """
    bands = ind.sonic_r_bands(df_htf, cfg.ema_fast, cfg.ema_slow)
    price_above = df_htf["close"] > bands["ema_fast_low"]
    dragon_above = bands["ema_fast_low"] > bands["ema_slow"]
    return (price_above & dragon_above).rename("base_ok")


# ------------------------------------------------------------------ Tầng 2

def main_wave_filters(df_h1: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    Toàn bộ bộ lọc trên khung sóng chính H1.
    Trả về DataFrame, mỗi filter một cột -> phục vụ ablation test.
    """
    bands = ind.sonic_r_bands(df_h1, cfg.ema_fast, cfg.ema_slow)
    atr_h1 = ind.atr(df_h1, cfg.atr_period)
    adx_h1 = ind.adx(df_h1, cfg.adx_period)

    out = pd.DataFrame(index=df_h1.index)

    # --- "EMA34 cắt lên EMA89 -> xu hướng tăng được xác nhận"
    above = bands["ema_fast_close"] > bands["ema_slow"]
    if cfg.cross_mode == "state":
        out["cross_fresh"] = above
    elif cfg.cross_mode == "event":
        crossed_up = above & (~above.shift(1, fill_value=False))
        bars_since = pd.Series(np.nan, index=df_h1.index)
        last_cross = -10**9
        for i in range(len(df_h1)):
            if crossed_up.iloc[i]:
                last_cross = i
            bars_since.iloc[i] = i - last_cross
        out["cross_fresh"] = (bars_since <= cfg.cross_valid_bars) & above
    else:
        raise ValueError("cross_mode phải là 'state' hoặc 'event'")

    # --- "sideway anh em cực kì dễ toang" -> hai lớp chống sideway
    out["adx_ok"] = adx_h1 > cfg.adx_min
    separation = (bands["ema_fast_close"] - bands["ema_slow"]).abs() / atr_h1
    out["separation_ok"] = separation > cfg.separation_min
    out["slope_ok"] = ind.slope(bands["ema_slow"], cfg.slope_lookback) > 0

    # --- Giá trị thô để tầng dưới dùng
    out["ema_fast_high"] = bands["ema_fast_high"]
    out["ema_fast_low"] = bands["ema_fast_low"]
    out["ema_slow"] = bands["ema_slow"]
    out["atr"] = atr_h1
    out["adx"] = adx_h1
    out["separation"] = separation

    return out


def dow_and_fib_state(df_h1: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    "dùng Dow" + proxy Elliott Tầng 1.

    Với mỗi nến H1, tính:
      - cấu trúc Dow tại thời điểm đó (chỉ dùng pivot ĐÃ xác nhận)
      - swing đẩy gần nhất (low -> high) để đo Fibo
    """
    pivots = ind.zigzag_confirmed(df_h1, cfg.zz_left, cfg.zz_right)
    out = pd.DataFrame(index=df_h1.index)
    out["dow"] = "unclear"
    out["swing_low"] = np.nan
    out["swing_high"] = np.nan

    if pivots.empty:
        return out

    pivot_rows = list(pivots.itertuples(index=False))
    visible, highs, lows = [], [], []
    next_pivot = 0

    for i in range(len(df_h1)):
        while (
            next_pivot < len(pivot_rows)
            and pivot_rows[next_pivot].confirmed_at <= i
        ):
            pivot = pivot_rows[next_pivot]
            visible.append(pivot)
            (highs if pivot.kind == "high" else lows).append(pivot.price)
            next_pivot += 1

        if len(visible) < 3:
            continue

        if len(highs) >= 2 and len(lows) >= 2:
            if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                out.iat[i, 0] = "uptrend"
            elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                out.iat[i, 0] = "downtrend"

        # Swing đẩy gần nhất: cặp low -> high liền kề cuối cùng
        recent = visible[-6:]
        last_high = next((p for p in reversed(recent) if p.kind == "high"), None)
        if last_high is None:
            continue
        last_low = next(
            (p for p in reversed(recent) if p.kind == "low" and p.idx < last_high.idx),
            None,
        )
        if last_low is None:
            continue

        current_close = df_h1["close"].iloc[i]
        if i - last_high.idx > cfg.swing_max_age:
            continue
        if current_close < last_low.price:
            continue
        if current_close > last_high.price:
            continue

        out.iat[i, 1] = last_low.price
        out.iat[i, 2] = last_high.price

    return out


# ------------------------------------------------------------------ Tầng 3

def build_signals(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
    d1: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """
    Gộp H4, H1, Dow, Value Zone và PA để sinh tín hiệu entry trên M15.

    D1 và vùng hồi Fibo được tính để tham khảo/ablation nhưng mặc định không lọc
    entry. Swing vẫn luôn được tính vì TP Fibo extension phụ thuộc vào nó.

    Trả về DataFrame index=M15 với:
      - từng cột filter (để ablation)
      - cột entry_signal cuối cùng
      - các mức SL/TP đề xuất
    """
    # --- Tầng 1: nền H4; D1 tham khảo, ghép xuống M15 (đã shift chống look-ahead)
    d1_ok = base_trend_ok(d1, cfg).to_frame()
    h4_ok = base_trend_ok(h4, cfg).to_frame()
    d1_al = align_htf_to_ltf(d1_ok, m15.index)
    h4_al = align_htf_to_ltf(h4_ok, m15.index)

    # --- Tầng 2: H1
    h1_filters = main_wave_filters(h1, cfg)
    h1_struct = dow_and_fib_state(h1, cfg)
    h1_all = pd.concat([h1_filters, h1_struct], axis=1)
    h1_al = align_htf_to_ltf(h1_all, m15.index)

    # --- Tầng 3: M15
    pa = ind.pa_signals(m15)
    atr_m15 = ind.atr(m15, cfg.atr_period)

    sig = pd.DataFrame(index=m15.index)
    sig["close"] = m15["close"]
    sig["high"] = m15["high"]
    sig["low"] = m15["low"]
    sig["atr_m15"] = atr_m15

    # Từng filter -> cột riêng
    sig["f_d1"] = d1_al["base_ok"].eq(True)
    sig["f_h4"] = h4_al["base_ok"].eq(True)
    sig["f_cross"] = h1_al["cross_fresh"].eq(True)
    sig["f_adx"] = h1_al["adx_ok"].eq(True)
    sig["f_sep"] = h1_al["separation_ok"].eq(True)
    sig["f_dow"] = (h1_al["dow"] == "uptrend").fillna(False)

    # "hồi về vùng giá trị" — Value Zone lấy từ H1
    vz_top = h1_al["ema_fast_high"]
    vz_bot = h1_al["ema_slow"]
    sig["vz_top"] = vz_top
    sig["vz_bot"] = vz_bot
    touched = (m15["low"] <= vz_top) & (m15["close"] > vz_bot)
    sig["f_value_zone"] = touched.fillna(False)

    # Elliott Tầng 1 — pullback nằm trong vùng Fibo hợp lệ
    sl_, sh_ = h1_al["swing_low"], h1_al["swing_high"]
    rng = sh_ - sl_
    retrace = (sh_ - m15["close"]) / rng.replace(0, np.nan)
    # H1 quyết định swing; M15 chỉ vô hiệu giá trị đã phá biên ngay tại nến entry.
    retrace = retrace.where(retrace.between(0, 1))
    sig["retrace_pct"] = retrace
    sig["f_fib"] = ((retrace >= cfg.fib_lo) & (retrace <= cfg.fib_hi)).fillna(False)
    sig["swing_low"] = sl_
    sig["swing_high"] = sh_

    # Bối cảnh H1 — cần cho phân tích sideway vs trending sau backtest
    sig["adx"] = h1_al["adx"]
    sig["separation"] = h1_al["separation"]
    sig["dow_state"] = h1_al["dow"]

    # Price Action
    sig["pa_engulfing"] = pa["engulfing"].fillna(False)
    sig["pa_pinbar"] = pa["pinbar"].fillna(False)
    sig["pa_bos"] = pa["bos"].fillna(False)
    sig["f_pa"] = sig[
        [f"pa_{pattern}" for pattern in cfg.pa_patterns]
    ].any(axis=1)

    # --- Gộp theo công tắc bật/tắt
    conds = [sig["f_value_zone"]]
    active_filters = ["f_value_zone"]
    if cfg.use_d1_filter:
        conds.append(sig["f_d1"])
        active_filters.append("f_d1")
    if cfg.use_h4_filter:
        conds.append(sig["f_h4"])
        active_filters.append("f_h4")
    if cfg.use_cross_filter:
        conds.append(sig["f_cross"])
        active_filters.append("f_cross")
    if cfg.use_adx_filter:
        conds.append(sig["f_adx"])
        active_filters.append("f_adx")
    if cfg.use_separation_filter:
        conds.append(sig["f_sep"])
        active_filters.append("f_sep")
    if cfg.use_dow_filter:
        conds.append(sig["f_dow"])
        active_filters.append("f_dow")
    if cfg.use_fib_filter:
        conds.append(sig["f_fib"])
        active_filters.append("f_fib")
    if cfg.require_pa:
        conds.append(sig["f_pa"])
        active_filters.append("f_pa")

    combined = conds[0]
    for c in conds[1:]:
        combined = combined & c
    sig["entry_signal"] = combined
    sig.attrs["active_filters"] = active_filters

    # --- Mức SL/TP
    swing_low_m15 = m15["low"].rolling(cfg.sl_lookback).min()
    sl_raw = pd.concat([swing_low_m15, vz_bot], axis=1).min(axis=1)
    sig["sl"] = sl_raw - cfg.sl_buffer_atr * atr_m15
    sig["risk"] = sig["close"] - sig["sl"]
    sig["tp_2r"] = sig["close"] + cfg.tp_r_multiple * sig["risk"]

    # TP theo Fibo extension — chế độ "ăn sóng dài"
    ext_range = sig["swing_high"] - sig["swing_low"]
    sig["tp_fib_1618"] = sig["low"] + cfg.tp_fib_1 * ext_range
    sig["tp_fib_2618"] = sig["low"] + cfg.tp_fib_2 * ext_range

    return sig
