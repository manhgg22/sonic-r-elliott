"""
Kiểm chứng core logic trước khi tin vào bất kỳ con số backtest nào.

Test quan trọng nhất: LOOK-AHEAD.
Nếu test này fail, mọi kết quả backtest đều vô nghĩa.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

from core import indicators as ind
from core.mtf import align_htf_to_ltf, verify_no_lookahead, resample_ohlcv
from core.signals import Config, build_signals
from backtest.engine import Costs, run_backtest
from backtest.metrics import basic_metrics, frequency_check


def make_synthetic(n=6000, seed=42, start="2024-01-01"):
    """Tạo chuỗi giá M15 tổng hợp: có trend, có sideway, có pullback."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="15min", tz="UTC")

    # Ghép nhiều chế độ thị trường
    regimes = []
    remaining = n
    while remaining > 0:
        length = min(remaining, rng.integers(300, 900))
        kind = rng.choice(["up", "down", "side"], p=[0.4, 0.25, 0.35])
        drift = {"up": 0.00035, "down": -0.00030, "side": 0.0}[kind]
        vol = {"up": 0.0022, "down": 0.0028, "side": 0.0014}[kind]
        regimes.append(rng.normal(drift, vol, int(length)))
        remaining -= length

    returns = np.concatenate(regimes)[:n]
    close = 40000 * np.exp(np.cumsum(returns))

    spread = close * 0.0012
    high = close + np.abs(rng.normal(0, 1, n)) * spread
    low = close - np.abs(rng.normal(0, 1, n)) * spread
    open_ = np.concatenate([[close[0]], close[:-1]])

    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum.reduce([high, open_, close]),
            "low": np.minimum.reduce([low, open_, close]),
            "close": close,
            "volume": rng.lognormal(10, 1, n),
        },
        index=idx,
    )


def test_ema_matches_manual():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = ind.ema(s, 3)
    # EMA(3): alpha=0.5
    expected = [1.0, 1.5, 2.25, 3.125, 4.0625]
    assert np.allclose(result.values, expected), "EMA sai công thức"
    print("  [OK] EMA khớp tính tay")


def test_zigzag_has_lag():
    df = make_synthetic(1000)
    piv = ind.zigzag_confirmed(df, left=5, right=5)
    assert not piv.empty, "ZigZag không tìm được pivot nào"
    lag = (piv["confirmed_at"] - piv["idx"]).unique()
    assert set(lag) == {5}, f"Độ trễ xác nhận sai: {lag}"
    print(f"  [OK] ZigZag có độ trễ đúng 5 nến ({len(piv)} pivot)")


def test_mtf_no_lookahead():
    """TEST QUAN TRỌNG NHẤT."""
    m15 = make_synthetic(4000)
    h1 = resample_ohlcv(m15, "1h")

    aligned = align_htf_to_ltf(h1, m15.index)
    report = verify_no_lookahead(h1, aligned, "close", samples=400)

    assert report["clean"], (
        f"LOOK-AHEAD! {report['violations']}/{report['checked']} vi phạm"
    )
    print(
        f"  [OK] MTF sạch look-ahead "
        f"({report['checked']} mẫu, 0 vi phạm)"
    )


def test_mtf_value_is_previous_bar():
    """Kiểm tra cụ thể: giá trị ghép phải là nến H1 TRƯỚC ĐÓ."""
    m15 = make_synthetic(2000)
    h1 = resample_ohlcv(m15, "1h")
    aligned = align_htf_to_ltf(h1, m15.index)

    # Chọn 1 timestamp M15 nằm giữa 1 nến H1
    ts = m15.index[500]
    h1_bar_open = h1.index[h1.index <= ts][-1]
    prev_h1_open = h1.index[h1.index < h1_bar_open][-1]

    assert np.isclose(aligned.loc[ts, "close"], h1.loc[prev_h1_open, "close"]), (
        "Giá trị ghép không phải nến H1 liền trước"
    )
    print("  [OK] Giá trị ghép đúng là nến H1 đã đóng liền trước")


def test_mtf_verifier_allows_equal_closes():
    idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    h1 = pd.DataFrame({"close": [100.0, 100.0, 101.0]}, index=idx)
    m15_idx = pd.date_range(idx[0], periods=12, freq="15min", tz="UTC")
    aligned = align_htf_to_ltf(h1, m15_idx)
    report = verify_no_lookahead(h1, aligned)
    assert report["clean"], "Hai nến đóng bằng nhau bị báo nhầm look-ahead"
    print("  [OK] Bộ kiểm tra không báo sai khi hai nến HTF đóng bằng nhau")


