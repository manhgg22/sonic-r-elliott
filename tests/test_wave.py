import numpy as np
import pandas as pd

from core import indicators as ind
from core.wave import detect_waves


def _long_fixture():
    close = np.array([8, 7, 5, 8, 11, 9, 8, 9, 12, 11], dtype=float)
    high = close + 1
    low = close - 1
    index = pd.date_range("2026-01-01", periods=len(close), freq="15min", tz="UTC")
    df = pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": 1.0},
        index=index,
    )
    bands = pd.DataFrame(
        {"ema_fast_high": 9.0, "ema_fast_low": 6.0},
        index=index,
    )
    return df, bands


def test_valid_long_wave_and_confirmation_delay():
    df, bands = _long_fixture()
    wave = detect_waves(df, bands, "LONG", left=1, right=1)
    assert not wave["wave_valid"].iloc[6]
    assert wave["wave_valid"].iloc[7]
    assert wave["leg"].iloc[7] == 3
    assert wave["wave_start_idx"].iloc[7] == 2
    assert wave["pivot_2_idx"].iloc[7] == 4
    assert wave["pivot_3_idx"].iloc[7] == 6
    assert wave["leg3_ready_at"].iloc[7] == 7
    assert wave["leg1_crossed_dragon"].iloc[7]


def test_lower_low_and_start_above_dragon_are_rejected():
    df, bands = _long_fixture()
    lower_low = df.copy()
    lower_low.iloc[6, lower_low.columns.get_loc("low")] = 3.0
    assert not detect_waves(
        lower_low, bands, "LONG", left=1, right=1
    )["wave_valid"].any()

    above = bands.copy()
    above["ema_fast_low"] = 4.0
    assert not detect_waves(
        df, above, "LONG", left=1, right=1
    )["wave_valid"].any()


def test_short_is_symmetric_to_long():
    long_df, long_bands = _long_fixture()
    short_df = pd.DataFrame(
        {
            "open": 20 - long_df["open"],
            "high": 20 - long_df["low"],
            "low": 20 - long_df["high"],
            "close": 20 - long_df["close"],
            "volume": long_df["volume"],
        },
        index=long_df.index,
    )
    short_bands = pd.DataFrame(
        {
            "ema_fast_high": 20 - long_bands["ema_fast_low"],
            "ema_fast_low": 20 - long_bands["ema_fast_high"],
        },
        index=long_df.index,
    )
    long_wave = detect_waves(long_df, long_bands, "LONG", 1, 1)
    short_wave = detect_waves(short_df, short_bands, "SHORT", 1, 1)
    for column in ["wave_valid", "leg", "leg1_crossed_dragon", "leg3_ready_at"]:
        pd.testing.assert_series_equal(
            long_wave[column], short_wave[column], check_names=False
        )


def test_breakout_before_confirmation_marks_wave_missed():
    df, bands = _long_fixture()
    df = df.copy()
    df.iloc[6, df.columns.get_loc("close")] = 10.0
    # Low vẫn là HL hợp lệ, nhưng close đã nằm ngoài Dragon trước ready_at=7.
    wave = detect_waves(df, bands, "LONG", left=1, right=1)
    assert wave["wave_valid"].iloc[7]
    assert wave["missed_preconfirmation"].iloc[7]


def test_wave_has_no_prefix_lookahead_on_random_data():
    rng = np.random.default_rng(20260729)
    close = 100 + rng.normal(0, 1, 100).cumsum()
    spread = rng.uniform(0.2, 1.2, len(close))
    index = pd.date_range("2026-01-01", periods=len(close), freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": rng.uniform(1, 10, len(close)),
        },
        index=index,
    )
    bands = ind.sonic_r_bands(df)
    full = detect_waves(df, bands, "LONG", left=3, right=3)
    for end in range(12, len(df)):
        prefix_df = df.iloc[:end + 1]
        prefix = detect_waves(
            prefix_df,
            ind.sonic_r_bands(prefix_df),
            "LONG",
            left=3,
            right=3,
        )
        pd.testing.assert_series_equal(
            full.iloc[end],
            prefix.iloc[-1],
            check_names=False,
        )
