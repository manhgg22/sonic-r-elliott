import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    admin_username = os.getenv("SONIC_ADMIN_USERNAME", "admin").strip()
    admin_password = os.getenv("SONIC_ADMIN_PASSWORD", "")
    session_secret = os.getenv("SONIC_SESSION_SECRET", "")
    session_cookie_name = "sonic_session"
    session_ttl_seconds = int(
        float(os.getenv("SONIC_SESSION_TTL_HOURS", "12")) * 3600
    )
    cookie_secure = _env_bool("SONIC_COOKIE_SECURE", False)
    login_max_attempts = int(os.getenv("SONIC_LOGIN_MAX_ATTEMPTS", "5"))
    login_window_seconds = int(os.getenv("SONIC_LOGIN_WINDOW_SECONDS", "300"))

    @property
    def auth_configuration_error(self) -> str | None:
        if not self.admin_username:
            return "SONIC_ADMIN_USERNAME không được để trống."
        if len(self.admin_password) < 12:
            return "SONIC_ADMIN_PASSWORD phải có ít nhất 12 ký tự."
        if len(self.session_secret) < 32:
            return "SONIC_SESSION_SECRET phải có ít nhất 32 ký tự."
        if self.session_ttl_seconds < 300:
            return "SONIC_SESSION_TTL_HOURS phải tương đương ít nhất 5 phút."
        if self.login_max_attempts < 1 or self.login_window_seconds < 1:
            return "Giới hạn đăng nhập phải là số nguyên dương."
        return None


settings = Settings()
