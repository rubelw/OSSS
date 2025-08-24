# src/OSSS/api/routers/admin_settings_standardized_tests.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.sis import StandardizedTest  # adjust path if different

router = APIRouter(prefix="/sis/settings", tags=["sis"])

# -------------------- Schemas --------------------

class StandardizedTestCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Assessment name (e.g., ISASP)")
    subject: Optional[str] = Field(
        None,
        description="Subject(s). For multiple, use a delimiter like ';' (e.g., 'Math; ELA; Science').",
    )

class StandardizedTestUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    subject: Optional[str] = None

class StandardizedTestOut(BaseModel):
    id: UUID
    name: str
    subject: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# -------------------- Routes --------------------

@router.get("/standardized_tests", response_model=list[StandardizedTestOut])
async def list_standardized_tests(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
    q: Optional[str] = Query(
        default=None,
        description="Case-insensitive search on name (e.g., 'iowa')",
    ),
) -> list[StandardizedTestOut]:
    stmt = select(StandardizedTest)
    if q:
        stmt = stmt.where(StandardizedTest.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(StandardizedTest.name.asc())

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [StandardizedTestOut.model_validate(r) for r in rows]


@router.get("/standardized_tests/{test_id}", response_model=StandardizedTestOut)
async def get_standardized_test(
    test_id: UUID,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> StandardizedTestOut:
    obj = await session.get(StandardizedTest, str(test_id))
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standardized test not found")
    return StandardizedTestOut.model_validate(obj)


@router.post("/standardized_tests", response_model=StandardizedTestOut, status_code=status.HTTP_201_CREATED)
async def create_standardized_test(
    payload: StandardizedTestCreate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> StandardizedTestOut:
    obj = StandardizedTest(
        name=payload.name,
        subject=payload.subject,
    )
    session.add(obj)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # In case you later add a unique constraint on name
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A standardized test with this name already exists")
    await session.refresh(obj)
    return StandardizedTestOut.model_validate(obj)


@router.patch("/standardized_tests/{test_id}", response_model=StandardizedTestOut)
async def update_standardized_test(
    test_id: UUID,
    payload: StandardizedTestUpdate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> StandardizedTestOut:
    obj = await session.get(StandardizedTest, str(test_id))
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standardized test not found")

    if payload.name is not None:
        obj.name = payload.name
    if payload.subject is not None:
        obj.subject = payload.subject

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Constraint violation updating standardized test")
    await session.refresh(obj)
    return StandardizedTestOut.model_validate(obj)


@router.delete("/standardized_tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_standardized_test(
    test_id: UUID,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> Response:
    obj = await session.get(StandardizedTest, str(test_id))
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standardized test not found")
    await session.delete(obj)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

