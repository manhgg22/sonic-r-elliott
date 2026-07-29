import os

import pandas as pd
import pytest

from backend.app.storage.database import (
    RISK_GUARD_SETTING_KEY,
    connect_database,
    portfolio_risk_guard_enabled,
    resolve_database_target,
    scalar,
    set_runtime_setting,
)
from paper_monitor import (
    acquire_scan_lock,
    manage_open_trades,
    open_ready_trades,
    release_scan_lock,
)


def test_database_target_prefers_postgres(monkeypatch, tmp_path):
    monkeypatch.delenv("SONIC_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/database")
    monkeypatch.setenv("SONIC_DB_PATH", str(tmp_path / "fallback.db"))
    assert resolve_database_target() == "postgresql://example/database"

    monkeypatch.setenv(
        "SONIC_DATABASE_URL", "postgresql://override/database"
    )
    assert resolve_database_target() == "postgresql://override/database"


def test_sqlite_schema_and_cross_process_lock(tmp_path):
    connection = connect_database(tmp_path / "paper.db")
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "scan_runs",
            "latest_setups",
            "paper_trades",
            "paper_events",
            "scan_lock",
            "runtime_settings",
        }.issubset(tables)
        trade_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(paper_trades)"
            )
        }
        assert {
            "risk_amount_usd",
            "position_size",
            "entry_notional_usd",
        }.issubset(trade_columns)
        assert portfolio_risk_guard_enabled(connection)
        set_runtime_setting(
            connection,
            RISK_GUARD_SETTING_KEY,
            "false",
        )
        assert not portfolio_risk_guard_enabled(connection)
        connection.close()
        connection = connect_database(tmp_path / "paper.db")
        assert not portfolio_risk_guard_enabled(connection)
        assert acquire_scan_lock(connection, "test")
        assert not acquire_scan_lock(connection, "second")
        release_scan_lock(connection)
        assert acquire_scan_lock(connection, "third")
        release_scan_lock(connection)
    finally:
        connection.close()


def test_postgres_schema_and_rollback():
    target = os.getenv("SONIC_TEST_DATABASE_URL")
    if not target:
        pytest.skip("SONIC_TEST_DATABASE_URL is not configured")

    connection = connect_database(target)
    try:
        assert connection.dialect == "postgresql"
        before = int(scalar(connection.execute(
            "SELECT COUNT(*) FROM scan_runs"
        )))

        class RollbackProbe(Exception):
            pass

        with pytest.raises(RollbackProbe):
            with connection.transaction():
                connection.execute(
                    """
                    INSERT INTO scan_runs (
                        scanned_at, universe_count, success_count,
                        long_ready, short_ready, wait_count, error_count,
                        duration_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("test", 1, 1, 0, 0, 0, 0, 0.1),
                )
                raise RollbackProbe

        after = int(scalar(connection.execute(
            "SELECT COUNT(*) FROM scan_runs"
        )))
        connection.rollback()
        assert after == before
    finally:
        connection.close()


def test_postgres_paper_trade_write_path():
    target = os.getenv("SONIC_TEST_DATABASE_URL")
    if not target:
        pytest.skip("SONIC_TEST_DATABASE_URL is not configured")

    connection = connect_database(target)
    signal_time = pd.Timestamp("2099-01-01T00:00:00Z")
    report = pd.DataFrame([{
        "symbol": "INTEGRATION/USDT",
        "base": "INTEGRATION",
        "name": "Integration Test",
        "side": "LONG",
        "status": "READY",
        "actionable": True,
        "signal_time": signal_time,
        "entry": 105.0,
        "sl": 95.0,
        "tp1": 120.0,
        "tp2": 135.0,
        "tp1_rr": 1.5,
        "tp2_rr": 3.0,
        "trail_h1": 98.0,
    }])
    try:
        assert open_ready_trades(connection, report) == 1
        trade = connection.execute(
            "SELECT * FROM paper_trades WHERE symbol=?",
            ("INTEGRATION/USDT",),
        ).fetchone()
        assert trade["status"] == "PENDING"

        next_bar = report.copy()
        next_bar.loc[0, "status"] = "NO_SETUP"
        next_bar.loc[0, "signal_time"] = signal_time + pd.Timedelta(
            minutes=15
        )
        next_bar.loc[0, "bar_high"] = 108.0
        next_bar.loc[0, "bar_low"] = 100.0
        next_bar.loc[0, "bar_close"] = 107.0
        manage_open_trades(connection, next_bar)

        trade = connection.execute(
            "SELECT * FROM paper_trades WHERE symbol=?",
            ("INTEGRATION/USDT",),
        ).fetchone()
        assert trade["status"] == "OPEN"
        assert scalar(connection.execute(
            """
            SELECT COUNT(*) FROM paper_events
            WHERE trade_id=? AND event='FILL'
            """,
            (trade["id"],),
        )) == 1
        connection.rollback()
    finally:
        with connection.transaction():
            connection.execute(
                """
                DELETE FROM paper_events WHERE trade_id IN (
                    SELECT id FROM paper_trades WHERE symbol=?
                )
                """,
                ("INTEGRATION/USDT",),
            )
            connection.execute(
                "DELETE FROM paper_trades WHERE symbol=?",
                ("INTEGRATION/USDT",),
            )
        connection.close()
