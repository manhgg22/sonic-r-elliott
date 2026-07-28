from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.dashboard import router
from backend.app.core.config import settings
from backend.app.schemas.dashboard import HealthResponse
from backend.app.api.dependencies import realtime_market_hub
from paper_monitor import connect


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database = connect(settings.database_path)
    database.close()
    hub = realtime_market_hub()
    await hub.start()
    yield
    await hub.stop()


app = FastAPI(
    title="Sonic R API",
    version="1.1.0",
    description=(
        "API vận hành Sonic R: scanner, paper positions, nến thị trường và "
        "realtime WebSocket. Mở `/api/v1/market/console` để quan sát luồng "
        "ticker/candle trực tiếp. Tín hiệu chiến lược chỉ xác nhận trên nến "
        "đã đóng."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "system",
            "description": "Health và trạng thái dịch vụ.",
        },
        {
            "name": "dashboard",
            "description": (
                "Snapshot, scanner, vị thế, candle REST và realtime status."
            ),
        },
    ],
)
app.add_middleware(
    CORSMiddleware,
    # Frontend chạy same-origin qua proxy (Vite :5173 / nginx :8501); danh sách
    # này chỉ phục vụ trường hợp gọi API trực tiếp từ origin của frontend.
    allow_origins=[
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:8501", "http://localhost:8501",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"], response_model=HealthResponse)
def health():
    hub = realtime_market_hub()
    status = "ok" if hub.status["connected"] else "degraded"
    return {"status": status, "service": "sonic-r-api"}


app.include_router(router, prefix=settings.api_prefix, tags=["dashboard"])
