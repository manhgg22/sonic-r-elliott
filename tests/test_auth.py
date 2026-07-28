from backend.app.core.auth import (
    LoginRateLimiter,
    create_session_token,
    read_session_token,
    valid_credentials,
)
from backend.app.core.config import settings


def configure_auth(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "operator")
    monkeypatch.setattr(settings, "admin_password", "a-strong-password")
    monkeypatch.setattr(
        settings, "session_secret", "s" * 48
    )
    monkeypatch.setattr(settings, "session_ttl_seconds", 3600)


def test_session_token_is_signed_and_expires(monkeypatch):
    configure_auth(monkeypatch)
    token = create_session_token("operator", now=1_000)
    session = read_session_token(token, now=1_001)
    assert session["sub"] == "operator"
    assert session["exp"] == 4_600
    assert read_session_token(token, now=4_600) is None


def test_session_token_rejects_tampering(monkeypatch):
    configure_auth(monkeypatch)
    token = create_session_token("operator", now=1_000)
    payload, signature = token.split(".", 1)
    changed = ("A" if payload[0] != "A" else "B") + payload[1:]
    assert read_session_token(f"{changed}.{signature}", now=1_001) is None


def test_credentials_fail_closed_when_configuration_is_weak(monkeypatch):
    configure_auth(monkeypatch)
    assert valid_credentials("operator", "a-strong-password")
    assert not valid_credentials("operator", "wrong-password")
    monkeypatch.setattr(settings, "session_secret", "too-short")
    assert settings.auth_configuration_error
    assert not valid_credentials("operator", "a-strong-password")


def test_login_rate_limiter_resets_after_window(monkeypatch):
    configure_auth(monkeypatch)
    monkeypatch.setattr(settings, "login_max_attempts", 2)
    monkeypatch.setattr(settings, "login_window_seconds", 10)
    limiter = LoginRateLimiter()
    limiter.fail("client", now=1)
    limiter.fail("client", now=2)
    assert limiter.blocked("client", now=3)
    assert not limiter.blocked("client", now=12)
