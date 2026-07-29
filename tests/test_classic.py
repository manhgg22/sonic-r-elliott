from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pandas as pd

from core.classic import SonicClassicConfig, build_classic_signals


def _frames(side="LONG", weekend=False):
    start = "2026-01-03" if weekend else "2026-01-05"
    index = pd.date_range(start, periods=32, freq="15min", tz="UTC")
    close = np.full(len(index), 100.0)
    close[10] = 110.0
    close[11:] = 108.0
    entry = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.linspace(10, 20, len(index)),
        },
        index=index,
    )
    main_index = pd.date_range(index[0].normalize(), periods=12, freq="1h", tz="UTC")
    main_close = 80.0 + 5.0 * np.arange(12)
    main = pd.DataFrame(
        {
            "open": main_close,
            "high": main_close + 0.1,
            "low": main_close - 0.1,
            "close": main_close,
            "volume": 100.0,
        },
        index=main_index,
    )
    daily_index = pd.date_range(
        index[0].normalize() - pd.Timedelta("19D"),
        periods=20,
        freq="1D",
        tz="UTC",
    )
    daily = pd.DataFrame(
        {
            "open": 100.0,
            "high": 115.0,
            "low": 85.0,
            "close": 100.0,
            "volume": 1000.0,
        },
        index=daily_index,
    )
    if side == "SHORT":
        def mirror(frame):
            result = frame.copy()
            result["open"] = 200 - frame["open"]
            result["high"] = 200 - frame["low"]
            result["low"] = 200 - frame["high"]
            result["close"] = 200 - frame["close"]
            return result

        entry, main, daily = mirror(entry), mirror(main), mirror(daily)
    return entry, main, daily


def _waves(index):
    waves = pd.DataFrame(index=index)
    waves["wave_valid"] = False
    waves["leg"] = 0
    waves["leg1_crossed_dragon"] = False
    waves["wave_id"] = pd.Series(pd.NA, index=index, dtype="string")
    waves["missed_preconfirmation"] = False
    for column in [
        "wave_start_idx", "pivot_2_idx", "pivot_3_idx", "leg3_ready_at"
    ]:
        waves[column] = pd.Series(pd.NA, index=index, dtype="Int64")
    active = np.arange(len(index)) >= 10
    waves.loc[active, "wave_valid"] = True
    waves.loc[active, "leg"] = 3
    waves.loc[active, "leg1_crossed_dragon"] = True
    waves.loc[active, "wave_start_idx"] = 2
    waves.loc[active, "pivot_2_idx"] = 5
    waves.loc[active, "pivot_3_idx"] = 7
    waves.loc[active, "leg3_ready_at"] = 10
    waves.loc[active, "wave_id"] = "LONG:2:5:7"
    return waves


def _build(side="LONG", cfg=None, weekend=False, entry_override=None):
    entry, main, daily = _frames(side, weekend)
    if entry_override is not None:
        entry = entry_override(entry)
    cfg = cfg or SonicClassicConfig(
        slope_lookback=1,
        tp_mode="fixed_r",
    )
    with patch("core.classic.detect_waves", return_value=_waves(entry.index)):
        return build_classic_signals(entry, main, daily, cfg, side), entry


def test_trigger_sl_and_fixed_r_long():
    sig, entry = _build()
    triggers = np.flatnonzero(sig["trigger_event"].to_numpy())
    assert triggers.tolist() == [10]
    row = sig.iloc[10]
    assert row["entry_signal"]
    assert row["entry_trigger"] > entry["high"].iloc[10]
    expected_sl = entry["low"].iloc[7] - 0.5 * row["atr_m15"]
    assert np.isclose(row["sl"], expected_sl)
    assert np.isclose(row["tp"], row["entry_trigger"] + row["risk"])
    assert row["tp_source"] == "fixed_r"


def test_preconfirmation_breakout_is_not_reused():
    def early_breakout(entry):
        entry = entry.copy()
        entry.loc[entry.index[9], ["open", "high", "low", "close"]] = [
            110, 111, 109, 110
        ]
        entry.loc[entry.index[10], ["open", "high", "low", "close"]] = [
            110, 111, 109, 110
        ]
        return entry

    sig, _ = _build(entry_override=early_breakout)
    assert not sig["trigger_event"].iloc[:11].any()


def test_sl_too_wide_and_too_tight_are_rejected():
    wide_cfg = SonicClassicConfig(
        slope_lookback=1, tp_mode="fixed_r", sl_min_adr=0.01, sl_max_adr=0.1
    )
    wide, _ = _build(cfg=wide_cfg)
    assert wide["rejected_reason"].iloc[10] == "SL_TOO_WIDE"
    assert not wide["entry_signal"].iloc[10]

    tight_cfg = SonicClassicConfig(
        slope_lookback=1, tp_mode="fixed_r", sl_min_adr=1.0, sl_max_adr=2.0
    )
    tight, _ = _build(cfg=tight_cfg)
    assert tight["rejected_reason"].iloc[10] == "SL_TOO_TIGHT"
    assert not tight["entry_signal"].iloc[10]


