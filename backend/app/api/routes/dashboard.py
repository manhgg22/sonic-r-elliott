from typing import Literal

import asyncio
import json
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from requests import RequestException

from backend.app.api.dependencies import dashboard_service, realtime_market_hub
from backend.app.schemas.dashboard import (
    CandleResponse,
    LivePositionsResponse,
    ScanResponse,
    SnapshotResponse,
    RealtimeSnapshotResponse,
    RealtimeStatusResponse,
)
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.realtime_market import RealtimeMarketHub
from backend.app.api.realtime_console import REALTIME_CONSOLE_HTML


router = APIRouter()


@router.get(
    "/market/realtime/status",
    response_model=RealtimeStatusResponse,
    summary="Realtime market health",
    description=(
        "Trạng thái kết nối ticker/candle OKX, độ trễ dữ liệu, số mã đang "
        "theo dõi và số WebSocket client."
    ),
)
def realtime_status(
    hub: RealtimeMarketHub = Depends(realtime_market_hub),
):
    return hub.health()


@router.get(
    "/market/realtime/snapshot",
    response_model=RealtimeSnapshotResponse,
    summary="Latest realtime snapshot",
    description=(
        "Snapshot ticker và nến M15 mới nhất trong bộ nhớ. Dùng để khởi tạo "
        "giao diện trước khi tiếp tục nhận delta qua WebSocket."
    ),
)
def realtime_snapshot(
    hub: RealtimeMarketHub = Depends(realtime_market_hub),
):
    return hub.snapshot()


@router.websocket("/market/stream")
async def market_stream(
    websocket: WebSocket,
    hub: RealtimeMarketHub = Depends(realtime_market_hub),
):
    await websocket.accept()
    queue = hub.subscribe()
    try:
        await websocket.send_text(json.dumps(hub.snapshot()))
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=10)
            except asyncio.TimeoutError:
                message = json.dumps({
                    "type": "heartbeat",
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "status": hub.health(),
                })
            await websocket.send_text(message)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(queue)


@router.get(
    "/market/console",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def realtime_console():
    return REALTIME_CONSOLE_HTML


@router.get(
    "/terminal/snapshot",
    response_model=SnapshotResponse,
    summary="Analytical Terminal snapshot",
)
def get_snapshot(service: DashboardService = Depends(dashboard_service)):
    return service.snapshot()


@router.get("/positions/live", response_model=LivePositionsResponse)
def get_live_positions(service: DashboardService = Depends(dashboard_service)):
    try:
        return {"positions": service.live_positions()}
    except (RequestException, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/market/candles/{instrument_id}", response_model=CandleResponse)
def get_candles(
    instrument_id: str,
    bar: Literal["1m", "5m", "15m", "1H", "4H", "1D"] = "15m",
    limit: int = Query(300, ge=50, le=300),
    service: DashboardService = Depends(dashboard_service),
):
    try:
        candles = service.market.candles(instrument_id, bar=bar, limit=limit)
        return {"instrument_id": instrument_id, "bar": bar, "candles": candles}
    except (RequestException, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/scanner/run", response_model=ScanResponse)
def run_scanner(service: DashboardService = Depends(dashboard_service)):
    try:
        summary = service.run_scan()
    except (RequestException, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if summary.get("skipped"):
        raise HTTPException(
            status_code=409,
            detail="Đã có lượt quét đang chạy, vui lòng thử lại sau.",
        )
    return summary
