from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.app.core.auth import (
    create_session_token,
    login_rate_limiter,
    read_session_token,
    valid_credentials,
)
from backend.app.core.config import settings


router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    authenticated: bool
    username: str
    expires_at: int


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # Nginx nối địa chỉ peer quan sát được ở cuối X-Forwarded-For.
        return forwarded.rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, response: Response):
    configuration_error = settings.auth_configuration_error
    if configuration_error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=configuration_error,
        )
    client_key = _client_key(request)
    if login_rate_limiter.blocked(client_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều lần đăng nhập sai. Vui lòng thử lại sau.",
        )
    if not valid_credentials(payload.username, payload.password):
        login_rate_limiter.fail(client_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng.",
        )
    login_rate_limiter.reset(client_key)
    token = create_session_token(settings.admin_username)
    session = read_session_token(token)
    _set_session_cookie(response, token)
    return {
        "authenticated": True,
        "username": settings.admin_username,
        "expires_at": session["exp"],
    }


@router.get("/session", response_model=SessionResponse)
def session(request: Request):
    payload = read_session_token(
        request.cookies.get(settings.session_cookie_name)
    )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
        )
    return {
        "authenticated": True,
        "username": payload["sub"],
        "expires_at": payload["exp"],
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
