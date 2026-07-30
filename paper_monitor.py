"""Quét mỗi nến M15 và mô phỏng lệnh; không kết nối API giao dịch."""

import argparse
import json
import logging
import math
import os
import time
from pathlib import Path

import pandas as pd

from backend.app.storage.database import (
    connect_database,
    portfolio_risk_guard_enabled,
    resolve_database_target,
    scalar,
)
from core.signal_scanner import scan_market
from data.loader import okx_usdt_swap_universe


DB_PATH = Path("results/paper_trading.db")
# Một lượt quét treo/crash sẽ tự nhả khoá sau ngần này để chu kỳ sau chạy tiếp.
SCAN_LOCK_STALE_SECONDS = float(os.getenv("SONIC_SCAN_LOCK_STALE_SECONDS", "600"))
MAX_NEW_TRADES_PER_WEEK = int(os.getenv("SONIC_MAX_TRADES_PER_WEEK", "5"))
PENDING_EXPIRY_BARS = int(os.getenv("SONIC_PENDING_EXPIRY_BARS", "4"))
RISK_PCT_PER_TRADE = float(os.getenv("SONIC_RISK_PCT_PER_TRADE", "0.5"))
MAX_PORTFOLIO_RISK_PCT = float(
    os.getenv("SONIC_MAX_PORTFOLIO_RISK_PCT", "2.0")
)
PAPER_EQUITY_USD = float(os.getenv("SONIC_PAPER_EQUITY_USD", "10000"))
if PENDING_EXPIRY_BARS < 1:
    raise ValueError("SONIC_PENDING_EXPIRY_BARS phải >= 1")
if not 0 < RISK_PCT_PER_TRADE <= MAX_PORTFOLIO_RISK_PCT:
    raise ValueError(
        "SONIC_RISK_PCT_PER_TRADE phải > 0 và không vượt "
        "SONIC_MAX_PORTFOLIO_RISK_PCT"
    )
if PAPER_EQUITY_USD <= 0:
    raise ValueError("SONIC_PAPER_EQUITY_USD phải > 0")
SCAN_COLUMNS = [
    "rank", "name", "symbol", "base", "side", "status", "actionable",
    "signal_time", "bar_open", "bar_high", "bar_low", "bar_close",
    "entry", "sl", "tp1", "tp2", "tp1_rr", "tp2_rr", "trail_h1",
    "pa", "missing", "f_trend", "f_regime", "f_session", "f_breakout",
    "f_dow", "f_value_zone", "f_pa", "session", "adx", "separation",
    "ema200_aligned", "pva_state", "pva_ratio", "pva_rising", "pva_climax",
    "entry_model", "contract_size", "amount_step", "min_contracts",
]


def connect(db_target=None):
    return connect_database(
        db_target,
        risk_pct_per_trade=RISK_PCT_PER_TRADE,
        paper_equity_usd=PAPER_EQUITY_USD,
    )


def acquire_scan_lock(conn, holder=None):
    """Khoá liên tiến trình bằng UPDATE nguyên tử trên SQLite/PostgreSQL."""
    holder = holder or f"pid-{os.getpid()}"
    now = pd.Timestamp.now(tz="UTC")
    cutoff = (now - pd.Timedelta(seconds=SCAN_LOCK_STALE_SECONDS)).isoformat()
    with conn.transaction():
        cursor = conn.execute(
            "UPDATE scan_lock SET locked_at=?, holder=? "
            "WHERE id=1 AND (locked_at IS NULL OR locked_at < ?)",
            (now.isoformat(), holder, cutoff),
        )
    return cursor.rowcount == 1


def release_scan_lock(conn):
    with conn.transaction():
        conn.execute(
            "UPDATE scan_lock SET locked_at=NULL, holder=NULL WHERE id=1"
        )


