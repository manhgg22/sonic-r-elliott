"""
Script chạy backtest hàng loạt trên toàn bộ universe.

Dùng:
    python run_backtest.py                    # top 10, 1 năm
    python run_backtest.py --days 1095        # 3 năm
    python run_backtest.py --symbols BTC/USDT ETH/USDT
"""

import argparse
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from core.signals import Config, build_signals
from core.mtf import align_htf_to_ltf, map_timeframes
from core import indicators as ind
from backtest.engine import run_backtest
from backtest.diagnostics import ablation_variants
from backtest import metrics as mt
from data.loader import fetch_ohlcv, TOP10, data_quality_check


def run_one(symbol, days, cfg, tp_mode, cache_max_age=3600):
    m15 = fetch_ohlcv(
        symbol, "15m", days, verbose=False, cache_max_age=cache_max_age
    )
    if m15.empty:
        return None, None
    latest_allowed = pd.Timestamp.now(tz="UTC") - timedelta(days=1)
    if len(m15) < days * 96 * 0.9 or m15.index.max() < latest_allowed:
        raise ValueError(
            f"Dữ liệu {symbol} không đủ {days} ngày: "
            f"{len(m15)} nến, kết thúc {m15.index.max()}"
        )
    quality = data_quality_check(m15, "15m")
    if not quality["ok"]:
        raise ValueError(f"Dữ liệu không hợp lệ: {quality}")

    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )

    sig = build_signals(entry, main, base, cfg)
    main_bands = ind.sonic_r_bands(main)
    trail = align_htf_to_ltf(
        main_bands[["ema_fast_low"]], entry.index
    )["ema_fast_low"]

    trades = run_backtest(
        sig,
        entry,
        symbol=symbol,
        tp_mode=tp_mode,
        risk_pct=cfg.risk_pct,
        max_bars=cfg.max_bars,
        trail_ema=trail,
    )
    return trades, entry.index


def run_universe(symbols, days, cfg, tp_mode):
    all_trades = []
    for symbol in symbols:
        trades, _ = run_one(symbol, days, cfg, tp_mode, cache_max_age=None)
        if trades is None:
            raise RuntimeError(f"Thiếu dữ liệu đầy đủ cho {symbol}")
        if not trades.empty:
            all_trades.append(trades)
    if not all_trades:
        return pd.DataFrame()
    return (
        pd.concat(all_trades, ignore_index=True)
        .sort_values("entry_time")
        .reset_index(drop=True)
    )


def run_ablation(symbols, days, cfg, tp_mode):
    rows = []
    for label, variant in ablation_variants(cfg):
        combined = run_universe(symbols, days, variant, tp_mode)
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


def _tp_configs(base_cfg):
    return [
        ("Đầy đủ mới", replace(base_cfg)),
        ("Bỏ PA", replace(base_cfg, require_pa=False)),
        ("Thêm Fibo", replace(base_cfg, use_fib_filter=True)),
    ]


def _matrix_rows(symbols, days, base_cfg):
    rows = []
    for config_name, cfg in _tp_configs(base_cfg):
        for tp_mode in ["fixed_2r", "sr_level", "fib_extension"]:
            trades = run_universe(symbols, days, cfg, tp_mode)
            metrics = mt.basic_metrics(trades)
            edge_ci = mt.wilson_edge_interval(trades)
            expectancy = metrics.get("expectancy_r")
            ci_low = edge_ci.get("wilson_ci_low")
            rows.append({
                "config": config_name,
                "tp_mode": tp_mode,
                "n_trades": metrics["n_trades"],
                "winrate": metrics.get("winrate"),
                "wilson_ci_low": ci_low,
                "wilson_ci_high": edge_ci.get("wilson_ci_high"),
                "expectancy_r": expectancy,
                "max_dd": metrics.get("max_drawdown_pct"),
                "avg_win_r": metrics.get("avg_win_r"),
                "avg_loss_r": metrics.get("avg_loss_r"),
                "cost_pct_of_r": (
                    round((abs(metrics["avg_loss_r"]) - 1) * 100, 2)
                    if metrics.get("avg_loss_r") is not None
                    else None
                ),
                "profit_factor": metrics.get("profit_factor"),
                "expectancy_positive": bool(expectancy is not None and expectancy > 0),
                "ci_positive": bool(ci_low is not None and ci_low > 0),
                "stat_edge": bool(
                    metrics["n_trades"] >= 150
                    and expectancy is not None and expectancy > 0
                    and ci_low is not None and ci_low > 0
                ),
                "tf_entry": cfg.tf_entry,
                "adx_min": cfg.adx_min,
                "separation_min": cfg.separation_min,
            })
    return rows


