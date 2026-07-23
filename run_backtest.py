"""
Script chạy backtest hàng loạt trên toàn bộ universe.

Dùng:
    python run_backtest.py                    # top 10, 1 năm
    python run_backtest.py --days 1095        # 3 năm
    python run_backtest.py --symbols BTC/USDT ETH/USDT
"""

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from core.signals import Config, build_signals
from core.mtf import resample_ohlcv, align_htf_to_ltf
from core import indicators as ind
from backtest.engine import run_backtest, Costs
from backtest.diagnostics import ablation_variants
from backtest import metrics as mt
from data.loader import fetch_ohlcv, TOP10, data_quality_check


def run_one(symbol, days, cfg, tp_mode):
    m15 = fetch_ohlcv(symbol, "15m", days, verbose=False)
    if m15.empty or len(m15) < 5000:
        return None, None
    quality = data_quality_check(m15, "15m")
    if not quality["ok"]:
        raise ValueError(f"Dữ liệu không hợp lệ: {quality}")

    h1 = resample_ohlcv(m15, "1h")
    h4 = resample_ohlcv(m15, "4h")
    d1 = resample_ohlcv(m15, "1D")

    sig = build_signals(m15, h1, h4, d1, cfg)
    h1_bands = ind.sonic_r_bands(h1)
    trail = align_htf_to_ltf(h1_bands[["ema_fast_low"]], m15.index)["ema_fast_low"]

    trades = run_backtest(sig, m15, symbol=symbol, tp_mode=tp_mode,
                          risk_pct=cfg.risk_pct, trail_ema=trail)
    return trades, m15.index


def run_ablation(symbols, days, cfg, tp_mode):
    rows = []
    for label, variant in ablation_variants(cfg):
        all_trades = []
        for symbol in symbols:
            trades, _ = run_one(symbol, days, variant, tp_mode)
            if trades is not None and not trades.empty:
                all_trades.append(trades)
        combined = (
            pd.concat(all_trades, ignore_index=True)
            .sort_values("entry_time")
            .reset_index(drop=True)
            if all_trades
            else pd.DataFrame()
        )
        metrics = mt.basic_metrics(combined)
        rows.append(
            {
                "config": label,
                "n_trades": metrics["n_trades"],
                "winrate": metrics.get("winrate"),
                "expectancy_r": metrics.get("expectancy_r"),
                "max_dd": metrics.get("max_drawdown_pct"),
            }
        )
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--symbols", nargs="+", default=TOP10)
    ap.add_argument("--tp", default="fixed_2r",
                    choices=["fixed_2r", "sr_level", "fib_extension"])
    ap.add_argument("--ablation", action="store_true")
    args = ap.parse_args()

    cfg = Config()
    if args.ablation:
        report = run_ablation(args.symbols, args.days, cfg, args.tp)
        print(report.to_string(index=False))
        out = Path("results")
        out.mkdir(exist_ok=True)
        report.to_csv(out / f"ablation_{args.days}d.csv", index=False)
        return

    all_trades = []
    all_indices = []

    print("=" * 70)
    print(f"BACKTEST — {len(args.symbols)} coin, {args.days} ngày, TP={args.tp}")
    print("=" * 70)

    for sym in args.symbols:
        print(f"\n{sym}")
        try:
            trades, idx = run_one(sym, args.days, cfg, args.tp)
        except Exception as e:
            print(f"  lỗi: {e}")
            continue

        if trades is None or trades.empty:
            print("  không có lệnh")
            continue

        m = mt.basic_metrics(trades)
        print(f"  {m['n_trades']} lệnh | WR {m['winrate']}% | "
              f"PF {m['profit_factor']} | exp {m['expectancy_r']}R | "
              f"DD {m['max_drawdown_pct']}%")
        all_trades.append(trades)
        all_indices.append(idx)

    if not all_trades:
        print("\nKhông có kết quả.")
        return

    combined = pd.concat(all_trades, ignore_index=True)
    combined = combined.sort_values("entry_time").reset_index(drop=True)

    print("\n" + "=" * 70)
    print("TỔNG HỢP TOÀN DANH MỤC")
    print("=" * 70)

    m = mt.basic_metrics(combined)
    for k, v in m.items():
        print(f"  {k:22s}: {v}")

    combined_index = all_indices[0].append(all_indices[1:]).unique().sort_values()
    print("\n  --- Tần suất")
    for k, v in mt.frequency_check(combined, combined_index).items():
        print(f"  {k:22s}: {v}")

    print("\n  --- Sideway vs Trending")
    for k, v in mt.sideway_vs_trend(combined).items():
        print(f"  {k:22s}: {v}")

    print("\n  --- MFE/MAE")
    for k, v in mt.mfe_mae_analysis(combined).items():
        print(f"  {k:22s}: {v}")

    print("\n  --- Độ tin cậy")
    for k, v in mt.confidence_interval_winrate(combined).items():
        print(f"  {k:22s}: {v}")

    print("\n  --- Monte Carlo")
    for k, v in mt.monte_carlo(combined).items():
        print(f"  {k:22s}: {v}")

    out = Path("results")
    out.mkdir(exist_ok=True)
    combined.to_csv(out / f"trades_{args.tp}_{args.days}d.csv", index=False)
    print(f"\nĐã lưu: results/trades_{args.tp}_{args.days}d.csv")


if __name__ == "__main__":
    main()
