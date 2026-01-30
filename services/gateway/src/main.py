"""
TRJM Gateway - Main Application
================================
FastAPI application entry point
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api.middleware.auth import setup_auth_middleware
from .api.middleware.cors import setup_cors_middleware
from .api.middleware.rate_limit import setup_rate_limit_middleware
from .api.middleware.security import setup_security_middleware
from .api.routes import admin, auth, files, glossary, history, translation
from .core.config import settings
from .core.logging import logger
from .db.session import check_db_health, close_db, init_db


# =============================================================================
# Application Lifespan
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan handler.

    Manages startup and shutdown events.
    """
    # Startup
    logger.info(
        "Starting TRJM Gateway",
        version=settings.app_version,
        dev_mode=settings.dev_mode,
        llm_provider=settings.llm_provider,
    )

    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down TRJM Gateway")
    await close_db()
    logger.info("Database connection closed")


# =============================================================================
# Application Factory
# =============================================================================


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="TRJM Gateway",
        description="Agentic AI Translator - API Gateway",
        version=settings.app_version,
        docs_url="/docs" if settings.dev_mode else None,
        redoc_url="/redoc" if settings.dev_mode else None,
        openapi_url="/openapi.json" if settings.dev_mode else None,
        lifespan=lifespan,
    )

    # Setup middleware (order matters!)
    setup_cors_middleware(app)
    setup_rate_limit_middleware(app)
    setup_auth_middleware(app)
    setup_security_middleware(app)

    # Register exception handlers
    register_exception_handlers(app)

    # Register routes
    register_routes(app)

    return app


# =============================================================================
# Exception Handlers
# =============================================================================


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle validation errors with user-friendly messages."""
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append({"field": field, "message": error["msg"]})

        logger.warning(
            "Validation error",
            path=request.url.path,
            errors=errors,
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": errors,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        correlation_id = getattr(request.state, "correlation_id", None)

        logger.exception(
            "Unhandled exception",
            path=request.url.path,
            correlation_id=correlation_id,
            error=str(exc),
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "correlation_id": correlation_id,
            },
        )


# =============================================================================
# Route Registration
# =============================================================================


def register_routes(app: FastAPI) -> None:
    """Register all API routes."""

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint.

        Returns service health status.
        """
        db_healthy = await check_db_health()

        return {
            "status": "healthy" if db_healthy else "degraded",
            "version": settings.app_version,
            "dev_mode": settings.dev_mode,
            "database": "connected" if db_healthy else "disconnected",
        }

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "TRJM Gateway",
            "version": settings.app_version,
            "description": "Agentic AI Translator API",
            "docs": "/docs" if settings.dev_mode else None,
        }

    # Register route modules
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(translation.router)
    app.include_router(glossary.router)
    app.include_router(history.router)
    app.include_router(files.router)

    logger.info("Routes registered")


# =============================================================================
# Application Instance
# =============================================================================

app = create_application()


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.dev_mode,
        log_level=settings.log_level.lower(),
    )
