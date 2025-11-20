"""ASGI middleware ensuring each request carries a valid session cookie."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .services import (
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SessionNotFoundError,
    session_runtime,
)


def _secure_cookie_default() -> bool:
    value = os.getenv("PLAYGROUND_SESSION_COOKIE_SECURE", "").lower()
    return value in {"1", "true", "yes", "on"}


def issue_session_cookie(
    response: Response, session_id: str, *, secure: bool | None = None
) -> None:
    flag = _secure_cookie_default() if secure is None else secure
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        samesite="lax",
        secure=flag,
        max_age=SESSION_COOKIE_MAX_AGE,
        path="/",
    )


class SessionCookieMiddleware(BaseHTTPMiddleware):
    """Ensure every HTTP request has a server-issued session cookie."""

    def __init__(self, app, *, secure: bool | None = None):
        super().__init__(app)
        self._secure = _secure_cookie_default() if secure is None else secure

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.cookies.get(SESSION_COOKIE_NAME)
        try:
            metadata, created = session_runtime.resolve_or_create(
                incoming,
                create_if_missing=False,
            )
            request.state.session_id = metadata.session_id
        except SessionNotFoundError:
            metadata, created = None, False
            request.state.session_id = None
        response = await call_next(request)
        if metadata and (created or incoming != metadata.session_id):
            issue_session_cookie(response, metadata.session_id, secure=self._secure)
        return response
