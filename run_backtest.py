"""
Script chạy backtest hàng loạt trên toàn bộ universe.

Dùng:
    python run_backtest.py                    # top 10, 1 năm
    python run_backtest.py --days 1095        # 3 năm
    python run_backtest.py --symbols BTC/USDT ETH/USDT
"""

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np

from core.signals import Config, build_signals
from core.mtf import (
    align_htf_to_ltf,
    map_timeframes,
    resample_ohlcv,
    verify_no_lookahead,
)
from core.pure_sonic import PureSonicConfig, build_pure_signals
from core.classic import SonicClassicConfig, build_classic_signals
from core import indicators as ind
from backtest.engine import Costs, run_backtest
from backtest.diagnostics import ablation_variants
from backtest import metrics as mt
from backtest.regime import (
    regime_adx_d1,
    regime_btc_ma200,
    regime_btc_quarterly,
    tag_trades_with_regime,
)
from data.loader import (
    fetch_ohlcv,
    okx_usdt_swap_universe,
    top_usdt_symbols,
    TOP10,
    data_quality_check,
)


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


def run_regime_report(symbols, days):
    """T20: ba định nghĩa regime × ba TP trên cùng trade log."""
    btc_d1 = fetch_ohlcv(
        "BTC/USDT", "1D", days + 250, cache_max_age=None
    )
    if len(btc_d1) < days + 200:
        raise RuntimeError("BTC D1 không đủ 200 ngày warmup cho MA200")

    definitions = [
        ("btc_ma200", regime_btc_ma200(btc_d1), ["bull", "bear"]),
        (
            "btc_quarterly",
            regime_btc_quarterly(btc_d1),
            ["bull", "bear", "sideway"],
        ),
        ("adx_d1", regime_adx_d1(btc_d1), ["trending", "ranging"]),
    ]
    trades_by_tp = {
        tp_mode: run_universe(symbols, days, Config(), tp_mode)
        for tp_mode in ["fixed_2r", "sr_level", "fib_extension"]
    }
    entry_index = pd.DatetimeIndex(
        pd.concat(
            [trades[["entry_time"]] for trades in trades_by_tp.values()],
            ignore_index=True,
        )["entry_time"].drop_duplicates().sort_values()
    )

    checks = {}
    rows = []
    for definition, regime, labels in definitions:
        aligned = regime.to_frame().reindex(entry_index, method="ffill")
        check = verify_no_lookahead(
            regime.shift(-1).to_frame(),
            aligned,
            "regime",
            samples=max(len(entry_index), 1),
        )
        checks[definition] = check
        if not check["clean"]:
            raise RuntimeError(f"Look-ahead regime {definition}: {check}")

        for tp_mode, trades in trades_by_tp.items():
            tagged = tag_trades_with_regime(trades, regime)
            for label in labels:
                group = tagged[tagged["regime"] == label]
                metrics = mt.basic_metrics(group)
                ci = mt.wilson_edge_interval(group)
                expectancy = metrics.get("expectancy_r")
                ci_low = ci.get("wilson_ci_low")
                n_trades = metrics["n_trades"]
                rows.append({
                    "definition": definition,
                    "regime": label,
                    "tp_mode": tp_mode,
                    "n_trades": n_trades,
                    "winrate": metrics.get("winrate"),
                    "wilson_ci_low": ci_low,
                    "wilson_ci_high": ci.get("wilson_ci_high"),
                    "expectancy_r": expectancy,
                    "profit_factor": metrics.get("profit_factor"),
                    "max_dd": metrics.get("max_drawdown_pct"),
                    "sample_ok": n_trades >= 50,
                    "stat_edge": bool(
                        n_trades >= 100
                        and expectancy is not None and expectancy > 0
                        and ci_low is not None and ci_low > 0
                    ),
                })
    return pd.DataFrame(rows), checks


def _combine_trades(parts):
    if not parts:
        return pd.DataFrame()
    return (
        pd.concat(parts, ignore_index=True)
        .sort_values("entry_time")
        .reset_index(drop=True)
    )


