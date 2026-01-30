"""
TRJM Gateway - Glossary API Routes
===================================
Endpoints for glossary management
"""

import csv
import io
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.logging import logger
from ...db.models import (
    AuditAction,
    Feature,
    Glossary,
    GlossaryEntry as GlossaryEntryModel,
)
from ...services.auth.jwt import AuditService
from ..deps import (
    CurrentUser,
    DBSession,
    RequireFeature,
    get_client_ip,
    get_correlation_id,
    get_user_agent,
)

router = APIRouter(prefix="/glossary", tags=["Glossary"])


# =============================================================================
# Request/Response Models
# =============================================================================


class GlossaryEntryCreate(BaseModel):
    """Request to create a glossary entry."""

    source_term: str = Field(..., min_length=1, max_length=500)
    target_term: str = Field(..., min_length=1, max_length=500)
    case_sensitive: bool = False
    context: Optional[str] = Field(None, max_length=1000)


class GlossaryEntryResponse(BaseModel):
    """Glossary entry response."""

    id: str
    source_term: str
    target_term: str
    case_sensitive: bool
    context: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateGlossaryRequest(BaseModel):
    """Request to create a glossary."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    source_language: str = Field(default="en", max_length=10)
    target_language: str = Field(default="ar", max_length=10)
    entries: List[GlossaryEntryCreate] = Field(default_factory=list)


class UpdateGlossaryRequest(BaseModel):
    """Request to update a glossary."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class GlossaryResponse(BaseModel):
    """Glossary response."""

    id: str
    name: str
    description: Optional[str]
    source_language: str
    target_language: str
    entry_count: int
    version: int
    is_global: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GlossaryDetailResponse(GlossaryResponse):
    """Detailed glossary response with entries."""

    entries: List[GlossaryEntryResponse]


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=List[GlossaryResponse],
    dependencies=[Depends(RequireFeature(Feature.USE_GLOSSARY))],
)
async def list_glossaries(db: DBSession, user: CurrentUser):
    """
    List all glossaries accessible to the user.

    Includes user's own glossaries and global glossaries.
    """
    result = await db.execute(
        select(Glossary)
        .options(selectinload(Glossary.entries))
        .where((Glossary.user_id == user.id) | (Glossary.is_global == True))
        .order_by(Glossary.name)
    )
    glossaries = result.scalars().all()

    return [
        GlossaryResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            source_language=g.source_language,
            target_language=g.target_language,
            entry_count=len(g.entries),
            version=g.version,
            is_global=g.is_global,
            created_at=g.created_at,
            updated_at=g.updated_at,
        )
        for g in glossaries
    ]


