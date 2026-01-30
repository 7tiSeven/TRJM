"""
TRJM Gateway - Admin Routes
============================
Role management and user administration endpoints
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from ...core.logging import logger
from ...db.models import AuditAction, Feature, Role, RoleFeature, User
from ...services.auth.jwt import AuditService, UserService
from ..deps import (
    CurrentUser,
    DBSession,
    RequireFeature,
    get_client_ip,
    get_correlation_id,
    get_user_agent,
)

router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
    dependencies=[Depends(RequireFeature(Feature.ADMIN_PANEL))],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class FeatureConfig(BaseModel):
    """Feature configuration for a role."""

    feature: str
    enabled: bool = True


class CreateRoleRequest(BaseModel):
    """Request to create a new role."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    features: List[FeatureConfig] = Field(default_factory=list)
    is_default: bool = False


class UpdateRoleRequest(BaseModel):
    """Request to update a role."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    features: Optional[List[FeatureConfig]] = None
    is_default: Optional[bool] = None


class RoleResponse(BaseModel):
    """Role information response."""

    id: str
    name: str
    description: Optional[str]
    features: List[FeatureConfig]
    is_default: bool
    user_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """User list item response."""

    id: str
    username: str
    email: Optional[str]
    display_name: Optional[str]
    role_name: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


class UpdateUserRoleRequest(BaseModel):
    """Request to update user's role."""

    role_id: str


class AdminStatsResponse(BaseModel):
    """Admin dashboard statistics."""

    total_users: int
    active_users: int
    total_roles: int
    total_jobs_today: int
    dev_mode: bool


# =============================================================================
# Role Endpoints
# =============================================================================


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db: DBSession):
    """
    List all roles with their features.
    """
    result = await db.execute(
        select(Role).options(selectinload(Role.features), selectinload(Role.users))
    )
    roles = result.scalars().all()

    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            features=[
                FeatureConfig(feature=f.feature_name, enabled=f.enabled) for f in role.features
            ],
            is_default=role.is_default,
            user_count=len(role.users),
            created_at=role.created_at,
            updated_at=role.updated_at,
        )
        for role in roles
    ]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    data: CreateRoleRequest,
):
    """
    Create a new role.
    """
    # Check if role name already exists
    existing = await db.execute(select(Role).where(Role.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{data.name}' already exists",
        )

    # Validate feature names
    valid_features = {f.value for f in Feature}
    for feature_config in data.features:
        if feature_config.feature not in valid_features:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid feature: {feature_config.feature}",
            )

    # If setting as default, unset other defaults
    if data.is_default:
        await db.execute(
            Role.__table__.update().where(Role.is_default == True).values(is_default=False)
        )

    # Create role
    role = Role(
        name=data.name,
        description=data.description,
        is_default=data.is_default,
    )
    db.add(role)
    await db.flush()

    # Add features
    for feature_config in data.features:
        role_feature = RoleFeature(
            role_id=role.id,
            feature_name=feature_config.feature,
            enabled=feature_config.enabled,
        )
        db.add(role_feature)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.ROLE_CREATED,
        user_id=user.id,
        resource="role",
        resource_id=role.id,
        details={"name": role.name},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        correlation_id=get_correlation_id(request),
    )

    logger.info("Role created", role_id=role.id, name=role.name, by_user=user.username)

    # Reload with relationships
    await db.refresh(role, ["features", "users"])

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        features=[FeatureConfig(feature=f.feature_name, enabled=f.enabled) for f in role.features],
        is_default=role.is_default,
        user_count=0,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(db: DBSession, role_id: str):
    """
    Get a specific role by ID.
    """
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.features), selectinload(Role.users))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        features=[FeatureConfig(feature=f.feature_name, enabled=f.enabled) for f in role.features],
        is_default=role.is_default,
        user_count=len(role.users),
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    role_id: str,
    data: UpdateRoleRequest,
):
    """
    Update an existing role.
    """
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.features), selectinload(Role.users))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Update fields
    if data.name is not None:
        # Check for duplicate
        existing = await db.execute(
            select(Role).where(Role.name == data.name, Role.id != role_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{data.name}' already exists",
            )
        role.name = data.name

    if data.description is not None:
        role.description = data.description

    if data.is_default is not None:
        if data.is_default:
            # Unset other defaults
            await db.execute(
                Role.__table__.update()
                .where(Role.is_default == True, Role.id != role_id)
                .values(is_default=False)
            )
        role.is_default = data.is_default

    # Update features if provided
    if data.features is not None:
        # Validate feature names
        valid_features = {f.value for f in Feature}
        for feature_config in data.features:
            if feature_config.feature not in valid_features:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid feature: {feature_config.feature}",
                )

        # Delete existing features
        await db.execute(delete(RoleFeature).where(RoleFeature.role_id == role_id))

        # Add new features
        for feature_config in data.features:
            role_feature = RoleFeature(
                role_id=role.id,
                feature_name=feature_config.feature,
                enabled=feature_config.enabled,
            )
            db.add(role_feature)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.ROLE_UPDATED,
        user_id=user.id,
        resource="role",
        resource_id=role.id,
        details={"name": role.name},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        correlation_id=get_correlation_id(request),
    )

    logger.info("Role updated", role_id=role.id, name=role.name, by_user=user.username)

    await db.flush()
    await db.refresh(role, ["features", "users"])

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        features=[FeatureConfig(feature=f.feature_name, enabled=f.enabled) for f in role.features],
        is_default=role.is_default,
        user_count=len(role.users),
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    role_id: str,
):
    """
    Delete a role.

    Cannot delete roles that have users assigned.
    """
    result = await db.execute(
        select(Role).options(selectinload(Role.users)).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    if role.users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete role with {len(role.users)} assigned users",
        )

    if role.is_default:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the default role",
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.ROLE_DELETED,
        user_id=user.id,
        resource="role",
        resource_id=role.id,
        details={"name": role.name},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        correlation_id=get_correlation_id(request),
    )

    logger.info("Role deleted", role_id=role.id, name=role.name, by_user=user.username)

    await db.delete(role)