def _pure_metrics(trades, days, n_symbols):
    metrics = mt.basic_metrics(trades, initial_balance=10000 * n_symbols)
    ci = mt.wilson_edge_interval(trades)
    mfe = mt.mfe_mae_analysis(trades)
    n_trades = metrics["n_trades"]
    expectancy = metrics.get("expectancy_r")
    ci_low = ci.get("wilson_ci_low")
    return {
        "n_trades": n_trades,
        "winrate": metrics.get("winrate"),
        "wilson_ci_low": ci_low,
        "wilson_ci_high": ci.get("wilson_ci_high"),
        "expectancy_r": expectancy,
        "profit_factor": metrics.get("profit_factor"),
        "max_dd": metrics.get("max_drawdown_pct"),
        "avg_win_r": metrics.get("avg_win_r"),
        "avg_loss_r": metrics.get("avg_loss_r"),
        "trades_per_day": round(n_trades / max(days, 1), 3),
        "avg_mfe_winners": mfe.get("avg_mfe_winners"),
        "pct_reached_2r": mfe.get("pct_reached_2r"),
        "pct_reached_3r": mfe.get("pct_reached_3r"),
        "stat_edge": bool(
            n_trades >= 150
            and expectancy is not None and expectancy > 0
            and ci_low is not None and ci_low > 0
        ),
    }


def _cache_universe(symbols, days, exchange_id):
    """Tải song song rồi bỏ DataFrame khỏi RAM; các bước sau đọc cache."""
    def cache_one(symbol):
        data = fetch_ohlcv(
            symbol,
            "15m",
            days,
            exchange_id=exchange_id,
            cache_max_age=None,
            verbose=False,
        )
        return symbol, len(data)

    failed = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(cache_one, symbol) for symbol in symbols]
        for done, future in enumerate(as_completed(futures), 1):
            symbol, bars = future.result()
            if bars == 0:
                failed.append(symbol)
            if done % 5 == 0 or done == len(symbols):
                print(f"  cache {exchange_id}: {done}/{len(symbols)}")

    for symbol in failed:
        _, bars = cache_one(symbol)
        if bars == 0:
            raise RuntimeError(f"Không tải được dữ liệu Binance cho {symbol}")


def _load_entry_main(symbol, days, exchange_id):
    entry = fetch_ohlcv(
        symbol,
        "15m",
        days,
        exchange_id=exchange_id,
        cache_max_age=None,
        verbose=False,
    )
    if entry.empty:
        raise RuntimeError(f"Không có dữ liệu {symbol}")
    quality = data_quality_check(entry, "15m")
    if not quality["ok"]:
        raise RuntimeError(f"Dữ liệu {symbol} không hợp lệ: {quality}")
    return entry, resample_ohlcv(entry, "1h")


def _run_pure_universe(
    symbols, days, exchange_id, cfg, tp_modes, costs=None
):
    parts = {tp_mode: [] for tp_mode in tp_modes}
    for symbol in symbols:
        entry, main = _load_entry_main(symbol, days, exchange_id)
        sig = build_pure_signals(entry, main, cfg)
        main_bands = ind.sonic_r_bands(main, cfg.ema_fast, cfg.ema_slow)
        trail = align_htf_to_ltf(
            main_bands[["ema_fast_low"]], entry.index
        )["ema_fast_low"]
        for tp_mode in tp_modes:
            trades = run_backtest(
                sig,
                entry,
                symbol=symbol,
                tp_mode=tp_mode,
                costs=costs or Costs(0, 0, 0),
                max_bars=500,
                trail_ema=trail,
            )
            if not trades.empty:
                parts[tp_mode].append(trades)
    return {mode: _combine_trades(items) for mode, items in parts.items()}


def _run_existing_binance(symbols, days, exchange_id, tp_mode):
    parts = []
    cfg = Config.m15_entry()
    for symbol in symbols:
        entry, main = _load_entry_main(symbol, days, exchange_id)
        base = resample_ohlcv(entry, "4h")
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
            costs=Costs(0, 0, 0),
            max_bars=cfg.max_bars,
            trail_ema=trail,
        )
        if not trades.empty:
            parts.append(trades)
    return _combine_trades(parts)


