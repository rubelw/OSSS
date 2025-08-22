# src/OSSS/routes/states.py
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth import require_auth
from OSSS.db import get_session

router = APIRouter(prefix="/states", tags=["states"])

@router.get("")
async def list_states(
    _claims: dict = Depends(require_auth),  # 🔐 must have a valid bearer token
    session: AsyncSession = Depends(get_session),
):
    # Replace with real table queries. Simple demo:
    rows = await session.execute(
        sa.text("SELECT 'CA' AS code, 'California' AS name UNION ALL SELECT 'NY','New York'")
    )
    return [dict(r) for r in rows.mappings()]
