"""
Kiểm chứng core logic trước khi tin vào bất kỳ con số backtest nào.

Test quan trọng nhất: LOOK-AHEAD.
Nếu test này fail, mọi kết quả backtest đều vô nghĩa.
"""

import sys
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

from core import indicators as ind
from core.mtf import (
    align_htf_to_ltf,
    map_timeframes,
    resample_ohlcv,
    verify_no_lookahead,
)
from core.pure_sonic import PureSonicConfig, build_pure_signals
from core.signals import Config, build_signals, dow_and_fib_state, main_wave_filters
from core.trade_setup import (
    build_short_trade_setup_signals,
    build_trade_setup_signals,
    closed_bars,
    latest_trade_setup,
)
from backtest.diagnostics import ablation_variants, funnel
from backtest.engine import Costs, run_backtest
from backtest.metrics import basic_metrics, frequency_check, wilson_edge_interval
from backtest.regime import (
    regime_adx_d1,
    regime_btc_ma200,
    regime_btc_quarterly,
    tag_trades_with_regime,
)
from data import loader


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


def test_default_mapping_has_no_lookahead():
    """Cả hai nhánh D1→H1 và H4→H1 phải sạch."""
    m15 = make_synthetic(120 * 96)
    cfg = Config()
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    checks = {
        "main→entry": verify_no_lookahead(
            main, align_htf_to_ltf(main[["close"]], entry.index)
        ),
        "base→entry": verify_no_lookahead(
            base, align_htf_to_ltf(base[["close"]], entry.index)
        ),
    }
    assert all(report["clean"] for report in checks.values()), checks
    assert all(report["violations"] == 0 for report in checks.values())
    print("  [OK] D1→H1 và H4→H1: 0 vi phạm look-ahead")


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


def test_regimes_use_only_closed_history_and_entry_time():
    btc_d1 = make_synthetic(330)
    btc_d1.index = pd.date_range(
        "2023-01-01", periods=len(btc_d1), freq="1D", tz="UTC"
    )
    entry_index = pd.date_range(
        btc_d1.index[210], btc_d1.index[-1], freq="1h", tz="UTC"
    )

    for regime_fn in [
        regime_btc_ma200,
        regime_btc_quarterly,
        regime_adx_d1,
    ]:
        full = regime_fn(btc_d1)
        partial = regime_fn(btc_d1.iloc[:280])
        assert full.iloc[:280].equals(partial), f"{regime_fn.__name__} nhìn tương lai"

        raw = full.shift(-1).to_frame()
        aligned = full.to_frame().reindex(entry_index, method="ffill")
        check = verify_no_lookahead(raw, aligned, "regime", samples=500)
        assert check["clean"], (regime_fn.__name__, check)

    regime = pd.Series(
        ["bull", "bear"],
        index=pd.to_datetime(["2023-09-08", "2023-09-09"], utc=True),
        name="regime",
    )
    trades = pd.DataFrame({
        "entry_time": [pd.Timestamp("2023-09-08 12:00", tz="UTC")],
        "exit_time": [pd.Timestamp("2023-09-09 12:00", tz="UTC")],
    })
    tagged = tag_trades_with_regime(trades, regime)
    assert tagged.loc[0, "regime"] == "bull"
    assert tagged["regime"].notna().all()
    print("  [OK] Regime chỉ dùng quá khứ và gắn theo entry_time")


def test_pure_sonic_no_lookahead():
    entry = make_synthetic(90 * 96)
    main = resample_ohlcv(entry, "1h")
    aligned = align_htf_to_ltf(main[["close"]], entry.index)
    report = verify_no_lookahead(main, aligned, samples=500)
    assert report["clean"], report

    full = build_pure_signals(entry, main, PureSonicConfig())
    cutoff = len(entry) - 96
    partial_entry = entry.iloc[:cutoff]
    partial_main = resample_ohlcv(partial_entry, "1h")
    partial = build_pure_signals(
        partial_entry, partial_main, PureSonicConfig()
    )
    assert full.loc[partial.index, "entry_signal"].equals(partial["entry_signal"])
    print(f"  [OK] Pure Sonic main→entry: 0/{report['checked']} vi phạm")


