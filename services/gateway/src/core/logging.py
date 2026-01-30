"""
TRJM Gateway - Logging Configuration
=====================================
Structured logging with optional PII redaction
"""

import logging
import re
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.types import Processor

from .config import settings


# =============================================================================
# PII Redaction Patterns
# =============================================================================

PII_PATTERNS = [
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    # Phone numbers (various formats)
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE]"),
    # SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Credit card numbers
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CARD]"),
    # IP addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP]"),
]


def redact_pii(value: Any) -> Any:
    """
    Redact PII from a value.

    Args:
        value: The value to redact

    Returns:
        Redacted value
    """
    if not settings.enable_pii_redaction:
        return value

    if isinstance(value, str):
        result = value
        for pattern, replacement in PII_PATTERNS:
            result = pattern.sub(replacement, result)
        return result
    elif isinstance(value, dict):
        return {k: redact_pii(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [redact_pii(item) for item in value]
    return value


# =============================================================================
# Custom Processors
# =============================================================================


def pii_redactor(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Structlog processor to redact PII."""
    if settings.enable_pii_redaction:
        return {k: redact_pii(v) for k, v in event_dict.items()}
    return event_dict


def add_app_context(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add application context to log events."""
    event_dict["app"] = settings.app_name
    event_dict["version"] = settings.app_version
    event_dict["environment"] = "development" if settings.dev_mode else "production"
    return event_dict


# =============================================================================
# Logger Configuration
# =============================================================================


def configure_logging() -> None:
    """Configure structlog and standard logging."""
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_app_context,
        pii_redactor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Use JSON in production, console in development
    if settings.dev_mode:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Optional logger name

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Initialize logging on module load
configure_logging()

# Default logger instance
logger = get_logger("trjm")
