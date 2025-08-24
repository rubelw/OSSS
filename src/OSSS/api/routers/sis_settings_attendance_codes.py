# src/OSSS/api/routers/admin_settings_attendance_codes.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.sis import AttendanceCode  # adjust path if needed

router = APIRouter(prefix="/sis/settings", tags=["sis"])

# -------------------- Schemas --------------------

class AttendanceCodeCreate(BaseModel):
    code: str = Field(..., min_length=1, description="Short code, e.g. 'P', 'A-EXC'")
    description: Optional[str] = Field(None, description="Human-readable description")
    is_present: bool = False
    is_excused: bool = False


class AttendanceCodeUpdate(BaseModel):
    description: Optional[str] = None
    is_present: Optional[bool] = None
    is_excused: Optional[bool] = None


class AttendanceCodeOut(BaseModel):
    code: str
    description: Optional[str] = None


    model_config = ConfigDict(from_attributes=True)

# -------------------- Routes --------------------

@router.get("/attendance_codes", response_model=list[AttendanceCodeOut])
async def list_attendance_codes(
    _claims: dict = Depends(require_auth),  # 🔐 must have a valid bearer token
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        sa.text("SELECT code, description FROM attendance_codes ORDER BY code")
    )
    return list(result.mappings().all())



@router.get("/attendance_codes/{code}", response_model=AttendanceCodeOut)
async def get_attendance_code(
    code: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> AttendanceCodeOut:
    obj = await session.get(AttendanceCode, code.upper())
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance code not found")
    return AttendanceCodeOut.model_validate(obj)


@router.post("/attendance_codes", response_model=AttendanceCodeOut, status_code=status.HTTP_201_CREATED)
async def create_attendance_code(
    payload: AttendanceCodeCreate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> AttendanceCodeOut:
    code_norm = payload.code.strip().upper()
    obj = AttendanceCode(
        code=code_norm,
        description=payload.description,
        is_present=payload.is_present,
        is_excused=payload.is_excused,
    )
    session.add(obj)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance code already exists",
        )
    await session.refresh(obj)
    return AttendanceCodeOut.model_validate(obj)


@router.patch("/attendance_codes/{code}", response_model=AttendanceCodeOut)
async def update_attendance_code(
    code: str,
    payload: AttendanceCodeUpdate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> AttendanceCodeOut:
    obj = await session.get(AttendanceCode, code.upper())
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance code not found")

    if payload.description is not None:
        obj.description = payload.description
    if payload.is_present is not None:
        obj.is_present = payload.is_present
    if payload.is_excused is not None:
        obj.is_excused = payload.is_excused

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Constraint violation updating attendance code",
        )
    await session.refresh(obj)
    return AttendanceCodeOut.model_validate(obj)


@router.delete("/attendance_codes/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attendance_code(
    code: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> Response:
    obj = await session.get(AttendanceCode, code.upper())
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance code not found")

    await session.delete(obj)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
