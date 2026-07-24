"""Quét mỗi nến M15 và mô phỏng lệnh; không kết nối API giao dịch."""

import argparse
import json
import logging
import math
import os
import sqlite3
import time
from pathlib import Path

import pandas as pd

from core.signal_scanner import scan_market
from data.loader import okx_usdt_swap_universe


DB_PATH = Path("results/paper_trading.db")
# Một lượt quét treo/crash sẽ tự nhả khoá sau ngần này để chu kỳ sau chạy tiếp.
SCAN_LOCK_STALE_SECONDS = float(os.getenv("SONIC_SCAN_LOCK_STALE_SECONDS", "600"))
SCAN_COLUMNS = [
    "rank", "name", "symbol", "base", "side", "status", "actionable",
    "signal_time", "bar_open", "bar_high", "bar_low", "bar_close",
    "entry", "sl", "tp1", "tp2", "tp1_rr", "tp2_rr", "trail_h1",
    "pa", "missing", "f_trend", "f_breakout", "f_dow", "f_value_zone",
    "f_pa", "contract_size", "amount_step", "min_contracts",
]


def connect(db_path=DB_PATH):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS scan_runs (
            id INTEGER PRIMARY KEY,
            scanned_at TEXT NOT NULL,
            universe_count INTEGER NOT NULL,
            success_count INTEGER NOT NULL,
            long_ready INTEGER NOT NULL,
            short_ready INTEGER NOT NULL,
            wait_count INTEGER NOT NULL,
            error_count INTEGER NOT NULL,
            duration_seconds REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS latest_setups (
            rank INTEGER, name TEXT, symbol TEXT, base TEXT, side TEXT,
            status TEXT, actionable INTEGER, signal_time TEXT,
            bar_open REAL, bar_high REAL, bar_low REAL, bar_close REAL,
            entry REAL, sl REAL, tp1 REAL, tp2 REAL, tp1_rr REAL, tp2_rr REAL,
            trail_h1 REAL, pa TEXT, missing TEXT, f_trend INTEGER,
            f_breakout INTEGER, f_dow INTEGER, f_value_zone INTEGER,
            f_pa INTEGER, contract_size REAL, amount_step REAL,
            min_contracts REAL, PRIMARY KEY (symbol, side)
        );
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY,
            signal_key TEXT NOT NULL UNIQUE,
            symbol TEXT NOT NULL, base TEXT, name TEXT, side TEXT NOT NULL,
            status TEXT NOT NULL, opened_at TEXT NOT NULL,
            entry REAL NOT NULL, initial_sl REAL NOT NULL,
            current_sl REAL NOT NULL, tp1 REAL NOT NULL, tp2 REAL NOT NULL,
            tp1_rr REAL NOT NULL, tp2_rr REAL NOT NULL, trail_h1 REAL,
            risk REAL NOT NULL, remaining REAL NOT NULL DEFAULT 1,
            realized_r REAL NOT NULL DEFAULT 0, tp1_hit INTEGER NOT NULL DEFAULT 0,
            tp2_hit INTEGER NOT NULL DEFAULT 0, last_bar_time TEXT NOT NULL,
            mfe_r REAL NOT NULL DEFAULT 0, mae_r REAL NOT NULL DEFAULT 0,
            closed_at TEXT, exit_price REAL, exit_reason TEXT, total_r REAL
        );
        CREATE TABLE IF NOT EXISTS paper_events (
            id INTEGER PRIMARY KEY, trade_id INTEGER NOT NULL,
            event_at TEXT NOT NULL, event TEXT NOT NULL, price REAL,
            delta_r REAL NOT NULL DEFAULT 0, detail TEXT,
            FOREIGN KEY (trade_id) REFERENCES paper_trades(id)
        );
        CREATE TABLE IF NOT EXISTS scan_lock (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            locked_at TEXT, holder TEXT
        );
        INSERT OR IGNORE INTO scan_lock (id, locked_at, holder)
        VALUES (1, NULL, NULL);
        """
    )
    return conn


def acquire_scan_lock(conn, holder=None):
    """Khoá quét liên-tiến-trình qua SQLite: chỉ một lượt scan chạy tại một
    thời điểm dù backend API và monitor nền là hai process khác nhau.
    UPDATE có điều kiện + SQLite tuần tự hoá writer nên không có race."""
    holder = holder or f"pid-{os.getpid()}"
    now = pd.Timestamp.now(tz="UTC")
    cutoff = (now - pd.Timedelta(seconds=SCAN_LOCK_STALE_SECONDS)).isoformat()
    with conn:
        cursor = conn.execute(
            "UPDATE scan_lock SET locked_at=?, holder=? "
            "WHERE id=1 AND (locked_at IS NULL OR locked_at < ?)",
            (now.isoformat(), holder, cutoff),
        )
    return cursor.rowcount == 1


def release_scan_lock(conn):
    with conn:
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


def save_scan(conn, report, scanned_at, duration):
    rows = [
        tuple(_value(row.get(column)) for column in SCAN_COLUMNS)
        for row in report.to_dict("records")
    ]
    placeholders = ",".join("?" for _ in SCAN_COLUMNS)
    with conn:
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
    with conn:
        for stored in conn.execute(
            "SELECT * FROM paper_trades WHERE status='OPEN'"
        ).fetchall():
            bar = bars.get((stored["symbol"], stored["side"]))
            if not bar:
                continue
            bar_time = pd.Timestamp(bar["signal_time"])
            if bar_time <= pd.Timestamp(stored["last_bar_time"]):
                continue
            state, events = advance_paper_trade(dict(stored), bar)
            state["closed_at"] = (
                _value(bar["signal_time"]) if state["status"] == "CLOSED" else None
            )
            conn.execute(
                """
                UPDATE paper_trades SET
                    status=?, current_sl=?, remaining=?, realized_r=?,
                    tp1_hit=?, tp2_hit=?, last_bar_time=?, trail_h1=?,
                    mfe_r=?, mae_r=?, closed_at=?, exit_price=?,
                    exit_reason=?, total_r=?
                WHERE id=?
                """,
                tuple(
                    state[key]
                    for key in [
                        "status", "current_sl", "remaining", "realized_r",
                        "tp1_hit", "tp2_hit", "last_bar_time", "trail_h1",
                        "mfe_r", "mae_r", "closed_at", "exit_price",
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
    with conn:
        for row in ready.to_dict("records"):
            if conn.execute(
                "SELECT 1 FROM paper_trades WHERE symbol=? AND status='OPEN'",
                (row["symbol"],),
            ).fetchone():
                continue
            signal_time = _value(row["signal_time"])
            key = f"{row['symbol']}|{row['side']}|{signal_time}"
            risk = abs(float(row["entry"]) - float(row["sl"]))
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO paper_trades (
                    signal_key, symbol, base, name, side, status, opened_at,
                    entry, initial_sl, current_sl, tp1, tp2, tp1_rr, tp2_rr,
                    trail_h1, risk, remaining, realized_r, tp1_hit, tp2_hit,
                    last_bar_time, mfe_r, mae_r
                ) VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, 1, 0, 0, 0, ?, 0, 0)
                """,
                (
                    key, row["symbol"], row.get("base"), row.get("name"),
                    row["side"], signal_time, float(row["entry"]), float(row["sl"]),
                    float(row["sl"]), float(row["tp1"]), float(row["tp2"]),
                    float(row["tp1_rr"]), float(row["tp2_rr"]),
                    _value(row.get("trail_h1")), risk, signal_time,
                ),
            )
            if cursor.rowcount:
                opened += 1
                _record_event(
                    conn, cursor.lastrowid, signal_time, "OPEN", float(row["entry"]), 0,
                    json.dumps(
                        {"sl": row["sl"], "tp1": row["tp1"], "tp2": row["tp2"]},
                        ensure_ascii=False,
                    ),
                )
    return opened


