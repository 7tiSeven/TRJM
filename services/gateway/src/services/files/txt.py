"""
TRJM Gateway - TXT File Parser
===============================
Parser for plain text files
"""

import chardet

from ...core.logging import logger
from .parser import FileParser, Paragraph, ParsedDocument, ParserRegistry


class TxtParser(FileParser):
    """Parser for .txt files."""

    @property
    def supported_extension(self) -> str:
        return ".txt"

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        """
        Parse TXT file.

        Handles encoding detection and paragraph splitting.
        """
        # Detect encoding
        detection = chardet.detect(content)
        encoding = detection.get("encoding", "utf-8") or "utf-8"
        confidence = detection.get("confidence", 0)

        logger.debug(
            "TXT encoding detected",
            filename=filename,
            encoding=encoding,
            confidence=confidence,
        )

        # Decode content
        try:
            text = content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            # Fallback to utf-8 with error handling
            text = content.decode("utf-8", errors="replace")
            encoding = "utf-8"

        # Split into paragraphs (double newline or single newline)
        raw_paragraphs = text.split("\n\n")
        if len(raw_paragraphs) == 1:
            # Try single newline if no double newlines
            raw_paragraphs = text.split("\n")

        paragraphs = []
        for i, para_text in enumerate(raw_paragraphs):
            stripped = para_text.strip()
            if stripped:
                paragraphs.append(
                    Paragraph(
                        text=stripped,
                        index=i,
                        metadata={"original_text": para_text},
                    )
                )

        return ParsedDocument(
            content=text,
            paragraphs=paragraphs,
            metadata={
                "encoding": encoding,
                "encoding_confidence": confidence,
                "line_count": text.count("\n") + 1,
            },
            format_hints={
                "paragraph_separator": "\n\n",
            },
            file_type="txt",
            file_name=filename,
            file_size=len(content),
        )

    async def generate(
        self,
        original: ParsedDocument,
        translated_paragraphs: list[Paragraph],
    ) -> bytes:
        """
        Generate translated TXT file.

        Preserves paragraph structure.
        """
        separator = original.format_hints.get("paragraph_separator", "\n\n")
        text = separator.join(p.text for p in translated_paragraphs)

        # Use original encoding if detected, otherwise UTF-8
        encoding = original.metadata.get("encoding", "utf-8")
        try:
            return text.encode(encoding)
        except (UnicodeEncodeError, LookupError):
            return text.encode("utf-8")


# Register parser
ParserRegistry.register(TxtParser())