def test_pure_sonic_only_four_conditions():
    entry = make_synthetic(90 * 96)
    main = resample_ohlcv(entry, "1h")
    sig = build_pure_signals(entry, main, PureSonicConfig())
    filters = [column for column in sig if column.startswith("f_")]
    assert filters == ["f_trend", "f_breakout", "f_value_zone", "f_pa"]
    assert not {"f_dow", "f_fib", "f_adx", "f_sep"} & set(sig)
    loose = build_pure_signals(
        entry,
        main,
        PureSonicConfig(use_breakout=False, use_pa=False),
    )
    assert (loose["entry_signal"] >= sig["entry_signal"]).all()
    print("  [OK] Pure Sonic chỉ có đúng 4 điều kiện")


def test_deploy_setup_has_five_gates_and_closed_bars():
    tiny = make_synthetic(4)
    now = tiny.index[-1] + pd.offsets.Minute(10)
    assert len(closed_bars(tiny, "15m", now)) == 3

    entry = make_synthetic(180 * 96, seed=0)
    main = resample_ohlcv(entry, "1h")
    sig = build_trade_setup_signals(entry, main)
    filters = [column for column in sig if column.startswith("f_")]
    assert filters == [
        "f_trend", "f_breakout", "f_dow", "f_value_zone", "f_pa"
    ]
    assert (sig["entry_signal"] <= sig["f_dow"]).all()
    signal_time = sig.index[sig["entry_signal"]][-1]
    setup = latest_trade_setup(
        "TEST/USDT",
        entry.loc[:signal_time],
        main.loc[:signal_time.floor("1h")],
        now=signal_time + pd.offsets.Minute(15),
    )
    assert setup["status"] == "READY"
    assert setup["sl"] < setup["entry"] < setup["tp1"] < setup["tp2"]

    down = entry.copy()
    ceiling = 300000.0
    down["open"] = ceiling - entry["open"]
    down["close"] = ceiling - entry["close"]
    down["high"] = ceiling - entry["low"]
    down["low"] = ceiling - entry["high"]
    down_main = resample_ohlcv(down, "1h")
    short_sig = build_short_trade_setup_signals(down, down_main)
    cutoff = len(down) - 96
    partial_down = down.iloc[:cutoff]
    partial_short = build_short_trade_setup_signals(
        partial_down, resample_ohlcv(partial_down, "1h")
    )
    assert short_sig.loc[
        partial_short.index, "entry_signal"
    ].equals(partial_short["entry_signal"])
    short_time = short_sig.index[short_sig["entry_signal"]][-1]
    short = latest_trade_setup(
        "TEST/USDT",
        down.loc[:short_time],
        down_main.loc[:short_time.floor("1h")],
        now=short_time + pd.offsets.Minute(15),
        side="SHORT",
    )
    assert short["status"] == "READY"
    assert short["tp2"] < short["tp1"] < short["entry"] < short["sl"]
    print("  [OK] Setup LONG/SHORT có đúng 5 gate và chỉ dùng nến đã đóng")


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


def test_swing_retrace_is_bounded():
    m15 = make_synthetic(90 * 96)
    h1 = resample_ohlcv(m15, "1h")
    state = dow_and_fib_state(h1, Config())
    valid = state[["swing_low", "swing_high"]].dropna()
    retrace = (
        valid["swing_high"] - h1.loc[valid.index, "close"]
    ) / (valid["swing_high"] - valid["swing_low"])
    in_range = retrace.between(0, 1).mean()
    assert in_range >= 0.95
    assert dow_and_fib_state(h1, Config(swing_max_age=0))["swing_low"].isna().all()
    cfg = Config()
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    sig = build_signals(entry, main, base, cfg)
    entry_in_range = sig["retrace_pct"].dropna().between(0, 1).mean()
    assert entry_in_range >= 0.95
    print(
        f"  [OK] retrace trong [0, 1]: main {in_range:.1%}, "
        f"entry {entry_in_range:.1%}"
    )