def run_cycle(db_path=DB_PATH, progress=None):
    conn = connect(db_path)
    if not acquire_scan_lock(conn):
        open_count = conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'"
        ).fetchone()[0]
        conn.close()
        logging.info("Bỏ qua lượt quét: đã có tiến trình khác đang quét.")
        return {
            "skipped": True, "coins": 0, "long_ready": 0, "short_ready": 0,
            "errors": 0, "opened": 0, "open_positions": open_count,
            "duration_seconds": 0.0,
        }
    try:
        started = time.monotonic()
        universe = okx_usdt_swap_universe()
        report = scan_market(universe, progress=progress)
        duration = time.monotonic() - started
        scanned_at = pd.Timestamp.now(tz="UTC")
        save_scan(conn, report, scanned_at, duration)
        manage_open_trades(conn, report)
        opened = open_ready_trades(conn, report)
        open_count = conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'"
        ).fetchone()[0]
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
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(db_path.with_name("paper_monitor.log"), encoding="utf-8"),
        ],
    )
    if args.once:
        run_cycle(db_path)
        return

    pid_path = db_path.with_name("paper_monitor.pid")
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    logging.info("Paper monitor PID %s; chỉ mô phỏng, không gửi lệnh thật.", os.getpid())
    try:
        while True:
            try:
                run_cycle(db_path)
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
