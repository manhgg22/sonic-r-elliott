import pandas as pd
import requests


class OkxMarketService:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": "Sonic-R-API/1.0"})

    def _get(self, path, params):
        response = self.http.get(
            f"{self.base_url}{path}", params=params, timeout=self.timeout
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "0":
            raise RuntimeError(payload.get("msg") or "OKX API error")
        return payload.get("data", [])

    def swap_prices(self):
        return {
            item["instId"]: float(item["last"])
            for item in self._get(
                "/api/v5/market/tickers", {"instType": "SWAP"}
            )
            if item.get("instId") and item.get("last")
        }

    def candles(self, instrument_id, bar="15m", limit=300):
        rows = self._get(
            "/api/v5/market/candles",
            {"instId": instrument_id, "bar": bar, "limit": limit},
        )
        columns = [
            "timestamp", "open", "high", "low", "close",
            "volume", "volume_ccy", "volume_quote", "confirmed",
        ]
        frame = pd.DataFrame(rows, columns=columns)
        if frame.empty:
            return []
        numeric = ["open", "high", "low", "close", "volume"]
        frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
        frame["timestamp"] = pd.to_datetime(
            pd.to_numeric(frame["timestamp"]), unit="ms", utc=True
        )
        frame["confirmed"] = frame["confirmed"].eq("1")
        frame = frame.sort_values("timestamp").reset_index(drop=True)
        frame["ema34"] = frame["close"].ewm(span=34, adjust=False).mean()
        frame["ema89"] = frame["close"].ewm(span=89, adjust=False).mean()
        frame["timestamp"] = frame["timestamp"].map(lambda value: value.isoformat())
        return frame.to_dict("records")
