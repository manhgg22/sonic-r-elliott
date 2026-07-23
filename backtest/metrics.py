"""
Metrics — không chỉ winrate, mà là các con số trả lời trực tiếp
những niềm tin trong phương pháp gốc.
"""

import numpy as np
import pandas as pd


def basic_metrics(trades: pd.DataFrame, initial_balance: float = 10000) -> dict:
    """Bộ chỉ số chuẩn."""
    if trades.empty:
        return {"n_trades": 0}

    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]

    gross_win = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())

    equity = initial_balance + trades["pnl"].cumsum()
    running_max = equity.cummax().clip(lower=initial_balance)
    dd = (equity - running_max) / running_max
    max_dd = abs(dd.min()) * 100 if len(dd) else 0

    # Chuỗi thua dài nhất
    is_loss = (trades["pnl"] <= 0).astype(int)
    streak, max_streak = 0, 0
    for v in is_loss:
        streak = streak + 1 if v else 0
        max_streak = max(max_streak, streak)

    r = trades["r_multiple"]

    return {
        "n_trades": len(trades),
        "winrate": round(100 * len(wins) / len(trades), 2),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else np.inf,
        "expectancy_r": round(r.mean(), 3),
        "net_pnl": round(trades["pnl"].sum(), 2),
        "return_pct": round(100 * trades["pnl"].sum() / initial_balance, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "max_loss_streak": int(max_streak),
        "avg_win_r": round(wins["r_multiple"].mean(), 3) if len(wins) else 0,
        "avg_loss_r": round(losses["r_multiple"].mean(), 3) if len(losses) else 0,
        "best_trade_r": round(r.max(), 2),
        "worst_trade_r": round(r.min(), 2),
        "avg_bars_held": round(trades["bars_held"].mean(), 1),
    }


def frequency_check(trades: pd.DataFrame, m15_index: pd.DatetimeIndex) -> dict:
    """
    Kiểm chứng niềm tin: "cả ngày chỉ có 1-2 entry, có hôm chẳng có lệnh nào"

    Đây là metric quan trọng — nếu ra 20 lệnh/ngày thì filter đang sai,
    không phải hệ thống Sonic R như mô tả.
    """
    if trades.empty:
        return {"trades_per_day": 0}

    total_days = int(m15_index.normalize().nunique())
    daily = trades.groupby(trades["entry_time"].dt.date).size()

    # Số ngày không có lệnh nào
    days_with_trades = len(daily)
    days_no_trade = total_days - days_with_trades

    return {
        "total_days": total_days,
        "trades_per_day": round(len(trades) / max(total_days, 1), 3),
        "trades_per_month": round(len(trades) / max(total_days / 30, 1), 1),
        "days_with_trades": days_with_trades,
        "days_no_trade": days_no_trade,
        "pct_days_no_trade": round(100 * days_no_trade / max(total_days, 1), 1),
        "max_trades_one_day": int(daily.max()),
        "avg_when_active": round(daily.mean(), 2),
    }


def sideway_vs_trend(trades: pd.DataFrame, adx_threshold: float = 25) -> dict:
    """
    Kiểm chứng: "đoạn sideway anh em cực kì dễ toang"

    Tách winrate theo ADX để đo chính xác mức độ "toang".
    """
    if trades.empty or "adx" in trades.columns and trades["adx"].isna().all():
        return {}

    low_adx = trades[trades["adx"] < adx_threshold]
    high_adx = trades[trades["adx"] >= adx_threshold]

    def wr(df):
        return round(100 * (df["pnl"] > 0).mean(), 2) if len(df) else None

    def exp_r(df):
        return round(df["r_multiple"].mean(), 3) if len(df) else None

    return {
        "sideway_n": len(low_adx),
        "sideway_winrate": wr(low_adx),
        "sideway_expectancy": exp_r(low_adx),
        "trending_n": len(high_adx),
        "trending_winrate": wr(high_adx),
        "trending_expectancy": exp_r(high_adx),
    }


def pa_breakdown(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Pattern nào thực sự work?
    "tín hiệu Price Action đẹp" — nhưng đẹp theo kiểu nào?
    """
    if trades.empty:
        return pd.DataFrame()

    rows = []
    for pa, grp in trades.groupby("pa_type"):
        rows.append({
            "pa_type": pa,
            "n": len(grp),
            "winrate": round(100 * (grp["pnl"] > 0).mean(), 2),
            "expectancy_r": round(grp["r_multiple"].mean(), 3),
            "avg_mfe_r": round(grp["mfe_r"].mean(), 2),
        })
    return pd.DataFrame(rows).sort_values("expectancy_r", ascending=False)


def mfe_mae_analysis(trades: pd.DataFrame) -> dict:
    """
    Phân tích MFE/MAE — trả lời: "gồng dài có đáng không?"

    Nếu MFE trung bình của lệnh thắng là 2.1R thì đặt TP 2.618R là tham lam.
    Nếu là 4.5R thì chốt 2R đang bỏ tiền trên bàn.
    """
    if trades.empty:
        return {}

    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]

    return {
        "avg_mfe_all": round(trades["mfe_r"].mean(), 2),
        "avg_mfe_winners": round(wins["mfe_r"].mean(), 2) if len(wins) else 0,
        "avg_mfe_losers": round(losses["mfe_r"].mean(), 2) if len(losses) else 0,
        "median_mfe_winners": round(wins["mfe_r"].median(), 2) if len(wins) else 0,
        "pct_reached_2r": round(100 * (trades["mfe_r"] >= 2).mean(), 1),
        "pct_reached_3r": round(100 * (trades["mfe_r"] >= 3).mean(), 1),
        "pct_reached_5r": round(100 * (trades["mfe_r"] >= 5).mean(), 1),
        "avg_mae_winners": round(wins["mae_r"].mean(), 2) if len(wins) else 0,
    }


def monte_carlo(trades: pd.DataFrame, n_sims: int = 1000,
                initial_balance: float = 10000, seed: int = 42) -> dict:
    """
    Xáo thứ tự lệnh 1000 lần -> phân bố drawdown.
    Trả lời: chuỗi thua tệ nhất có thể gặp là bao nhiêu?
    """
    if trades.empty or len(trades) < 10:
        return {}

    rng = np.random.default_rng(seed)
    pnls = trades["pnl"].values
    max_dds, finals = [], []

    for _ in range(n_sims):
        shuffled = rng.permutation(pnls)
        equity = initial_balance + np.cumsum(shuffled)
        running_max = np.maximum.accumulate(np.maximum(equity, initial_balance))
        dd = (equity - running_max) / running_max
        max_dds.append(abs(dd.min()) * 100)
        finals.append(equity[-1])

    return {
        "mc_median_dd": round(np.median(max_dds), 2),
        "mc_dd_95pct": round(np.percentile(max_dds, 95), 2),
        "mc_worst_dd": round(np.max(max_dds), 2),
        "mc_median_final": round(np.median(finals), 2),
        "mc_prob_loss": round(100 * np.mean(np.array(finals) < initial_balance), 1),
    }


def confidence_interval_winrate(trades: pd.DataFrame) -> dict:
    """
    Khoảng tin cậy 95% của winrate.
    "winrate cực cao" — nhưng với 30 lệnh thì khoảng tin cậy rộng đến mức
    con số đó gần như vô nghĩa.
    """
    if trades.empty:
        return {}

    n = len(trades)
    wins = (trades["pnl"] > 0).sum()
    p = wins / n

    # Wilson score interval
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom

    return {
        "winrate_point": round(100 * p, 2),
        "winrate_ci_low": round(100 * (center - margin), 2),
        "winrate_ci_high": round(100 * (center + margin), 2),
        "sample_size": n,
        "reliable": n >= 100,
    }


def full_report(trades: pd.DataFrame, m15_index: pd.DatetimeIndex,
                initial_balance: float = 10000) -> dict:
    """Gộp tất cả."""
    return {
        "basic": basic_metrics(trades, initial_balance),
        "frequency": frequency_check(trades, m15_index),
        "sideway_vs_trend": sideway_vs_trend(trades),
        "mfe_mae": mfe_mae_analysis(trades),
        "monte_carlo": monte_carlo(trades, initial_balance=initial_balance),
        "winrate_ci": confidence_interval_winrate(trades),
    }
