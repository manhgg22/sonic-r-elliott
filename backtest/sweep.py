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
    "cross_mode": ["state", "event"],
    "fib_lo": [0.20, 0.30, 0.382],
    "fib_hi": [0.618, 0.75, 0.90],
    "adx_min": [15, 20, 25],
    "zz_left": [3, 5, 8],
}


def _edge_params(params: dict) -> list[str]:
    return [
        name
        for name, values in GRID.items()
        if name != "cross_mode" and params[name] in (values[0], values[-1])
    ]


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
    for values in product(*(GRID[name] for name in names)):
        params = dict(zip(names, values))
        cfg = Config(
            **params,
            use_d1_filter=True,
            use_h4_filter=True,
            use_separation_filter=True,
            use_dow_filter=True,
            use_fib_filter=True,
        )
        sig = build_signals(m15, h1, h4, d1, cfg)
        trades = run_backtest(
            sig,
            m15,
            symbol="SWEEP",
            tp_mode=tp_mode,
            risk_pct=cfg.risk_pct,
        )
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
                "is_edge": bool(edge),
                "edge_params": ",".join(edge),
            }
        )

    result = pd.DataFrame(rows).sort_values(
        ["eligible", "is_edge", "expectancy_r"],
        ascending=[False, True, False],
        na_position="last",
        ignore_index=True,
    )
    result["recommended"] = False
    candidates = result.index[result["eligible"] & ~result["is_edge"]]
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
    print(f"Đã lưu: {output}")
    print("\nTOP 20")
    print(result.head(20).to_string(index=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
