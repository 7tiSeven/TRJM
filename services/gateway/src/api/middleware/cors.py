"""
TRJM Gateway - CORS Middleware Configuration
=============================================
Cross-Origin Resource Sharing configuration
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ...core.config import settings
from ...core.logging import logger


def setup_cors_middleware(app: FastAPI) -> None:
    """
    Configure CORS middleware for the application.

    Uses strict allowlist from configuration.

    Args:
        app: FastAPI application instance
    """
    origins = settings.cors_origins_list

    if not origins:
        logger.warning("No CORS origins configured, using default localhost")
        origins = ["https://localhost:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-Correlation-ID",
            "X-CSRF-Token",
        ],
        expose_headers=[
            "X-Correlation-ID",
            "X-Response-Time",
            "Content-Disposition",
        ],
        max_age=600,  # Cache preflight for 10 minutes
    )

    logger.info("CORS middleware configured", origins=origins)
