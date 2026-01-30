"""
TRJM Gateway - JWT Token Service
=================================
Token management and user session handling
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.logging import logger
from ...core.security import TokenData, TokenResponse, create_access_token, verify_token
from ...db.models import AuditAction, AuditLog, Feature, Role, RoleFeature, User
from .ldap import LDAPUser


# =============================================================================
# User Management Service
# =============================================================================


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: User's username

        Returns:
            User if found, None otherwise
        """
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.role).selectinload(Role.features))
            .where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User's unique ID

        Returns:
            User if found, None otherwise
        """
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.role).selectinload(Role.features))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_default_role(self) -> Optional[Role]:
        """
        Get the default role for new users.

        Returns:
            Default Role if exists, None otherwise
        """
        result = await self.db.execute(
            select(Role).options(selectinload(Role.features)).where(Role.is_default == True)
        )
        return result.scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """
        Get role by name.

        Args:
            name: Role name

        Returns:
            Role if found, None otherwise
        """
        result = await self.db.execute(
            select(Role).options(selectinload(Role.features)).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def create_or_update_user(self, ldap_user: LDAPUser) -> User:
        """
        Create or update user from LDAP data.

        Args:
            ldap_user: User data from LDAP

        Returns:
            Created or updated User
        """
        # Check if user exists
        user = await self.get_user_by_username(ldap_user.username)

        if user:
            # Update existing user
            user.email = ldap_user.email or user.email
            user.display_name = ldap_user.display_name or user.display_name
            user.last_login = datetime.now(timezone.utc)
            logger.info("Updated existing user", username=ldap_user.username)
        else:
            # Get default role
            default_role = await self.get_default_role()
            if not default_role:
                logger.error("No default role found")
                raise ValueError("No default role configured")

            # Determine role based on LDAP groups
            role = default_role
            if ldap_user.groups:
                # Map LDAP groups to roles
                if "admins" in [g.lower() for g in ldap_user.groups]:
                    admin_role = await self.get_role_by_name("Administrator")
                    if admin_role:
                        role = admin_role
                elif "translators" in [g.lower() for g in ldap_user.groups]:
                    translator_role = await self.get_role_by_name("Translator")
                    if translator_role:
                        role = translator_role

            # Create new user
            user = User(
                username=ldap_user.username,
                email=ldap_user.email,
                display_name=ldap_user.display_name,
                role_id=role.id,
                last_login=datetime.now(timezone.utc),
            )
            self.db.add(user)
            logger.info("Created new user", username=ldap_user.username, role=role.name)

        await self.db.flush()

        # Reload with relationships
        return await self.get_user_by_username(ldap_user.username)

    async def update_last_login(self, user: User) -> None:
        """Update user's last login timestamp."""
        user.last_login = datetime.now(timezone.utc)
        await self.db.flush()


# =============================================================================
# Token Service
# =============================================================================


class TokenService:
    """Service for JWT token operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def create_token_for_user(self, user: User) -> TokenResponse:
        """
        Create access token for authenticated user.

        Args:
            user: Authenticated user

        Returns:
            TokenResponse with access token
        """
        features = user.role.get_enabled_features()

        return create_access_token(
            user_id=user.id,
            username=user.username,
            role_id=user.role_id,
            features=features,
        )

    async def validate_token(self, token: str) -> Optional[TokenData]:
        """
        Validate access token.

        Args:
            token: JWT token string

        Returns:
            TokenData if valid, None otherwise
        """
        return verify_token(token)

    async def get_user_from_token(self, token: str) -> Optional[User]:
        """
        Get user from token.

        Args:
            token: JWT token string

        Returns:
            User if token is valid and user exists, None otherwise
        """
        token_data = await self.validate_token(token)
        if not token_data:
            return None

        return await self.user_service.get_user_by_id(token_data.sub)


# =============================================================================
# Audit Service
# =============================================================================


class AuditService:
    """Service for audit logging."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditLog:
        """
        Create an audit log entry.

        Args:
            action: The action being logged
            user_id: ID of the user performing the action
            resource: Type of resource affected
            resource_id: ID of the resource affected
            details: Additional details as JSON
            ip_address: Client IP address
            user_agent: Client user agent
            correlation_id: Request correlation ID

        Returns:
            Created AuditLog
        """
        audit_log = AuditLog(
            user_id=user_id,
            action=action.value,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
        self.db.add(audit_log)
        await self.db.flush()

        logger.info(
            "Audit log created",
            action=action.value,
            user_id=user_id,
            resource=resource,
            correlation_id=correlation_id,
        )

        return audit_log
