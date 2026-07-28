from functools import lru_cache

from backend.app.core.config import settings
from backend.app.repositories.trading_repository import TradingRepository
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.okx_market_service import OkxMarketService
from backend.app.services.realtime_market import RealtimeMarketHub


@lru_cache
def dashboard_service():
    repository = TradingRepository(settings.database_target)
    market = OkxMarketService(settings.okx_base_url, settings.request_timeout)
    return DashboardService(repository, market)


def _realtime_instruments():
    payload = dashboard_service().repository.snapshot()
    instruments = []
    for row in payload.get("setups", []):
        symbol = row.get("symbol") or row.get("base")
        if symbol:
            instruments.append(symbol)
    for row in dashboard_service().repository.active_positions():
        base = row.get("base")
        if base:
            instruments.append(base)
    return instruments


@lru_cache
def realtime_market_hub():
    return RealtimeMarketHub(
        settings.okx_ws_url,
        candle_ws_url=settings.okx_candle_ws_url,
        instrument_provider=_realtime_instruments,
        max_instruments=settings.realtime_max_instruments,
        stale_seconds=settings.realtime_stale_seconds,
        broadcast_interval=settings.realtime_broadcast_interval,
    )
