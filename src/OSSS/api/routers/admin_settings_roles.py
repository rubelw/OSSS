# src/OSSS/api/routers/admin_settings_roles.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, status

# Adjust these imports to your project layout as needed:
from OSSS.db.session import get_session
from OSSS.db.models.sis import Role  # update if Role is defined elsewhere

from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/admin/settings/roles", tags=["admin"])


# -------------------------
# Pydantic Schemas (v2)
# -------------------------
class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class RoleOut(RoleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Helpers
# -------------------------
async def _get_role_or_404(session: AsyncSession, role_id: UUID) -> Role:
    result = await session.execute(
        sa.select(Role).where(Role.id == str(role_id))
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


# -------------------------
# Routes
# -------------------------
@router.get("", response_model=list[RoleOut])
async def list_roles(session: AsyncSession = Depends(get_session)):
    """Return all roles (no filters/pagination)."""
    result = await session.execute(sa.select(Role).order_by(Role.name))
    return result.scalars().all()


@router.get("/{role_id}", response_model=RoleOut)
async def get_role(role_id: UUID, session: AsyncSession = Depends(get_session)):
    role = await _get_role_or_404(session, role_id)
    return role


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(payload: RoleCreate, session: AsyncSession = Depends(get_session)):
    role = Role(**payload.model_dump())
    session.add(role)
    try:
        await session.flush()
        await session.refresh(role)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Role with this name already exists."
        ) from e
    return role


@router.patch("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    session: AsyncSession = Depends(get_session),
):
    role = await _get_role_or_404(session, role_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(role, k, v)
    try:
        await session.flush()
        await session.refresh(role)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Role with this name already exists."
        ) from e
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: UUID, session: AsyncSession = Depends(get_session)):
    role = await _get_role_or_404(session, role_id)
    await session.delete(role)
    await session.flush()
    return None
