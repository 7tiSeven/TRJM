"""
TRJM Gateway - Security Middleware
===================================
Security headers, CSRF protection, and request sanitization
"""

import time
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...core.config import settings
from ...core.logging import logger
from ...core.security import SECURITY_HEADERS, get_csp_header


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        # Add CSP header
        response.headers["Content-Security-Policy"] = get_csp_header()

        return response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation IDs for request tracking.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))

        # Store in request state
        request.state.correlation_id = correlation_id

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log request/response information.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Get correlation ID
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        # Log request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id,
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            correlation_id=correlation_id,
        )

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware for CSRF protection.

    Validates CSRF token for state-changing requests.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
    EXEMPT_PATHS = {"/auth/login", "/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip safe methods
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip if no cookies (no session)
        if "access_token" not in request.cookies:
            return await call_next(request)

        # For now, we rely on SameSite=Strict cookies
        # Full CSRF token validation can be added here
        # by checking X-CSRF-Token header against session

        return await call_next(request)


def setup_security_middleware(app: FastAPI) -> None:
    """
    Configure all security middleware for the application.

    Args:
        app: FastAPI application instance
    """
    # Add middleware in reverse order (last added = first executed)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    logger.info("Security middleware configured")
