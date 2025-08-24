# src/OSSS/api/routers/admin_settings_departments.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from OSSS.db.session import get_session
from OSSS.db.models import Department  # adjust import if Department lives elsewhere

router = APIRouter(prefix="/admin/settings/departments", tags=["admin"])


# -------------------------
# Schemas (Pydantic v2)
# -------------------------
class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class DepartmentCreate(DepartmentBase):
    school_id: UUID


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    school_id: Optional[UUID] = None


class DepartmentOut(DepartmentBase):
    id: UUID
    school_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Helpers
# -------------------------
async def _get_department_or_404(session: AsyncSession, department_id: UUID) -> Department:
    result = await session.execute(
        sa.select(Department).where(Department.id == str(department_id))
    )
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


# -------------------------
# Routes
# -------------------------
@router.get("", response_model=list[DepartmentOut])
async def list_departments(session: AsyncSession = Depends(get_session)):
    """Return all departments (no query parameters)."""
    result = await session.execute(sa.select(Department).order_by(Department.name))
    return result.scalars().all()


@router.get("/school/{school_id}", response_model=list[DepartmentOut])
async def list_departments_for_school(
    school_id: UUID, session: AsyncSession = Depends(get_session)
):
    """Convenience endpoint to list departments for a specific school."""
    stmt = (
        sa.select(Department)
        .where(Department.school_id == str(school_id))
        .order_by(Department.name)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{department_id}", response_model=DepartmentOut)
async def get_department(department_id: UUID, session: AsyncSession = Depends(get_session)):
    dept = await _get_department_or_404(session, department_id)
    return dept


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(payload: DepartmentCreate, session: AsyncSession = Depends(get_session)):
    dept = Department(
        school_id=str(payload.school_id),
        name=payload.name,
    )
    session.add(dept)
    try:
        await session.flush()
        await session.refresh(dept)
    except IntegrityError as e:
        await session.rollback()
        # Unique constraint: uq_department_name (school_id, name)
        raise HTTPException(
            status_code=409, detail="Department with this name already exists for the school."
        ) from e
    return dept


@router.patch("/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: UUID,
    payload: DepartmentUpdate,
    session: AsyncSession = Depends(get_session),
):
    dept = await _get_department_or_404(session, department_id)
    data = payload.model_dump(exclude_unset=True)

    if "school_id" in data and data["school_id"] is not None:
        data["school_id"] = str(data["school_id"])

    for k, v in data.items():
        setattr(dept, k, v)

    try:
        await session.flush()
        await session.refresh(dept)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Department with this name already exists for the school."
        ) from e

    return dept


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(department_id: UUID, session: AsyncSession = Depends(get_session)):
    dept = await _get_department_or_404(session, department_id)
    await session.delete(dept)
    await session.flush()
    return None
