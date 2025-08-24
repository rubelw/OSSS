# src/OSSS/api/routers/admin_settings_subjects.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

# Adjust these imports to your project structure
from OSSS.db.session import get_session
from OSSS.db.models.sis import Subject  # <-- update if Subject lives elsewhere

router = APIRouter(prefix="/admin/settings/subjects", tags=["admin"])


# -------------------------
# Pydantic Schemas (v2)
# -------------------------
class SubjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=255)
    department_id: Optional[UUID] = None


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=255)
    department_id: Optional[UUID] = None


class SubjectOut(SubjectBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Helpers
# -------------------------
async def _get_subject_or_404(session: AsyncSession, subject_id: UUID) -> Subject:
    # If your GUID column is truly UUID on PG you can use Subject.id == subject_id.
    result = await session.execute(sa.select(Subject).where(Subject.id == str(subject_id)))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


# -------------------------
# Routes
# -------------------------

@router.get("", response_model=list[SubjectOut])
async def list_subjects(
    session: AsyncSession = Depends(get_session),
    q: Optional[str] = None,                 # search in name/code
    department_id: Optional[UUID] = None,    # filter
    limit: int = 100,
    offset: int = 0,
    order: str = "name",                     # name | code | created_at | updated_at
    desc: bool = False,
):
    stmt = sa.select(Subject)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(sa.or_(Subject.name.ilike(like), Subject.code.ilike(like)))

    if department_id is not None:
        stmt = stmt.where(Subject.department_id == str(department_id))

    order_col = {
        "name": Subject.name,
        "code": Subject.code,
        "created_at": Subject.created_at,
        "updated_at": Subject.updated_at,
    }.get(order, Subject.name)
    if desc:
        order_col = order_col.desc()

    stmt = stmt.order_by(order_col).limit(limit).offset(offset)

    rows = (await session.execute(stmt)).scalars().all()
    return rows


@router.get("/{subject_id}", response_model=SubjectOut)
async def get_subject(
    subject_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    subject = await _get_subject_or_404(session, subject_id)
    return subject


@router.post("", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    session: AsyncSession = Depends(get_session),
):
    subject = Subject(**payload.model_dump())
    session.add(subject)
    try:
        await session.flush()   # get PK & defaults
        await session.refresh(subject)
    except IntegrityError as e:
        await session.rollback()
        # If you later add unique constraints (e.g., per-department name), return 409 here.
        raise HTTPException(status_code=409, detail="Duplicate subject.") from e
    return subject


@router.patch("/{subject_id}", response_model=SubjectOut)
async def update_subject(
    subject_id: UUID,
    payload: SubjectUpdate,
    session: AsyncSession = Depends(get_session),
):
    subject = await _get_subject_or_404(session, subject_id)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(subject, k, v)

    try:
        await session.flush()
        await session.refresh(subject)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Duplicate subject.") from e

    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    subject = await _get_subject_or_404(session, subject_id)
    await session.delete(subject)
    await session.flush()
    return None
