# src/OSSS/api/routers/states.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.state import State
from OSSS.schemas.state import StateOut

router = APIRouter(prefix="", tags=["states"])

@router.get("/states", response_model=list[StateOut])
async def list_states(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> list[StateOut]:
    """
    Return all states from the database.
    Requires a valid Bearer token (accepted audiences include osss-api and osss-web).
    """
    result = await session.execute(
        select(State).order_by(State.code)  # or .order_by(State.name)
    )
    states = result.scalars().all()

    # Pydantic v2: from_attributes=True on StateOut makes this work
    return [StateOut.model_validate(s) for s in states]
