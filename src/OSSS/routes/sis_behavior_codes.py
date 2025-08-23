# src/OSSS/routes/sis_behavior_codes.py
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth import require_auth
from OSSS.db import get_session

router = APIRouter(prefix="/sis/behavior_codes", tags=["sis", "behavior_codes"])

@router.get("")
async def list_behavior_codes(
    _claims: dict = Depends(require_auth),  # 🔐 must have a valid bearer token
    session: AsyncSession = Depends(get_session),
):
    # Fetch all behavior codes (expects table `behavior_codes` with `code`, `description`)
    result = await session.execute(
        sa.text("SELECT code, description FROM behavior_codes ORDER BY code")
    )
    return list(result.mappings().all())