# =============================================================================
# User Management Endpoints
# =============================================================================


@router.get("/users", response_model=List[UserListResponse])
async def list_users(db: DBSession, skip: int = 0, limit: int = 100):
    """
    List all users.
    """
    result = await db.execute(
        select(User).options(selectinload(User.role)).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    return [
        UserListResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            role_name=user.role.name,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
        )
        for user in users
    ]


@router.put("/users/{user_id}/role")
async def update_user_role(
    request: Request,
    db: DBSession,
    admin: CurrentUser,
    user_id: str,
    data: UpdateUserRoleRequest,
):
    """
    Update a user's role.
    """
    # Get target user
    user_service = UserService(db)
    target_user = await user_service.get_user_by_id(user_id)

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify new role exists
    result = await db.execute(select(Role).where(Role.id == data.role_id))
    new_role = result.scalar_one_or_none()

    if not new_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    old_role_name = target_user.role.name
    target_user.role_id = data.role_id

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.USER_ROLE_CHANGED,
        user_id=admin.id,
        resource="user",
        resource_id=user_id,
        details={
            "target_username": target_user.username,
            "old_role": old_role_name,
            "new_role": new_role.name,
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        correlation_id=get_correlation_id(request),
    )

    logger.info(
        "User role changed",
        target_user_id=user_id,
        target_username=target_user.username,
        old_role=old_role_name,
        new_role=new_role.name,
        by_user=admin.username,
    )

    return {"message": "User role updated", "new_role": new_role.name}


@router.get("/features", response_model=List[str])
async def list_features():
    """
    List all available features.
    """
    return [f.value for f in Feature]


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(db: DBSession):
    """
    Get admin dashboard statistics.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    from ...db.models import Job

    # Count users
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(select(func.count(User.id)).where(User.is_active == True))

    # Count roles
    total_roles = await db.scalar(select(func.count(Role.id)))

    # Count jobs today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_jobs_today = await db.scalar(
        select(func.count(Job.id)).where(Job.created_at >= today_start)
    )

    from ...core.config import settings

    return AdminStatsResponse(
        total_users=total_users or 0,
        active_users=active_users or 0,
        total_roles=total_roles or 0,
        total_jobs_today=total_jobs_today or 0,
        dev_mode=settings.dev_mode,
    )
