"""
TRJM Gateway - API Dependencies
================================
FastAPI dependency injection utilities
"""

from typing import Annotated, Optional

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.logging import logger
from ..core.security import TokenData, verify_token
from ..db.models import Feature, User
from ..db.session import get_db
from ..services.auth.jwt import TokenService, UserService


# =============================================================================
# Database Dependency
# =============================================================================

DBSession = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# Authentication Dependencies
# =============================================================================


async def get_token_from_request(
    request: Request,
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
) -> Optional[str]:
    """
    Extract JWT token from request.

    Checks Authorization header first, then cookies.

    Args:
        request: FastAPI request
        authorization: Authorization header value
        access_token: Cookie value

    Returns:
        Token string if found, None otherwise
    """
    # Try Authorization header first
    if authorization:
        if authorization.startswith("Bearer "):
            return authorization[7:]
        return authorization

    # Try cookie
    if access_token:
        return access_token

    return None


async def get_current_token(
    token: Optional[str] = Depends(get_token_from_request),
) -> TokenData:
    """
    Validate and return current token data.

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def get_current_user(
    db: DBSession,
    token_data: TokenData = Depends(get_current_token),
) -> User:
    """
    Get current authenticated user.

    Raises:
        HTTPException: If user not found or inactive
    """
    user_service = UserService(db)
    user = await user_service.get_user_by_id(token_data.sub)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_optional_user(
    db: DBSession,
    token: Optional[str] = Depends(get_token_from_request),
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    """
    if not token:
        return None

    token_data = verify_token(token)
    if not token_data:
        return None

    user_service = UserService(db)
    user = await user_service.get_user_by_id(token_data.sub)

    if user and user.is_active:
        return user

    return None


# Type aliases for dependency injection
CurrentToken = Annotated[TokenData, Depends(get_current_token)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]


# =============================================================================
# Feature-Based Authorization
# =============================================================================


class RequireFeature:
    """
    Dependency that requires a specific feature.

    Usage:
        @app.get("/admin", dependencies=[Depends(RequireFeature(Feature.ADMIN_PANEL))])
        async def admin_endpoint():
            ...
    """

    def __init__(self, feature: Feature):
        self.feature = feature

    async def __call__(self, user: CurrentUser) -> User:
        if not user.has_feature(self.feature):
            logger.warning(
                "Feature access denied",
                user_id=user.id,
                username=user.username,
                feature=self.feature.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {self.feature.value} feature required",
            )
        return user


def require_feature(feature: Feature):
    """
    Create a dependency that requires a specific feature.

    Usage:
        @app.get("/translate")
        async def translate(user: User = Depends(require_feature(Feature.TRANSLATE_TEXT))):
            ...
    """
    return RequireFeature(feature)


def require_any_feature(*features: Feature):
    """
    Create a dependency that requires any of the specified features.

    Usage:
        @app.get("/files")
        async def files(user: User = Depends(require_any_feature(
            Feature.TRANSLATE_DOCX, Feature.TRANSLATE_PDF
        ))):
            ...
    """

    async def check_features(user: CurrentUser) -> User:
        for feature in features:
            if user.has_feature(feature):
                return user

        feature_names = [f.value for f in features]
        logger.warning(
            "Feature access denied",
            user_id=user.id,
            username=user.username,
            required_features=feature_names,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: one of {feature_names} features required",
        )

    return check_features


# =============================================================================
# Request Context
# =============================================================================


def get_client_ip(request: Request) -> Optional[str]:
    """
    Get client IP address from request.

    Checks X-Forwarded-For header first (for reverse proxy).
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take first IP in chain
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return None


def get_user_agent(request: Request) -> Optional[str]:
    """Get user agent from request."""
    return request.headers.get("User-Agent")


def get_correlation_id(request: Request) -> Optional[str]:
    """Get correlation ID from request state."""
    return getattr(request.state, "correlation_id", None)