def run_pure_sonic_report(symbols, days, exchange_id):
    """Ba TP, bốn ablation và đối chứng 7-filter — đều không phí."""
    _cache_universe(symbols, days, exchange_id)
    tp_modes = ["fixed_2r", "sr_level", "fib_extension"]
    full_cfg = PureSonicConfig()
    pure_trades = _run_pure_universe(
        symbols, days, exchange_id, full_cfg, tp_modes
    )

    tp_rows = []
    for tp_mode, trades in pure_trades.items():
        tp_rows.append({
            "tp_mode": tp_mode,
            **_pure_metrics(trades, days, len(symbols)),
        })
    tp_report = pd.DataFrame(tp_rows)
    best_tp = tp_report.sort_values(
        ["expectancy_r", "n_trades"], ascending=False
    ).iloc[0]["tp_mode"]

    ablation_rows = [{
        "config": "Đầy đủ 4 bước",
        **_pure_metrics(pure_trades[best_tp], days, len(symbols)),
    }]
    for label, cfg in [
        ("Bỏ breakout", replace(full_cfg, use_breakout=False)),
        ("Bỏ Price Action", replace(full_cfg, use_pa=False)),
        (
            "Chỉ trend + Value Zone",
            replace(full_cfg, use_breakout=False, use_pa=False),
        ),
    ]:
        trades = _run_pure_universe(
            symbols, days, exchange_id, cfg, [best_tp]
        )[best_tp]
        ablation_rows.append({
            "config": label,
            **_pure_metrics(trades, days, len(symbols)),
        })
    ablation_report = pd.DataFrame(ablation_rows)

    comparison_tp = "fixed_2r"
    existing = _run_existing_binance(
        symbols, days, exchange_id, comparison_tp
    )
    comparison_rows = []
    for system, trades in [
        ("Sonic R thuần", pure_trades[comparison_tp]),
        ("Hệ thống 7-filter", existing),
    ]:
        metrics = _pure_metrics(trades, days, len(symbols))
        comparison_rows.append({
            "system": system,
            "tp_mode": comparison_tp,
            "n_trades": metrics["n_trades"],
            "expectancy_r": metrics["expectancy_r"],
            "avg_mfe_winners": metrics["avg_mfe_winners"],
            "pct_reached_3r": metrics["pct_reached_3r"],
            "max_dd": metrics["max_dd"],
        })
    return (
        tp_report,
        ablation_report,
        pd.DataFrame(comparison_rows),
        best_tp,
    )


