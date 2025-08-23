# src/OSSS/api/routers/sis_behavior_codes.py
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth import require_auth
from OSSS.db import get_session

router = APIRouter(prefix="/sis/settings", tags=["sis"])

# ---------- Schemas ----------
class BehaviorCodeCreate(BaseModel):
    code: str = Field(..., min_length=1, description="Unique behavior code (e.g., TARDY)")
    description: str = Field(..., min_length=1, description="Human-friendly description")

class BehaviorCodeOut(BaseModel):
    code: str
    description: str


# ---------- Routes ----------

@router.get("/behavior_codes", response_model=list[BehaviorCodeOut])
async def list_behavior_codes(
    _claims: dict = Depends(require_auth),  # 🔐 must have a valid bearer token
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        sa.text("SELECT code, description FROM behavior_codes ORDER BY code")
    )
    return list(result.mappings().all())


@router.get("/behavior_codes/{code}", response_model=BehaviorCodeOut)
async def get_behavior_code(
    code: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        sa.text("SELECT code, description FROM behavior_codes WHERE code = :code").bindparams(code=code.upper())
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Behavior code not found")
    return dict(row)


@router.post("/behavior_codes", response_model=BehaviorCodeOut, status_code=status.HTTP_201_CREATED)
async def create_behavior_code(
    payload: BehaviorCodeCreate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """Create a behavior code. Assumes a UNIQUE constraint on behavior_codes.code."""
    code = payload.code.upper()
    try:
        await session.execute(
            sa.text(
                "INSERT INTO behavior_codes (code, description) VALUES (:code, :description)"
            ).bindparams(code=code, description=payload.description)
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Behavior code already exists")

    return {"code": code, "description": payload.description}


@router.delete("/behavior_codes/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_behavior_code(
    code: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        sa.text("DELETE FROM behavior_codes WHERE code = :code RETURNING code")
        .bindparams(code=code.upper())
    )
    deleted = result.scalar_one_or_none()
    if deleted is None:
        # For DBs that don't support RETURNING, you could do a preceding SELECT
        # or check rowcount on the result (dialect-dependent).
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Behavior code not found")

    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

