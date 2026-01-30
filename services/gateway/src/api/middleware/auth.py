"""
TRJM Gateway - Authentication Middleware
=========================================
JWT token extraction and validation middleware
"""

from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...core.logging import logger
from ...core.security import verify_token


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and validate JWT tokens.

    Sets user information in request state for downstream handlers.
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/auth/login",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Try to extract token
        token = self._extract_token(request)

        if token:
            # Validate token
            token_data = verify_token(token)

            if token_data:
                # Set user info in request state
                request.state.user_id = token_data.sub
                request.state.username = token_data.username
                request.state.role_id = token_data.role_id
                request.state.features = token_data.features
                request.state.authenticated = True
            else:
                request.state.authenticated = False
                logger.debug("Invalid or expired token", path=request.url.path)
        else:
            request.state.authenticated = False

        return await call_next(request)

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from request."""
        # Try Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header:
            if auth_header.startswith("Bearer "):
                return auth_header[7:]
            return auth_header

        # Try cookie
        return request.cookies.get("access_token")


def setup_auth_middleware(app) -> None:
    """
    Configure authentication middleware.

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(AuthenticationMiddleware)
    logger.info("Authentication middleware configured")
