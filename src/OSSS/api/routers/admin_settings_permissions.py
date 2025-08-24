# src/OSSS/api/routers/admin_settings_permissions.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from OSSS.db.session import get_session
from OSSS.db.models.permissions import Permission

router = APIRouter(prefix="/admin/settings/permissions", tags=["admin"])


# -------------------------
# Pydantic Schemas (v2)
# -------------------------
class PermissionBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=255)  # e.g., "sis.students.read"
    description: Optional[str] = None


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None


class PermissionOut(PermissionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Helpers
# -------------------------
async def _get_permission_or_404(
    session: AsyncSession, permission_id: UUID
) -> Permission:
    result = await session.execute(
        sa.select(Permission).where(Permission.id == str(permission_id))
    )
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    return perm


# -------------------------
# Routes
# -------------------------
@router.get("", response_model=list[PermissionOut])
async def list_permissions(
    session: AsyncSession = Depends(get_session),
):
    """Return all permissions sorted by code (no filters/pagination)."""
    result = await session.execute(sa.select(Permission).order_by(Permission.code.asc()))
    return result.scalars().all()


@router.get("/{permission_id}", response_model=PermissionOut)
async def get_permission(
    permission_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    perm = await _get_permission_or_404(session, permission_id)
    return perm


@router.post("", response_model=PermissionOut, status_code=status.HTTP_201_CREATED)
async def create_permission(
    payload: PermissionCreate,
    session: AsyncSession = Depends(get_session),
):
    perm = Permission(**payload.model_dump())
    session.add(perm)
    try:
        await session.flush()   # assign PK/server defaults
        await session.refresh(perm)
    except IntegrityError as e:
        await session.rollback()
        # likely unique constraint on code
        raise HTTPException(
            status_code=409, detail="Permission with this code already exists."
        ) from e
    return perm


@router.patch("/{permission_id}", response_model=PermissionOut)
async def update_permission(
    permission_id: UUID,
    payload: PermissionUpdate,
    session: AsyncSession = Depends(get_session),
):
    perm = await _get_permission_or_404(session, permission_id)

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(perm, k, v)

    try:
        await session.flush()
        await session.refresh(perm)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Permission with this code already exists."
        ) from e

    return perm


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    perm = await _get_permission_or_404(session, permission_id)
    await session.delete(perm)
    await session.flush()
    return None
