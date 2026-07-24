"""Lớp dữ liệu dùng chung cho dashboard Sonic R."""

from pathlib import Path

import pandas as pd
import requests

from paper_monitor import connect


class DashboardBackend:
    """Đọc dữ liệu đã lưu và lấy giá công khai từ OKX."""

    def __init__(self, db_path, timeout=5):
        self.db_path = Path(db_path)
        self.timeout = timeout
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": "Sonic-R-Paper-Monitor/1.0"})

    def load(self):
        conn = connect(self.db_path)
        try:
            setups = pd.read_sql_query("SELECT * FROM latest_setups", conn)
            runs = pd.read_sql_query(
                "SELECT * FROM scan_runs ORDER BY id DESC LIMIT 96", conn
            )
            trades = pd.read_sql_query(
                "SELECT * FROM paper_trades ORDER BY id DESC", conn
            )
            events = pd.read_sql_query(
                "SELECT * FROM paper_events ORDER BY id DESC LIMIT 500", conn
            )
        finally:
            conn.close()

        for frame, columns in [
            (setups, ["signal_time"]),
            (runs, ["scanned_at"]),
            (trades, ["opened_at", "last_bar_time", "closed_at"]),
            (events, ["event_at"]),
        ]:
            for column in columns:
                if column in frame:
                    frame[column] = pd.to_datetime(
                        frame[column], utc=True, errors="coerce"
                    )
        return setups, runs, trades, events

    def fetch_swap_prices(self):
        response = self.http.get(
            "https://www.okx.com/api/v5/market/tickers",
            params={"instType": "SWAP"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "0":
            raise RuntimeError(payload.get("msg") or "OKX trả về lỗi không xác định")
        return {
            item["instId"]: float(item["last"])
            for item in payload.get("data", [])
            if item.get("instId") and item.get("last")
        }

    @staticmethod
    def live_positions(open_positions, prices):
        positions = []
        for _, trade in open_positions.iterrows():
            inst_id = f"{trade['base']}-USDT-SWAP"
            last = prices.get(inst_id)
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
            positions.append(
                {
                    "id": int(trade["id"]),
                    "base": trade["base"],
                    "side": trade["side"],
                    "inst_id": inst_id,
                    "last": last,
                    "live_r": live_r,
                }
            )
        return positions
