from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.dashboard import router
from backend.app.core.auth import read_session_token
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

public_auth_paths = {
    f"{settings.api_prefix}/auth/login",
    f"{settings.api_prefix}/auth/logout",
    f"{settings.api_prefix}/auth/session",
}
protected_system_paths = {"/docs", "/redoc", "/openapi.json"}


def _add_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' data:; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    return response


@app.middleware("http")
async def require_authenticated_session(request: Request, call_next):
    path = request.url.path
    protected = (
        path in protected_system_paths
        or (
            path.startswith(f"{settings.api_prefix}/")
            and path not in public_auth_paths
        )
    )
    if protected:
        configuration_error = settings.auth_configuration_error
        if configuration_error:
            return _add_security_headers(JSONResponse(
                status_code=503,
                content={"detail": configuration_error},
                headers={"Cache-Control": "no-store"},
            ))
        session = read_session_token(
            request.cookies.get(settings.session_cookie_name)
        )
        if not session:
            return _add_security_headers(JSONResponse(
                status_code=401,
                content={"detail": "Bạn cần đăng nhập để truy cập Sonic R."},
                headers={"Cache-Control": "no-store"},
            ))
    response = await call_next(request)
    if path.startswith(f"{settings.api_prefix}/"):
        response.headers["Cache-Control"] = "no-store"
    return _add_security_headers(response)


@app.get("/health", tags=["system"], response_model=HealthResponse)
def health(response: Response):
    if settings.auth_configuration_error:
        response.status_code = 503
        return {"status": "misconfigured", "service": "sonic-r-api"}
    hub = realtime_market_hub()
    status = "ok" if hub.status["connected"] else "degraded"
    return {"status": status, "service": "sonic-r-api"}


app.include_router(
    auth_router, prefix=f"{settings.api_prefix}/auth", tags=["authentication"]
)
app.include_router(router, prefix=settings.api_prefix, tags=["dashboard"])

# Replit exposes one web port. When the deployment build has produced
# frontend/dist, FastAPI serves the React application and all API/WebSocket
# routes remain same-origin. Docker Compose still uses the dedicated Nginx
# frontend because its routes are registered before this fallback mount.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount(
        "/", StaticFiles(directory=frontend_dist, html=True), name="frontend"
    )