def _value(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return int(value)
    return value.item() if hasattr(value, "item") else value


def committed_risk_pct(trade) -> float:
    """Risk tối đa còn lại tại current SL, tính theo % equity ban đầu."""
    state = dict(trade)
    risk_pct = float(state.get("risk_pct") or RISK_PCT_PER_TRADE)
    if state.get("status") == "PENDING":
        return risk_pct
    if state.get("status") != "OPEN":
        return 0.0
    risk = float(state.get("risk") or 0)
    if risk <= 0:
        return 0.0
    direction = 1 if state["side"] == "LONG" else -1
    stop_r = (
        (float(state["current_sl"]) - float(state["entry"]))
        * direction
        / risk
    )
    result_at_stop_r = (
        float(state.get("realized_r") or 0)
        + float(state.get("remaining") or 0) * stop_r
    )
    return max(0.0, -result_at_stop_r) * risk_pct


def committed_risk_usd(trade) -> float:
    """Rủi ro tối đa còn lại tại current SL, tính bằng USD."""
    state = dict(trade)
    risk_pct = float(state.get("risk_pct") or RISK_PCT_PER_TRADE)
    risk_amount = float(
        state.get("risk_amount_usd")
        or PAPER_EQUITY_USD * risk_pct / 100
    )
    if risk_pct <= 0:
        return 0.0
    return committed_risk_pct(state) / risk_pct * risk_amount


def dedupe_setups(report):
    """Bỏ trùng cặp (symbol, side), giữ bản ghi cuối.

    ``latest_setups`` có ``PRIMARY KEY (symbol, side)``. Nếu universe trả về
    một symbol hai lần thì ``executemany`` vi phạm ràng buộc và làm vỡ cả lượt
    quét. Một universe trùng là dữ liệu bẩn, không phải lý do để mất cả chu kỳ.
    """
    if report.empty or not {"symbol", "side"}.issubset(report.columns):
        return report
    return report.drop_duplicates(subset=["symbol", "side"], keep="last")


def save_scan(conn, report, scanned_at, duration):
    report = dedupe_setups(report)
    rows = [
        tuple(_value(row.get(column)) for column in SCAN_COLUMNS)
        for row in report.to_dict("records")
    ]
    placeholders = ",".join("?" for _ in SCAN_COLUMNS)
    with conn.transaction():
        conn.execute("DELETE FROM latest_setups")
        conn.executemany(
            f"INSERT INTO latest_setups ({','.join(SCAN_COLUMNS)}) "
            f"VALUES ({placeholders})",
            rows,
        )
        success = report[report["status"] != "ERROR"]
        ready = success[success["status"] == "READY"]
        conn.execute(
            """
            INSERT INTO scan_runs (
                scanned_at, universe_count, success_count, long_ready,
                short_ready, wait_count, error_count, duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scanned_at.isoformat(),
                int(report["symbol"].nunique()),
                int(success["symbol"].nunique()),
                int((ready["side"] == "LONG").sum()),
                int((ready["side"] == "SHORT").sum()),
                int(success["status"].isin(["WAIT_PA", "WAIT_PULLBACK"]).sum()),
                int(report.loc[report["status"] == "ERROR", "symbol"].nunique()),
                round(duration, 2),
            ),
        )


def advance_paper_trade(trade, bar):
    """Xử lý một nến; nếu SL và TP cùng chạm thì ưu tiên SL."""
    state = dict(trade)
    events = []
    side = state["side"]
    direction = 1 if side == "LONG" else -1
    entry, risk = float(state["entry"]), float(state["risk"])
    high, low, close = (float(bar[key]) for key in ("bar_high", "bar_low", "bar_close"))

    state["mfe_r"] = max(
        float(state["mfe_r"]),
        (high - entry) / risk if side == "LONG" else (entry - low) / risk,
    )
    state["mae_r"] = min(
        float(state["mae_r"]),
        (low - entry) / risk if side == "LONG" else (entry - high) / risk,
    )

    def touched(level, kind):
        if kind == "stop":
            return low <= level if side == "LONG" else high >= level
        return high >= level if side == "LONG" else low <= level

    def close_remaining(reason, price):
        delta = float(state["remaining"]) * (price - entry) * direction / risk
        state["realized_r"] = float(state["realized_r"]) + delta
        state["remaining"] = 0.0
        state["status"] = "CLOSED"
        state["exit_price"] = price
        state["exit_reason"] = reason
        state["total_r"] = state["realized_r"]
        events.append((reason, price, delta))

    if touched(float(state["current_sl"]), "stop"):
        close_remaining("SL" if not state["tp1_hit"] else "BE", float(state["current_sl"]))
    else:
        if not state["tp1_hit"] and touched(float(state["tp1"]), "target"):
            delta = 0.5 * float(state["tp1_rr"])
            state["realized_r"] = float(state["realized_r"]) + delta
            state["remaining"] = float(state["remaining"]) - 0.5
            state["tp1_hit"] = 1
            state["current_sl"] = entry
            events.append(("TP1", float(state["tp1"]), delta))
            if touched(entry, "stop"):
                close_remaining("BE", entry)

        if (
            state["status"] == "OPEN"
            and not state["tp2_hit"]
            and touched(float(state["tp2"]), "target")
        ):
            delta = 0.3 * float(state["tp2_rr"])
            state["realized_r"] = float(state["realized_r"]) + delta
            state["remaining"] = float(state["remaining"]) - 0.3
            state["tp2_hit"] = 1
            events.append(("TP2", float(state["tp2"]), delta))

        trail = bar.get("trail_h1")
        trail_hit = (
            trail is not None
            and math.isfinite(float(trail))
            and ((side == "LONG" and close < trail) or (side == "SHORT" and close > trail))
        )
        if state["status"] == "OPEN" and state["tp2_hit"] and trail_hit:
            close_remaining("TRAIL", close)

    state["trail_h1"] = _value(bar.get("trail_h1"))
    state["last_bar_time"] = _value(bar["signal_time"])
    return state, events


def _record_event(conn, trade_id, event_at, event, price, delta_r, detail=None):
    conn.execute(
        """
        INSERT INTO paper_events (
            trade_id, event_at, event, price, delta_r, detail
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, event_at, event, price, delta_r, detail),
    )


def manage_open_trades(conn, report):
    bars = {
        (row["symbol"], row["side"]): row
        for row in report.to_dict("records")
        if row.get("status") != "ERROR" and pd.notna(row.get("signal_time"))
    }
    with conn.transaction():
        for stored in conn.execute(
            "SELECT * FROM paper_trades WHERE status IN ('PENDING', 'OPEN')"
        ).fetchall():
            bar = bars.get((stored["symbol"], stored["side"]))
            if not bar:
                continue
            bar_time = pd.Timestamp(bar["signal_time"])
            if bar_time <= pd.Timestamp(stored["last_bar_time"]):
                continue
            state = dict(stored)
            events = []
            if state["status"] == "PENDING":
                expires_at = state.get("expires_at")
                if expires_at is None:
                    expires_at = (
                        pd.Timestamp(state["opened_at"])
                        + pd.Timedelta(minutes=15 * PENDING_EXPIRY_BARS)
                    ).isoformat()
                if bar_time > pd.Timestamp(expires_at):
                    conn.execute(
                        """
                        UPDATE paper_trades SET
                            status='EXPIRED', remaining=0, last_bar_time=?,
                            closed_at=?, exit_reason='EXPIRY', total_r=0
                        WHERE id=?
                        """,
                        (
                            _value(bar["signal_time"]),
                            _value(bar["signal_time"]),
                            state["id"],
                        ),
                    )
                    _record_event(
                        conn,
                        state["id"],
                        _value(bar["signal_time"]),
                        "EXPIRED",
                        float(state["entry"]),
                        0,
                        f"Không khớp sau {PENDING_EXPIRY_BARS} nến M15",
                    )
                    continue
                triggered = (
                    float(bar["bar_high"]) >= float(state["entry"])
                    if state["side"] == "LONG"
                    else float(bar["bar_low"]) <= float(state["entry"])
                )
                if not triggered:
                    conn.execute(
                        "UPDATE paper_trades SET last_bar_time=?, trail_h1=? WHERE id=?",
                        (_value(bar["signal_time"]), _value(bar.get("trail_h1")), state["id"]),
                    )
                    continue
                state["status"] = "OPEN"
                state["filled_at"] = _value(bar["signal_time"])
                events.append(("FILL", float(state["entry"]), 0.0))

            state, lifecycle_events = advance_paper_trade(state, bar)
            events.extend(lifecycle_events)
            state["closed_at"] = (
                _value(bar["signal_time"]) if state["status"] == "CLOSED" else None
            )
            conn.execute(
                """
                UPDATE paper_trades SET
                    status=?, current_sl=?, remaining=?, realized_r=?,
                    tp1_hit=?, tp2_hit=?, last_bar_time=?, trail_h1=?,
                    mfe_r=?, mae_r=?, filled_at=?, closed_at=?, exit_price=?,
                    exit_reason=?, total_r=?
                WHERE id=?
                """,
                tuple(
                    state[key]
                    for key in [
                        "status", "current_sl", "remaining", "realized_r",
                        "tp1_hit", "tp2_hit", "last_bar_time", "trail_h1",
                        "mfe_r", "mae_r", "filled_at", "closed_at", "exit_price",
                        "exit_reason", "total_r", "id",
                    ]
                ),
            )
            for event, price, delta in events:
                _record_event(
                    conn, state["id"], _value(bar["signal_time"]),
                    event, price, delta,
                )


def open_ready_trades(conn, report):
    opened = 0
    ready = report[(report["status"] == "READY") & report["actionable"].astype(bool)]
    with conn.transaction():
        risk_guard_enabled = portfolio_risk_guard_enabled(conn)
        week_cutoff = (
            pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
        ).isoformat()
        opened_this_week = scalar(conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE opened_at >= ?",
            (week_cutoff,),
        ))
        active_trades = conn.execute(
            "SELECT * FROM paper_trades "
            "WHERE status IN ('PENDING', 'OPEN')"
        ).fetchall()
        committed_risk = sum(
            committed_risk_pct(trade) for trade in active_trades
        )
        for row in ready.to_dict("records"):
            if opened_this_week >= MAX_NEW_TRADES_PER_WEEK:
                break
            if (
                risk_guard_enabled
                and committed_risk + RISK_PCT_PER_TRADE
                > MAX_PORTFOLIO_RISK_PCT
            ):
                break
            if conn.execute(
                "SELECT 1 FROM paper_trades "
                "WHERE symbol=? AND status IN ('PENDING', 'OPEN')",
                (row["symbol"],),
            ).fetchone():
                continue
            signal_time = _value(row["signal_time"])
            key = f"{row['symbol']}|{row['side']}|{signal_time}"
            risk = abs(float(row["entry"]) - float(row["sl"]))
            if risk <= 0:
                continue
            risk_amount_usd = PAPER_EQUITY_USD * RISK_PCT_PER_TRADE / 100
            position_size = risk_amount_usd / risk
            entry_notional_usd = position_size * float(row["entry"])
            expires_at = (
                pd.Timestamp(row["signal_time"])
                + pd.Timedelta(minutes=15 * PENDING_EXPIRY_BARS)
            ).isoformat()
            cursor = conn.execute(
                """
                INSERT INTO paper_trades (
                    signal_key, symbol, base, name, side, status, opened_at,
                    entry, initial_sl, current_sl, tp1, tp2, tp1_rr, tp2_rr,
                    trail_h1, risk, remaining, realized_r, tp1_hit, tp2_hit,
                    last_bar_time, mfe_r, mae_r, risk_pct, expires_at,
                    risk_amount_usd, position_size, entry_notional_usd
                ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, 1, 0, 0, 0, ?, 0, 0, ?, ?, ?, ?, ?)
                ON CONFLICT (signal_key) DO NOTHING
                RETURNING id
                """,
                (
                    key, row["symbol"], row.get("base"), row.get("name"),
                    row["side"], signal_time, float(row["entry"]), float(row["sl"]),
                    float(row["sl"]), float(row["tp1"]), float(row["tp2"]),
                    float(row["tp1_rr"]), float(row["tp2_rr"]),
                    _value(row.get("trail_h1")), risk, signal_time,
                    RISK_PCT_PER_TRADE, expires_at, risk_amount_usd,
                    position_size, entry_notional_usd,
                ),
            )
            inserted = cursor.fetchone()
            if inserted:
                trade_id = (
                    inserted["id"] if isinstance(inserted, dict) else inserted[0]
                )
                opened += 1
                opened_this_week += 1
                committed_risk += RISK_PCT_PER_TRADE
                _record_event(
                    conn, trade_id, signal_time, "ARMED", float(row["entry"]), 0,
                    json.dumps(
                        {"sl": row["sl"], "tp1": row["tp1"], "tp2": row["tp2"]},
                        ensure_ascii=False,
                    ),
                )
    return opened