def _classic_diagnostics(signal_parts, trades):
    candidates = sum(int(sig["risk_candidate"].sum()) for sig in signal_parts)
    rejected_wide = sum(
        int(sig["rejected_reason"].eq("SL_TOO_WIDE").sum())
        for sig in signal_parts
    )
    rejected_tight = sum(
        int(sig["rejected_reason"].eq("SL_TOO_TIGHT").sum())
        for sig in signal_parts
    )
    sources = (
        trades["tp_source"]
        if not trades.empty and "tp_source" in trades
        else pd.Series(dtype=object)
    )
    distribution = sources.value_counts(normalize=True)

    funding_pct_r = 0.0
    funding_net = 0.0
    funding_debit = 0.0
    funding_credit = 0.0
    funding_periods = 0
    weekend_n = 0
    weekend_expectancy = None
    if not trades.empty:
        total_risk = trades["risk_amount"].sum()
        funding_net = float(trades["funding_pnl"].sum())
        funding_debit = float(-trades.loc[trades["funding_pnl"] < 0, "funding_pnl"].sum())
        funding_credit = float(trades.loc[trades["funding_pnl"] > 0, "funding_pnl"].sum())
        funding_periods = int(trades["funding_periods"].sum())
        if total_risk:
            funding_pct_r = 100 * funding_net / total_risk
        timestamps = pd.to_datetime(trades["entry_time"], utc=True)
        weekend = trades.loc[timestamps.dt.weekday >= 5]
        weekend_n = len(weekend)
        if weekend_n:
            weekend_expectancy = float(weekend["r_multiple"].mean())
    risk_groups = {}
    if signal_parts:
        all_signals = pd.concat(signal_parts, ignore_index=True)
        ratio = all_signals["risk"] / all_signals["adr"]
        for label, mask in {
            "accepted": all_signals["entry_signal"],
            "rejected": all_signals["rejected_reason"].ne(""),
        }.items():
            quantiles = ratio[mask & np.isfinite(ratio)].quantile(
                [0.10, 0.50, 0.90, 0.95]
            )
            for q, name in [(0.10, "p10"), (0.50, "p50"), (0.90, "p90"), (0.95, "p95")]:
                risk_groups[f"risk_adr_{label}_{name}"] = (
                    round(float(quantiles.loc[q]), 4)
                    if q in quantiles and pd.notna(quantiles.loc[q])
                    else None
                )
    return {
        "candidate_setups": candidates,
        "pct_rejected_sl_too_wide": (
            round(100 * rejected_wide / candidates, 2) if candidates else 0.0
        ),
        "pct_rejected_sl_too_tight": (
            round(100 * rejected_tight / candidates, 2) if candidates else 0.0
        ),
        "tp_sr_level_pct": round(100 * distribution.get("sr_level", 0), 2),
        "tp_rdh_pct": round(100 * distribution.get("rdh", 0), 2),
        "tp_rdl_pct": round(100 * distribution.get("rdl", 0), 2),
        "tp_fixed_r_pct": round(100 * distribution.get("fixed_r", 0), 2),
        "tp_fallback_no_sr_pct": round(
            100 * distribution.get("fallback_no_sr", 0), 2
        ),
        "tp_fallback_invalid_rdh_rdl_pct": round(
            100 * distribution.get("fallback_invalid_rdh_rdl", 0), 2
        ),
        "funding_net": round(funding_net, 6),
        "funding_debit": round(funding_debit, 6),
        "funding_credit": round(funding_credit, 6),
        "funding_periods": funding_periods,
        "funding_pct_r": round(funding_pct_r, 4),
        "weekend_trades": weekend_n,
        "weekend_expectancy_r": (
            round(weekend_expectancy, 4)
            if weekend_expectancy is not None else None
        ),
        **risk_groups,
    }


def _run_classic_universe(symbols, days, exchange_id, cfg):
    trade_parts = []
    signal_parts = []
    lookahead_violations = 0
    for symbol in symbols:
        entry, main = _load_entry_main(symbol, days, exchange_id)
        daily = resample_ohlcv(entry, "1D")
        h1_aligned = align_htf_to_ltf(main[["close"]], entry.index)
        d1_aligned = align_htf_to_ltf(daily[["close"]], entry.index)
        lookahead_violations += verify_no_lookahead(
            main[["close"]], h1_aligned
        )["violations"]
        lookahead_violations += verify_no_lookahead(
            daily[["close"]], d1_aligned
        )["violations"]

        for side in ("LONG", "SHORT"):
            sig = build_classic_signals(entry, main, daily, cfg, side)
            signal_parts.append(sig)
            trades = run_backtest(
                sig,
                entry,
                symbol=symbol,
                tp_mode=cfg.tp_mode,
                costs=Costs(),
                max_bars=500,
                pending_expiry_bars=cfg.pending_expiry_bars,
            )
            if not trades.empty:
                trade_parts.append(trades)
    if lookahead_violations:
        raise RuntimeError(
            f"Classic có {lookahead_violations} vi phạm look-ahead MTF"
        )
    combined = _combine_trades(trade_parts)
    return combined, _classic_diagnostics(signal_parts, combined)


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_classic_manifest(path, symbols, days, exchange_id):
    if path is None:
        raise ValueError(
            "--classic bắt buộc có --validation-manifest đã commit trước"
        )
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "venue", "market_type", "instruments", "start_utc", "end_utc",
        "timeframe", "requested_days", "files", "funding_source",
        "code_commit", "code_files", "config", "primary_tp_mode", "ablations",
        "random_seed",
    }
    missing = required.difference(manifest)
    if missing:
        raise ValueError(f"Validation manifest thiếu field: {sorted(missing)}")
    if manifest["venue"] != exchange_id:
        raise ValueError("Venue CLI không khớp validation manifest")
    if manifest["market_type"] != "linear_usdt_perpetual":
        raise ValueError("Classic validation chỉ nhận linear USDT perpetual")
    if manifest["timeframe"] != "15m" or manifest["requested_days"] != days:
        raise ValueError("Timeframe/days CLI không khớp validation manifest")
    if list(manifest["instruments"]) != list(symbols):
        raise ValueError("Danh sách/order instrument không khớp validation manifest")
    if manifest["primary_tp_mode"] != "sr_level":
        raise ValueError("Primary TP phải được khóa là sr_level")
    if manifest["config"] != asdict(SonicClassicConfig()):
        raise ValueError("Config hiện tại không khớp config đã đăng ký")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", manifest["code_commit"], commit],
        capture_output=True,
    )
    if ancestry.returncode != 0:
        raise ValueError("Code commit trong manifest không phải ancestor hiện tại")
    for item in manifest["code_files"]:
        code_path = Path(item["path"])
        if not code_path.exists() or _file_sha256(code_path) != item["sha256"]:
            raise ValueError(f"Code đã đổi sau khi đăng ký: {code_path}")
    for item in manifest["files"]:
        file_path = Path(item["path"])
        if not file_path.exists():
            raise ValueError(f"Thiếu data file trong manifest: {file_path}")
        if file_path.stat().st_size != item["size"]:
            raise ValueError(f"Size data đã đổi: {file_path}")
        if _file_sha256(file_path) != item["sha256"]:
            raise ValueError(f"SHA-256 data đã đổi: {file_path}")
    return manifest


