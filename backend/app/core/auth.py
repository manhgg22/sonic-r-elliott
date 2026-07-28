import base64
import binascii
import hashlib
import hmac
import json
import threading
import time
from collections import defaultdict, deque
from typing import Any

from backend.app.core.config import settings


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_session_token(username: str, now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = {
        "exp": issued_at + settings.session_ttl_seconds,
        "iat": issued_at,
        "sub": username,
    }
    encoded = _encode(
        json.dumps(
            payload, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    )
    signature = hmac.new(
        settings.session_secret.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded}.{_encode(signature)}"


def read_session_token(
    token: str | None, now: int | None = None
) -> dict[str, Any] | None:
    if not token or settings.auth_configuration_error:
        return None
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(
            settings.session_secret.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(
            expected_signature, _decode(supplied_signature)
        ):
            return None
        payload = json.loads(_decode(encoded))
        current_time = int(time.time() if now is None else now)
        if (
            payload.get("sub") != settings.admin_username
            or not isinstance(payload.get("exp"), int)
            or payload["exp"] <= current_time
        ):
            return None
        return payload
    except (
        ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error
    ):
        return None


def valid_credentials(username: str, password: str) -> bool:
    if settings.auth_configuration_error:
        return False
    username_ok = hmac.compare_digest(
        username.encode("utf-8"), settings.admin_username.encode("utf-8")
    )
    password_ok = hmac.compare_digest(
        password.encode("utf-8"), settings.admin_password.encode("utf-8")
    )
    return username_ok and password_ok


class LoginRateLimiter:
    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> deque[float]:
        attempts = self._attempts[key]
        cutoff = now - settings.login_window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts:
            self._attempts.pop(key, None)
            return deque()
        return attempts

    def blocked(self, key: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            attempts = self._trim(key, current)
            return len(attempts) >= settings.login_max_attempts

    def fail(self, key: str, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            attempts = self._trim(key, current)
            attempts.append(current)
            self._attempts[key] = attempts

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


login_rate_limiter = LoginRateLimiter()
