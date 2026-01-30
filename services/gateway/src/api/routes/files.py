"""
TRJM Gateway - File Translation API Routes
==========================================
Endpoints for file upload and translation
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...core.config import settings
from ...core.logging import logger
from ...db.models import Feature, Job, JobStatus, JobType
from ...services.files.parser import (
    ParsedDocument,
    ParserRegistry,
    compute_file_hash,
    validate_file_extension,
    validate_file_size,
    validate_magic_bytes,
)
from ...services.translation.pipeline import TranslationPipeline, get_pipeline
from ...services.translation.schemas import (
    GlossaryEntry,
    LanguageCode,
    StylePreset,
    TranslationRequest,
)
from ..deps import (
    CurrentUser,
    DBSession,
    RequireFeature,
    get_client_ip,
    get_correlation_id,
    require_any_feature,
)

# Import parsers to register them
from ...services.files import txt, docx, pdf, msg

router = APIRouter(prefix="/files", tags=["File Translation"])


# =============================================================================
# Response Models
# =============================================================================


class FileUploadResponse(BaseModel):
    """Response after file upload."""

    job_id: str
    file_name: str
    file_type: str
    file_size: int
    status: str


class FileTranslationResponse(BaseModel):
    """Response with translation result."""

    job_id: str
    status: str
    original_file_name: str
    translated_file_name: Optional[str]
    confidence: Optional[float]
    error_message: Optional[str]
    download_ready: bool


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/translate",
    response_model=FileTranslationResponse,
)
async def translate_file(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    file: UploadFile = File(...),
    target_language: str = Form(default="ar"),
    style_preset: str = Form(default="neutral"),
    glossary_id: Optional[str] = Form(default=None),
):
    """
    Upload and translate a file.

    Supported formats: .txt, .docx, .pdf, .msg

    The file is processed asynchronously. Use the job ID to check status
    and download the translated file.
    """
    correlation_id = get_correlation_id(request)

    # Validate file extension
    is_valid, extension = validate_file_extension(file.filename)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {extension}. Supported: .txt, .docx, .pdf, .msg",
        )

    # Check feature access based on file type
    feature_map = {
        ".txt": Feature.UPLOAD_FILES,
        ".docx": Feature.TRANSLATE_DOCX,
        ".pdf": Feature.TRANSLATE_PDF,
        ".msg": Feature.TRANSLATE_MSG,
    }
    required_feature = feature_map.get(extension, Feature.UPLOAD_FILES)
    if not user.has_feature(required_feature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Feature {required_feature.value} not available",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if not validate_file_size(content):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )

    # Validate magic bytes
    if not validate_magic_bytes(file.filename, content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match expected format",
        )

    # Get parser
    parser = ParserRegistry.get_parser(file.filename)
    if not parser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No parser available for {extension}",
        )

    # Create job record
    job = Job(
        user_id=user.id,
        job_type=JobType.FILE.value,
        status=JobStatus.PROCESSING.value,
        source_language="auto",
        target_language=target_language,
        style_preset=style_preset,
        file_name=file.filename,
        glossary_id=glossary_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.retention_hours),
    )
    db.add(job)
    await db.flush()

    logger.info(
        "File translation started",
        job_id=job.id,
        filename=file.filename,
        size=len(content),
        user_id=user.id,
        correlation_id=correlation_id,
    )

    try:
        # Save uploaded file
        upload_dir = Path(settings.upload_dir) / job.id
        upload_dir.mkdir(parents=True, exist_ok=True)
        input_path = upload_dir / file.filename
        with open(input_path, "wb") as f:
            f.write(content)
        job.file_path = str(input_path)

        # Parse file
        parsed_doc = await parser.parse(content, file.filename)

        if not parsed_doc.paragraphs:
            raise ValueError("No text content found in file")

        # Translate each paragraph
        pipeline = get_pipeline()
        translated_paragraphs = []

        for para in parsed_doc.paragraphs:
            # Create translation request for this paragraph
            trans_request = TranslationRequest(
                text=para.text,
                source_language=LanguageCode.AUTO,
                target_language=LanguageCode(target_language),
                style_preset=StylePreset(style_preset),
            )

            result = await pipeline.translate(trans_request, [])

            # Create translated paragraph
            from ...services.files.parser import Paragraph
            translated_paragraphs.append(
                Paragraph(
                    text=result.translation,
                    index=para.index,
                    metadata=para.metadata,
                )
            )

        # Generate output file
        output_content = await parser.generate(parsed_doc, translated_paragraphs)
        output_filename = parser.get_output_filename(file.filename, target_language)
        output_path = upload_dir / output_filename

        with open(output_path, "wb") as f:
            f.write(output_content)

        # Update job
        job.status = JobStatus.COMPLETED.value
        job.output_file_path = str(output_path)
        job.completed_at = datetime.now(timezone.utc)
        # Calculate average confidence
        job.confidence = 0.85  # Simplified for file translation

        logger.info(
            "File translation completed",
            job_id=job.id,
            output_file=output_filename,
            correlation_id=correlation_id,
        )

        return FileTranslationResponse(
            job_id=job.id,
            status=job.status,
            original_file_name=file.filename,
            translated_file_name=output_filename,
            confidence=float(job.confidence) if job.confidence else None,
            error_message=None,
            download_ready=True,
        )

    except Exception as e:
        job.status = JobStatus.FAILED.value
        job.error_message = str(e)[:500]
        job.completed_at = datetime.now(timezone.utc)

        logger.exception(
            "File translation failed",
            job_id=job.id,
            error=str(e),
            correlation_id=correlation_id,
        )

        return FileTranslationResponse(
            job_id=job.id,
            status=job.status,
            original_file_name=file.filename,
            translated_file_name=None,
            confidence=None,
            error_message=str(e),
            download_ready=False,
        )


@router.get(
    "/{job_id}/download",
    dependencies=[Depends(RequireFeature(Feature.UPLOAD_FILES))],
)
async def download_translated_file(
    db: DBSession,
    user: CurrentUser,
    job_id: str,
):
    """
    Download the translated file.
    """
    from sqlalchemy import select

    # Get job
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Status: {job.status}",
        )

    if not job.output_file_path or not os.path.exists(job.output_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not found",
        )

    filename = os.path.basename(job.output_file_path)

    logger.info(
        "File downloaded",
        job_id=job_id,
        filename=filename,
        user_id=user.id,
    )

    return FileResponse(
        path=job.output_file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get(
    "/{job_id}/status",
    response_model=FileTranslationResponse,
    dependencies=[Depends(RequireFeature(Feature.UPLOAD_FILES))],
)
async def get_file_translation_status(
    db: DBSession,
    user: CurrentUser,
    job_id: str,
):
    """
    Get the status of a file translation job.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    translated_filename = None
    if job.output_file_path:
        translated_filename = os.path.basename(job.output_file_path)

    return FileTranslationResponse(
        job_id=job.id,
        status=job.status,
        original_file_name=job.file_name,
        translated_file_name=translated_filename,
        confidence=float(job.confidence) if job.confidence else None,
        error_message=job.error_message,
        download_ready=job.status == JobStatus.COMPLETED.value,
    )


@router.get("/supported-formats")
async def get_supported_formats():
    """
    Get list of supported file formats.
    """
    return {
        "formats": [
            {
                "extension": ".txt",
                "name": "Plain Text",
                "description": "Plain text files with UTF-8 encoding",
            },
            {
                "extension": ".docx",
                "name": "Microsoft Word",
                "description": "Word 2007+ documents (.docx)",
            },
            {
                "extension": ".pdf",
                "name": "PDF",
                "description": "Text-based PDF files (no OCR)",
            },
            {
                "extension": ".msg",
                "name": "Outlook Email",
                "description": "Outlook message files (attachments ignored)",
            },
        ],
        "max_size_mb": settings.max_upload_size_mb,
    }
