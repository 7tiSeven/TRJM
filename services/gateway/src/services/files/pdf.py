"""
TRJM Gateway - PDF File Parser
===============================
Parser for PDF documents (text-based only)
"""

import io
from typing import List

from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph as RLParagraph, SimpleDocTemplate, Spacer

from ...core.config import settings
from ...core.logging import logger
from .parser import FileParser, Paragraph, ParsedDocument, ParserRegistry


class PdfParser(FileParser):
    """
    Parser for .pdf files.

    Note: This parser extracts text from PDFs. It does not preserve
    the exact layout. For layout-perfect translation, OCR would be needed.
    """

    @property
    def supported_extension(self) -> str:
        return ".pdf"

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        """
        Parse PDF file.

        Extracts text from each page.
        """
        reader = PdfReader(io.BytesIO(content))

        paragraphs = []
        full_text_parts = []
        para_index = 0

        for page_num, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num}: {e}")
                text = ""

            if text:
                # Split page into paragraphs
                page_paras = text.split("\n\n")
                for para_text in page_paras:
                    stripped = para_text.strip()
                    if stripped:
                        paragraphs.append(
                            Paragraph(
                                text=stripped,
                                index=para_index,
                                metadata={
                                    "page": page_num + 1,
                                },
                            )
                        )
                        full_text_parts.append(stripped)
                        para_index += 1

        # Check if we got any text
        if not paragraphs:
            logger.warning(
                "No text extracted from PDF",
                filename=filename,
                pages=len(reader.pages),
            )
            # Check if OCR might help
            if settings.ocr_enabled:
                # OCR stub - not implemented
                logger.info("OCR is enabled but not implemented")

        metadata = {
            "page_count": len(reader.pages),
            "has_text": len(paragraphs) > 0,
            "encrypted": reader.is_encrypted,
        }

        # Extract PDF metadata if available
        if reader.metadata:
            metadata.update(
                {
                    "title": reader.metadata.get("/Title"),
                    "author": reader.metadata.get("/Author"),
                    "creator": reader.metadata.get("/Creator"),
                }
            )

        logger.debug(
            "PDF parsed",
            filename=filename,
            pages=len(reader.pages),
            paragraphs=len(paragraphs),
        )

        return ParsedDocument(
            content="\n\n".join(full_text_parts),
            paragraphs=paragraphs,
            metadata=metadata,
            format_hints={
                "is_text_based": len(paragraphs) > 0,
                "may_need_ocr": len(paragraphs) == 0 and len(reader.pages) > 0,
            },
            file_type="pdf",
            file_name=filename,
            file_size=len(content),
        )

    async def generate(
        self,
        original: ParsedDocument,
        translated_paragraphs: List[Paragraph],
    ) -> bytes:
        """
        Generate translated PDF file.

        Creates a simple PDF with the translated text.
        Note: This does not preserve the original layout.
        """
        output = io.BytesIO()

        # Create document
        doc = SimpleDocTemplate(
            output,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        # Set up styles
        styles = getSampleStyleSheet()

        # Create RTL-friendly style for Arabic
        rtl_style = ParagraphStyle(
            "RTL",
            parent=styles["Normal"],
            fontSize=12,
            leading=18,
            alignment=2,  # Right align for RTL
            wordWrap="RTL",
        )

        # Build content
        story = []

        # Add title
        title = original.metadata.get("title") or original.file_name
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=20,
        )
        story.append(RLParagraph(f"Translation: {title}", title_style))
        story.append(Spacer(1, 20))

        # Add translated paragraphs
        for para in translated_paragraphs:
            # Use RTL style for Arabic content
            text = para.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(RLParagraph(text, rtl_style))
            story.append(Spacer(1, 12))

        # Add footer
        story.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Italic"],
            fontSize=9,
            textColor="gray",
        )
        story.append(
            RLParagraph(
                "Translated by TRJM Agentic AI Translator",
                footer_style,
            )
        )

        # Build PDF
        doc.build(story)

        output.seek(0)
        return output.read()


# Register parser
ParserRegistry.register(PdfParser())
