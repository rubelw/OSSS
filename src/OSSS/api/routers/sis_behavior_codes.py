# src/OSSS/api/routers/sis_behavior_codes.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.behavior_codes import BehaviorCode
from OSSS.schemas.sis import BehaviorCodeOut

router = APIRouter(prefix="/sis", tags=["SIS"])

@router.get("/behavior_codes", response_model=list[BehaviorCodeOut])
async def list_behavior_codes(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> list[BehaviorCodeOut]:
    """
    Return all SIS behavior codes ordered by code.
    Requires a valid Bearer token (accepted audiences include osss-api and osss-web).
    """
    result = await session.execute(
        select(BehaviorCode).order_by(BehaviorCode.code)
    )
    rows = result.scalars().all()
    return [BehaviorCodeOut.model_validate(row) for row in rows]