def test_full_pipeline():
    m15 = make_synthetic(8000)
    cfg = Config()
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    sig = build_signals(entry, main, base, cfg)

    n_entries = int(sig["entry_signal"].sum())
    days = (entry.index[-1] - entry.index[0]).days

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


def test_cross_mode_state_vs_event():
    h1 = resample_ohlcv(make_synthetic(90 * 96), "1h")
    state = main_wave_filters(h1, Config(cross_mode="state"))["cross_fresh"]
    event = main_wave_filters(h1, Config(cross_mode="event"))["cross_fresh"]
    assert state.sum() > event.sum()
    assert 0.40 <= state.mean() <= 0.60
    assert int(event.sum()) == 222, "Nhánh event đã khác baseline cũ"
    print(f"  [OK] Cross state {state.mean():.1%} > event {event.mean():.1%}")


def test_config_entry_defaults_and_sampling_preset():
    cfg = Config()
    assert (cfg.tf_base, cfg.tf_main, cfg.tf_entry) == ("1D", "4H", "1H")
    assert cfg.sl_lookback == 5 and cfg.max_bars == 150
    assert cfg.swing_max_age == 100 and (cfg.zz_left, cfg.zz_right) == (5, 5)
    assert cfg.use_h4_filter and cfg.use_cross_filter and cfg.use_adx_filter
    assert cfg.use_separation_filter and cfg.use_dow_filter and cfg.require_pa
    assert not cfg.use_d1_filter and not cfg.use_fib_filter
    assert cfg.adx_min == 18 and cfg.separation_min == 0.35
    sampling = Config.baseline_sampling()
    assert sampling.use_cross_filter and sampling.use_adx_filter
    assert not any(
        getattr(sampling, flag)
        for flag in [
            "use_d1_filter",
            "use_h4_filter",
            "use_separation_filter",
            "use_dow_filter",
            "use_fib_filter",
        ]
    )

    old = Config.m15_entry()
    assert (old.tf_base, old.tf_main, old.tf_entry) == ("4H", "1H", "15m")
    assert old.max_bars == 500 and old.swing_max_age == 200

    m15 = make_synthetic(90 * 96)
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    default_sig = build_signals(entry, main, base, cfg)
    default_funnel = funnel(default_sig)
    loose = funnel(build_signals(entry, main, base, sampling))
    assert "f_d1" not in default_sig.attrs["active_filters"]
    assert "f_fib" not in default_sig.attrs["active_filters"]
    assert set(
        default_funnel.loc[
            default_funnel["stage"].isin(["f_d1", "f_fib"]), "active"
        ]
    ) == {"OFF"}
    assert (
        default_funnel.loc[
            default_funnel["stage"].isin(["f_d1", "f_fib"]), "solo_count"
        ]
        > 0
    ).all()
    assert set(loose.loc[loose["active"] == "OFF", "cumulative"]) == {"-"}
    assert default_funnel["solo_count"].equals(loose["solo_count"])
    print("  [OK] Config D1/H4/H1 và preset M15 giữ đúng thông số")


