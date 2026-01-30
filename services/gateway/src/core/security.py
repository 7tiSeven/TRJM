"""
TRJM Gateway - Security Utilities
==================================
JWT handling, password hashing, CSRF tokens, and security helpers
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings


# =============================================================================
# JWT Token Models
# =============================================================================


class TokenData(BaseModel):
    """JWT token payload data."""

    sub: str  # Subject (user_id)
    username: str
    role_id: str
    features: list[str]
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for revocation


class TokenResponse(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


# =============================================================================
# JWT Functions
# =============================================================================


def create_access_token(
    user_id: str,
    username: str,
    role_id: str,
    features: list[str],
    expires_delta: Optional[timedelta] = None,
) -> TokenResponse:
    """
    Create a new JWT access token.

    Args:
        user_id: User's unique identifier
        username: User's username
        role_id: User's role ID
        features: List of enabled features for the user
        expires_delta: Optional custom expiry time

    Returns:
        TokenResponse with access token and expiry
    """
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=settings.jwt_expiry_hours)

    token_data = TokenData(
        sub=user_id,
        username=username,
        role_id=role_id,
        features=features,
        exp=expire,
        iat=now,
        jti=str(uuid4()),
    )

    # JWT requires exp/iat as Unix timestamps, not ISO strings
    payload = token_data.model_dump()
    payload["exp"] = int(expire.timestamp())
    payload["iat"] = int(now.timestamp())

    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    return TokenResponse(
        access_token=encoded_jwt,
        expires_at=expire,
    )


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT access token.

    Args:
        token: The JWT token string

    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        # Convert Unix timestamps back to datetime
        if isinstance(payload.get("exp"), (int, float)):
            payload["exp"] = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        if isinstance(payload.get("iat"), (int, float)):
            payload["iat"] = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        return TokenData(**payload)
    except JWTError:
        return None


def verify_token(token: str) -> Optional[TokenData]:
    """
    Verify token and check expiration.

    Args:
        token: The JWT token string

    Returns:
        TokenData if valid and not expired, None otherwise
    """
    token_data = decode_access_token(token)
    if token_data is None:
        return None

    # Check expiration
    if token_data.exp < datetime.now(timezone.utc):
        return None

    return token_data


# =============================================================================
# CSRF Token Functions
# =============================================================================


def generate_csrf_token(session_id: str) -> str:
    """
    Generate a CSRF token tied to a session.

    Args:
        session_id: The session identifier

    Returns:
        CSRF token string
    """
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    random_bytes = secrets.token_hex(16)
    message = f"{session_id}:{timestamp}:{random_bytes}"
    signature = hmac.new(
        settings.csrf_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{message}:{signature}"


def verify_csrf_token(token: str, session_id: str, max_age_seconds: int = 3600) -> bool:
    """
    Verify a CSRF token.

    Args:
        token: The CSRF token to verify
        session_id: The expected session ID
        max_age_seconds: Maximum token age in seconds

    Returns:
        True if valid, False otherwise
    """
    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return False

        message, signature = parts
        expected_signature = hmac.new(
            settings.csrf_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return False

        # Parse message parts
        msg_parts = message.split(":")
        if len(msg_parts) != 3:
            return False

        token_session_id, timestamp, _ = msg_parts

        # Verify session ID
        if token_session_id != session_id:
            return False

        # Verify age
        token_time = int(timestamp)
        current_time = int(datetime.now(timezone.utc).timestamp())
        if current_time - token_time > max_age_seconds:
            return False

        return True

    except (ValueError, TypeError):
        return False


# =============================================================================
# Correlation ID
# =============================================================================


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracking."""
    return str(uuid4())


# =============================================================================
# Security Headers
# =============================================================================


SECURITY_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}


def get_csp_header() -> str:
    """
    Get Content-Security-Policy header value.

    Returns:
        CSP header string
    """
    directives = [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'self'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    return "; ".join(directives)
