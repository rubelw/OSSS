# src/OSSS/api/routers/academic_terms.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.academic_terms import AcademicTerm  # adjust path if different

router = APIRouter(prefix="/sis/settings", tags=["sis"])

# ---------- Schemas ----------

class AcademicTermCreate(BaseModel):
    school_id: UUID = Field(..., description="School UUID (FK)")
    name: str = Field(..., min_length=1, description="Display name of the term")
    type: Optional[str] = Field(None, description="e.g., semester, quarter, trimester, session, year")
    start_date: date = Field(..., description="Term start date (inclusive)")
    end_date: date = Field(..., description="Term end date (inclusive)")

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: date, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class AcademicTermOut(BaseModel):
    id: UUID
    school_id: UUID
    name: str
    type: Optional[str] = None
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Routes ----------

@router.get("/academic_terms", response_model=list[AcademicTermOut])
async def list_academic_terms(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
    school_id: Optional[UUID] = Query(default=None, description="Filter by school UUID"),
) -> list[AcademicTermOut]:
    """
    List academic terms (optionally filtered by school). Ordered by start_date ascending.
    """
    stmt = select(AcademicTerm)
    if school_id:
        stmt = stmt.where(AcademicTerm.school_id == str(school_id))
    stmt = stmt.order_by(AcademicTerm.start_date.asc())

    result = await session.execute(stmt)
    terms = result.scalars().all()
    return [AcademicTermOut.model_validate(t) for t in terms]


@router.get("/academic_terms/{term_id}", response_model=AcademicTermOut)
async def get_academic_term(
    term_id: UUID,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> AcademicTermOut:
    """
    Retrieve a single academic term by UUID.
    """
    obj = await session.get(AcademicTerm, str(term_id))
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic term not found")
    return AcademicTermOut.model_validate(obj)


@router.post("/academic_terms", response_model=AcademicTermOut, status_code=status.HTTP_201_CREATED)
async def create_academic_term(
    payload: AcademicTermCreate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> AcademicTermOut:
    """
    Create a new academic term. Ensures end_date >= start_date.
    """
    new_obj = AcademicTerm(
        school_id=str(payload.school_id),
        name=payload.name,
        type=payload.type,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )

    session.add(new_obj)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # Most likely FK violation (school_id) or any future unique constraint
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create term due to a constraint violation (check school_id or duplicates).",
        )

    await session.refresh(new_obj)
    return AcademicTermOut.model_validate(new_obj)


@router.delete("/academic_terms/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_academic_term(
    term_id: UUID,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """
    Delete an academic term by UUID.
    """
    obj = await session.get(AcademicTerm, str(term_id))
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic term not found")

    await session.delete(obj)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