def test_m15_preset_regression():
    """Refactor timeframe không được đổi tín hiệu M15 lịch sử."""
    m15 = make_synthetic(90 * 96)
    cfg = Config.m15_entry()
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    sig = build_signals(entry, main, base, cfg)
    columns = ["entry_signal", "sl", "tp_2r", "tp_fib_1618", "tp_fib_2618"]
    fingerprint = int(pd.util.hash_pandas_object(sig[columns], index=True).sum())
    assert int(sig["entry_signal"].sum()) == 30
    assert fingerprint == 17872205066520887617

    main_bands = ind.sonic_r_bands(main)
    trail = align_htf_to_ltf(
        main_bands[["ema_fast_low"]], entry.index
    )["ema_fast_low"]
    trades = run_backtest(
        sig,
        entry,
        costs=Costs(0, 0),
        max_bars=cfg.max_bars,
        trail_ema=trail,
    )
    assert len(trades) == 4
    print("  [OK] Preset M15 giữ nguyên 30 tín hiệu và 4 giao dịch baseline")


def test_fib_tp_is_independent_from_entry_filter():
    m15 = make_synthetic(90 * 96)
    cfg = Config(use_fib_filter=False)
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    sig = build_signals(entry, main, base, cfg)
    with_swing = sig["swing_low"].notna() & sig["swing_high"].notna()
    valid_tp = sig.loc[with_swing, ["tp_fib_1618", "tp_fib_2618"]].notna().all(axis=1)
    assert with_swing.any() and valid_tp.mean() >= 0.80

    custom = build_signals(
        entry, main, base, Config(use_fib_filter=False, tp_fib_1=1.5)
    )
    expected = custom["low"] + 1.5 * (custom["swing_high"] - custom["swing_low"])
    assert np.allclose(
        custom.loc[with_swing, "tp_fib_1618"],
        expected.loc[with_swing],
        equal_nan=True,
    )
    print(f"  [OK] TP Fibo độc lập entry, hợp lệ {valid_tp.mean():.1%} nến có swing")


def test_ablation_variants():
    variants = dict(ablation_variants(Config()))
    assert list(variants) == [
        "Đầy đủ (mới)", "Bỏ f_h4", "Bỏ f_cross", "Bỏ f_adx", "Bỏ f_sep",
        "Bỏ f_dow", "Bỏ f_pa", "Thêm lại f_d1", "Thêm lại f_fib",
    ]
    assert not variants["Bỏ f_h4"].use_h4_filter
    assert not variants["Bỏ f_pa"].require_pa
    assert variants["Thêm lại f_d1"].use_d1_filter
    assert variants["Thêm lại f_fib"].use_fib_filter
    print("  [OK] Ablation đủ 9 cấu hình mới")


def test_wilson_edge_interval():
    trades = pd.DataFrame({
        "pnl": [2.0] * 100 + [-1.0] * 100,
        "r_multiple": [2.0] * 100 + [-1.0] * 100,
    })
    ci = wilson_edge_interval(trades)
    assert np.isclose(ci["breakeven_winrate"], 33.33)
    assert ci["wilson_ci_low"] > 0
    print("  [OK] Wilson CI đo phần winrate vượt hòa vốn")


def test_pa_pattern_subset():
    m15 = make_synthetic(90 * 96)
    cfg = Config(pa_patterns=("engulfing", "pinbar"))
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    sig = build_signals(entry, main, base, cfg)
    assert sig["f_pa"].equals(sig[["pa_engulfing", "pa_pinbar"]].any(axis=1))
    print("  [OK] PA subset dùng đúng pattern được chỉ định")


def test_filters_not_mutually_exclusive():
    m15 = make_synthetic(90 * 96)
    cfg = Config()
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    sig = build_signals(entry, main, base, cfg)
    filters = [
        "f_d1", "f_h4", "f_cross", "f_adx", "f_sep",
        "f_dow", "f_fib", "f_value_zone", "f_pa",
    ]
    empty = [
        (a, b)
        for a, b in combinations(filters, 2)
        if not (sig[a] & sig[b]).any()
    ]
    assert not empty, f"Cặp filter loại trừ nhau: {empty}"
    print("  [OK] Không cặp filter nào loại trừ nhau")


