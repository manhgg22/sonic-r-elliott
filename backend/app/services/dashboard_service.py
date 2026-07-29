from paper_monitor import (
    MAX_PORTFOLIO_RISK_PCT,
    PAPER_EQUITY_USD,
    PENDING_EXPIRY_BARS,
    RISK_PCT_PER_TRADE,
    committed_risk_pct,
    committed_risk_usd,
    run_cycle,
)


class DashboardService:
    def __init__(self, repository, market):
        self.repository = repository
        self.market = market

    def snapshot(self):
        payload = self.repository.snapshot()
        for trade in payload["trades"]:
            risk_amount = float(trade.get("risk_amount_usd") or 0)
            trade["realized_pnl_usd"] = round(
                float(trade.get("realized_r") or 0) * risk_amount,
                4,
            )
            total_r = trade.get("total_r")
            trade["total_pnl_usd"] = (
                None
                if total_r is None
                else round(float(total_r) * risk_amount, 4)
            )
            trade["mfe_usd"] = round(
                float(trade.get("mfe_r") or 0) * risk_amount,
                4,
            )
            trade["mae_usd"] = round(
                float(trade.get("mae_r") or 0) * risk_amount,
                4,
            )
        for event in payload["events"]:
            event["delta_usd"] = round(
                float(event.get("delta_r") or 0)
                * float(event.get("risk_amount_usd") or 0),
                4,
            )
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
                    "live_pnl_usd": (
                        live_r * float(trade["risk_amount_usd"])
                    ),
                    "risk_amount_usd": trade["risk_amount_usd"],
                    "position_size": trade["position_size"],
                    "entry_notional_usd": trade["entry_notional_usd"],
                }
            )
        return results

    def risk_summary(self):
        active = self.repository.active_positions()
        committed = 0.0
        committed_usd = 0.0
        pending = 0
        opened = 0
        for trade in active:
            if trade["status"] == "PENDING":
                pending += 1
            else:
                opened += 1
            committed += committed_risk_pct(trade)
            committed_usd += committed_risk_usd(trade)
        return {
            "paper_equity_usd": PAPER_EQUITY_USD,
            "risk_per_trade_pct": RISK_PCT_PER_TRADE,
            "risk_per_trade_usd": (
                PAPER_EQUITY_USD * RISK_PCT_PER_TRADE / 100
            ),
            "max_portfolio_risk_pct": MAX_PORTFOLIO_RISK_PCT,
            "max_portfolio_risk_usd": (
                PAPER_EQUITY_USD * MAX_PORTFOLIO_RISK_PCT / 100
            ),
            "risk_guard_enabled": (
                self.repository.portfolio_risk_guard_enabled()
            ),
            "committed_risk_pct": round(committed, 4),
            "committed_risk_usd": round(committed_usd, 4),
            "pending_orders": pending,
            "open_positions": opened,
            "pending_expiry_bars": PENDING_EXPIRY_BARS,
        }

    def set_portfolio_risk_guard(self, enabled: bool):
        self.repository.set_portfolio_risk_guard(enabled)
        return self.risk_summary()
