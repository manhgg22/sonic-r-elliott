from paper_monitor import (
    MAX_PORTFOLIO_RISK_PCT,
    PENDING_EXPIRY_BARS,
    RISK_PCT_PER_TRADE,
    committed_risk_pct,
    run_cycle,
)


class DashboardService:
    def __init__(self, repository, market):
        self.repository = repository
        self.market = market

    def snapshot(self):
        payload = self.repository.snapshot()
        payload["risk"] = self.risk_summary()
        return payload

    def run_scan(self):
        return run_cycle(self.repository.database_path)

    def live_positions(self):
        prices = self.market.swap_prices()
        results = []
        for trade in self.repository.open_positions():
            instrument_id = f"{trade['base']}-USDT-SWAP"
            last = prices.get(instrument_id)
            if last is None:
                continue
            direction = 1 if trade["side"] == "LONG" else -1
            live_r = (
                trade["realized_r"]
                + trade["remaining"]
                * (last - trade["entry"])
                * direction
                / trade["risk"]
            )
            results.append(
                {
                    "id": trade["id"],
                    "base": trade["base"],
                    "side": trade["side"],
                    "instrument_id": instrument_id,
                    "last": last,
                    "live_r": live_r,
                }
            )
        return results

    def risk_summary(self):
        active = self.repository.active_positions()
        committed = 0.0
        pending = 0
        opened = 0
        for trade in active:
            if trade["status"] == "PENDING":
                pending += 1
            else:
                opened += 1
            committed += committed_risk_pct(trade)
        return {
            "risk_per_trade_pct": RISK_PCT_PER_TRADE,
            "max_portfolio_risk_pct": MAX_PORTFOLIO_RISK_PCT,
            "risk_guard_enabled": (
                self.repository.portfolio_risk_guard_enabled()
            ),
            "committed_risk_pct": round(committed, 4),
            "pending_orders": pending,
            "open_positions": opened,
            "pending_expiry_bars": PENDING_EXPIRY_BARS,
        }

    def set_portfolio_risk_guard(self, enabled: bool):
        self.repository.set_portfolio_risk_guard(enabled)
        return self.risk_summary()
