from backend.app.services.dashboard_service import DashboardService
from paper_monitor import (
    MAX_PORTFOLIO_RISK_PCT,
    PAPER_EQUITY_USD,
    RISK_PCT_PER_TRADE,
)


class FakeRepository:
    database_path = "unused.db"

    def snapshot(self):
        return {
            "setups": [],
            "runs": [],
            "trades": [{
                "id": 1,
                "status": "CLOSED",
                "risk_amount_usd": 50.0,
                "realized_r": 1.25,
                "total_r": 1.5,
                "mfe_r": 2.0,
                "mae_r": -0.4,
            }],
            "events": [{
                "id": 1,
                "delta_r": 0.75,
                "risk_amount_usd": 50.0,
            }],
        }

    def active_positions(self):
        return []

    def open_positions(self):
        return []

    def portfolio_risk_guard_enabled(self):
        return True

    def set_portfolio_risk_guard(self, _enabled):
        pass


class FakeMarket:
    def swap_prices(self):
        return {}


class LiveRepository(FakeRepository):
    def open_positions(self):
        return [{
            "id": 2,
            "base": "BTC",
            "side": "LONG",
            "entry": 100.0,
            "risk": 10.0,
            "remaining": 0.5,
            "realized_r": 0.75,
            "risk_amount_usd": 50.0,
            "position_size": 5.0,
            "entry_notional_usd": 500.0,
        }]


class LiveMarket:
    def swap_prices(self):
        return {"BTC-USDT-SWAP": 110.0}


def test_snapshot_exposes_paper_results_in_usd():
    snapshot = DashboardService(FakeRepository(), FakeMarket()).snapshot()
    trade = snapshot["trades"][0]
    event = snapshot["events"][0]

    assert trade["realized_pnl_usd"] == 62.5
    assert trade["total_pnl_usd"] == 75.0
    assert trade["mfe_usd"] == 100.0
    assert trade["mae_usd"] == -20.0
    assert event["delta_usd"] == 37.5


def test_risk_summary_exposes_usd_budget():
    risk = DashboardService(FakeRepository(), FakeMarket()).risk_summary()

    assert risk["paper_equity_usd"] == PAPER_EQUITY_USD
    assert risk["risk_per_trade_usd"] == (
        PAPER_EQUITY_USD * RISK_PCT_PER_TRADE / 100
    )
    assert risk["max_portfolio_risk_usd"] == (
        PAPER_EQUITY_USD * MAX_PORTFOLIO_RISK_PCT / 100
    )
    assert risk["committed_risk_usd"] == 0


def test_live_positions_expose_usd_pnl_and_sizing():
    positions = DashboardService(
        LiveRepository(),
        LiveMarket(),
    ).live_positions()

    assert positions[0]["live_r"] == 1.25
    assert positions[0]["live_pnl_usd"] == 62.5
    assert positions[0]["risk_amount_usd"] == 50.0
    assert positions[0]["position_size"] == 5.0
    assert positions[0]["entry_notional_usd"] == 500.0
