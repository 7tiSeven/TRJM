"""
TRJM Gateway - LDAP Authentication Service
==========================================
LDAP bind authentication with mock provider for development
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ...core.config import settings
from ...core.logging import logger


# =============================================================================
# LDAP User Data
# =============================================================================


@dataclass
class LDAPUser:
    """User data from LDAP authentication."""

    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    groups: list[str] = None

    def __post_init__(self):
        if self.groups is None:
            self.groups = []


# =============================================================================
# LDAP Provider Interface
# =============================================================================


class LDAPProvider(ABC):
    """Abstract base class for LDAP providers."""

    @abstractmethod
    async def authenticate(self, username: str, password: str) -> Optional[LDAPUser]:
        """
        Authenticate user against LDAP.

        Args:
            username: User's username
            password: User's password

        Returns:
            LDAPUser if authentication successful, None otherwise
        """
        pass

    @abstractmethod
    async def get_user_info(self, username: str) -> Optional[LDAPUser]:
        """
        Get user information from LDAP.

        Args:
            username: User's username

        Returns:
            LDAPUser if found, None otherwise
        """
        pass


# =============================================================================
# Mock LDAP Provider (Development)
# =============================================================================


class MockLDAPProvider(LDAPProvider):
    """
    Mock LDAP provider for development and testing.

    Provides predefined users for testing different roles.
    """

    # Predefined mock users
    MOCK_USERS = {
        "admin": {
            "password": "admin123",
            "email": "admin@trjm.local",
            "display_name": "Administrator",
            "groups": ["admins", "translators"],
        },
        "translator": {
            "password": "trans123",
            "email": "translator@trjm.local",
            "display_name": "Senior Translator",
            "groups": ["translators"],
        },
        "user": {
            "password": "user123",
            "email": "user@trjm.local",
            "display_name": "Regular User",
            "groups": ["users"],
        },
    }

    async def authenticate(self, username: str, password: str) -> Optional[LDAPUser]:
        """Authenticate against mock user database."""
        logger.debug("Mock LDAP authentication attempt", username=username)

        user_data = self.MOCK_USERS.get(username.lower())
        if user_data is None:
            logger.debug("Mock LDAP: user not found", username=username)
            return None

        if user_data["password"] != password:
            logger.debug("Mock LDAP: invalid password", username=username)
            return None

        logger.info("Mock LDAP: authentication successful", username=username)
        return LDAPUser(
            username=username.lower(),
            email=user_data["email"],
            display_name=user_data["display_name"],
            groups=user_data["groups"],
        )

    async def get_user_info(self, username: str) -> Optional[LDAPUser]:
        """Get user info from mock database."""
        user_data = self.MOCK_USERS.get(username.lower())
        if user_data is None:
            return None

        return LDAPUser(
            username=username.lower(),
            email=user_data["email"],
            display_name=user_data["display_name"],
            groups=user_data["groups"],
        )


# =============================================================================
# Real LDAP Provider
# =============================================================================


class RealLDAPProvider(LDAPProvider):
    """
    Real LDAP provider using python-ldap.

    Supports LDAPS and StartTLS with CA certificate validation.
    """

    def __init__(self):
        """Initialize LDAP connection settings."""
        self.ldap_url = settings.ldap_url
        self.base_dn = settings.ldap_base_dn
        self.bind_dn = settings.ldap_bind_dn
        self.bind_password = settings.ldap_bind_password
        self.user_dn_template = settings.ldap_user_dn_template
        self.search_filter = settings.ldap_search_filter
        self.use_starttls = settings.ldap_starttls
        self.ca_cert_path = settings.ldap_ca_cert_path

    def _get_connection(self):
        """Create and configure LDAP connection."""
        try:
            import ldap

            # Initialize connection
            conn = ldap.initialize(self.ldap_url)

            # Set options
            conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
            conn.set_option(ldap.OPT_REFERRALS, 0)

            # TLS configuration
            if self.ca_cert_path:
                conn.set_option(ldap.OPT_X_TLS_CACERTFILE, self.ca_cert_path)
                conn.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)

            # StartTLS if configured
            if self.use_starttls:
                conn.start_tls_s()

            return conn

        except ImportError:
            logger.error("python-ldap not installed")
            raise RuntimeError("LDAP support requires python-ldap package")
        except Exception as e:
            logger.error("Failed to create LDAP connection", error=str(e))
            raise

    async def authenticate(self, username: str, password: str) -> Optional[LDAPUser]:
        """
        Authenticate user using LDAP bind.

        Uses simple bind with the user's DN constructed from the template.
        """
        try:
            import ldap

            conn = self._get_connection()

            # Construct user DN
            user_dn = self.user_dn_template.format(username=username)

            # Attempt bind with user credentials
            try:
                conn.simple_bind_s(user_dn, password)
                logger.info("LDAP authentication successful", username=username)
            except ldap.INVALID_CREDENTIALS:
                logger.debug("LDAP: invalid credentials", username=username)
                return None
            except ldap.NO_SUCH_OBJECT:
                logger.debug("LDAP: user not found", username=username)
                return None

            # Search for user attributes
            search_filter = self.search_filter.format(username=username)
            result = conn.search_s(
                self.base_dn,
                ldap.SCOPE_SUBTREE,
                search_filter,
                ["mail", "displayName", "cn", "memberOf"],
            )

            if not result:
                return LDAPUser(username=username)

            dn, attrs = result[0]

            # Extract user info
            email = None
            if "mail" in attrs:
                email = attrs["mail"][0].decode("utf-8")

            display_name = None
            if "displayName" in attrs:
                display_name = attrs["displayName"][0].decode("utf-8")
            elif "cn" in attrs:
                display_name = attrs["cn"][0].decode("utf-8")

            groups = []
            if "memberOf" in attrs:
                for group_dn in attrs["memberOf"]:
                    # Extract CN from group DN
                    group_cn = group_dn.decode("utf-8").split(",")[0]
                    if group_cn.startswith("CN=") or group_cn.startswith("cn="):
                        groups.append(group_cn[3:])

            conn.unbind_s()

            return LDAPUser(
                username=username,
                email=email,
                display_name=display_name,
                groups=groups,
            )

        except Exception as e:
            logger.error("LDAP authentication error", username=username, error=str(e))
            return None

    async def get_user_info(self, username: str) -> Optional[LDAPUser]:
        """
        Get user information using service account.

        Uses bind DN and password to search for user.
        """
        try:
            import ldap

            conn = self._get_connection()

            # Bind with service account if configured
            if self.bind_dn and self.bind_password:
                conn.simple_bind_s(self.bind_dn, self.bind_password)

            # Search for user
            search_filter = self.search_filter.format(username=username)
            result = conn.search_s(
                self.base_dn,
                ldap.SCOPE_SUBTREE,
                search_filter,
                ["mail", "displayName", "cn", "memberOf"],
            )

            if not result:
                return None

            dn, attrs = result[0]

            email = attrs.get("mail", [b""])[0].decode("utf-8") or None
            display_name = (
                attrs.get("displayName", attrs.get("cn", [b""]))[0].decode("utf-8") or None
            )

            groups = []
            for group_dn in attrs.get("memberOf", []):
                group_cn = group_dn.decode("utf-8").split(",")[0]
                if group_cn.startswith("CN=") or group_cn.startswith("cn="):
                    groups.append(group_cn[3:])

            conn.unbind_s()

            return LDAPUser(
                username=username,
                email=email,
                display_name=display_name,
                groups=groups,
            )

        except Exception as e:
            logger.error("LDAP user info lookup error", username=username, error=str(e))
            return None


# =============================================================================
# Provider Factory
# =============================================================================


def get_ldap_provider() -> LDAPProvider:
    """
    Get the configured LDAP provider.

    Returns:
        MockLDAPProvider if LDAP_MOCK is true, RealLDAPProvider otherwise
    """
    if settings.ldap_mock:
        logger.info("Using mock LDAP provider")
        return MockLDAPProvider()
    else:
        logger.info("Using real LDAP provider", ldap_url=settings.ldap_url)
        return RealLDAPProvider()


# Singleton instance
_ldap_provider: Optional[LDAPProvider] = None


def get_ldap_service() -> LDAPProvider:
    """Get or create the LDAP provider singleton."""
    global _ldap_provider
    if _ldap_provider is None:
        _ldap_provider = get_ldap_provider()
    return _ldap_provider