def run_cycle(db_target=None, progress=None):
    conn = connect(db_target)
    if not acquire_scan_lock(conn):
        open_count = scalar(conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'"
        ))
        conn.close()
        logging.info("Bỏ qua lượt quét: đã có tiến trình khác đang quét.")
        return {
            "skipped": True, "coins": 0, "long_ready": 0, "short_ready": 0,
            "errors": 0, "opened": 0, "open_positions": open_count,
            "duration_seconds": 0.0, "scan_saved": False,
        }
    try:
        started = time.monotonic()
        universe = okx_usdt_swap_universe()
        report = dedupe_setups(scan_market(universe, progress=progress))
        duration = time.monotonic() - started
        scanned_at = pd.Timestamp.now(tz="UTC")
        # save_scan chỉ ghi nhận quan sát (snapshot + scan_runs). Quản trị lệnh
        # đang mở quan trọng hơn nhiều, nên một lỗi ghi snapshot không được phép
        # bỏ qua manage_open_trades/open_ready_trades của cả chu kỳ.
        # transaction() đã rollback nên connection vẫn dùng được sau lỗi.
        try:
            save_scan(conn, report, scanned_at, duration)
            scan_saved = True
        except Exception:
            scan_saved = False
            logging.exception(
                "Lưu snapshot lượt quét thất bại; vẫn tiếp tục quản trị lệnh."
            )
        manage_open_trades(conn, report)
        opened = open_ready_trades(conn, report)
        open_count = scalar(conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'"
        ))
    finally:
        release_scan_lock(conn)
        conn.close()
    ready = report[report["status"] == "READY"]
    summary = {
        "skipped": False,
        "coins": int(report["symbol"].nunique()),
        "long_ready": int((ready["side"] == "LONG").sum()),
        "short_ready": int((ready["side"] == "SHORT").sum()),
        "errors": int(report.loc[report["status"] == "ERROR", "symbol"].nunique()),
        "opened": opened,
        "open_positions": open_count,
        "duration_seconds": round(duration, 1),
        "scan_saved": scan_saved,
    }
    logging.info("Chu kỳ hoàn tất: %s", summary)
    return summary


