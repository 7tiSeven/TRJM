"""
TRJM Gateway - History API Routes
==================================
Endpoints for viewing translation history
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.logging import logger
from ...db.models import Feature, Job, JobStatus, JobType
from ..deps import CurrentUser, DBSession, RequireFeature

router = APIRouter(prefix="/history", tags=["History"])


# =============================================================================
# Response Models
# =============================================================================


class JobSummary(BaseModel):
    """Summary of a translation job."""

    id: str
    job_type: str
    status: str
    source_language: str
    target_language: str
    style_preset: Optional[str]
    input_preview: Optional[str] = Field(None, description="First 200 chars of input")
    output_preview: Optional[str] = Field(None, description="First 200 chars of output")
    file_name: Optional[str]
    confidence: Optional[float]
    processing_time_ms: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]


class JobDetail(JobSummary):
    """Detailed view of a translation job."""

    input_text: Optional[str]
    output_text: Optional[str]
    qa_report: Optional[dict]
    error_message: Optional[str]
    retries: int


class HistoryListResponse(BaseModel):
    """Paginated history response."""

    jobs: List[JobSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class HistoryStats(BaseModel):
    """User's translation statistics."""

    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_characters_translated: int
    average_confidence: Optional[float]
    average_processing_time_ms: Optional[float]


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=HistoryListResponse,
    dependencies=[Depends(RequireFeature(Feature.VIEW_HISTORY))],
)
async def list_history(
    db: DBSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    search: Optional[str] = Query(None, description="Search in input/output text"),
):
    """
    Get paginated list of user's translation jobs.
    """
    # Build query
    query = select(Job).where(Job.user_id == user.id)

    # Apply filters
    if status_filter:
        query = query.where(Job.status == status_filter)

    if job_type:
        query = query.where(Job.job_type == job_type)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Job.input_text.ilike(search_pattern))
            | (Job.output_text.ilike(search_pattern))
            | (Job.file_name.ilike(search_pattern))
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size

    # Get paginated results
    query = query.order_by(desc(Job.created_at)).offset(offset).limit(page_size)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return HistoryListResponse(
        jobs=[
            JobSummary(
                id=job.id,
                job_type=job.job_type,
                status=job.status,
                source_language=job.source_language,
                target_language=job.target_language,
                style_preset=job.style_preset,
                input_preview=job.input_text[:200] if job.input_text else None,
                output_preview=job.output_text[:200] if job.output_text else None,
                file_name=job.file_name,
                confidence=float(job.confidence) if job.confidence else None,
                processing_time_ms=job.processing_time_ms,
                created_at=job.created_at,
                completed_at=job.completed_at,
            )
            for job in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/stats",
    response_model=HistoryStats,
    dependencies=[Depends(RequireFeature(Feature.VIEW_HISTORY))],
)
async def get_history_stats(db: DBSession, user: CurrentUser):
    """
    Get user's translation statistics.
    """
    # Total jobs
    total_jobs = await db.scalar(
        select(func.count(Job.id)).where(Job.user_id == user.id)
    ) or 0

    # Completed jobs
    completed_jobs = await db.scalar(
        select(func.count(Job.id)).where(
            Job.user_id == user.id,
            Job.status == JobStatus.COMPLETED.value,
        )
    ) or 0

    # Failed jobs
    failed_jobs = await db.scalar(
        select(func.count(Job.id)).where(
            Job.user_id == user.id,
            Job.status == JobStatus.FAILED.value,
        )
    ) or 0

    # Total characters (from completed text jobs)
    total_chars = await db.scalar(
        select(func.sum(func.length(Job.input_text))).where(
            Job.user_id == user.id,
            Job.job_type == JobType.TEXT.value,
            Job.status == JobStatus.COMPLETED.value,
        )
    ) or 0

    # Average confidence
    avg_confidence = await db.scalar(
        select(func.avg(Job.confidence)).where(
            Job.user_id == user.id,
            Job.status == JobStatus.COMPLETED.value,
            Job.confidence.isnot(None),
        )
    )

    # Average processing time
    avg_time = await db.scalar(
        select(func.avg(Job.processing_time_ms)).where(
            Job.user_id == user.id,
            Job.status == JobStatus.COMPLETED.value,
            Job.processing_time_ms.isnot(None),
        )
    )

    return HistoryStats(
        total_jobs=total_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        total_characters_translated=total_chars,
        average_confidence=float(avg_confidence) if avg_confidence else None,
        average_processing_time_ms=float(avg_time) if avg_time else None,
    )


@router.get(
    "/{job_id}",
    response_model=JobDetail,
    dependencies=[Depends(RequireFeature(Feature.VIEW_HISTORY))],
)
async def get_job_detail(db: DBSession, user: CurrentUser, job_id: str):
    """
    Get detailed information about a specific job.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobDetail(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        source_language=job.source_language,
        target_language=job.target_language,
        style_preset=job.style_preset,
        input_preview=job.input_text[:200] if job.input_text else None,
        output_preview=job.output_text[:200] if job.output_text else None,
        input_text=job.input_text if not settings.enable_pii_redaction else None,
        output_text=job.output_text if not settings.enable_pii_redaction else None,
        file_name=job.file_name,
        confidence=float(job.confidence) if job.confidence else None,
        qa_report=job.qa_report,
        error_message=job.error_message,
        retries=job.retries,
        processing_time_ms=job.processing_time_ms,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireFeature(Feature.VIEW_HISTORY))],
)
async def delete_job(db: DBSession, user: CurrentUser, job_id: str):
    """
    Delete a job from history.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    logger.info("Job deleted", job_id=job_id, user_id=user.id)
    await db.delete(job)