def test_signal_frequency_in_range():
    m15 = make_synthetic(90 * 96)
    cfg = Config()
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    sig = build_signals(entry, main, base, cfg)
    per_day = sig["entry_signal"].sum() / 90
    median = sig.loc[sig["entry_signal"], "retrace_pct"].median()
    assert 0 < per_day <= 5.0
    print(f"  [OK] {per_day:.3f} tín hiệu/ngày, median retrace {median:.3f}")


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


def test_no_cost_backtest_keeps_tight_stops():
    idx = pd.date_range("2024-01-01", periods=3, freq="15min", tz="UTC")
    prices = pd.DataFrame(
        {
            "high": [100.01, 100.20, 100.20],
            "low": [99.99, 100.00, 100.00],
            "close": [100.00, 100.10, 100.10],
        },
        index=idx,
    )
    sig = pd.DataFrame(
        {
            "entry_signal": [True, False, False],
            "sl": [99.95] * 3,
            "pa_engulfing": [False] * 3,
            "pa_pinbar": [True] * 3,
            "pa_bos": [False] * 3,
        },
        index=idx,
    )
    assert len(run_backtest(sig, prices, costs=Costs(0, 0))) == 1
    assert run_backtest(sig, prices).empty
    print("  [OK] Backtest không phí không loại SL sát")


def test_drawdown_includes_initial_balance():
    trades = pd.DataFrame(
        {"pnl": [-100.0], "r_multiple": [-1.0], "bars_held": [1]}
    )
    assert basic_metrics(trades)["max_drawdown_pct"] == 1.0
    assert basic_metrics(trades, initial_balance=20000)["max_drawdown_pct"] == 0.5
    print("  [OK] Drawdown tính từ số dư ban đầu")


def test_loader_keeps_cache_after_partial_download():
    class FakeExchange:
        rateLimit = 0
        calls = 0

        def milliseconds(self):
            return 2_000_000_000

        def fetch_ohlcv(self, *args, **kwargs):
            self.calls += 1
            if self.calls > 1:
                raise RuntimeError("rate limit")
            return [[i, 1, 2, 0, 1, 1] for i in range(300)]

    class FakeCcxt:
        okx = staticmethod(lambda options: FakeExchange())

    old_cache, old_ccxt = loader.CACHE_DIR, loader.ccxt
    with TemporaryDirectory() as tmp:
        try:
            loader.CACHE_DIR = Path(tmp)
            loader.ccxt = FakeCcxt()
            cached = make_synthetic(10)
            path = loader._cache_path("BTC/USDT", "15m", 1, "okx")
            cached.to_parquet(path)
            result = loader.fetch_ohlcv(
                "BTC/USDT", "15m", 1, exchange_id="okx", cache_max_age=-1
            )
            assert result.equals(cached)
            assert pd.read_parquet(path).equals(cached)
        finally:
            loader.CACHE_DIR, loader.ccxt = old_cache, old_ccxt
    print("  [OK] Loader không ghi đè cache khi download lỗi giữa chừng")


def test_binance_top_symbols_excludes_stable_and_leveraged():
    class FakeExchange:
        def fetch_tickers(self):
            return {
                "BTC/USDT": {"quoteVolume": 100},
                "ETH/USDT": {"quoteVolume": 90},
                "SOL/USDT": {"quoteVolume": 80},
                "USDC/USDT": {"quoteVolume": 1000},
                "ETHUP/USDT": {"quoteVolume": 900},
                "BTC/USDT:USDT": {"quoteVolume": 800},
            }

    class FakeCcxt:
        binance = staticmethod(lambda options: FakeExchange())

    old_ccxt = loader.ccxt
    try:
        loader.ccxt = FakeCcxt()
        assert loader.top_usdt_symbols(limit=3) == [
            "BTC/USDT", "ETH/USDT", "SOL/USDT"
        ]
    finally:
        loader.ccxt = old_ccxt
    print("  [OK] Binance TOP volume loại stablecoin và leveraged token")


