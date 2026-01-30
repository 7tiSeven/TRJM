"""
TRJM Gateway - Rate Limiting Middleware
========================================
Request rate limiting per user and per IP
"""

from typing import Callable, Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from ...core.config import settings
from ...core.logging import logger


def get_identifier(request: Request) -> str:
    """
    Get rate limit identifier from request.

    Uses user ID if authenticated, otherwise IP address.
    """
    # Try to get user ID from request state (set by auth)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"

    if request.client:
        return f"ip:{request.client.host}"

    return "ip:unknown"


# Create limiter instance
limiter = Limiter(
    key_func=get_identifier,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    storage_uri="memory://",  # Use Redis in production for distributed rate limiting
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom handler for rate limit exceeded errors."""
    logger.warning(
        "Rate limit exceeded",
        identifier=get_identifier(request),
        path=request.url.path,
    )

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Rate limit exceeded. Please try again later.",
            "retry_after": exc.detail,
        },
        headers={"Retry-After": str(60)},  # Suggest retry after 60 seconds
    )


def setup_rate_limit_middleware(app: FastAPI) -> None:
    """
    Configure rate limiting middleware for the application.

    Args:
        app: FastAPI application instance
    """
    # Attach limiter to app state
    app.state.limiter = limiter

    # Add error handler
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Add middleware
    app.add_middleware(SlowAPIMiddleware)

    logger.info(
        "Rate limiting configured",
        limit=f"{settings.rate_limit_per_minute}/minute",
    )


# Decorator for custom rate limits on specific endpoints
def rate_limit(limit: str):
    """
    Decorator to apply custom rate limit to an endpoint.

    Usage:
        @app.get("/expensive-operation")
        @rate_limit("5/minute")
        async def expensive_operation():
            ...
    """
    return limiter.limit(limit)
