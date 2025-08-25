# schemas/personalnote.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PersonalNoteCreate(BaseModel):
    user_id: str
    entity_type: str
    entity_id: str
    text: Optional[str] = None


class PersonalNoteOut(ORMBase):
    id: str
    user_id: str
    entity_type: str
    entity_id: str
    text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