def run_classic_report(symbols, days, exchange_id, manifest_path):
    """Ba TP mode, bốn ablation đăng ký trước và đối chứng Pure Sonic."""
    _validate_classic_manifest(
        manifest_path, symbols, days, exchange_id
    )
    _cache_universe(symbols, days, exchange_id)
    base = SonicClassicConfig()
    tp_rows = []
    main_trades = {}
    main_diagnostics = {}
    for mode in ("sr_level", "rdh_rdl", "fixed_r"):
        cfg = replace(base, tp_mode=mode)
        trades, diagnostics = _run_classic_universe(
            symbols, days, exchange_id, cfg
        )
        main_trades[mode] = trades
        main_diagnostics[mode] = diagnostics
        tp_rows.append({
            "tp_mode": mode,
            **_pure_metrics(trades, days, len(symbols)),
            **diagnostics,
        })
    tp_report = pd.DataFrame(tp_rows)

    ablation_rows = []
    for label, cfg in [
        ("baseline", base),
        ("require_leg1_cross", replace(base, require_leg1_cross=True)),
        (
            "no_sl_adr_gate",
            replace(base, sl_max_adr=None),
        ),
        ("sonic_ny_session", replace(base, session_filter="sonic_ny")),
        ("pivot_right_5", replace(base, pivot_right=5)),
    ]:
        trades, diagnostics = (
            (main_trades["sr_level"], main_diagnostics["sr_level"])
            if label == "baseline"
            else _run_classic_universe(symbols, days, exchange_id, cfg)
        )
        ablation_rows.append({
            "config": label,
            **_pure_metrics(trades, days, len(symbols)),
            **diagnostics,
        })
    ablation_report = pd.DataFrame(ablation_rows)

    pure = _run_pure_universe(
        symbols,
        days,
        exchange_id,
        PureSonicConfig(),
        ["sr_level"],
        costs=Costs(),
    )["sr_level"]
    comparison = pd.DataFrame([
        {"system": "pure_sonic", **_pure_metrics(pure, days, len(symbols))},
        {
            "system": "classic_sr_level",
            **_pure_metrics(main_trades["sr_level"], days, len(symbols)),
        },
    ])
    return tp_report, ablation_report, comparison


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--symbols", nargs="+")
    ap.add_argument("--exchange", default="binance")
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--validation-manifest", type=Path)
    ap.add_argument("--tp", default="fixed_2r",
                    choices=["fixed_2r", "sr_level", "fib_extension"])
    reports = ap.add_mutually_exclusive_group()
    reports.add_argument("--ablation", action="store_true")
    reports.add_argument("--tp-matrix", action="store_true")
    reports.add_argument("--mfe-report", action="store_true")
    reports.add_argument("--pa-breakdown", action="store_true")
    reports.add_argument("--regime-report", action="store_true")
    reports.add_argument("--pure-sonic", action="store_true")
    reports.add_argument("--classic", action="store_true")
    args = ap.parse_args()

    if args.classic:
        if args.symbols:
            symbols = args.symbols
        elif args.exchange == "okx":
            symbols = [
                row["symbol"] for row in okx_usdt_swap_universe()[:args.top]
            ]
        else:
            symbols = top_usdt_symbols(args.exchange, args.top)
        print(
            f"SONIC CLASSIC — {args.exchange}, {len(symbols)} coin, "
            f"{args.days} ngày, funding giả định 0.01%/8h"
        )
        tp_report, ablation, comparison = run_classic_report(
            symbols, args.days, args.exchange, args.validation_manifest
        )
        print("\n3 TP MODES")
        print(tp_report.to_string(index=False))
        print("\n4 ABLATIONS ĐĂNG KÝ TRƯỚC")
        print(ablation.to_string(index=False))
        print("\nCLASSIC VS PURE SONIC")
        print(comparison.to_string(index=False))
        primary_edge = bool(
            tp_report.loc[
                tp_report["tp_mode"] == "sr_level", "stat_edge"
            ].iloc[0]
        )
        verdict = (
            "PRIMARY SR_LEVEL CÓ BẰNG CHỨNG EDGE"
            if primary_edge
            else "PRIMARY SR_LEVEL KHÔNG ĐẠT CỔNG EDGE"
        )
        print(f"\nKẾT LUẬN: {verdict}")
        out = Path("results")
        out.mkdir(exist_ok=True)
        tp_report.to_csv(
            out / f"classic_tp_{args.days}d.csv", index=False
        )
        ablation.to_csv(
            out / f"classic_ablation_{args.days}d.csv", index=False
        )
        comparison.to_csv(
            out / f"classic_vs_pure_{args.days}d.csv", index=False
        )
        return

    if args.pure_sonic:
        symbols = args.symbols or top_usdt_symbols(args.exchange, args.top)
        print(
            f"PURE SONIC — {args.exchange}, {len(symbols)} coin, "
            f"{args.days} ngày, KHÔNG PHÍ"
        )
        tp_report, ablation, comparison, best_tp = run_pure_sonic_report(
            symbols, args.days, args.exchange
        )
        print("\n3 TP MODES")
        print(tp_report.to_string(index=False))
        print(f"\nBEST TP: {best_tp}")
        print("\nABLATION")
        print(ablation.to_string(index=False))
        print("\nPURE VS 7-FILTER")
        print(comparison.to_string(index=False))
        verdict = (
            "TÌM THẤY EDGE"
            if tp_report["stat_edge"].any()
            else "KHÔNG CÓ TP MODE NÀO ĐẠT STAT_EDGE"
        )
        print(f"\nKẾT LUẬN: {verdict}")

        out = Path("results")
        out.mkdir(exist_ok=True)
        tp_report.to_csv(
            out / f"pure_sonic_tp_{args.days}d.csv", index=False
        )
        ablation.to_csv(
            out / f"pure_sonic_ablation_{args.days}d.csv", index=False
        )
        comparison.to_csv(
            out / f"pure_vs_7filter_{args.days}d.csv", index=False
        )
        return

    args.symbols = args.symbols or TOP10
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

    if args.regime_report:
        report, checks = run_regime_report(args.symbols, args.days)
        for name, check in checks.items():
            print(
                f"LOOK-AHEAD {name}: {check['violations']} vi phạm/"
                f"{check['checked']} mẫu"
            )
        print(report.to_string(index=False))
        verdict = (
            "TÌM THẤY ỨNG VIÊN EDGE — PHẢI CHẠY T21"
            if report["stat_edge"].any()
            else "KHÔNG CÓ REGIME NÀO ĐẠT EDGE CÓ Ý NGHĨA THỐNG KÊ"
        )
        print(f"KẾT LUẬN: {verdict}")
        out = Path("results")
        out.mkdir(exist_ok=True)
        report.to_csv(out / f"regime_report_{args.days}d.csv", index=False)
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
