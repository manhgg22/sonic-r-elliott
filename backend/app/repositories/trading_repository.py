from pathlib import Path

from backend.app.storage.database import (
    RISK_GUARD_SETTING_KEY,
    connect_database,
    portfolio_risk_guard_enabled,
    set_runtime_setting,
)


class TradingRepository:
    def __init__(self, database_target: str | Path):
        self.database_target = database_target
        # Kept as a compatibility alias for DashboardService/run_cycle.
        self.database_path = database_target

    def _connect(self):
        return connect_database(self.database_target, initialize=False)

    @staticmethod
    def _rows(connection, sql, parameters=()):
        return [dict(row) for row in connection.execute(sql, parameters)]

    def _query(self, sql, parameters=()):
        with self._connect() as connection:
            return self._rows(connection, sql, parameters)

    def snapshot(self):
        with self._connect() as connection:
            return {
                "setups": self._rows(
                    connection, "SELECT * FROM latest_setups"
                ),
                "runs": self._rows(
                    connection,
                    "SELECT * FROM scan_runs ORDER BY id DESC LIMIT 96",
                ),
                "trades": self._rows(
                    connection,
                    "SELECT * FROM paper_trades ORDER BY id DESC",
                ),
                "events": self._rows(
                    connection,
                    """
                    SELECT
                        e.*, t.symbol, t.base, t.side, t.risk_amount_usd
                    FROM paper_events AS e
                    JOIN paper_trades AS t ON t.id = e.trade_id
                    ORDER BY e.id DESC
                    LIMIT 500
                    """,
                ),
            }

    def open_positions(self):
        return self._query(
            "SELECT * FROM paper_trades WHERE status = 'OPEN' ORDER BY opened_at DESC"
        )

    def active_positions(self):
        return self._query(
            "SELECT * FROM paper_trades "
            "WHERE status IN ('PENDING', 'OPEN') ORDER BY opened_at DESC"
        )

    def portfolio_risk_guard_enabled(self) -> bool:
        with self._connect() as connection:
            return portfolio_risk_guard_enabled(connection)

    def set_portfolio_risk_guard(self, enabled: bool) -> None:
        with self._connect() as connection:
            set_runtime_setting(
                connection,
                RISK_GUARD_SETTING_KEY,
                "true" if enabled else "false",
            )
