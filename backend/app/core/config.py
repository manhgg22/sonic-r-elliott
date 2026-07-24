import os
from pathlib import Path


class Settings:
    api_prefix = "/api/v1"
    database_path = Path(os.getenv("SONIC_DB_PATH", "results/paper_trading.db"))
    okx_base_url = os.getenv("OKX_BASE_URL", "https://www.okx.com")
    request_timeout = float(os.getenv("OKX_TIMEOUT_SECONDS", "5"))
    okx_ws_url = os.getenv(
        "OKX_WS_URL", "wss://ws.okx.com:8443/ws/v5/public"
    )
    okx_candle_ws_url = os.getenv(
        "OKX_CANDLE_WS_URL", "wss://ws.okx.com:8443/ws/v5/business"
    )
    realtime_max_instruments = int(
        os.getenv("SONIC_REALTIME_MAX_INSTRUMENTS", "50")
    )
    realtime_stale_seconds = float(
        os.getenv("SONIC_REALTIME_STALE_SECONDS", "10")
    )
    realtime_broadcast_interval = float(
        os.getenv("SONIC_REALTIME_BROADCAST_INTERVAL", "0.25")
    )


settings = Settings()
