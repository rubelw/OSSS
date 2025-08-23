from __future__ import annotations
import secrets
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.auth.dependencies import require_auth
from OSSS.db.session import get_session
from OSSS.db.models.activities import Activity, Event, TicketType, Order, Ticket, TicketScan
from OSSS.schemas.activities import (
    ActivityIn, ActivityOut,
    EventIn, EventOut,
    TicketTypeIn, TicketTypeOut,
    OrderCreate, OrderOut, TicketOut,
    ScanRequest, ScanResult
)

router = APIRouter(prefix="/activities", tags=["activities"])

# ----- Activities -----
@router.get("/activities", response_model=list[ActivityOut])
async def list_activities(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.scalars(select(Activity).order_by(Activity.name))
    return [ActivityOut.model_validate(a) for a in rows.all()]

@router.post("/activities", response_model=ActivityOut, status_code=201)
async def create_activity(
    payload: ActivityIn,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    a = Activity(**payload.model_dump())
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return ActivityOut.model_validate(a)

# ----- Events -----
@router.get("/events", response_model=list[EventOut])
async def list_events(
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.scalars(select(Event).order_by(Event.starts_at.desc()))
    return [EventOut.model_validate(e) for e in rows.all()]

@router.post("/events", response_model=EventOut, status_code=201)
async def create_event(
    payload: EventIn,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    e = Event(**payload.model_dump())
    session.add(e)
    await session.commit()
    await session.refresh(e)
    return EventOut.model_validate(e)

@router.get("/events/{event_id}", response_model=EventOut)
async def get_event(
    event_id: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    e = await session.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    return EventOut.model_validate(e)

# ----- Ticket types -----
@router.get("/events/{event_id}/ticket_types", response_model=list[TicketTypeOut])
async def list_ticket_types(
    event_id: str,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.scalars(select(TicketType).where(TicketType.event_id == event_id).order_by(TicketType.name))
    return [TicketTypeOut.model_validate(t) for t in rows.all()]

@router.post("/events/{event_id}/ticket_types", response_model=TicketTypeOut, status_code=201)
async def create_ticket_type(
    event_id: str,
    payload: TicketTypeIn,
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    t = TicketType(event_id=event_id, **payload.model_dump())
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return TicketTypeOut.model_validate(t)

# ----- Orders / Tickets -----
@router.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreate,
    claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    # Compute totals and availability
    tt_ids = [i.ticket_type_id for i in payload.items]
    ttypes = (await session.scalars(select(TicketType).where(TicketType.id.in_(tt_ids)))).all()
    ttype_map = {t.id: t for t in ttypes}

    if any(i.ticket_type_id not in ttype_map for i in payload.items):
        raise HTTPException(400, "Unknown ticket type")

    total_cents = 0
    for i in payload.items:
        t = ttype_map[i.ticket_type_id]
        remaining = t.quantity_total - t.quantity_sold
        if i.quantity > remaining:
            raise HTTPException(409, f"Insufficient inventory for {t.name} (remaining {remaining})")
        total_cents += t.price_cents * i.quantity

    # Create order
    o = Order(
        event_id=payload.event_id,
        purchaser_user_id=claims.get("sub"),
        total_cents=total_cents,
        status="paid" if total_cents == 0 else "pending",
    )
    session.add(o)
    await session.flush()  # get o.id

    # Create tickets and bump sold count
    tickets: list[Ticket] = []
    for i in payload.items:
        t = ttype_map[i.ticket_type_id]

        # determine next serial
        next_serial = (await session.scalar(
            select(func.coalesce(func.max(Ticket.serial_no), 0) + 1).where(Ticket.ticket_type_id == t.id)
        )) or 1

        for _ in range(i.quantity):
            tk = Ticket(
                order_id=o.id,
                ticket_type_id=t.id,
                serial_no=next_serial,
                price_cents=t.price_cents,
                qr_code=secrets.token_urlsafe(16),
            )
            tickets.append(tk)
            next_serial += 1

        t.quantity_sold += i.quantity
        session.add(t)

    session.add_all(tickets)
    await session.commit()
    await session.refresh(o)

    # load tickets for response
    tks = (await session.scalars(select(Ticket).where(Ticket.order_id == o.id))).all()
    return OrderOut.model_validate(o, update={"tickets": [TicketOut.model_validate(x) for x in tks]})

@router.post("/tickets/scan", response_model=ScanResult)
async def scan_ticket(
    body: ScanRequest,
    claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    tk = (await session.scalars(select(Ticket).where(Ticket.qr_code == body.qr_code))).first()
    if not tk:
        scan = TicketScan(ticket_id="00000000-0000-0000-0000-000000000000",  # dummy
                          scanned_by_user_id=claims.get("sub"), result="invalid", location=body.location)
        session.add(scan)
        await session.commit()
        return ScanResult(ok=False, message="Invalid ticket")

    if tk.status == "void":
        result = "void"
        ok = False
        msg = "Ticket void"
    elif tk.status == "checked_in":
        result = "duplicate"
        ok = False
        msg = "Already checked in"
    else:
        tk.status = "checked_in"
        tk.checked_in_at = sa.func.now()
        result = "ok"
        ok = True
        msg = "Checked in"

    scan = TicketScan(ticket_id=tk.id, scanned_by_user_id=claims.get("sub"), result=result, location=body.location)
    session.add(scan)
    await session.commit()
    return ScanResult(ok=ok, ticket_id=tk.id, status=tk.status, message=msg)
