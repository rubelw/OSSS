# src/OSSS/api/routers/districts.py
from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.sis import District

router = APIRouter(prefix="/admin/settings", tags=["admin"])

# --------- Schemas (input/output) ---------
class DistrictCreate(BaseModel):
    name: str = Field(..., min_length=1, description="District name (unique)")
    code: Optional[str] = Field(None, description="Optional unique district code")

class DistrictOut(BaseModel):
    id: UUID
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Pydantic v2 way to read from SQLAlchemy objects
    model_config = ConfigDict(from_attributes=True)

# --------- Routes ---------

@router.get("/districts", response_model=list[DistrictOut])
async def list_districts(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> list[DistrictOut]:
    result = await session.execute(select(District).order_by(District.name))
    rows = result.scalars().all()
    return [DistrictOut.model_validate(d) for d in rows]

@router.get("/districts/{district_id}", response_model=DistrictOut)
async def get_district(
    district_id: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> DistrictOut:
    obj = await session.get(District, district_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")
    return DistrictOut.model_validate(obj)

@router.post("/districts", response_model=DistrictOut, status_code=status.HTTP_201_CREATED)
async def create_district(
    payload: DistrictCreate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> DistrictOut:
    new_obj = District(name=payload.name, code=payload.code)
    session.add(new_obj)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="District with this name or code already exists",
        )
    await session.refresh(new_obj)
    return DistrictOut.model_validate(new_obj)

@router.delete("/districts/{district_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_district(
    district_id: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> Response:
    obj = await session.get(District, district_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")

    await session.delete(obj)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
