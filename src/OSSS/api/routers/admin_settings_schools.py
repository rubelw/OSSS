# src/OSSS/routes/schools.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth import require_auth
from OSSS.db import get_session
from OSSS.db.models.sis import School

router = APIRouter(prefix="/admin/settings", tags=["admin"])

# ---------- Schemas ----------
class SchoolCreate(BaseModel):
    name: str = Field(..., description="School display name")
    school_code: str | None = Field(None, description="Local/internal school code")
    nces_school_id: str | None = Field(None, description="US NCES school id")
    building_code: str | None = Field(None, description="Facility/building code")
    type: str | None = Field(None, description="e.g., elementary, middle, high")
    timezone: str | None = Field(None, description="IANA timezone, e.g., America/Chicago")

# ---------- Routes ----------

@router.get("/schools")
async def list_schools(
    _claims: dict = Depends(require_auth),  # 🔐 require valid bearer token
    session: AsyncSession = Depends(get_session),
    q: str | None = Query(default=None, description="Optional text search on school name"),
):
    stmt = select(
        School.id,
        School.name,
        School.school_code,
        School.nces_school_id,
        School.building_code,
        School.type,
        School.timezone,
    )

    if q:
        # simple case-insensitive search by name
        stmt = stmt.where(School.name.ilike(f"%{q}%"))

    stmt = stmt.order_by(School.name.asc())

    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings().all()]


@router.get("/schools/{school_id}")
async def get_school(
    school_id: int,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(
            School.id,
            School.name,
            School.school_code,
            School.nces_school_id,
            School.building_code,
            School.type,
            School.timezone,
        ).where(School.id == school_id)
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")
    return dict(row)


@router.post("/schools", status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: SchoolCreate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    # Create and persist a new School
    new_school = School(
        name=payload.name,
        school_code=payload.school_code,
        nces_school_id=payload.nces_school_id,
        building_code=payload.building_code,
        type=payload.type,
        timezone=payload.timezone,
    )
    session.add(new_school)
    await session.commit()
    await session.refresh(new_school)

    return {
        "id": new_school.id,
        "name": new_school.name,
        "school_code": new_school.school_code,
        "nces_school_id": new_school.nces_school_id,
        "building_code": new_school.building_code,
        "type": new_school.type,
        "timezone": new_school.timezone,
    }


@router.delete("/schools/{school_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_school(
    school_id: int,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    # Find the school
    obj = await session.get(School, school_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")

    # Delete and commit
    await session.delete(obj)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
