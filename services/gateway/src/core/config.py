"""
TRJM Gateway - Configuration Module
====================================
Centralized configuration using Pydantic Settings
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Application Settings
    # =========================================================================
    app_name: str = "TRJM Gateway"
    app_version: str = "1.0.0"
    debug: bool = False
    dev_mode: bool = Field(default=True, description="Show dev mode warning banner")
    log_level: str = "INFO"
    enable_pii_redaction: bool = False

    # =========================================================================
    # Database Configuration
    # =========================================================================
    database_url: str = Field(
        default="postgresql+asyncpg://trjm:trjm@localhost:5432/trjm",
        description="PostgreSQL connection URL",
    )

    # =========================================================================
    # LDAP Configuration
    # =========================================================================
    ldap_mock: bool = Field(default=True, description="Use mock LDAP for development")
    ldap_url: Optional[str] = Field(default=None, description="LDAP server URL")
    ldap_base_dn: Optional[str] = Field(default=None, description="LDAP base DN")
    ldap_bind_dn: Optional[str] = Field(default=None, description="Service account DN")
    ldap_bind_password: Optional[str] = Field(default=None, description="Service account password")
    ldap_user_dn_template: Optional[str] = Field(
        default="uid={username},ou=users,dc=example,dc=com",
        description="Template for user DN",
    )
    ldap_search_filter: Optional[str] = Field(
        default="(uid={username})",
        description="LDAP search filter",
    )
    ldap_starttls: bool = Field(default=False, description="Use StartTLS")
    ldap_ca_cert_path: Optional[str] = Field(default=None, description="CA certificate path")

    # =========================================================================
    # LLM Provider Configuration
    # =========================================================================
    llm_provider: str = Field(default="openai", description="LLM provider (openai/vllm)")
    llm_base_url: str = Field(default="https://api.openai.com/v1", description="LLM API base URL")
    llm_api_key: str = Field(default="", description="LLM API key")
    llm_model: str = Field(default="gpt-4.1", description="LLM model name")
    llm_timeout: int = Field(default=120, description="LLM request timeout in seconds")
    llm_max_retries: int = Field(default=3, description="Max LLM request retries")

    # =========================================================================
    # Security Configuration
    # =========================================================================
    jwt_secret: str = Field(
        default="change-this-secret-in-production",
        description="JWT signing secret",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiry_hours: int = Field(default=24, description="JWT expiry in hours")
    csrf_secret: str = Field(
        default="change-this-csrf-secret",
        description="CSRF token secret",
    )
    cors_origins: str = Field(
        default="https://localhost:3000",
        description="Comma-separated CORS origins",
    )

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    rate_limit_per_minute: int = Field(default=60, description="Requests per minute per user")
    rate_limit_burst: int = Field(default=10, description="Burst allowance")
    max_concurrent_jobs_per_user: int = Field(default=3, description="Max concurrent jobs")

    # =========================================================================
    # Storage Configuration
    # =========================================================================
    upload_dir: str = Field(default="/data/uploads", description="Upload directory path")
    max_upload_size_mb: int = Field(default=10, description="Max upload size in MB")
    retention_hours: int = Field(default=24, description="Data retention in hours")

    # =========================================================================
    # TLS Configuration
    # =========================================================================
    tls_cert_path: Optional[str] = Field(default=None, description="TLS certificate path")
    tls_key_path: Optional[str] = Field(default=None, description="TLS key path")

    # =========================================================================
    # Feature Flags
    # =========================================================================
    ocr_enabled: bool = Field(default=False, description="Enable OCR for PDF")

    # =========================================================================
    # Validators
    # =========================================================================
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
