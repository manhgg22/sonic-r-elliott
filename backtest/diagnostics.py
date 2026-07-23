"""Chẩn đoán filter funnel cho hệ thống Sonic R + Dow + PA."""

import argparse
import sys
from dataclasses import replace

import pandas as pd

from core.mtf import (
    align_htf_to_ltf,
    map_timeframes,
    resample_ohlcv,
    verify_no_lookahead,
)
from core.signals import Config, build_signals
from data.loader import fetch_ohlcv


FILTERS = [
    "f_d1",
    "f_h4",
    "f_cross",
    "f_adx",
    "f_sep",
    "f_dow",
    "f_fib",
    "f_value_zone",
    "f_pa",
]

FILTER_FLAGS = {
    "f_d1": "use_d1_filter",
    "f_h4": "use_h4_filter",
    "f_cross": "use_cross_filter",
    "f_adx": "use_adx_filter",
    "f_sep": "use_separation_filter",
    "f_dow": "use_dow_filter",
    "f_fib": "use_fib_filter",
    "f_pa": "require_pa",
}


def ablation_variants(cfg: Config) -> list[tuple[str, Config]]:
    """Các cấu hình bắt buộc của Ticket 12, không sửa ``cfg`` gốc."""
    return [
        ("Đầy đủ (mới)", replace(cfg)),
        ("Bỏ f_h4", replace(cfg, use_h4_filter=False)),
        ("Bỏ f_cross", replace(cfg, use_cross_filter=False)),
        ("Bỏ f_adx", replace(cfg, use_adx_filter=False)),
        ("Bỏ f_sep", replace(cfg, use_separation_filter=False)),
        ("Bỏ f_dow", replace(cfg, use_dow_filter=False)),
        ("Bỏ f_pa", replace(cfg, require_pa=False)),
        ("Thêm lại f_d1", replace(cfg, use_d1_filter=True)),
        ("Thêm lại f_fib", replace(cfg, use_fib_filter=True)),
    ]


def funnel(sig: pd.DataFrame) -> pd.DataFrame:
    """
    Đếm số nến còn lại sau từng tầng lọc.

    Trả về: stage | solo_count | active | cumulative | pct_total | killed.
    """
    mask = pd.Series(True, index=sig.index)
    active = set(sig.attrs.get("active_filters", FILTERS))
    previous = len(sig)
    rows = []
    for stage in FILTERS:
        is_active = stage in active
        solo_count = int(sig[stage].sum())
        if is_active:
            mask &= sig[stage].fillna(False)
            cumulative = int(mask.sum())
            pct_total = round(100 * cumulative / max(len(sig), 1), 3)
            killed = previous - cumulative
            previous = cumulative
        else:
            cumulative = pct_total = killed = "-"
        rows.append(
            {
                "stage": stage,
                "solo_count": solo_count,
                "active": "ON" if is_active else "OFF",
                "cumulative": cumulative,
                "pct_total": pct_total,
                "killed": killed,
            }
        )
    return pd.DataFrame(rows)


def _active_filters(cfg: Config) -> list[str]:
    return [
        name
        for name in FILTERS
        if name == "f_value_zone"
        or getattr(cfg, FILTER_FLAGS.get(name, ""), False)
    ]


