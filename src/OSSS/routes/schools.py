# src/OSSS/routes/schools.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth import require_auth
from OSSS.db import get_session
from OSSS.db.models.sis import School

router = APIRouter(prefix="/schools", tags=["schools"])

@router.get("")
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
