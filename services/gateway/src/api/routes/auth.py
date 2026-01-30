"""
TRJM Gateway - Authentication Routes
=====================================
Login, logout, and session management endpoints
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ...core.config import settings
from ...core.logging import logger
from ...core.security import generate_csrf_token
from ...db.models import AuditAction
from ...services.auth.jwt import AuditService, TokenService, UserService
from ...services.auth.ldap import get_ldap_service
from ..deps import (
    CurrentUser,
    DBSession,
    get_client_ip,
    get_correlation_id,
    get_user_agent,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# Request/Response Models
# =============================================================================


class LoginRequest(BaseModel):
    """Login request payload."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class UserResponse(BaseModel):
    """User information response."""

    id: str
    username: str
    email: Optional[str]
    display_name: Optional[str]
    role: "RoleResponse"
    features: list[str]
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    """Role information response."""

    id: str
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response payload."""

    user: UserResponse
    expires_at: datetime
    csrf_token: str
    dev_mode: bool = Field(default=False)


class LogoutResponse(BaseModel):
    """Logout response payload."""

    message: str = "Logged out successfully"


class SessionResponse(BaseModel):
    """Current session response."""

    user: UserResponse
    valid: bool = True
    dev_mode: bool = Field(default=False)


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    db: DBSession,
    credentials: LoginRequest,
):
    """
    Authenticate user via LDAP and create session.

    Returns JWT token in httpOnly cookie and user information.
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    correlation_id = get_correlation_id(request)

    logger.info(
        "Login attempt",
        username=credentials.username,
        ip=client_ip,
        correlation_id=correlation_id,
    )

    # Authenticate via LDAP
    ldap_service = get_ldap_service()
    ldap_user = await ldap_service.authenticate(credentials.username, credentials.password)

    if not ldap_user:
        # Log failed attempt
        audit_service = AuditService(db)
        await audit_service.log(
            action=AuditAction.LOGIN_FAILED,
            resource="auth",
            details={"username": credentials.username, "reason": "invalid_credentials"},
            ip_address=client_ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
        await db.commit()

        logger.warning("Login failed", username=credentials.username, ip=client_ip)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Create or update user in database
    user_service = UserService(db)
    user = await user_service.create_or_update_user(ldap_user)

    # Create access token
    token_service = TokenService(db)
    token_response = await token_service.create_token_for_user(user)

    # Generate CSRF token
    csrf_token = generate_csrf_token(user.id)

    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token_response.access_token,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="lax",  # Allow cookie on top-level navigation
        max_age=settings.jwt_expiry_hours * 3600,
        path="/",
    )

    # Log successful login
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.LOGIN,
        user_id=user.id,
        resource="auth",
        ip_address=client_ip,
        user_agent=user_agent,
        correlation_id=correlation_id,
    )

    logger.info(
        "Login successful",
        user_id=user.id,
        username=user.username,
        role=user.role.name,
        ip=client_ip,
    )

    return LoginResponse(
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            role=RoleResponse(
                id=user.role.id,
                name=user.role.name,
                description=user.role.description,
            ),
            features=user.role.get_enabled_features(),
            created_at=user.created_at,
            last_login=user.last_login,
        ),
        expires_at=token_response.expires_at,
        csrf_token=csrf_token,
        dev_mode=settings.dev_mode,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    db: DBSession,
    user: CurrentUser,
):
    """
    Log out current user and invalidate session.
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    correlation_id = get_correlation_id(request)

    # Clear the cookie
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    # Log the logout
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.LOGOUT,
        user_id=user.id,
        resource="auth",
        ip_address=client_ip,
        user_agent=user_agent,
        correlation_id=correlation_id,
    )

    logger.info("Logout successful", user_id=user.id, username=user.username)

    return LogoutResponse()


@router.get("/me", response_model=SessionResponse)
async def get_current_session(
    user: CurrentUser,
):
    """
    Get current session information.
    """
    return SessionResponse(
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            role=RoleResponse(
                id=user.role.id,
                name=user.role.name,
                description=user.role.description,
            ),
            features=user.role.get_enabled_features(),
            created_at=user.created_at,
            last_login=user.last_login,
        ),
        valid=True,
        dev_mode=settings.dev_mode,
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: DBSession,
    user: CurrentUser,
):
    """
    Refresh the access token.

    Issues a new token with fresh expiry.
    """
    # Create new token
    token_service = TokenService(db)
    token_response = await token_service.create_token_for_user(user)

    # Generate new CSRF token
    csrf_token = generate_csrf_token(user.id)

    # Set new cookie
    response.set_cookie(
        key="access_token",
        value=token_response.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.jwt_expiry_hours * 3600,
        path="/",
    )

    logger.debug("Token refreshed", user_id=user.id)

    return {
        "expires_at": token_response.expires_at,
        "csrf_token": csrf_token,
    }
