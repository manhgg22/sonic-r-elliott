import numpy as np
import pandas as pd

from backtest.engine import Costs, run_backtest
from core import indicators as ind


def test_adr_ignores_zero_range_days():
    index = pd.date_range("2026-01-01", periods=16, freq="1D", tz="UTC")
    daily = pd.DataFrame(
        {
            "high": [110.0] * 14 + [100.0, 120.0],
            "low": [100.0] * 16,
        },
        index=index,
    )
    result = ind.adr(daily, period=14)
    assert result.iloc[:13].isna().all()
    assert result.iloc[13] == 10.0
    assert result.iloc[14] == 10.0
    assert np.isclose(result.iloc[15], (13 * 10 + 20) / 14)


def _flat_signal(index, side):
    sl = 90.0 if side == "LONG" else 110.0
    return pd.DataFrame(
        {
            "entry_signal": [True] + [False] * (len(index) - 1),
            "sl": sl,
            "side": side,
        },
        index=index,
    )


def test_funding_counts_exact_timestamps_and_side_sign():
    index = pd.date_range(
        "2026-01-01 01:00", periods=101, freq="15min", tz="UTC"
    )
    market = pd.DataFrame(
        {"high": 100.1, "low": 99.9, "close": 100.0},
        index=index,
    )
    costs = Costs(0, 0, funding_rate_8h=0.0001)
    long = run_backtest(
        _flat_signal(index, "LONG"), market, costs=costs, max_bars=1000
    ).iloc[0]
    short = run_backtest(
        _flat_signal(index, "SHORT"), market, costs=costs, max_bars=1000
    ).iloc[0]
    assert np.isclose(long["funding_paid"], 0.3)
    assert np.isclose(short["funding_paid"], -0.3)
    assert np.isclose(long["r_multiple"], -0.003)
    assert np.isclose(short["r_multiple"], 0.003)


def test_short_stop_entry_and_signal_tp():
    index = pd.date_range("2026-01-01", periods=4, freq="15min", tz="UTC")
    market = pd.DataFrame(
        {
            "high": [101.0, 100.0, 90.0, 90.0],
            "low": [96.0, 94.0, 84.0, 84.0],
            "close": [98.0, 96.0, 85.0, 85.0],
        },
        index=index,
    )
    sig = pd.DataFrame(
        {
            "entry_signal": [True, False, False, False],
            "entry_trigger": [95.0, np.nan, np.nan, np.nan],
            "sl": [105.0] * 4,
            "tp": [85.0, np.nan, np.nan, np.nan],
            "tp_source": ["fixed_r", "", "", ""],
            "side": ["SHORT"] * 4,
        },
        index=index,
    )
    trades = run_backtest(
        sig, market, tp_mode="fixed_r", costs=Costs(0, 0, 0)
    )
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["side"] == "SHORT"
    assert trade["entry_time"] == index[1]
    assert trade["exit_time"] == index[2]
    assert trade["exit_price"] == 85.0
    assert np.isclose(trade["r_multiple"], 1.0)


def test_rdh_is_snapshotted_at_fill_from_prior_closed_bars():
    index = pd.date_range("2026-01-01", periods=4, freq="15min", tz="UTC")
    market = pd.DataFrame(
        {
            "high": [101.0, 106.0, 111.0, 111.0],
            "low": [90.0, 100.0, 104.0, 104.0],
            "close": [100.0, 105.0, 110.0, 110.0],
        },
        index=index,
    )
    sig = pd.DataFrame(
        {
            "entry_signal": [True, False, False, False],
            "entry_trigger": [105.0, np.nan, np.nan, np.nan],
            "sl": [95.0] * 4,
            "tp": [np.nan] * 4,
            "tp_source": [""] * 4,
            "tp_r": [1.0] * 4,
            "adr": [20.0] * 4,
            "side": ["LONG"] * 4,
        },
        index=index,
    )
    trade = run_backtest(
        sig, market, tp_mode="rdh_rdl", costs=Costs(0, 0, 0)
    ).iloc[0]
    assert trade["tp"] == 110.0
    assert trade["tp_source"] == "rdh"
    assert trade["exit_time"] == index[2]


def test_real_funding_series_missing_period_fails_and_negative_rate_credits():
    index = pd.date_range(
        "2026-01-01 01:00", periods=101, freq="15min", tz="UTC"
    )
    market = pd.DataFrame(
        {"high": 100.1, "low": 99.9, "close": 100.0},
        index=index,
    )
    incomplete = pd.Series(
        [0.0001],
        index=pd.DatetimeIndex(["2026-01-01 08:00"], tz="UTC"),
    )
    try:
        run_backtest(
            _flat_signal(index, "LONG"),
            market,
            symbol="BTC",
            costs=Costs(0, 0, 0, {"BTC": incomplete}),
            max_bars=1000,
        )
    except ValueError as error:
        assert "thiếu timestamp" in str(error)
    else:
        raise AssertionError("Funding thiếu kỳ phải bị reject")

    credited = run_backtest(
        _flat_signal(index, "LONG"),
        market,
        costs=Costs(0, 0, -0.0001),
        max_bars=1000,
    ).iloc[0]
    assert np.isclose(credited["funding_pnl"], 0.3)
    assert credited["funding_periods"] == 3


def test_funding_boundary_excludes_entry_and_includes_exit():
    index = pd.date_range(
        "2026-01-01 08:00", periods=33, freq="15min", tz="UTC"
    )
    market = pd.DataFrame(
        {"high": 100.1, "low": 99.9, "close": 100.0},
        index=index,
    )
    trade = run_backtest(
        _flat_signal(index, "LONG"),
        market,
        costs=Costs(0, 0, 0.0001),
        max_bars=1000,
    ).iloc[0]
    assert trade["entry_time"] == index[0]
    assert trade["exit_time"] == index[-1]
    assert trade["funding_periods"] == 1
    assert np.isclose(trade["funding_paid"], 0.1)