def test_sr_without_level_falls_back_to_one_r():
    cfg = SonicClassicConfig(slope_lookback=1, tp_mode="sr_level")
    sig, _ = _build(cfg=cfg)
    row = sig.iloc[10]
    assert row["tp_source"] == "fallback_no_sr"
    assert np.isclose(row["tp"], row["entry_trigger"] + row["risk"])


def test_weekend_and_short_are_supported():
    weekend, _ = _build(weekend=True)
    assert weekend["entry_signal"].iloc[10]
    assert weekend.index[10].weekday() >= 5

    short, entry = _build(side="SHORT")
    row = short.iloc[10]
    assert row["entry_signal"]
    assert row["entry_trigger"] < entry["low"].iloc[10]
    assert row["sl"] > entry["high"].iloc[7]
    assert row["tp"] < row["entry_trigger"]


def test_leg1_cross_can_be_required():
    entry, main, daily = _frames()
    waves = _waves(entry.index)
    waves["leg1_crossed_dragon"] = False
    cfg = SonicClassicConfig(
        slope_lookback=1, tp_mode="fixed_r", require_leg1_cross=True
    )
    with patch("core.classic.detect_waves", return_value=waves):
        sig = build_classic_signals(entry, main, daily, cfg, "LONG")
    assert sig["trigger_event"].iloc[10]
    assert not sig["entry_signal"].iloc[10]


def test_missing_adr_and_engine_minimum_are_explicit_rejections():
    entry, main, daily = _frames()
    short_history = daily.iloc[:13]
    with patch("core.classic.detect_waves", return_value=_waves(entry.index)):
        missing = build_classic_signals(
            entry,
            main,
            short_history,
            SonicClassicConfig(slope_lookback=1, tp_mode="fixed_r"),
            "LONG",
        )
    assert missing["rejected_reason"].iloc[10] == "ADR_UNAVAILABLE"

    cfg = SonicClassicConfig(
        slope_lookback=1,
        tp_mode="fixed_r",
        min_risk_price_pct=0.20,
    )
    with patch("core.classic.detect_waves", return_value=_waves(entry.index)):
        minimum = build_classic_signals(entry, main, daily, cfg, "LONG")
    assert minimum["rejected_reason"].iloc[10] == "SL_BELOW_ENGINE_MIN"


def test_pvsra_location_window_uses_typical_price_and_requires_20_bars():
    from core.classic import _pva_location_counts

    index = pd.date_range("2026-01-01", periods=20, freq="15min", tz="UTC")
    values = np.arange(20.0)
    frame = pd.DataFrame(
        {"high": values + 1, "low": values, "close": values + 0.5},
        index=index,
    )
    climax = pd.Series(False, index=index)
    climax.iloc[-1] = True
    highs, lows = _pva_location_counts(frame, climax)
    assert highs.iloc[:19].isna().all()
    assert lows.iloc[:19].isna().all()
    assert highs.iloc[-1] == 1
    assert lows.iloc[-1] == 0


def test_classic_decision_columns_are_prefix_stable():
    from core.mtf import resample_ohlcv

    rng = np.random.default_rng(20260729)
    close = 100 + rng.normal(0, 0.7, 120).cumsum()
    index = pd.date_range("2026-02-01", periods=120, freq="15min", tz="UTC")
    entry = pd.DataFrame(
        {
            "open": close,
            "high": close + rng.uniform(0.2, 0.8, len(close)),
            "low": close - rng.uniform(0.2, 0.8, len(close)),
            "close": close,
            "volume": rng.uniform(10, 100, len(close)),
        },
        index=index,
    )
    daily_index = pd.date_range(
        "2026-01-12", periods=21, freq="1D", tz="UTC"
    )
    daily = pd.DataFrame(
        {
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": 100.0,
            "volume": 1000.0,
        },
        index=daily_index,
    )
    cfg = SonicClassicConfig(
        slope_lookback=1, pivot_left=2, pivot_right=2, tp_mode="fixed_r"
    )
    full = build_classic_signals(
        entry, resample_ohlcv(entry, "1h"), daily, cfg, "LONG"
    )
    columns = [
        "entry_signal", "side", "entry_trigger", "sl",
        "tp_source", "rejected_reason",
    ]
    for end in range(59, len(entry), 10):
        prefix_entry = entry.iloc[:end + 1]
        prefix = build_classic_signals(
            prefix_entry,
            resample_ohlcv(prefix_entry, "1h"),
            daily,
            cfg,
            "LONG",
        )
        pd.testing.assert_series_equal(
            full.loc[entry.index[end], columns],
            prefix.iloc[-1][columns],
            check_names=False,
        )