@router.post(
    "",
    response_model=GlossaryDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireFeature(Feature.MANAGE_GLOSSARY))],
)
async def create_glossary(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    data: CreateGlossaryRequest,
):
    """
    Create a new glossary with optional initial entries.
    """
    # Create glossary
    glossary = Glossary(
        user_id=user.id,
        name=data.name,
        description=data.description,
        source_language=data.source_language,
        target_language=data.target_language,
    )
    db.add(glossary)
    await db.flush()

    # Add entries
    for entry_data in data.entries:
        entry = GlossaryEntryModel(
            glossary_id=glossary.id,
            source_term=entry_data.source_term,
            target_term=entry_data.target_term,
            case_sensitive=entry_data.case_sensitive,
            context=entry_data.context,
        )
        db.add(entry)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.GLOSSARY_CREATED,
        user_id=user.id,
        resource="glossary",
        resource_id=glossary.id,
        details={"name": glossary.name, "entry_count": len(data.entries)},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        correlation_id=get_correlation_id(request),
    )

    logger.info(
        "Glossary created",
        glossary_id=glossary.id,
        name=glossary.name,
        entries=len(data.entries),
        user_id=user.id,
    )

    await db.refresh(glossary, ["entries"])

    return GlossaryDetailResponse(
        id=glossary.id,
        name=glossary.name,
        description=glossary.description,
        source_language=glossary.source_language,
        target_language=glossary.target_language,
        entry_count=len(glossary.entries),
        version=glossary.version,
        is_global=glossary.is_global,
        created_at=glossary.created_at,
        updated_at=glossary.updated_at,
        entries=[
            GlossaryEntryResponse(
                id=e.id,
                source_term=e.source_term,
                target_term=e.target_term,
                case_sensitive=e.case_sensitive,
                context=e.context,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in glossary.entries
        ],
    )


@router.get(
    "/{glossary_id}",
    response_model=GlossaryDetailResponse,
    dependencies=[Depends(RequireFeature(Feature.USE_GLOSSARY))],
)
async def get_glossary(db: DBSession, user: CurrentUser, glossary_id: str):
    """
    Get a glossary with all entries.
    """
    result = await db.execute(
        select(Glossary)
        .options(selectinload(Glossary.entries))
        .where(
            Glossary.id == glossary_id,
            (Glossary.user_id == user.id) | (Glossary.is_global == True),
        )
    )
    glossary = result.scalar_one_or_none()

    if not glossary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Glossary not found",
        )

    return GlossaryDetailResponse(
        id=glossary.id,
        name=glossary.name,
        description=glossary.description,
        source_language=glossary.source_language,
        target_language=glossary.target_language,
        entry_count=len(glossary.entries),
        version=glossary.version,
        is_global=glossary.is_global,
        created_at=glossary.created_at,
        updated_at=glossary.updated_at,
        entries=[
            GlossaryEntryResponse(
                id=e.id,
                source_term=e.source_term,
                target_term=e.target_term,
                case_sensitive=e.case_sensitive,
                context=e.context,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in glossary.entries
        ],
    )


@router.put(
    "/{glossary_id}",
    response_model=GlossaryResponse,
    dependencies=[Depends(RequireFeature(Feature.MANAGE_GLOSSARY))],
)
async def update_glossary(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    glossary_id: str,
    data: UpdateGlossaryRequest,
):
    """
    Update glossary metadata.
    """
    result = await db.execute(
        select(Glossary)
        .options(selectinload(Glossary.entries))
        .where(Glossary.id == glossary_id, Glossary.user_id == user.id)
    )
    glossary = result.scalar_one_or_none()

    if not glossary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Glossary not found or access denied",
        )

    if data.name is not None:
        glossary.name = data.name
    if data.description is not None:
        glossary.description = data.description

    glossary.version += 1

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.GLOSSARY_UPDATED,
        user_id=user.id,
        resource="glossary",
        resource_id=glossary.id,
        details={"name": glossary.name},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        correlation_id=get_correlation_id(request),
    )

    return GlossaryResponse(
        id=glossary.id,
        name=glossary.name,
        description=glossary.description,
        source_language=glossary.source_language,
        target_language=glossary.target_language,
        entry_count=len(glossary.entries),
        version=glossary.version,
        is_global=glossary.is_global,
        created_at=glossary.created_at,
        updated_at=glossary.updated_at,
    )


@router.delete(
    "/{glossary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireFeature(Feature.MANAGE_GLOSSARY))],
)
async def delete_glossary(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    glossary_id: str,
):
    """
    Delete a glossary.
    """
    result = await db.execute(
        select(Glossary).where(Glossary.id == glossary_id, Glossary.user_id == user.id)
    )
    glossary = result.scalar_one_or_none()

    if not glossary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Glossary not found or access denied",
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.GLOSSARY_DELETED,
        user_id=user.id,
        resource="glossary",
        resource_id=glossary.id,
        details={"name": glossary.name},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        correlation_id=get_correlation_id(request),
    )

    logger.info("Glossary deleted", glossary_id=glossary_id, user_id=user.id)

    await db.delete(glossary)


