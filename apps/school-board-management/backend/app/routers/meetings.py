from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models, schemas
from typing import List
from ..auth import current_user

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.post("/", response_model=schemas.Meeting)
def create_meeting(payload: schemas.MeetingIn, db: Session = Depends(get_db), user: dict = Depends(current_user)):
    m = models.Meeting(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

@router.get("/", response_model=List[schemas.Meeting])
def list_meetings(db: Session = Depends(get_db)):
    return db.query(models.Meeting).order_by(models.Meeting.start_at.desc()).all()

@router.get("/{meeting_id}", response_model=schemas.Meeting)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    m = db.get(models.Meeting, meeting_id)
    if not m:
        raise HTTPException(404, "Meeting not found")
    return m

@router.post("/{meeting_id}/agenda", response_model=schemas.AgendaItem)
def add_agenda(meeting_id: int, item: schemas.AgendaItemIn, db: Session = Depends(get_db), user: dict = Depends(current_user)):
    if not db.get(models.Meeting, meeting_id):
        raise HTTPException(404, "Meeting not found")
    a = models.AgendaItem(meeting_id=meeting_id, **item.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a