def run_tp_matrix(symbols, days):
    """T17: H1 3x3, có đối chứng M15 và relaxation T18 đúng thứ tự."""
    cfg = Config()
    rows = _matrix_rows(symbols, days, cfg)

    # T18: chỉ nới đúng hai ngưỡng đã duyệt, dựa trên ô đầy đủ/fixed_2r.
    if rows[0]["n_trades"] < 150:
        cfg = replace(cfg, adx_min=15)
        rows = _matrix_rows(symbols, days, cfg)
    if rows[0]["n_trades"] < 150:
        cfg = replace(cfg, separation_min=0.25)
        rows = _matrix_rows(symbols, days, cfg)

    h1_report = pd.DataFrame(rows)
    m15_cfg = replace(
        Config.m15_entry(),
        adx_min=cfg.adx_min,
        separation_min=cfg.separation_min,
    )
    m15_report = pd.DataFrame(_matrix_rows(symbols, days, m15_cfg))
    compare = m15_report.set_index(["config", "tp_mode"])

    for column in [
        "n_trades", "expectancy_r", "avg_loss_r", "cost_pct_of_r"
    ]:
        h1_report[f"m15_{column}"] = [
            compare.loc[(row.config, row.tp_mode), column]
            for row in h1_report.itertuples()
        ]
    h1_report["delta_expectancy_vs_m15"] = (
        h1_report["expectancy_r"] - h1_report["m15_expectancy_r"]
    ).round(3)
    h1_report["delta_cost_pct_vs_m15"] = (
        h1_report["cost_pct_of_r"] - h1_report["m15_cost_pct_of_r"]
    ).round(2)
    return h1_report


def run_mfe_report(symbols, days):
    trades = run_universe(symbols, days, Config(), "fixed_2r")
    report = mt.mfe_mae_analysis(trades)
    avg_mfe = report["avg_mfe_winners"]
    if report["pct_reached_3r"] > 25 or avg_mfe > 2.4:
        conclusion = "TP hiện tại quá sớm."
    elif avg_mfe < 1.8:
        conclusion = "TP hiện tại quá muộn."
    else:
        conclusion = "TP hiện tại vừa."
    return report, conclusion


def run_pa_report(symbols, days):
    baseline = run_universe(symbols, days, Config(), "fixed_2r")
    breakdown = mt.pa_breakdown(baseline)
    rows = []
    configs = [
        ("Engulfing + pinbar", Config(pa_patterns=("engulfing", "pinbar"))),
        ("Chỉ engulfing", Config(pa_patterns=("engulfing",))),
        ("Không PA", Config(require_pa=False)),
    ]
    for label, cfg in configs:
        metrics = mt.basic_metrics(run_universe(symbols, days, cfg, "fixed_2r"))
        rows.append({
            "config": label,
            "n_trades": metrics["n_trades"],
            "winrate": metrics.get("winrate"),
            "expectancy_r": metrics.get("expectancy_r"),
        })
    return breakdown, pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--symbols", nargs="+", default=TOP10)
    ap.add_argument("--tp", default="fixed_2r",
                    choices=["fixed_2r", "sr_level", "fib_extension"])
    reports = ap.add_mutually_exclusive_group()
    reports.add_argument("--ablation", action="store_true")
    reports.add_argument("--tp-matrix", action="store_true")
    reports.add_argument("--mfe-report", action="store_true")
    reports.add_argument("--pa-breakdown", action="store_true")
    args = ap.parse_args()

    cfg = Config()
    if args.ablation:
        report = run_ablation(args.symbols, args.days, cfg, args.tp)
        print(report.to_string(index=False))
        out = Path("results")
        out.mkdir(exist_ok=True)
        report.to_csv(out / f"ablation_{args.days}d.csv", index=False)
        return

    if args.tp_matrix:
        report = run_tp_matrix(args.symbols, args.days)
        print("Wilson CI = điểm % winrate vượt ngưỡng hòa vốn")
        print(report.to_string(index=False))
        baseline = report.iloc[0]
        print(
            "T16/T18: "
            f"{baseline['tf_entry']} entry, ADX>={baseline['adx_min']}, "
            f"separation>{baseline['separation_min']}, "
            f"n={int(baseline['n_trades'])}"
        )
        verdict = (
            "TÌM THẤY EDGE"
            if report["stat_edge"].any()
            else "KHÔNG CÓ Ô NÀO ĐẠT EDGE CÓ Ý NGHĨA THỐNG KÊ"
        )
        print(f"KẾT LUẬN: {verdict}")
        out = Path("results")
        out.mkdir(exist_ok=True)
        report.to_csv(out / f"tp_matrix_{args.days}d.csv", index=False)
        return

    if args.mfe_report:
        report, conclusion = run_mfe_report(args.symbols, args.days)
        for key in [
            "avg_mfe_winners", "pct_reached_2r", "pct_reached_3r",
            "pct_reached_5r", "avg_mae_winners",
        ]:
            print(f"{key:20s}: {report[key]}")
        print(f"KẾT LUẬN: {conclusion}")
        return

    if args.pa_breakdown:
        breakdown, report = run_pa_report(args.symbols, args.days)
        print("PA BREAKDOWN")
        print(breakdown.to_string(index=False))
        print("\nPA CONFIG TEST")
        print(report.to_string(index=False))
        worst = breakdown.sort_values("expectancy_r").iloc[0]
        print(
            f"KẾT LUẬN: {worst['pa_type']} kéo nhóm xuống mạnh nhất "
            f"({worst['expectancy_r']:+.3f}R)."
        )
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
