"""Sensitivity sweep cho các tham số Sonic R + Elliott."""

import argparse
import sys
from itertools import product
from pathlib import Path

import pandas as pd

from backtest.diagnostics import load_data
from backtest.engine import run_backtest
from backtest.metrics import basic_metrics
from core.signals import Config, build_signals


GRID = {
    "adx_min": [15, 18, 20, 25],
    "separation_min": [0.2, 0.35, 0.5, 0.7],
    "fib_lo": [0.20, 0.25, 0.30],
    "fib_hi": [0.75, 0.85, 0.95],
    "zz_left": [3, 5, 8],
    "swing_max_age": [100, 200, 400],
}


def _edge_params(params: dict) -> list[str]:
    return [
        name
        for name, values in GRID.items()
        if params[name] in (values[0], values[-1])
    ]


def _has_eligible_neighbor(row: pd.Series, eligible: set[tuple]) -> bool:
    names = list(GRID)
    values = [row[name] for name in names]
    for i, name in enumerate(names):
        position = GRID[name].index(values[i])
        for adjacent in (position - 1, position + 1):
            if 0 <= adjacent < len(GRID[name]):
                neighbor = values.copy()
                neighbor[i] = GRID[name][adjacent]
                if tuple(neighbor) in eligible:
                    return True
    return False


def run_sweep(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
    d1: pd.DataFrame,
    tp_mode: str = "fixed_2r",
) -> pd.DataFrame:
    """Chạy toàn bộ GRID và trả về bảng đã xếp theo gate QA."""
    names = list(GRID)
    days = max(int(m15.index.normalize().nunique()), 1)
    rows = []
    structural = product(GRID["zz_left"], GRID["swing_max_age"])
    thresholds = product(
        GRID["adx_min"],
        GRID["separation_min"],
        GRID["fib_lo"],
        GRID["fib_hi"],
    )
    thresholds = list(thresholds)
    for zz_left, swing_max_age in structural:
        cfg = Config(zz_left=zz_left, swing_max_age=swing_max_age)
        sig = build_signals(m15, h1, h4, d1, cfg)
        static = sig[
            ["f_d1", "f_h4", "f_cross", "f_dow", "f_value_zone", "f_pa"]
        ].all(axis=1)
        engine_columns = [
            "sl",
            "adx",
            "retrace_pct",
            "pa_engulfing",
            "pa_pinbar",
            "pa_bos",
        ]
        if tp_mode == "fib_extension":
            engine_columns += ["tp_fib_1618", "tp_fib_2618"]

        for adx_min, separation_min, fib_lo, fib_hi in thresholds:
            params = {
                "adx_min": adx_min,
                "separation_min": separation_min,
                "fib_lo": fib_lo,
                "fib_hi": fib_hi,
                "zz_left": zz_left,
                "swing_max_age": swing_max_age,
            }
            entry = (
                static
                & (sig["adx"] > adx_min)
                & (sig["separation"] > separation_min)
                & sig["retrace_pct"].between(fib_lo, fib_hi)
            )
            if entry.any():
                engine_sig = sig[engine_columns].copy()
                engine_sig["entry_signal"] = entry
                trades = run_backtest(
                    engine_sig,
                    m15,
                    symbol="SWEEP",
                    tp_mode=tp_mode,
                    risk_pct=cfg.risk_pct,
                )
            else:
                trades = pd.DataFrame()
            metrics = basic_metrics(trades)
            n_trades = int(metrics["n_trades"])
            per_day = n_trades / days
            edge = _edge_params(params)
            rows.append(
                {
                    **params,
                    "n_trades": n_trades,
                    "trades_per_day": round(per_day, 3),
                    "winrate": metrics.get("winrate"),
                    "expectancy_r": metrics.get("expectancy_r"),
                    "max_dd": metrics.get("max_drawdown_pct"),
                    "eligible": n_trades >= 100 and 0.3 <= per_day <= 2.0,
                    "is_edge_of_grid": bool(edge),
                    "edge_params": ",".join(edge),
                }
            )

    result = pd.DataFrame(rows)
    eligible = {
        tuple(row[name] for name in names)
        for _, row in result[result["eligible"]].iterrows()
    }
    result["has_eligible_neighbor"] = result.apply(
        _has_eligible_neighbor, axis=1, eligible=eligible
    )
    result["stable_candidate"] = (
        result["eligible"]
        & ~result["is_edge_of_grid"]
        & result["has_eligible_neighbor"]
    )
    result = result.sort_values(
        ["stable_candidate", "eligible", "is_edge_of_grid", "expectancy_r"],
        ascending=[False, False, True, False],
        na_position="last",
        ignore_index=True,
    )
    result["recommended"] = False
    candidates = result.index[result["stable_candidate"]]
    if len(candidates):
        result.loc[candidates[0], "recommended"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument(
        "--tp",
        choices=["fixed_2r", "sr_level", "fib_extension"],
        default="fixed_2r",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    m15, h1, h4, d1 = load_data(args.symbol, args.days, args.synthetic)
    result = run_sweep(m15, h1, h4, d1, args.tp)
    source = "synthetic" if args.synthetic else args.symbol.replace("/", "_")
    output = args.output or Path("results") / f"sweep_{source}_{args.days}d.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)

    print(f"\nSENSITIVITY SWEEP — {source}, {args.days} ngày, {len(result)} configs")
    print(f"Đủ gate QA: {int(result['eligible'].sum())}")
    print(f"Ứng viên ổn định: {int(result['stable_candidate'].sum())}")
    print(f"Đã lưu: {output}")
    print("\nTOP 20")
    print(result.head(20).to_string(index=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
