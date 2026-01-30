"""
TRJM Gateway - Database Models
===============================
SQLAlchemy models for all database tables
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# =============================================================================
# Base Model
# =============================================================================


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


# =============================================================================
# Enums
# =============================================================================


class Feature(str, Enum):
    """Feature flags for role-based access control."""

    TRANSLATE_TEXT = "TRANSLATE_TEXT"
    UPLOAD_FILES = "UPLOAD_FILES"
    TRANSLATE_DOCX = "TRANSLATE_DOCX"
    TRANSLATE_PDF = "TRANSLATE_PDF"
    TRANSLATE_MSG = "TRANSLATE_MSG"
    USE_GLOSSARY = "USE_GLOSSARY"
    MANAGE_GLOSSARY = "MANAGE_GLOSSARY"
    VIEW_HISTORY = "VIEW_HISTORY"
    EXPORT_RESULTS = "EXPORT_RESULTS"
    ADMIN_PANEL = "ADMIN_PANEL"


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class JobType(str, Enum):
    """Job type."""

    TEXT = "text"
    FILE = "file"


class AuditAction(str, Enum):
    """Audit log action types."""

    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    TRANSLATION_STARTED = "translation_started"
    TRANSLATION_COMPLETED = "translation_completed"
    FILE_UPLOADED = "file_uploaded"
    FILE_DOWNLOADED = "file_downloaded"
    GLOSSARY_CREATED = "glossary_created"
    GLOSSARY_UPDATED = "glossary_updated"
    GLOSSARY_DELETED = "glossary_deleted"
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"
    USER_ROLE_CHANGED = "user_role_changed"


# =============================================================================
# Role Models
# =============================================================================


class Role(Base):
    """Role model for RBAC."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    features: Mapped[List["RoleFeature"]] = relationship(
        "RoleFeature",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    users: Mapped[List["User"]] = relationship("User", back_populates="role")

    def get_enabled_features(self) -> List[str]:
        """Get list of enabled feature names."""
        return [f.feature_name for f in self.features if f.enabled]


class RoleFeature(Base):
    """Feature flags for roles."""

    __tablename__ = "role_features"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    role_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_name: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="features")

    __table_args__ = (
        UniqueConstraint("role_id", "feature_name", name="uq_role_feature"),
        Index("idx_role_features_role_id", "role_id"),
    )


# =============================================================================
# User Model
# =============================================================================


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("roles.id"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="users")
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="user")
    glossaries: Mapped[List["Glossary"]] = relationship("Glossary", back_populates="user")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_role_id", "role_id"),
    )

    def has_feature(self, feature: Feature) -> bool:
        """Check if user has a specific feature enabled."""
        return feature.value in self.role.get_enabled_features()


# =============================================================================
# Job Model
# =============================================================================


class Job(Base):
    """Translation job model."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JobStatus.PENDING.value)
    source_language: Mapped[str] = mapped_column(String(10), nullable=False)
    target_language: Mapped[str] = mapped_column(String(10), nullable=False)
    style_preset: Mapped[Optional[str]] = mapped_column(String(50))
    input_text: Mapped[Optional[str]] = mapped_column(Text)
    output_text: Mapped[Optional[str]] = mapped_column(Text)
    file_name: Mapped[Optional[str]] = mapped_column(String(255))
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    output_file_path: Mapped[Optional[str]] = mapped_column(String(500))
    glossary_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    qa_report: Mapped[Optional[dict]] = mapped_column(JSON)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="jobs")

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('text', 'file')",
            name="ck_job_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'expired')",
            name="ck_job_status",
        ),
        Index("idx_jobs_user_id", "user_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_expires_at", "expires_at"),
    )


# =============================================================================
# Glossary Models
# =============================================================================


class Glossary(Base):
    """Glossary model for terminology management."""

    __tablename__ = "glossaries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    target_language: Mapped[str] = mapped_column(String(10), nullable=False, default="ar")
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="glossaries")
    entries: Mapped[List["GlossaryEntry"]] = relationship(
        "GlossaryEntry",
        back_populates="glossary",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("idx_glossaries_user_id", "user_id"),)


class GlossaryEntry(Base):
    """Glossary entry model."""

    __tablename__ = "glossary_entries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    glossary_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("glossaries.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_term: Mapped[str] = mapped_column(String(500), nullable=False)
    target_term: Mapped[str] = mapped_column(String(500), nullable=False)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    context: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    glossary: Mapped["Glossary"] = relationship("Glossary", back_populates="entries")

    __table_args__ = (
        Index("idx_glossary_entries_glossary_id", "glossary_id"),
        Index("idx_glossary_entries_source_term", "source_term"),
    )


# =============================================================================
# Audit Log Model
# =============================================================================


class AuditLog(Base):
    """Audit log for tracking user actions."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(String(255))
    resource_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    correlation_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_correlation_id", "correlation_id"),
    )
