# src/OSSS/api/routers/states.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.states import State
from OSSS.schemas.state import StateOut

router = APIRouter(prefix="/admin/settings", tags=["admin"])

# --------- Schemas (input) ---------
class StateCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=2, description="Two-letter state code")
    name: str = Field(..., min_length=1, description="Full state name")


# --------- Routes ---------

@router.get("/states", response_model=list[StateOut])
async def list_states(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> list[StateOut]:
    """
    Return all states from the database.
    Requires a valid Bearer token (accepted audiences include osss-api and osss-web).
    """
    result = await session.execute(select(State).order_by(State.code))
    states = result.scalars().all()
    return [StateOut.model_validate(s) for s in states]


@router.get("/states/{code}", response_model=StateOut)
async def get_state(
    code: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> StateOut:
    """Return a single state by its two-letter code."""
    code = code.upper()
    result = await session.execute(select(State).where(State.code == code))
    obj = result.scalars().first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="State not found")
    return StateOut.model_validate(obj)


@router.post("/states", response_model=StateOut, status_code=status.HTTP_201_CREATED)
async def create_state(
    payload: StateCreate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> StateOut:
    """Create a new state (code must be unique)."""
    # normalize code to uppercase
    new_state = State(code=payload.code.upper(), name=payload.name)
    session.add(new_state)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="State code already exists")
    await session.refresh(new_state)
    return StateOut.model_validate(new_state)


@router.delete("/states/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_state(
    code: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete a state by its two-letter code."""
    code = code.upper()
    result = await session.execute(select(State).where(State.code == code))
    obj = result.scalars().first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="State not found")

    await session.delete(obj)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
