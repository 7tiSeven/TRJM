"""
TRJM Gateway - File Parser Base
================================
Base class and utilities for file parsing
"""

import hashlib
import io
import mimetypes
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...core.config import settings
from ...core.logging import logger


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Paragraph:
    """Represents a paragraph or text segment."""

    text: str
    index: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Result of parsing a document."""

    content: str
    paragraphs: List[Paragraph]
    metadata: Dict[str, Any]
    format_hints: Dict[str, Any]
    file_type: str
    file_name: str
    file_size: int


@dataclass
class TranslatedDocument:
    """Result of translating a document."""

    original: ParsedDocument
    translated_paragraphs: List[Paragraph]
    output_content: bytes
    output_format: str
    output_filename: str


# =============================================================================
# File Validation
# =============================================================================

# Allowed file extensions and their MIME types
ALLOWED_FILES = {
    ".txt": ["text/plain"],
    ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    ".pdf": ["application/pdf"],
    ".msg": ["application/vnd.ms-outlook", "application/octet-stream"],
}

# Magic bytes for file type verification
MAGIC_BYTES = {
    ".docx": [b"PK\x03\x04"],  # ZIP archive (Office Open XML)
    ".pdf": [b"%PDF"],
    ".msg": [b"\xd0\xcf\x11\xe0"],  # OLE compound document
}


def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase."""
    return Path(filename).suffix.lower()


def validate_file_extension(filename: str) -> Tuple[bool, str]:
    """
    Validate file extension.

    Returns:
        Tuple of (is_valid, extension)
    """
    ext = get_file_extension(filename)
    if ext not in ALLOWED_FILES:
        return False, ext
    return True, ext


def validate_mime_type(filename: str, content_type: Optional[str]) -> bool:
    """Validate MIME type matches expected for extension."""
    if not content_type:
        return True  # Skip if not provided

    ext = get_file_extension(filename)
    allowed_mimes = ALLOWED_FILES.get(ext, [])
    return content_type in allowed_mimes


def validate_magic_bytes(filename: str, content: bytes) -> bool:
    """Validate file content matches expected magic bytes."""
    ext = get_file_extension(filename)
    expected_magic = MAGIC_BYTES.get(ext)

    if not expected_magic:
        return True  # No magic bytes check for this type

    for magic in expected_magic:
        if content.startswith(magic):
            return True

    return False


def validate_file_size(content: bytes) -> bool:
    """Validate file is within size limits."""
    return len(content) <= settings.max_upload_size_bytes


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


# =============================================================================
# Parser Base Class
# =============================================================================


class FileParser(ABC):
    """Abstract base class for file parsers."""

    @property
    @abstractmethod
    def supported_extension(self) -> str:
        """Get the file extension this parser handles."""
        pass

    @abstractmethod
    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        """
        Parse file content into structured document.

        Args:
            content: Raw file bytes
            filename: Original filename

        Returns:
            ParsedDocument with extracted text and metadata
        """
        pass

    @abstractmethod
    async def generate(
        self,
        original: ParsedDocument,
        translated_paragraphs: List[Paragraph],
    ) -> bytes:
        """
        Generate translated file from paragraphs.

        Args:
            original: Original parsed document
            translated_paragraphs: Translated paragraphs

        Returns:
            Generated file as bytes
        """
        pass

    def get_output_filename(self, original_filename: str, target_lang: str) -> str:
        """Generate output filename with language suffix."""
        path = Path(original_filename)
        return f"{path.stem}_{target_lang}{path.suffix}"


# =============================================================================
# Parser Registry
# =============================================================================


class ParserRegistry:
    """Registry for file parsers."""

    _parsers: Dict[str, FileParser] = {}

    @classmethod
    def register(cls, parser: FileParser) -> None:
        """Register a parser."""
        cls._parsers[parser.supported_extension] = parser
        logger.debug(f"Registered parser for {parser.supported_extension}")

    @classmethod
    def get_parser(cls, filename: str) -> Optional[FileParser]:
        """Get parser for a file."""
        ext = get_file_extension(filename)
        return cls._parsers.get(ext)

    @classmethod
    def supported_extensions(cls) -> List[str]:
        """Get list of supported extensions."""
        return list(cls._parsers.keys())