def test_market_cap_universe_is_tradable_and_excludes_stablecoins():
    markets = {
        "btc": {
            "symbol": "BTC/USDT", "base": "BTC", "quote": "USDT",
            "spot": True, "active": True,
        },
        "usdc": {
            "symbol": "USDC/USDT", "base": "USDC", "quote": "USDT",
            "spot": True, "active": True,
        },
        "eth": {
            "symbol": "ETH/USDT", "base": "ETH", "quote": "USDT",
            "spot": True, "active": True,
        },
    }
    coins = [
        {"symbol": "eth", "name": "Ethereum", "market_cap": 200, "market_cap_rank": 2},
        {"symbol": "none", "name": "Not listed", "market_cap": 300, "market_cap_rank": 1},
        {"symbol": "usdc", "name": "USDC", "market_cap": 250, "market_cap_rank": 3},
        {"symbol": "btc", "name": "Bitcoin", "market_cap": 400, "market_cap_rank": 1},
    ]
    universe = loader._select_market_cap_universe(coins, markets, 2)
    assert [row["symbol"] for row in universe] == ["BTC/USDT", "ETH/USDT"]
    assert [row["rank"] for row in universe] == [1, 2]

    swap_markets = {
        "btc": {
            "symbol": "BTC/USDT:USDT", "base": "BTC", "settle": "USDT",
            "swap": True, "linear": True, "active": True, "contractSize": 0.01,
            "precision": {"amount": 0.01}, "info": {"instCategory": "1"},
        },
        "aapl": {
            "symbol": "AAPL/USDT:USDT", "base": "AAPL", "settle": "USDT",
            "swap": True, "linear": True, "active": True,
            "info": {"instCategory": "3"},
        },
    }
    swaps = loader._select_usdt_crypto_swaps(swap_markets)
    assert [row["symbol"] for row in swaps] == ["BTC/USDT:USDT"]
    assert ":" not in loader._cache_path(
        "BTC/USDT:USDT", "15m", 3, "okx"
    ).name
    print("  [OK] Universe lọc đúng spot vốn hóa và perpetual crypto")


if __name__ == "__main__":
    print("=" * 60)
    print("KIỂM CHỨNG CORE LOGIC")
    print("=" * 60)

    print("\n[1] Indicators")
    test_ema_matches_manual()
    test_adx_range()
    test_fib_math()
    test_zigzag_has_lag()
    test_swing_retrace_is_bounded()

    print("\n[2] Multi-timeframe (chống look-ahead)")
    test_mtf_no_lookahead()
    test_default_mapping_has_no_lookahead()
    test_mtf_value_is_previous_bar()
    test_mtf_verifier_allows_equal_closes()
    test_regimes_use_only_closed_history_and_entry_time()
    test_pure_sonic_no_lookahead()
    test_pure_sonic_only_four_conditions()
    test_deploy_setup_has_five_gates_and_closed_bars()

    print("\n[3] Pipeline đầy đủ")
    sig = test_full_pipeline()
    test_cross_mode_state_vs_event()
    test_config_entry_defaults_and_sampling_preset()
    test_m15_preset_regression()
    test_fib_tp_is_independent_from_entry_filter()
    test_ablation_variants()
    test_wilson_edge_interval()
    test_pa_pattern_subset()
    test_filters_not_mutually_exclusive()
    test_signal_frequency_in_range()

    print("\n[4] Backtest engine")
    test_backtest_closes_at_end()
    test_no_cost_backtest_keeps_tight_stops()
    test_drawdown_includes_initial_balance()
    test_loader_keeps_cache_after_partial_download()
    test_binance_top_symbols_excludes_stable_and_leveraged()
    test_market_cap_universe_is_tradable_and_excludes_stablecoins()

    print("\n" + "=" * 60)
    print("TẤT CẢ TEST PASS")
    print("=" * 60)
