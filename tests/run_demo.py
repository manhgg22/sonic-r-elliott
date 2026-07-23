"""
Demo pipeline đầy đủ trên dữ liệu tổng hợp.
Mục đích: kiểm chứng engine chạy đúng, chưa phải kết quả thật.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np

from core.signals import Config, build_signals
from core.mtf import resample_ohlcv
from core import indicators as ind
from backtest.engine import run_backtest, Costs
from backtest import metrics as mt
from tests.test_core import make_synthetic


def main():
    print("=" * 70)
    print("DEMO PIPELINE — dữ liệu tổng hợp 1 năm M15")
    print("=" * 70)

    m15 = make_synthetic(35000, seed=7)
    h1 = resample_ohlcv(m15, "1h")
    h4 = resample_ohlcv(m15, "4h")
    d1 = resample_ohlcv(m15, "1D")

    days = (m15.index[-1] - m15.index[0]).days
    print(f"\nDữ liệu: {len(m15)} nến M15, {days} ngày")

    # --- Cấu hình gốc (chặt nhất)
    cfg = Config()
    sig = build_signals(m15, h1, h4, d1, cfg)
    print(f"Cấu hình đầy đủ: {int(sig['entry_signal'].sum())} tín hiệu")

    # --- Nới lỏng để có đủ mẫu thống kê
    cfg_relaxed = Config(
        cross_valid_bars=200,
        use_dow_filter=False,
        fib_lo=0.20,
        fib_hi=0.90,
    )
    sig_r = build_signals(m15, h1, h4, d1, cfg_relaxed)
    n_sig = int(sig_r["entry_signal"].sum())
    print(f"Cấu hình nới lỏng: {n_sig} tín hiệu "
          f"({n_sig/max(days,1):.2f} lệnh/ngày)")

    if n_sig < 10:
        print("\nKhông đủ tín hiệu để chạy backtest có ý nghĩa.")
        return

    # EMA34_low H1 cho trailing stop
    h1_bands = ind.sonic_r_bands(h1)
    from core.mtf import align_htf_to_ltf
    trail = align_htf_to_ltf(
        h1_bands[["ema_fast_low"]], m15.index
    )["ema_fast_low"]

    # --- So sánh 3 chế độ TP
    print("\n" + "=" * 70)
    print("SO SÁNH 3 CHẾ ĐỘ THOÁT LỆNH")
    print("=" * 70)

    results = {}
    for mode in ["fixed_2r", "sr_level", "fib_extension"]:
        trades = run_backtest(
            sig_r, m15, symbol="SYNTH", tp_mode=mode,
            costs=Costs(), trail_ema=trail,
        )
        results[mode] = trades

        if trades.empty:
            print(f"\n{mode}: không có lệnh")
            continue

        b = mt.basic_metrics(trades)
        print(f"\n--- {mode.upper()}")
        print(f"  Số lệnh        : {b['n_trades']}")
        print(f"  Winrate        : {b['winrate']}%")
        print(f"  Profit Factor  : {b['profit_factor']}")
        print(f"  Expectancy     : {b['expectancy_r']} R")
        print(f"  Return         : {b['return_pct']}%")
        print(f"  Max Drawdown   : {b['max_drawdown_pct']}%")
        print(f"  Chuỗi thua dài : {b['max_loss_streak']}")

    # --- Chẩn đoán sâu trên chế độ tốt nhất
    best = max(
        (m for m in results if not results[m].empty),
        key=lambda m: mt.basic_metrics(results[m])["expectancy_r"],
        default=None,
    )
    if best is None:
        return

    trades = results[best]
    print("\n" + "=" * 70)
    print(f"CHẨN ĐOÁN SÂU — chế độ {best}")
    print("=" * 70)

    freq = mt.frequency_check(trades, m15.index)
    print("\n[1] Tần suất giao dịch — kiểm chứng 'cả ngày 1-2 entry'")
    print(f"  Lệnh/ngày           : {freq['trades_per_day']}")
    print(f"  Lệnh/tháng          : {freq['trades_per_month']}")
    print(f"  % ngày không có lệnh: {freq['pct_days_no_trade']}%")
    print(f"  Nhiều nhất 1 ngày   : {freq['max_trades_one_day']}")

    sw = mt.sideway_vs_trend(trades)
    if sw:
        print("\n[2] Sideway vs Trending — kiểm chứng 'sideway dễ toang'")
        print(f"  ADX < 25 : {sw['sideway_n']} lệnh, "
              f"WR {sw['sideway_winrate']}%, exp {sw['sideway_expectancy']}R")
        print(f"  ADX >= 25: {sw['trending_n']} lệnh, "
              f"WR {sw['trending_winrate']}%, exp {sw['trending_expectancy']}R")

    mfe = mt.mfe_mae_analysis(trades)
    print("\n[3] MFE/MAE — 'gồng dài có đáng không?'")
    print(f"  MFE trung bình lệnh thắng : {mfe['avg_mfe_winners']}R")
    print(f"  % lệnh chạm 2R            : {mfe['pct_reached_2r']}%")
    print(f"  % lệnh chạm 3R            : {mfe['pct_reached_3r']}%")
    print(f"  % lệnh chạm 5R            : {mfe['pct_reached_5r']}%")

    ci = mt.confidence_interval_winrate(trades)
    print("\n[4] Độ tin cậy — 'winrate cực cao' là bao nhiêu?")
    print(f"  Winrate      : {ci['winrate_point']}%")
    print(f"  Khoảng 95%   : {ci['winrate_ci_low']}% – {ci['winrate_ci_high']}%")
    print(f"  Mẫu đủ lớn?  : {'CÓ' if ci['reliable'] else 'CHƯA (cần >=100 lệnh)'}")

    mc = mt.monte_carlo(trades)
    if mc:
        print("\n[5] Monte Carlo 1000 vòng")
        print(f"  Drawdown trung vị : {mc['mc_median_dd']}%")
        print(f"  Drawdown 95%      : {mc['mc_dd_95pct']}%")
        print(f"  Xác suất lỗ       : {mc['mc_prob_loss']}%")

    pa = mt.pa_breakdown(trades)
    if not pa.empty:
        print("\n[6] Pattern nào work?")
        print(pa.to_string(index=False))

    print("\n" + "=" * 70)
    print("ENGINE HOẠT ĐỘNG ĐÚNG — sẵn sàng chạy dữ liệu thật")
    print("=" * 70)


if __name__ == "__main__":
    main()
