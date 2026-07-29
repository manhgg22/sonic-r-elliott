"""Đo phân phối PVA trên universe thật trước khi thay đổi ngưỡng Sonic."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core import indicators as ind
from data.loader import fetch_ohlcv, okx_usdt_swap_universe


def measure_frame(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    lookback: int = 10,
    rising_mult: float = 1.5,
    climax_mult: float = 2.0,
) -> dict:
    volume = pd.to_numeric(df["volume"], errors="coerce")
    spread = (df["high"] - df["low"]).abs()
    activity = spread * volume
    average = volume.rolling(lookback, min_periods=lookback).mean().shift(1)
    previous_peak = activity.rolling(
        lookback, min_periods=lookback
    ).max().shift(1)
    ratio = volume / average.replace(0, np.nan)
    by_volume = ratio >= climax_mult
    by_spread = activity >= previous_peak
    eligible = average.notna() & previous_peak.notna()
    pva = ind.pva_signals(
        df, lookback, rising_mult=rising_mult, climax_mult=climax_mult
    )
    denominator = max(int(eligible.sum()), 1)

    def pct(mask: pd.Series) -> float:
        return 100 * int((mask & eligible).sum()) / denominator

    quantiles = ratio[eligible].quantile([0.50, 0.90, 0.95, 0.99])
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "n_bars": len(df),
        "n_eligible": int(eligible.sum()),
        "pct_rising": pct(pva["rising"]),
        "pct_climax": pct(pva["climax"]),
        "pct_climax_by_volume": pct(by_volume & ~by_spread),
        "pct_climax_by_spread": pct(by_spread & ~by_volume),
        "pct_climax_by_both": pct(by_volume & by_spread),
        "p50_ratio": float(quantiles.get(0.50, np.nan)),
        "p90_ratio": float(quantiles.get(0.90, np.nan)),
        "p95_ratio": float(quantiles.get(0.95, np.nan)),
        "p99_ratio": float(quantiles.get(0.99, np.nan)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--exchange", default="okx")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.symbols:
        symbols = args.symbols
    elif args.exchange == "okx":
        symbols = [
            row["symbol"] for row in okx_usdt_swap_universe()[:args.top]
        ]
    else:
        raise ValueError("Sàn khác OKX cần truyền --symbols rõ ràng")

    rows = []
    for symbol in symbols:
        df = fetch_ohlcv(
            symbol,
            args.timeframe,
            args.days,
            exchange_id=args.exchange,
            verbose=False,
        )
        if df.empty:
            continue
        rows.append(measure_frame(df, symbol, args.timeframe))

    report = pd.DataFrame(rows)
    if report.empty:
        raise RuntimeError("Không có dữ liệu PVA để đo")
    print(report.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    weight = report["n_eligible"].replace(0, np.nan)
    pooled_climax = float(
        (report["pct_climax"] * weight).sum() / weight.sum()
    )
    print(
        "\nCLIMAX SUMMARY: "
        f"pooled={pooled_climax:.3f}% | "
        f"median_symbol={report['pct_climax'].median():.3f}% | "
        f"min_symbol={report['pct_climax'].min():.3f}% | "
        f"max_symbol={report['pct_climax'].max():.3f}%"
    )
    print(
        "\nKẾT LUẬN NGƯỠNG: "
        + (
            "giữ 150/200"
            if report["pct_climax"].between(3, 12).all()
            else "pct_climax ngoài 3–12%; cần chủ project duyệt trước khi đổi"
        )
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
