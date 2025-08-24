# src/OSSS/api/routers/organizations.py
from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.organizations import Organization

router = APIRouter(prefix="/admin/settings", tags=["admin"])

# --------- Schemas (input/output) ---------
class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Organization name (unique)")
    code: Optional[str] = Field(None, description="Optional unique organization code")

class OrganizationOut(BaseModel):
    id: UUID
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Pydantic v2 way to read from SQLAlchemy objects
    model_config = ConfigDict(from_attributes=True)

# --------- Routes ---------

@router.get("/organizations", response_model=list[OrganizationOut])
async def list_organizations(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> list[OrganizationOut]:
    result = await session.execute(select(Organization).order_by(Organization.name))
    rows = result.scalars().all()
    return [OrganizationOut.model_validate(d) for d in rows]

@router.get("/organizations/{organization_id}", response_model=OrganizationOut)
async def get_organization(
    organization_id: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> OrganizationOut:
    obj = await session.get(Organization, organization_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationOut.model_validate(obj)

@router.post("/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> OrganizationOut:
    new_obj = Organization(name=payload.name, code=payload.code)
    session.add(new_obj)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization with this name or code already exists",
        )
    await session.refresh(new_obj)
    return OrganizationOut.model_validate(new_obj)

@router.delete("/organizations/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> Response:
    obj = await session.get(Organization, organization_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    await session.delete(obj)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
