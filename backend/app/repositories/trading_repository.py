import sqlite3
from pathlib import Path


class TradingRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _query(self, sql, parameters=()):
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, parameters)]

    def snapshot(self):
        return {
            "setups": self._query("SELECT * FROM latest_setups"),
            "runs": self._query(
                "SELECT * FROM scan_runs ORDER BY id DESC LIMIT 96"
            ),
            "trades": self._query(
                "SELECT * FROM paper_trades ORDER BY id DESC"
            ),
            "events": self._query(
                "SELECT * FROM paper_events ORDER BY id DESC LIMIT 500"
            ),
        }

    def open_positions(self):
        return self._query(
            "SELECT * FROM paper_trades WHERE status = 'OPEN' ORDER BY opened_at DESC"
        )
