# src/OSSS/api/routers/sis_settings_academics_grading_periods.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, status

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Adjust these imports to your project structure
from OSSS.db.session import get_session
from OSSS.db.models.grading_periods import GradingPeriod  # update path if different

router = APIRouter(prefix="/sis/settings", tags=["sis"])


# -------------------------
# Schemas (Pydantic v2)
# -------------------------
class GPBase(BaseModel):
    term_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on/after start_date")
        return self


class GPCreate(GPBase):
    pass


class GPUpdate(BaseModel):
    term_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def _validate_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on/after start_date")
        return self


class GPOut(GPBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Helpers
# -------------------------
async def _get_gp_or_404(session: AsyncSession, gp_id: UUID) -> GradingPeriod:
    res = await session.execute(sa.select(GradingPeriod).where(GradingPeriod.id == str(gp_id)))
    gp = res.scalar_one_or_none()
    if not gp:
        raise HTTPException(status_code=404, detail="Grading period not found")
    return gp


# -------------------------
# Routes
# -------------------------
@router.get("/grading_periods", response_model=list[GPOut])
async def list_grading_periods(session: AsyncSession = Depends(get_session)):
    """
    Return **all** grading periods, ordered by (term_id, start_date).
    Keep it simple—no query params.
    """
    stmt = sa.select(GradingPeriod).order_by(GradingPeriod.term_id, GradingPeriod.start_date)
    rows = (await session.execute(stmt)).scalars().all()
    return rows


@router.get("/grading_periods/term/{term_id}", response_model=list[GPOut])
async def list_grading_periods_for_term(term_id: UUID, session: AsyncSession = Depends(get_session)):
    """
    Convenience: periods for a single term.
    """
    stmt = (
        sa.select(GradingPeriod)
        .where(GradingPeriod.term_id == str(term_id))
        .order_by(GradingPeriod.start_date)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return rows


@router.get("/grading_periods/{gp_id}", response_model=GPOut)
async def get_grading_period(gp_id: UUID, session: AsyncSession = Depends(get_session)):
    gp = await _get_gp_or_404(session, gp_id)
    return gp


@router.post("/grading_periods", response_model=GPOut, status_code=status.HTTP_201_CREATED)
async def create_grading_period(payload: GPCreate, session: AsyncSession = Depends(get_session)):
    # Extra guard: ensure dates valid even if model validator is bypassed somewhere
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date must be on/after start_date")

    gp = GradingPeriod(
        term_id=str(payload.term_id),
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    session.add(gp)
    try:
        await session.flush()
        await session.refresh(gp)
    except IntegrityError as e:
        await session.rollback()
        # Likely FK failure or uniqueness (if you add one later)
        raise HTTPException(status_code=409, detail="Could not create grading period.") from e
    return gp


@router.patch("/grading_periods/{gp_id}", response_model=GPOut)
async def update_grading_period(
    gp_id: UUID,
    payload: GPUpdate,
    session: AsyncSession = Depends(get_session),
):
    gp = await _get_gp_or_404(session, gp_id)

    # Compute prospective dates to validate
    new_start = payload.start_date if payload.start_date is not None else gp.start_date
    new_end = payload.end_date if payload.end_date is not None else gp.end_date
    if new_start and new_end and new_end < new_start:
        raise HTTPException(status_code=422, detail="end_date must be on/after start_date")

    data = payload.model_dump(exclude_unset=True)
    if "term_id" in data:
        data["term_id"] = str(data["term_id"])
    for k, v in data.items():
        setattr(gp, k, v)

    try:
        await session.flush()
        await session.refresh(gp)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Could not update grading period.") from e

    return gp


@router.delete("/grading_periods/{gp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grading_period(gp_id: UUID, session: AsyncSession = Depends(get_session)):
    gp = await _get_gp_or_404(session, gp_id)
    await session.delete(gp)
    await session.flush()
    return None
