# src/OSSS/api/routers/states.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa
from OSSS.db.session import get_session
from OSSS.auth.dependencies import require_auth
from OSSS.schemas.state import StateOut

router = APIRouter(prefix="", tags=["states"])

@router.get("/states", response_model=list[StateOut])
async def list_states(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.execute(sa.text("""
        SELECT 'CA' AS code, 'California' AS name
         UNION ALL SELECT 'NY','New York'
    """))
    return list(rows.mappings())