@router.post(
    "/{glossary_id}/entries",
    response_model=GlossaryEntryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequireFeature(Feature.MANAGE_GLOSSARY))],
)
async def add_glossary_entry(
    db: DBSession,
    user: CurrentUser,
    glossary_id: str,
    data: GlossaryEntryCreate,
):
    """
    Add an entry to a glossary.
    """
    # Verify glossary access
    result = await db.execute(
        select(Glossary).where(Glossary.id == glossary_id, Glossary.user_id == user.id)
    )
    glossary = result.scalar_one_or_none()

    if not glossary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Glossary not found or access denied",
        )

    entry = GlossaryEntryModel(
        glossary_id=glossary_id,
        source_term=data.source_term,
        target_term=data.target_term,
        case_sensitive=data.case_sensitive,
        context=data.context,
    )
    db.add(entry)
    glossary.version += 1
    await db.flush()

    return GlossaryEntryResponse(
        id=entry.id,
        source_term=entry.source_term,
        target_term=entry.target_term,
        case_sensitive=entry.case_sensitive,
        context=entry.context,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.delete(
    "/{glossary_id}/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireFeature(Feature.MANAGE_GLOSSARY))],
)
async def delete_glossary_entry(
    db: DBSession,
    user: CurrentUser,
    glossary_id: str,
    entry_id: str,
):
    """
    Delete a glossary entry.
    """
    # Verify glossary access
    result = await db.execute(
        select(Glossary).where(Glossary.id == glossary_id, Glossary.user_id == user.id)
    )
    glossary = result.scalar_one_or_none()

    if not glossary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Glossary not found or access denied",
        )

    # Delete entry
    await db.execute(
        delete(GlossaryEntryModel).where(
            GlossaryEntryModel.id == entry_id,
            GlossaryEntryModel.glossary_id == glossary_id,
        )
    )
    glossary.version += 1


@router.post(
    "/{glossary_id}/import",
    response_model=GlossaryDetailResponse,
    dependencies=[Depends(RequireFeature(Feature.MANAGE_GLOSSARY))],
)
async def import_glossary_csv(
    db: DBSession,
    user: CurrentUser,
    glossary_id: str,
    file: UploadFile = File(...),
):
    """
    Import entries from a CSV file.

    CSV format: source,target,case_sensitive,context
    """
    # Verify glossary access
    result = await db.execute(
        select(Glossary)
        .options(selectinload(Glossary.entries))
        .where(Glossary.id == glossary_id, Glossary.user_id == user.id)
    )
    glossary = result.scalar_one_or_none()

    if not glossary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Glossary not found or access denied",
        )

    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )

    # Read and parse CSV
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("utf-8-sig")  # Try with BOM

    reader = csv.DictReader(io.StringIO(text))
    imported_count = 0

    for row in reader:
        source = row.get("source", "").strip()
        target = row.get("target", "").strip()

        if not source or not target:
            continue

        case_sensitive = row.get("case_sensitive", "false").lower() == "true"
        context = row.get("context", "").strip() or None

        entry = GlossaryEntryModel(
            glossary_id=glossary_id,
            source_term=source,
            target_term=target,
            case_sensitive=case_sensitive,
            context=context,
        )
        db.add(entry)
        imported_count += 1

    glossary.version += 1
    await db.flush()
    await db.refresh(glossary, ["entries"])

    logger.info(
        "Glossary CSV imported",
        glossary_id=glossary_id,
        imported_count=imported_count,
        user_id=user.id,
    )

    return GlossaryDetailResponse(
        id=glossary.id,
        name=glossary.name,
        description=glossary.description,
        source_language=glossary.source_language,
        target_language=glossary.target_language,
        entry_count=len(glossary.entries),
        version=glossary.version,
        is_global=glossary.is_global,
        created_at=glossary.created_at,
        updated_at=glossary.updated_at,
        entries=[
            GlossaryEntryResponse(
                id=e.id,
                source_term=e.source_term,
                target_term=e.target_term,
                case_sensitive=e.case_sensitive,
                context=e.context,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in glossary.entries
        ],
    )
