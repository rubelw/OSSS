# src/OSSS/api/routers/transport_bus_routes.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, status

from pydantic import BaseModel, ConfigDict, Field

# Adjust these imports to your project layout as needed:
from OSSS.db.session import get_session
from OSSS.db.models.sis import BusRoute  # <-- update if model lives elsewhere

router = APIRouter(prefix="/transport/bus_routes", tags=["transportation"])


# -------------------------
# Pydantic Schemas (v2)
# -------------------------
class BusRouteBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    school_id: Optional[UUID] = Field(
        None, description="GUID of the school this route is primarily associated to"
    )


class BusRouteCreate(BusRouteBase):
    pass


class BusRouteUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    # Pass null to clear school_id, omit to leave unchanged
    school_id: Optional[Optional[UUID]] = None


class BusRouteOut(BusRouteBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Helpers
# -------------------------
async def _get_route_or_404(session: AsyncSession, route_id: UUID) -> BusRoute:
    result = await session.execute(
        sa.select(BusRoute).where(BusRoute.id == str(route_id))
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Bus route not found")
    return route


# -------------------------
# Routes
# -------------------------
@router.get("", response_model=list[BusRouteOut])
async def list_bus_routes(
    session: AsyncSession = Depends(get_session),
    school_id: Optional[UUID] = None,
    limit: int = 100,
    offset: int = 0,
    order: str = "name",  # name | created_at | updated_at
    desc: bool = False,
):
    stmt = sa.select(BusRoute)

    if school_id is not None:
        stmt = stmt.where(BusRoute.school_id == str(school_id))

    order_col = {
        "name": BusRoute.name,
        "created_at": BusRoute.created_at,
        "updated_at": BusRoute.updated_at,
    }.get(order, BusRoute.name)
    if desc:
        order_col = order_col.desc()

    stmt = stmt.order_by(order_col).limit(limit).offset(offset)

    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{route_id}", response_model=BusRouteOut)
async def get_bus_route(
    route_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await _get_route_or_404(session, route_id)


@router.post("", response_model=BusRouteOut, status_code=status.HTTP_201_CREATED)
async def create_bus_route(
    payload: BusRouteCreate,
    session: AsyncSession = Depends(get_session),
):
    route = BusRoute(
        name=payload.name,
        school_id=str(payload.school_id) if payload.school_id else None,
    )
    session.add(route)
    try:
        await session.flush()
        await session.refresh(route)
    except IntegrityError as e:
        await session.rollback()
        # No unique constraint on name by default, but catch any DB issues
        raise HTTPException(status_code=400, detail="Failed to create bus route.") from e
    return route


@router.patch("/{route_id}", response_model=BusRouteOut)
async def update_bus_route(
    route_id: UUID,
    payload: BusRouteUpdate,
    session: AsyncSession = Depends(get_session),
):
    route = await _get_route_or_404(session, route_id)

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        route.name = data["name"]

    # school_id behavior: omit => unchanged; null => clear; UUID => set
    if "school_id" in data:
        val = data["school_id"]
        route.school_id = str(val) if val else None

    try:
        await session.flush()
        await session.refresh(route)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Failed to update bus route.") from e

    return route


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bus_route(
    route_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    route = await _get_route_or_404(session, route_id)
    await session.delete(route)
    await session.flush()
    return None
