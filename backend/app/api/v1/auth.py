"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AuthSvc, CurrentUser, UserSvc
from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError
from app.core.logging import get_logger
from app.core.rate_limit import AUTH_LIMIT, PASSWORD_RESET_LIMIT, client_ip, enforce
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserProfile

logger = get_logger(__name__)
router = APIRouter(tags=["auth"])

REFRESH_COOKIE = "graphmaster_refresh"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Deliver the refresh token as an HttpOnly cookie.

    HttpOnly so client-side JavaScript cannot read it, which is what limits the
    damage of an XSS bug to the short-lived access token held in memory.
    """
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.is_production,  # a Secure cookie is dropped over plain HTTP in dev
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/")


def _read_refresh_token(request: Request, payload: RefreshRequest | None) -> str | None:
    """Prefer the cookie; fall back to the body.

    The body form exists for clients that cannot hold cookies (a mobile app,
    an automated test); browsers use the cookie.
    """
    if payload is not None and payload.refresh_token:
        return payload.refresh_token
    return request.cookies.get(REFRESH_COOKIE)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a student account",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    auth: AuthSvc,
    users: UserSvc,
) -> AuthResponse:
    enforce(request, AUTH_LIMIT, key_suffix="auth")

    user, tokens = await auth.register(
        payload,
        user_agent=request.headers.get("User-Agent"),
        ip_address=client_ip(request),
    )
    _set_refresh_cookie(response, tokens.refresh_token)

    return AuthResponse(
        user=UserProfile.model_validate(await users.get_profile(user.id)),
        tokens=TokenPair(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
        ),
    )


@router.post("/login", response_model=AuthResponse, summary="Sign in")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthSvc,
    users: UserSvc,
) -> AuthResponse:
    enforce(request, AUTH_LIMIT, key_suffix="auth")

    user, tokens = await auth.login(
        payload.email,
        payload.password,
        user_agent=request.headers.get("User-Agent"),
        ip_address=client_ip(request),
    )
    _set_refresh_cookie(response, tokens.refresh_token)

    return AuthResponse(
        user=UserProfile.model_validate(await users.get_profile(user.id)),
        tokens=TokenPair(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
        ),
    )


@router.post("/refresh", response_model=TokenPair, summary="Rotate the refresh token")
async def refresh(
    request: Request,
    response: Response,
    auth: AuthSvc,
    payload: RefreshRequest | None = None,
) -> TokenPair:
    token = _read_refresh_token(request, payload)
    if not token:
        raise InvalidTokenError("No refresh token was supplied.")

    _, tokens = await auth.refresh(
        token,
        user_agent=request.headers.get("User-Agent"),
        ip_address=client_ip(request),
    )
    _set_refresh_cookie(response, tokens.refresh_token)

    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=MessageResponse, summary="Revoke the current session")
async def logout(
    request: Request,
    response: Response,
    auth: AuthSvc,
    payload: RefreshRequest | None = None,
) -> MessageResponse:
    # Deliberately unauthenticated: an expired access token must not stop
    # someone signing out, or a stale session could never be cleared.
    await auth.logout(_read_refresh_token(request, payload))
    _clear_refresh_cookie(response)
    return MessageResponse(message="Signed out.")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Revoke every session for the current user",
)
async def logout_all(response: Response, auth: AuthSvc, user: CurrentUser) -> MessageResponse:
    count = await auth.logout_all(user.id)
    _clear_refresh_cookie(response)
    return MessageResponse(message=f"Signed out of {count} session(s).")


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Request a password reset",
)
async def request_password_reset(
    payload: PasswordResetRequest, request: Request, auth: AuthSvc
) -> MessageResponse:
    enforce(request, PASSWORD_RESET_LIMIT, key_suffix="password-reset")

    token = await auth.request_password_reset(payload.email)

    if token:
        # Email delivery is out of scope for this sprint. Logged at debug so a
        # developer can complete the flow locally; it never reaches the
        # response, which would hand anyone a reset for any address.
        logger.debug("Password reset token for %s: %s", payload.email, token)

    # Identical response whether or not the account exists — a different one
    # would turn this endpoint into an account-enumeration oracle.
    return MessageResponse(
        message="If an account exists for that email, a reset link has been sent."
    )


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Set a new password using a reset token",
)
async def confirm_password_reset(
    payload: PasswordResetConfirm, response: Response, auth: AuthSvc
) -> MessageResponse:
    await auth.confirm_password_reset(payload.token, payload.new_password)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Password updated. Please sign in again.")


@router.post("/change-password", response_model=MessageResponse, summary="Change your own password")
async def change_password(
    payload: ChangePasswordRequest, response: Response, auth: AuthSvc, user: CurrentUser
) -> MessageResponse:
    await auth.change_password(user, payload.current_password, payload.new_password)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Password updated. Please sign in again.")