def marginal_contribution(
    entry: pd.DataFrame,
    main: pd.DataFrame,
    base: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """
    Bỏ từng filter và đo số tín hiệu tăng thêm.

    Trả về: filter | signals_without | delta | per_day.
    """
    sig = build_signals(entry, main, base, cfg)
    active = _active_filters(cfg)
    baseline = int(sig["entry_signal"].sum())
    days = max(int(entry.index.normalize().nunique()), 1)
    rows = []
    for removed in FILTERS:
        if removed not in active:
            count = baseline
        else:
            remaining = [name for name in active if name != removed]
            count = int(sig[remaining].all(axis=1).sum())
        rows.append(
            {
                "filter": removed,
                "signals_without": count,
                "delta": count - baseline,
                "per_day": round(count / days, 3),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["delta", "filter"], ascending=[False, True], ignore_index=True
    )


def overlap_matrix(sig: pd.DataFrame, filters: list[str]) -> pd.DataFrame:
    """
    Ma trận ``actual / expected`` của từng cặp filter.

    Expected giả định hai filter độc lập. Actual thấp hơn nhiều expected
    cho thấy hai điều kiện chống nhau.
    """
    values = sig[filters].fillna(False).astype(bool)
    counts = values.sum()
    total = max(len(values), 1)
    result = pd.DataFrame(index=filters, columns=filters, dtype=object)
    for left in filters:
        for right in filters:
            actual = int((values[left] & values[right]).sum())
            expected = (
                float(counts[left])
                if left == right
                else counts[left] * counts[right] / total
            )
            result.loc[left, right] = f"{actual} / {expected:.1f}"
    result.index.name = "actual / expected"
    return result


def retrace_distribution(sig: pd.DataFrame) -> dict:
    """Phân bố retrace tại các nến chạm Value Zone."""
    values = sig.loc[sig["f_value_zone"], "retrace_pct"].dropna()
    if values.empty:
        return {
            "n": 0,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "max": None,
            "pct_in_current_band": None,
        }
    in_band = sig.loc[values.index, "f_fib"]
    return {
        "n": len(values),
        "min": round(values.min(), 4),
        "p25": round(values.quantile(0.25), 4),
        "median": round(values.median(), 4),
        "p75": round(values.quantile(0.75), 4),
        "max": round(values.max(), 4),
        "pct_in_current_band": round(100 * in_band.mean(), 2),
    }


def load_data(symbol: str, days: int, synthetic: bool) -> tuple[pd.DataFrame, ...]:
    if synthetic:
        from tests.test_core import make_synthetic

        m15 = make_synthetic(days * 96)
    else:
        m15 = fetch_ohlcv(symbol, "15m", days)
        if m15.empty:
            raise RuntimeError(f"Không tải được dữ liệu {symbol}")
    return (
        m15,
        resample_ohlcv(m15, "1h"),
        resample_ohlcv(m15, "4h"),
        resample_ohlcv(m15, "1D"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--cross-mode", choices=["state", "event"], default="state")
    parser.add_argument("--baseline-sampling", action="store_true")
    args = parser.parse_args()

    m15, _, _, _ = load_data(args.symbol, args.days, args.synthetic)
    cfg = Config.baseline_sampling() if args.baseline_sampling else Config()
    cfg.cross_mode = args.cross_mode
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    sig = build_signals(entry, main, base, cfg)

    source = "synthetic" if args.synthetic else args.symbol
    print(
        f"\nDIAGNOSTICS — {source}, {args.days} ngày, "
        f"{cfg.tf_base}/{cfg.tf_main}/{cfg.tf_entry}, cross={args.cross_mode}"
    )
    for label, raw in [("main→entry", main), ("base→entry", base)]:
        aligned = align_htf_to_ltf(raw[["close"]], entry.index)
        check = verify_no_lookahead(raw, aligned)
        print(
            f"LOOK-AHEAD {label}: {check['violations']} vi phạm/"
            f"{check['checked']} mẫu"
        )
    print(f"ACTIVE FILTERS: {', '.join(sig.attrs['active_filters'])}")
    print("\nFUNNEL (solo | cumulative | killed)")
    print(funnel(sig).to_string(index=False))
    print("\nMARGINAL CONTRIBUTION")
    print(marginal_contribution(entry, main, base, cfg).to_string(index=False))
    print("\nOVERLAP (actual / expected nếu độc lập)")
    print(overlap_matrix(sig, FILTERS).to_string())
    print("\nRETRACE KHI CHẠM VALUE ZONE")
    for key, value in retrace_distribution(sig).items():
        print(f"  {key:24s}: {value}")
    print(f"\nENTRY SIGNALS: {int(sig['entry_signal'].sum())}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
