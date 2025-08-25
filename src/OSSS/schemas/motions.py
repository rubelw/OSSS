from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MotionCreate(BaseModel):
    agenda_item_id: str
    text: str
    moved_by_id: Optional[str] = None
    seconded_by_id: Optional[str] = None
    passed: Optional[bool] = None
    tally_for: Optional[int] = None
    tally_against: Optional[int] = None
    tally_abstain: Optional[int] = None


class MotionOut(ORMBase):
    id: str
    agenda_item_id: str
    text: str
    moved_by_id: Optional[str] = None
    seconded_by_id: Optional[str] = None
    passed: Optional[bool] = None
    tally_for: Optional[int] = None
    tally_against: Optional[int] = None
    tally_abstain: Optional[int] = None