def test_adx_range():
    df = make_synthetic(2000)
    a = ind.adx(df, 14).dropna()
    assert (a >= 0).all() and (a <= 100).all(), "ADX ngoài khoảng 0-100"
    print(f"  [OK] ADX hợp lệ (trung bình {a.mean():.1f})")


def test_fib_math():
    r = ind.fib_retracement(100, 200)
    assert np.isclose(r["0.618"], 138.2), "Fibo retracement sai"
    e = ind.fib_extension(100, 200, 150)
    assert np.isclose(e["1.618"], 311.8), "Fibo extension sai"
    print("  [OK] Fibonacci đúng công thức")


def test_full_pipeline():
    m15 = make_synthetic(8000)
    h1 = resample_ohlcv(m15, "1h")
    h4 = resample_ohlcv(m15, "4h")
    d1 = resample_ohlcv(m15, "1D")

    cfg = Config()
    sig = build_signals(m15, h1, h4, d1, cfg)

    n_entries = int(sig["entry_signal"].sum())
    days = (m15.index[-1] - m15.index[0]).days

    assert n_entries >= 0
    assert "sl" in sig.columns and "tp_2r" in sig.columns

    print(f"  [OK] Pipeline chạy: {n_entries} entry / {days} ngày "
          f"= {n_entries/max(days,1):.2f} lệnh/ngày")

    # Kiểm tra tỉ lệ lọc của từng tầng
    print("\n  Tỉ lệ nến pass từng filter:")
    for col in ["f_d1", "f_h4", "f_cross", "f_adx", "f_sep",
                "f_dow", "f_fib", "f_value_zone", "f_pa"]:
        pct = 100 * sig[col].mean()
        print(f"    {col:16s} {pct:5.1f}%")

    return sig


def test_backtest_closes_at_end():
    idx = pd.date_range("2024-01-01 23:45", periods=3, freq="15min", tz="UTC")
    m15 = pd.DataFrame(
        {"high": [100.5, 101.0, 101.5], "low": [99.5, 100.0, 100.5],
         "close": [100.0, 100.5, 101.0]},
        index=idx,
    )
    sig = pd.DataFrame(
        {
            "entry_signal": [True, False, False],
            "sl": [99.0, 99.0, 99.0],
            "adx": [30.0] * 3,
            "retrace_pct": [0.5] * 3,
            "pa_engulfing": [True] * 3,
            "pa_pinbar": [False] * 3,
            "pa_bos": [False] * 3,
        },
        index=idx,
    )
    trades = run_backtest(sig, m15, costs=Costs(0, 0))
    assert len(trades) == 1 and trades.iloc[0]["exit_reason"] == "END_OF_DATA"
    assert np.isclose(trades.iloc[0]["r_multiple"], 1.0)
    assert frequency_check(trades, idx)["total_days"] == 2
    print("  [OK] Engine đóng lệnh cuối dữ liệu, tính đúng 1R và số ngày")


def test_drawdown_includes_initial_balance():
    trades = pd.DataFrame(
        {"pnl": [-100.0], "r_multiple": [-1.0], "bars_held": [1]}
    )
    assert basic_metrics(trades)["max_drawdown_pct"] == 1.0
    print("  [OK] Drawdown tính từ số dư ban đầu")


if __name__ == "__main__":
    print("=" * 60)
    print("KIỂM CHỨNG CORE LOGIC")
    print("=" * 60)

    print("\n[1] Indicators")
    test_ema_matches_manual()
    test_adx_range()
    test_fib_math()
    test_zigzag_has_lag()

    print("\n[2] Multi-timeframe (chống look-ahead)")
    test_mtf_no_lookahead()
    test_mtf_value_is_previous_bar()
    test_mtf_verifier_allows_equal_closes()

    print("\n[3] Pipeline đầy đủ")
    sig = test_full_pipeline()

    print("\n[4] Backtest engine")
    test_backtest_closes_at_end()
    test_drawdown_includes_initial_balance()

    print("\n" + "=" * 60)
    print("TẤT CẢ TEST PASS")
    print("=" * 60)
