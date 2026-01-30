"""
TRJM Gateway - Translation API Routes
======================================
Endpoints for text translation
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.logging import logger
from ...db.models import Feature, Glossary, GlossaryEntry as GlossaryEntryModel, Job, JobStatus, JobType
from ...services.translation.pipeline import TranslationPipeline
from ...services.translation.schemas import (
    GlossaryEntry,
    LanguageCode,
    QAReport,
    StylePreset,
    TranslationRequest,
    TranslationResponse,
)
from ..deps import (
    CurrentUser,
    DBSession,
    RequireFeature,
    get_client_ip,
    get_correlation_id,
)

router = APIRouter(prefix="/translation", tags=["Translation"])


# =============================================================================
# Request/Response Models
# =============================================================================


class TranslateTextRequest(BaseModel):
    """Request to translate text."""

    text: str = Field(..., min_length=1, max_length=100000)
    source_language: LanguageCode = LanguageCode.AUTO
    target_language: LanguageCode = LanguageCode.ARABIC
    style_preset: StylePreset = StylePreset.NEUTRAL
    glossary_id: Optional[str] = None
    protected_patterns: List[str] = Field(default_factory=list)


class TranslateTextResponse(BaseModel):
    """Response from text translation."""

    job_id: str
    translation: str
    source_language: LanguageCode
    target_language: LanguageCode
    confidence: float
    qa_report: QAReport
    processing_time_ms: int
    retries: int
    dev_mode: bool = False


# =============================================================================
# Pipeline Instance (singleton for efficiency)
# =============================================================================

_pipeline: Optional[TranslationPipeline] = None


def get_pipeline() -> TranslationPipeline:
    """Get or create the translation pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = TranslationPipeline()
    return _pipeline


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/translate",
    response_model=TranslateTextResponse,
    dependencies=[Depends(RequireFeature(Feature.TRANSLATE_TEXT))],
)
async def translate_text(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    data: TranslateTextRequest,
):
    """
    Translate text using the agentic pipeline.

    The pipeline:
    1. Analyzes the text (language detection, content type)
    2. Generates translation with glossary/token protection
    3. Reviews for quality and provides confidence score
    4. Retries if confidence is below threshold
    5. Applies post-processing (RTL fixes, typography)

    Returns the translation with a detailed QA report.
    """
    correlation_id = get_correlation_id(request)
    client_ip = get_client_ip(request)

    logger.info(
        "Translation request received",
        user_id=user.id,
        text_length=len(data.text),
        target_language=data.target_language.value,
        correlation_id=correlation_id,
    )

    # Check concurrent job limit
    active_jobs = await db.scalar(
        select(func.count(Job.id)).where(
            Job.user_id == user.id,
            Job.status == JobStatus.PROCESSING.value,
        )
    )

    if active_jobs and active_jobs >= settings.max_concurrent_jobs_per_user:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum concurrent jobs ({settings.max_concurrent_jobs_per_user}) reached",
        )

    # Load glossary if specified
    glossary_entries: List[GlossaryEntry] = []
    if data.glossary_id:
        # Check if user has glossary feature
        if not user.has_feature(Feature.USE_GLOSSARY):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Glossary feature not available",
            )

        # Load glossary entries
        result = await db.execute(
            select(GlossaryEntryModel)
            .join(Glossary)
            .where(
                Glossary.id == data.glossary_id,
                (Glossary.user_id == user.id) | (Glossary.is_global == True),
            )
        )
        entries = result.scalars().all()
        glossary_entries = [
            GlossaryEntry(
                source=entry.source_term,
                target=entry.target_term,
                case_sensitive=entry.case_sensitive,
                context=entry.context,
            )
            for entry in entries
        ]

    # Create job record
    job = Job(
        user_id=user.id,
        job_type=JobType.TEXT.value,
        status=JobStatus.PROCESSING.value,
        source_language=data.source_language.value,
        target_language=data.target_language.value,
        style_preset=data.style_preset.value,
        input_text=data.text[:10000] if settings.enable_pii_redaction else data.text,
        glossary_id=data.glossary_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.retention_hours),
    )
    db.add(job)
    await db.flush()

    try:
        # Execute translation pipeline
        pipeline = get_pipeline()
        translation_request = TranslationRequest(
            text=data.text,
            source_language=data.source_language,
            target_language=data.target_language,
            style_preset=data.style_preset,
            glossary_id=data.glossary_id,
            protected_patterns=data.protected_patterns,
        )

        result = await pipeline.translate(translation_request, glossary_entries)

        # Update job with results
        job.status = JobStatus.COMPLETED.value
        job.output_text = result.translation[:10000] if settings.enable_pii_redaction else result.translation
        job.confidence = result.confidence
        job.qa_report = result.qa_report.model_dump()
        job.retries = result.retries
        job.processing_time_ms = result.metadata.processing_time_ms
        job.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Translation completed",
            job_id=job.id,
            confidence=result.confidence,
            processing_time_ms=result.metadata.processing_time_ms,
            correlation_id=correlation_id,
        )

        return TranslateTextResponse(
            job_id=job.id,
            translation=result.translation,
            source_language=result.source_language,
            target_language=result.target_language,
            confidence=result.confidence,
            qa_report=result.qa_report,
            processing_time_ms=result.metadata.processing_time_ms,
            retries=result.retries,
            dev_mode=settings.dev_mode,
        )

    except Exception as e:
        # Update job with error
        job.status = JobStatus.FAILED.value
        job.error_message = str(e)[:500]
        job.completed_at = datetime.now(timezone.utc)

        logger.exception(
            "Translation failed",
            job_id=job.id,
            error=str(e),
            correlation_id=correlation_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}",
        )


@router.get("/languages")
async def get_supported_languages():
    """
    Get list of supported languages.
    """
    return {
        "source_languages": [
            {"code": "auto", "name": "Auto-detect"},
            {"code": "en", "name": "English"},
            {"code": "ar", "name": "Arabic"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "es", "name": "Spanish"},
        ],
        "target_languages": [
            {"code": "ar", "name": "Arabic (MSA)", "rtl": True, "default": True},
            {"code": "en", "name": "English", "rtl": False},
            {"code": "fr", "name": "French", "rtl": False},
            {"code": "de", "name": "German", "rtl": False},
            {"code": "es", "name": "Spanish", "rtl": False},
        ],
    }


@router.get("/styles")
async def get_style_presets():
    """
    Get available style presets.
    """
    return {
        "presets": [
            {
                "id": "formal_msa",
                "name": "Formal MSA",
                "description": "Formal Modern Standard Arabic for official documents",
            },
            {
                "id": "neutral",
                "name": "Neutral",
                "description": "Balanced, professional tone",
            },
            {
                "id": "marketing",
                "name": "Marketing",
                "description": "Engaging, persuasive style for marketing content",
            },
            {
                "id": "government_memo",
                "name": "Government Memo",
                "description": "Formal bureaucratic style for government documents",
            },
        ],
        "default": "neutral",
    }


# Import for job count query
from sqlalchemy import func
