from paper_monitor import run_cycle


class DashboardService:
    def __init__(self, repository, market):
        self.repository = repository
        self.market = market

    def snapshot(self):
        return self.repository.snapshot()

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
