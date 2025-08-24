# src/OSSS/api/routers/sis_settings_catalog_courses.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from OSSS.db.session import get_session
from OSSS.db.models.courses import Course  # adjust import if Course lives elsewhere

router = APIRouter(prefix="/sis/settings", tags=["sis"])


# -------------------------
# Pydantic Schemas (v2)
# -------------------------
class CourseBase(BaseModel):
    school_id: UUID
    subject_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=255)
    credit_hours: Optional[Decimal] = None


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    school_id: Optional[UUID] = None
    subject_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=255)
    credit_hours: Optional[Decimal] = None


class CourseOut(CourseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Helpers
# -------------------------
async def _get_course_or_404(session: AsyncSession, course_id: UUID) -> Course:
    result = await session.execute(sa.select(Course).where(Course.id == str(course_id)))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


# -------------------------
# Routes
# -------------------------
@router.get("/courses", response_model=list[CourseOut])
async def list_courses(
    session: AsyncSession = Depends(get_session),
    school_id: Optional[UUID] = None,
    subject_id: Optional[UUID] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order: str = "name",          # name | code | created_at | updated_at
    desc: bool = False,
):
    stmt = sa.select(Course)

    if school_id:
        stmt = stmt.where(Course.school_id == str(school_id))
    if subject_id:
        stmt = stmt.where(Course.subject_id == str(subject_id))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(sa.or_(Course.name.ilike(like), Course.code.ilike(like)))

    order_col = {
        "name": Course.name,
        "code": Course.code,
        "created_at": Course.created_at,
        "updated_at": Course.updated_at,
    }.get(order, Course.name)
    if desc:
        order_col = order_col.desc()

    stmt = stmt.order_by(order_col).limit(limit).offset(offset)

    rows = (await session.execute(stmt)).scalars().all()
    return rows


@router.get("/courses/{course_id}", response_model=CourseOut)
async def get_course(
    course_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await _get_course_or_404(session, course_id)


@router.post("/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    session: AsyncSession = Depends(get_session),
):
    course = Course(**payload.model_dump())
    session.add(course)
    try:
        await session.flush()     # get PK/defaults
        await session.refresh(course)
    except IntegrityError as e:
        await session.rollback()
        # FK violations or unique constraints (if present) surface here
        raise HTTPException(status_code=400, detail="Invalid course or duplicate.") from e
    return course


@router.patch("/courses/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: UUID,
    payload: CourseUpdate,
    session: AsyncSession = Depends(get_session),
):
    course = await _get_course_or_404(session, course_id)

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(course, k, v)

    try:
        await session.flush()
        await session.refresh(course)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Invalid update or duplicate.") from e

    return course


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    course = await _get_course_or_404(session, course_id)
    await session.delete(course)
    await session.flush()
    return None