def seconds_to_next_close(now=None):
    now = now or pd.Timestamp.now(tz="UTC")
    next_close = now.floor("15min") + pd.Timedelta(minutes=15, seconds=5)
    return max(1.0, (next_close - now).total_seconds())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Chạy đúng một lượt")
    parser.add_argument(
        "--db",
        default=None,
        help=(
            "SQLite path or PostgreSQL URL. Mặc định dùng DATABASE_URL trên "
            "Replit, nếu không có thì dùng SONIC_DB_PATH."
        ),
    )
    args = parser.parse_args()

    db_target = resolve_database_target(args.db)
    log_path = Path(
        os.getenv("SONIC_MONITOR_LOG_PATH", "results/paper_monitor.log")
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    if args.once:
        run_cycle(db_target)
        return

    pid_path = log_path.with_name("paper_monitor.pid")
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    logging.info("Paper monitor PID %s; chỉ mô phỏng, không gửi lệnh thật.", os.getpid())
    try:
        while True:
            try:
                run_cycle(db_target)
            except Exception:
                logging.exception("Chu kỳ lỗi; monitor sẽ tiếp tục ở nến sau.")
            delay = seconds_to_next_close()
            logging.info("Ngủ %.0f giây tới nến M15 kế tiếp.", delay)
            time.sleep(delay)
    finally:
        if pid_path.exists() and pid_path.read_text(encoding="utf-8") == str(os.getpid()):
            pid_path.unlink()


if __name__ == "__main__":
    main()
